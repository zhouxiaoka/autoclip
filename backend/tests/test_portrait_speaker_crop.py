"""9:16 crops follow the frontal speaker and keep a group inside the frame.

Synthetic footage uses the bundled example face. One head is a real frontal face.
The other is a turned crop that YuNet still boxes, with the eyes collapsed and the
nose outside them, and it is larger and moves more. The group still is three
frontal faces. On the 9:16 path the old largest-or-loudest face crop centres the
turned head and slices the group down to one person.
"""
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.services.studio import framing
from backend.services.studio.models import Draft, Scene
from backend.services.studio.qa import face
from backend.services.studio.qa.report import Context, SceneSpan
from backend.utils.ffmpeg_utils import get_ffmpeg_path

COVER = Path(__file__).resolve().parents[1] / 'assets' / 'example' / 'cover.jpg'
SOURCE = (960, 540)
FPS = 12
SWITCH_AT = 7.0
TALK_LENGTH = 14.0


def _faces():
    cover = cv2.imread(str(COVER))
    assert cover is not None, 'bundled example cover is required'
    # Frontal face (right subject on the cover) and the turned head (left subject).
    # YuNet keeps a box on the turned crop, but the eyes collapse and the nose
    # leaves the eye span, which is the back-of-head / turned-away case.
    frontal = cover[50:150, 450:560]
    turned = cover[40:150, 80:200]
    assert frontal.size and turned.size
    return frontal, turned


def _blit(canvas, face, cx, cy):
    height, width = face.shape[:2]
    x, y = int(cx - width / 2), int(cy - height / 2)
    canvas[y:y + height, x:x + width] = face


def _talk_frame(frontal, turned, second, tick):
    image = np.full((SOURCE[1], SOURCE[0], 3), (22, 22, 20), np.uint8)
    speaker = cv2.resize(frontal, (110, 140))
    other = cv2.resize(turned, (200, 230))
    if tick:
        # A small mouth change keeps YuNet's box. Blacking the mouth out drops the speaker.
        speaker = speaker.copy()
        speaker[86:104, 36:74] = (speaker[86:104, 36:74].astype(np.int16) * 0.45).astype(np.uint8)
        other = np.roll(other, 10, axis=0)
    host_side = 'left' if second < SWITCH_AT else 'right'
    slots = {'left': (170, 250), 'right': (760, 270)}
    other_side = 'right' if host_side == 'left' else 'left'
    _blit(image, speaker, *slots[host_side])
    _blit(image, other, *slots[other_side])
    return image


def _encode(folder, count, path, extra=()):
    subprocess.run(
        [get_ffmpeg_path(), '-y', '-v', 'error', '-framerate', str(FPS), '-i', str(folder / '%04d.jpg'),
         '-frames:v', str(count), *extra, '-pix_fmt', 'yuv420p', str(path)],
        check=True, capture_output=True, timeout=60,
    )


def _talk_video(tmp_path):
    frontal, turned = _faces()
    folder = tmp_path / 'talk'
    folder.mkdir()
    count = int(TALK_LENGTH * FPS)
    for index in range(count):
        cv2.imwrite(str(folder / f'{index:04d}.jpg'), _talk_frame(frontal, turned, index / FPS, index % 2 == 1))
    path = tmp_path / 'talk.mp4'
    _encode(folder, count, path)
    return path


def _group_video(tmp_path):
    frontal, _turned = _faces()
    folder = tmp_path / 'group'
    folder.mkdir()
    image = np.full((SOURCE[1], SOURCE[0], 3), (28, 28, 26), np.uint8)
    face_image = cv2.resize(frontal, (120, 150))
    for cx in (180, 480, 780):
        _blit(image, face_image, cx, 270)
    count = FPS * 2
    for index in range(count):
        cv2.imwrite(str(folder / f'{index:04d}.jpg'), image)
    path = tmp_path / 'group.mp4'
    _encode(folder, count, path)
    return path


def _cues():
    return [
        {'start': 0.0, 'end': SWITCH_AT, 'text': '[host] I am on this side.', 'speaker': 'host'},
        {'start': SWITCH_AT, 'end': TALK_LENGTH, 'text': '[guest] And now I am speaking.', 'speaker': 'guest'},
    ]


def _frame_at(video, at):
    proc = subprocess.run(
        [get_ffmpeg_path(), '-v', 'error', '-ss', f'{at:.3f}', '-i', str(video), '-frames:v', '1',
         '-vf', 'scale=480:-2', '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1'],
        check=True, capture_output=True, timeout=20,
    )
    image = cv2.imdecode(np.frombuffer(proc.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def _detected(image):
    height, width = image.shape[:2]
    detector = cv2.FaceDetectorYN.create(
        str(framing.MODEL), '', (width, height), score_threshold=0.6, nms_threshold=0.3, top_k=20,
    )
    _scores, found = detector.detect(image)
    assert found is not None and len(found) >= 1
    rows = []
    for face_row in found:
        box_w = float(face_row[2])
        nose = float(face_row[8])
        left_eye, right_eye = sorted((float(face_row[4]), float(face_row[6])))
        if nose < left_eye:
            outside = (left_eye - nose) / box_w
        elif nose > right_eye:
            outside = (nose - right_eye) / box_w
        else:
            outside = 0.0
        rows.append({
            'x': (float(face_row[0]) + box_w / 2) / width,
            'outside': outside,
            'w': box_w / width,
        })
    return rows


def _frontal_and_turned(image):
    rows = _detected(image)
    assert len(rows) >= 2, rows
    frontal = min(rows, key=lambda row: row['outside'])
    turned = max(rows, key=lambda row: row['outside'])
    # The turned head's nose sits outside the eyes. The speaker's does not.
    assert frontal['outside'] <= 0.05, rows
    assert turned['outside'] >= 0.10, rows
    assert abs(frontal['x'] - turned['x']) > 0.35, rows
    return frontal, turned


def _active_point(track, at):
    current = track[0]
    for point in track:
        if point['start'] <= at + 1e-6:
            current = point
    return current


def _window(crop_x, fraction):
    left = crop_x * (1 - fraction)
    return left, left + fraction


def _auto_frame(video, draft, cues):
    kwargs = {'cues': cues} if 'cues' in framing.auto_frame.__code__.co_varnames else {}
    return framing.auto_frame(video, draft, *SOURCE, **kwargs)


def test_crop_follows_the_frontal_speaker_when_the_other_head_is_turned_away(tmp_path):
    video = _talk_video(tmp_path)
    early = _frame_at(video, 1.0)
    late = _frame_at(video, 11.0)
    host, host_turned = _frontal_and_turned(early)
    guest, guest_turned = _frontal_and_turned(late)
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='talk', label='a', start=0, end=TALK_LENGTH)])
    result = _auto_frame(video, draft, _cues())
    scene = result['scenes'][0]
    fraction = result['window_fraction']
    track = scene['crop_track']
    assert track, scene

    def shown(at, speaker, other):
        point = _active_point(track, at)
        assert point['mode'] == 'crop', (at, track)
        left, right = _window(point['crop_x'], fraction)
        assert left <= speaker['x'] <= right, (at, speaker, other, point, track)
        assert not (left <= other['x'] <= right), (at, speaker, other, point, track)

    shown(1.0, host, host_turned)
    shown(11.0, guest, guest_turned)
    # One direction of travel. A reversal inside the jitter window is a flash.
    from backend.services.studio.qa import jitter
    assert jitter.flashes([(point['start'], point['crop_x']) for point in track], 1080) == 0


def test_group_still_fits_everyone_instead_of_cropping_to_one_face(tmp_path):
    video = _group_video(tmp_path)
    image = _frame_at(video, 0.4)
    found = _detected(image)
    assert len(found) >= 3
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='group', label='a', start=0, end=2)])
    result = _auto_frame(video, draft, [])
    scene = result['scenes'][0]
    track = scene['crop_track']
    assert track and all(point['mode'] == 'fit' for point in track), track
    graph = framing.layout_filter(Scene(id='group', label='a', start=0, end=2, crop_track=track), 0.5, 1080, 1920)
    assert 'gblur' in graph and 'overlay' in graph
    # A group that cannot share the window is a justified fit, even at 100%.
    group_qa = face.check(Context(
        output=video, source=video, width=1080, height=1920,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.5)], ['fit'])],
    ), 8)
    assert group_qa[0] != 'fail', group_qa


def test_face_qa_fails_when_the_turned_head_is_framed_for_more_than_a_second(tmp_path):
    video = _talk_video(tmp_path)
    image = _frame_at(video, 1.0)
    _speaker, turned = _frontal_and_turned(image)
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    bad = framing.crop_x_for_center(turned['x'], fraction)
    good_image_speaker, _other = _frontal_and_turned(image)
    good = framing.crop_x_for_center(good_image_speaker['x'], fraction)

    def outcome(length, crop_x):
        ctx = Context(
            output=video, source=video, width=1080, height=1920,
            scenes=[SceneSpan(0.0, length, [(0.0, crop_x)])],
        )
        return face.check(ctx, 8)

    assert outcome(2.0, bad) == ('fail', 'back_of_head')
    assert outcome(0.8, bad)[0] != 'fail'
    held = outcome(2.0, good)
    assert held[0] != 'fail', held
    fitted = face.check(Context(
        output=video, source=video, width=1080, height=1920,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.5)], ['fit'])],
    ), 8)
    assert fitted == ('fail', 'fit_heavy'), fitted


def test_cues_read_explicit_labels_and_gtgt_turns():
    explicit = framing.cues_from_entries([
        {'start': 0, 'end': 1, 'text': '[host] hello'},
        {'start': 1, 'end': 2, 'text': 'still me'},
        {'start': 2, 'end': 3, 'text': 'Guest: now me'},
    ])
    # One `Guest:` does not switch the speaker. The same name has to label two cues.
    assert [cue['speaker'] for cue in explicit] == ['host', 'host', 'host']
    repeated = framing.cues_from_entries([
        {'start': 0, 'end': 1, 'text': 'Jensen: hello'},
        {'start': 1, 'end': 2, 'text': 'still talking'},
        {'start': 2, 'end': 3, 'text': 'Jensen: again'},
    ])
    assert [cue['speaker'] for cue in repeated] == ['Jensen', 'Jensen', 'Jensen']
    once = framing.cues_from_entries([
        {'start': 0, 'end': 1, 'text': 'Guest: hello once'},
        {'start': 1, 'end': 2, 'text': 'and the line continues'},
    ])
    assert all('speaker' not in cue for cue in once)
    turns = framing.cues_from_entries([
        {'start_time': '00:00:00,000', 'end_time': '00:00:01,000', 'text': 'intro'},
        {'start_time': '00:00:01,000', 'end_time': '00:00:02,000', 'text': '>> answer'},
        {'start_time': '00:00:02,050', 'end_time': '00:00:03,000', 'text': '>> more'},
        {'start_time': '00:00:05,000', 'end_time': '00:00:06,000', 'text': '>> later'},
    ])
    assert [cue['speaker'] for cue in turns] == ['speaker_a', 'speaker_b', 'speaker_a', 'speaker_b']


def test_binding_stays_on_the_speaker_when_someone_else_is_louder():
    samples = [
        {'offset': 0.3, 't': 0.3, 'frontal': [
            {'x': 0.2, 'w': 0.1, 'motion': 8, 'area': 1},
            {'x': 0.8, 'w': 0.1, 'motion': 0, 'area': 1},
        ], 'turned': []},
        {'offset': 2.8, 't': 2.8, 'frontal': [
            {'x': 0.2, 'w': 0.1, 'motion': 3, 'area': 1},
            {'x': 0.8, 'w': 0.1, 'motion': 15, 'area': 1},
        ], 'turned': []},
        {'offset': 8.0, 't': 8.0, 'frontal': [
            {'x': 0.2, 'w': 0.1, 'motion': 0, 'area': 1},
            {'x': 0.8, 'w': 0.1, 'motion': 9, 'area': 1},
        ], 'turned': []},
    ]
    cues = [
        {'start': 0, 'end': 6, 'speaker': 'host', 'text': '[host] a'},
        {'start': 6, 'end': 12, 'speaker': 'guest', 'text': '[guest] b'},
    ]
    binding = framing.bind_speakers(samples, cues)
    assert binding['host'] == pytest.approx(0.2)
    assert binding['guest'] == pytest.approx(0.8)
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    assert framing._center_for(samples[1], binding, cues, fraction) == pytest.approx(0.2)
    group = {'offset': 0.2, 't': 0.2, 'frontal': [
        {'x': 0.19, 'w': 0.12, 'motion': 0, 'area': 1},
        {'x': 0.50, 'w': 0.12, 'motion': 0, 'area': 1},
        {'x': 0.81, 'w': 0.12, 'motion': 0, 'area': 1},
    ], 'turned': []}
    assert framing._center_for(group, {}, [], fraction) is None
    points = framing.frame_observed([group, {**group, 'offset': 1.0, 't': 1.0}], 0.0, 2.0, fraction, [], {})
    assert points and all(point['mode'] == 'fit' for point in points)


def test_crop_expression_eases_an_interior_pan_and_keeps_a_hard_cut():
    eased = Scene(id='s', label='a', start=0, end=20, crop_track=[
        {'start': 0, 'crop_x': 0.3},
        {'start': 10, 'crop_x': 0.8, 'ease': 0.45},
    ])
    expression = framing.crop_expression(eased, 0.5)
    assert expression == "if(lt(t,10.0),0.3,if(lt(t,10.45),(0.3+(0.5)*(t-10.0)/0.45),0.8))"
    hard = Scene(id='s', label='a', start=0, end=30, crop_track=[
        {'start': 0, 'crop_x': .3}, {'start': 10, 'crop_x': .8}, {'start': 17.5, 'crop_x': .3},
    ])
    assert framing.crop_expression(hard, .5) == "if(lt(t,17.5),if(lt(t,10.0),0.3,0.8),0.3)"


def _face_row(score, eye_ratio, outside_ratio, *, x=40, box_w=80):
    """A YuNet row. `outside_ratio` pushes the nose past the right eye."""
    height = 100
    eye_span = eye_ratio * box_w
    center = x + box_w / 2
    eye_y, nose_y, mouth_y = 70, 88, 110
    right_eye = center - eye_span / 2
    left_eye = center + eye_span / 2
    return [
        x, 40, box_w, height,
        right_eye, eye_y, left_eye, eye_y,
        left_eye + outside_ratio * box_w, nose_y,
        center - 8, mouth_y, center + 8, mouth_y,
        score,
    ]


def _fit_percent(track, length):
    return framing.fit_ratio(track, length) * 100


def _flash_rate(track, length, width=1080):
    from backend.services.studio.qa import jitter
    count = jitter.flashes([(point['start'], point['crop_x']) for point in track], width, [point['mode'] for point in track])
    return count / max(length, 1e-3) * 60


def _scans(samples, length, faces):
    return [{'shots': [(0.0, float(length), samples)], 'faces': faces, 'samples': len(samples)}]


def test_unlabeled_transcript_follows_each_talking_face_and_ignores_look(tmp_path):
    cues = framing.cues_from_entries([
        {'start': 0, 'end': 8, 'text': 'we did not have our best year'},
        {'start': 8, 'end': 16, 'text': 'Look: the other person is asking now'},
        {'start': 16, 'end': 20, 'text': 'and the answer keeps going'},
    ])
    assert cues and all('speaker' not in cue for cue in cues)
    samples = []
    for at in (0.4, 2.9, 5.4, 7.9, 10.4, 12.9, 15.4, 17.9):
        on_left = at < 8
        samples.append({'offset': at, 't': at, 'turned': [], 'frontal': [
            {'x': 0.25, 'w': 0.10, 'motion': 8 if on_left else 0, 'area': 1},
            {'x': 0.72, 'w': 0.10, 'motion': 0 if on_left else 8, 'area': 1},
        ]})
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='talk', label='a', start=0, end=20)])
    result = framing.auto_frame(tmp_path / 'clip.mp4', draft, *SOURCE, scans=_scans(samples, 20, 8), cues=cues)
    track = result['scenes'][0]['crop_track']
    fraction = result['window_fraction']
    assert _fit_percent(track, 20) == 0, track
    assert _flash_rate(track, 20) <= 1, (_flash_rate(track, 20), track)

    def contains(at, face_x, other_x):
        point = _active_point(track, at)
        left, right = _window(point['crop_x'], fraction)
        assert point['mode'] == 'crop'
        assert left <= face_x <= right
        assert not (left <= other_x <= right)

    contains(1.0, 0.25, 0.72)
    contains(16.0, 0.72, 0.25)


def test_single_speaker_stays_cropped_for_tiktok_and_classic(tmp_path):
    from backend.services.studio.jobs import INTERVIEW_WINDOW
    cues = framing.cues_from_entries([
        {'start': start, 'end': start + 3, 'text': 'one person keeps talking about the work'}
        for start in range(0, 12, 3)
    ])
    assert all('speaker' not in cue for cue in cues)
    samples = [
        {'offset': at, 't': at, 'turned': [], 'frontal': [{'x': 0.42, 'w': 0.12, 'motion': 1, 'area': 1}]}
        for at in (0.4, 2.9, 5.4, 7.9, 10.4)
    ]
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='solo', label='a', start=0, end=12)])
    for window in (None, INTERVIEW_WINDOW):
        result = framing.auto_frame(tmp_path / 'solo.mp4', draft, *SOURCE, window=window,
                                    scans=_scans(samples, 12, len(samples)), cues=cues)
        track = result['scenes'][0]['crop_track']
        assert _fit_percent(track, 12) == 0, (window, track)
        assert _flash_rate(track, 12) == 0, (window, track)
        assert all(point['mode'] == 'crop' for point in track)


def test_a_missing_bound_speaker_crops_the_one_face_that_is_there():
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    sample = {'offset': 1.0, 't': 1.0, 'turned': [], 'frontal': [{'x': 0.22, 'w': 0.10, 'motion': 0, 'area': 1}]}
    cues = [{'start': 0, 'end': 5, 'speaker': 'host', 'text': '[host] hello'}]
    assert framing._center_for(sample, {'host': 0.80}, cues, fraction) == pytest.approx(0.22)


def test_three_quarter_face_is_frontal_and_false_boxes_are_not():
    three_quarter = _face_row(0.91, 0.28, 0.082)
    assert framing.is_frontal(three_quarter)
    back_of_head = _face_row(0.64, 0.28, 0.0)
    assert not framing.is_frontal(back_of_head)
    false_box = _face_row(0.61, 0.40, 0.0, x=0, box_w=int(0.33 * 480))
    assert not framing._reliable_box(false_box, 480)
    stuck = _face_row(0.90, 0.40, 0.0, x=0, box_w=int(0.33 * 480))
    assert not framing._reliable_box(stuck, 480)


def test_a_one_off_false_face_does_not_pull_the_crop():
    real = {'x': 0.42, 'w': 0.10, 'motion': 2, 'area': 1}
    fake = {'x': 0.107, 'w': 0.33, 'motion': 0, 'area': 8}
    samples = []
    for at in (0.4, 2.9, 5.4, 7.9, 10.4):
        frontal = [dict(real)]
        if abs(at - 5.4) < 0.01:
            frontal.append(dict(fake))
        samples.append({'offset': at, 't': at, 'frontal': frontal, 'turned': []})
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    track = framing.frame_observed(samples, 0.0, 12.0, fraction, [], {})
    assert _fit_percent(track, 12) == 0, track
    point = _active_point(track, 6)
    left, right = _window(point['crop_x'], fraction)
    assert left <= 0.42 <= right
    assert not (left <= 0.107 <= right)


def test_every_gtgt_is_a_turn_and_a_rolling_line_is_not():
    rolling = framing.cues_from_entries([
        {'start': 0.0, 'end': 1.0, 'text': 'intro line'},
        {'start': 1.0, 'end': 2.0, 'text': '&gt;&gt; I think we were trying'},
        {'start': 1.4, 'end': 2.6, 'text': '&gt;&gt; I think we were trying to do too much'},
        {'start': 2.6, 'end': 3.4, 'text': '>> and now the other person'},
    ])
    assert [cue['speaker'] for cue in rolling] == ['speaker_a', 'speaker_b', 'speaker_a']
    assert 'too much' in rolling[1]['text']
    assert '&gt;' not in rolling[1]['text']


def test_parse_srt_keeps_markup_and_framing_unescapes_speaker_marks(tmp_path):
    from backend.utils.text_processor import TextProcessor
    srt = tmp_path / 'input.srt'
    srt.write_text(
        '1\n00:00:00,000 --> 00:00:01,000\nTom & Jerry <guest> paid\n\n'
        '2\n00:00:01,000 --> 00:00:02,000\n&gt;&gt; I think we were trying\n',
        encoding='utf-8',
    )
    parsed = TextProcessor.parse_srt(srt)
    assert parsed[0]['text'] == 'Tom & Jerry <guest> paid'
    assert '&' in parsed[0]['text'] and '<' in parsed[0]['text']
    assert parsed[1]['text'].startswith('&gt;&gt;')
    cues = framing.cues_from_entries(parsed)
    assert 'Tom & Jerry <guest> paid' in cues[0]['text']
    assert cues[1]['text'].startswith('>>')
    assert cues[1]['speaker'] == 'speaker_b'
    assert '&gt;' not in cues[1]['text']


def test_a_short_fit_blip_is_absorbed_and_a_fast_flip_still_flashes():
    from backend.services.studio.qa import jitter
    blip = [
        {'start': 0.0, 'crop_x': 0.2, 'mode': 'crop'},
        {'start': 3.0, 'crop_x': 0.5, 'mode': 'fit'},
        {'start': 3.4, 'crop_x': 0.2, 'mode': 'crop'},
    ]
    absorbed = framing._absorb_short(blip, 0.0, 10.0)
    assert _fit_percent(absorbed, 10) == 0, absorbed
    fast = [(0.0, 0.2), (0.2, 0.5), (0.5, 0.2)]
    assert jitter.flashes(fast, 1000, ['crop', 'fit', 'crop']) == 1
    held = [(0.0, 0.2), (5.0, 0.5), (10.0, 0.8)]
    assert jitter.flashes(held, 1000, ['crop', 'fit', 'crop']) == 0
    # Without modes the same 0.5 is a crop position, so the way back is a reversal.
    assert jitter.flashes(fast, 1000) == 1


def test_presence_fails_only_after_a_second_of_the_same_miss():
    assert face.judge_presence([(0.8, 'turned')])[0] == 'pass'
    assert face.judge_presence([(1.0, 'turned')])[0] == 'pass'
    assert face.judge_presence([(1.2, 'turned')]) == ('fail', 'back_of_head')
    assert face.judge_presence([(0.6, 'turned'), (0.6, 'turned')]) == ('fail', 'back_of_head')
    assert face.judge_presence([(0.6, 'missing'), (0.4, 'frontal'), (0.6, 'missing')])[0] == 'pass'
    assert face.judge_presence([(1.2, 'missing')]) == ('fail', 'speaker_out')
    assert face.judge_presence([(1.2, 'empty')]) == ('fail', 'no_face')
    assert face.judge_presence([(1.2, 'group')]) == ('fail', 'group_crop')
    assert face.judge_presence([(0.8, 'group')])[0] == 'pass'


def test_low_score_faces_keep_a_wide_shot_from_a_single_face_crop():
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    wide = {
        'offset': 0.5, 't': 1.0,
        'frontal': [{'x': 0.22, 'w': 0.08, 'motion': 6, 'area': 1, 'score': 0.91}],
        'turned': [
            {'x': 0.55, 'w': 0.04, 'motion': 0, 'area': 0.2, 'score': 0.55},
            {'x': 0.82, 'w': 0.035, 'motion': 0, 'area': 0.2, 'score': 0.50},
        ],
    }
    assert framing._center_for(wide, {}, [], fraction) is None
    pair = {
        'offset': 0.4, 't': 0.4,
        'frontal': [{'x': 0.20, 'w': 0.10, 'motion': 4, 'area': 1, 'score': 0.91}],
        'turned': [{'x': 0.75, 'w': 0.04, 'motion': 0, 'area': 0.2, 'score': 0.52}],
    }
    assert framing._center_for(pair, {}, [], fraction) is None
    # One frontal face and one high-score turned head is still the interview punch-in.
    interview = {
        'offset': 0.5, 't': 1.0,
        'frontal': [{'x': 0.18, 'w': 0.06, 'motion': 6, 'area': 1, 'score': 0.90}],
        'turned': [{'x': 0.80, 'w': 0.09, 'motion': 1, 'area': 2, 'score': 0.87}],
    }
    assert framing._center_for(interview, {}, [], fraction) == pytest.approx(0.18)


def test_fit_votes_inside_a_shot_stay_when_they_last():
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    samples = []
    for offset in (0.3, 0.8, 1.3, 1.8, 2.3, 2.8, 3.3, 4.3, 4.8, 5.3, 5.8):
        if offset < 3.5:
            frontal = [
                {'x': 0.2, 'w': 0.08, 'motion': 0, 'area': 1, 'score': 0.93},
                {'x': 0.5, 'w': 0.08, 'motion': 0, 'area': 1, 'score': 0.94},
                {'x': 0.8, 'w': 0.08, 'motion': 0, 'area': 1, 'score': 0.95},
            ]
        else:
            frontal = [{'x': 0.72, 'w': 0.12, 'motion': 5, 'area': 1, 'score': 0.9}]
        samples.append({'offset': offset, 't': offset, 'frontal': frontal, 'turned': []})
    track = framing.frame_observed(samples, 0.0, 6.5, fraction, [], {})
    assert _active_point(track, 1.0)['mode'] == 'fit', track
    close = _active_point(track, 5.5)
    assert close['mode'] == 'crop', track
    left, right = _window(close['crop_x'], fraction)
    assert left <= 0.72 <= right


def test_a_shot_shorter_than_the_hold_keeps_its_own_crop():
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    samples = [{'offset': 0.18, 't': 77.58, 'frontal': [
        {'x': 0.70, 'w': 0.12, 'motion': 2, 'area': 1, 'score': 0.9},
    ], 'turned': []}]
    track = framing.frame_observed(samples, 77.4, 0.37, fraction, [], {})
    assert len(track) == 1 and track[0]['mode'] == 'crop'
    assert track[0]['start'] == pytest.approx(77.4, abs=0.02)
    left, right = _window(track[0]['crop_x'], fraction)
    assert left <= 0.70 <= right


def _write_clip(tmp_path, name, frames):
    folder = tmp_path / name
    folder.mkdir()
    for index, frame in enumerate(frames):
        cv2.imwrite(str(folder / f'{index:04d}.jpg'), frame)
    path = tmp_path / f'{name}.mp4'
    _encode(folder, len(frames), path)
    return path


def test_crossfade_from_a_group_still_to_a_close_up_splits_the_framing(tmp_path):
    frontal, _turned = _faces()
    group_face = cv2.resize(frontal, (120, 150))
    group = np.full((SOURCE[1], SOURCE[0], 3), (210, 186, 150), np.uint8)
    for cx in (180, 480, 780):
        _blit(group, group_face, cx, 270)
    close = np.full((SOURCE[1], SOURCE[0], 3), (16, 22, 30), np.uint8)
    speaker = cv2.resize(frontal, (200, 250))
    _blit(close, speaker, 700, 270)
    frames = []
    for index in range(int(7 * FPS)):
        second = index / FPS
        if second < 3.0:
            frames.append(group)
        elif second < 4.0:
            alpha = second - 3.0
            frames.append(cv2.addWeighted(group, 1 - alpha, close, alpha, 0))
        else:
            frames.append(close)
    video = _write_clip(tmp_path, 'crossfade', frames)
    cuts = framing.detect_cuts(video, 0, 7)
    assert any(2.4 <= cut <= 4.6 for cut in cuts), cuts
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='fade', label='a', start=0, end=7)])
    result = _auto_frame(video, draft, [])
    track = result['scenes'][0]['crop_track']
    fraction = result['window_fraction']
    assert _active_point(track, 1.0)['mode'] == 'fit', track
    close_point = _active_point(track, 5.8)
    assert close_point['mode'] == 'crop', track
    image = _frame_at(video, 5.8)
    found = _detected(image)
    face_x = max(found, key=lambda row: row['w'])['x']
    left, right = _window(close_point['crop_x'], fraction)
    assert left <= face_x <= right, (face_x, close_point, track)


def test_wide_shot_with_small_faces_is_not_cropped_to_one_person(tmp_path):
    frontal, _turned = _faces()
    host = cv2.resize(frontal, (96, 120))
    small = cv2.resize(frontal, (58, 74))
    image = np.full((SOURCE[1], SOURCE[0], 3), (36, 44, 38), np.uint8)
    _blit(image, host, 180, 250)
    for cx in (430, 640, 840):
        _blit(image, small, cx, 300)
    video = _write_clip(tmp_path, 'wide', [image] * (FPS * 3))
    seen = _frame_at(video, 1.0)
    found = _detected(seen)
    assert len(found) >= 3, found
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='wide', label='a', start=0, end=3)])
    result = _auto_frame(video, draft, [])
    track = result['scenes'][0]['crop_track']
    assert track and all(point['mode'] == 'fit' for point in track), track


def test_a_very_short_final_shot_gets_its_own_crop(tmp_path):
    frontal, _turned = _faces()
    left = np.full((SOURCE[1], SOURCE[0], 3), (18, 18, 22), np.uint8)
    right = np.full((SOURCE[1], SOURCE[0], 3), (230, 214, 186), np.uint8)
    _blit(left, cv2.resize(frontal, (150, 190)), 170, 270)
    _blit(right, cv2.resize(frontal, (170, 210)), 780, 270)
    length = 4.0
    cut_at = length - 0.37
    frames = []
    for index in range(int(length * FPS)):
        frames.append(left if index / FPS < cut_at else right)
    video = _write_clip(tmp_path, 'tail', frames)
    cuts = framing.detect_cuts(video, 0, length)
    assert any(abs(cut - cut_at) <= 0.25 for cut in cuts), cuts
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='tail', label='a', start=0, end=length)])
    result = _auto_frame(video, draft, [])
    track = result['scenes'][0]['crop_track']
    fraction = result['window_fraction']
    early = _detected(_frame_at(video, 0.6))
    late = _detected(_frame_at(video, 3.85))
    early_x = early[0]['x']
    late_x = late[0]['x']
    assert early_x < 0.4 and late_x > 0.6, (early, late)

    def holds(at, face_x, other_x):
        point = _active_point(track, at)
        assert point['mode'] == 'crop', (at, track)
        window_left, window_right = _window(point['crop_x'], fraction)
        assert window_left <= face_x <= window_right, (at, face_x, point, track)
        assert not (window_left <= other_x <= window_right), (at, other_x, point, track)

    holds(0.6, early_x, late_x)
    holds(3.85, late_x, early_x)


def test_face_qa_under_the_production_budget(tmp_path, monkeypatch):
    from backend.services.studio.qa.media import ProbeError
    video = _talk_video(tmp_path)
    image = _frame_at(video, 1.0)
    _speaker, turned = _frontal_and_turned(image)
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    bad = framing.crop_x_for_center(turned['x'], fraction)
    # Captions are on, so the crop check gets 0.9 s of the 2.0 s face budget.
    turned_head = face.check(Context(
        output=video, source=video, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, bad)])],
    ), 2.0)
    assert turned_head == ('fail', 'back_of_head'), turned_head

    group = _group_video(tmp_path)
    group_image = _frame_at(group, 0.4)
    faces = _detected(group_image)
    assert len(faces) >= 3
    one = framing.crop_x_for_center(sorted(faces, key=lambda row: row['x'])[0]['x'], fraction)
    cropped_group = face.check(Context(
        output=group, source=group, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, one)])],
    ), 2.0)
    assert cropped_group == ('fail', 'group_crop'), cropped_group

    blank = _write_clip(tmp_path, 'blank', [np.full((SOURCE[1], SOURCE[0], 3), 12, np.uint8)] * (FPS * 2))
    empty = face.check(Context(
        output=blank, source=blank, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.5)])],
    ), 2.0)
    assert empty == ('fail', 'no_face'), empty

    source = tmp_path / 'huge.mp4'
    source.write_bytes(b'\x00' * 64)

    def timed_out(*_args, **_kwargs):
        raise ProbeError('timeout')

    monkeypatch.setattr(face, '_grab_frames', timed_out)
    covered = {'ran': False}

    def boxes(*_args):
        covered['ran'] = True
        return [(100.0, 1800.0, 80.0, 80.0)]

    monkeypatch.setattr(face, 'detect_faces', boxes)
    skipped = face.check(Context(
        output=source, source=source, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.2)])],
    ), 2.0)
    assert covered['ran'] is True
    assert skipped == ('fail', 'gt40'), skipped
    quiet = face.check(Context(
        output=source, source=source, width=1080, height=1920, captions=False,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.2)])],
    ), 2.0)
    assert quiet == ('skip', 'timeout'), quiet
    # The caption check passes, but the crop check never read a frame: a skip, not a pass.
    monkeypatch.setattr(face, 'detect_faces', lambda *_args: [])
    unread = face.check(Context(
        output=source, source=source, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.2)])],
    ), 2.0)
    assert unread == ('skip', 'timeout'), unread


def test_production_budget_samples_three_frames_across_the_longest_spans():
    # The old cap was int(0.9 / 0.7) == 1, so a 0.9 s crop budget saw a single frame.
    spans = [(0.0, 4.0, 0.2, 'crop'), (10.0, 1.2, 0.8, 'crop')]
    plan = face._grab_plan(spans, 0.9)
    assert len(plan) == 3
    assert face._grab_count(0.9) == 3 and face._grab_count(2.0) > 3
    assert int(0.9 / 0.7) == 1
    long_times = sorted(when for index, when in plan if index == 0)
    assert long_times[0] < 0.6 and long_times[-1] > 3.2, plan


def test_three_looks_go_to_different_framings_not_three_takes_of_one_crop():
    """Three long spans on the same host crop and a shorter span on another crop.

    Longest-first spent all three looks on the host. The fourth span is where a turned head
    was framed in a real render, so it has to get one of the three looks.
    """
    spans = [
        (0.0, 16.1, 0.238, 'crop'), (16.1, 23.0, 0.247, 'crop'), (39.1, 17.7, 0.67, 'crop'),
        (56.8, 3.3, 0.506, 'crop'), (60.1, 11.9, 0.159, 'crop'), (72.0, 0.4, 0.58, 'crop'),
    ]
    plan = face._grab_plan(spans, 0.9)
    assert [index for index, _when in plan] == [1, 2, 4], plan
    assert all(spans[index][0] < when < spans[index][0] + spans[index][1] * 0.2 for index, when in plan)
    # A fit span is a different framing from any crop.
    mixed = [(0.0, 20.0, 0.3, 'crop'), (20.0, 19.0, 0.31, 'crop'), (39.0, 5.0, 0.5, 'fit')]
    assert [index for index, _when in face._grab_plan(mixed, 0.9)] == [0, 2, 1]


def test_a_frame_from_the_wrong_timestamp_is_discarded(tmp_path, monkeypatch):
    video = _write_clip(tmp_path, 'stamp', [np.full((SOURCE[1], SOURCE[0], 3), 20, np.uint8)] * (FPS * 3))
    original = face.run

    def shifted(cmd, timeout, **kwargs):
        proc = original(cmd, timeout, **kwargs)
        proc.stderr = b'n:   0 pts: 0 pts_time:0.05\n'
        return proc

    monkeypatch.setattr(face, 'run', shifted)
    assert face._grab_frames(video, [2.5], 2.0) == [None]


def test_grab_pts_are_matched_by_output_name_not_log_order(tmp_path, monkeypatch):
    """The parallel filtergraphs log in any order. Each pts belongs to the output that named it."""
    video = _write_clip(tmp_path, 'order', [np.full((SOURCE[1], SOURCE[0], 3), 20, np.uint8)] * (FPS * 3))
    original = face.run

    def reordered(cmd, timeout, **kwargs):
        proc = original(cmd, timeout, **kwargs)
        proc.stderr = (
            b'[showinfo@g2 @ 0x3] n:   0 pts: 1 pts_time:2.6\n'
            b'[showinfo@g0 @ 0x1] n:   0 pts: 1 pts_time:0.4\n'
            b'[showinfo@g1 @ 0x2] n:   0 pts: 1 pts_time:9.0\n'
        )
        return proc

    monkeypatch.setattr(face, 'run', reordered)
    grabbed = face._grab_frames(video, [0.4, 1.5, 2.6], 8.0)
    assert [bool(frame) for frame in grabbed] == [True, False, True]


def test_production_budget_rejects_a_bad_crop_the_middle_frame_would_pass(tmp_path, monkeypatch):
    """The old 0.9 s budget sampled the middle once. Edges next to the cuts are the bad crop."""
    frontal, turned = _faces()
    length = 3.0
    count = int(length * FPS)

    def placed(image, face_image, size, cx):
        _blit(image, cv2.resize(face_image, size), cx, 270)
        return image

    good = placed(np.full((SOURCE[1], SOURCE[0], 3), (230, 214, 186), np.uint8), frontal, (150, 190), 700)
    bad = placed(np.full((SOURCE[1], SOURCE[0], 3), (18, 18, 22), np.uint8), turned, (200, 230), 700)
    frames = []
    for index in range(count):
        second = index / FPS
        frames.append(good if 0.9 <= second < 2.1 else bad)
    video = _write_clip(tmp_path, 'edge-turn', frames)
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    turned_box = _detected(_frame_at(video, 0.36))[0]
    crop = framing.crop_x_for_center(turned_box['x'], fraction)
    grabbed = face._grab_frames(video, [0.36, 1.5, 2.64], 2.0, 480)
    assert all(grabbed), 'each requested time has to come back, not the neighbouring keyframe'
    commands = []
    original = face.run

    def spy(cmd, timeout, **kwargs):
        commands.append([str(part) for part in cmd])
        return original(cmd, timeout, **kwargs)

    monkeypatch.setattr(face, 'run', spy)
    turned_head = face.check(Context(
        output=video, source=video, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, length, [(0.0, crop)])],
    ), 2.0)
    assert turned_head == ('fail', 'back_of_head'), turned_head
    assert commands and all('-noaccurate_seek' not in cmd for cmd in commands)
    assert any('-accurate_seek' in cmd and '-copyts' in cmd for cmd in commands)

    single = np.full((SOURCE[1], SOURCE[0], 3), (210, 198, 170), np.uint8)
    group = np.full((SOURCE[1], SOURCE[0], 3), (28, 28, 26), np.uint8)
    face_image = cv2.resize(frontal, (120, 150))
    _blit(single, face_image, 180, 270)
    for cx in (180, 480, 780):
        _blit(group, face_image, cx, 270)
    grouped_frames = []
    for index in range(count):
        second = index / FPS
        grouped_frames.append(single if 0.9 <= second < 2.1 else group)
    grouped = _write_clip(tmp_path, 'edge-group', grouped_frames)
    seen = _detected(_frame_at(grouped, 0.36))
    assert len(seen) >= 3, seen
    one = framing.crop_x_for_center(sorted(seen, key=lambda row: row['x'])[0]['x'], fraction)
    cropped = face.check(Context(
        output=grouped, source=grouped, width=1080, height=1920, captions=True,
        scenes=[SceneSpan(0.0, length, [(0.0, one)])],
    ), 2.0)
    assert cropped == ('fail', 'group_crop'), cropped


def test_fit_heavy_counts_people_not_only_frontal_faces(tmp_path):
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    assert face._single_face_fit(
        [{'x': 0.22, 'w': 0.08, 'score': 0.91}],
        [],
        [{'x': 0.55, 'w': 0.04, 'score': 0.55}, {'x': 0.82, 'w': 0.035, 'score': 0.50}],
        fraction,
    ) is False
    assert face._single_face_fit(
        [{'x': 0.18, 'w': 0.06, 'score': 0.90}],
        [{'x': 0.80, 'w': 0.09, 'score': 0.87}],
        [],
        fraction,
    ) is True

    group = _group_video(tmp_path)
    held = face.check(Context(
        output=group, source=group, width=1080, height=1920,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.5)], ['fit'])],
    ), 2.0)
    assert held[0] == 'pass' and held[1] != 'fit_heavy', held

    frontal, turned = _faces()
    frames = [_talk_frame(frontal, turned, 1.0, index % 2 == 1) for index in range(FPS * 2)]
    video = _write_clip(tmp_path, 'one-face-fit', frames)
    heavy = face.check(Context(
        output=video, source=video, width=1080, height=1920,
        scenes=[SceneSpan(0.0, 2.0, [(0.0, 0.5)], ['fit'])],
    ), 2.0)
    assert heavy == ('fail', 'fit_heavy'), heavy


def test_tracking_detector_stays_at_point_six():
    assert framing.TRACK_SCORE == 0.6
    assert framing.WIDE_SCORE == 0.45
    assert framing.WIDE_SCORE < framing.TRACK_SCORE <= framing.MIN_SCORE


def test_profile_talker_beats_a_silent_frontal_guest():
    """A side-profile speaker next to a guest facing the camera is the crop centre.

    YuNet marks the profile as turned. Returning the only frontal face used to punch in on
    the guest while the name card still named the profile.
    """
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    sample = {
        'offset': 0.4, 't': 0.4,
        'frontal': [{'x': 0.74, 'w': 0.10, 'motion': 0.2, 'area': 1, 'score': 0.93}],
        'turned': [{'x': 0.22, 'w': 0.14, 'motion': 8, 'area': 2, 'score': 0.88}],
    }
    center = framing._center_for(sample, {}, [], fraction)
    assert center == pytest.approx(0.22)
    left, right = _window(framing.crop_x_for_subject(center, 0.14, fraction), fraction)
    assert left <= 0.22 - 0.07 and right >= 0.22 + 0.07
    assert not (left <= 0.74 <= right)


def test_bound_profile_is_not_replaced_by_the_listener():
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    sample = {
        'offset': 1.0, 't': 1.0,
        'frontal': [{'x': 0.74, 'w': 0.10, 'motion': 6, 'area': 1, 'score': 0.93}],
        'turned': [{'x': 0.22, 'w': 0.14, 'motion': 1, 'area': 2, 'score': 0.88}],
    }
    cues = [{'start': 0, 'end': 5, 'speaker': 'host', 'text': '[host] hello'}]
    assert framing._center_for(sample, {'host': 0.20}, cues, fraction) == pytest.approx(0.22)


def test_edge_truncated_face_is_pulled_inward_and_an_interior_face_is_not():
    fraction = framing.window_fraction(*SOURCE, 1080, 1920)
    assert framing.crop_x_for_subject(0.30, 0.10, fraction) == pytest.approx(
        framing.crop_x_for_center(0.30, fraction),
    )
    edge = framing.crop_x_for_subject(0.08, 0.16, fraction)
    assert edge > 0.02
    left, right = _window(edge, fraction)
    assert left <= 0.08 <= right
    # About one face width past the inward edge of the box (0.16), still short of the guest.
    assert right >= 0.30
    assert not (left <= 0.74 <= right)
    clamped_left, clamped_right = _window(framing.crop_x_for_center(0.08, fraction), fraction)
    assert clamped_left == pytest.approx(0.0, abs=1e-6)
    assert right > clamped_right


def test_unlabeled_scene_locks_onto_the_talking_profile_and_fits_a_silent_guest(tmp_path):
    """The arrogance failure: one scene, no speaker labels, crop_x swinging 0.8 ↔ 0.0.

    Shot A is the two-shot (profile talking on the left, silent guest on the right).
    Shot B is the guest alone and silent. Shot C is the profile close-up, box cut by the
    left edge. The window stays on the profile, the guest reaction is shown whole, and
    the close-up is not clamped to crop_x 0.
    """
    def look(offset, t, frontal, turned):
        return {'offset': offset, 't': t, 'frontal': frontal, 'turned': turned, 'wide': []}

    guest = {'x': 0.74, 'w': 0.10, 'motion': 0.2, 'area': 1, 'score': 0.93}
    profile = {'x': 0.22, 'w': 0.14, 'motion': 8, 'area': 2, 'score': 0.88}
    # Mouth motion below the talking threshold: a profile close-up often looks still,
    # and the crop still has to stay on the person who was talking in the two-shot.
    close = {'x': 0.08, 'w': 0.16, 'motion': 1, 'area': 3, 'score': 0.90}
    shot_a = [look(at, at, [dict(guest)], [dict(profile)]) for at in (0.4, 1.6, 2.8, 4.0, 5.2)]
    shot_b = [look(at - 6, at, [{**guest, 'motion': 0.0}], []) for at in (6.4, 7.6, 8.8)]
    shot_c = [look(at - 10, at, [], [dict(close)]) for at in (10.4, 11.6, 12.8, 14.0, 15.2)]
    scans = [{'shots': [(0.0, 6.0, shot_a), (6.0, 10.0, shot_b), (10.0, 16.0, shot_c)],
              'faces': 13, 'samples': 13}]
    draft = Draft(id='d', title='t', aspect='portrait', layout='crop',
                  scenes=[Scene(id='talk', label='a', start=0, end=16)])
    cues = framing.cues_from_entries([
        {'start': 0, 'end': 16, 'text': 'I say this in the company all the time'},
    ])
    assert cues and all(not cue.get('speaker') for cue in cues)
    result = framing.auto_frame(tmp_path / 'clip.mp4', draft, *SOURCE, scans=scans, cues=cues)
    track = result['scenes'][0]['crop_track']
    fraction = result['window_fraction']
    assert _active_point(track, 8.0)['mode'] == 'fit', track
    assert _active_point(track, 12.0)['crop_x'] > 0.02, track

    def covers_speaker(at, center, width):
        point = _active_point(track, at)
        assert point['mode'] == 'crop', (at, track)
        left, right = _window(point['crop_x'], fraction)
        assert left <= center <= right
        assert right >= center + width / 2
        assert not (left <= 0.74 <= right)

    covers_speaker(1.0, 0.22, 0.14)
    covers_speaker(12.0, 0.08, 0.16)
    for point in track:
        if point['mode'] != 'crop':
            continue
        left, right = _window(point['crop_x'], fraction)
        assert not (left <= 0.74 <= right), point

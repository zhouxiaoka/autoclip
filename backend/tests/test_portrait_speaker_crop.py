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


def _encode(folder, count, path):
    subprocess.run(
        [get_ffmpeg_path(), '-y', '-v', 'error', '-framerate', str(FPS), '-i', str(folder / '%04d.jpg'),
         '-frames:v', str(count), '-pix_fmt', 'yuv420p', str(path)],
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


def test_cues_read_explicit_labels_and_gtgt_turns():
    explicit = framing.cues_from_entries([
        {'start': 0, 'end': 1, 'text': '[host] hello'},
        {'start': 1, 'end': 2, 'text': 'still me'},
        {'start': 2, 'end': 3, 'text': 'Guest: now me'},
    ])
    assert [cue['speaker'] for cue in explicit] == ['host', 'host', 'Guest']
    turns = framing.cues_from_entries([
        {'start_time': '00:00:00,000', 'end_time': '00:00:01,000', 'text': 'intro'},
        {'start_time': '00:00:01,000', 'end_time': '00:00:02,000', 'text': '>> answer'},
        {'start_time': '00:00:02,050', 'end_time': '00:00:03,000', 'text': '>> more'},
        {'start_time': '00:00:05,000', 'end_time': '00:00:06,000', 'text': '>> later'},
    ])
    assert [cue['speaker'] for cue in turns] == ['speaker_a', 'speaker_b', 'speaker_b', 'speaker_a']


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


def test_presence_fails_only_after_a_second_of_the_same_miss():
    assert face.judge_presence([(0.8, 'turned')])[0] == 'pass'
    assert face.judge_presence([(1.0, 'turned')])[0] == 'pass'
    assert face.judge_presence([(1.2, 'turned')]) == ('fail', 'back_of_head')
    assert face.judge_presence([(0.6, 'turned'), (0.6, 'turned')]) == ('fail', 'back_of_head')
    assert face.judge_presence([(0.6, 'missing'), (0.4, 'frontal'), (0.6, 'missing')])[0] == 'pass'
    assert face.judge_presence([(1.2, 'missing')]) == ('fail', 'speaker_out')

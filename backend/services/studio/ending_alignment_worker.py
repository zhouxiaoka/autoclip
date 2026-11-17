"""Offline word timestamps for at most 24 seconds. Parent owns cancellation/deadline."""
from __future__ import annotations

import json
import subprocess
import sys


def main():
    model_path, video, offset, duration, ffmpeg = sys.argv[1:]
    lo, span = float(offset), float(duration)
    if not 0 <= lo or not 0 < span <= 24:
        raise ValueError('invalid alignment window')
    import numpy as np
    from faster_whisper import WhisperModel
    pcm = subprocess.run([ffmpeg,'-nostdin','-v','error','-ss',str(lo),'-t',str(span),'-i',video,
                          '-vn','-ac','1','-ar','16000','-f','s16le','pipe:1'],
                         capture_output=True,check=True,timeout=15).stdout
    model = WhisperModel(model_path,device='cpu',compute_type='int8',cpu_threads=2,local_files_only=True)
    segments, _ = model.transcribe(np.frombuffer(pcm,dtype=np.int16).astype(np.float32)/32768,
                                  beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
    words = [{'text':w.word,'start':w.start+lo,'end':w.end+lo,'probability':w.probability} for s in segments for w in (s.words or [])]
    print(json.dumps({'words':words},ensure_ascii=False,allow_nan=False))


if __name__ == '__main__':
    main()

"""Standalone worker: launched with -S, importing only the optional runtime.

Do not import backend here. PyTorch/NumPy must never enter the API process.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'transcribe'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--audio', type=Path)
    parser.add_argument('--language', default='auto')
    parser.add_argument('--deny-network', action='store_true')  # acceptance only
    args = parser.parse_args()
    runtime = args.root / 'runtime'
    sys.path.insert(0, str(runtime))
    os.environ.update(OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', NUMBA_NUM_THREADS='2',
                      HF_HOME=str(args.root / 'models'), HF_HUB_DISABLE_PROGRESS_BARS='1')
    if args.action == 'transcribe':
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', MODELSCOPE_OFFLINE='1')
    if args.deny_network:
        import socket
        def denied(*a, **kw):
            raise RuntimeError('offline acceptance forbids network access')
        socket.socket.connect = denied
        socket.create_connection = denied
    import torch
    import funasr
    assert Path(torch.__file__).resolve().is_relative_to(runtime.resolve())
    assert Path(funasr.__file__).resolve().is_relative_to(runtime.resolve())
    torch.set_num_threads(2)
    from funasr import AutoModel
    if args.action == 'prepare':
        from huggingface_hub import snapshot_download
        paths = {key: snapshot_download(repo_id=repo, cache_dir=str(args.root / 'models' / 'hub'),
                    allow_patterns=['*.json', '*.yaml', '*.txt', '*.model', '*.mvn', 'model.pt'])
                 for key, repo in [('model', 'FunAudioLLM/SenseVoiceSmall'), ('vad_model', 'funasr/fsmn-vad')]}
    else:
        paths = json.loads((args.root / 'ready.json').read_text(encoding='utf-8'))['paths']
        if any(not Path(p).resolve().is_relative_to((args.root / 'models').resolve()) for p in paths.values()):
            raise ValueError('Invalid model cache path')
    model = AutoModel(**paths, hub='hf', device='cpu', ncpu=2, disable_update=True,
                      disable_pbar=True, trust_remote_code=False,
                      vad_kwargs={'max_single_segment_time': 30000})
    if args.action == 'prepare':
        result = {'paths': paths}
    else:
        result = model.generate(input=str(args.audio), cache={}, language=args.language,
                                use_itn=True, output_timestamp=True, batch_size_s=30,
                                merge_vad=False, disable_pbar=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()

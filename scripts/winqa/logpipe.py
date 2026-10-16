#!/usr/bin/env python3
"""R29 #317: the live log channel of run_winqa.sh. One small process owns scrubbing, run.log and the terminal, so
Bash 3.2 needs no FIFO, extra pids or tee.

    python3 logpipe.py --log FILE --status FILE --keys-fd N

- Reads stdin (the script's stdout+stderr) through redact.Stream, the same single path as redact.py --lines
  (#414 v5 part A: one decoder + line-by-line scanner; nothing held back or rescanned).
- Writes the scrubbed bytes to FILE (append) and to stdout (the original terminal). Nothing unscrubbed is written.
- Handshake: after the keys are read and FILE is open it writes "READY <pid>" to the status file; the script does
  not start its business output before it sees that line.
- At EOF it writes "EXIT <code>" to the status file and exits with that code. Any failure (keys, log open, write,
  scrubber error) prints only the fixed line "WINQA_E_LOGPIPE <code>" on stderr, drops held text and exits 70.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redact  # noqa: E402

E_LOGPIPE = 70


def _status(path, text):
    with open(path, 'a', encoding='ascii') as fh:
        fh.write(text + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def main(argv):
    try:
        log, status = argv[argv.index('--log') + 1], argv[argv.index('--status') + 1]
        keys = redact._read_fd_keys(int(argv[argv.index('--keys-fd') + 1]))
    except Exception:
        sys.stderr.write(f'WINQA_E_LOGPIPE {E_LOGPIPE}\n')
        return E_LOGPIPE
    code = 0
    try:
        if not redact.keys_ok(keys):
            raise ValueError('key with a line break')
        with open(log, 'ab') as fh:
            def write(b):
                fh.write(b); fh.flush()
                sys.stdout.buffer.write(b); sys.stdout.buffer.flush()
            _status(status, f'READY {os.getpid()}')
            st = redact.Stream(keys, write)
            while True:
                chunk = os.read(0, 65536)
                if not chunk:
                    break
                st.feed(chunk)
            st.close()
            fh.flush(); os.fsync(fh.fileno())
    except BaseException:
        code = E_LOGPIPE
        try:
            sys.stderr.write(f'WINQA_E_LOGPIPE {code}\n')
        except Exception:
            pass
    try:
        _status(status, f'EXIT {code}')
    except Exception:
        code = E_LOGPIPE
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

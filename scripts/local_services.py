#!/usr/bin/env python3
"""Manage only PID-recorded services belonging to this checkout (macOS/Linux)."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('backend', 'frontend', 'celery')


def paths(root, role):
    return root / f'{role}.pid', root / f'{role}.pid.json'


def matches_service(process, root, role):
    cwd = Path(process.cwd()).resolve()
    args = process.cmdline()
    if role == 'frontend':
        return cwd == root / 'frontend' and (
            ('run' in args and 'dev' in args and any(Path(a).name in ('npm', 'npm-cli.js') for a in args))
            or (bool(args) and (args[0] == 'npm run dev' or args[0].startswith('npm run dev ')))
            or any(Path(a).name in ('vite', 'vite.js') for a in args)
        )
    if cwd != root:
        return False
    if role == 'backend':
        return 'uvicorn' in args and 'backend.main:app' in args
    return ('worker' in args and 'backend.core.celery_app' in args
            and any(Path(a).name == 'celery' for a in args))


def owned_process(root, role):
    pid_file, identity_file = paths(root, role)
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        if pid <= 1:
            raise ValueError('invalid PID')
        process = psutil.Process(pid)
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            return None
        if identity_file.exists():
            identity = json.loads(identity_file.read_text())
            if (identity['pid'] != pid or identity['root'] != str(root)
                    or identity['role'] != role or identity['created'] != process.create_time()):
                raise ValueError('PID identity changed')
        if not matches_service(process, root, role):
            raise ValueError('process belongs to another service or checkout')
        return process
    except psutil.NoSuchProcess:
        return None
    except (ValueError, KeyError, OSError, psutil.AccessDenied) as error:
        raise RuntimeError(f'{role}: refusing to use {pid_file}: {error}') from error


def record(root, role, pid):
    process = psutil.Process(pid)
    for _ in range(20):
        if matches_service(process, root, role):
            break
        time.sleep(0.1)
    if not matches_service(process, root, role):
        raise RuntimeError(f'{role}: new process does not belong to this checkout')
    pid_file, identity_file = paths(root, role)
    identity = dict(pid=pid, root=str(root), role=role, created=process.create_time())
    temporary = identity_file.with_suffix('.tmp')
    temporary.write_text(json.dumps(identity))
    temporary.replace(identity_file)
    pid_file.write_text(str(pid) + '\n')


def stop(root, role):
    process = owned_process(root, role)
    if process is not None:
        # Snapshot children before the parent exits. psutil retains creation-time
        # identity on these Process objects, guarding against subsequent PID reuse.
        children = process.children(recursive=True)
        targets = children + [process]
        for target in reversed(targets):
            try:
                target.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(targets, timeout=5)
        for target in alive:
            try:
                target.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(alive, timeout=3)
        if alive:
            raise RuntimeError(f'{role}: processes did not exit')
    for path in paths(root, role):
        path.unlink(missing_ok=True)
    print(f'{role}: stopped (Redis and other checkouts untouched)')


def redis_check():
    import redis
    redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
                        socket_connect_timeout=3, socket_timeout=3).ping()


def status(root):
    ok = True
    for role in ROLES:
        try:
            process = owned_process(root, role)
            if process is None:
                raise RuntimeError('not running / no PID record')
            if role in ('backend', 'frontend'):
                port = os.getenv('BACKEND_PORT' if role == 'backend' else 'FRONTEND_PORT',
                                 '8000' if role == 'backend' else '3000')
                suffix = '/api/v1/health/' if role == 'backend' else '/'
                with urllib.request.urlopen(f'http://127.0.0.1:{int(port)}{suffix}', timeout=3) as response:
                    if response.status != 200:
                        raise RuntimeError(f'HTTP {response.status}')
            print(f'{role}: running (PID {process.pid})' + ('; see logs/celery.log for task readiness' if role == 'celery' else ''))
        except Exception as error:
            print(f'{role}: {error}', file=sys.stderr)
            ok = False
    try:
        redis_check()
        print('Redis: reachable')
    except Exception as error:
        # Do not print exception strings which may contain a credentialed URL.
        print(f'Redis: unavailable ({type(error).__name__})', file=sys.stderr)
        ok = False
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('record', 'check', 'stop', 'status', 'redis'))
    parser.add_argument('role', nargs='?', choices=ROLES)
    parser.add_argument('pid', nargs='?', type=int)
    args = parser.parse_args()
    try:
        if args.action == 'redis':
            redis_check()
        elif args.action == 'status':
            return 0 if status(ROOT) else 1
        elif args.action == 'record':
            if args.role is None or args.pid is None:
                parser.error('record requires role and pid')
            record(ROOT, args.role, args.pid)
        elif args.action == 'check':
            if args.role is None:
                parser.error('check requires role')
            return 0 if owned_process(ROOT, args.role) else 1
        else:
            ok = True
            for role in (args.role,) if args.role else ROLES:
                try:
                    stop(ROOT, role)
                except Exception as error:
                    print(error, file=sys.stderr)
                    ok = False
            return 0 if ok else 1
    except Exception as error:
        print(type(error).__name__ if args.action == 'redis' else str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

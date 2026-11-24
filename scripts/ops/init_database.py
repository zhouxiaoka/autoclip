#!/usr/bin/env python3
"""Manual database initialization; shares the backend's normal initialization."""
from pathlib import Path
import sys


def init_database():
    import backend.models  # Register all tables before shared initialization.
    from backend.core.database import init_database as initialize
    return initialize()


def main():
    from dotenv import load_dotenv
    here = Path(__file__).resolve().parent
    root = next((p for p in (here, *here.parents) if (p / 'backend').is_dir()), here)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    load_dotenv(root / '.env', override=False)
    # Paths in project .env are relative to the project, even when called elsewhere.
    import os
    os.chdir(root)
    (root / 'data').mkdir(exist_ok=True)
    if not init_database():
        return 1
    print('数据库初始化完成；使用 ./scripts/ops/start_autoclip.sh 启动服务。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

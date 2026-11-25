"""
数据库配置
包含数据库连接、会话管理和依赖注入
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, NullPool
from sqlalchemy.engine import make_url
from typing import Generator
from backend.models.base import Base

# 数据库配置
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///autoclip.db"
)

# 如果没有设置环境变量，使用配置函数获取数据库URL
if DATABASE_URL == "sqlite:///autoclip.db":
    try:
        from .config import get_database_url
        DATABASE_URL = get_database_url()
    except ImportError:
        # 如果导入失败，保持默认值
        pass

def is_memory_sqlite(database_url: str) -> bool:
    url = make_url(database_url)
    return url.get_backend_name() == 'sqlite' and (not url.database or url.database == ':memory:' or url.query.get('mode') == 'memory')


def sqlite_engine_kwargs(database_url: str) -> dict:
    return {'poolclass': StaticPool if is_memory_sqlite(database_url) else NullPool}


# File-backed databases use separate connections; in-memory databases keep one.
def create_database_engine(database_url):
    url = make_url(database_url)
    if url.get_backend_name() != 'sqlite':
        return create_engine(database_url, pool_pre_ping=True, pool_recycle=300, echo=False)
    in_memory = is_memory_sqlite(database_url)
    database_engine = create_engine(
        database_url,
        connect_args={'check_same_thread': False, 'timeout': 30},
        **sqlite_engine_kwargs(database_url),
        pool_pre_ping=True,
        echo=False,
    )
    if not in_memory:
        wal_lock = threading.Lock()
        wal_initialized = {'done': False}

        @event.listens_for(database_engine, 'connect')
        def sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            try:
                # Apply busy_timeout first so normal queries never race on NullPool connects.
                cursor.execute('PRAGMA busy_timeout=30000')
                if not wal_initialized['done']:
                    with wal_lock:
                        if not wal_initialized['done']:
                            try:
                                cursor.execute('PRAGMA busy_timeout=0')
                                row = cursor.execute('PRAGMA journal_mode').fetchone()
                                mode = row[0] if row else ''
                                if str(mode).lower() != 'wal':
                                    wal_row = cursor.execute('PRAGMA journal_mode=WAL').fetchone()
                                    if wal_row and str(wal_row[0]).lower() == 'wal':
                                        wal_initialized['done'] = True
                                else:
                                    wal_initialized['done'] = True
                            except sqlite3.OperationalError as error:
                                # Windows transient lock / IO / sharing errors must not fail the request
                                # when initializing optional WAL mode (PYTHON-FASTAPI-1C / -81).
                                code = getattr(error, 'sqlite_errorcode', 0) & 0xff
                                logging.getLogger(__name__).info('SQLite WAL initialization deferred (code=%s)', code)
                            finally:
                                try:
                                    cursor.execute('PRAGMA busy_timeout=30000')
                                except sqlite3.OperationalError:
                                    pass
            finally:
                cursor.close()
    return database_engine


engine = create_database_engine(DATABASE_URL)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    数据库会话依赖注入
    用于FastAPI的依赖注入系统
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """短生命周期会话。不要用 next(get_db())：生成器被丢掉时 finally 不会马上执行，连接不归还。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()

def create_tables():
    """创建所有数据库表，并清洗项目表里当前代码无法识别的枚举值。"""
    Base.metadata.create_all(bind=engine)
    _normalize_project_enums()


def _normalize_project_enums():
    try:
        from backend.core.project_enum_migration import normalize_legacy_project_enums
        normalize_legacy_project_enums(engine)
    except Exception:
        logging.getLogger(__name__).exception("清洗项目枚举旧值失败")


def drop_tables():
    """删除所有数据库表"""
    Base.metadata.drop_all(bind=engine)

def reset_database():
    """重置数据库"""
    drop_tables()
    create_tables()

from sqlalchemy import text

def test_connection() -> bool:
    """测试数据库连接"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        return False

# 数据库初始化
def init_database():
    """初始化数据库"""
    print("正在初始化数据库...")
    
    # 测试连接
    if not test_connection():
        print("❌ 数据库连接失败")
        return False
    
    # 创建表
    try:
        create_tables()
        print("✅ 数据库表创建成功")
        return True
    except Exception as e:
        print(f"❌ 数据库表创建失败: {e}")
        return False

if __name__ == "__main__":
    # 直接运行此文件时初始化数据库
    init_database()

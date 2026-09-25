"""
数据库配置
包含数据库连接、会话管理和依赖注入
"""

import logging
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, StaticPool
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

def is_memory_sqlite(url: str) -> bool:
    """:memory: 必须整进程共用一条连接，否则每个连接都是空库。

    ``sqlite://`` 也是内存库。rstrip(\"/\") 会把它收成 ``sqlite:``，不能拿收完的字符串
    去比 ``sqlite://``。
    """
    normalized = (url or "").strip()
    if ":memory:" in normalized:
        return True
    return normalized.rstrip("/") in ("sqlite:", "sqlite")


def sqlite_engine_kwargs(url: str) -> dict:
    """文件 SQLite 用 NullPool，不在进程里囤连接。

    StaticPool 只适合 :memory:。文件库上用它，桌面模式里 API 请求线程、导入任务线程、
    流水线线程会在同一条连接上交错 BEGIN / COMMIT / ROLLBACK。
    默认 QueuePool（size 5 + overflow 10）会在会话没归还时打满，项目列表 / 详情 / 下载
    一起超时报 QueuePool limit reached（#175）。NullPool 每次取用都新建连接，用完即关，
    不设池上限；会话仍必须 close()，否则会泄漏文件句柄。
    """
    if is_memory_sqlite(url):
        return {"poolclass": StaticPool}
    return {"poolclass": NullPool}


# 创建数据库引擎
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30
        },
        pool_pre_ping=True,
        echo=False,  # 设置为True可以看到SQL语句
        **sqlite_engine_kwargs(DATABASE_URL),
    )
    if not is_memory_sqlite(DATABASE_URL):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()
else:
    # PostgreSQL配置
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )

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
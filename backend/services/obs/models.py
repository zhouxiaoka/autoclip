"""Desktop-only additive tables. Keep capture receipts after project deletion."""

from sqlalchemy import Column, Integer, String, Float, Text, Boolean, UniqueConstraint
from backend.models.base import Base


class ObsSettings(Base):
    __tablename__ = 'obs_settings'
    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    has_password = Column(Boolean, nullable=False, default=False)
    port = Column(Integer, nullable=False, default=4455)
    revision = Column(String(36), nullable=False, default='')
    directory = Column(Text, nullable=False, default='')
    consent = Column(String(64), nullable=False, default='')
    consent_epoch = Column(String(36), nullable=False, default='')
    consent_at = Column(Float, nullable=False, default=0)
    max_calls = Column(Integer, nullable=False, default=50)


class ObsCapture(Base):
    __tablename__ = 'obs_captures'
    id = Column(String(36), primary_key=True)
    path = Column(Text, nullable=False)
    start = Column(Float, nullable=False)
    end = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    created = Column(Float, nullable=False)
    epoch = Column(String(36), nullable=False)
    status = Column(String(32), nullable=False)
    dispatcher_pid = Column(Integer)
    dispatcher_start = Column(Float)
    file_key = Column(String(64), unique=True)
    project_id = Column(String(36), unique=True)


class ObsCall(Base):
    __tablename__ = 'obs_calls'
    __table_args__ = (UniqueConstraint('project_id', 'signature'),)
    id = Column(Integer, primary_key=True)
    project_id = Column(String(36), nullable=False, index=True)
    signature = Column(String(64), nullable=False)
    process = Column(String(36), nullable=False)
    result = Column(Text, nullable=True)


class ObsReplayFile(Base):
    """Recording identity observed at stop, for a later explicit import."""
    __tablename__ = 'obs_replay_files'
    capture_id = Column(String(36), primary_key=True)
    directory = Column(Text, nullable=False)
    identity = Column(String(64), nullable=False)

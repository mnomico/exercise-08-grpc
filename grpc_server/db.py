"""SQLAlchemy models and session handling for the node registry."""
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://noderegistry:noderegistry@localhost:5432/noderegistry",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    metadata_json = Column(JSON, default=dict)
    status = Column(String, default="ACTIVE")
    registered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)

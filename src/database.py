"""Database models and engine for PostgreSQL storage."""
from datetime import datetime, timezone

from decouple import config
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = (
    f"postgresql+psycopg://{config('POSTGRES_USER')}:{config('POSTGRES_PASSWORD')}"
    f"@{config('POSTGRES_HOST')}/{config('POSTGRES_DB')}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True)
    user_email = Column(String, unique=True, nullable=False)
    token_data = Column(JSONB, nullable=False)
    is_last_user = Column(DateTime(timezone=True), nullable=True)


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base_entries"

    id = Column(Integer, primary_key=True)
    user_email = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False, default="")


class KnowledgeBaseBackup(Base):
    __tablename__ = "knowledge_base_backups"

    id = Column(Integer, primary_key=True)
    user_email = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    user_email = Column(String, nullable=False)
    category = Column(String, nullable=False)  # "personal" or "professional"
    text = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_email", "category", "text", name="uq_reminder"),
    )


class CrucialEvent(Base):
    __tablename__ = "crucial_events"

    id = Column(Integer, primary_key=True)
    user_email = Column(String, nullable=False)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)  # "MM-DD" or "MM-Nth-sun"

    __table_args__ = (
        UniqueConstraint("user_email", "name", name="uq_crucial_event"),
    )


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=False)
    user_email = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def init_db():
    """Create all tables if they don't exist. Safe to call repeatedly."""
    Base.metadata.create_all(engine)

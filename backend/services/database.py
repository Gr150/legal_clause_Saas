"""
Claura — database.py
SQLAlchemy async database setup and table definitions
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Enum as SAEnum
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://claura:claura@localhost:5432/claura"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── TABLES ────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:           Mapped[int]           = mapped_column(Integer, primary_key=True)
    email:        Mapped[str]           = mapped_column(String(255), unique=True, nullable=False)
    password_hash:Mapped[str]           = mapped_column(String(255), nullable=False)
    company_name: Mapped[str]           = mapped_column(String(255), nullable=False)
    plan:         Mapped[str]           = mapped_column(String(50), default="free")
    created_at:   Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    contracts:    Mapped[list["Contract"]] = relationship("Contract", back_populates="user")


class Contract(Base):
    __tablename__ = "contracts"

    id:            Mapped[int]         = mapped_column(Integer, primary_key=True)
    user_id:       Mapped[int]         = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    filename:      Mapped[str]         = mapped_column(String(500), nullable=False)
    contract_type: Mapped[str]         = mapped_column(String(255), nullable=False)
    status:        Mapped[str]         = mapped_column(String(50), default="processing")
    high_risk:     Mapped[int]         = mapped_column(Integer, default=0)
    medium_risk:   Mapped[int]         = mapped_column(Integer, default=0)
    low_risk:      Mapped[int]         = mapped_column(Integer, default=0)
    verdict:       Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    uploaded_at:   Mapped[datetime]    = mapped_column(DateTime, default=datetime.utcnow)
    user:          Mapped["User"]      = relationship("User", back_populates="contracts")
    clauses:       Mapped[list["Clause"]] = relationship("Clause", back_populates="contract")


class Clause(Base):
    __tablename__ = "clauses"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int]           = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False)
    clause_text: Mapped[str]           = mapped_column(Text, nullable=False)
    clause_type: Mapped[str]           = mapped_column(String(255), nullable=False)
    risk_level:  Mapped[str]           = mapped_column(String(50), nullable=False)
    summary:     Mapped[str]           = mapped_column(Text, nullable=False)
    reason:      Mapped[str]           = mapped_column(Text, nullable=False)
    wording:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence:  Mapped[float]         = mapped_column(Float, default=0.9)
    contract:    Mapped["Contract"]    = relationship("Contract", back_populates="clauses")
    corrections: Mapped[list["Correction"]] = relationship("Correction", back_populates="clause")


class Correction(Base):
    __tablename__ = "corrections"

    id:               Mapped[int]           = mapped_column(Integer, primary_key=True)
    clause_id:        Mapped[int]           = mapped_column(Integer, ForeignKey("clauses.id"), nullable=False)
    user_id:          Mapped[int]           = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    corrected_type:   Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    corrected_risk:   Mapped[Optional[str]] = mapped_column(String(50),  nullable=True)
    corrected_reason: Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    created_at:       Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    clause:           Mapped["Clause"]      = relationship("Clause", back_populates="corrections")


# ── HELPERS ───────────────────────────────────────────────────────

async def init_db():
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency — yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

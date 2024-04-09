import logging
from asyncio import current_task, shield
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.declarative import declarative_base

from betatester_web_service.utils import settings

logger = logging.getLogger(__name__)

meta = MetaData(
    naming_convention={
        "ix": "%(table_name)s_%(column_0_name)s_idx",
        "fk": "%(table_name)s_%(column_0_name)s_%(referred_table_name)s_fk",
        "pk": "%(table_name)s_pkey",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
    },
)

Base = declarative_base(metadata=meta)

engine_to_bind = create_async_engine(
    settings.postgres_connection_string,
    pool_pre_ping=True,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_scoped_session(
    session_factory=async_sessionmaker(
        bind=engine_to_bind,
        expire_on_commit=True,
    ),
    scopefunc=current_task,
)


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[Any, AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await shield(session.close())
        await shield(SessionLocal.remove())


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_scope() as db:
        yield db


async def create_tables():
    engine = create_async_engine(settings.postgres_connection_string)
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables_dangerous():
    engine = create_async_engine(settings.postgres_connection_string)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def shutdown_session():
    await engine_to_bind.dispose()

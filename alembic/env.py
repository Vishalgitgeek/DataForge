from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

import app.models  # noqa: F401
from app.core.config import get_settings
from app.infrastructure.database import Base, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_sync(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = engine
    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations_sync)


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())

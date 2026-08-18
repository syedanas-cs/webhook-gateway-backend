import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 1. Import your application configuration and models
from app.core.config import settings
from app.models import Base  # Imports all models registered via Base

# Alembic Config object, which provides access to values within alembic.ini
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Point target_metadata to your SQLAlchemy DeclarativeBase metadata
target_metadata = Base.metadata

# 3. Inject our dynamic database URL directly from settings into Alembic's config
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detects column type changes (e.g. String(50) -> String(100))
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Detects column type changes in online mode
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool avoids connection leaks during one-off migration runs
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using asyncio."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
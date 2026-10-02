"""Alembic environment.

The database URL and metadata come from the application itself rather than
alembic.ini, so migrations always target the same database the app runs
against and never drift from `backend.config.settings`.
"""
from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

from backend.database import Base, engine

# Importing backend.database registers every model on Base.metadata, which is
# what `alembic revision --autogenerate` diffs against.
import backend.database  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _set_sqlite_foreign_keys(connection, enabled: bool) -> None:
    """Toggle FK enforcement on the raw DBAPI connection.

    backend.database turns `PRAGMA foreign_keys=ON` on for every connection.
    Batch migrations rebuild a table by dropping and recreating it, which makes
    any ON DELETE CASCADE pointing at that table fire and silently delete child
    rows — rebuilding `tg_bot_configs` would wipe `tg_channels`.

    The pragma is issued through the driver connection rather than
    `exec_driver_sql`, because the latter opens an implicit SQLAlchemy
    transaction; Alembic would then treat its own transaction as nested and
    never commit, rolling the whole migration back. SQLite also ignores this
    pragma inside a transaction, so it must run while none is open.
    """
    connection.connection.driver_connection.execute(
        f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}"
    )


def run_migrations_online() -> None:
    """Run migrations against the live database."""
    connectable = engine.execution_options(poolclass=pool.NullPool)

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        if is_sqlite:
            _set_sqlite_foreign_keys(connection, False)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER most things in place; batch mode rebuilds the
            # table instead, so the same migration script works on SQLite and
            # MySQL alike.
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()

        # Alembic's transaction block does not always commit when the
        # connection was already in use; commit explicitly so the DDL sticks.
        if connection.in_transaction():
            connection.commit()

        if is_sqlite:
            _set_sqlite_foreign_keys(connection, True)
            # A rebuild that broke referential integrity must not pass silently.
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"Migration left foreign key violations: {violations}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

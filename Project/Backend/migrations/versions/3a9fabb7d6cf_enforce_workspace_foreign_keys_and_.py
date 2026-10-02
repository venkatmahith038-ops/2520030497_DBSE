"""enforce workspace foreign keys and token hash index

The `workspace_id` columns were originally added by the hand-rolled
`ensure_saas_columns()` helper as plain `INTEGER`, with no foreign key. The
models declared `ondelete="CASCADE"`, but nothing enforced it: deleting a
workspace left orphaned accounts, templates, opt-outs and bot configs behind
instead of removing them. This reconciles the database with the models.

`tg_bot_configs.bot_token_hash` was likewise created without its index, so the
duplicate-bot lookup on insert was a full table scan.

Revision ID: 3a9fabb7d6cf
Revises: 44a67695df92
Create Date: 2026-07-25 07:26:26.666052
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a9fabb7d6cf'
down_revision: Union[str, Sequence[str], None] = '44a67695df92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, parent table, parent column, constraint name, ondelete)
FOREIGN_KEYS = [
    ("accounts", "workspace_id", "workspaces", "id", "fk_accounts_workspace_id", "CASCADE"),
    ("message_templates", "workspace_id", "workspaces", "id", "fk_message_templates_workspace_id", "CASCADE"),
    ("opt_outs", "workspace_id", "workspaces", "id", "fk_opt_outs_workspace_id", "CASCADE"),
    ("tg_bot_configs", "workspace_id", "workspaces", "id", "fk_tg_bot_configs_workspace_id", "CASCADE"),
    ("tg_channels", "user_id", "users", "id", "fk_tg_channels_user_id", "SET NULL"),
]


def _clear_orphans() -> None:
    """Null out references to rows that no longer exist.

    Because the constraint was never enforced, a deployment may already hold
    dangling ids. Adding the foreign key on top of those would fail, so they
    are cleared first — the parent row is gone either way.
    """
    connection = op.get_bind()
    for table, column, parent, parent_column, _, _ in FOREIGN_KEYS:
        connection.execute(sa.text(
            f"UPDATE {table} SET {column} = NULL "
            f"WHERE {column} IS NOT NULL "
            f"AND {column} NOT IN (SELECT {parent_column} FROM {parent})"
        ))


def upgrade() -> None:
    _clear_orphans()

    for table, column, parent, parent_column, name, ondelete in FOREIGN_KEYS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            if table == "tg_bot_configs":
                batch_op.create_index("ix_tg_bot_configs_bot_token_hash", ["bot_token_hash"], unique=False)
            batch_op.create_foreign_key(name, parent, [column], [parent_column], ondelete=ondelete)


def downgrade() -> None:
    for table, _, _, _, name, _ in reversed(FOREIGN_KEYS):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(name, type_="foreignkey")
            if table == "tg_bot_configs":
                batch_op.drop_index("ix_tg_bot_configs_bot_token_hash")

"""users.email: normalize to lowercase and add unique index

Revision ID: b1a2c3d4e5f6
Revises: a0790c76a129
Create Date: 2026-06-10 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, None] = "a0790c76a129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Normalize existing emails to lowercase before enforcing uniqueness,
    # otherwise rows that already differ only by case would block the
    # constraint from being added.
    op.execute("UPDATE users SET email = LOWER(email) WHERE email <> LOWER(email)")

    # Fail loudly if normalization revealed duplicates — the admin must
    # decide how to merge before the constraint can be created.
    duplicate = bind.execute(
        sa.text(
            "SELECT email, COUNT(*) AS c FROM users "
            "GROUP BY email HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).fetchone()
    if duplicate is not None:
        raise RuntimeError(
            f"Cannot add UNIQUE constraint on users.email: duplicate "
            f"{duplicate[0]!r} ({duplicate[1]} rows). Resolve manually "
            "before re-running this migration."
        )

    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")

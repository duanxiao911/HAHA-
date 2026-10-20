"""Require a globally unique login email for personal account registration."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0016"
down_revision = "20261018_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            """SELECT lower(email) AS normalized_email, count(*) AS credential_count
               FROM auth_credentials
               GROUP BY lower(email)
               HAVING count(*) > 1"""
        )
    ).fetchall()
    if duplicates:
        raise RuntimeError(
            "auth_credentials contains duplicate normalized emails; "
            "reconcile legacy internal accounts before enabling self registration"
        )
    op.create_index(
        "uq_auth_credential_email_lower",
        "auth_credentials",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_auth_credential_email_lower", table_name="auth_credentials")

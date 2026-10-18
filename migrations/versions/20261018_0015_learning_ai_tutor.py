"""Add durable, idempotent AI tutor interactions."""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0015"
down_revision = "20261018_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tutor_interactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("answer", sa.String(4000), nullable=False, server_default=""),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "workspace_id",
            "idempotency_key",
            name="uq_tutor_interaction_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')",
            name="ck_tutor_interaction_status",
        ),
    )
    op.create_index(
        "ix_tutor_interactions_owner_created",
        "tutor_interactions",
        ["user_id", "workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tutor_interactions_owner_created", table_name="tutor_interactions")
    op.drop_table("tutor_interactions")

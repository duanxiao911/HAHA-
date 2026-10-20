"""Persist auditable, idempotent AI shopping-advisor interactions."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0018"
down_revision = "20261020_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commerce_advisor_interactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("answer", sa.String(4000), nullable=False),
        sa.Column("recommendations_json", sa.String(12000), nullable=False),
        sa.Column("suggestions_json", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("request_id", sa.String(200), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint(
            "user_id", "workspace_id", "idempotency_key", name="uq_commerce_advisor_key"
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed')", name="ck_commerce_advisor_status"
        ),
        sa.CheckConstraint("input_tokens >= 0", name="ck_commerce_advisor_input_tokens"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_commerce_advisor_output_tokens"),
    )
    op.create_index(
        "ix_commerce_advisor_history",
        "commerce_advisor_interactions",
        ["user_id", "workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commerce_advisor_history", table_name="commerce_advisor_interactions"
    )
    op.drop_table("commerce_advisor_interactions")

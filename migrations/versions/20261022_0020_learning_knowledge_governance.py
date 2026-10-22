"""Add auditable knowledge contribution review isolation for S08."""

import sqlalchemy as sa
from alembic import op

revision = "20261022_0020"
down_revision = "20261021_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_contributions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("source_title", sa.String(300), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewer_note", sa.String(2000), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("submitted_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','submitted','approved','rejected')",
            name="ck_knowledge_contribution_status",
        ),
    )
    op.create_index(
        "ix_knowledge_contributions_owner_updated",
        "knowledge_contributions", ["user_id", "workspace_id", "updated_at"],
    )
    op.create_index(
        "ix_knowledge_contributions_review_queue",
        "knowledge_contributions", ["workspace_id", "status", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_contributions_review_queue", table_name="knowledge_contributions")
    op.drop_index("ix_knowledge_contributions_owner_updated", table_name="knowledge_contributions")
    op.drop_table("knowledge_contributions")

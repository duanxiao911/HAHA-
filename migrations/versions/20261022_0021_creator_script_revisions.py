"""Add immutable human script revisions for creator S09."""

import sqlalchemy as sa
from alembic import op

revision = "20261022_0021"
down_revision = "20261022_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_revisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("base_script_id", sa.String(64), sa.ForeignKey("script_versions.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("review_note", sa.String(2000), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("review_status IN ('draft','reviewed')", name="ck_script_revision_review_status"),
        sa.UniqueConstraint("run_id", "version", name="uq_script_revision_run_version"),
    )
    op.create_index("ix_script_revisions_project", "script_revisions", ["project_id"])
    op.create_index("ix_script_revisions_run_updated", "script_revisions", ["run_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_script_revisions_run_updated", table_name="script_revisions")
    op.drop_index("ix_script_revisions_project", table_name="script_revisions")
    op.drop_table("script_revisions")

"""Create versioned creator core tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260929_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_table(
        "brief_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("project_id", "version", name="uq_brief_project_version"),
    )
    op.create_index("ix_brief_versions_project_id", "brief_versions", ["project_id"])
    op.create_table(
        "runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("brief_version_id", sa.String(64), sa.ForeignKey("brief_versions.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model_preference", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=False),
        sa.Column("error_message", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_runs_project_id", "runs", ["project_id"])
    op.create_index("ix_runs_brief_version_id", "runs", ["brief_version_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_table(
        "script_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False, unique=True),
        sa.Column("brief_version_id", sa.String(64), sa.ForeignKey("brief_versions.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("project_id", "version", name="uq_script_project_version"),
    )
    op.create_index("ix_script_versions_project_id", "script_versions", ["project_id"])


def downgrade() -> None:
    op.drop_table("script_versions")
    op.drop_table("runs")
    op.drop_table("brief_versions")
    op.drop_table("projects")

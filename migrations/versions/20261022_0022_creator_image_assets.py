"""Add durable creator image requests and immutable assets.

Revision ID: 20261022_0022
Revises: 20261022_0021
"""

import sqlalchemy as sa
from alembic import op

revision = "20261022_0022"
down_revision = "20261022_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_generation_requests",
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("prompt", sa.String(4000), nullable=False),
        sa.Column("negative_prompt", sa.String(2000), nullable=False, server_default=""),
        sa.Column("size", sa.String(20), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("watermark", sa.Boolean(), nullable=False),
        sa.Column("reference_asset_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("count >= 1 AND count <= 4", name="ck_image_request_count"),
        sa.CheckConstraint("size IN ('1K', '2K', '4K')", name="ck_image_request_size"),
    )
    op.create_index(
        "ix_image_generation_requests_project_created",
        "image_generation_requests",
        ["project_id", "created_at"],
    )
    op.create_table(
        "creator_image_assets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("source_url_host", sa.String(255), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("run_id", "version", name="uq_creator_image_run_version"),
        sa.UniqueConstraint("storage_key", name="uq_creator_image_storage_key"),
        sa.CheckConstraint("byte_size > 0", name="ck_creator_image_byte_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_creator_image_dimensions"),
    )
    op.create_index(
        "ix_creator_image_assets_project_created",
        "creator_image_assets",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_creator_image_assets_workspace_sha256",
        "creator_image_assets",
        ["workspace_id", "sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_creator_image_assets_workspace_sha256", table_name="creator_image_assets")
    op.drop_index("ix_creator_image_assets_project_created", table_name="creator_image_assets")
    op.drop_table("creator_image_assets")
    op.drop_index("ix_image_generation_requests_project_created", table_name="image_generation_requests")
    op.drop_table("image_generation_requests")

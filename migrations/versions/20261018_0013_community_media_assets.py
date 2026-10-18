"""Add durable community submission media assets."""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0013"
down_revision = "20261016_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_media_assets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("owner_user_id", sa.String(200), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("declared_mime_type", sa.String(100), nullable=False),
        sa.Column("detected_mime_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["community_submissions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "owner_user_id",
            "idempotency_key",
            name="uq_community_media_idempotency",
        ),
        sa.UniqueConstraint("storage_key", name="uq_community_media_storage_key"),
    )
    op.create_index(
        "ix_community_media_submission",
        "community_media_assets",
        ["workspace_id", "submission_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_community_media_submission", table_name="community_media_assets"
    )
    op.drop_table("community_media_assets")

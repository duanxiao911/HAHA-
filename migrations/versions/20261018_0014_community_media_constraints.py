"""Constrain durable community media metadata."""

from alembic import op

revision = "20261018_0014"
down_revision = "20261018_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_community_media_kind",
        "community_media_assets",
        "kind IN ('video', 'image')",
    )
    op.create_check_constraint(
        "ck_community_media_size", "community_media_assets", "byte_size > 0"
    )
    op.create_check_constraint(
        "ck_community_media_status", "community_media_assets", "status = 'ready'"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_community_media_status", "community_media_assets", type_="check"
    )
    op.drop_constraint(
        "ck_community_media_size", "community_media_assets", type_="check"
    )
    op.drop_constraint(
        "ck_community_media_kind", "community_media_assets", type_="check"
    )

"""Add idempotency keys for commerce product creation."""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0012"
down_revision = "20261016_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commerce_products",
        sa.Column("creation_key", sa.String(200), nullable=True),
    )
    op.execute(
        "UPDATE commerce_products "
        "SET creation_key = 'legacy:' || id "
        "WHERE creation_key IS NULL"
    )
    op.alter_column(
        "commerce_products",
        "creation_key",
        existing_type=sa.String(200),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_commerce_product_creation_key",
        "commerce_products",
        ["seller_user_id", "workspace_id", "creation_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_commerce_product_creation_key",
        "commerce_products",
        type_="unique",
    )
    op.drop_column("commerce_products", "creation_key")

"""Add Gate D auditable commerce sandbox state."""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0011"
down_revision = "20261016_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commerce_stores",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("owner_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("workspace_id", "owner_user_id", name="uq_commerce_store_owner"),
        sa.CheckConstraint("status IN ('active','suspended')", name="ck_commerce_store_status"),
    )
    op.create_table(
        "commerce_products",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.String(64), sa.ForeignKey("commerce_stores.id"), nullable=False),
        sa.Column("seller_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source_note", sa.String(1000), nullable=False),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewer_note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("price_cents > 0", name="ck_commerce_product_price"),
        sa.CheckConstraint("status IN ('draft','submitted','approved','rejected','listed','delisted')", name="ck_commerce_product_status"),
    )
    op.create_index("ix_commerce_product_catalog", "commerce_products", ["workspace_id", "status", "updated_at"])
    op.create_index("ix_commerce_product_seller", "commerce_products", ["workspace_id", "seller_user_id", "updated_at"])
    op.create_table(
        "commerce_inventory",
        sa.Column("product_id", sa.String(64), sa.ForeignKey("commerce_products.id"), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("available_qty", sa.Integer(), nullable=False),
        sa.Column("sold_qty", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("available_qty >= 0 AND sold_qty >= 0", name="ck_commerce_inventory_nonnegative"),
    )
    op.create_table(
        "commerce_cart_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("buyer_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("product_id", sa.String(64), sa.ForeignKey("commerce_products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("buyer_user_id", "workspace_id", "product_id", name="uq_commerce_cart_owner_product"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 99", name="ck_commerce_cart_quantity"),
    )
    op.create_index("ix_commerce_cart_owner", "commerce_cart_items", ["buyer_user_id", "workspace_id", "updated_at"])
    op.create_table(
        "commerce_orders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("buyer_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("store_id", sa.String(64), sa.ForeignKey("commerce_stores.id"), nullable=False),
        sa.Column("seller_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("checkout_key", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("buyer_user_id", "workspace_id", "checkout_key", name="uq_commerce_checkout_key"),
        sa.CheckConstraint("status IN ('awaiting_sandbox_payment','paid','shipped','completed','after_sales','cancelled')", name="ck_commerce_order_status"),
        sa.CheckConstraint("total_cents > 0", name="ck_commerce_order_total"),
    )
    op.create_index("ix_commerce_order_buyer", "commerce_orders", ["buyer_user_id", "workspace_id", "created_at"])
    op.create_index("ix_commerce_order_seller", "commerce_orders", ["seller_user_id", "workspace_id", "created_at"])
    op.create_table(
        "commerce_order_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("commerce_orders.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("product_id", sa.String(64), sa.ForeignKey("commerce_products.id"), nullable=False),
        sa.Column("title_snapshot", sa.String(200), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_commerce_order_item_order", "commerce_order_items", ["order_id", "workspace_id"])
    op.create_table(
        "commerce_payments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("commerce_orders.id"), nullable=False),
        sa.Column("buyer_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("order_id", "workspace_id", name="uq_commerce_payment_order"),
        sa.UniqueConstraint("buyer_user_id", "workspace_id", "idempotency_key", name="uq_commerce_payment_key"),
        sa.CheckConstraint("provider = 'internal_sandbox'", name="ck_commerce_payment_provider"),
        sa.CheckConstraint("status = 'authorized'", name="ck_commerce_payment_status"),
    )
    op.create_table(
        "commerce_fulfillments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("commerce_orders.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("seller_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tracking_note", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("order_id", "workspace_id", name="uq_commerce_fulfillment_order"),
        sa.CheckConstraint("status IN ('shipped','delivered')", name="ck_commerce_fulfillment_status"),
    )
    op.create_table(
        "commerce_after_sales",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("commerce_orders.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("buyer_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("seller_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decision_note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("order_id", "workspace_id", name="uq_commerce_after_sale_order"),
        sa.CheckConstraint("status IN ('requested','approved','rejected','resolved')", name="ck_commerce_after_sale_status"),
    )
    op.create_index("ix_commerce_after_sale_owner", "commerce_after_sales", ["workspace_id", "buyer_user_id", "updated_at"])
    op.create_table(
        "commerce_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(200), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("detail_json", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("actor_user_id", "workspace_id", "idempotency_key", name="uq_commerce_event_key"),
    )
    op.create_index("ix_commerce_event_entity", "commerce_events", ["workspace_id", "entity_type", "entity_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_commerce_event_entity", table_name="commerce_events")
    op.drop_table("commerce_events")
    op.drop_index("ix_commerce_after_sale_owner", table_name="commerce_after_sales")
    op.drop_table("commerce_after_sales")
    op.drop_table("commerce_fulfillments")
    op.drop_table("commerce_payments")
    op.drop_index("ix_commerce_order_item_order", table_name="commerce_order_items")
    op.drop_table("commerce_order_items")
    op.drop_index("ix_commerce_order_seller", table_name="commerce_orders")
    op.drop_index("ix_commerce_order_buyer", table_name="commerce_orders")
    op.drop_table("commerce_orders")
    op.drop_index("ix_commerce_cart_owner", table_name="commerce_cart_items")
    op.drop_table("commerce_cart_items")
    op.drop_table("commerce_inventory")
    op.drop_index("ix_commerce_product_seller", table_name="commerce_products")
    op.drop_index("ix_commerce_product_catalog", table_name="commerce_products")
    op.drop_table("commerce_products")
    op.drop_table("commerce_stores")

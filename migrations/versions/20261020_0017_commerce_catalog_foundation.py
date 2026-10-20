"""Add the structured commerce catalog foundation without rewriting Gate D history."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0017"
down_revision = "20261020_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commerce_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("slug", name="uq_commerce_category_slug"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_commerce_category_status"),
        sa.CheckConstraint("version >= 1", name="ck_commerce_category_version"),
    )
    op.create_index(
        "ix_commerce_category_status_sort",
        "commerce_categories",
        ["status", "sort_order"],
    )
    now = "2026-10-20T00:00:00.000+00:00"
    categories = (
        ("category-weaving", "weaving", "织绣与编织", "织造、刺绣、染色与编织相关作品。", 10),
        ("category-ceramics", "ceramics", "陶瓷与烧造", "陶瓷、琉璃及相关烧造作品。", 20),
        ("category-woodwork", "woodwork", "木作与雕刻", "木作、雕刻、漆艺及相关作品。", 30),
        ("category-metalwork", "metalwork", "金工与首饰", "金属工艺、首饰及相关作品。", 40),
        ("category-gifts", "gifts", "文创与礼赠", "适合日常使用或礼赠的文化创意商品。", 50),
        ("category-other", "other", "其他作品", "尚未归入专门类目的作品。", 999),
    )
    table = sa.table(
        "commerce_categories",
        sa.column("id", sa.String),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("status", sa.String),
        sa.column("version", sa.Integer),
        sa.column("created_at", sa.String),
        sa.column("updated_at", sa.String),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": category_id,
                "slug": slug,
                "name": name,
                "description": description,
                "sort_order": sort_order,
                "status": "active",
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
            for category_id, slug, name, description, sort_order in categories
        ],
    )

    op.add_column(
        "commerce_products",
        sa.Column(
            "category_id",
            sa.String(64),
            sa.ForeignKey("commerce_categories.id"),
            nullable=False,
            server_default="category-other",
        ),
    )
    op.add_column(
        "commerce_products",
        sa.Column("craft_type", sa.String(120), nullable=False, server_default=""),
    )
    op.add_column(
        "commerce_products",
        sa.Column("origin_region", sa.String(120), nullable=False, server_default=""),
    )
    op.add_column(
        "commerce_products",
        sa.Column("season_tag", sa.String(80), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_commerce_product_discovery",
        "commerce_products",
        ["workspace_id", "status", "category_id", "updated_at"],
    )

    op.create_table(
        "commerce_product_media",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("product_id", sa.String(64), sa.ForeignKey("commerce_products.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("alt_text", sa.String(300), nullable=False),
        sa.Column("source_note", sa.String(1000), nullable=False),
        sa.Column("rights_status", sa.String(32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("product_id", "workspace_id", "storage_key", name="uq_commerce_product_media_key"),
        sa.CheckConstraint("media_type IN ('image','video')", name="ck_commerce_product_media_type"),
        sa.CheckConstraint("rights_status IN ('seller_declared','reviewed_internal')", name="ck_commerce_product_media_rights"),
        sa.CheckConstraint("version >= 1", name="ck_commerce_product_media_version"),
    )
    op.create_index(
        "ix_commerce_product_media_product",
        "commerce_product_media",
        ["workspace_id", "product_id", "sort_order"],
    )

    op.create_table(
        "commerce_product_variants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("product_id", sa.String(64), sa.ForeignKey("commerce_products.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("sku", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("attributes_json", sa.String(2000), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("workspace_id", "sku", name="uq_commerce_variant_workspace_sku"),
        sa.CheckConstraint("price_cents > 0", name="ck_commerce_variant_price"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_commerce_variant_status"),
        sa.CheckConstraint("is_default IN (0,1)", name="ck_commerce_variant_default_flag"),
        sa.CheckConstraint("version >= 1", name="ck_commerce_variant_version"),
    )
    op.create_index(
        "ix_commerce_variant_product",
        "commerce_product_variants",
        ["workspace_id", "product_id", "status"],
    )
    op.create_index(
        "uq_commerce_variant_one_default",
        "commerce_product_variants",
        ["product_id", "workspace_id"],
        unique=True,
        postgresql_where=sa.text("is_default = 1"),
    )
    op.execute(
        sa.text(
            """INSERT INTO commerce_product_variants
               (id, product_id, workspace_id, sku, name, attributes_json,
                price_cents, currency, status, is_default, version, created_at, updated_at)
               SELECT 'variant_' || id, id, workspace_id,
                      'DEFAULT-' || upper(right(id, 12)), '默认规格', '{}',
                      price_cents, currency, 'active', 1, 1, created_at, updated_at
               FROM commerce_products"""
        )
    )

    op.create_table(
        "commerce_product_heritage_links",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("product_id", sa.String(64), sa.ForeignKey("commerce_products.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("heritage_ref", sa.String(200), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("claim_status", sa.String(32), nullable=False),
        sa.Column("source_note", sa.String(1000), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint(
            "product_id",
            "workspace_id",
            "heritage_ref",
            "relation_type",
            name="uq_commerce_product_heritage_link",
        ),
        sa.CheckConstraint(
            "claim_status IN ('seller_declared','source_linked','reviewed_internal')",
            name="ck_commerce_heritage_claim_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_commerce_heritage_link_version"),
    )
    op.create_index(
        "ix_commerce_heritage_link_product",
        "commerce_product_heritage_links",
        ["workspace_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_commerce_heritage_link_product", table_name="commerce_product_heritage_links")
    op.drop_table("commerce_product_heritage_links")
    op.drop_index("uq_commerce_variant_one_default", table_name="commerce_product_variants")
    op.drop_index("ix_commerce_variant_product", table_name="commerce_product_variants")
    op.drop_table("commerce_product_variants")
    op.drop_index("ix_commerce_product_media_product", table_name="commerce_product_media")
    op.drop_table("commerce_product_media")
    op.drop_index("ix_commerce_product_discovery", table_name="commerce_products")
    op.drop_column("commerce_products", "season_tag")
    op.drop_column("commerce_products", "origin_region")
    op.drop_column("commerce_products", "craft_type")
    op.drop_column("commerce_products", "category_id")
    op.drop_index("ix_commerce_category_status_sort", table_name="commerce_categories")
    op.drop_table("commerce_categories")


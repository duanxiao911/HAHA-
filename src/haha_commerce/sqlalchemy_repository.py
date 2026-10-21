"""SQLAlchemy persistence adapter for the Gate D transaction sandbox."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    delete,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from haha_commerce.domain import (
    AfterSale,
    CartItem,
    CommerceConflictError,
    CommerceNotFoundError,
    CommercePermissionError,
    Fulfillment,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductCategory,
    ProductHeritageLink,
    ProductMedia,
    ProductVariant,
    ShoppingAdvisorInteraction,
    Store,
)

commerce_metadata = MetaData()

commerce_stores = Table(
    "commerce_stores", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False),
    Column("owner_user_id", String(200), nullable=False),
    Column("name", String(200), nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("workspace_id", "owner_user_id", name="uq_commerce_store_owner"),
)

commerce_products = Table(
    "commerce_products", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False),
    Column("store_id", String(64), nullable=False),
    Column("seller_user_id", String(200), nullable=False),
    Column("title", String(200), nullable=False),
    Column("summary", String(2000), nullable=False),
    Column("price_cents", Integer, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("source_note", String(1000), nullable=False),
    Column("provenance", String(32), nullable=False),
    Column("creation_key", String(200), nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("reviewer_note", String(1000), nullable=False),
    Column("reviewed_by", String(200), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("category_id", String(64), nullable=False, default="category-other"),
    Column("craft_type", String(120), nullable=False, default=""),
    Column("origin_region", String(120), nullable=False, default=""),
    Column("season_tag", String(80), nullable=False, default=""),
    UniqueConstraint(
        "seller_user_id",
        "workspace_id",
        "creation_key",
        name="uq_commerce_product_creation_key",
    ),
)
Index("ix_commerce_product_catalog", commerce_products.c.workspace_id, commerce_products.c.status, commerce_products.c.updated_at)
Index("ix_commerce_product_seller", commerce_products.c.workspace_id, commerce_products.c.seller_user_id, commerce_products.c.updated_at)
Index("ix_commerce_product_discovery", commerce_products.c.workspace_id, commerce_products.c.status, commerce_products.c.category_id, commerce_products.c.updated_at)

commerce_categories = Table(
    "commerce_categories", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("slug", String(80), nullable=False, unique=True),
    Column("name", String(120), nullable=False),
    Column("description", String(500), nullable=False),
    Column("sort_order", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)
Index("ix_commerce_category_status_sort", commerce_categories.c.status, commerce_categories.c.sort_order)

commerce_product_media = Table(
    "commerce_product_media", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("product_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("media_type", String(20), nullable=False),
    Column("storage_key", String(500), nullable=False),
    Column("alt_text", String(300), nullable=False),
    Column("source_note", String(1000), nullable=False),
    Column("rights_status", String(32), nullable=False),
    Column("sort_order", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("product_id", "workspace_id", "storage_key", name="uq_commerce_product_media_key"),
)
Index("ix_commerce_product_media_product", commerce_product_media.c.workspace_id, commerce_product_media.c.product_id, commerce_product_media.c.sort_order)

commerce_product_variants = Table(
    "commerce_product_variants", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("product_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("sku", String(120), nullable=False),
    Column("name", String(200), nullable=False),
    Column("attributes_json", String(2000), nullable=False),
    Column("price_cents", Integer, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("status", String(20), nullable=False),
    Column("is_default", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("workspace_id", "sku", name="uq_commerce_variant_workspace_sku"),
)
Index("ix_commerce_variant_product", commerce_product_variants.c.workspace_id, commerce_product_variants.c.product_id, commerce_product_variants.c.status)

commerce_product_heritage_links = Table(
    "commerce_product_heritage_links", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("product_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("heritage_ref", String(200), nullable=False),
    Column("relation_type", String(32), nullable=False),
    Column("claim_status", String(32), nullable=False),
    Column("source_note", String(1000), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("product_id", "workspace_id", "heritage_ref", "relation_type", name="uq_commerce_product_heritage_link"),
)
Index("ix_commerce_heritage_link_product", commerce_product_heritage_links.c.workspace_id, commerce_product_heritage_links.c.product_id)

commerce_advisor_interactions = Table(
    "commerce_advisor_interactions", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(200), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("question", String(1000), nullable=False),
    Column("answer", String(4000), nullable=False),
    Column("recommendations_json", String(12000), nullable=False),
    Column("suggestions_json", String(2000), nullable=False),
    Column("status", String(20), nullable=False),
    Column("mode", String(40), nullable=False),
    Column("model", String(120), nullable=False),
    Column("provider", String(80), nullable=False),
    Column("request_id", String(200), nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("error_code", String(120), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("user_id", "workspace_id", "idempotency_key", name="uq_commerce_advisor_key"),
)
Index("ix_commerce_advisor_history", commerce_advisor_interactions.c.user_id, commerce_advisor_interactions.c.workspace_id, commerce_advisor_interactions.c.created_at)

commerce_inventory = Table(
    "commerce_inventory", commerce_metadata,
    Column("product_id", String(64), primary_key=True),
    Column("workspace_id", String(100), primary_key=True),
    Column("available_qty", Integer, nullable=False),
    Column("sold_qty", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("updated_at", String(40), nullable=False),
)

commerce_cart_items = Table(
    "commerce_cart_items", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("buyer_user_id", String(200), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("product_id", String(64), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("buyer_user_id", "workspace_id", "product_id", name="uq_commerce_cart_owner_product"),
)
Index("ix_commerce_cart_owner", commerce_cart_items.c.buyer_user_id, commerce_cart_items.c.workspace_id, commerce_cart_items.c.updated_at)

commerce_orders = Table(
    "commerce_orders", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("buyer_user_id", String(200), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("store_id", String(64), nullable=False),
    Column("seller_user_id", String(200), nullable=False),
    Column("status", String(32), nullable=False),
    Column("total_cents", Integer, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("checkout_key", String(200), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("buyer_user_id", "workspace_id", "checkout_key", name="uq_commerce_checkout_key"),
)
Index("ix_commerce_order_buyer", commerce_orders.c.buyer_user_id, commerce_orders.c.workspace_id, commerce_orders.c.created_at)
Index("ix_commerce_order_seller", commerce_orders.c.seller_user_id, commerce_orders.c.workspace_id, commerce_orders.c.created_at)

commerce_order_items = Table(
    "commerce_order_items", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("order_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("product_id", String(64), nullable=False),
    Column("title_snapshot", String(200), nullable=False),
    Column("unit_price_cents", Integer, nullable=False),
    Column("quantity", Integer, nullable=False),
)
Index("ix_commerce_order_item_order", commerce_order_items.c.order_id, commerce_order_items.c.workspace_id)

commerce_payments = Table(
    "commerce_payments", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("order_id", String(64), nullable=False),
    Column("buyer_user_id", String(200), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("provider", String(40), nullable=False),
    Column("status", String(20), nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("order_id", "workspace_id", name="uq_commerce_payment_order"),
    UniqueConstraint("buyer_user_id", "workspace_id", "idempotency_key", name="uq_commerce_payment_key"),
)

commerce_fulfillments = Table(
    "commerce_fulfillments", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("order_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("seller_user_id", String(200), nullable=False),
    Column("status", String(20), nullable=False),
    Column("tracking_note", String(500), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("order_id", "workspace_id", name="uq_commerce_fulfillment_order"),
)

commerce_after_sales = Table(
    "commerce_after_sales", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("order_id", String(64), nullable=False),
    Column("workspace_id", String(100), nullable=False),
    Column("buyer_user_id", String(200), nullable=False),
    Column("seller_user_id", String(200), nullable=False),
    Column("reason", String(1000), nullable=False),
    Column("status", String(20), nullable=False),
    Column("decision_note", String(1000), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("order_id", "workspace_id", name="uq_commerce_after_sale_order"),
)
Index("ix_commerce_after_sale_owner", commerce_after_sales.c.workspace_id, commerce_after_sales.c.buyer_user_id, commerce_after_sales.c.updated_at)

commerce_events = Table(
    "commerce_events", commerce_metadata,
    Column("id", String(64), primary_key=True),
    Column("workspace_id", String(100), nullable=False),
    Column("actor_user_id", String(200), nullable=False),
    Column("event_type", String(80), nullable=False),
    Column("entity_type", String(32), nullable=False),
    Column("entity_id", String(64), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("detail_json", String(4000), nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("actor_user_id", "workspace_id", "idempotency_key", name="uq_commerce_event_key"),
)
Index("ix_commerce_event_entity", commerce_events.c.workspace_id, commerce_events.c.entity_type, commerce_events.c.entity_id, commerce_events.c.created_at)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _engine(database_url: str) -> Engine:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url == "sqlite+pysqlite:///:memory:":
        options.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(database_url, **options)


def _url_from_path(path: str | Path) -> str:
    if str(path) == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    return f"sqlite+pysqlite:///{Path(path).resolve().as_posix()}"


_DEFAULT_CATEGORIES = (
    ("category-weaving", "weaving", "织绣与编织", "织造、刺绣、染色与编织相关作品。", 10),
    ("category-ceramics", "ceramics", "陶瓷与烧造", "陶瓷、琉璃及相关烧造作品。", 20),
    ("category-woodwork", "woodwork", "木作与雕刻", "木作、雕刻、漆艺及相关作品。", 30),
    ("category-metalwork", "metalwork", "金工与首饰", "金属工艺、首饰及相关作品。", 40),
    ("category-gifts", "gifts", "文创与礼赠", "适合日常使用或礼赠的文化创意商品。", 50),
    ("category-other", "other", "其他作品", "尚未归入专门类目的作品。", 999),
)


class SQLAlchemyCommerceRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine = _engine(database_url)
        if create_schema:
            commerce_metadata.create_all(self.engine)
            self._seed_categories()

    @classmethod
    def for_sqlite_path(cls, path: str | Path) -> SQLAlchemyCommerceRepository:
        return cls(_url_from_path(path), create_schema=True)

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            return connection.scalar(select(1)) == 1

    def _seed_categories(self) -> None:
        now = _now()
        with self.engine.begin() as connection:
            for category_id, slug, name, description, sort_order in _DEFAULT_CATEGORIES:
                values = {
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
                if connection.dialect.name == "sqlite":
                    connection.execute(
                        sqlite_insert(commerce_categories)
                        .values(**values)
                        .on_conflict_do_nothing(index_elements=[commerce_categories.c.slug])
                    )
                elif connection.dialect.name == "postgresql":
                    connection.execute(
                        postgresql_insert(commerce_categories)
                        .values(**values)
                        .on_conflict_do_nothing(index_elements=[commerce_categories.c.slug])
                    )

    @staticmethod
    def _row(model: type[Any], row: Any) -> Any:
        return model(**dict(row._mapping)) if row else None

    @staticmethod
    def _event(connection: Any, *, actor: str, workspace_id: str, event_type: str, entity_type: str, entity_id: str, key: str, detail: str = "") -> None:
        values = {
            "id": f"cevt_{uuid4().hex}", "workspace_id": workspace_id,
            "actor_user_id": actor, "event_type": event_type,
            "entity_type": entity_type, "entity_id": entity_id,
            "idempotency_key": key, "detail_json": detail, "created_at": _now(),
        }
        connection.execute(commerce_events.insert().values(**values))

    def ensure_store(self, user_id: str, workspace_id: str, name: str) -> Store:
        with self.engine.begin() as connection:
            row = connection.execute(select(commerce_stores).where(
                commerce_stores.c.owner_user_id == user_id,
                commerce_stores.c.workspace_id == workspace_id,
            )).first()
            if row:
                return self._row(Store, row)
            now = _now()
            store = Store(f"store_{uuid4().hex}", workspace_id, user_id, name, "active", 1, now, now)
            connection.execute(commerce_stores.insert().values(**asdict(store)))
            return store

    def get_store(self, user_id: str, workspace_id: str) -> Store | None:
        with self.engine.connect() as connection:
            return self._row(Store, connection.execute(select(commerce_stores).where(
                commerce_stores.c.owner_user_id == user_id,
                commerce_stores.c.workspace_id == workspace_id,
            )).first())

    def get_product(self, product_id: str, workspace_id: str) -> Product | None:
        with self.engine.connect() as connection:
            return self._row(Product, connection.execute(select(commerce_products).where(
                commerce_products.c.id == product_id,
                commerce_products.c.workspace_id == workspace_id,
            )).first())

    def list_categories(self) -> list[ProductCategory]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(commerce_categories)
                .where(commerce_categories.c.status == "active")
                .order_by(commerce_categories.c.sort_order, commerce_categories.c.name)
            )
            return [self._row(ProductCategory, row) for row in rows]

    def list_product_media(self, product_id: str, workspace_id: str) -> list[ProductMedia]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(commerce_product_media)
                .where(
                    commerce_product_media.c.product_id == product_id,
                    commerce_product_media.c.workspace_id == workspace_id,
                )
                .order_by(commerce_product_media.c.sort_order, commerce_product_media.c.created_at)
            )
            return [self._row(ProductMedia, row) for row in rows]

    def get_product_media(self, media_id: str, workspace_id: str) -> ProductMedia | None:
        with self.engine.connect() as connection:
            return self._row(ProductMedia, connection.execute(
                select(commerce_product_media).where(
                    commerce_product_media.c.id == media_id,
                    commerce_product_media.c.workspace_id == workspace_id,
                )
            ).first())

    def add_product_media(
        self, media: ProductMedia, product: Product, expected_version: int
    ) -> None:
        with self.engine.begin() as connection:
            product_result = connection.execute(update(commerce_products).where(
                commerce_products.c.id == product.id,
                commerce_products.c.workspace_id == product.workspace_id,
                commerce_products.c.version == expected_version,
            ).values(**asdict(product)))
            if product_result.rowcount != 1:
                raise CommerceConflictError("商品版本已变化，请刷新后重试")
            connection.execute(commerce_product_media.insert().values(**asdict(media)))
            self._event(
                connection, actor=product.seller_user_id,
                workspace_id=product.workspace_id, event_type="product.media_added",
                entity_type="product_media", entity_id=media.id,
                key=f"product-media:{media.id}:created",
            )

    def remove_product_media(
        self, media_id: str, product: Product, expected_version: int
    ) -> ProductMedia:
        with self.engine.begin() as connection:
            row = connection.execute(select(commerce_product_media).where(
                commerce_product_media.c.id == media_id,
                commerce_product_media.c.product_id == product.id,
                commerce_product_media.c.workspace_id == product.workspace_id,
            )).first()
            media = self._row(ProductMedia, row)
            if not media:
                raise CommerceNotFoundError("商品图片不存在")
            product_result = connection.execute(update(commerce_products).where(
                commerce_products.c.id == product.id,
                commerce_products.c.workspace_id == product.workspace_id,
                commerce_products.c.version == expected_version,
            ).values(**asdict(product)))
            if product_result.rowcount != 1:
                raise CommerceConflictError("商品版本已变化，请刷新后重试")
            connection.execute(delete(commerce_product_media).where(
                commerce_product_media.c.id == media_id
            ))
            self._event(
                connection, actor=product.seller_user_id,
                workspace_id=product.workspace_id, event_type="product.media_removed",
                entity_type="product_media", entity_id=media.id,
                key=f"product-media:{media.id}:removed",
            )
            return media

    def list_product_variants(self, product_id: str, workspace_id: str) -> list[ProductVariant]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(commerce_product_variants)
                .where(
                    commerce_product_variants.c.product_id == product_id,
                    commerce_product_variants.c.workspace_id == workspace_id,
                )
                .order_by(commerce_product_variants.c.is_default.desc(), commerce_product_variants.c.created_at)
            )
            return [self._row(ProductVariant, row) for row in rows]

    def list_product_heritage_links(
        self, product_id: str, workspace_id: str
    ) -> list[ProductHeritageLink]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(commerce_product_heritage_links)
                .where(
                    commerce_product_heritage_links.c.product_id == product_id,
                    commerce_product_heritage_links.c.workspace_id == workspace_id,
                )
                .order_by(commerce_product_heritage_links.c.created_at)
            )
            return [self._row(ProductHeritageLink, row) for row in rows]

    def find_advisor_interaction(
        self, user_id: str, workspace_id: str, idempotency_key: str
    ) -> ShoppingAdvisorInteraction | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(commerce_advisor_interactions).where(
                    commerce_advisor_interactions.c.user_id == user_id,
                    commerce_advisor_interactions.c.workspace_id == workspace_id,
                    commerce_advisor_interactions.c.idempotency_key == idempotency_key,
                )
            ).first()
            return self._row(ShoppingAdvisorInteraction, row)

    def list_advisor_interactions(
        self, user_id: str, workspace_id: str, *, limit: int = 20
    ) -> list[ShoppingAdvisorInteraction]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(commerce_advisor_interactions)
                .where(
                    commerce_advisor_interactions.c.user_id == user_id,
                    commerce_advisor_interactions.c.workspace_id == workspace_id,
                )
                .order_by(commerce_advisor_interactions.c.created_at.desc())
                .limit(limit)
            )
            return [self._row(ShoppingAdvisorInteraction, row) for row in rows]

    def count_advisor_interactions_since(
        self, user_id: str, workspace_id: str, created_after: str
    ) -> int:
        with self.engine.connect() as connection:
            return int(connection.scalar(
                select(func.count()).select_from(commerce_advisor_interactions).where(
                    commerce_advisor_interactions.c.user_id == user_id,
                    commerce_advisor_interactions.c.workspace_id == workspace_id,
                    commerce_advisor_interactions.c.created_at >= created_after,
                )
            ) or 0)

    def create_advisor_interaction(self, interaction: ShoppingAdvisorInteraction) -> bool:
        values = asdict(interaction)
        columns = [
            commerce_advisor_interactions.c.user_id,
            commerce_advisor_interactions.c.workspace_id,
            commerce_advisor_interactions.c.idempotency_key,
        ]
        with self.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                inserted_id = connection.scalar(
                    postgresql_insert(commerce_advisor_interactions)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=columns)
                    .returning(commerce_advisor_interactions.c.id)
                )
                return inserted_id is not None
            elif connection.dialect.name == "sqlite":
                result = connection.execute(sqlite_insert(commerce_advisor_interactions).values(**values).on_conflict_do_nothing(index_elements=columns))
            else:
                try:
                    result = connection.execute(commerce_advisor_interactions.insert().values(**values))
                except IntegrityError:
                    return False
            return result.rowcount == 1

    def update_advisor_interaction(
        self, interaction: ShoppingAdvisorInteraction, expected_status: str
    ) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(commerce_advisor_interactions)
                .where(
                    commerce_advisor_interactions.c.id == interaction.id,
                    commerce_advisor_interactions.c.status == expected_status,
                )
                .values(**asdict(interaction))
            )
            return result.rowcount == 1

    def search_catalog(
        self,
        workspace_id: str,
        *,
        query: str = "",
        category_slug: str = "",
        craft_type: str = "",
        origin_region: str = "",
        season_tag: str = "",
        sort: str = "newest",
        offset: int = 0,
        limit: int = 24,
    ) -> tuple[list[Product], int]:
        base = select(commerce_products).where(
            commerce_products.c.workspace_id == workspace_id,
            commerce_products.c.status == "listed",
        )
        count_query = select(func.count()).select_from(commerce_products).where(
            commerce_products.c.workspace_id == workspace_id,
            commerce_products.c.status == "listed",
        )
        filters: list[Any] = []
        if query:
            pattern = f"%{query.casefold()}%"
            filters.append(or_(
                func.lower(commerce_products.c.title).like(pattern),
                func.lower(commerce_products.c.summary).like(pattern),
                func.lower(commerce_products.c.craft_type).like(pattern),
                func.lower(commerce_products.c.origin_region).like(pattern),
            ))
        if category_slug:
            category_id = select(commerce_categories.c.id).where(
                commerce_categories.c.slug == category_slug,
                commerce_categories.c.status == "active",
            ).scalar_subquery()
            filters.append(commerce_products.c.category_id == category_id)
        if craft_type:
            filters.append(func.lower(commerce_products.c.craft_type) == craft_type.casefold())
        if origin_region:
            filters.append(func.lower(commerce_products.c.origin_region) == origin_region.casefold())
        if season_tag:
            filters.append(func.lower(commerce_products.c.season_tag) == season_tag.casefold())
        if filters:
            base = base.where(*filters)
            count_query = count_query.where(*filters)
        order = {
            "newest": commerce_products.c.updated_at.desc(),
            "price_asc": commerce_products.c.price_cents.asc(),
            "price_desc": commerce_products.c.price_cents.desc(),
        }[sort]
        with self.engine.connect() as connection:
            total = int(connection.scalar(count_query) or 0)
            rows = connection.execute(base.order_by(order, commerce_products.c.id).offset(offset).limit(limit))
            return [self._row(Product, row) for row in rows], total

    def find_product_by_creation_key(self, user_id: str, workspace_id: str, creation_key: str) -> Product | None:
        with self.engine.connect() as connection:
            return self._row(Product, connection.execute(select(commerce_products).where(
                commerce_products.c.seller_user_id == user_id,
                commerce_products.c.workspace_id == workspace_id,
                commerce_products.c.creation_key == creation_key,
            )).first())

    def list_products(self, workspace_id: str, *, seller_user_id: str = "", review_queue: bool = False) -> list[Product]:
        query = select(commerce_products).where(commerce_products.c.workspace_id == workspace_id)
        if seller_user_id:
            query = query.where(commerce_products.c.seller_user_id == seller_user_id)
        elif review_queue:
            query = query.where(commerce_products.c.status == "submitted")
        else:
            query = query.where(commerce_products.c.status == "listed")
        query = query.order_by(commerce_products.c.updated_at.desc())
        with self.engine.connect() as connection:
            return [self._row(Product, row) for row in connection.execute(query)]

    def create_product(self, product: Product) -> bool:
        with self.engine.begin() as connection:
            values = asdict(product)
            columns = [
                commerce_products.c.seller_user_id,
                commerce_products.c.workspace_id,
                commerce_products.c.creation_key,
            ]
            if connection.dialect.name == "postgresql":
                result = connection.execute(postgresql_insert(commerce_products).values(**values).on_conflict_do_nothing(index_elements=columns))
            elif connection.dialect.name == "sqlite":
                result = connection.execute(sqlite_insert(commerce_products).values(**values).on_conflict_do_nothing(index_elements=columns))
            else:
                existing = connection.scalar(select(commerce_products.c.id).where(
                    commerce_products.c.seller_user_id == product.seller_user_id,
                    commerce_products.c.workspace_id == product.workspace_id,
                    commerce_products.c.creation_key == product.creation_key,
                ))
                if existing:
                    return False
                result = connection.execute(commerce_products.insert().values(**values))
            if result.rowcount != 1:
                return False
            variant = ProductVariant(
                id=f"variant_{product.id}",
                product_id=product.id,
                workspace_id=product.workspace_id,
                sku=f"DEFAULT-{product.id[-12:].upper()}",
                name="默认规格",
                attributes_json="{}",
                price_cents=product.price_cents,
                currency=product.currency,
                status="active",
                is_default=1,
                version=1,
                created_at=product.created_at,
                updated_at=product.updated_at,
            )
            connection.execute(commerce_product_variants.insert().values(**asdict(variant)))
            self._event(connection, actor=product.seller_user_id, workspace_id=product.workspace_id, event_type="product.created", entity_type="product", entity_id=product.id, key=f"product-create:{product.id}")
            return True

    def transition_product(self, product: Product, expected_version: int) -> None:
        with self.engine.begin() as connection:
            result = connection.execute(update(commerce_products).where(
                commerce_products.c.id == product.id,
                commerce_products.c.workspace_id == product.workspace_id,
                commerce_products.c.version == expected_version,
            ).values(**asdict(product)))
            if result.rowcount != 1:
                raise CommerceConflictError("商品版本已变化，请刷新后重试")
            self._event(connection, actor=product.reviewed_by or product.seller_user_id, workspace_id=product.workspace_id, event_type=f"product.{product.status}", entity_type="product", entity_id=product.id, key=f"product:{product.id}:v{product.version}")

    def update_product(self, product: Product, expected_version: int) -> None:
        with self.engine.begin() as connection:
            result = connection.execute(update(commerce_products).where(
                commerce_products.c.id == product.id,
                commerce_products.c.workspace_id == product.workspace_id,
                commerce_products.c.version == expected_version,
            ).values(**asdict(product)))
            if result.rowcount != 1:
                raise CommerceConflictError("商品版本已变化，请刷新后重试")
            connection.execute(update(commerce_product_variants).where(
                commerce_product_variants.c.product_id == product.id,
                commerce_product_variants.c.workspace_id == product.workspace_id,
                commerce_product_variants.c.is_default == 1,
            ).values(price_cents=product.price_cents, updated_at=product.updated_at))
            self._event(
                connection, actor=product.seller_user_id,
                workspace_id=product.workspace_id, event_type="product.updated",
                entity_type="product", entity_id=product.id,
                key=f"product:{product.id}:v{product.version}:updated",
            )

    def get_inventory(self, product_id: str, workspace_id: str) -> Inventory | None:
        with self.engine.connect() as connection:
            return self._row(Inventory, connection.execute(select(commerce_inventory).where(
                commerce_inventory.c.product_id == product_id,
                commerce_inventory.c.workspace_id == workspace_id,
            )).first())

    def set_inventory(self, inventory: Inventory, expected_version: int, product: Product) -> None:
        with self.engine.begin() as connection:
            if expected_version == 0:
                try:
                    connection.execute(commerce_inventory.insert().values(**asdict(inventory)))
                except IntegrityError as exc:
                    raise CommerceConflictError("库存版本已变化，请刷新后重试") from exc
            else:
                result = connection.execute(update(commerce_inventory).where(
                    commerce_inventory.c.product_id == inventory.product_id,
                    commerce_inventory.c.workspace_id == inventory.workspace_id,
                    commerce_inventory.c.version == expected_version,
                ).values(**asdict(inventory)))
                if result.rowcount != 1:
                    raise CommerceConflictError("库存版本已变化，请刷新后重试")
            product_result = connection.execute(update(commerce_products).where(
                commerce_products.c.id == product.id,
                commerce_products.c.workspace_id == product.workspace_id,
                commerce_products.c.version == product.version - 1,
            ).values(**asdict(product)))
            if product_result.rowcount != 1:
                raise CommerceConflictError("商品版本已变化，请刷新后重试")
            self._event(connection, actor=product.seller_user_id, workspace_id=product.workspace_id, event_type="inventory.updated", entity_type="product", entity_id=product.id, key=f"inventory:{product.id}:v{inventory.version}")

    def list_cart_items(self, user_id: str, workspace_id: str) -> list[CartItem]:
        with self.engine.connect() as connection:
            return [self._row(CartItem, row) for row in connection.execute(select(commerce_cart_items).where(
                commerce_cart_items.c.buyer_user_id == user_id,
                commerce_cart_items.c.workspace_id == workspace_id,
            ).order_by(commerce_cart_items.c.updated_at.desc()))]

    def set_cart_item(self, item: CartItem, expected_version: int) -> None:
        with self.engine.begin() as connection:
            if expected_version == 0:
                try:
                    connection.execute(commerce_cart_items.insert().values(**asdict(item)))
                except IntegrityError as exc:
                    raise CommerceConflictError("购物车版本已变化，请刷新后重试") from exc
            else:
                result = connection.execute(update(commerce_cart_items).where(
                    commerce_cart_items.c.buyer_user_id == item.buyer_user_id,
                    commerce_cart_items.c.workspace_id == item.workspace_id,
                    commerce_cart_items.c.product_id == item.product_id,
                    commerce_cart_items.c.version == expected_version,
                ).values(**asdict(item)))
                if result.rowcount != 1:
                    raise CommerceConflictError("购物车版本已变化，请刷新后重试")

    def remove_cart_item(self, user_id: str, workspace_id: str, product_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(commerce_cart_items).where(
                commerce_cart_items.c.buyer_user_id == user_id,
                commerce_cart_items.c.workspace_id == workspace_id,
                commerce_cart_items.c.product_id == product_id,
            ))

    def checkout(self, user_id: str, workspace_id: str, idempotency_key: str) -> tuple[Order, bool]:
        with self.engine.begin() as connection:
            existing = connection.execute(select(commerce_orders).where(
                commerce_orders.c.buyer_user_id == user_id,
                commerce_orders.c.workspace_id == workspace_id,
                commerce_orders.c.checkout_key == idempotency_key,
            )).first()
            if existing:
                return self._row(Order, existing), False
            cart = connection.execute(select(commerce_cart_items).where(
                commerce_cart_items.c.buyer_user_id == user_id,
                commerce_cart_items.c.workspace_id == workspace_id,
            ).order_by(commerce_cart_items.c.created_at)).all()
            if not cart:
                replay = connection.execute(select(commerce_orders).where(
                    commerce_orders.c.buyer_user_id == user_id,
                    commerce_orders.c.workspace_id == workspace_id,
                    commerce_orders.c.checkout_key == idempotency_key,
                )).first()
                if replay:
                    return self._row(Order, replay), False
                raise CommerceConflictError("购物车为空，不能结算")
            products: list[Any] = []
            inventories: list[Any] = []
            for line in cart:
                product = connection.execute(select(commerce_products).where(
                    commerce_products.c.id == line.product_id,
                    commerce_products.c.workspace_id == workspace_id,
                )).first()
                inventory = connection.execute(select(commerce_inventory).where(
                    commerce_inventory.c.product_id == line.product_id,
                    commerce_inventory.c.workspace_id == workspace_id,
                )).first()
                if not product or product.status != "listed" or not inventory:
                    raise CommerceConflictError("购物车中存在已下架商品")
                if inventory.available_qty < line.quantity:
                    raise CommerceConflictError(f"{product.title} 库存不足")
                products.append(product)
                inventories.append(inventory)
            if len({item.store_id for item in products}) != 1:
                raise CommerceConflictError("交易沙盒当前仅支持单店结算")
            now = _now()
            total = sum(product.price_cents * line.quantity for product, line in zip(products, cart, strict=True))
            order = Order(f"order_{uuid4().hex}", user_id, workspace_id, products[0].store_id, products[0].seller_user_id, "awaiting_sandbox_payment", total, "CNY", idempotency_key, 1, now, now)
            try:
                with connection.begin_nested():
                    connection.execute(commerce_orders.insert().values(**asdict(order)))
            except IntegrityError as exc:
                existing = connection.execute(select(commerce_orders).where(
                    commerce_orders.c.buyer_user_id == user_id,
                    commerce_orders.c.workspace_id == workspace_id,
                    commerce_orders.c.checkout_key == idempotency_key,
                )).first()
                if existing:
                    return self._row(Order, existing), False
                raise CommerceConflictError("结算请求发生并发冲突，请刷新后重试") from exc
            for product, line, inventory in zip(products, cart, inventories, strict=True):
                result = connection.execute(update(commerce_inventory).where(
                    commerce_inventory.c.product_id == product.id,
                    commerce_inventory.c.workspace_id == workspace_id,
                    commerce_inventory.c.version == inventory.version,
                    commerce_inventory.c.available_qty >= line.quantity,
                ).values(
                    available_qty=inventory.available_qty - line.quantity,
                    sold_qty=inventory.sold_qty + line.quantity,
                    version=inventory.version + 1,
                    updated_at=now,
                ))
                if result.rowcount != 1:
                    raise CommerceConflictError(f"{product.title} 库存被其他订单占用，请重试")
                item = OrderItem(f"oi_{uuid4().hex}", order.id, workspace_id, product.id, product.title, product.price_cents, line.quantity)
                connection.execute(commerce_order_items.insert().values(**asdict(item)))
            connection.execute(delete(commerce_cart_items).where(
                commerce_cart_items.c.buyer_user_id == user_id,
                commerce_cart_items.c.workspace_id == workspace_id,
            ))
            self._event(connection, actor=user_id, workspace_id=workspace_id, event_type="order.created", entity_type="order", entity_id=order.id, key=f"checkout:{idempotency_key}")
            return order, True

    def get_order(self, order_id: str, workspace_id: str) -> Order | None:
        with self.engine.connect() as connection:
            return self._row(Order, connection.execute(select(commerce_orders).where(
                commerce_orders.c.id == order_id,
                commerce_orders.c.workspace_id == workspace_id,
            )).first())

    def list_orders(self, workspace_id: str, *, buyer_user_id: str = "", seller_user_id: str = "") -> list[Order]:
        query = select(commerce_orders).where(commerce_orders.c.workspace_id == workspace_id)
        if buyer_user_id:
            query = query.where(commerce_orders.c.buyer_user_id == buyer_user_id)
        if seller_user_id:
            query = query.where(commerce_orders.c.seller_user_id == seller_user_id)
        with self.engine.connect() as connection:
            return [self._row(Order, row) for row in connection.execute(query.order_by(commerce_orders.c.created_at.desc()))]

    def list_order_items(self, order_id: str, workspace_id: str) -> list[OrderItem]:
        with self.engine.connect() as connection:
            return [self._row(OrderItem, row) for row in connection.execute(select(commerce_order_items).where(
                commerce_order_items.c.order_id == order_id,
                commerce_order_items.c.workspace_id == workspace_id,
            ))]

    def cancel_order(self, order_id: str, user_id: str, workspace_id: str, expected_version: int) -> Order:
        with self.engine.begin() as connection:
            row = connection.execute(select(commerce_orders).where(
                commerce_orders.c.id == order_id,
                commerce_orders.c.workspace_id == workspace_id,
            )).first()
            if not row:
                raise CommerceNotFoundError("订单不存在")
            order = self._row(Order, row)
            if order.buyer_user_id != user_id:
                raise CommercePermissionError("不能取消其他账户的订单")
            if order.status != "awaiting_sandbox_payment":
                raise CommerceConflictError("只有待沙盒支付订单可以取消")
            if order.version != expected_version:
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            now = _now()
            updated = replace(order, status="cancelled", version=order.version + 1, updated_at=now)
            result = connection.execute(update(commerce_orders).where(
                commerce_orders.c.id == order.id,
                commerce_orders.c.version == expected_version,
            ).values(**asdict(updated)))
            if result.rowcount != 1:
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            for item in connection.execute(select(commerce_order_items).where(commerce_order_items.c.order_id == order.id)):
                inventory_result = connection.execute(update(commerce_inventory).where(
                    commerce_inventory.c.product_id == item.product_id,
                    commerce_inventory.c.workspace_id == workspace_id,
                    commerce_inventory.c.sold_qty >= item.quantity,
                ).values(
                    available_qty=commerce_inventory.c.available_qty + item.quantity,
                    sold_qty=commerce_inventory.c.sold_qty - item.quantity,
                    version=commerce_inventory.c.version + 1,
                    updated_at=now,
                ))
                if inventory_result.rowcount != 1:
                    raise CommerceConflictError("订单库存状态异常，取消操作已回滚")
            self._event(connection, actor=user_id, workspace_id=workspace_id, event_type="order.cancelled", entity_type="order", entity_id=order.id, key=f"order-cancel:{order.id}:v{updated.version}")
            return updated

    def authorize_sandbox_payment(self, order_id: str, user_id: str, workspace_id: str, idempotency_key: str, expected_version: int) -> tuple[Order, Payment, bool]:
        with self.engine.begin() as connection:
            existing = connection.execute(select(commerce_payments).where(
                commerce_payments.c.buyer_user_id == user_id,
                commerce_payments.c.workspace_id == workspace_id,
                commerce_payments.c.idempotency_key == idempotency_key,
            )).first()
            if existing:
                payment = self._row(Payment, existing)
                if payment.order_id != order_id:
                    raise CommerceConflictError("幂等键已用于其他沙盒支付")
                order_row = connection.execute(select(commerce_orders).where(
                    commerce_orders.c.id == order_id,
                    commerce_orders.c.workspace_id == workspace_id,
                )).first()
                return self._row(Order, order_row), payment, False
            row = connection.execute(select(commerce_orders).where(
                commerce_orders.c.id == order_id,
                commerce_orders.c.workspace_id == workspace_id,
            )).first()
            if not row:
                raise CommerceNotFoundError("订单不存在")
            order = self._row(Order, row)
            if order.buyer_user_id != user_id:
                raise CommercePermissionError("不能支付其他账户的订单")
            if order.status != "awaiting_sandbox_payment":
                replay = connection.execute(select(commerce_payments).where(
                    commerce_payments.c.buyer_user_id == user_id,
                    commerce_payments.c.workspace_id == workspace_id,
                    commerce_payments.c.idempotency_key == idempotency_key,
                )).first()
                if replay:
                    payment = self._row(Payment, replay)
                    if payment.order_id != order_id:
                        raise CommerceConflictError("幂等键已用于其他沙盒支付")
                    return order, payment, False
                raise CommerceConflictError("订单当前不能执行沙盒支付")
            if order.version != expected_version:
                replay = connection.execute(select(commerce_payments).where(
                    commerce_payments.c.buyer_user_id == user_id,
                    commerce_payments.c.workspace_id == workspace_id,
                    commerce_payments.c.idempotency_key == idempotency_key,
                )).first()
                if replay:
                    payment = self._row(Payment, replay)
                    if payment.order_id != order_id:
                        raise CommerceConflictError("幂等键已用于其他沙盒支付")
                    return order, payment, False
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            now = _now()
            paid_order = replace(order, status="paid", version=order.version + 1, updated_at=now)
            result = connection.execute(update(commerce_orders).where(
                commerce_orders.c.id == order.id,
                commerce_orders.c.version == expected_version,
            ).values(**asdict(paid_order)))
            if result.rowcount != 1:
                replay = connection.execute(select(commerce_payments).where(
                    commerce_payments.c.buyer_user_id == user_id,
                    commerce_payments.c.workspace_id == workspace_id,
                    commerce_payments.c.idempotency_key == idempotency_key,
                )).first()
                if replay:
                    payment = self._row(Payment, replay)
                    if payment.order_id != order_id:
                        raise CommerceConflictError("幂等键已用于其他沙盒支付")
                    current_order = connection.execute(select(commerce_orders).where(
                        commerce_orders.c.id == order_id,
                        commerce_orders.c.workspace_id == workspace_id,
                    )).first()
                    return self._row(Order, current_order), payment, False
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            payment = Payment(f"pay_{uuid4().hex}", order.id, user_id, workspace_id, "internal_sandbox", "authorized", order.total_cents, order.currency, idempotency_key, now)
            connection.execute(commerce_payments.insert().values(**asdict(payment)))
            self._event(connection, actor=user_id, workspace_id=workspace_id, event_type="payment.sandbox_authorized", entity_type="order", entity_id=order.id, key=f"payment:{idempotency_key}", detail="No real funds moved; no payment credentials collected.")
            return paid_order, payment, True

    def get_payment(self, order_id: str, workspace_id: str) -> Payment | None:
        with self.engine.connect() as connection:
            return self._row(Payment, connection.execute(select(commerce_payments).where(
                commerce_payments.c.order_id == order_id,
                commerce_payments.c.workspace_id == workspace_id,
            )).first())

    def ship_order(self, order_id: str, seller_user_id: str, workspace_id: str, tracking_note: str, expected_version: int) -> tuple[Order, Fulfillment]:
        with self.engine.begin() as connection:
            row = connection.execute(select(commerce_orders).where(commerce_orders.c.id == order_id, commerce_orders.c.workspace_id == workspace_id)).first()
            if not row:
                raise CommerceNotFoundError("订单不存在")
            order = self._row(Order, row)
            if order.seller_user_id != seller_user_id:
                raise CommercePermissionError("不能履约其他卖家的订单")
            if order.status != "paid":
                raise CommerceConflictError("只有已完成沙盒支付的订单可以发货")
            if order.version != expected_version:
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            now = _now()
            shipped = replace(order, status="shipped", version=order.version + 1, updated_at=now)
            result = connection.execute(update(commerce_orders).where(
                commerce_orders.c.id == order.id,
                commerce_orders.c.workspace_id == workspace_id,
                commerce_orders.c.version == expected_version,
            ).values(**asdict(shipped)))
            if result.rowcount != 1:
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            existing_fulfillment = connection.execute(select(commerce_fulfillments).where(
                commerce_fulfillments.c.order_id == order.id,
                commerce_fulfillments.c.workspace_id == workspace_id,
            )).first()
            if existing_fulfillment:
                raise CommerceConflictError("订单已经存在履约记录")
            fulfillment = Fulfillment(f"ful_{uuid4().hex}", order.id, workspace_id, seller_user_id, "shipped", tracking_note, 1, now, now)
            connection.execute(commerce_fulfillments.insert().values(**asdict(fulfillment)))
            self._event(connection, actor=seller_user_id, workspace_id=workspace_id, event_type="fulfillment.shipped", entity_type="order", entity_id=order.id, key=f"ship:{order.id}:v{shipped.version}")
            return shipped, fulfillment

    def confirm_delivery(self, order_id: str, buyer_user_id: str, workspace_id: str, expected_version: int) -> tuple[Order, Fulfillment]:
        with self.engine.begin() as connection:
            row = connection.execute(select(commerce_orders).where(commerce_orders.c.id == order_id, commerce_orders.c.workspace_id == workspace_id)).first()
            if not row:
                raise CommerceNotFoundError("订单不存在")
            order = self._row(Order, row)
            if order.buyer_user_id != buyer_user_id:
                raise CommercePermissionError("不能确认其他账户的订单")
            if order.status != "shipped" or order.version != expected_version:
                raise CommerceConflictError("订单状态或版本已变化，请刷新后重试")
            fulfillment_row = connection.execute(select(commerce_fulfillments).where(commerce_fulfillments.c.order_id == order_id, commerce_fulfillments.c.workspace_id == workspace_id)).first()
            if not fulfillment_row:
                raise CommerceConflictError("订单缺少履约记录")
            fulfillment = self._row(Fulfillment, fulfillment_row)
            if fulfillment.status != "shipped":
                raise CommerceConflictError("履约状态已变化，请刷新后重试")
            now = _now()
            completed = replace(order, status="completed", version=order.version + 1, updated_at=now)
            delivered = replace(fulfillment, status="delivered", version=fulfillment.version + 1, updated_at=now)
            order_result = connection.execute(update(commerce_orders).where(
                commerce_orders.c.id == order.id,
                commerce_orders.c.workspace_id == workspace_id,
                commerce_orders.c.version == expected_version,
            ).values(**asdict(completed)))
            if order_result.rowcount != 1:
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            fulfillment_result = connection.execute(update(commerce_fulfillments).where(
                commerce_fulfillments.c.id == fulfillment.id,
                commerce_fulfillments.c.workspace_id == workspace_id,
                commerce_fulfillments.c.version == fulfillment.version,
                commerce_fulfillments.c.status == "shipped",
            ).values(**asdict(delivered)))
            if fulfillment_result.rowcount != 1:
                raise CommerceConflictError("履约状态已变化，请刷新后重试")
            self._event(connection, actor=buyer_user_id, workspace_id=workspace_id, event_type="fulfillment.delivered", entity_type="order", entity_id=order.id, key=f"deliver:{order.id}:v{completed.version}")
            return completed, delivered

    def get_fulfillment(self, order_id: str, workspace_id: str) -> Fulfillment | None:
        with self.engine.connect() as connection:
            return self._row(Fulfillment, connection.execute(select(commerce_fulfillments).where(
                commerce_fulfillments.c.order_id == order_id,
                commerce_fulfillments.c.workspace_id == workspace_id,
            )).first())

    def request_after_sale(self, after_sale: AfterSale, expected_order_version: int) -> AfterSale:
        with self.engine.begin() as connection:
            row = connection.execute(select(commerce_orders).where(commerce_orders.c.id == after_sale.order_id, commerce_orders.c.workspace_id == after_sale.workspace_id)).first()
            if not row:
                raise CommerceNotFoundError("订单不存在")
            order = self._row(Order, row)
            if order.buyer_user_id != after_sale.buyer_user_id:
                raise CommercePermissionError("不能为其他账户的订单发起售后")
            if order.status not in {"paid", "shipped", "completed"} or order.version != expected_order_version:
                raise CommerceConflictError("订单当前不能发起售后，或版本已变化")
            order_result = connection.execute(update(commerce_orders).where(
                commerce_orders.c.id == order.id,
                commerce_orders.c.workspace_id == after_sale.workspace_id,
                commerce_orders.c.version == expected_order_version,
            ).values(
                status="after_sales",
                version=order.version + 1,
                updated_at=after_sale.updated_at,
            ))
            if order_result.rowcount != 1:
                raise CommerceConflictError("订单版本已变化，请刷新后重试")
            try:
                with connection.begin_nested():
                    connection.execute(commerce_after_sales.insert().values(**asdict(after_sale)))
            except IntegrityError as exc:
                raise CommerceConflictError("该订单已经存在售后申请") from exc
            self._event(connection, actor=after_sale.buyer_user_id, workspace_id=after_sale.workspace_id, event_type="after_sale.requested", entity_type="order", entity_id=order.id, key=f"after-sale:{order.id}")
            return after_sale

    def decide_after_sale(self, after_sale: AfterSale, expected_version: int) -> AfterSale:
        with self.engine.begin() as connection:
            result = connection.execute(update(commerce_after_sales).where(
                commerce_after_sales.c.id == after_sale.id,
                commerce_after_sales.c.workspace_id == after_sale.workspace_id,
                commerce_after_sales.c.version == expected_version,
            ).values(**asdict(after_sale)))
            if result.rowcount != 1:
                raise CommerceConflictError("售后版本已变化，请刷新后重试")
            self._event(connection, actor=after_sale.seller_user_id, workspace_id=after_sale.workspace_id, event_type=f"after_sale.{after_sale.status}", entity_type="after_sale", entity_id=after_sale.id, key=f"after-sale:{after_sale.id}:v{after_sale.version}")
            return after_sale

    def list_after_sales(self, workspace_id: str, *, buyer_user_id: str = "", seller_user_id: str = "") -> list[AfterSale]:
        query = select(commerce_after_sales).where(commerce_after_sales.c.workspace_id == workspace_id)
        if buyer_user_id:
            query = query.where(commerce_after_sales.c.buyer_user_id == buyer_user_id)
        if seller_user_id:
            query = query.where(commerce_after_sales.c.seller_user_id == seller_user_id)
        with self.engine.connect() as connection:
            return [self._row(AfterSale, row) for row in connection.execute(query.order_by(commerce_after_sales.c.updated_at.desc()))]

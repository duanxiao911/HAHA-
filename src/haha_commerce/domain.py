"""Framework-independent contracts for the Gate D commerce sandbox."""

from __future__ import annotations

from dataclasses import dataclass


class CommercePermissionError(RuntimeError):
    """The current account lacks the required business role or ownership."""


class CommerceNotFoundError(RuntimeError):
    """A commerce resource is absent from the current workspace."""


class CommerceConflictError(RuntimeError):
    """A state, version, inventory, or idempotency invariant was violated."""


class CommerceAdvisorUnavailableError(RuntimeError):
    """The real shopping advisor is unavailable or returned an unsafe result."""


class CommerceAdvisorRateLimitError(RuntimeError):
    """The account exhausted its rolling shopping-advisor allowance."""


@dataclass(frozen=True, slots=True)
class Store:
    id: str
    workspace_id: str
    owner_user_id: str
    name: str
    status: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Product:
    id: str
    workspace_id: str
    store_id: str
    seller_user_id: str
    title: str
    summary: str
    price_cents: int
    currency: str
    source_note: str
    provenance: str
    creation_key: str
    status: str
    version: int
    reviewer_note: str
    reviewed_by: str
    created_at: str
    updated_at: str
    category_id: str = "category-other"
    craft_type: str = ""
    origin_region: str = ""
    season_tag: str = ""


@dataclass(frozen=True, slots=True)
class ProductCategory:
    id: str
    slug: str
    name: str
    description: str
    sort_order: int
    status: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProductMedia:
    id: str
    product_id: str
    workspace_id: str
    media_type: str
    storage_key: str
    alt_text: str
    source_note: str
    rights_status: str
    sort_order: int
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProductVariant:
    id: str
    product_id: str
    workspace_id: str
    sku: str
    name: str
    attributes_json: str
    price_cents: int
    currency: str
    status: str
    is_default: int
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProductHeritageLink:
    id: str
    product_id: str
    workspace_id: str
    heritage_ref: str
    relation_type: str
    claim_status: str
    source_note: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ShoppingAdvisorInteraction:
    id: str
    user_id: str
    workspace_id: str
    question: str
    answer: str
    recommendations_json: str
    suggestions_json: str
    status: str
    mode: str
    model: str
    provider: str
    request_id: str
    input_tokens: int
    output_tokens: int
    error_code: str
    idempotency_key: str
    request_hash: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Inventory:
    product_id: str
    workspace_id: str
    available_qty: int
    sold_qty: int
    version: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class CartItem:
    id: str
    buyer_user_id: str
    workspace_id: str
    product_id: str
    quantity: int
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    buyer_user_id: str
    workspace_id: str
    store_id: str
    seller_user_id: str
    status: str
    total_cents: int
    currency: str
    checkout_key: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class OrderItem:
    id: str
    order_id: str
    workspace_id: str
    product_id: str
    title_snapshot: str
    unit_price_cents: int
    quantity: int


@dataclass(frozen=True, slots=True)
class Payment:
    id: str
    order_id: str
    buyer_user_id: str
    workspace_id: str
    provider: str
    status: str
    amount_cents: int
    currency: str
    idempotency_key: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Fulfillment:
    id: str
    order_id: str
    workspace_id: str
    seller_user_id: str
    status: str
    tracking_note: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AfterSale:
    id: str
    order_id: str
    workspace_id: str
    buyer_user_id: str
    seller_user_id: str
    reason: str
    status: str
    decision_note: str
    version: int
    created_at: str
    updated_at: str

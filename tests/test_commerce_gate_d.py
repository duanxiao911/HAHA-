from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from haha_api.main import create_app
from haha_commerce.sqlalchemy_repository import SQLAlchemyCommerceRepository
from haha_core.repository import SQLiteCreatorRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _grant(repository: SQLiteCreatorRepository, user_id: str, workspace_id: str, role: str) -> None:
    repository.ensure_identity(user_id, workspace_id, role="owner")
    IdentityService(repository).bootstrap(user_id, workspace_id)
    repository.save_role_grant(RoleGrant(
        id=f"grant_{uuid4().hex}", user_id=user_id, workspace_id=workspace_id,
        role=role, status="active", scope_json=json.dumps({"workspace_id": workspace_id}),
        granted_by="test-owner", created_at=_now(), revoked_at="",
    ))


def _stack() -> tuple[TestClient, SQLiteCreatorRepository]:
    identity = SQLiteCreatorRepository(":memory:")
    commerce = SQLAlchemyCommerceRepository.for_sqlite_path(":memory:")
    return TestClient(create_app(identity, commerce_repository=commerce)), identity


def _headers(user_id: str) -> dict[str, str]:
    return {"X-User-ID": user_id, "X-Workspace-ID": "commerce-ws"}


def _approved_listing(client: TestClient, identity: SQLiteCreatorRepository) -> tuple[str, dict[str, str], dict[str, str]]:
    seller = _headers("seller-a")
    reviewer = _headers("reviewer-b")
    _grant(identity, "seller-a", "commerce-ws", "seller")
    _grant(identity, "reviewer-b", "commerce-ws", "reviewer")
    assert client.post("/api/commerce/stores", headers=seller, json={"name": "内部测试店铺"}).status_code == 200
    created = client.post("/api/commerce/products", headers={
        **seller, "Idempotency-Key": "product-create-approved-listing-0001"
    }, json={
        "title": "来源待核验的内部测试作品",
        "summary": "仅用于验证交易状态机，不代表正式非遗事实或商品认证。",
        "price_cents": 6800,
        "source_note": "卖家自述；授权与来源仍需人工核验。",
    })
    assert created.status_code == 201
    product = created.json()["seller_products"][0]
    submitted = client.post(
        f"/api/commerce/products/{product['id']}/submit", headers=seller,
        json={"expected_version": product["version"]},
    )
    assert submitted.status_code == 200
    queued = submitted.json()["seller_products"][0]
    reviewed = client.post(
        f"/api/commerce/products/{product['id']}/review", headers=reviewer,
        json={"decision": "approved", "note": "仅批准进入内部交易沙盒。", "expected_version": queued["version"]},
    )
    assert reviewed.status_code == 200
    listed = client.put(
        f"/api/commerce/products/{product['id']}/inventory", headers=seller,
        json={"quantity": 2, "expected_version": 0},
    )
    assert listed.status_code == 200
    return product["id"], seller, reviewer


def test_product_creation_is_idempotent_and_rejects_payload_reuse() -> None:
    client, identity = _stack()
    seller = _headers("seller-idempotent")
    _grant(identity, "seller-idempotent", "commerce-ws", "seller")
    assert client.post(
        "/api/commerce/stores", headers=seller, json={"name": "幂等测试店铺"}
    ).status_code == 200
    headers = {**seller, "Idempotency-Key": "product-create-idempotent-0001"}
    payload = {
        "title": "幂等商品草稿",
        "summary": "验证重复提交不会生成重复草稿。",
        "price_cents": 1200,
        "source_note": "内部测试，来源尚未核验。",
    }
    first = client.post("/api/commerce/products", headers=headers, json=payload)
    replay = client.post("/api/commerce/products", headers=headers, json=payload)
    conflict = client.post(
        "/api/commerce/products",
        headers=headers,
        json={**payload, "title": "不同商品草稿"},
    )
    assert first.status_code == 201
    assert replay.status_code == 201
    assert len(replay.json()["seller_products"]) == 1
    assert replay.json()["seller_products"][0]["id"] == first.json()["seller_products"][0]["id"]
    assert conflict.status_code == 409


def test_rejected_seller_cannot_open_store_and_listing_can_be_delisted() -> None:
    client, identity = _stack()
    applicant = _headers("seller-rejected")
    identity.ensure_identity("seller-rejected", "commerce-ws", role="owner")
    service = IdentityService(identity)
    service.bootstrap("seller-rejected", "commerce-ws")
    application = service.apply_for_role(
        "seller-rejected", "commerce-ws", "seller", "申请内部沙盒卖家"
    )
    service.decide_application(
        application.id, "independent-owner", "rejected", "材料不完整"
    )
    denied = client.post(
        "/api/commerce/stores", headers=applicant, json={"name": "不可创建的店铺"}
    )
    assert denied.status_code == 403

    product_id, seller, _reviewer = _approved_listing(client, identity)
    delisted = client.put(
        f"/api/commerce/products/{product_id}/inventory",
        headers=seller,
        json={"quantity": 0, "expected_version": 1},
    )
    assert delisted.status_code == 200
    product = delisted.json()["seller_products"][0]
    assert product["status"] == "delisted"
    assert product["inventory"]["available_qty"] == 0
    assert delisted.json()["catalog"] == []

    relisted = client.put(
        f"/api/commerce/products/{product_id}/inventory",
        headers=seller,
        json={"quantity": 3, "expected_version": 2},
    )
    assert relisted.status_code == 200
    assert relisted.json()["seller_products"][0]["status"] == "listed"
    assert relisted.json()["catalog"][0]["inventory"]["available_qty"] == 3


def test_full_sandbox_transaction_is_authorized_durable_and_auditable() -> None:
    client, identity = _stack()
    product_id, seller, _reviewer = _approved_listing(client, identity)
    buyer = _headers("buyer-c")

    catalog = client.get("/api/commerce", headers=buyer)
    assert catalog.status_code == 200
    assert catalog.json()["sandbox"]["real_money_moved"] is False
    assert catalog.json()["catalog"][0]["provenance"] == "seller_supplied_unverified"

    added = client.put(
        f"/api/commerce/cart/{product_id}", headers=buyer,
        json={"quantity": 1, "expected_version": 0},
    )
    assert added.status_code == 200
    checkout_key = "checkout-test-0001"
    checked = client.post(
        "/api/commerce/checkout", headers={**buyer, "Idempotency-Key": checkout_key},
    )
    assert checked.status_code == 200
    order = checked.json()["buyer_orders"][0]
    assert order["status"] == "awaiting_sandbox_payment"
    assert order["total_cents"] == 6800

    replay = client.post(
        "/api/commerce/checkout", headers={**buyer, "Idempotency-Key": checkout_key},
    )
    assert replay.status_code == 200
    assert len(replay.json()["buyer_orders"]) == 1

    payment_headers = {**buyer, "Idempotency-Key": "sandbox-payment-0001"}
    paid = client.post(
        f"/api/commerce/orders/{order['id']}/sandbox-payment", headers=payment_headers,
        json={"expected_version": order["version"]},
    )
    assert paid.status_code == 200
    paid_order = paid.json()["buyer_orders"][0]
    assert paid_order["payment"]["provider"] == "internal_sandbox"
    assert paid_order["status"] == "paid"
    replayed_payment = client.post(
        f"/api/commerce/orders/{order['id']}/sandbox-payment", headers=payment_headers,
        json={"expected_version": order["version"]},
    )
    assert replayed_payment.status_code == 200

    seller_snapshot = client.get("/api/commerce", headers=seller).json()
    seller_order = seller_snapshot["seller_orders"][0]
    shipped = client.post(
        f"/api/commerce/orders/{order['id']}/ship", headers=seller,
        json={"expected_version": seller_order["version"], "tracking_note": "内部沙盒履约记录，无真实物流单号。"},
    )
    assert shipped.status_code == 200
    shipped_order = shipped.json()["seller_orders"][0]
    delivered = client.post(
        f"/api/commerce/orders/{order['id']}/confirm-delivery", headers=buyer,
        json={"expected_version": shipped_order["version"]},
    )
    assert delivered.status_code == 200
    completed = delivered.json()["buyer_orders"][0]
    assert completed["status"] == "completed"

    after_sale = client.post(
        f"/api/commerce/orders/{order['id']}/after-sales", headers=buyer,
        json={"expected_version": completed["version"], "reason": "验证售后状态流转，不触发真实退款。"},
    )
    assert after_sale.status_code == 200
    request = after_sale.json()["buyer_after_sales"][0]
    decision = client.post(
        f"/api/commerce/after-sales/{request['id']}/decision", headers=seller,
        json={"expected_version": request["version"], "decision": "approved", "note": "内部沙盒售后已受理。"},
    )
    assert decision.status_code == 200
    assert decision.json()["seller_after_sales"][0]["status"] == "approved"

    seller_notices = [
        item
        for item in identity.list_user_notifications("seller-a", "commerce-ws")
        if item.kind == "commerce"
    ]
    buyer_notices = [
        item
        for item in identity.list_user_notifications("buyer-c", "commerce-ws")
        if item.kind == "commerce"
    ]
    assert {item.title for item in seller_notices} == {
        "商品审核结果：通过",
        "收到新的沙盒订单",
        "沙盒订单已支付",
        "沙盒订单已确认收货",
        "收到沙盒售后申请",
    }
    assert {item.title for item in buyer_notices} == {
        "沙盒订单已发货",
        "沙盒售后已受理",
    }
    assert len({item.id for item in seller_notices}) == len(seller_notices)


def test_permissions_versions_inventory_and_order_isolation_fail_closed() -> None:
    client, identity = _stack()
    product_id, seller, _reviewer = _approved_listing(client, identity)
    buyer = _headers("buyer-c")
    outsider = _headers("buyer-d")

    self_review = client.post(
        f"/api/commerce/products/{product_id}/review", headers=seller,
        json={"decision": "approved", "note": "不能自审", "expected_version": 2},
    )
    assert self_review.status_code == 403
    stale_stock = client.put(
        f"/api/commerce/products/{product_id}/inventory", headers=seller,
        json={"quantity": 5, "expected_version": 0},
    )
    assert stale_stock.status_code == 409
    too_many = client.put(
        f"/api/commerce/cart/{product_id}", headers=buyer,
        json={"quantity": 3, "expected_version": 0},
    )
    assert too_many.status_code == 409

    assert client.put(
        f"/api/commerce/cart/{product_id}", headers=buyer,
        json={"quantity": 1, "expected_version": 0},
    ).status_code == 200
    checked = client.post(
        "/api/commerce/checkout",
        headers={**buyer, "Idempotency-Key": "checkout-isolation-01"},
    ).json()
    order = checked["buyer_orders"][0]
    denied = client.post(
        f"/api/commerce/orders/{order['id']}/sandbox-payment",
        headers={**outsider, "Idempotency-Key": "sandbox-denied-001"},
        json={"expected_version": order["version"]},
    )
    assert denied.status_code == 403
    cancelled = client.post(
        f"/api/commerce/orders/{order['id']}/cancel", headers=buyer,
        json={"expected_version": order["version"]},
    )
    assert cancelled.status_code == 200
    restored = client.get("/api/commerce", headers=buyer).json()["catalog"][0]
    assert restored["inventory"]["available_qty"] == 2


def test_structured_catalog_search_and_detail_are_server_authoritative() -> None:
    client, identity = _stack()
    seller = _headers("seller-catalog")
    reviewer = _headers("reviewer-catalog")
    buyer = _headers("buyer-catalog")
    _grant(identity, "seller-catalog", "commerce-ws", "seller")
    _grant(identity, "reviewer-catalog", "commerce-ws", "reviewer")
    identity.ensure_identity("buyer-catalog", "commerce-ws", role="owner")
    IdentityService(identity).bootstrap("buyer-catalog", "commerce-ws")
    assert client.post(
        "/api/commerce/stores", headers=seller, json={"name": "目录测试店铺"}
    ).status_code == 200

    created = client.post(
        "/api/commerce/products",
        headers={**seller, "Idempotency-Key": "catalog-product-create-0001"},
        json={
            "title": "竹编收纳篮测试作品",
            "summary": "用于验证结构化目录，不构成正式非遗认证。",
            "price_cents": 8800,
            "source_note": "卖家声明，来源待独立核验。",
            "category_slug": "weaving",
            "craft_type": "竹编",
            "origin_region": "四川",
            "season_tag": "新春礼赠",
        },
    )
    assert created.status_code == 201
    product = created.json()["seller_products"][0]
    assert product["category"]["slug"] == "weaving"
    assert product["variants"][0]["is_default"] == 1
    assert product["variants"][0]["price_cents"] == 8800

    submitted = client.post(
        f"/api/commerce/products/{product['id']}/submit",
        headers=seller,
        json={"expected_version": product["version"]},
    ).json()["seller_products"][0]
    reviewed = client.post(
        f"/api/commerce/products/{product['id']}/review",
        headers=reviewer,
        json={
            "decision": "approved",
            "note": "仅允许进入内部沙盒目录。",
            "expected_version": submitted["version"],
        },
    ).json()
    assert reviewed["review_queue"] == []
    assert client.put(
        f"/api/commerce/products/{product['id']}/inventory",
        headers=seller,
        json={"quantity": 4, "expected_version": 0},
    ).status_code == 200

    result = client.get(
        "/api/commerce/catalog",
        headers=buyer,
        params={
            "q": "竹编",
            "category": "weaving",
            "origin_region": "四川",
            "season_tag": "新春礼赠",
            "sort": "price_asc",
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == product["id"]
    assert body["items"][0]["trust"] == {
        "status": "seller_supplied_unverified",
        "label": "商家提供，待独立核验",
        "platform_endorsement": False,
    }
    assert body["filters"]["category"] == "weaving"

    detail = client.get(
        f"/api/commerce/products/{product['id']}", headers=buyer
    )
    assert detail.status_code == 200
    assert detail.json()["inventory"]["available_qty"] == 4
    assert detail.json()["media"] == []
    assert detail.json()["heritage_links"] == []

    empty = client.get(
        "/api/commerce/catalog", headers=buyer, params={"q": "不存在的商品"}
    )
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []

    invalid_category = client.post(
        "/api/commerce/products",
        headers={**seller, "Idempotency-Key": "catalog-product-invalid-0001"},
        json={
            "title": "无效类目",
            "summary": "验证服务端拒绝未知类目。",
            "price_cents": 100,
            "source_note": "内部测试。",
            "category_slug": "unknown-category",
        },
    )
    assert invalid_category.status_code == 400

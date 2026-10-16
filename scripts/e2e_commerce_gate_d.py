"""Real PostgreSQL/API acceptance for the Gate D transaction sandbox."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from haha_core.sqlalchemy_repository import SQLAlchemyCreatorRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "e2e" / "commerce-gate-d-api"
STATE_FILE = ARTIFACTS / "state.json"
REPORT_FILE = ARTIFACTS / "report.json"
API_URL = os.getenv("HAHA_E2E_API_URL", "http://127.0.0.1:8000").rstrip("/")
POSTGRES_URL = os.getenv("HAHA_TEST_POSTGRES_URL", "")


def request(method: str, path: str, user_id: str, workspace_id: str, payload: dict[str, object] | None = None, key: str = "") -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Accept": "application/json", "X-User-ID": user_id, "X-Workspace-ID": workspace_id}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    call = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=20) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body) if body else None
        except json.JSONDecodeError:
            return exc.code, body.decode(errors="replace")


def grant(user_id: str, workspace_id: str, role: str) -> None:
    if not POSTGRES_URL:
        raise RuntimeError("HAHA_TEST_POSTGRES_URL is required")
    repository = SQLAlchemyCreatorRepository(POSTGRES_URL)
    repository.ensure_identity(user_id, workspace_id, role="owner")
    identity = IdentityService(repository)
    identity.bootstrap(user_id, workspace_id)
    if any(item.role == role and item.status == "active" for item in repository.list_role_grants(user_id, workspace_id)):
        return
    now = datetime.now(UTC).isoformat(timespec="milliseconds")
    repository.save_role_grant(RoleGrant(
        id=f"grant_{uuid4().hex}", user_id=user_id, workspace_id=workspace_id,
        role=role, status="active", scope_json="{}", granted_by="gate-d-e2e",
        created_at=now, revoked_at="",
    ))


def exercise() -> dict[str, object]:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    suffix = uuid4().hex[:10]
    workspace = f"gate-d-{suffix}"
    seller, reviewer, buyer, outsider = (f"{kind}-{suffix}" for kind in ("seller", "reviewer", "buyer", "outsider"))
    grant(seller, workspace, "seller")
    grant(reviewer, workspace, "reviewer")
    assertions: dict[str, bool] = {}

    assertions["store_created"] = request("POST", "/api/commerce/stores", seller, workspace, {"name": "Gate D 内部测试店铺"})[0] == 200
    status, created = request("POST", "/api/commerce/products", seller, workspace, {
        "title": "Gate D 来源待核验测试作品", "summary": "仅验证交易沙盒，不是正式商品。",
        "price_cents": 8800, "source_note": "内部测试；来源、授权和资质均未作权威认证。",
    }, key="gate-d-product-create-0001")
    product = created["seller_products"][0]
    assertions["product_draft_created"] = status == 201 and product["status"] == "draft"
    _, submitted = request("POST", f"/api/commerce/products/{product['id']}/submit", seller, workspace, {"expected_version": product["version"]})
    queued = submitted["seller_products"][0]
    assertions["seller_cannot_self_review"] = request("POST", f"/api/commerce/products/{product['id']}/review", seller, workspace, {"decision": "approved", "note": "self", "expected_version": queued["version"]})[0] == 403
    status, _ = request("POST", f"/api/commerce/products/{product['id']}/review", reviewer, workspace, {"decision": "approved", "note": "仅批准内部沙盒验证。", "expected_version": queued["version"]})
    assertions["independent_review"] = status == 200
    status, listed = request("PUT", f"/api/commerce/products/{product['id']}/inventory", seller, workspace, {"quantity": 3, "expected_version": 0})
    assertions["inventory_listed"] = status == 200 and listed["seller_products"][0]["status"] == "listed"

    assertions["buyer_cart"] = request("PUT", f"/api/commerce/cart/{product['id']}", buyer, workspace, {"quantity": 1, "expected_version": 0})[0] == 200
    checkout_key = "gate-d-checkout-0001"
    status, checked = request("POST", "/api/commerce/checkout", buyer, workspace, key=checkout_key)
    order = checked["buyer_orders"][0]
    assertions["transactional_checkout"] = status == 200 and order["status"] == "awaiting_sandbox_payment"
    _, repeated = request("POST", "/api/commerce/checkout", buyer, workspace, key=checkout_key)
    assertions["checkout_idempotent"] = len(repeated["buyer_orders"]) == 1
    assertions["order_isolation"] = request("POST", f"/api/commerce/orders/{order['id']}/sandbox-payment", outsider, workspace, {"expected_version": order["version"]}, "gate-d-denied-payment")[0] == 403

    payment_key = "gate-d-payment-0001"
    status, paid = request("POST", f"/api/commerce/orders/{order['id']}/sandbox-payment", buyer, workspace, {"expected_version": order["version"]}, payment_key)
    paid_order = paid["buyer_orders"][0]
    assertions["sandbox_payment_explicit"] = status == 200 and paid_order["payment"]["provider"] == "internal_sandbox" and paid["sandbox"]["real_money_moved"] is False
    _, repeated_payment = request("POST", f"/api/commerce/orders/{order['id']}/sandbox-payment", buyer, workspace, {"expected_version": order["version"]}, payment_key)
    assertions["payment_idempotent"] = repeated_payment["buyer_orders"][0]["version"] == paid_order["version"]

    status, shipped = request("POST", f"/api/commerce/orders/{order['id']}/ship", seller, workspace, {"expected_version": paid_order["version"], "tracking_note": "内部沙盒履约，无真实物流。"})
    shipped_order = shipped["seller_orders"][0]
    assertions["seller_fulfillment"] = status == 200 and shipped_order["status"] == "shipped"
    status, delivered = request("POST", f"/api/commerce/orders/{order['id']}/confirm-delivery", buyer, workspace, {"expected_version": shipped_order["version"]})
    completed = delivered["buyer_orders"][0]
    assertions["buyer_delivery"] = status == 200 and completed["status"] == "completed"
    status, after = request("POST", f"/api/commerce/orders/{order['id']}/after-sales", buyer, workspace, {"expected_version": completed["version"], "reason": "内部售后验证，不触发真实退款。"})
    after_sale = after["buyer_after_sales"][0]
    assertions["after_sale_requested"] = status == 200 and after_sale["status"] == "requested"
    status, decided = request("POST", f"/api/commerce/after-sales/{after_sale['id']}/decision", seller, workspace, {"expected_version": after_sale["version"], "decision": "approved", "note": "内部沙盒已受理。"})
    assertions["after_sale_audited"] = status == 200 and decided["seller_after_sales"][0]["status"] == "approved"
    if not all(assertions.values()):
        raise RuntimeError({key: value for key, value in assertions.items() if not value})
    state = {"workspace": workspace, "seller": seller, "reviewer": reviewer, "buyer": buyer, "order_id": order["id"], "product_id": product["id"], "assertions": assertions}
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"phase": "exercise", "status": "passed", **state}
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def verify() -> dict[str, object]:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    status, buyer = request("GET", "/api/commerce", state["buyer"], state["workspace"])
    _, seller = request("GET", "/api/commerce", state["seller"], state["workspace"])
    order = next(item for item in buyer["buyer_orders"] if item["id"] == state["order_id"])
    product = next(item for item in seller["seller_products"] if item["id"] == state["product_id"])
    assertions = {
        "restored_after_restart": status == 200,
        "order_and_payment_restored": order["status"] == "after_sales" and order["payment"]["provider"] == "internal_sandbox",
        "fulfillment_restored": order["fulfillment"]["status"] == "delivered",
        "after_sale_restored": buyer["buyer_after_sales"][0]["status"] == "approved",
        "inventory_restored": product["inventory"]["available_qty"] == 2 and product["inventory"]["sold_qty"] == 1,
        "sandbox_boundary_restored": buyer["sandbox"]["real_money_moved"] is False,
    }
    if not all(assertions.values()):
        raise RuntimeError({key: value for key, value in assertions.items() if not value})
    report = {"phase": "verify-after-restart", "status": "passed", "exercise_assertions": state["assertions"], "restart_assertions": assertions}
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("exercise", "verify"), default="exercise")
    args = parser.parse_args()
    print(json.dumps(exercise() if args.phase == "exercise" else verify(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

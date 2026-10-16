"""Application service for the auditable Gate D transaction sandbox."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from haha_commerce.domain import (
    AfterSale,
    CartItem,
    CommerceConflictError,
    CommerceNotFoundError,
    CommercePermissionError,
    Inventory,
    Product,
)
from haha_commerce.repository import CommerceRepository
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService
from haha_user_center.service import UserCenterService


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _clean(value: str, label: str, maximum: int, *, required: bool = True) -> str:
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{label}不能为空")
    if len(cleaned) > maximum:
        raise ValueError(f"{label}不能超过 {maximum} 个字符")
    return cleaned


def _key(value: str) -> str:
    cleaned = _clean(value, "幂等键", 200)
    if len(cleaned) < 8:
        raise ValueError("幂等键不能少于 8 个字符")
    return cleaned


class CommerceService:
    def __init__(self, repository: CommerceRepository, identity_repository: Any) -> None:
        self.repository = repository
        self.identity_repository = identity_repository
        self.identity_service = IdentityService(identity_repository)
        self.user_center = UserCenterService(identity_repository)

    def snapshot(self, user_id: str, workspace_id: str) -> dict[str, object]:
        roles = self._roles(user_id, workspace_id)
        if "buyer" not in roles:
            raise CommercePermissionError("当前账户未开通买家身份")
        store = self.repository.get_store(user_id, workspace_id)
        seller_products = self.repository.list_products(
            workspace_id, seller_user_id=user_id
        ) if "seller" in roles else []
        catalog = self.repository.list_products(workspace_id)
        cart = self.repository.list_cart_items(user_id, workspace_id)
        buyer_orders = self.repository.list_orders(workspace_id, buyer_user_id=user_id)
        seller_orders = self.repository.list_orders(
            workspace_id, seller_user_id=user_id
        ) if "seller" in roles else []
        review_queue = self.repository.list_products(
            workspace_id, review_queue=True
        ) if roles & {"reviewer", "admin"} else []
        product_ids = {item.id for item in catalog + seller_products + review_queue}
        products = {
            item.id: item for item in catalog + seller_products + review_queue
        }
        inventory = {
            product_id: self.repository.get_inventory(product_id, workspace_id)
            for product_id in product_ids
        }

        def product_payload(item: Product) -> dict[str, object]:
            stock = inventory.get(item.id)
            return {
                **asdict(item),
                "inventory": asdict(stock) if stock else {
                    "available_qty": 0, "sold_qty": 0, "version": 0, "updated_at": "",
                },
            }

        def order_payload(order: Any) -> dict[str, object]:
            payment = self.repository.get_payment(order.id, workspace_id)
            fulfillment = self.repository.get_fulfillment(order.id, workspace_id)
            return {
                **asdict(order),
                "items": [asdict(item) for item in self.repository.list_order_items(order.id, workspace_id)],
                "payment": asdict(payment) if payment else None,
                "fulfillment": asdict(fulfillment) if fulfillment else None,
            }

        cart_payload = []
        for line in cart:
            product = products.get(line.product_id) or self.repository.get_product(
                line.product_id, workspace_id
            )
            cart_payload.append({
                **asdict(line),
                "product": product_payload(product) if product else None,
            })
        return {
            "roles": sorted(roles),
            "store": asdict(store) if store else None,
            "catalog": [product_payload(item) for item in catalog],
            "seller_products": [product_payload(item) for item in seller_products],
            "review_queue": [product_payload(item) for item in review_queue],
            "cart": cart_payload,
            "buyer_orders": [order_payload(item) for item in buyer_orders],
            "seller_orders": [order_payload(item) for item in seller_orders],
            "buyer_after_sales": [asdict(item) for item in self.repository.list_after_sales(workspace_id, buyer_user_id=user_id)],
            "seller_after_sales": [asdict(item) for item in self.repository.list_after_sales(workspace_id, seller_user_id=user_id)] if "seller" in roles else [],
            "sandbox": {
                "status": "internal_test_only",
                "payment_provider": "internal_sandbox",
                "real_money_moved": False,
                "notice": "内部交易沙盒：不处理真实资金，不采集银行卡或支付凭证，不代表商品已获权威认证。",
                "checkout_scope": "single_store",
            },
        }

    def open_store(self, user_id: str, workspace_id: str, name: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "seller")
        self.repository.ensure_store(user_id, workspace_id, _clean(name, "店铺名称", 200))
        return self.snapshot(user_id, workspace_id)

    def create_product(self, user_id: str, workspace_id: str, *, title: str, summary: str, price_cents: int, source_note: str, idempotency_key: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "seller")
        creation_key = _key(idempotency_key)
        if not 1 <= price_cents <= 10_000_000:
            raise ValueError("沙盒价格必须在 0.01 至 100000.00 元之间")
        store = self.repository.get_store(user_id, workspace_id)
        if not store:
            raise CommerceConflictError("请先创建店铺")
        cleaned_title = _clean(title, "商品名称", 200)
        cleaned_summary = _clean(summary, "商品说明", 2000)
        cleaned_source = _clean(source_note, "来源与授权说明", 1000)
        existing = self.repository.find_product_by_creation_key(
            user_id, workspace_id, creation_key
        )
        if existing:
            if (
                existing.title != cleaned_title
                or existing.summary != cleaned_summary
                or existing.price_cents != price_cents
                or existing.source_note != cleaned_source
            ):
                raise CommerceConflictError("幂等键已用于不同的商品草稿")
            return self.snapshot(user_id, workspace_id)
        now = _now()
        product = Product(
            f"product_{uuid4().hex}", workspace_id, store.id, user_id,
            cleaned_title, cleaned_summary, price_cents, "CNY", cleaned_source,
            "seller_supplied_unverified", creation_key, "draft", 1, "", "", now, now,
        )
        if not self.repository.create_product(product):
            existing = self.repository.find_product_by_creation_key(
                user_id, workspace_id, creation_key
            )
            if not existing or (
                existing.title != cleaned_title
                or existing.summary != cleaned_summary
                or existing.price_cents != price_cents
                or existing.source_note != cleaned_source
            ):
                raise CommerceConflictError("商品草稿创建发生并发冲突")
        return self.snapshot(user_id, workspace_id)

    def submit_product(self, user_id: str, workspace_id: str, product_id: str, expected_version: int) -> dict[str, object]:
        product = self._owned_product(user_id, workspace_id, product_id)
        if product.status not in {"draft", "rejected"}:
            raise CommerceConflictError("商品当前不能提交审核")
        if product.version != expected_version:
            raise CommerceConflictError("商品版本已变化，请刷新后重试")
        self.repository.transition_product(replace(
            product, status="submitted", version=product.version + 1,
            reviewer_note="", reviewed_by="", updated_at=_now(),
        ), expected_version)
        return self.snapshot(user_id, workspace_id)

    def moderate_product(self, user_id: str, workspace_id: str, product_id: str, decision: str, note: str, expected_version: int) -> dict[str, object]:
        self._require_any_role(user_id, workspace_id, {"reviewer", "admin"})
        product = self._product(product_id, workspace_id)
        if product.seller_user_id == user_id:
            raise CommercePermissionError("卖家不能审核自己的商品")
        if product.status != "submitted" or product.version != expected_version:
            raise CommerceConflictError("商品审核状态或版本已变化")
        if decision not in {"approved", "rejected"}:
            raise ValueError("审核决定无效")
        self.repository.transition_product(replace(
            product, status=decision, version=product.version + 1,
            reviewer_note=_clean(note, "审核意见", 1000), reviewed_by=user_id,
            updated_at=_now(),
        ), expected_version)
        self._notify(
            product.seller_user_id,
            workspace_id,
            title=f"商品审核结果：{'通过' if decision == 'approved' else '退回'}",
            body=_clean(note, "审核意见", 1000),
            target_href="/commerce?view=seller",
            key=f"product-review:{product.id}:v{product.version + 1}",
        )
        return self.snapshot(user_id, workspace_id)

    def set_inventory(self, user_id: str, workspace_id: str, product_id: str, quantity: int, expected_version: int) -> dict[str, object]:
        product = self._owned_product(user_id, workspace_id, product_id)
        if product.status not in {"approved", "listed", "delisted"}:
            raise CommerceConflictError("商品通过审核后才能设置库存")
        if not 0 <= quantity <= 1_000_000:
            raise ValueError("库存数量无效")
        current = self.repository.get_inventory(product_id, workspace_id)
        current_version = current.version if current else 0
        if current_version != expected_version:
            raise CommerceConflictError("库存版本已变化，请刷新后重试")
        now = _now()
        stock = Inventory(product_id, workspace_id, quantity, current.sold_qty if current else 0, current_version + 1, now)
        next_status = "listed" if quantity > 0 else (
            "delisted" if product.status in {"listed", "delisted"} else "approved"
        )
        product_update = replace(
            product, status=next_status,
            version=product.version + 1, updated_at=now,
        )
        self.repository.set_inventory(stock, expected_version, product_update)
        return self.snapshot(user_id, workspace_id)

    def set_cart_item(self, user_id: str, workspace_id: str, product_id: str, quantity: int, expected_version: int) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        product = self._product(product_id, workspace_id)
        stock = self.repository.get_inventory(product_id, workspace_id)
        if product.status != "listed" or not stock:
            raise CommerceConflictError("商品当前不可购买")
        if not 1 <= quantity <= 99 or quantity > stock.available_qty:
            raise CommerceConflictError("购买数量超过可用库存")
        current = next((item for item in self.repository.list_cart_items(user_id, workspace_id) if item.product_id == product_id), None)
        current_version = current.version if current else 0
        if current_version != expected_version:
            raise CommerceConflictError("购物车版本已变化，请刷新后重试")
        now = _now()
        item = CartItem(
            current.id if current else f"cart_{uuid4().hex}", user_id, workspace_id,
            product_id, quantity, current_version + 1,
            current.created_at if current else now, now,
        )
        self.repository.set_cart_item(item, expected_version)
        return self.snapshot(user_id, workspace_id)

    def remove_cart_item(self, user_id: str, workspace_id: str, product_id: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        self.repository.remove_cart_item(user_id, workspace_id, product_id)
        return self.snapshot(user_id, workspace_id)

    def checkout(self, user_id: str, workspace_id: str, idempotency_key: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        order, _created = self.repository.checkout(
            user_id, workspace_id, _key(idempotency_key)
        )
        self._notify(
            order.seller_user_id,
            workspace_id,
            title="收到新的沙盒订单",
            body="买家已创建内部沙盒订单，请等待沙盒支付状态更新。",
            target_href="/commerce?view=seller",
            key=f"order-created:{order.id}",
        )
        return self.snapshot(user_id, workspace_id)

    def sandbox_pay(self, user_id: str, workspace_id: str, order_id: str, expected_version: int, idempotency_key: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        order, _payment, _created = self.repository.authorize_sandbox_payment(
            order_id, user_id, workspace_id, _key(idempotency_key), expected_version
        )
        self._notify(
            order.seller_user_id,
            workspace_id,
            title="沙盒订单已支付",
            body="内部沙盒支付状态已更新；未发生真实资金划转。",
            target_href="/commerce?view=seller",
            key=f"order-paid:{order.id}:v{order.version}",
        )
        return self.snapshot(user_id, workspace_id)

    def cancel_order(self, user_id: str, workspace_id: str, order_id: str, expected_version: int) -> dict[str, object]:
        order = self.repository.cancel_order(
            order_id, user_id, workspace_id, expected_version
        )
        self._notify(
            order.seller_user_id,
            workspace_id,
            title="沙盒订单已取消",
            body="买家取消了待支付订单，占用库存已经恢复。",
            target_href="/commerce?view=seller",
            key=f"order-cancelled:{order.id}:v{order.version}",
        )
        return self.snapshot(user_id, workspace_id)

    def ship_order(self, user_id: str, workspace_id: str, order_id: str, tracking_note: str, expected_version: int) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "seller")
        order, _fulfillment = self.repository.ship_order(
            order_id,
            user_id,
            workspace_id,
            _clean(tracking_note, "履约备注", 500),
            expected_version,
        )
        self._notify(
            order.buyer_user_id,
            workspace_id,
            title="沙盒订单已发货",
            body="卖家已记录内部沙盒履约信息，请在确认后完成收货。",
            target_href="/commerce?view=orders",
            key=f"order-shipped:{order.id}:v{order.version}",
        )
        return self.snapshot(user_id, workspace_id)

    def confirm_delivery(self, user_id: str, workspace_id: str, order_id: str, expected_version: int) -> dict[str, object]:
        order, _fulfillment = self.repository.confirm_delivery(
            order_id, user_id, workspace_id, expected_version
        )
        self._notify(
            order.seller_user_id,
            workspace_id,
            title="沙盒订单已确认收货",
            body="买家已确认内部沙盒履约完成。",
            target_href="/commerce?view=seller",
            key=f"order-delivered:{order.id}:v{order.version}",
        )
        return self.snapshot(user_id, workspace_id)

    def request_after_sale(self, user_id: str, workspace_id: str, order_id: str, reason: str, expected_order_version: int) -> dict[str, object]:
        order = self.repository.get_order(order_id, workspace_id)
        if not order:
            raise CommerceNotFoundError("订单不存在")
        now = _now()
        after_sale = self.repository.request_after_sale(AfterSale(
            f"after_{uuid4().hex}", order_id, workspace_id, user_id,
            order.seller_user_id, _clean(reason, "售后原因", 1000),
            "requested", "", 1, now, now,
        ), expected_order_version)
        self._notify(
            order.seller_user_id,
            workspace_id,
            title="收到沙盒售后申请",
            body=after_sale.reason,
            target_href="/commerce?view=seller",
            key=f"after-sale-requested:{after_sale.id}",
        )
        return self.snapshot(user_id, workspace_id)

    def decide_after_sale(self, user_id: str, workspace_id: str, after_sale_id: str, decision: str, note: str, expected_version: int) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "seller")
        current = next((item for item in self.repository.list_after_sales(workspace_id, seller_user_id=user_id) if item.id == after_sale_id), None)
        if not current:
            raise CommerceNotFoundError("售后申请不存在")
        if current.status != "requested" or current.version != expected_version:
            raise CommerceConflictError("售后状态或版本已变化")
        if decision not in {"approved", "rejected"}:
            raise ValueError("售后决定无效")
        decided = self.repository.decide_after_sale(replace(
            current, status=decision, decision_note=_clean(note, "售后意见", 1000),
            version=current.version + 1, updated_at=_now(),
        ), expected_version)
        self._notify(
            decided.buyer_user_id,
            workspace_id,
            title=f"沙盒售后已{'受理' if decision == 'approved' else '驳回'}",
            body=decided.decision_note,
            target_href="/commerce?view=orders",
            key=f"after-sale-decision:{decided.id}:v{decided.version}",
        )
        return self.snapshot(user_id, workspace_id)

    def _notify(
        self,
        user_id: str,
        workspace_id: str,
        *,
        title: str,
        body: str,
        target_href: str,
        key: str,
    ) -> None:
        self.user_center.create_notification(
            user_id,
            workspace_id,
            kind="commerce",
            title=title,
            body=body,
            target_href=target_href,
            idempotency_key=key,
        )

    def _roles(self, user_id: str, workspace_id: str) -> set[str]:
        self.identity_service.bootstrap(user_id, workspace_id)
        grants: list[RoleGrant] = self.identity_repository.list_role_grants(user_id, workspace_id)
        return {item.role for item in grants if item.status == "active"}

    def _require_role(self, user_id: str, workspace_id: str, role: str) -> None:
        if role not in self._roles(user_id, workspace_id):
            raise CommercePermissionError(f"当前账户未获得{role}身份授权")

    def _require_any_role(self, user_id: str, workspace_id: str, roles: set[str]) -> None:
        if not self._roles(user_id, workspace_id) & roles:
            raise CommercePermissionError("当前账户没有商品审核权限")

    def _product(self, product_id: str, workspace_id: str) -> Product:
        product = self.repository.get_product(product_id, workspace_id)
        if not product:
            raise CommerceNotFoundError("商品不存在")
        return product

    def _owned_product(self, user_id: str, workspace_id: str, product_id: str) -> Product:
        self._require_role(user_id, workspace_id, "seller")
        product = self._product(product_id, workspace_id)
        if product.seller_user_id != user_id:
            raise CommercePermissionError("不能管理其他卖家的商品")
        return product

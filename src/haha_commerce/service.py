"""Application service for the auditable Gate D transaction sandbox."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from haha_commerce.advisor import ShoppingAdvisor
from haha_commerce.domain import (
    AfterSale,
    CartItem,
    CommerceAdvisorRateLimitError,
    CommerceAdvisorUnavailableError,
    CommerceConflictError,
    CommerceNotFoundError,
    CommercePermissionError,
    Inventory,
    Product,
    ProductMedia,
    ShoppingAdvisorInteraction,
)
from haha_commerce.repository import CommerceRepository
from haha_community.media_storage import FileSystemMediaStorage, MediaStorageError
from haha_identity.domain import RoleGrant
from haha_identity.service import IdentityService
from haha_media.model_router import ModelCallError
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
    def __init__(
        self,
        repository: CommerceRepository,
        identity_repository: Any,
        advisor: ShoppingAdvisor | None = None,
        advisor_request_limit: int | None = None,
        media_storage: FileSystemMediaStorage | None = None,
    ) -> None:
        self.repository = repository
        self.identity_repository = identity_repository
        self.identity_service = IdentityService(identity_repository)
        self.user_center = UserCenterService(identity_repository)
        self.advisor = advisor or ShoppingAdvisor()
        self.media_storage = media_storage or FileSystemMediaStorage()
        self.advisor_request_limit = advisor_request_limit or int(
            os.getenv("COMMERCE_ADVISOR_REQUEST_LIMIT_24H", "30")
        )
        if not 1 <= self.advisor_request_limit <= 100:
            raise ValueError("AI 导购 24 小时请求上限必须在 1 至 100 之间")

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
        categories = {item.id: item for item in self.repository.list_categories()}

        def product_payload(item: Product) -> dict[str, object]:
            stock = inventory.get(item.id)
            return {
                **asdict(item),
                "category": asdict(categories[item.category_id])
                if item.category_id in categories
                else None,
                "media": [
                    self._media_payload(media)
                    for media in self.repository.list_product_media(item.id, workspace_id)
                ],
                "variants": [
                    asdict(variant)
                    for variant in self.repository.list_product_variants(item.id, workspace_id)
                ],
                "heritage_links": [
                    asdict(link)
                    for link in self.repository.list_product_heritage_links(item.id, workspace_id)
                ],
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
            "seller_insights": self._seller_insights(seller_products, seller_orders)
            if "seller" in roles else None,
            "categories": [asdict(item) for item in categories.values()],
            "sandbox": {
                "status": "internal_test_only",
                "payment_provider": "internal_sandbox",
                "real_money_moved": False,
                "notice": "内部交易沙盒：不处理真实资金，不采集银行卡或支付凭证，不代表商品已获权威认证。",
                "checkout_scope": "single_store",
                "production_gates": {
                    "payment": {
                        "status": "blocked",
                        "reason": "尚未接入持牌支付机构、回调验签、对账、退款与资金安全审查。",
                    },
                    "logistics": {
                        "status": "blocked",
                        "reason": "尚未接入承运商、真实运单、轨迹回调、隐私地址保护与异常赔付流程。",
                    },
                    "public_release": {
                        "status": "blocked",
                        "reason": "商家资质、商品权利审核、内容治理、客服和发布门禁尚未完成。",
                    },
                },
            },
        }

    def open_store(self, user_id: str, workspace_id: str, name: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "seller")
        self.repository.ensure_store(user_id, workspace_id, _clean(name, "店铺名称", 200))
        return self.snapshot(user_id, workspace_id)

    def create_product(
        self,
        user_id: str,
        workspace_id: str,
        *,
        title: str,
        summary: str,
        price_cents: int,
        source_note: str,
        idempotency_key: str,
        category_slug: str = "other",
        craft_type: str = "",
        origin_region: str = "",
        season_tag: str = "",
    ) -> dict[str, object]:
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
        categories = {item.slug: item for item in self.repository.list_categories()}
        cleaned_category = _clean(category_slug, "商品类目", 80).casefold()
        category = categories.get(cleaned_category)
        if not category:
            raise ValueError("商品类目不存在或已停用")
        cleaned_craft = _clean(craft_type, "工艺类型", 120, required=False)
        cleaned_region = _clean(origin_region, "来源地区", 120, required=False)
        cleaned_season = _clean(season_tag, "季节主题", 80, required=False)
        existing = self.repository.find_product_by_creation_key(
            user_id, workspace_id, creation_key
        )
        if existing:
            if (
                existing.title != cleaned_title
                or existing.summary != cleaned_summary
                or existing.price_cents != price_cents
                or existing.source_note != cleaned_source
                or existing.category_id != category.id
                or existing.craft_type != cleaned_craft
                or existing.origin_region != cleaned_region
                or existing.season_tag != cleaned_season
            ):
                raise CommerceConflictError("幂等键已用于不同的商品草稿")
            return self.snapshot(user_id, workspace_id)
        now = _now()
        product = Product(
            f"product_{uuid4().hex}", workspace_id, store.id, user_id,
            cleaned_title, cleaned_summary, price_cents, "CNY", cleaned_source,
            "seller_supplied_unverified", creation_key, "draft", 1, "", "", now, now,
            category.id, cleaned_craft, cleaned_region, cleaned_season,
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
                or existing.category_id != category.id
                or existing.craft_type != cleaned_craft
                or existing.origin_region != cleaned_region
                or existing.season_tag != cleaned_season
            ):
                raise CommerceConflictError("商品草稿创建发生并发冲突")
        return self.snapshot(user_id, workspace_id)

    def catalog(
        self,
        user_id: str,
        workspace_id: str,
        *,
        query: str = "",
        category: str = "",
        craft_type: str = "",
        origin_region: str = "",
        season_tag: str = "",
        sort: str = "newest",
        page: int = 1,
        page_size: int = 24,
    ) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        cleaned_query = _clean(query, "搜索词", 200, required=False)
        cleaned_category = _clean(category, "商品类目", 80, required=False).casefold()
        cleaned_craft = _clean(craft_type, "工艺类型", 120, required=False)
        cleaned_region = _clean(origin_region, "来源地区", 120, required=False)
        cleaned_season = _clean(season_tag, "季节主题", 80, required=False)
        if sort not in {"newest", "price_asc", "price_desc"}:
            raise ValueError("商品排序方式无效")
        if not 1 <= page <= 10_000 or not 1 <= page_size <= 60:
            raise ValueError("商品分页参数无效")
        items, total = self.repository.search_catalog(
            workspace_id,
            query=cleaned_query,
            category_slug=cleaned_category,
            craft_type=cleaned_craft,
            origin_region=cleaned_region,
            season_tag=cleaned_season,
            sort=sort,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [self._catalog_product_payload(item, workspace_id) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total,
            "categories": [asdict(item) for item in self.repository.list_categories()],
            "filters": {
                "query": cleaned_query,
                "category": cleaned_category,
                "craft_type": cleaned_craft,
                "origin_region": cleaned_region,
                "season_tag": cleaned_season,
                "sort": sort,
            },
        }

    def product_detail(
        self, user_id: str, workspace_id: str, product_id: str
    ) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        product = self._product(product_id, workspace_id)
        roles = self._roles(user_id, workspace_id)
        may_preview = product.seller_user_id == user_id or bool(
            roles & {"reviewer", "admin"}
        )
        if product.status != "listed" and not may_preview:
            raise CommerceNotFoundError("商品不存在或当前不可查看")
        return self._catalog_product_payload(product, workspace_id)

    def advisor_snapshot(self, user_id: str, workspace_id: str) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        return {
            "advisor": {
                **self.advisor.status(),
                "request_limit_24h": self.advisor_request_limit,
                "authority": "recommend_only",
            },
            "history": [
                self._advisor_payload(item, workspace_id)
                for item in self.repository.list_advisor_interactions(
                    user_id, workspace_id, limit=20
                )
                if item.status == "completed"
            ],
        }

    def ask_advisor(
        self,
        user_id: str,
        workspace_id: str,
        *,
        question: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        self._require_role(user_id, workspace_id, "buyer")
        clean_question = _clean(question, "导购问题", 1000)
        clean_key = _key(idempotency_key)
        request_hash = hashlib.sha256(clean_question.encode("utf-8")).hexdigest()
        existing = self.repository.find_advisor_interaction(
            user_id, workspace_id, clean_key
        )
        if existing:
            if existing.request_hash != request_hash:
                raise CommerceConflictError("幂等键已用于不同的导购问题")
            if existing.status == "completed":
                result = self.advisor_snapshot(user_id, workspace_id)
                result["last_result"] = self._advisor_payload(existing, workspace_id)
                return result
            raise CommerceConflictError("相同导购请求正在处理或此前已失败，请更换请求键重试")
        status = self.advisor.status()
        if status["status"] != "available":
            raise CommerceAdvisorUnavailableError(str(status["reason"]))
        created_after = (datetime.now(UTC) - timedelta(hours=24)).isoformat(
            timespec="milliseconds"
        )
        if self.repository.count_advisor_interactions_since(
            user_id, workspace_id, created_after
        ) >= self.advisor_request_limit:
            raise CommerceAdvisorRateLimitError(
                f"当前账户 24 小时内最多提交 {self.advisor_request_limit} 次 AI 导购请求"
            )
        now = _now()
        pending = ShoppingAdvisorInteraction(
            id=f"advisor_{uuid4().hex}",
            user_id=user_id,
            workspace_id=workspace_id,
            question=clean_question,
            answer="",
            recommendations_json="[]",
            suggestions_json="[]",
            status="pending",
            mode="pending",
            model=str(status["model"]),
            provider="",
            request_id="",
            input_tokens=0,
            output_tokens=0,
            error_code="",
            idempotency_key=clean_key,
            request_hash=request_hash,
            created_at=now,
            updated_at=now,
        )
        if not self.repository.create_advisor_interaction(pending):
            raise CommerceConflictError("导购请求发生并发冲突，请重试")
        products, _ = self.repository.search_catalog(workspace_id, limit=30)
        try:
            answer = self.advisor.answer(clean_question, products)
        except ModelCallError as exc:
            evidence = exc.evidence
            failed = replace(
                pending,
                status="failed",
                mode="model_error",
                provider=evidence.provider if evidence else "",
                request_id=evidence.request_id if evidence else "",
                input_tokens=evidence.input_tokens if evidence else 0,
                output_tokens=evidence.output_tokens if evidence else 0,
                error_code=type(exc).__name__,
                updated_at=_now(),
            )
            self.repository.update_advisor_interaction(failed, "pending")
            raise CommerceAdvisorUnavailableError(str(exc)) from exc
        evidence = answer.evidence
        completed = replace(
            pending,
            answer=answer.answer,
            recommendations_json=json.dumps(
                [asdict(item) for item in answer.recommendations],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            suggestions_json=json.dumps(
                list(answer.suggestions), ensure_ascii=False, separators=(",", ":")
            ),
            status="completed",
            mode=answer.mode,
            provider=evidence.provider if evidence else "server",
            request_id=evidence.request_id if evidence else "",
            input_tokens=evidence.input_tokens if evidence else 0,
            output_tokens=evidence.output_tokens if evidence else 0,
            updated_at=_now(),
        )
        if not self.repository.update_advisor_interaction(completed, "pending"):
            raise CommerceConflictError("导购结果保存发生并发冲突")
        result = self.advisor_snapshot(user_id, workspace_id)
        result["last_result"] = self._advisor_payload(completed, workspace_id)
        return result

    def _advisor_payload(
        self, interaction: ShoppingAdvisorInteraction, workspace_id: str
    ) -> dict[str, object]:
        raw_recommendations = json.loads(interaction.recommendations_json)
        recommendations: list[dict[str, object]] = []
        for item in raw_recommendations:
            product = self.repository.get_product(item["product_id"], workspace_id)
            if product and product.status == "listed":
                recommendations.append({
                    "product": self._catalog_product_payload(product, workspace_id),
                    "reason": item["reason"],
                })
        return {
            "id": interaction.id,
            "question": interaction.question,
            "answer": interaction.answer,
            "recommendations": recommendations,
            "suggestions": json.loads(interaction.suggestions_json),
            "mode": interaction.mode,
            "model": interaction.model,
            "provider": interaction.provider,
            "request_id": interaction.request_id,
            "input_tokens": interaction.input_tokens,
            "output_tokens": interaction.output_tokens,
            "created_at": interaction.created_at,
        }

    def _catalog_product_payload(
        self, product: Product, workspace_id: str
    ) -> dict[str, object]:
        category = next(
            (
                item
                for item in self.repository.list_categories()
                if item.id == product.category_id
            ),
            None,
        )
        stock = self.repository.get_inventory(product.id, workspace_id)
        return {
            **asdict(product),
            "category": asdict(category) if category else None,
            "media": [
                self._media_payload(item)
                for item in self.repository.list_product_media(product.id, workspace_id)
            ],
            "variants": [
                asdict(item)
                for item in self.repository.list_product_variants(product.id, workspace_id)
            ],
            "heritage_links": [
                asdict(item)
                for item in self.repository.list_product_heritage_links(
                    product.id, workspace_id
                )
            ],
            "inventory": asdict(stock)
            if stock
            else {"available_qty": 0, "sold_qty": 0, "version": 0, "updated_at": ""},
            "trust": {
                "status": product.provenance,
                "label": "商家提供，待独立核验"
                if product.provenance == "seller_supplied_unverified"
                else product.provenance,
                "platform_endorsement": False,
            },
        }

    @staticmethod
    def _media_payload(media: ProductMedia) -> dict[str, object]:
        payload = asdict(media)
        payload.pop("storage_key", None)
        payload["url"] = f"/api/commerce/media/{media.id}"
        return payload

    def _seller_insights(self, products: list[Product], orders: list[Any]) -> dict[str, object]:
        status_counts = {
            status: sum(item.status == status for item in products)
            for status in ("draft", "submitted", "approved", "rejected", "listed", "delisted")
        }
        actionable = {
            "drafts_to_finish": status_counts["draft"] + status_counts["rejected"],
            "orders_to_ship": sum(item.status == "paid" for item in orders),
            "after_sales_to_handle": sum(item.status == "after_sales" for item in orders),
        }
        completed = [item for item in orders if item.status == "completed"]
        return {
            "product_status_counts": status_counts,
            "order_count": len(orders),
            "completed_order_count": len(completed),
            "completed_revenue_cents": sum(item.total_cents for item in completed),
            "actionable": actionable,
            "scope": "internal_sandbox_only",
            "generated_at": _now(),
        }

    def update_product_details(
        self, user_id: str, workspace_id: str, product_id: str, *,
        title: str, summary: str, price_cents: int, source_note: str,
        category_slug: str, craft_type: str, origin_region: str,
        season_tag: str, expected_version: int,
    ) -> dict[str, object]:
        product = self._owned_product(user_id, workspace_id, product_id)
        if product.status not in {"draft", "rejected"}:
            raise CommerceConflictError("仅草稿或被退回的商品可以编辑；在售商品请先下架并重新审核")
        if product.version != expected_version:
            raise CommerceConflictError("商品版本已变化，请刷新后重试")
        if not 1 <= price_cents <= 10_000_000:
            raise ValueError("沙盒价格必须在 0.01 至 100000.00 元之间")
        category = next((item for item in self.repository.list_categories()
                         if item.slug == category_slug.casefold()), None)
        if not category:
            raise ValueError("商品类目不存在或已停用")
        updated = replace(
            product, title=_clean(title, "商品名称", 200),
            summary=_clean(summary, "商品说明", 2000), price_cents=price_cents,
            source_note=_clean(source_note, "来源与授权说明", 1000),
            category_id=category.id,
            craft_type=_clean(craft_type, "工艺类型", 120, required=False),
            origin_region=_clean(origin_region, "来源地区", 120, required=False),
            season_tag=_clean(season_tag, "季节主题", 80, required=False),
            reviewer_note="", reviewed_by="", version=product.version + 1,
            updated_at=_now(),
        )
        self.repository.update_product(updated, expected_version)
        return self.snapshot(user_id, workspace_id)

    def add_product_image(
        self, user_id: str, workspace_id: str, product_id: str, *,
        staged_path: Any, filename: str, declared_content_type: str,
        alt_text: str, source_note: str, expected_version: int,
    ) -> dict[str, object]:
        _clean(filename, "文件名", 255)
        product = self._owned_product(user_id, workspace_id, product_id)
        if product.status not in {"draft", "rejected"}:
            raise CommerceConflictError("仅草稿或被退回的商品可以管理图片")
        if product.version != expected_version:
            raise CommerceConflictError("商品版本已变化，请刷新后重试")
        existing = self.repository.list_product_media(product.id, workspace_id)
        if len(existing) >= 8:
            raise CommerceConflictError("每个商品最多上传 8 张图片")
        data = staged_path.read_bytes()
        detected = "image/jpeg" if data.startswith(b"\xff\xd8\xff") else (
            "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else ""
        )
        if detected not in {"image/jpeg", "image/png"} or declared_content_type != detected:
            raise ValueError("商品图片仅支持内容匹配的 JPEG 或 PNG 文件")
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("商品图片不能超过 10 MB")
        extension = ".jpg" if detected == "image/jpeg" else ".png"
        media_id = f"product_media_{uuid4().hex}"
        workspace_hash = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()[:16]
        storage_key = f"commerce/{workspace_hash}/{media_id}{extension}"
        now = _now()
        media = ProductMedia(
            media_id, product.id, workspace_id, "image", storage_key,
            _clean(alt_text, "图片替代文本", 300),
            _clean(source_note, "图片来源与权利说明", 1000),
            "seller_declared", len(existing), 1, now, now,
        )
        self.media_storage.commit(staged_path, storage_key)
        try:
            self.repository.add_product_media(
                media, replace(product, version=product.version + 1, updated_at=now),
                expected_version,
            )
        except Exception:
            self.media_storage.delete(storage_key)
            raise
        return self.snapshot(user_id, workspace_id)

    def remove_product_image(
        self, user_id: str, workspace_id: str, product_id: str, media_id: str,
        expected_version: int,
    ) -> dict[str, object]:
        product = self._owned_product(user_id, workspace_id, product_id)
        if product.status not in {"draft", "rejected"}:
            raise CommerceConflictError("仅草稿或被退回的商品可以管理图片")
        if product.version != expected_version:
            raise CommerceConflictError("商品版本已变化，请刷新后重试")
        removed = self.repository.remove_product_media(
            media_id, replace(product, version=product.version + 1, updated_at=_now()),
            expected_version,
        )
        try:
            self.media_storage.delete(removed.storage_key)
        except MediaStorageError:
            pass
        return self.snapshot(user_id, workspace_id)

    def product_image_path(
        self, user_id: str, workspace_id: str, media_id: str
    ) -> tuple[Any, str]:
        media = self.repository.get_product_media(media_id, workspace_id)
        if not media:
            raise CommerceNotFoundError("商品图片不存在")
        product = self._product(media.product_id, workspace_id)
        roles = self._roles(user_id, workspace_id)
        if product.status != "listed" and product.seller_user_id != user_id and not roles & {"reviewer", "admin"}:
            raise CommerceNotFoundError("商品图片不存在")
        content_type = "image/jpeg" if media.storage_key.endswith(".jpg") else "image/png"
        return self.media_storage.path_for(media.storage_key), content_type

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

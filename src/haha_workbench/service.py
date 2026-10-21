"""Build honest, role-specific workbench projections from durable state."""

from __future__ import annotations

from typing import Any

from haha_commerce.repository import CommerceRepository
from haha_identity.domain import BusinessRole
from haha_identity.service import ROLE_LABELS
from haha_learning.tutor import HeritageTutor
from haha_user_center.domain import LibraryKind
from haha_user_center.service import UserCenterService
from haha_workbench.domain import CapabilityStatus, WorkbenchMaturity
from haha_workbench.repository import WorkbenchRepository


class WorkbenchPermissionError(RuntimeError):
    """The persisted active role does not have an active server grant."""


ROLE_COPY: dict[BusinessRole, tuple[str, str, WorkbenchMaturity, str]] = {
    BusinessRole.VIEWER: (
        "继续发现值得信任的非遗内容",
        "观看、收藏、关注和稍后看使用当前账户的真实保存状态。",
        WorkbenchMaturity.PARTIAL,
        "社区目录仍有本地数据适配器；文化资产与观看状态已经服务端持久化。",
    ),
    BusinessRole.BUYER: (
        "管理文化收藏与内部沙盒购买旅程",
        "商品、购物车、订单、沙盒支付、履约和售后状态由服务端持久化。",
        WorkbenchMaturity.PARTIAL,
        "仅限内部交易沙盒，不处理真实资金，也不代表商品获得权威认证。",
    ),
    BusinessRole.LEARNER: (
        "沿真实学习路径积累可追溯的文化成长",
        "学习路径、进度、知识卡、测验、每日任务和成就均由服务端持久化。",
        WorkbenchMaturity.PARTIAL,
        "确定性学习闭环已接入；AI 非遗老师仍等待真实模型与可信知识检索。",
    ),
    BusinessRole.CREATOR: (
        "从创作项目继续完成脚本与投稿",
        "创作项目来自当前工作空间，可进入现有创作链路继续工作。",
        WorkbenchMaturity.PARTIAL,
        "脚本项目链路可用；真实媒体发布与创作者数据仍需后续内容 API。",
    ),
    BusinessRole.CONTRIBUTOR: (
        "准备有来源的非遗知识贡献",
        "身份与审核结果已持久化，正式知识稿件领域尚未建立。",
        WorkbenchMaturity.PARTIAL,
        "本阶段不会把普通收藏或模型文本伪装成已核验知识贡献。",
    ),
    BusinessRole.SELLER: (
        "管理内部沙盒店铺与履约任务",
        "店铺、商品审核、库存、订单、履约和售后状态由服务端持久化。",
        WorkbenchMaturity.PARTIAL,
        "当前不接真实支付、物流或结算，不可作为正式经营凭证。",
    ),
    BusinessRole.REVIEWER: (
        "处理被明确授权的审核任务",
        "当前仅有工作空间所有者可执行身份申请决策。",
        WorkbenchMaturity.BLOCKED,
        "内容、知识和商品审核队列尚未建立；审核员身份不会自动扩大权限。",
    ),
    BusinessRole.ADMIN: (
        "管理受控的平台能力",
        "管理员身份不能由用户自行申请或切换获得。",
        WorkbenchMaturity.BLOCKED,
        "平台管理、风险和审计后台尚未建立，当前不暴露占位管理操作。",
    ),
}

PUBLIC_PLATFORM_WORKBENCHES = {
    BusinessRole.CREATOR,
    BusinessRole.CONTRIBUTOR,
    BusinessRole.SELLER,
}


def _capability(
    key: str,
    label: str,
    description: str,
    status: CapabilityStatus,
    *,
    href: str = "",
    action_label: str = "",
    reason: str = "",
) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "description": description,
        "status": status.value,
        "href": href,
        "action_label": action_label,
        "reason": reason,
    }


CAPABILITIES: dict[BusinessRole, tuple[dict[str, str], ...]] = {
    BusinessRole.VIEWER: (
        _capability(
            "discover",
            "发现非遗内容",
            "浏览专题、人物与社区内容。",
            CapabilityStatus.LIMITED,
            href="/community",
            action_label="去发现",
            reason="社区内容仍含本地适配数据。",
        ),
        _capability(
            "library",
            "文化资产",
            "查看收藏、稍后看和想学清单。",
            CapabilityStatus.AVAILABLE,
            href="/identity",
            action_label="查看资产",
        ),
        _capability(
            "history",
            "观看足迹",
            "从服务端恢复当前账户的观看进度。",
            CapabilityStatus.AVAILABLE,
            href="/identity",
            action_label="继续观看",
        ),
    ),
    BusinessRole.BUYER: (
        _capability(
            "saved_culture",
            "文化收藏",
            "继续整理感兴趣的内容与项目。",
            CapabilityStatus.AVAILABLE,
            href="/identity",
            action_label="查看收藏",
        ),
        _capability(
            "orders",
            "订单与履约",
            "查看订单、物流和收货状态。",
            CapabilityStatus.LIMITED,
            href="/commerce",
            action_label="进入交易沙盒",
            reason="仅限内部沙盒订单与模拟履约。",
        ),
        _capability(
            "after_sales",
            "售后服务",
            "退款、退货和售后进度。",
            CapabilityStatus.LIMITED,
            href="/commerce",
            action_label="查看售后",
            reason="售后状态可审计，但不触发真实退款。",
        ),
    ),
    BusinessRole.LEARNER: (
        _capability(
            "learning_center",
            "学习成长中心",
            "进入真实学习路径、测验、每日任务与成就。",
            CapabilityStatus.AVAILABLE,
            href="/learning",
            action_label="继续学习",
        ),
        _capability(
            "learning_list",
            "想学清单",
            "查看服务端保存的学习候选内容。",
            CapabilityStatus.AVAILABLE,
            href="/learning",
            action_label="查看想学",
        ),
        _capability(
            "heritage_search",
            "非遗检索",
            "检索项目、人物和文化内容。",
            CapabilityStatus.AVAILABLE,
            href="/search",
            action_label="开始检索",
        ),
        _capability(
            "ai_tutor",
            "AI 非遗老师",
            "带来源解释、知识卡片与测验。",
            CapabilityStatus.BLOCKED,
            reason="等待真实模型 API、知识检索与学习评测接入。",
        ),
    ),
    BusinessRole.CREATOR: (
        _capability(
            "creator_projects",
            "创作项目",
            "进入真实脚本项目和运行链路。",
            CapabilityStatus.AVAILABLE,
            href="/creator",
            action_label="进入创作台",
        ),
        _capability(
            "submission",
            "内容投稿",
            "准备社区投稿资料。",
            CapabilityStatus.LIMITED,
            href="/creator/submissions/new",
            action_label="准备投稿",
            reason="投稿界面已存在，正式内容发布 API 尚未闭环。",
        ),
        _capability(
            "creator_analytics",
            "创作数据",
            "查看发布后的播放与互动表现。",
            CapabilityStatus.BLOCKED,
            reason="等待真实内容与互动 API。",
        ),
    ),
    BusinessRole.CONTRIBUTOR: (
        _capability(
            "application",
            "身份与任务",
            "查看贡献者身份和相关待办。",
            CapabilityStatus.AVAILABLE,
            href="/identity",
            action_label="查看任务",
        ),
        _capability(
            "source_dossier",
            "来源资料提交",
            "提交声明、来源和证据材料。",
            CapabilityStatus.BLOCKED,
            reason="知识稿件与来源版本领域将在下一垂直切片实现。",
        ),
        _capability(
            "corrections",
            "知识纠错",
            "对现有条目发起可审计纠错。",
            CapabilityStatus.BLOCKED,
            reason="可信知识条目与审核队列尚未接入。",
        ),
    ),
    BusinessRole.SELLER: (
        _capability(
            "application",
            "入驻状态",
            "查看卖家身份申请与审核结果。",
            CapabilityStatus.AVAILABLE,
            href="/identity",
            action_label="查看申请",
        ),
        _capability(
            "catalog",
            "商品与库存",
            "管理商品草稿、审核和库存。",
            CapabilityStatus.AVAILABLE,
            href="/commerce",
            action_label="管理商品",
        ),
        _capability(
            "orders",
            "经营订单",
            "处理订单、履约与售后。",
            CapabilityStatus.LIMITED,
            href="/commerce",
            action_label="处理沙盒订单",
            reason="只处理内部沙盒订单，不产生真实资金与物流。",
        ),
    ),
    BusinessRole.REVIEWER: (
        _capability(
            "identity_review",
            "身份审核",
            "由工作空间所有者处理身份申请。",
            CapabilityStatus.LIMITED,
            href="/review",
            action_label="查看审核入口",
            reason="业务审核员权限模型尚未独立接入。",
        ),
        _capability(
            "moderation",
            "内容与来源审核",
            "处理内容、知识和商品审核队列。",
            CapabilityStatus.BLOCKED,
            reason="统一审核系统尚未建立。",
        ),
    ),
    BusinessRole.ADMIN: (
        _capability(
            "platform_admin",
            "平台管理",
            "管理授权、风险和审计。",
            CapabilityStatus.BLOCKED,
            reason="平台管理后台尚未建立。",
        ),
    ),
}


class WorkbenchService:
    def __init__(
        self,
        repository: WorkbenchRepository,
        commerce_repository: CommerceRepository | None = None,
        learning_tutor: HeritageTutor | None = None,
    ) -> None:
        self.repository = repository
        self.commerce_repository = commerce_repository
        self.user_center = UserCenterService(repository)
        self.learning_tutor = learning_tutor or HeritageTutor()

    def platform_capabilities(self, user_id: str, workspace_id: str) -> dict[str, object]:
        """Return account-level capabilities without depending on active workbench UI state."""

        center = self.user_center.bootstrap(user_id, workspace_id)
        grants = center["roles"]
        assert isinstance(grants, list)
        professional_roles = [
            str(item["role"])
            for item in grants
            if isinstance(item, dict)
            and item.get("status") == "active"
            and BusinessRole(str(item["role"])) in PUBLIC_PLATFORM_WORKBENCHES
        ]
        tutor = self.learning_tutor.status()
        tutor_available = tutor["status"] == "available"
        return {
            "contract_version": "platform-capabilities.v1",
            "account_scope": {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "consumer_capabilities": ["viewer", "buyer", "learner"],
                "professional_workbenches": professional_roles,
            },
            "catalog_scope": {
                "status": "decision_required",
                "mode": "workspace_isolated",
                "reason": "D1 公共审核目录范围尚未批准；历史数据不会自动公开。",
            },
            "modules": [
                {
                    "key": "community", "label": "视频社区", "href": "/community",
                    "status": "limited", "reason": "已发布内容可用；跨空间公共目录等待 D1。",
                },
                {
                    "key": "commerce", "label": "非遗电商", "href": "/commerce",
                    "status": "limited", "reason": "内部交易沙盒可用；真实支付和物流保持阻断。",
                },
                {
                    "key": "learning", "label": "AI 学习", "href": "/learning",
                    "status": "available", "reason": "确定性学习闭环可用。",
                    "features": {
                        "ai_tutor": {
                            "status": "available" if tutor_available else "blocked",
                            "reason": str(tutor["reason"]),
                        }
                    },
                },
                {
                    "key": "identity", "label": "用户中心", "href": "/identity",
                    "status": "available", "reason": "统一账户、成长摘要和专业工作台管理可用。",
                },
            ],
            "internal_roles": {
                "self_service": False,
                "roles": ["reviewer", "admin"],
                "reason": "仅平台内部受控授予，不出现在公众申请或切换入口。",
            },
        }

    def snapshot(self, user_id: str, workspace_id: str) -> dict[str, object]:
        # Bootstrap owns first-account side effects such as the welcome
        # notification. Never create settings directly here: doing so can
        # race the parallel user-center request and suppress that notification.
        # Once settings exist, keep the read fail-closed so an invalid active
        # role is not silently repaired by a workbench projection.
        if self.repository.has_user_center_settings(user_id, workspace_id):
            center = self.user_center.snapshot(user_id, workspace_id)
        else:
            center = self.user_center.bootstrap(user_id, workspace_id)
        profile = center["profile"]
        assert isinstance(profile, dict)
        role = BusinessRole(str(profile["active_role"]))
        grants = center["roles"]
        if not isinstance(grants, list) or not any(
            isinstance(item, dict)
            and item.get("role") == role.value
            and item.get("status") == "active"
            for item in grants
        ):
            raise WorkbenchPermissionError("当前身份授权已失效")

        headline, description, maturity, boundary_note = ROLE_COPY[role]
        tasks = [
            item
            for item in center["tasks"]
            if isinstance(item, dict) and item.get("role") == role.value
        ]
        capabilities = [dict(item) for item in CAPABILITIES[role]]
        if role is BusinessRole.LEARNER and self.learning_tutor.status()["status"] == "available":
            tutor_capability = next(
                item for item in capabilities if item["key"] == "ai_tutor"
            )
            tutor_capability.update(
                status=CapabilityStatus.AVAILABLE.value,
                href="/learning#ai-tutor",
                action_label="向老师提问",
                reason="回答仅限版本化知识库命中的来源记录。",
            )
            boundary_note = (
                "AI 非遗老师已接通真实模型和版本化来源检索；内部已核验不等于官方认证，"
                "正式使用仍需打开具体来源复核。"
            )
        return {
            "role": role.value,
            "label": ROLE_LABELS[role],
            "headline": headline,
            "description": description,
            "maturity": maturity.value,
            "metrics": self._metrics(role, center, workspace_id),
            "capabilities": capabilities,
            "resources": self._resources(role, center, workspace_id),
            "tasks": tasks,
            "boundary_note": boundary_note,
        }

    def _metrics(
        self, role: BusinessRole, center: dict[str, object], workspace_id: str
    ) -> list[dict[str, object]]:
        summary = center["summary"]
        assert isinstance(summary, dict)
        values: list[tuple[str, str, int]]
        if role is BusinessRole.VIEWER:
            values = [
                ("history", "观看记录", int(summary["history"])),
                ("bookmarks", "收藏", int(summary["bookmarks"])),
                ("following", "关注", int(summary["following"])),
            ]
        elif role is BusinessRole.LEARNER:
            growth = center["growth"]
            assert isinstance(growth, dict)
            values = [
                ("completed_units", "完成节点", int(growth["completed_units"])),
                ("achievements", "成长成就", int(growth["achievements"])),
                ("current_streak", "连续学习", int(growth["current_streak"])),
            ]
        elif role is BusinessRole.CREATOR:
            values = [
                (
                    "projects",
                    "近期项目",
                    len(self.repository.list_projects(workspace_id, limit=100)),
                ),
                ("open_tasks", "创作待办", self._open_task_count(center, role)),
                ("unread", "未读消息", int(summary["unread_notifications"])),
            ]
        elif role is BusinessRole.BUYER:
            orders = self.commerce_repository.list_orders(
                workspace_id, buyer_user_id=str(center["profile"]["user_id"])
            ) if self.commerce_repository else []
            after_sales = self.commerce_repository.list_after_sales(
                workspace_id, buyer_user_id=str(center["profile"]["user_id"])
            ) if self.commerce_repository else []
            values = [
                ("bookmarks", "文化收藏", int(summary["bookmarks"])),
                ("orders", "沙盒订单", len(orders)),
                ("after_sales", "售后处理中", sum(item.status == "requested" for item in after_sales)),
            ]
        elif role is BusinessRole.SELLER and self.commerce_repository:
            profile = center["profile"]
            assert isinstance(profile, dict)
            seller_id = str(profile["user_id"])
            values = [
                ("products", "商品", len(self.commerce_repository.list_products(workspace_id, seller_user_id=seller_id))),
                ("orders", "沙盒订单", len(self.commerce_repository.list_orders(workspace_id, seller_user_id=seller_id))),
                ("after_sales", "售后处理中", sum(item.status == "requested" for item in self.commerce_repository.list_after_sales(workspace_id, seller_user_id=seller_id))),
            ]
        else:
            applications = center["applications"]
            assert isinstance(applications, list)
            values = [
                (
                    "applications",
                    "身份申请",
                    sum(
                        isinstance(item, dict) and item.get("role") == role.value
                        for item in applications
                    ),
                ),
                ("open_tasks", "当前待办", self._open_task_count(center, role)),
                ("unread", "未读消息", int(summary["unread_notifications"])),
            ]
        return [{"key": key, "label": label, "value": value} for key, label, value in values]

    def _resources(
        self, role: BusinessRole, center: dict[str, object], workspace_id: str
    ) -> list[dict[str, str]]:
        if role is BusinessRole.CREATOR:
            return [
                {
                    "id": item.id,
                    "kind": "creator_project",
                    "title": item.title,
                    "subtitle": "创作项目",
                    "href": "/creator",
                    "status": "saved",
                }
                for item in self.repository.list_projects(workspace_id, limit=5)
            ]
        if role in {BusinessRole.LEARNER, BusinessRole.VIEWER, BusinessRole.BUYER}:
            library = center["library"]
            history = center["history"]
            assert isinstance(library, list) and isinstance(history, list)
            if role is BusinessRole.LEARNER:
                selected = [
                    item
                    for item in library
                    if isinstance(item, dict)
                    and item.get("kind") == LibraryKind.WANT_TO_LEARN.value
                ]
            elif role is BusinessRole.BUYER:
                selected = [
                    item
                    for item in library
                    if isinstance(item, dict) and item.get("kind") == LibraryKind.BOOKMARK.value
                ]
            else:
                selected = [item for item in history if isinstance(item, dict)] + [
                    item for item in library if isinstance(item, dict)
                ]
            return [self._resource_from_item(item) for item in selected[:5]]
        applications = center["applications"]
        assert isinstance(applications, list)
        return [
            {
                "id": str(item["id"]),
                "kind": "role_application",
                "title": f"{ROLE_LABELS[role]}身份申请",
                "subtitle": str(item["status"]),
                "href": "/identity",
                "status": str(item["status"]),
            }
            for item in applications
            if isinstance(item, dict) and item.get("role") == role.value
        ][:5]

    @staticmethod
    def _open_task_count(center: dict[str, object], role: BusinessRole) -> int:
        tasks = center["tasks"]
        assert isinstance(tasks, list)
        return sum(
            isinstance(item, dict)
            and item.get("role") == role.value
            and item.get("status") == "open"
            for item in tasks
        )

    @staticmethod
    def _resource_from_item(item: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(item.get("id", "")),
            "kind": str(item.get("kind", "history")),
            "title": str(item.get("title", "未命名文化资产")),
            "subtitle": "服务端已保存",
            "href": str(item.get("target_href", "")) or "/identity",
            "status": "saved",
        }

"""Application service for durable multi-role identity workflows."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

from haha_identity.domain import (
    APPLICATION_ROLES,
    BASE_ROLES,
    CONSUMER_ROLES,
    CONTROLLED_ROLES,
    PUBLIC_PROFESSIONAL_ROLES,
    SELF_ACTIVATABLE_ROLES,
    BusinessRole,
    IdentityAuditEvent,
    IdentityTask,
    RoleApplication,
    RoleApplicationStatus,
    RoleGrant,
    TaskStatus,
)
from haha_identity.repository import IdentityRepository


class IdentityConflictError(RuntimeError):
    pass


class IdentityPermissionError(RuntimeError):
    pass


class IdentityNotFoundError(RuntimeError):
    pass


ROLE_LABELS = {
    BusinessRole.VIEWER: "浏览者",
    BusinessRole.BUYER: "买家",
    BusinessRole.LEARNER: "学习者",
    BusinessRole.CREATOR: "创作者",
    BusinessRole.CONTRIBUTOR: "知识贡献者",
    BusinessRole.SELLER: "卖家",
    BusinessRole.REVIEWER: "审核员",
    BusinessRole.ADMIN: "管理员",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class IdentityService:
    def __init__(self, repository: IdentityRepository) -> None:
        self.repository = repository

    def bootstrap(self, user_id: str, workspace_id: str) -> dict[str, object]:
        if not self.repository.get_membership_role(user_id, workspace_id):
            raise IdentityPermissionError("当前账户不属于该工作空间")
        profile = self.repository.ensure_user_profile(user_id, workspace_id)
        grants = self.repository.list_role_grants(user_id, workspace_id)
        active_roles = {BusinessRole(item.role) for item in grants if item.status == "active"}
        for role in BASE_ROLES - active_roles:
            self._grant(user_id, workspace_id, role, actor_user_id="system")
        grants = self.repository.list_role_grants(user_id, workspace_id)
        active_values = {item.role for item in grants if item.status == "active"}
        if (
            profile.active_role not in active_values
            or BusinessRole(profile.active_role) not in PUBLIC_PROFESSIONAL_ROLES
        ):
            profile = replace(profile, active_role=BusinessRole.VIEWER.value, updated_at=_now())
            self.repository.save_user_profile(profile)
        return self.snapshot(user_id, workspace_id)

    def snapshot(self, user_id: str, workspace_id: str) -> dict[str, object]:
        profile = self.repository.ensure_user_profile(user_id, workspace_id)
        grants = self.repository.list_role_grants(user_id, workspace_id)
        applications = self.repository.list_role_applications(user_id, workspace_id)
        tasks = self.repository.list_identity_tasks(user_id, workspace_id)
        active_roles = [item.role for item in grants if item.status == "active"]
        return {
            "profile": asdict(profile),
            "roles": [
                {
                    **asdict(item),
                    "label": ROLE_LABELS[BusinessRole(item.role)],
                    "is_active_context": item.role == profile.active_role,
                }
                for item in grants
            ],
            "applications": [asdict(item) for item in applications],
            "tasks": [asdict(item) for item in tasks],
            "available_actions": {
                "self_activate": [role.value for role in sorted(SELF_ACTIVATABLE_ROLES - {BusinessRole(value) for value in active_roles})],
                "apply": [role.value for role in sorted(APPLICATION_ROLES - {BusinessRole(value) for value in active_roles})],
            },
            "consumer_capabilities": [
                role.value for role in sorted(CONSUMER_ROLES)
            ],
            "professional_roles": [
                item.role
                for item in grants
                if item.status == "active"
                and BusinessRole(item.role) in PUBLIC_PROFESSIONAL_ROLES
            ],
        }

    def activate_role(self, user_id: str, workspace_id: str, role_value: str) -> dict[str, object]:
        role = self._parse_role(role_value)
        if role not in SELF_ACTIVATABLE_ROLES:
            raise IdentityPermissionError("该身份不能由用户自行开通")
        if any(
            item.role == role.value and item.status == "active"
            for item in self.repository.list_role_grants(user_id, workspace_id)
        ):
            return self.snapshot(user_id, workspace_id)
        self._grant(user_id, workspace_id, role, actor_user_id=user_id)
        self._create_task(
            user_id,
            workspace_id,
            role,
            kind="onboarding",
            title=f"完成{ROLE_LABELS[role]}工作台设置",
            description="补充资料并完成第一个真实任务；未接入的业务能力会明确标记。",
            target_href="/identity?view=workspace",
        )
        return self.snapshot(user_id, workspace_id)

    def apply_for_role(self, user_id: str, workspace_id: str, role_value: str, reason: str) -> RoleApplication:
        role = self._parse_role(role_value)
        if role in CONTROLLED_ROLES or role not in APPLICATION_ROLES:
            raise IdentityPermissionError("该身份不能通过此申请入口获得")
        if any(item.role == role.value and item.status == "active" for item in self.repository.list_role_grants(user_id, workspace_id)):
            raise IdentityConflictError("该身份已经开通")
        pending = self.repository.find_pending_role_application(user_id, workspace_id, role.value)
        if pending:
            return pending
        now = _now()
        application = RoleApplication(
            id=_id("roleapp"), user_id=user_id, workspace_id=workspace_id,
            role=role.value, status=RoleApplicationStatus.PENDING.value,
            reason=reason.strip(), decision_note="", reviewed_by="",
            created_at=now, updated_at=now,
        )
        self.repository.save_role_application(application)
        self._audit(user_id, workspace_id, user_id, "role.application.created", role, {"application_id": application.id})
        return application

    def decide_application(
        self, application_id: str, actor_user_id: str, decision: str, note: str
    ) -> RoleApplication:
        application = self.repository.get_role_application(application_id)
        if not application:
            raise IdentityNotFoundError("身份申请不存在")
        if application.user_id == actor_user_id:
            raise IdentityPermissionError("不能审核自己的身份申请")
        if decision not in {RoleApplicationStatus.APPROVED.value, RoleApplicationStatus.REJECTED.value}:
            raise ValueError("审核结论无效")
        if application.status != RoleApplicationStatus.PENDING.value:
            if application.status == decision:
                return application
            raise IdentityConflictError("该申请已经完成审核")
        updated = replace(
            application, status=decision, decision_note=note.strip(),
            reviewed_by=actor_user_id, updated_at=_now(),
        )
        self.repository.save_role_application(updated)
        role = BusinessRole(updated.role)
        if decision == RoleApplicationStatus.APPROVED.value:
            self._grant(updated.user_id, updated.workspace_id, role, actor_user_id=actor_user_id)
        self._create_task(
            updated.user_id, updated.workspace_id, role,
            kind="role_application_result",
            title=f"{ROLE_LABELS[role]}身份申请已{'通过' if decision == 'approved' else '驳回'}",
            description=updated.decision_note or "审核结果已记录，可在身份总览查看。",
            target_href="/identity",
        )
        self._audit(updated.user_id, updated.workspace_id, actor_user_id, f"role.application.{decision}", role, {"application_id": updated.id})
        return updated

    def switch_context(self, user_id: str, workspace_id: str, role_value: str) -> dict[str, object]:
        role = self._parse_role(role_value)
        if role in CONSUMER_ROLES:
            raise IdentityPermissionError("浏览、学习和购物是账户默认能力，无需切换身份")
        if role in CONTROLLED_ROLES:
            raise IdentityPermissionError("内部员工权限不能通过公众用户中心切换")
        grants = self.repository.list_role_grants(user_id, workspace_id)
        if not any(item.role == role.value and item.status == "active" for item in grants):
            raise IdentityPermissionError("当前账户未获得该身份授权")
        profile = self.repository.ensure_user_profile(user_id, workspace_id)
        self.repository.save_user_profile(replace(profile, active_role=role.value, updated_at=_now()))
        self._audit(user_id, workspace_id, user_id, "identity.context.switched", role, {})
        return self.snapshot(user_id, workspace_id)

    def complete_task(self, task_id: str, user_id: str, workspace_id: str) -> IdentityTask:
        task = self.repository.get_identity_task(task_id, user_id, workspace_id)
        if not task:
            raise IdentityNotFoundError("任务不存在")
        if task.status == TaskStatus.COMPLETED.value:
            return task
        updated = replace(task, status=TaskStatus.COMPLETED.value, completed_at=_now())
        self.repository.save_identity_task(updated)
        self._audit(user_id, workspace_id, user_id, "identity.task.completed", BusinessRole(task.role), {"task_id": task.id})
        return updated

    def _grant(self, user_id: str, workspace_id: str, role: BusinessRole, actor_user_id: str) -> RoleGrant:
        existing = next((item for item in self.repository.list_role_grants(user_id, workspace_id) if item.role == role.value and item.status == "active"), None)
        if existing:
            return existing
        grant = RoleGrant(
            id=_id("grant"), user_id=user_id, workspace_id=workspace_id,
            role=role.value, status="active", scope_json="{}", granted_by=actor_user_id,
            created_at=_now(), revoked_at="",
        )
        self.repository.save_role_grant(grant)
        self._audit(user_id, workspace_id, actor_user_id, "role.granted", role, {"grant_id": grant.id})
        return grant

    def _create_task(self, user_id: str, workspace_id: str, role: BusinessRole, *, kind: str, title: str, description: str, target_href: str) -> IdentityTask:
        task = IdentityTask(
            id=_id("task"), user_id=user_id, workspace_id=workspace_id,
            role=role.value, kind=kind, title=title, description=description,
            target_href=target_href, status=TaskStatus.OPEN.value,
            created_at=_now(), completed_at="",
        )
        self.repository.save_identity_task(task)
        return task

    def _audit(self, user_id: str, workspace_id: str, actor_user_id: str, event_type: str, role: BusinessRole, detail: dict[str, object]) -> None:
        self.repository.save_identity_audit_event(IdentityAuditEvent(
            id=_id("audit"), user_id=user_id, workspace_id=workspace_id,
            actor_user_id=actor_user_id, event_type=event_type,
            target_role=role.value, detail_json=json.dumps(detail, ensure_ascii=False, sort_keys=True),
            created_at=_now(),
        ))

    @staticmethod
    def _parse_role(value: str) -> BusinessRole:
        try:
            return BusinessRole(value)
        except ValueError as exc:
            raise ValueError("未知业务身份") from exc

"""Independent, deterministic acceptance checks for generated scripts."""

from __future__ import annotations

import re
from dataclasses import asdict

from haha_core.domain import BriefVersion, VerificationIssue, VerificationResult
from haha_media.knowledge import load_heritage_facts
from haha_media.script_writer import ContentScript

_CRITICAL_ATOM_PATTERNS = (
    re.compile(r"(?:世界级|国家级|省级|市级|县级)(?:\+联合国人类非遗)?"),
    re.compile(r"公元前?\s*\d{1,4}\s*年?"),
    re.compile(r"\d{1,2}\s*世纪(?:前后)?"),
    re.compile(r"(?<!\d)\d{3,4}\s*年(?!\d)"),
    re.compile(r"(?:位于|来自|流传于|发源于|起源于)([^，。；！？\n]{2,30})"),
    re.compile(r"([\u4e00-\u9fff·]{2,12})(?:是|为)(?:国家级|省级|市级|县级)?(?:代表性)?传承人"),
)


def _normalized(value: str) -> str:
    return re.sub(r"[\s，。；：、（）()“”‘’·+-]", "", value).lower()


def _critical_atoms(script: ContentScript) -> tuple[str, ...]:
    public_text = "\n".join(
        (script.title, script.hook, *script.voiceover, script.caption, *script.tags)
    )
    atoms: list[str] = []
    for pattern in _CRITICAL_ATOM_PATTERNS:
        for match in pattern.finditer(public_text):
            atom = match.group(1) if match.lastindex else match.group(0)
            if atom.strip():
                atoms.append(atom.strip())
    return tuple(dict.fromkeys(atoms))


def _ungrounded_critical_atoms(script: ContentScript) -> tuple[str, ...]:
    atoms = _critical_atoms(script)
    if not atoms:
        return ()
    allowed_ids = set(script.retrieval_trace.fact_chunks_used) if script.retrieval_trace else set()
    trusted_facts = tuple(fact for fact in load_heritage_facts() if fact.id in allowed_ids)
    trusted_text = _normalized(
        " ".join(
            " ".join(
                (
                    fact.name,
                    fact.category,
                    fact.region,
                    fact.level,
                    fact.summary,
                    fact.history,
                    fact.core_craft,
                    fact.characteristics,
                    fact.representative_bearers,
                    fact.misconceptions,
                    fact.visual_points,
                )
            )
            for fact in trusted_facts
        )
    )
    return tuple(atom for atom in atoms if _normalized(atom) not in trusted_text)


def verify_script(brief: BriefVersion, script: ContentScript) -> VerificationResult:
    issues: list[VerificationIssue] = []
    judgment = dict(script.judgment)
    expected_spec = f"{brief.duration} · {brief.aspect_ratio}"
    checks = (
        (judgment.get("推荐平台") == brief.platform, "platform_mismatch", "platform", "生成平台与参数版本不一致"),
        (judgment.get("推荐规格") == expected_spec, "spec_mismatch", "duration", "生成规格与参数版本不一致"),
        (judgment.get("表达气质") == brief.tone, "tone_mismatch", "tone", "表达气质与参数版本不一致"),
    )
    for passed, code, field, message in checks:
        if not passed:
            issues.append(VerificationIssue(code, field, message))
    required = {
        "title": script.title,
        "hook": script.hook,
        "voiceover": script.voiceover,
        "shots": script.shots,
        "caption": script.caption,
        "tags": script.tags,
    }
    for field, value in required.items():
        if not value:
            issues.append(VerificationIssue("missing_field", field, f"必需字段 {field} 为空"))
    duration_match = re.search(r"\d+", brief.duration)
    final_match = re.search(r"[–-](\d+)\s*秒", script.shots[-1]) if script.shots else None
    if duration_match and (not final_match or final_match.group(1) != duration_match.group()):
        issues.append(VerificationIssue("timeline_mismatch", "shots", "分镜终点与目标时长不一致"))
    if not script.retrieval_trace:
        issues.append(VerificationIssue("missing_evidence", "retrieval_trace", "缺少检索证据"))
    ungrounded_atoms = _ungrounded_critical_atoms(script)
    if ungrounded_atoms:
        issues.append(
            VerificationIssue(
                "ungrounded_fact",
                "content",
                f"关键事实缺少已检索来源支持：{'、'.join(ungrounded_atoms)}",
            )
        )
    return VerificationResult(not issues, tuple(issues))


def verification_to_dict(result: VerificationResult) -> dict[str, object]:
    return {
        "passed": result.passed,
        "issues": [asdict(issue) for issue in result.issues],
        "checked_at": result.checked_at,
    }

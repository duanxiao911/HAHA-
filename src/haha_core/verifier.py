"""Independent, deterministic acceptance checks for generated scripts."""

from __future__ import annotations

import re
from dataclasses import asdict

from haha_core.domain import BriefVersion, VerificationIssue, VerificationResult
from haha_media.script_writer import ContentScript


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
    return VerificationResult(not issues, tuple(issues))


def verification_to_dict(result: VerificationResult) -> dict[str, object]:
    return {
        "passed": result.passed,
        "issues": [asdict(issue) for issue in result.issues],
        "checked_at": result.checked_at,
    }

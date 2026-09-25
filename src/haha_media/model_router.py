"""Provider-neutral routing for HAHA text and image model calls."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

TaskType = Literal["creation_judgement", "master_script", "storyboard", "publish_pack", "image"]


class ModelCallError(RuntimeError):
    """A sanitized provider error safe to display in the application."""

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        evidence: CallEvidence | None = None,
    ) -> None:
        super().__init__(message)
        self.detail = detail or message
        self.evidence = evidence
        self.retrieval_trace = None


@dataclass(frozen=True, slots=True)
class CallEvidence:
    provider: str
    model: str
    request_id: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    status: str = "completed"


@dataclass(frozen=True, slots=True)
class TextModelResult:
    data: dict[str, Any]
    evidence: CallEvidence


@dataclass(frozen=True, slots=True)
class ImageModelResult:
    images: tuple[str, ...]
    evidence: CallEvidence


@dataclass(frozen=True, slots=True)
class RouterStatus:
    text_ready: bool
    image_ready: bool
    text_model: str
    image_model: str


class ModelRouter:
    """Route creative tasks without exposing provider details to business code."""

    TEXT_TASKS = frozenset({"creation_judgement", "master_script", "storyboard", "publish_pack"})

    def __init__(self) -> None:
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.deepseek_base_url = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ).rstrip("/")
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
        self.ark_api_key = os.getenv("ARK_API_KEY", os.getenv("LAS_API_KEY", "")).strip()
        self.seedream_base_url = os.getenv(
            "SEEDREAM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        ).rstrip("/")
        self.seedream_model = os.getenv("SEEDREAM_MODEL", "doubao-seedream-4.5").strip()
        self.timeout = float(os.getenv("MODEL_API_TIMEOUT", "120"))

    def status(self) -> RouterStatus:
        return RouterStatus(
            text_ready=bool(self.deepseek_api_key),
            image_ready=bool(self.ark_api_key),
            text_model=self.deepseek_model,
            image_model=self.seedream_model,
        )

    def resolve_text_mode(self, preference: str) -> Literal["deepseek", "local"]:
        """Resolve the UI preference to a usable text-generation route."""
        if preference == "本地演示":
            return "local"
        if preference == "DeepSeek":
            if not self.deepseek_api_key:
                raise ModelCallError("尚未配置 DEEPSEEK_API_KEY，无法使用 DeepSeek。")
            return "deepseek"
        if preference == "自动选择":
            return "deepseek" if self.deepseek_api_key else "local"
        raise ValueError(f"不支持的模型选择：{preference}")

    def generate_json(
        self,
        task: TaskType,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> TextModelResult:
        if task not in self.TEXT_TASKS:
            raise ValueError(f"任务 {task!r} 不是文本生成任务。")
        if not self.deepseek_api_key:
            raise ModelCallError("尚未配置 DEEPSEEK_API_KEY。")
        payload = {
            "model": self.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        response, headers, latency = self._post_json(
            f"{self.deepseek_base_url}/chat/completions",
            self.deepseek_api_key,
            payload,
            provider="deepseek",
            model=self.deepseek_model,
        )
        usage = response.get("usage", {})
        evidence = CallEvidence(
            provider="deepseek",
            model=str(response.get("model", self.deepseek_model)),
            request_id=str(response.get("id") or headers.get("x-request-id", "")),
            latency_ms=latency,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )
        try:
            choice = response["choices"][0]
            content = choice["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            finish_reason = response.get("choices", [{}])[0].get("finish_reason", "unknown")
            raise ModelCallError(
                f"DeepSeek 返回了无法解析的结构化结果（finish_reason={finish_reason}）。",
                detail=f"Invalid structured response: {exc}; finish_reason={finish_reason}",
                evidence=CallEvidence(
                    evidence.provider,
                    evidence.model,
                    evidence.request_id,
                    evidence.latency_ms,
                    evidence.input_tokens,
                    evidence.output_tokens,
                    status="failed",
                ),
            ) from exc
        return TextModelResult(data=data, evidence=evidence)

    def generate_image(
        self,
        prompt: str,
        *,
        reference_images: tuple[str, ...] = (),
        size: str = "2K",
        count: int = 1,
        watermark: bool = True,
    ) -> ImageModelResult:
        if not self.ark_api_key:
            raise ModelCallError("尚未配置 ARK_API_KEY（也兼容 LAS_API_KEY）。")
        if not prompt.strip():
            raise ValueError("生图提示词不能为空。")
        payload: dict[str, Any] = {
            "model": self.seedream_model,
            "prompt": prompt,
            "size": size,
            "response_format": "url",
            "watermark": watermark,
            "stream": False,
            "sequential_image_generation": "auto" if count > 1 else "disabled",
        }
        if reference_images:
            payload["image"] = list(reference_images) if len(reference_images) > 1 else reference_images[0]
        if count > 1:
            payload["sequential_image_generation_options"] = {"max_images": min(count, 15)}
        response, headers, latency = self._post_json(
            f"{self.seedream_base_url}/images/generations",
            self.ark_api_key,
            payload,
            provider="volcengine",
            model=self.seedream_model,
        )
        images = tuple(
            str(item["url"])
            for item in response.get("data", ())
            if isinstance(item, dict) and item.get("url")
        )
        if not images:
            raise ModelCallError("Seedream 调用成功，但没有返回图片地址。")
        usage = response.get("usage", {})
        evidence = CallEvidence(
            provider="volcengine",
            model=str(response.get("model", self.seedream_model)),
            request_id=str(response.get("id") or headers.get("x-request-id", "")),
            latency_ms=latency,
            output_tokens=int(usage.get("output_tokens", 0)),
        )
        return ImageModelResult(images=images, evidence=evidence)

    def _post_json(
        self,
        url: str,
        api_key: str,
        payload: dict[str, Any],
        *,
        provider: str,
        model: str,
    ) -> tuple[dict[str, Any], dict[str, str], int]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
                headers = {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as exc:
            latency = round((time.perf_counter() - started) * 1000)
            headers = {key.lower(): value for key, value in (exc.headers or {}).items()}
            detail = exc.read().decode("utf-8", errors="replace")
            detail = detail.replace(api_key, "[REDACTED]") if api_key else detail
            evidence = CallEvidence(
                provider, model, headers.get("x-request-id", ""), latency, status="failed"
            )
            raise ModelCallError(
                f"模型服务返回 HTTP {exc.code}。",
                detail=f"HTTP {exc.code}: {detail or exc.reason}",
                evidence=evidence,
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            latency = round((time.perf_counter() - started) * 1000)
            reason = getattr(exc, "reason", exc)
            detail = f"{type(exc).__name__}: {reason}"
            detail = detail.replace(api_key, "[REDACTED]") if api_key else detail
            raise ModelCallError(
                "模型服务连接失败或超时，请检查网络与 API 配置。",
                detail=detail,
                evidence=CallEvidence(provider, model, "", latency, status="failed"),
            ) from exc
        latency = round((time.perf_counter() - started) * 1000)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            detail = f"Invalid JSON response: {exc}; body={raw[:1000]}"
            detail = detail.replace(api_key, "[REDACTED]") if api_key else detail
            raise ModelCallError(
                "模型服务返回了无效 JSON。",
                detail=detail,
                evidence=CallEvidence(
                    provider, model, headers.get("x-request-id", ""), latency, status="failed"
                ),
            ) from exc
        if not isinstance(parsed, dict):
            raise ModelCallError(
                "模型服务返回格式不正确。",
                detail=f"Expected a JSON object, got {type(parsed).__name__}.",
                evidence=CallEvidence(
                    provider, model, headers.get("x-request-id", ""), latency, status="failed"
                ),
            )
        return parsed, headers, latency


def get_model_router() -> ModelRouter:
    """Factory used by application code and future provider substitutions."""
    return ModelRouter()

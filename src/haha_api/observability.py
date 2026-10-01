"""Small dependency-free structured logging and metrics boundary."""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_context: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", record.getMessage()),
            "component": getattr(record, "component", "api"),
            "request_id": getattr(record, "request_id", "") or request_id_context.get(),
        }
        fields = getattr(record, "fields", {})
        if isinstance(fields, dict):
            payload.update({key: value for key, value in fields.items() if value not in {None, ""}})
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("haha")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = configure_logging()


def log_event(event: str, *, component: str = "api", **fields: object) -> None:
    logger.info(event, extra={"event": event, "component": component, "fields": fields})


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def add(self, name: str, value: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += value

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            values = sorted(self._counters.items())
        for (name, labels), value in values:
            label_text = ""
            if labels:
                escaped = [f'{key}="{item.replace(chr(34), chr(92) + chr(34))}"' for key, item in labels]
                label_text = "{" + ",".join(escaped) + "}"
            lines.append(f"{name}{label_text} {value:g}")
        return "\n".join(lines) + "\n"


metrics = Metrics()

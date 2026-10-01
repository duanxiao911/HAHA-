"""SQLite persistence for local creator projects and conversation history."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from haha_media.knowledge import RetrievalTrace
from haha_media.model_router import CallEvidence
from haha_media.script_writer import ContentBrief, ContentScript

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "haha_projects.db"


def _db_path() -> Path:
    configured = os.getenv("HAHA_PROJECT_DB", "").strip()
    return Path(configured) if configured else DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_projects (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            brief_json TEXT NOT NULL,
            script_json TEXT NOT NULL,
            messages_json TEXT NOT NULL,
            run_json TEXT NOT NULL,
            model_choice TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return connection


def save_project(
    *,
    project_id: str | None,
    brief: ContentBrief,
    script: ContentScript,
    messages: list[dict[str, str]],
    run_attempt: dict[str, object] | None,
    model_choice: str,
) -> str:
    project_id = project_id or uuid4().hex
    updated_at = datetime.now(UTC).isoformat(timespec="seconds")
    payload = (
        project_id,
        script.title,
        json.dumps(asdict(brief), ensure_ascii=False),
        json.dumps(asdict(script), ensure_ascii=False),
        json.dumps(messages, ensure_ascii=False),
        json.dumps(run_attempt or {}, ensure_ascii=False),
        model_choice,
        updated_at,
    )
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO creator_projects
                (id, title, brief_json, script_json, messages_json, run_json, model_choice, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                brief_json=excluded.brief_json,
                script_json=excluded.script_json,
                messages_json=excluded.messages_json,
                run_json=excluded.run_json,
                model_choice=excluded.model_choice,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        connection.commit()
    return project_id


def list_projects(limit: int = 30) -> list[dict[str, str]]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT id, title, model_choice, updated_at FROM creator_projects ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def load_project(project_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM creator_projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None:
        return None
    brief_data = json.loads(row["brief_json"])
    script_data = json.loads(row["script_json"])
    trace_data = script_data.pop("retrieval_trace", None)
    evidence_data = script_data.pop("model_evidence", None)
    tuple_fields = (
        "voiceover",
        "shots",
        "tags",
        "titles",
        "covers",
        "interactions",
        "sources",
        "fact_checks",
    )
    nested_tuple_fields = (
        "judgment",
        "storyboard",
        "audits",
        "operation_scores",
        "method_sources",
        "strategy_sources",
        "fact_sources",
    )
    for key in tuple_fields:
        script_data[key] = tuple(script_data.get(key, ()))
    for key in nested_tuple_fields:
        script_data[key] = tuple(tuple(item) for item in script_data.get(key, ()))
    if trace_data:
        for key in ("creative_chunks_used", "operation_chunks_used", "fact_chunks_used"):
            trace_data[key] = tuple(trace_data.get(key, ()))
        trace_data["rerank_scores"] = tuple(
            tuple(item) for item in trace_data.get("rerank_scores", ())
        )
    return {
        "project_id": row["id"],
        "brief": ContentBrief(**brief_data),
        "script": ContentScript(
            **script_data,
            retrieval_trace=RetrievalTrace(**trace_data) if trace_data else None,
            model_evidence=CallEvidence(**evidence_data) if evidence_data else None,
        ),
        "messages": json.loads(row["messages_json"]),
        "run_attempt": json.loads(row["run_json"]),
        "model_choice": row["model_choice"],
        "updated_at": row["updated_at"],
    }

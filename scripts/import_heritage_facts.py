"""Import the reviewed heritage fact catalogue from its Word delivery file."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from docx import Document

FIELDS = (
    "name",
    "category",
    "region",
    "level",
    "summary",
    "history",
    "core_craft",
    "characteristics",
    "representative_bearers",
    "misconceptions",
    "visual_points",
    "authority",
    "source_url",
    "material_year",
    "review_status",
)


def parse_records(source: Path) -> list[dict[str, str]]:
    paragraphs = [p.text.strip() for p in Document(source).paragraphs if p.text.strip()]
    body = paragraphs[7:]
    records: list[dict[str, str]] = []
    buffer = ""
    for paragraph in body:
        if not buffer:
            buffer = paragraph
        elif buffer.endswith(",") or paragraph.startswith(","):
            buffer += paragraph
        else:
            buffer += "," + paragraph
        row = next(csv.reader([buffer]))
        if len(row) < len(FIELDS):
            continue
        if len(row) != len(FIELDS):
            raise ValueError(f"Unexpected column count {len(row)} near {row[0]!r}")
        record = dict(zip(FIELDS, (value.strip() for value in row), strict=True))
        record["id"] = f"F-{len(records) + 1:03d}"
        record["source_document"] = source.name
        records.append(record)
        buffer = ""
    if buffer:
        raise ValueError("Trailing incomplete record in source document")
    if len(records) != 164:
        raise ValueError(f"Expected 164 reviewed records, got {len(records)}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    records = parse_records(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_document": args.source.name,
                "record_count": len(records),
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Imported {len(records)} records into {args.output}")


if __name__ == "__main__":
    main()

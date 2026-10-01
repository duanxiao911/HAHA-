"""Safe, dependency-light extraction for creator reference assets."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True, slots=True)
class ExtractedAsset:
    name: str
    context: str
    status: str


def extract_asset(name: str, data: bytes, *, max_chars: int = 12_000) -> ExtractedAsset:
    suffix = Path(name).suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            text = data.decode("utf-8-sig", errors="replace")
        elif suffix == ".docx":
            text = _extract_docx(data)
        elif suffix == ".pdf":
            return ExtractedAsset(name, "", "PDF 解析组件未安装，暂未进入模型上下文")
        elif suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return ExtractedAsset(name, "", "图片已挂载；当前文本模型不读取图片内容")
        else:
            return ExtractedAsset(name, "", "不支持的文件类型")
    except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError):
        return ExtractedAsset(name, "", "文件解析失败")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        return ExtractedAsset(name, "", "没有提取到正文")
    clipped = text[:max_chars]
    status = "正文已进入模型上下文"
    if len(text) > max_chars:
        status += f"（截取前 {max_chars} 字）"
    return ExtractedAsset(name, clipped, status)


def build_asset_context(assets: list[ExtractedAsset], *, max_chars: int = 24_000) -> str:
    sections = [f"文件：{asset.name}\n{asset.context}" for asset in assets if asset.context]
    return "\n\n---\n\n".join(sections)[:max_chars]


def _extract_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document = archive.read("word/document.xml")
    root = ElementTree.fromstring(document)
    paragraphs: list[str] = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        text = "".join(
            node.text or ""
            for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        )
        if text.strip():
            paragraphs.append(text.strip())
    return "\n".join(paragraphs)

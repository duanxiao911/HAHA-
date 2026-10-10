"""Safe, dependency-light extraction for creator reference assets."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.parsers import expat

MAX_DOCX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_DOCX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_DOCX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
DOCX_READ_CHUNK_BYTES = 64 * 1024


class AssetSecurityError(ValueError):
    """The uploaded asset violates a deterministic security boundary."""


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
    except AssetSecurityError:
        return ExtractedAsset(name, "", "文件被安全策略拒绝")
    except (
        OSError,
        ValueError,
        zipfile.BadZipFile,
        expat.ExpatError,
    ):
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
    if len(data) > MAX_DOCX_ARCHIVE_BYTES:
        raise AssetSecurityError("DOCX archive exceeds compressed size limit")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        documents = [info for info in infos if info.filename == "word/document.xml"]
        if len(documents) != 1:
            raise AssetSecurityError("DOCX must contain exactly one word/document.xml")
        total_uncompressed = 0
        for info in infos:
            if info.flag_bits & 0x1:
                raise AssetSecurityError("Encrypted DOCX entries are not accepted")
            if info.file_size > MAX_DOCX_ENTRY_BYTES:
                raise AssetSecurityError("DOCX entry exceeds size limit")
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES:
                raise AssetSecurityError("DOCX uncompressed total exceeds budget")
            if info.file_size:
                ratio = info.file_size / max(1, info.compress_size)
                if ratio > MAX_DOCX_COMPRESSION_RATIO:
                    raise AssetSecurityError("DOCX entry compression ratio exceeds limit")

        document_info = documents[0]
        if document_info.file_size > MAX_DOCX_DOCUMENT_BYTES:
            raise AssetSecurityError("word/document.xml exceeds size limit")
        chunks: list[bytes] = []
        bytes_read = 0
        with archive.open(document_info, "r") as source:
            while chunk := source.read(DOCX_READ_CHUNK_BYTES):
                bytes_read += len(chunk)
                if bytes_read > MAX_DOCX_DOCUMENT_BYTES:
                    raise AssetSecurityError("word/document.xml exceeded streaming limit")
                chunks.append(chunk)
        if bytes_read != document_info.file_size:
            raise AssetSecurityError("word/document.xml size does not match ZIP metadata")
        document = b"".join(chunks)
    return _parse_docx_xml(document)


def _parse_docx_xml(document: bytes) -> str:
    """Extract Word paragraphs with DTDs and every entity mechanism disabled."""
    paragraphs: list[str] = []
    paragraph_parts: list[str] | None = None
    inside_text = False
    parser = expat.ParserCreate(namespace_separator="}")

    def reject_markup(*_args: object) -> None:
        raise AssetSecurityError("DTD and entity declarations are not accepted")

    def start_element(name: str, _attributes: dict[str, str]) -> None:
        nonlocal paragraph_parts, inside_text
        local_name = name.rsplit("}", 1)[-1]
        if local_name == "p":
            paragraph_parts = []
        elif local_name == "t" and paragraph_parts is not None:
            inside_text = True

    def end_element(name: str) -> None:
        nonlocal paragraph_parts, inside_text
        local_name = name.rsplit("}", 1)[-1]
        if local_name == "t":
            inside_text = False
        elif local_name == "p" and paragraph_parts is not None:
            text = "".join(paragraph_parts).strip()
            if text:
                paragraphs.append(text)
            paragraph_parts = None

    def character_data(value: str) -> None:
        if inside_text and paragraph_parts is not None:
            paragraph_parts.append(value)

    parser.StartDoctypeDeclHandler = reject_markup
    parser.EntityDeclHandler = reject_markup
    parser.ExternalEntityRefHandler = reject_markup
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = character_data
    parser.Parse(document, True)
    return "\n".join(paragraphs)

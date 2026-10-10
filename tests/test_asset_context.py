import io
import zipfile

import haha_media.asset_context as asset_context_module
from haha_media.asset_context import build_asset_context, extract_asset


def test_text_asset_enters_context() -> None:
    asset = extract_asset("notes.md", "剪纸以红纸和剪刀为主要画面。".encode())

    assert "进入模型上下文" in asset.status
    assert "剪纸" in build_asset_context([asset])


def test_docx_asset_is_extracted_without_optional_dependency() -> None:
    buffer = io.BytesIO()
    xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>龙泉青瓷参考资料</w:t></w:r></w:p></w:body>
    </w:document>'''.encode()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)

    asset = extract_asset("facts.docx", buffer.getvalue())

    assert asset.context == "龙泉青瓷参考资料"


def _docx(document_xml: bytes, *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_docx_xml_entities_are_rejected_before_expansion() -> None:
    xml = b'''<?xml version="1.0"?>
    <!DOCTYPE w:document [
      <!ENTITY a "1234567890">
      <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
    ]>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body>
    </w:document>'''

    asset = extract_asset("entity-bomb.docx", _docx(xml))

    assert asset.context == ""
    assert asset.status == "文件被安全策略拒绝"


def test_docx_high_compression_ratio_is_rejected() -> None:
    asset = extract_asset("zip-bomb.docx", _docx(b"0" * (1024 * 1024)))

    assert asset.context == ""
    assert asset.status == "文件被安全策略拒绝"


def test_docx_document_entry_is_checked_before_streaming(
    monkeypatch,
) -> None:
    monkeypatch.setattr(asset_context_module, "MAX_DOCX_DOCUMENT_BYTES", 64)
    xml = b"<document>" + b"x" * 100 + b"</document>"

    asset = extract_asset(
        "oversized-document.docx", _docx(xml, compression=zipfile.ZIP_STORED)
    )

    assert asset.context == ""
    assert asset.status == "文件被安全策略拒绝"


def test_docx_total_uncompressed_budget_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(asset_context_module, "MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES", 200)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", b"<document />")
        archive.writestr("word/media/payload.bin", b"x" * 256)

    asset = extract_asset("oversized-total.docx", buffer.getvalue())

    assert asset.context == ""
    assert asset.status == "文件被安全策略拒绝"

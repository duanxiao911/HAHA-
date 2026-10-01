import io
import zipfile

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

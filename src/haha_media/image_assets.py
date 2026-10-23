"""Controlled download and deterministic validation for generated images."""

from __future__ import annotations

import hashlib
import os
import struct
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError


class ImageAssetError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    data: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    sha256: str
    source_host: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _allowed_host(host: str) -> bool:
    configured = os.getenv(
        "HAHA_IMAGE_DOWNLOAD_HOSTS",
        ".volces.com,.volccdn.com,.byteimg.com",
    )
    rules = tuple(item.strip().lower() for item in configured.split(",") if item.strip())
    host = host.lower().rstrip(".")
    return any(host == rule or (rule.startswith(".") and host.endswith(rule)) for rule in rules)


def _dimensions(data: bytes) -> tuple[str, str, int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", ".png", width, height
    if data.startswith(b"\xff\xd8\xff"):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset : offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                return "image/jpeg", ".jpg", width, height
            offset += length
    raise ImageAssetError("模型结果不是可解码的 PNG 或 JPEG 图片")


def validate_image_bytes(data: bytes, *, source_host: str = "provider") -> ValidatedImage:
    if not data or len(data) > 20 * 1024 * 1024:
        raise ImageAssetError("图片为空或超过 20 MB 限制")
    mime_type, extension, width, height = _dimensions(data)
    try:
        with Image.open(BytesIO(data)) as decoded:
            decoded.verify()
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()
            if decoded.size != (width, height) or decoded.format not in {"PNG", "JPEG"}:
                raise ImageAssetError("图片解码结果与文件签名不一致")
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageAssetError("图片数据无法完整解码") from exc
    if width < 64 or height < 64 or width * height > 40_000_000:
        raise ImageAssetError("图片尺寸不在允许范围内")
    return ValidatedImage(
        data=data,
        mime_type=mime_type,
        extension=extension,
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
        source_host=source_host,
    )


def download_generated_image(url: str, *, timeout: float = 30.0) -> ValidatedImage:
    opener = urllib.request.build_opener(_NoRedirect())
    current = url
    for _ in range(4):
        parsed = urllib.parse.urlsplit(current)
        if parsed.scheme != "https" or not parsed.hostname or not _allowed_host(parsed.hostname):
            raise ImageAssetError("图片下载地址不在受控 HTTPS 域名范围内")
        request = urllib.request.Request(current, headers={"Accept": "image/png,image/jpeg"})
        try:
            with opener.open(request, timeout=timeout) as response:  # noqa: S310
                declared = response.headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > 20 * 1024 * 1024:
                    raise ImageAssetError("图片响应超过 20 MB 限制")
                data = response.read(20 * 1024 * 1024 + 1)
                return validate_image_bytes(data, source_host=parsed.hostname)
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location", "")
                if not location:
                    raise ImageAssetError("图片重定向缺少目标地址") from exc
                current = urllib.parse.urljoin(current, location)
                continue
            raise ImageAssetError(f"图片下载失败（HTTP {exc.code}）") from exc
        except urllib.error.URLError as exc:
            raise ImageAssetError("图片下载网络失败") from exc
    raise ImageAssetError("图片下载重定向次数过多")

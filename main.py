"""Civitai media downloader plugin for AstrBot."""

from __future__ import annotations

import asyncio
import mimetypes
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image, Video


URL_PATTERN = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
IMAGE_SUFFIXES = {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_SUFFIXES = {".m4v", ".mkv", ".mov", ".mp4", ".webm"}
MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 90


class DownloadError(Exception):
    """A download error that can be shown to the chat user."""


def _extract_url(raw_value: str) -> str:
    """Extract a URL from command arguments or a formatted chat message."""
    value = urllib.parse.unquote(raw_value.strip())
    match = URL_PATTERN.search(value)
    if not match:
        raise DownloadError("消息中没有可下载的 HTTPS 链接。")
    return match.group(0).rstrip(".,;:!?)]}，。；：！？")


def _is_civitai_host(hostname: str | None) -> bool:
    return bool(hostname) and (hostname == "civitai.red" or hostname.endswith(".civitai.com"))


def _validate_url(raw_url: str) -> str:
    url = _extract_url(raw_url)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not _is_civitai_host(parsed.hostname):
        raise DownloadError("仅支持 Civitai 的 HTTPS 媒体链接。")
    if parsed.username or parsed.password:
        raise DownloadError("链接格式无效。")
    return url


def _extension(url: str, content_type: str | None) -> str:
    if content_type:
        detected = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if detected in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
            return detected
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
        return suffix
    return ".bin"


def _download_sync(url: str, target_dir: Path) -> tuple[Path, str, str]:
    """Download one allowed media URL without loading its body into memory."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AstrBot-CivitaiDownloader/1.0", "Accept": "image/*,video/*;q=0.9,*/*;q=0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            _validate_url(final_url)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
                raise DownloadError("文件超过 150 MB 下载上限。")

            content_type = response.headers.get_content_type()
            suffix = _extension(final_url, content_type)
            if suffix not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
                raise DownloadError("该链接不是支持的图片或视频格式。")

            destination = target_dir / f"civitai_{uuid.uuid4().hex}{suffix}"
            total = 0
            with destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        destination.unlink(missing_ok=True)
                        raise DownloadError("文件超过 150 MB 下载上限。")
                    output.write(chunk)
            return destination, content_type, final_url
    except DownloadError:
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise DownloadError(f"下载失败：{exc}") from exc


@star.register("astrbot_plugin_civitai_downloader", "jun23", "下载 Civitai 图片和视频链接", "1.0.2")
class CivitaiDownloaderPlugin(star.Star):
    """Download media from Civitai CDN and send it back as a media message."""

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self.download_dir = Path(tempfile.gettempdir()) / "astrbot_civitai_downloader"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    async def _handle_url(self, event: AstrMessageEvent, raw_url: str) -> None:
        try:
            url = _validate_url(raw_url)
            path, content_type, final_url = await asyncio.to_thread(
                _download_sync, url, self.download_dir
            )
        except DownloadError as exc:
            event.set_result(event.plain_result(str(exc)))
            return

        is_video = path.suffix.lower() in VIDEO_SUFFIXES or content_type.startswith("video/")
        if is_video:
            # OneBot/NapCat commonly runs in a different container from AstrBot.
            # It cannot read AstrBot's /tmp path, but it can fetch the HTTPS URL itself.
            component = Video.fromURL(final_url)
            path.unlink(missing_ok=True)
        else:
            component = Image.fromFileSystem(path)
        event.set_result(event.chain_result([component]))

    @filter.command("civitai下载")
    async def download_command(self, event: AstrMessageEvent, url: str) -> None:
        """下载 Civitai 媒体：/civitai下载 <URL>。"""
        await self._handle_url(event, url)

    @filter.regex(r"https://(?:image\.civitai\.com|civitai\.red)/\S+", priority=100)
    async def download_from_message(self, event: AstrMessageEvent) -> None:
        """自动下载消息中的第一个 Civitai 媒体链接。"""
        message = event.message_str
        if message.lstrip().startswith("/civitai下载"):
            return
        match = URL_PATTERN.search(message)
        if match:
            await self._handle_url(event, match.group(0))

    async def terminate(self) -> None:
        """Remove media files created by this plugin on shutdown."""
        await asyncio.to_thread(shutil.rmtree, self.download_dir, True)

"""
麦麦!来点二次元图片! — MaiBot 插件
==================================

基于 Lolicon API v2 (api.lolicon.app) 的 Pixiv 随机图片爬取插件。

功能：
1. 定时通过 Lolicon API 拉取指定标签的随机 Pixiv 图片
2. 被 @ 问到涩图（或用户指定关键词）时发送未发过的图片
3. 发过的图片不重复，支持年龄分级、AI排除、总量控制、@模式

依赖：httpx + Pillow
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from maibot_sdk import CONFIG_RELOAD_SCOPE_SELF, Command, MaiBotPlugin, Tool
from .config import CONFIG_SCHEMA_VERSION, PixivCrawlerConfig

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# ═══════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════

SENT_TRACKING_FILE = "sent_images.json"
LOLICON_API = "https://api.lolicon.app/setu/v2"

AGE_R18_MAP: dict[str, int] = {
    "safe": 0,
    "all": 2,
    "r18": 1,
}

VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


# ═══════════════════════════════════════════════════════════════════════
# 主插件类
# ═══════════════════════════════════════════════════════════════════════


class PixivCrawlerPlugin(MaiBotPlugin):
    config_model = PixivCrawlerConfig

    def __init__(self) -> None:
        super().__init__()
        self._crawl_task: asyncio.Task | None = None
        self._running = True
        self._sent_files: set[str] = set()
        self._image_urls: dict[str, str] = {}
        self._sent_path: str = ""
        self._image_root: str = ""
        self._last_cmd_time: float = 0.0
        self._crawling_now: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def on_load(self) -> None:
        self.ctx.logger.info("[SetuPlugin] 插件已加载 (v%s, Lolicon API)", CONFIG_SCHEMA_VERSION)
        if not self.config.plugin.enabled:
            self.ctx.logger.info("[SetuPlugin] 总开关已关闭，跳过初始化")
            return
        if not HAS_HTTPX:
            self.ctx.logger.error("[SetuPlugin] httpx 未安装，插件无法运行！")

        plugin_dir = Path(__file__).parent.resolve()
        self._image_root = str(plugin_dir / self.config.storage.image_dir)
        self._sent_path = str(plugin_dir / SENT_TRACKING_FILE)

        self._ensure_dirs()
        self._load_sent_tracking()
        
        # 清理无效的 URL 映射
        cleaned = self._cleanup_invalid_urls()
        if cleaned > 0:
            self.ctx.logger.info("[SetuPlugin] 清理了 %d 条无效 URL 映射", cleaned)
            self._save_sent_tracking()

        if self.config.schedule.enabled:
            self._crawl_task = asyncio.create_task(self._crawl_loop())
            self.ctx.logger.info("[SetuPlugin] 定时爬取已启动: %s", self.config.schedule.times)

    async def on_unload(self) -> None:
        self._running = False
        if self._crawl_task:
            self._crawl_task.cancel()
            try: await self._crawl_task
            except asyncio.CancelledError: pass
            self._crawl_task = None
        self._save_sent_tracking()
        self.ctx.logger.info("[SetuPlugin] 插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        if scope != CONFIG_RELOAD_SCOPE_SELF:
            return
        self.ctx.logger.info("[SetuPlugin] 配置已更新, v=%s", version)
        if not self.config.plugin.enabled:
            if self._crawl_task:
                self._crawl_task.cancel()
                try: await self._crawl_task
                except asyncio.CancelledError: pass
                self._crawl_task = None
            return
        plugin_dir = Path(__file__).parent.resolve()
        if not self._image_root:
            self._image_root = str(plugin_dir / self.config.storage.image_dir)
            self._sent_path = str(plugin_dir / SENT_TRACKING_FILE)
            self._ensure_dirs()
            self._load_sent_tracking()
        new_root = str(plugin_dir / self.config.storage.image_dir)
        if new_root != self._image_root:
            self._image_root = new_root
            self._ensure_dirs()
        if self._crawl_task:
            self._crawl_task.cancel()
            try: await self._crawl_task
            except asyncio.CancelledError: pass
        if self.config.schedule.enabled:
            self._crawl_task = asyncio.create_task(self._crawl_loop())
            self.ctx.logger.info("[SetuPlugin] 定时任务已重启: %s", self.config.schedule.times)
        else:
            self._crawl_task = None

    # ── 目录 & 追踪 ────────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        os.makedirs(self._image_root, exist_ok=True)

    def _load_sent_tracking(self) -> None:
        try:
            with open(self._sent_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._sent_files = {PurePosixPath(p).as_posix() for p in data.get("sent", [])}
                self._image_urls = {PurePosixPath(k).as_posix(): v for k, v in data.get("urls", {}).items()}
        except (FileNotFoundError, json.JSONDecodeError):
            self._sent_files = set()
            self._image_urls = {}

    def _save_sent_tracking(self) -> None:
        try:
            normalized_sent = sorted(PurePosixPath(p).as_posix() for p in self._sent_files)
            normalized_urls = {PurePosixPath(k).as_posix(): v for k, v in self._image_urls.items()}
            with open(self._sent_path, "w", encoding="utf-8") as f:
                json.dump({"sent": normalized_sent, "urls": normalized_urls}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.ctx.logger.error("[SetuPlugin] 保存发送记录失败: %s", e)

    def _proxy_url(self) -> str | None:
        if self.config.proxy.enabled and self.config.proxy.url:
            return self.config.proxy.url
        return None

    # ── 爬取 ───────────────────────────────────────────────────────────

    async def _crawl_loop(self) -> None:
        while self._running:
            try:
                now = datetime.now()
                if now.strftime("%H:%M") in self.config.schedule.times:
                    self.ctx.logger.info("[SetuPlugin] 定时爬取触发: %s", now.strftime("%H:%M"))
                    await self._execute_full_crawl()
                    await asyncio.sleep(61)
                else:
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.ctx.logger.error("[SetuPlugin] 爬取循环异常: %s", e)
                await asyncio.sleep(60)

    def _get_templates(self) -> list[list[str]]:
        """获取标签模板列表，优先 tag_templates，fallback 到旧版 tags。"""
        if self.config.api.tag_templates and len(self.config.api.tag_templates) > 0:
            return [
                [t.strip() for t in tmpl.split(",") if t.strip()]
                for tmpl in self.config.api.tag_templates
                if tmpl.strip()
            ]
        # 向后兼容：旧版 tags → 每个 tag 包装成单元素模板
        legacy_tags = [t.strip() for t in self.config.api.tags if t.strip()]
        if legacy_tags:
            return [[t] for t in legacy_tags]
        return []

    async def _execute_full_crawl(self, per_tag_count: int | None = None) -> None:
        if not self.config.plugin.enabled:
            return
        templates = self._get_templates()
        if not templates:
            self.ctx.logger.warning("[SetuPlugin] 标签模板列表为空，跳过爬取")
            return
        if per_tag_count is None:
            per_tag_count = self.config.api.per_tag_count
        self.ctx.logger.info("[SetuPlugin] 开始爬取，模板: %s，每个 %d 张", templates, per_tag_count)
        for tags in templates:
            try:
                await self._crawl_template(tags, per_tag_count)
                await asyncio.sleep(1)
            except Exception as e:
                self.ctx.logger.error("[SetuPlugin] 爬取模板 '%s' 失败: %s", tags, e)
        await self._enforce_total_limit()
        self.ctx.logger.info("[SetuPlugin] 全量爬取完成")

    async def _crawl_template(self, tags: list[str], target: int | None = None) -> None:
        if target is None:
            target = self.config.api.per_tag_count
        tag_label = "_".join(tags)
        tag_dir = os.path.join(self._image_root, self._sanitize_dirname(tag_label))
        os.makedirs(tag_dir, exist_ok=True)
        max_bytes = int(self.config.storage.max_image_size_mb * 1024 * 1024)
        r18_val = AGE_R18_MAP.get(self.config.api.age_rating, 2)
        size_key = self.config.api.image_size
        self.ctx.logger.info(
            "[SetuPlugin] 模板 '%s' → 目标 %d 张, r18=%d, size=%s",
            tags, target, r18_val, size_key,
        )
        downloaded = 0
        skipped_size = 0
        seen_pids: set[tuple[int, int]] = set()
        # Lolicon 每次最多 20 张，预留充足的尝试次数
        max_attempts = max(3, (target + 19) // 20 * 3)

        while downloaded < target and max_attempts > 0:
            max_attempts -= 1
            remaining = target - downloaded
            batch_size = min(remaining, 20)
            try:
                items = await self._fetch_batch(tags, batch_size, r18_val, size_key)
                if not items:
                    await asyncio.sleep(1)
                    continue
                for item in items:
                    if downloaded >= target:
                        break
                    pid = item.get("pid", 0)
                    p = item.get("p", 0)
                    pid_key = (pid, p)
                    if pid_key in seen_pids:
                        continue
                    seen_pids.add(pid_key)
                    if self._find_existing_image(tag_dir, str(pid)):
                        continue
                    image_url = item.get("urls", {}).get(size_key, "")
                    if not image_url:
                        continue
                    title = item.get("title", "untitled")
                    ext = item.get("ext", ".jpg")
                    if not ext.startswith("."):
                        ext = "." + ext
                    filename = f"{pid}_{p}_{self._sanitize_filename(title)}{ext}"
                    filepath = os.path.join(tag_dir, filename)
                    actual_size = await self._download_image(image_url, filepath, max_bytes)
                    if actual_size == 0:
                        skipped_size += 1
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        continue
                    downloaded += 1
                    # 保存 URL 映射（路径要与 _collect_unsent_images 一致）
                    rel = PurePosixPath(os.path.relpath(filepath, Path(self._image_root).parent)).as_posix()
                    self._image_urls[rel] = image_url
                    author = item.get("author", "?")
                    self.ctx.logger.info(
                        "[SetuPlugin] 已下载: %s/%s by %s (%.1fMB, %d/%d)",
                        tag_label, filename, author, actual_size / 1048576, downloaded, target,
                    )
                    await asyncio.sleep(0.5)
            except Exception as e:
                self.ctx.logger.warning("[SetuPlugin] 批次下载失败: %s", e)
                await asyncio.sleep(2)
                continue

        msg = "[SetuPlugin] 模板 '%s' 完成: 下载 %d 张" % (tags, downloaded)
        if skipped_size:
            msg += "，跳过 %d 张(超大小)" % skipped_size
        self.ctx.logger.info(msg)

    # ── API ────────────────────────────────────────────────────────────

    async def _fetch_batch(self, tags: list[str], num: int, r18: int, size_key: str) -> list[dict]:
        """调用 Lolicon API v2 获取一批图片，最多 20 张。"""
        payload: dict[str, Any] = {
            "tag": tags,
            "num": num,
            "r18": r18,
            "excludeAI": self.config.api.exclude_ai,
            "size": [size_key],
            "proxy": "i.pixiv.re",
        }
        try:
            async with httpx.AsyncClient(proxy=self._proxy_url(), timeout=25.0) as client:
                resp = await client.post(LOLICON_API, json=payload)
                resp.raise_for_status()
                result = resp.json()
        except Exception as e:
            self.ctx.logger.warning("[SetuPlugin] Lolicon API 请求失败: %s", e)
            return []
        if result.get("error"):
            self.ctx.logger.warning("[SetuPlugin] Lolicon API 返回错误: %s", result["error"])
            return []
        return result.get("data") or []

    # ── 下载 ───────────────────────────────────────────────────────────

    async def _download_image(self, url: str, filepath: str, max_bytes: int) -> int:
        headers = {
            "Referer": "https://www.pixiv.net/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        }
        async with httpx.AsyncClient(proxy=self._proxy_url(), headers=headers, timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                cl = resp.headers.get("content-length")
                if cl and int(cl) > max_bytes:
                    self.ctx.logger.info("[SetuPlugin] 跳过超大图: %.1fMB", int(cl) / 1048576)
                    return 0
                total = 0
                with open(filepath, "wb") as f:
                    async for chunk in resp.aiter_bytes(65536):
                        f.write(chunk)
                        total += len(chunk)
                        if total > max_bytes:
                            self.ctx.logger.info("[SetuPlugin] 下载中超限，丢弃")
                            return 0
                return total

    # ── 总量清理 ───────────────────────────────────────────────────────

    async def _enforce_total_limit(self) -> None:
        max_total = self.config.storage.max_total_images
        if max_total <= 0:
            return
        all_images = self._list_all_images()
        if len(all_images) <= max_total:
            return
        all_images.sort(key=lambda x: x[0])
        excess = len(all_images) - max_total
        self.ctx.logger.info("[SetuPlugin] 总量 %d > %d，清理 %d 张", len(all_images), max_total, excess)
        removed = 0
        for _mtime, rel_path, abs_path in all_images:
            if removed >= excess:
                break
            try:
                os.remove(abs_path)
                self._sent_files.discard(rel_path)
                self._image_urls.pop(rel_path, None)
                removed += 1
            except Exception as e:
                self.ctx.logger.warning("[SetuPlugin] 删除失败 %s: %s", abs_path, e)
        self._save_sent_tracking()
        self.ctx.logger.info("[SetuPlugin] 清理完成: %d 张", removed)

    def _list_all_images(self) -> list[tuple[float, str, str]]:
        result: list[tuple[float, str, str]] = []
        image_root = Path(self._image_root)
        if not image_root.exists():
            return result
        for tag_dir in image_root.iterdir():
            if not tag_dir.is_dir():
                continue
            for fpath in tag_dir.iterdir():
                if not fpath.is_file() or fpath.suffix.lower() not in VALID_IMAGE_EXTS:
                    continue
                rel = PurePosixPath(fpath.relative_to(image_root.parent)).as_posix()
                result.append((fpath.stat().st_mtime, rel, str(fpath)))
        return result

    # ── 发送 ───────────────────────────────────────────────────────────

    async def _send_setu_images(self, stream_id: str, count: int | None = None) -> str:
        if count is None:
            count = self.config.send.count
        unsent = self._collect_unsent_images()
        if not unsent:
            # 仓库为空，尝试自动爬取
            if self.config.schedule.auto_crawl_when_empty and not self._crawling_now:
                self.ctx.logger.info("[SetuPlugin] 仓库为空，触发自动爬取")
                self._crawling_now = True
                try:
                    await self._execute_full_crawl(per_tag_count=self.config.schedule.auto_crawl_count)
                except Exception as e:
                    self.ctx.logger.error("[SetuPlugin] 自动爬取失败: %s", e)
                finally:
                    self._crawling_now = False
                unsent = self._collect_unsent_images()
                if not unsent:
                    return "仓库里没有图片，自动爬取也没拉到图，稍后再试试吧～"
            else:
                return "仓库里已经没有图片了，等下次定时爬取后再来找我吧～"
        random.shuffle(unsent)
        selected = unsent[: min(count, len(unsent))]
        sent_count = 0
        for rel_path, abs_path in selected:
            try:
                img_data = self._read_and_compress(abs_path)
                if await self.ctx.send.image(img_data, stream_id):
                    self._sent_files.add(rel_path)
                    sent_count += 1
                    await asyncio.sleep(0.5)
            except Exception as e:
                self.ctx.logger.error("[SetuPlugin] 发送 %s 失败: %s", rel_path, e)
        self._save_sent_tracking()
        remain = len(unsent) - sent_count
        msg = f"发了 {sent_count} 张，仓库里还有 {remain} 张存货～"
        if remain == 0:
            msg += " 下次爬取后再来吧！"
        return msg

    def _collect_unsent_images(self) -> list[tuple[str, str]]:
        unsent: list[tuple[str, str]] = []
        image_root = Path(self._image_root)
        if not image_root.exists():
            return unsent
        for tag_dir in image_root.iterdir():
            if not tag_dir.is_dir():
                continue
            for fpath in tag_dir.iterdir():
                if not fpath.is_file() or fpath.suffix.lower() not in VALID_IMAGE_EXTS:
                    continue
                rel = PurePosixPath(fpath.relative_to(image_root.parent)).as_posix()
                if rel not in self._sent_files:
                    unsent.append((rel, str(fpath)))
        return unsent

    # ── @ 检测 ─────────────────────────────────────────────────────────

    def _is_at_mentioned(self, raw_message: str, is_group: bool, **kwargs) -> bool:
        at_mode = self.config.at_mode
        if not at_mode.enabled:
            return True
        if not is_group and not at_mode.require_at_private:
            return True
        if is_group and not at_mode.require_at_group:
            return True

        # 方法1：从 message 字典检查 MaiBot SDK 内置 is_at / is_mentioned 字段
        msg_dict = kwargs.get("message", {})
        if isinstance(msg_dict, dict):
            if msg_dict.get("is_at") or msg_dict.get("is_mentioned"):
                return True

        # 方法2：检查顶层 kwargs（兼容 Tool 调用路径，NapCat 直接传 is_at/is_mentioned）
        if kwargs.get("is_at") or kwargs.get("is_mentioned"):
            return True

        # 方法3：字符串匹配 @bot_name 或 CQ:at / <@
        # 优先用 text 字段（Command 路径），fallback 到 raw_message（Tool 路径）
        matched_text = raw_message or kwargs.get("text", "") or ""
        bot_name = at_mode.bot_name
        if bot_name and (
            f"@{bot_name}" in matched_text or matched_text.strip().startswith(bot_name)
        ):
            return True
        if "[CQ:at" in matched_text or "<@" in matched_text:
            return True

        # 方法4：Tool/LLM 调用路径 — kwargs 中没有 message 字典也没有文本
        # 说明是 LLM 发起的工具调用，@ 检测已由 Command 路径或 LLM 自身处理过
        if not kwargs.get("message") and not matched_text:
            return True

        return False

    def _is_group_chat(self, kwargs: dict) -> bool:
        # 方法1：从 message 字典中检查 message_info.group_info
        msg = kwargs.get("message", {})
        if isinstance(msg, dict):
            msg_info = msg.get("message_info", {})
            if isinstance(msg_info, dict) and msg_info.get("group_info") is not None:
                return True

        # 方法2：检查顶层 group_id（Command 路径直接传了 group_id）
        raw_group_id = kwargs.get("group_id", "") or ""
        if raw_group_id:
            return True

        # 方法3：从 kwargs 中直接提取 message_info（Tool 路径直接传 message_info）
        raw_msg_info = kwargs.get("message_info", {})
        if isinstance(raw_msg_info, dict) and raw_msg_info.get("group_info"):
            return True

        # 方法4：检查 kwargs 中的 user_id（如果只有 user_id 没有 group_id → 私聊）
        # Command 路径一定传了 user_id 或 group_id；如果只有 user_id → 私聊
        raw_user_id = kwargs.get("user_id", "") or ""
        if raw_user_id and not raw_group_id:
            return False

        # 方法5：退化检查 — stream_id（MD5 hash，不包含 "group" 明文）
        # 这个基本不会匹配，但保留作为最后的 fallback
        stream_id = kwargs.get("stream_id", "")
        if "group" in stream_id.lower():
            return True
        if "private" in stream_id.lower() or "friend" in stream_id.lower():
            return False

        # 如果所有方法都无法判断，保守地假设是私聊
        return False

    def _check_access(self, kwargs: dict) -> str | None:
        if not self.config.plugin.enabled:
            return "插件总开关已关闭"
        is_group = self._is_group_chat(kwargs)
        if not self._is_at_mentioned(kwargs.get("raw_message", "").strip(), is_group, **kwargs):
            return self.config.at_mode.reject_message
        return None

    # ── @Tool：发图 ────────────────────────────────────────────────────

    @Tool(
        "send_setu",
        brief_description="发送涩图/色图/看看腿给用户",
        description="当用户想要看涩图、色图、美图、看看腿、来点图时，从图片仓库挑选未发送过的图片发送。",
        detailed_description="从图片仓库中挑未发送过的图片发送，不重复。",
        parameters=[],
    )
    async def handle_send_setu_tool(self, **kwargs) -> dict[str, Any]:
        if time.time() - self._last_cmd_time < 10:
            return {"success": True, "content": "刚刚已触发发图，跳过重复发送"}
        error = self._check_access(kwargs)
        if error is not None:
            return {"success": False, "content": error}
        msg = await self._send_setu_images(kwargs.get("stream_id", ""))
        return {"success": True, "content": msg}

    # ── @Command：发图关键词 ───────────────────────────────────────────
    #
    # 注意：pattern 必须宽匹配（r".+"），因为关键词列表在 config.toml 中动态配置
    # 实际关键词过滤在 handler 中完成，这样用户修改 trigger_keywords 才能生效
    #

    @Command(
        "setu_cmd",
        description="当用户消息中包含涩图/色图等关键词时直接触发发图",
        pattern=r".+",
        aliases=["来点图"],
    )
    async def handle_send_setu_command(self, **kwargs) -> tuple[bool, str, int]:
        stream_id = kwargs.get("stream_id", "")

        # 从 kwargs 获取消息原文（Command 路径用 text，Tool 路径用 raw_message）
        msg_text = kwargs.get("text", "") or kwargs.get("raw_message", "") or ""

        # 检查 trigger_keywords 是否匹配（读取自 config.toml，支持动态修改）
        trigger_kws = self.config.send.trigger_keywords
        if trigger_kws and not any(kw in msg_text for kw in trigger_kws):
            return False, "", 0

        self._last_cmd_time = time.time()

        error = self._check_access(kwargs)
        if error is not None:
            if error:
                await self.ctx.send.text(error, stream_id)
            return False, error, 0
        msg = await self._send_setu_images(stream_id)
        return True, msg, 2

    # ── @Command：立刻爬取 ─────────────────────────────────────────────
    #
    # 注意：pattern 必须保持宽匹配（r"."），关键词过滤在 handler 中用 config 的
    # crawl_trigger_keywords 动态判断。
    #

    @Command(
        "crawl_now_cmd",
        description="立刻触发一次图片爬取",
        # pattern 使用默认关键词（handler 内还会再用 config.crawl_trigger_keywords 二次过滤）
        pattern=r"(?:爬取|爬图|crawl|立刻爬|立即爬|马上爬|现在爬|开始爬)",
        aliases=["立刻爬取", "立即爬取", "立刻爬图", "立即爬图", "马上爬", "现在爬", "爬图", "开始爬"],
    )
    async def handle_crawl_now_command(self, **kwargs) -> tuple[bool, str, int]:
        stream_id = kwargs.get("stream_id", "")
        # Command 路径的 text 在 kwargs["text"]，不是 kwargs["raw_message"]
        msg_text = kwargs.get("text", "") or kwargs.get("raw_message", "") or ""
        keywords = self.config.schedule.crawl_trigger_keywords
        if not any(kw in msg_text for kw in keywords):
            return False, "", 0
        result = await self.handle_crawl_now_tool(**kwargs)
        if result.get("success"):
            await self.ctx.send.text(result["content"], stream_id)
        else:
            await self.ctx.send.text(f"❌ {result['content']}", stream_id)
        return result["success"], result["content"], 1

    # ── @Tool：立刻爬取 ────────────────────────────────────────────────

    @Tool("pixiv_crawl_now", brief_description="立刻执行一次图片爬取", description="立刻触发一次全量爬取。正在爬取中则提示等待。", parameters=[])
    async def handle_crawl_now_tool(self, **kwargs) -> dict[str, Any]:
        if not self.config.plugin.enabled:
            return {"success": False, "content": "插件总开关已关闭"}
        if self._crawling_now:
            return {"success": False, "content": "正在爬取中，请稍后再试～"}
        self._crawling_now = True
        try:
            start = time.time()
            self.ctx.logger.info("[SetuPlugin] 手动触发立刻爬取")
            await self._execute_full_crawl()
            elapsed = time.time() - start
            total = self._count_all_images()
            unsent = self._count_unsent_images()
            return {"success": True, "content": f"✅ 爬取完成！用时 {elapsed:.0f} 秒，仓库共 {total} 张，{unsent} 张未发送。@我 说涩图试试～"}
        except Exception as e:
            self.ctx.logger.error("[SetuPlugin] 手动爬取出错: %s", e)
            return {"success": False, "content": f"爬取失败：{e}"}
        finally:
            self._crawling_now = False

    # ── @Tool：仓库状态 ────────────────────────────────────────────────

    @Tool("pixiv_status", brief_description="查看图片仓库状态", description="查看已缓存和已发送的图片数量统计。", parameters=[])
    async def handle_status_tool(self, **kwargs) -> dict[str, Any]:
        total_files = 0
        tag_stats: dict[str, int] = {}
        sent_stats: dict[str, int] = {}
        image_root = Path(self._image_root) if self._image_root else None
        if image_root and image_root.exists():
            for tag_dir in image_root.iterdir():
                if not tag_dir.is_dir():
                    continue
                count = sum(1 for f in tag_dir.iterdir() if f.is_file() and f.suffix.lower() in VALID_IMAGE_EXTS)
                if count > 0:
                    tag_stats[tag_dir.name] = count
                    total_files += count
                    sent_stats[tag_dir.name] = sum(1 for p in self._sent_files if f"/{tag_dir.name}/" in PurePosixPath(p).as_posix())
        sent_count = len(self._sent_files)
        url_count = len(self._image_urls)
        max_total = self.config.storage.max_total_images
        lines = [
            "📊 图片仓库状态",
            f"  总开关:   {'✅ 开启' if self.config.plugin.enabled else '❌ 关闭'}",
            f"  年龄分级: {self.config.api.age_rating}",
            f"  总图片数: {total_files}{' / ' + str(max_total) + ' 上限' if max_total > 0 else ''}",
            f"  已发送:   {sent_count}",
            f"  未发送:   {max(0, total_files - sent_count)}",
            f"  URL缓存:  {url_count} 条",
            f"  发送模式: URL优先，失败回退base64",
        ]
        if tag_stats:
            lines.append("  ── 各标签分布 ──")
            for tag, cnt in sorted(tag_stats.items()):
                lines.append(f"    {tag}: {cnt} 张（已发 {sent_stats.get(tag, 0)}）")
        return {"success": True, "content": "\n".join(lines)}

    # ── @Tool：清理缓存 ────────────────────────────────────────────────

    @Tool("pixiv_cleanup", brief_description="清理发送记录和无效URL缓存", description="重置发送记录（允许重新发送已发图片）或清理无效URL映射。", parameters=[])
    async def handle_cleanup_tool(self, **kwargs) -> dict[str, Any]:
        if not self.config.plugin.enabled:
            return {"success": False, "content": "插件总开关已关闭"}
        
        # 清理无效 URL
        url_cleaned = self._cleanup_invalid_urls()
        
        # 统计当前状态
        total_images = len(self._list_all_images())
        sent_count = len(self._sent_files)
        url_count = len(self._image_urls)
        
        # 重置发送记录
        old_sent_count = len(self._sent_files)
        self._sent_files.clear()
        self._save_sent_tracking()
        
        lines = [
            "🧹 缓存清理完成",
            f"  已重置 {old_sent_count} 条发送记录",
            f"  清理了 {url_cleaned} 条无效URL",
            f"  当前URL缓存: {url_count} 条",
            f"  仓库图片数: {total_images} 张",
            "  现在所有图片都可以重新发送了！",
        ]
        return {"success": True, "content": "\n".join(lines)}

    # ── 工具方法 ───────────────────────────────────────────────────────

    def _cleanup_invalid_urls(self) -> int:
        """清理没有对应图片文件的 URL 映射。"""
        image_root = Path(self._image_root)
        if not image_root.exists():
            count = len(self._image_urls)
            self._image_urls.clear()
            return count
        valid_urls: dict[str, str] = {}
        for rel_path, url in self._image_urls.items():
            full_path = image_root.parent / rel_path
            if full_path.exists() and full_path.is_file():
                valid_urls[rel_path] = url
        removed = len(self._image_urls) - len(valid_urls)
        self._image_urls = valid_urls
        return removed

    _MAX_RAW_FOR_SEND = 500 * 1024  # 超过500KB就压缩（VPS到QQ服务器上传较慢，需控制图片大小）
    _MAX_DIMENSION = 1600
    _TARGET_MAX_SIZE = 400 * 1024  # 压缩后目标不超过400KB

    def _read_and_compress(self, abs_path: str) -> str:
        raw_size = os.path.getsize(abs_path)
        if raw_size <= self._MAX_RAW_FOR_SEND or not HAS_PIL:
            with open(abs_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        self.ctx.logger.info("[SetuPlugin] 大图压缩中: %.1fKB", raw_size / 1024)
        try:
            with Image.open(abs_path) as img:
                img = img.convert("RGB")
                if img.width > self._MAX_DIMENSION or img.height > self._MAX_DIMENSION:
                    img.thumbnail((self._MAX_DIMENSION, self._MAX_DIMENSION), Image.LANCZOS)

                # 渐进式压缩：从高质量开始，逐步降低直到小于目标大小
                for quality in (85, 75, 60, 45, 30):
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality, optimize=True)
                    compressed = buf.getvalue()
                    if len(compressed) <= self._TARGET_MAX_SIZE or quality <= 30:
                        break

                self.ctx.logger.info("[SetuPlugin] 压缩: %.1fKB → %.1fKB (q=%d)", raw_size / 1024, len(compressed) / 1024, quality)
                return base64.b64encode(compressed).decode()
        except Exception as e:
            self.ctx.logger.warning("[SetuPlugin] 压缩失败: %s", e)
            with open(abs_path, "rb") as f:
                return base64.b64encode(f.read()).decode()

    def _count_all_images(self) -> int:
        return len(self._list_all_images())

    def _count_unsent_images(self) -> int:
        return len(self._collect_unsent_images())

    @staticmethod
    def _sanitize_dirname(name: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', "_", name).strip()

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        clean = re.sub(r'[<>:"/\\|?*]', "_", name).strip()
        return clean[:60] if len(clean) > 60 else clean

    @staticmethod
    def _find_existing_image(tag_dir: str, illust_id: str) -> str | None:
        prefix = f"{illust_id}_"
        if not os.path.isdir(tag_dir):
            return None
        for fname in os.listdir(tag_dir):
            if fname.startswith(prefix):
                return os.path.join(tag_dir, fname)
        return None


def create_plugin() -> PixivCrawlerPlugin:
    return PixivCrawlerPlugin()

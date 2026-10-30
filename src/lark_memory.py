#!/usr/bin/env python3
# =============================================
# lark_memory.py - 飞书 Bot 会话记忆（C）
#
# 定位：让 Bot 能承接指代 —— 「它的提取物呢」「这个案子的详情」。
#   - 每个 chat 保留最近 N 轮（user/assistant）+ last_case_id（最近指到的案件）
#   - 落盘 `.run/bot/sessions.json`（已 gitignore）；🔴 禁落 data/
#   - 只存**摘要级**文本（截断），不存材料全文；不存密钥
#
# 纯 stdlib（ornament 依赖），线程安全：WS 后台线程 + 异步 worker 并发写。
# 见 docs/SPEC-feishu-bot.md §5.3。
# =============================================
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .lark_identity import DEFAULT_STATE_DIR

logger = logging.getLogger(__name__)

MAX_TURN_CHARS = 500          # 单轮文本截断（防会话文件膨胀）
MAX_DOC_CHARS = 20000         # 最近文书全文留存上限（防会话文件膨胀）
DEFAULT_MAX_TURNS = 6         # 每 chat 保留轮数
DEFAULT_MAX_CHATS = 200       # 最多保留多少个 chat
DEFAULT_TTL = 7 * 24 * 3600   # 会话过期（秒）
DEFAULT_PENDING_TTL = 1800    # 待确认上下文（如刚收到的附件）有效期（秒）


@dataclass
class Turn:
    role: str        # "user" | "assistant"
    text: str
    ts: float = field(default_factory=time.time)


class SessionStore:
    """会话记忆：per-chat 轮次 + 最近案件。可注入 path / clock 便于测试。"""

    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        max_turns: int = DEFAULT_MAX_TURNS,
        max_chats: int = DEFAULT_MAX_CHATS,
        ttl: float = DEFAULT_TTL,
        pending_ttl: float = DEFAULT_PENDING_TTL,
        enabled: bool = True,
        clock=time.time,
    ):
        self.path = Path(path or (DEFAULT_STATE_DIR / "sessions.json"))
        self.max_turns = max(1, int(max_turns))
        self.max_chats = max(1, int(max_chats))
        self.ttl = float(ttl)
        self.pending_ttl = float(pending_ttl)
        self.enabled = bool(enabled)
        self._clock = clock
        self._lock = threading.RLock()
        self._chats: dict[str, dict] = {}
        self._load()

    # ---------- 读写 ----------

    def history(self, chat_id: str, limit: Optional[int] = None) -> list[Turn]:
        """最近轮次（时间正序）；无会话返回 []。"""
        if not self.enabled:
            return []
        with self._lock:
            entry = self._chats.get(self._chat_key(chat_id)) or {}
            turns = [Turn(t["role"], t["text"], float(t.get("ts") or 0)) for t in entry.get("turns") or []]
        return turns[-limit:] if limit else turns

    def remember(self, chat_id: str, role: str, text: str) -> None:
        """追加一轮（超长截断；超 max_turns 头部丢弃）并持久化。"""
        if not self.enabled:
            return
        text = (text or "").strip()[:MAX_TURN_CHARS]
        if not text:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.setdefault(key, {"turns": [], "last_case_id": "", "updated": 0.0})
            entry["turns"].append({"role": role, "text": text, "ts": self._clock()})
            entry["turns"] = entry["turns"][-self.max_turns:]
            entry["updated"] = self._clock()
            self._save()

    def last_case(self, chat_id: str) -> str:
        """最近一次操作/提及的案件 ID（指代补全用）。"""
        if not self.enabled:
            return ""
        with self._lock:
            entry = self._chats.get(self._chat_key(chat_id)) or {}
        return str(entry.get("last_case_id") or "")

    def set_last_case(self, chat_id: str, case_id: str) -> None:
        if not self.enabled or not case_id:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.setdefault(key, {"turns": [], "last_case_id": "", "updated": 0.0})
            if entry.get("last_case_id") == case_id:
                return
            entry["last_case_id"] = str(case_id)
            entry["updated"] = self._clock()
            self._save()

    def clear_last_case(self, chat_id: str) -> None:
        """清掉最近案件（如该案已删除），避免下一轮指代解析到失效 ID。"""
        if not self.enabled:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key)
            if entry and entry.get("last_case_id"):
                entry["last_case_id"] = ""
                entry["updated"] = self._clock()
                self._save()

    def set_pending(self, chat_id: str, pending: dict) -> None:
        """暂存「待用户确认意图」的上下文（如刚收到、尚未决定怎么处理的附件）。

        与 last_case 一样落盘持久化（Bot 每 5s 会重启一次 WS 循环，内存态会丢）。
        """
        if not self.enabled or not pending:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.setdefault(key, {"turns": [], "last_case_id": "", "updated": 0.0})
            entry["pending"] = dict(pending)
            entry["pending_ts"] = self._clock()
            entry["updated"] = self._clock()
            self._save()

    def pending(self, chat_id: str) -> dict:
        """读取待确认上下文；不存在或已过期（默认 30 分钟）返回 {}。"""
        if not self.enabled:
            return {}
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key) or {}
            pend = entry.get("pending")
            ts = float(entry.get("pending_ts") or 0)
        if not isinstance(pend, dict) or not pend:
            return {}
        if self._clock() - ts > self.pending_ttl:
            return {}
        return dict(pend)

    def clear_pending(self, chat_id: str) -> None:
        if not self.enabled:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key)
            if entry and entry.get("pending"):
                entry["pending"] = {}
                entry["pending_ts"] = 0.0
                entry["updated"] = self._clock()
                self._save()

    # ---------- 候选案件（多命中消歧） ----------

    def set_candidates(self, chat_id: str, items: list, action: str = "") -> None:
        """暂存「多命中候选案件」+ 待续跑动作，供点选 / 序号选中后续跑。"""
        if not self.enabled or not items:
            return
        payload = {
            "action": action or "",
            "items": [
                {
                    "case_id": str(i.get("id") or i.get("case_id") or ""),
                    "case_name": str(i.get("case_name") or ""),
                    "case_number": str(i.get("case_number") or ""),
                }
                for i in list(items)[:20]
                if isinstance(i, dict) and (i.get("id") or i.get("case_id"))
            ],
        }
        if not payload["items"]:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.setdefault(key, {"turns": [], "last_case_id": "", "updated": 0.0})
            entry["candidates"] = payload
            entry["candidates_ts"] = self._clock()
            entry["updated"] = self._clock()
            self._save()

    def candidates(self, chat_id: str) -> dict:
        """读取候选案件上下文；不存在或已过期返回 {}。"""
        if not self.enabled:
            return {}
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key) or {}
            cand = entry.get("candidates")
            ts = float(entry.get("candidates_ts") or 0)
        if not isinstance(cand, dict) or not cand.get("items"):
            return {}
        if self._clock() - ts > self.pending_ttl:
            return {}
        return dict(cand)

    def clear_candidates(self, chat_id: str) -> None:
        if not self.enabled:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key)
            if entry and entry.get("candidates"):
                entry["candidates"] = {}
                entry["candidates_ts"] = 0.0
                entry["updated"] = self._clock()
                self._save()

    # ---------- 最近文书（分段续看） ----------

    def set_last_doc(self, chat_id: str, text: str, *, case_id: str = "") -> None:
        """暂存最近一次生成的文书全文 + 续读位置（`pos` = 已发字节数）。"""
        if not self.enabled:
            return
        body = (text or "")[:MAX_DOC_CHARS]
        if not body.strip():
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.setdefault(key, {"turns": [], "last_case_id": "", "updated": 0.0})
            entry["last_doc"] = {"text": body, "pos": 0, "case_id": str(case_id or "")}
            entry["updated"] = self._clock()
            self._save()

    def last_doc(self, chat_id: str) -> dict:
        """读取最近文书上下文；无则返回 {}。"""
        if not self.enabled:
            return {}
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key) or {}
            doc = entry.get("last_doc")
        if not isinstance(doc, dict) or not doc.get("text"):
            return {}
        return dict(doc)

    def set_doc_pos(self, chat_id: str, pos: int) -> None:
        """更新续读位置。"""
        if not self.enabled:
            return
        key = self._chat_key(chat_id)
        with self._lock:
            entry = self._chats.get(key) or {}
            doc = entry.get("last_doc")
            if isinstance(doc, dict) and doc.get("text"):
                doc["pos"] = int(pos)
                entry["updated"] = self._clock()
                self._save()

    def clear(self, chat_id: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._chats.pop(self._chat_key(chat_id), None) is not None:
                self._save()

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._chats, ensure_ascii=False))

    # ---------- 内部 ----------

    @staticmethod
    def _chat_key(chat_id: str) -> str:
        return (chat_id or "").strip() or "(local)"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            logger.warning("会话记忆文件损坏，忽略：%s", self.path)
            return
        chats = raw.get("chats") if isinstance(raw, dict) else None
        if isinstance(chats, dict):
            self._chats = {k: v for k, v in chats.items() if isinstance(v, dict)}
        self._prune()

    def _prune(self) -> None:
        """TTL 清理 + chat 数量上限（保留最近活跃）。"""
        now = self._clock()
        for key in [k for k, v in self._chats.items()
                    if now - float(v.get("updated") or 0) > self.ttl]:
            self._chats.pop(key, None)
        if len(self._chats) > self.max_chats:
            keep = sorted(self._chats.items(), key=lambda kv: float(kv[1].get("updated") or 0))
            for key, _ in keep[: len(self._chats) - self.max_chats]:
                self._chats.pop(key, None)

    def _save(self) -> None:
        """原子写（临时文件 + os.replace），避免并发/中断写坏 JSON。"""
        self._prune()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"chats": self._chats}, ensure_ascii=False)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".sessions-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                os.replace(tmp, self.path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        except OSError:
            logger.exception("会话记忆写入失败（已忽略）：%s", self.path)


__all__ = ["Turn", "SessionStore", "DEFAULT_MAX_TURNS", "MAX_TURN_CHARS"]
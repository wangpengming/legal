#!/usr/bin/env python3
# =============================================
# lark_transport.py - 飞书通道层（SPEC-feishu-bot §4）
# 默认长连接（WebSocket，主动外连，无需入站端口）；webhook 为可选开关。
# 两种模式共用官方 EventDispatcherHandler，业务层零感知。
#
# 本层只负责"把事件从飞书搬进/搬出"：
#   - 归一化事件（消息 / 卡片回调 / 表情 / 入群）
#   - 去重（消息 24h / 卡片 15min，落 .run/bot/，禁止落 data/）
#   - <3s 立即 ack；长任务交后台 worker（同 chat 串行、跨 chat 并发）
#   - 回消息 / 回卡片（缺 SDK 时降级为 no-op，便于本机静态验证）
#   - 心跳文件（供 bin/bot_status.py 判定健康）
#
# 不 import case_service：本层与业务解耦，dispatcher 由上层注入。
# =============================================
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:  # 飞书官方 SDK（websockets 为其 WS 传输依赖）
    import lark_oapi as lark
    LARK_SDK_AVAILABLE = True
except ImportError:  # 本机/CI 无 SDK：降级为可导入、可测的纯逻辑
    lark = None
    LARK_SDK_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_DIR = PROJECT_ROOT / ".run" / "bot"

# 去重 TTL（秒）与环形上限（SPEC §9）
DEDUP_MESSAGE_TTL = 24 * 3600
DEDUP_CARD_TTL = 15 * 60
# 「进入 p2p 会话」欢迎卡：同一会话 12h 内只发一次（避免每次打开都刷屏）
DEDUP_P2P_TTL = 12 * 3600
DEDUP_MAX_ENTRIES = 2048


# =============================================
# 数据契约（transport ↔ bot 交互，避免依赖具体 SDK 类型）
# =============================================

@dataclass
class Reply:
    """一条待发送的回复。kind="none" 表示不回。

    kind="card_update" 时按 message_id 原地更新已发卡片（异步完成回执）；
    message_id 为空则退化为新发一张卡。
    followup 非空时，主回执之后**追加**发一张卡（如提取完成后的「案件要点」）。
    """
    kind: str = "none"                 # "text" | "card" | "card_update" | "none"
    text: str = ""
    card: Optional[dict] = None
    message_id: str = ""
    followup: Optional[dict] = None


@dataclass
class DispatchResult:
    """dispatcher 的返回：立即回执 + 可选异步任务。

    immediate: <3s 内必须发出的回执（可为 none）。
    deferred : 长任务闭包，入参为**立即回执已发送卡片的消息 ID**（无则 None）；
               worker 执行后以其返回的 Reply 回执（同 chat 串行）。
    """
    immediate: Reply = field(default_factory=Reply)
    deferred: Optional[Callable[[Optional[str]], Reply]] = None


# =============================================
# 去重存储（JSON 持久化 + TTL + 环形上限）
# =============================================

class DedupStore:
    """key → seen_at 的去重表；线程安全；落 `.run/bot/`。"""

    def __init__(self, path: Path, ttl: float, max_entries: int):
        self.path = Path(path)
        self.ttl = ttl
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._data: dict[str, float] = self._load()

    def _load(self) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {str(k): float(v) for k, v in raw.items()}
        except Exception:
            return {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            logger.warning("去重表写入失败: %s", self.path, exc_info=True)

    def _prune(self, now: float) -> None:
        for k in [k for k, v in self._data.items() if now - v > self.ttl]:
            self._data.pop(k, None)

    def _trim(self) -> None:
        if len(self._data) > self.max_entries:
            overflow = len(self._data) - self.max_entries
            for k, _ in sorted(self._data.items(), key=lambda kv: kv[1])[:overflow]:
                self._data.pop(k, None)

    def seen(self, key: Optional[str]) -> bool:
        """True = 重复（已见过）；首次出现则记录并返回 False。"""
        if not key:
            return False
        now = time.time()
        with self._lock:
            self._prune(now)
            if key in self._data:
                return True
            self._data[key] = now
            self._trim()
            self._save()
            return False


# =============================================
# 心跳（供 bot_status 判定：进程存活 ∧ 心跳新鲜）
# =============================================

class Heartbeat:
    def __init__(self, path: Path):
        self.path = Path(path)

    def touch(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(str(int(time.time())), encoding="utf-8")
        except Exception:
            logger.warning("心跳写入失败: %s", self.path, exc_info=True)

    def age(self) -> Optional[float]:
        try:
            return time.time() - float(self.path.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def is_fresh(self, max_age: float = 90.0) -> bool:
        a = self.age()
        return a is not None and a <= max_age


# =============================================
# 事件归一化 / webhook 校验（纯函数，便于单测）
# =============================================

def _extract_text(message_type: Optional[str], content: Any) -> str:
    if message_type and message_type != "text":
        return ""
    if isinstance(content, str):
        try:
            return str(json.loads(content).get("text", ""))
        except Exception:
            return content
    if isinstance(content, dict):
        return str(content.get("text", ""))
    return ""


def _extract_attachments(message_type: Optional[str], content: Any) -> list[dict]:
    """图片 / 文件 / 媒体消息 → [{"file_key","file_name","type"}]；文本消息返回 []。

    file_key 是"资源键"，下载需带上 message_id（见 MessageSender.download_resource）。
    """
    if not message_type or message_type == "text":
        return []
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            return []
    if not isinstance(content, dict):
        return []
    if message_type == "image":
        key = content.get("image_key")
        return [{"file_key": key, "file_name": "", "type": "image"}] if key else []
    if message_type in ("file", "media", "audio"):
        key = content.get("file_key")
        if not key:
            return []
        return [{
            "file_key": key,
            "file_name": content.get("file_name") or "",
            "type": message_type,
        }]
    return []


def normalize_event(event: dict) -> dict:
    """飞书 v2 事件 → 统一结构（消息 / 卡片回调 / 表情 / 入群）。

    返回键：kind, event_type, event_id, chat_id, chat_type, message_id,
            open_id, text, token, action, mentions, message_type, attachments
    """
    event = event or {}
    header = event.get("header") or {}
    etype = header.get("event_type") or ""
    body = event.get("event") or {}

    out = {
        "kind": "other", "event_type": etype, "event_id": header.get("event_id") or "",
        "chat_id": "", "chat_type": "", "message_id": "", "open_id": "",
        "text": "", "token": "", "action": {}, "mentions": [], "message_type": "",
        "attachments": [],
    }

    if etype == "im.message.receive_v1":
        msg = body.get("message") or {}
        sender = body.get("sender") or {}
        mentions = msg.get("mentions") or []
        mtype = msg.get("message_type") or ""
        out.update(
            kind="message",
            message_id=msg.get("message_id") or "",
            chat_id=msg.get("chat_id") or "",
            chat_type=msg.get("chat_type") or "",
            open_id=(sender.get("sender_id") or {}).get("open_id") or "",
            text=_extract_text(mtype, msg.get("content")),
            mentions=mentions if isinstance(mentions, list) else [],
            message_type=mtype,
            attachments=_extract_attachments(mtype, msg.get("content")),
        )
    elif etype == "card.action.trigger":
        ctx = body.get("context") or {}
        out.update(
            kind="card",
            open_id=(body.get("operator") or {}).get("open_id") or "",
            chat_id=ctx.get("open_chat_id") or "",
            message_id=ctx.get("open_message_id") or "",
            token=body.get("token") or "",
            action=body.get("action") or {},
        )
    elif etype.startswith("im.message.reaction."):
        msg = body.get("message_id")
        out.update(
            kind="reaction",
            message_id=msg or "",
            open_id=(body.get("user_id") or {}).get("open_id") or "",
        )
    elif etype == "im.chat.member.bot.added_v1":
        out.update(kind="bot_added", chat_id=body.get("chat_id") or "")
    elif etype == "im.chat.access_event.bot_p2p_chat_entered_v1":
        # 用户打开与 Bot 的单聊：SDK 默认无处理器会打 ERROR，注册此事件后用于首次欢迎（去重）。
        out.update(
            kind="p2p_entered",
            chat_id=body.get("chat_id") or "",
            open_id=(body.get("operator_id") or {}).get("open_id") or "",
        )

    return out


def verify_signature(
    timestamp: Any, nonce: Any, encrypt_key: str, body: Any, signature: str
) -> bool:
    """webhook 签名校验：SHA256(timestamp + nonce + encrypt_key + body)，timing-safe。"""
    if isinstance(body, str):
        body = body.encode("utf-8")
    elif isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    elif not isinstance(body, (bytes, bytearray)):
        body = b""
    raw = f"{timestamp}{nonce}{encrypt_key}".encode("utf-8") + body
    digest = hashlib.sha256(raw).hexdigest()
    return hmac.compare_digest(digest, signature or "")


def url_verification_response(event: dict) -> Optional[dict]:
    """回调订阅校验：`type=url_verification` → 回显 challenge。"""
    event = event or {}
    if event.get("type") == "url_verification":
        return {"challenge": event.get("challenge", "")}
    return None


# =============================================
# 消息发送（缺 SDK 时降级 no-op）
# =============================================

class MessageSender:
    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.available = bool(LARK_SDK_AVAILABLE and app_id and app_secret)
        self._client = None
        if self.available:
            try:
                self._client = (
                    lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
                )
            except Exception:
                logger.exception("构建飞书 Client 失败，发送降级为 no-op")
                self.available = False

    def _create_message(self, chat_id: str, msg_type: str, content: str):
        if not self._client or not chat_id:
            logger.info("[noop-send] chat=%s type=%s", chat_id, msg_type)
            return None
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        resp = self._client.im.v1.message.create(request)
        if not resp.success():
            logger.warning("发送失败 code=%s msg=%s", resp.code, resp.msg)
        return resp

    def send_text(self, chat_id: str, text: str) -> Optional[str]:
        return self._message_id(
            self._create_message(chat_id, "text", json.dumps({"text": text}, ensure_ascii=False))
        )

    def send_card(self, chat_id: str, card: dict) -> Optional[str]:
        return self._message_id(
            self._create_message(chat_id, "interactive", json.dumps(card, ensure_ascii=False))
        )

    @staticmethod
    def _message_id(resp) -> Optional[str]:
        try:
            return (resp.data.message_id if resp and resp.success() else None) or None
        except Exception:
            return None

    def reply_text(self, message_id: str, text: str):
        if not self._client or not message_id:
            logger.info("[noop-reply] msg=%s", message_id)
            return None
        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .msg_type("text")
                .build()
            )
            .build()
        )
        return self._client.im.v1.message.reply(request)

    def update_card(self, message_id: str, card: dict):
        """更新已发送卡片（异步任务完成回执）。"""
        if not self._client or not message_id:
            logger.info("[noop-update-card] msg=%s", message_id)
            return None
        from lark_oapi.api.im.v1 import PatchMessageRequest, PatchMessageRequestBody

        request = (
            PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                PatchMessageRequestBody.builder()
                .content(json.dumps(card, ensure_ascii=False))
                .build()
            )
            .build()
        )
        return self._client.im.v1.message.patch(request)

    def download_resource(
        self, message_id: str, file_key: str, type_: str = "file"
    ) -> Optional[bytes]:
        """下载消息附件（图片 / 文件 / 媒体）→ bytes；失败或未启用返回 None。

        权限前提：`im:resource`（SPEC §12）。type_ 取 "image" / "file" / "media"。
        """
        if not self._client or not message_id or not file_key:
            logger.info("[noop-download] msg=%s key=%s type=%s", message_id, file_key, type_)
            return None
        from lark_oapi.api.im.v1 import GetMessageResourceRequest

        request = (
            GetMessageResourceRequest.builder()
            .message_id(message_id)
            .file_key(file_key)
            .type(type_ or "file")
            .build()
        )
        resp = self._client.im.v1.message_resource.get(request)
        if not resp.success():
            logger.warning("附件下载失败 code=%s msg=%s", resp.code, resp.msg)
            return None
        data = getattr(resp, "file", None)
        try:
            if hasattr(data, "read"):
                return data.read()
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
        except Exception:
            logger.exception("附件读取失败 key=%s", file_key)
        return None


def _to_dict(data: Any) -> dict:
    """SDK 事件对象 → dict（handler 回调入参归一）。"""
    if isinstance(data, dict):
        return data
    if lark is not None:
        try:
            return json.loads(lark.JSON.marshal(data))
        except Exception:
            pass
    try:
        return json.loads(str(data))
    except Exception:
        return {}


# =============================================
# 通道主体
# =============================================

class LarkTransport:
    """飞书通道：WS 后台线程（默认）/ webhook 原语（可选）。

    dispatcher 契约：`dispatcher(ev: dict) -> DispatchResult`，ev 为 normalize_event 输出。
    """

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        dispatcher: Optional[Callable[[dict], DispatchResult]] = None,
        *,
        mode: str = "websocket",
        state_dir: Optional[Path] = None,
        verify_token: str = "",
        encrypt_key: str = "",
        max_workers: int = 4,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.dispatcher = dispatcher
        self.mode = "webhook" if str(mode).lower() == "webhook" else "websocket"
        self.verify_token = verify_token or ""
        self.encrypt_key = encrypt_key or ""
        self.state_dir = Path(state_dir or os.environ.get("LARK_STATE_DIR") or DEFAULT_STATE_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.message_dedup = DedupStore(
            self.state_dir / "seen_message_ids.json", DEDUP_MESSAGE_TTL, DEDUP_MAX_ENTRIES
        )
        self.card_dedup = DedupStore(
            self.state_dir / "seen_card_tokens.json", DEDUP_CARD_TTL, DEDUP_MAX_ENTRIES
        )
        self.p2p_dedup = DedupStore(
            self.state_dir / "seen_p2p_chats.json", DEDUP_P2P_TTL, 512
        )
        self.heartbeat = Heartbeat(self.state_dir / "heartbeat")
        self.sender = MessageSender(app_id, app_secret)

        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="case-bot")
        self._chat_locks: dict[str, threading.Lock] = {}
        self._chat_locks_guard = threading.Lock()
        self._stop = threading.Event()
        self._ws_thread: Optional[threading.Thread] = None
        self._hb_thread: Optional[threading.Thread] = None

    # ---------- 事件入口（WS 回调与 webhook 共用） ----------

    def handle_event(self, event: dict) -> dict:
        """校验 → 去重 → 派发 → 立即 ack（<3s）。返回 ack dict。"""
        ev = normalize_event(event)

        if ev["kind"] == "card":
            # 卡片回调复用同一 event_id（同一张卡多次点击），真值在 token
            if self.card_dedup.seen(ev.get("token") or ev.get("event_id")):
                return _ack("duplicate-card")
        elif ev["kind"] == "p2p_entered":
            # 每次打开单聊都是新 event_id → 按 chat 去重（同一会话 12h 只欢迎一次）
            if self.p2p_dedup.seen(ev.get("chat_id") or ev.get("event_id")):
                return _ack("duplicate-p2p")
        else:
            dedup_key = ev.get("message_id") or ev.get("event_id")
            if self.message_dedup.seen(dedup_key):
                return _ack("duplicate")

        self.heartbeat.touch()

        if self.dispatcher is None:
            return _ack("no-dispatcher")

        try:
            result = self.dispatcher(ev) or DispatchResult()
        except Exception as e:
            logger.exception("dispatcher 处理失败")
            self._send(ev, Reply(kind="text", text=f"❌ 处理失败：{e}"))
            return _ack("error")

        ack_message_id = None
        if result.immediate and result.immediate.kind != "none":
            ack_message_id = self._send(ev, result.immediate)
        if result.deferred is not None:
            self._submit_deferred(ev, result.deferred, ack_message_id)
        return _ack("ok")

    def _submit_deferred(
        self, ev: dict, task: Callable[[Optional[str]], Reply], ack_message_id: Optional[str]
    ) -> None:
        chat_key = ev.get("chat_id") or ev.get("open_id") or "_"
        lock = self._chat_lock(chat_key)

        def run() -> None:
            with lock:
                if self._stop.is_set():
                    return
                try:
                    final = task(ack_message_id) or Reply()
                except Exception as e:
                    logger.exception("异步任务失败")
                    final = Reply(kind="text", text=f"❌ 处理失败：{e}")
                if final and final.kind != "none":
                    self._send(ev, final)

        try:
            self._executor.submit(run)
        except RuntimeError:
            logger.warning("worker 已关闭，异步任务丢弃")

    def _send(self, ev: dict, reply: Reply) -> Optional[str]:
        """发送回执（含可选 followup 卡），返回主回执消息 ID（无则 None）。"""
        chat_id = ev.get("chat_id") or ""
        mid = None
        try:
            if reply.kind == "card_update" and reply.card is not None:
                mid = reply.message_id or ""
                if mid:
                    self.sender.update_card(mid, reply.card)
                else:
                    mid = self._send_card(chat_id, reply.card)
            elif reply.kind == "card" and reply.card is not None:
                mid = self._send_card(chat_id, reply.card)
            elif reply.kind == "text" and reply.text:
                mid = self.sender.send_text(chat_id, reply.text)
        except Exception:
            logger.exception("发送回执失败")
        if reply.followup:
            try:
                self._send_card(chat_id, reply.followup)
            except Exception:
                logger.exception("发送后续卡失败")
        return mid

    def _send_card(self, chat_id: str, card_json: dict) -> Optional[str]:
        return self.sender.send_card(chat_id, card_json) or None

    def download_resource(self, message_id: str, file_key: str, type_: str = "file"):
        """附件下载入口（注入给 CaseBot 的 downloader；未配 SDK 时返回 None）。"""
        return self.sender.download_resource(message_id, file_key, type_)

    def _chat_lock(self, chat_id: str) -> threading.Lock:
        with self._chat_locks_guard:
            lock = self._chat_locks.get(chat_id)
            if lock is None:
                lock = threading.Lock()
                self._chat_locks[chat_id] = lock
            return lock

    # ---------- webhook 模式（原语，供外部 HTTP server 调用） ----------

    def handle_webhook(self, event: dict, headers: Optional[dict] = None) -> tuple[int, dict]:
        """回调入口：返回 (http_status, json_body)。

        外部 HTTP server（aiohttp 等）负责取原始 body 与 X-Lark-* 头。
        """
        headers = headers or {}
        challenge = url_verification_response(event)
        if challenge is not None:
            return 200, challenge

        token = ((event or {}).get("header") or {}).get("token")
        if self.verify_token and token and token != self.verify_token:
            return 401, {"code": 1, "msg": "token mismatch"}

        self.handle_event(event)
        return 200, {"code": 0, "msg": "success"}

    @staticmethod
    def check_webhook_signature(
        headers: dict, body: Any, encrypt_key: str
    ) -> bool:
        """校验 X-Lark-Signature（无 encrypt_key 时视为不校验）。"""
        if not encrypt_key:
            return True
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        return verify_signature(
            headers.get("x-lark-request-timestamp", ""),
            headers.get("x-lark-request-nonce", ""),
            encrypt_key,
            body,
            headers.get("x-lark-signature", ""),
        )

    # ---------- 启动 / 停止 ----------

    def start(self) -> None:
        self._stop.clear()
        self._start_heartbeat()
        if self.mode == "webhook":
            logger.info("webhook 模式：需外部 HTTP server 调用 handle_webhook()（本层不监听端口）")
        else:
            self._start_ws()

    def _start_heartbeat(self) -> None:
        def beat() -> None:
            while not self._stop.is_set():
                self.heartbeat.touch()
                self._stop.wait(30)

        self.heartbeat.touch()
        self._hb_thread = threading.Thread(target=beat, name="case-bot-heartbeat", daemon=True)
        self._hb_thread.start()

    def _start_ws(self) -> None:
        if not LARK_SDK_AVAILABLE:
            raise RuntimeError("websocket 模式不可用：缺少 lark-oapi（websockets）依赖")
        handler = self._build_handler()
        ws_client = lark.ws.Client(
            self.app_id, self.app_secret, event_handler=handler, log_level=lark.LogLevel.INFO
        )

        def run() -> None:
            try:
                ws_client.start()
            except Exception:
                logger.exception("WS 客户端退出")

        self._ws_thread = threading.Thread(target=run, name="case-bot-ws", daemon=True)
        self._ws_thread.start()

    def _build_handler(self):
        """注册事件（消息 / 卡片回调 / 表情 / 入群）——两模式共用。"""
        builder = lark.EventDispatcherHandler.builder(
            self.verify_token or "", self.encrypt_key or ""
        )
        builder = builder.register_p2_im_message_receive_v1(self._on_sdk_event)
        builder = builder.register_p2_card_action_trigger(self._on_sdk_event)
        for name in (
            "register_p2_im_message_reaction_created_v1",
            "register_p2_im_chat_member_bot_added_v1",
            "register_p2_im_chat_access_event_bot_p2p_chat_entered_v1",
        ):
            fn = getattr(builder, name, None)
            if callable(fn):
                try:
                    builder = fn(self._on_sdk_event)
                except Exception:
                    logger.debug("注册事件 %s 失败（SDK 版本差异），跳过", name)
        return builder.build()

    def _on_sdk_event(self, data: Any):
        """SDK handler：归一化 → handle_event → 立即返回 None（隐式 ack）。"""
        try:
            self.handle_event(_to_dict(data))
        except Exception:
            logger.exception("处理 SDK 事件失败")
        return None

    def stop(self) -> None:
        self._stop.set()
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass

    # ---------- 状态（供 bin/bot_status.py） ----------

    def status(self) -> dict:
        return {
            "mode": self.mode,
            "sdk_available": LARK_SDK_AVAILABLE,
            "ws_thread_alive": bool(self._ws_thread and self._ws_thread.is_alive()),
            "heartbeat_age": self.heartbeat.age(),
            "heartbeat_fresh": self.heartbeat.is_fresh(),
            "state_dir": str(self.state_dir),
        }


def _ack(status: str) -> dict:
    return {"status_code": 0, "status_message": status}


__all__ = [
    "LARK_SDK_AVAILABLE",
    "DEDUP_MESSAGE_TTL",
    "DEDUP_CARD_TTL",
    "DEDUP_P2P_TTL",
    "DEDUP_MAX_ENTRIES",
    "DEFAULT_STATE_DIR",
    "Reply",
    "DispatchResult",
    "DedupStore",
    "Heartbeat",
    "MessageSender",
    "LarkTransport",
    "normalize_event",
    "verify_signature",
    "url_verification_response",
]
#!/usr/bin/env python3
# =============================================
# lark_bot.py - 飞书 Bot 交互层（命令解析 + 卡片编排）
#
# 定位：与 CLI（bin/extract.py）、Streamlit UI 平级的**第三个前端**。
#   - 只做：命令解析 / 角色校验 / 卡片选取 / 异步编排
#   - 不做：直连 SQLite（已全部删除，统一走 case_service）
#
# 事件入口：
#   dispatch(ev) -> DispatchResult      供 lark_transport 调用（WS / webhook 共用）
#   handle_message(text) -> str         文本模式（本地 CLI 调试 / 无卡片通道）
#
# 见 docs/SPEC-feishu-bot.md §5 / §6 / §10。
# =============================================
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional, Union

from . import case_service as svc
from . import lark_agent as agent
from . import lark_cards as cards
from . import lark_identity as ident
from . import lark_intent as intent
from . import lark_policy as policy
from .lark_transport import DispatchResult, Reply
from config import PAGE_SIZE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 角色层级（SPEC §8）
ROLE_LEVELS = {"readonly": 0, "writer": 1, "generator": 2, "admin": 3}

DOC_CHUNK_CHARS = 1500      # 文书续看：每段字数（与结果卡预览长度一致）

# 操作 → 最低角色
ROLE_REQUIRED = {
    "list": "readonly", "search": "readonly", "detail": "readonly",
    "artifacts": "readonly", "artifact_content": "readonly", "report": "readonly",
    "templates": "readonly", "match": "readonly", "help": "readonly", "say": "readonly",
    "web_search": "readonly", "advise": "readonly", "discuss": "readonly",
    "law_lookup": "readonly", "select": "readonly", "select_case": "readonly",
    "doc_more": "readonly", "corpus": "readonly", "compare": "readonly", "stats": "readonly",
    "register": "writer", "register_submit": "writer", "register_confirm": "writer",
    "register_cancel": "readonly", "extract": "writer", "scan": "writer",
    "intake_confirm": "writer", "intake_merge": "writer", "intake_cancel": "readonly",
    "generate": "generator", "generate_run": "generator",
    "roles": "admin", "role_set": "admin", "audit": "admin", "delete": "admin",
}

# 需要 case_id 的卡片回调
_CARD_OPS = {
    cards.ACT_REGISTER_SUBMIT, cards.ACT_REGISTER_CONFIRM, cards.ACT_REGISTER_CANCEL,
    cards.ACT_DETAIL, cards.ACT_EXTRACT, cards.ACT_GENERATE, cards.ACT_GENERATE_RUN,
    cards.ACT_MATCH, cards.ACT_HELP,
}

# 待处理附件的自然语言处置指令（规则优先；判不出交 LLM 兜底 _dispatch_attachment_llm）
#   并入已有案件：「并入 腾讯案」/「把这份材料补充到腾讯案」
_MERGE_RE = re.compile(r"(?:并入|并进|归入|补充到|补充进|加到|放进|加入|挂到)\s*(.+)$")
#   暂不处理
_ATT_CANCEL_RE = re.compile(r"(暂不|先不|不用了|不处理|先放|放着|忽略|取消|丢弃|放弃|稍后|以后再说|回头再说)")
#   录入新案件：仅「强信号」（明确的写入动作词）才判定；「分析/提取 + 这份材料」
#   只是含糊表达 → 回确认卡（不擅自建案）
_ATT_NEW_STRONG_RE = re.compile(
    r"(新案件|新案子|新建案件|新建|建案|建立案件|登记案件|立案|归档|收录|入库|"
    r"作为新案|当作新案|当成新案|录入)"
)
_ATT_DOC_RE = re.compile(r"(这|该|本|此)?(份|个|批)?(材料|文件|文档|证据|附件|起诉状|证据清单|判决书|合同|协议)")
_ATT_ACT_RE = re.compile(r"(分析|解析|提取|处理|看一下|看看|读一下|了解|整理)")


def _clean_merge_ref(ref: str) -> str:
    """并入指令里的案件引用：去掉「的 / 这份材料」等尾缀噪声。"""
    s = re.sub(r"[，。,.；;：:!！?？]+$", "", (ref or "").strip())
    s = re.sub(r"(这|该|本)?(份|个|批)?(材料|文件|文档|证据|附件|资料|起诉状|证据清单).*$", "", s).strip()
    return s


def _attachment_instruction(text: str) -> tuple:
    """待处理附件存在时，把用户文本判为对材料的处置指令 → (act, ref)。

    act ∈ {"new","merge","cancel","ask"}；判不出返回 ("", "")。
    规则优先（确定性、零成本、离线可测）；判不出由调用方交 LLM 兜底或再问。

    仅「提到材料 + 分析动作」（如「帮我分析这份材料」）**不足以判定写入**——
    这类**含糊表达**归为 "ask"：由调用方回显理解并请用户一键确认，绝不擅自建案。
    """
    t = (text or "").strip()
    if not t:
        return "", ""
    m = _MERGE_RE.search(t)
    if m:
        ref = _clean_merge_ref(m.group(1))
        if ref:
            return "merge", ref
    if _ATT_CANCEL_RE.search(t):
        return "cancel", ""
    if _ATT_NEW_STRONG_RE.search(t):
        return "new", ""
    if _ATT_DOC_RE.search(t) and _ATT_ACT_RE.search(t):
        return "ask", ""
    return "", ""


_FIELD_ALIASES = {
    "案号": "case_number", "原告": "plaintiff", "被告": "defendant",
    "案由": "cause", "法院": "court", "名称": "case_name", "案件名称": "case_name",
    "来源": "source_path", "路径": "source_path", "备注": "notes",
}


def _normalize_ref(text: str) -> str:
    """引用归一：全角转半角（NFKC）+ 去空白 + 小写——比对案号时抹平格式差异。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or "")).lower()


def _number_key(text: str) -> str:
    """案号比对键：NFKC + 只保留数字/字母/汉字（抹平括号、连字符、空格差异）。"""
    return re.sub(r"[^0-9a-z一-鿿]", "", unicodedata.normalize("NFKC", text or "").lower())


# 纯指代词：「它的提取物呢」的 ref 会残留「它」→ 无信息量，应交由会话记忆补全
_PRONOUNS = {
    "它", "他", "她", "牠", "这", "那", "这个", "那个", "该", "此", "其",
    "该案", "此案", "本案", "这件", "那件", "刚才", "刚", "上面", "前面", "上述",
}
_PRONOUN_CHARS = set("它他她牠这那该此其之刚")


def _is_pronoun(ref: str) -> bool:
    """ref 是否为纯指代（「它」「这个」「刚才」）——是则应回退最近案件。"""
    s = re.sub(r"[\s、,，。；;：:?？!！]", "", ref or "")
    if not s:
        return True
    return s in _PRONOUNS or all(ch in _PRONOUN_CHARS for ch in s)


# 无信息量的口语填充词（「刚才 后来 了」这类）——视为纯指代，回退最近案件
_FILLER_RE = re.compile(
    r"(刚才|刚刚|之前|上次|先前|先前那个|后来|然后|接着|最后|到底|究竟|"
    r"那会儿|这会儿|的话|的|了|嘛|呢|吧|呀|啊)"
)
# 泛指词：去掉后若只剩这些，说明引用**不含案件线索**（「它的提取物呢」「刚才那个案子」）
_GENERIC_REF_RE = re.compile(
    r"(那个|这个|那一|这一|那一个|这一个|案子|案件|材料|资料|提取物|内容|情况|结果|信息|"
    r"怎么样|怎样|如何|什么|后续|进展|怎么样样)"
)


def _ref_core(ref: str) -> str:
    """引用去噪：去口语填充词 + 泛指词 → 剩下的才是真正的案件线索。"""
    return _GENERIC_REF_RE.sub("", _FILLER_RE.sub("", ref or "")).strip()


# 案号归一化：全角/半角括号、空格、连接号差异 → 同一案号（库内 167 条里有 39 组重复登记）
_CASE_NOISE_RE = re.compile(r"[^0-9a-z一-鿿]+")


def _norm_case_number(number: str) -> str:
    """案号归一化键：NFKC + 只留数字/字母/汉字 + 小写。"""
    return _CASE_NOISE_RE.sub("", unicodedata.normalize("NFKC", number or "").lower())


def _is_shell_case(c: dict) -> bool:
    """空壳案件：既无案号、又无可展示的案件名（内部 ID / 空名）——排到列表末尾。"""
    name = (c.get("case_name") or "").strip()
    if cards._INTERNAL_ID_RE.match(name) or not name:
        return not (c.get("case_number") or "").strip()
    return False


def _sort_cases_by_meaning(cases: list) -> list:
    """列表排序：空壳条目（无案号 + 无名）沉到末尾——首屏先给有意义的案件。"""
    meaningful = [c for c in cases if not _is_shell_case(c)]
    shells = [c for c in cases if _is_shell_case(c)]
    return meaningful + shells


def _dedupe_cases(cases: list) -> tuple:
    """按归一案号折叠重复登记 → (唯一案件列表, 被合并条数)。

    同一案件常因全角/半角括号、空格差异被登记多次；展示时折叠为一条并说明合并了几条，
    免得用户对着「7 个相关案件」实际只有 3 个真实案件做选择。
    折叠时优先保留**已提取**（有五维内容）的那条。
    """
    seen: dict = {}
    out: list = []
    merged = 0
    for c in cases or []:
        key = _norm_case_number(c.get("case_number") or "")
        if not key:
            out.append(c)
            continue
        if key in seen:
            merged += 1
            if (c.get("status") or "") == "extracted" and (seen[key].get("status") or "") != "extracted":
                idx = out.index(seen[key])
                out[idx] = c
                seen[key] = c
            continue
        seen[key] = c
        out.append(c)
    return out, merged


def _is_filler(ref: str) -> bool:
    """去掉口语填充词与泛指词后是否没剩什么（→ 当指代处理，交会话记忆补全）。"""
    return not _ref_core(ref)


# 隐私索取：索取他人身份信息 / 批量导出 → 明确拒绝（保密红线）
_PRIVACY_REQ_RE = re.compile(
    r"(身份证号?|手机号?|电话号码?|银行卡|全部当事人|所有当事人|所有电话|"
    r"全部电话|联系方式清单|把数据库.{0,6}列出来|导出全部)"
)

# 对比请求的连接词（「A 和 B」「A 跟 B」「A 与 B」）与前后缀噪声
_COMPARE_SPLIT_RE = re.compile(r"\s*(?:和|跟|与|同|versus|vs\.?)\s*", re.IGNORECASE)
_COMPARE_NOISE_RE = re.compile(
    r"(对比|比较|相比|区别|差异|一下|帮我|请|把|这两个|这两件|两个案子)"
)
# 「那个 / 这个」是指代噪声，去掉后才剩案件名（保留尾部「案子」类词由后续剥离处理）
_COMPARE_PRONOUN_RE = re.compile(r"(那个|这个)")


def _split_compare_refs(text: str) -> list:
    """从「对比一下 A 和 B」里拆出两个案件引用；拆不出恰好 2 个 → 返回实际个数。"""
    t = _COMPARE_NOISE_RE.sub(" ", text or "")
    t = re.sub(r"[？?！!。，,；;：:\s]+", " ", t).strip()
    parts = [p.strip() for p in _COMPARE_SPLIT_RE.split(t) if p.strip()]
    out: list = []
    for p in parts:
        p = _COMPARE_PRONOUN_RE.sub("", p).strip()
        p = re.sub(r"(的|案子|案件)$", "", p).strip()
        if p:
            out.append(p)
    return out[:2]



# =============================================
# 命令载体
# =============================================

@dataclass
class Command:
    """文本命令与卡片回调归一后的同一结构（同一管线处理）。"""
    name: str
    args: str = ""
    open_id: str = ""
    chat_id: str = ""
    chat_type: str = ""
    message_id: str = ""
    value: dict = field(default_factory=dict)
    form: dict = field(default_factory=dict)
    mentions: list = field(default_factory=list)

    def ref(self) -> str:
        """案件引用：卡片取 value.case_id；文本取**全部**参数（压缩空白，勿只取首 token——案名常含空格）。"""
        if self.value.get("case_id"):
            return str(self.value["case_id"])
        return " ".join(self.args.split())


def parse_text(text: str) -> Optional[Command]:
    """`/case <cmd> [args]` 或合成命令 `/card {json}` → Command；无法识别返回 None。"""
    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("/card"):
        try:
            payload = json.loads(t[len("/card"):].strip() or "{}")
        except json.JSONDecodeError:
            return None
        cmd = Command(name=str(payload.get("action") or "unknown"))
        value = payload.get("value") or {}
        cmd.value = value if isinstance(value, dict) else {}
        form = payload.get("form") or {}
        cmd.form = form if isinstance(form, dict) else {}
        return cmd
    if not t.startswith("/case"):
        return None
    rest = t[len("/case"):].strip()
    if not rest:
        return Command(name="list")
    parts = rest.split(maxsplit=1)
    return Command(name=parts[0].lower(), args=parts[1].strip() if len(parts) > 1 else "")


def _intent_to_command(text: str) -> Optional[Command]:
    """自然语言 → Command（走规则意图路由）；识别不了返回 None。"""
    it = intent.route(text)
    if it is None:
        return None
    return Command(name=it.name, args=it.args, value=dict(it.value))


def parse_fields(text: str) -> dict:
    """解析 `案号: xxx` 形式的键值行（登记表单的文本等价物）。"""
    out: dict = {}
    for line in (text or "").splitlines():
        parts = re.split(r"[:：]", line, maxsplit=1)
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        out[_FIELD_ALIASES.get(key, key.lower())] = parts[1].strip()
    return out


def _derive_case_name(fields: dict) -> str:
    plaintiff = (fields.get("plaintiff") or "").strip()
    defendant = (fields.get("defendant") or "").strip()
    cause = (fields.get("cause") or "纠纷").strip()
    if plaintiff and defendant:
        return f"{plaintiff}诉{defendant}{cause}"
    if plaintiff:
        return f"{plaintiff}{cause}"
    return (fields.get("case_number") or "").strip() or "未命名案件"


# =============================================
# Bot
# =============================================

class CaseBot:
    """飞书案件 Bot：命令 → 卡片；写操作统一走 case_service。"""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        identity=None,
        engine: Optional[str] = None,
        downloader=None,
        intake_dir: Optional[Path] = None,
        memory=None,
        llm=None,
        agent_graph=None,
    ):
        self.db_path = db_path
        self.identity = identity
        self.engine = engine or os.environ.get("LARK_BOT_ENGINE") or "minimax"
        self.bot_name = os.environ.get("LARK_BOT_NAME") or cards.DEFAULT_BOT_NAME
        # 会话记忆（C）：惰性创建，避免无用例触碰 .run/；可注入 fake 便于测试
        self._memory_store = memory
        self.memory_enabled = os.environ.get("LARK_MEMORY_ENABLED", "1") not in ("0", "false", "False")
        # LLM 客户端（A 兜底意图 / B agent 共用）：可注入 fake；None → 按 env 惰性创建
        self.llm = llm
        self.llm_enabled = os.environ.get("LARK_LLM_FALLBACK", "1") not in ("0", "false", "False")
        # B：ReAct agent（多步兜底）。agent_graph 可注入 fake → 单测不出网
        self.agent_graph = agent_graph
        self.agent_enabled = os.environ.get("LARK_AGENT_ENABLED", "1") not in ("0", "false", "False")
        self.agent_max_steps = int(os.environ.get("LARK_AGENT_MAX_STEPS") or agent.DEFAULT_MAX_STEPS)
        self._registry_store = None
        # 附件下载器：签名 (message_id, file_key, type_) -> bytes | None（由 transport 注入）
        self.downloader = downloader
        self.intake_dir = Path(
            intake_dir or os.environ.get("LARK_INTAKE_DIR") or ident.DEFAULT_STATE_DIR / "intake"
        )

    # ---------- 事件入口 ----------

    def dispatch(self, ev: dict) -> DispatchResult:
        """transport 入口：归一事件 → 命令 → 卡片/异步回执。"""
        kind = (ev or {}).get("kind")

        if kind == "bot_added":
            return self._result(cards.welcome_card(self.bot_name))

        if kind == "p2p_entered":
            # 用户打开单聊：首次欢迎（12h 内去重由 transport 负责），并暴露 open_id 便于授权
            logger.info("p2p_entered open_id=%s chat_id=%s", ev.get("open_id"), ev.get("chat_id"))
            return self._result(cards.welcome_card(self.bot_name))

        if kind == "message":
            if self._ignore_group(ev):
                return DispatchResult()
            text = (ev.get("text") or "").strip()
            attachments = ev.get("attachments") or []
            mtype = ev.get("message_type") or ""
            has_att = bool(attachments) or mtype in ("file", "image", "media")
            logger.info(
                "收到消息 open_id=%s chat_id=%s chat_type=%s attachments=%d text=%.60s",
                ev.get("open_id"), ev.get("chat_id"), ev.get("chat_type"),
                len(attachments), text,
            )
            chat_id = ev.get("chat_id") or ""
            explicit = parse_text(text) if text else None
            # 显式 `/` 命令优先：即便带附件，也执行命令而非吞成材料录入
            if explicit is not None:
                self._memory().remember(chat_id, "user", text)
                return self._remember_reply(self._dispatch_command(self._bind(explicit, ev)), chat_id)
            # 隐私红线：索取批量个人敏感信息 → 明确拒绝（不给通用引导卡）
            if text and _PRIVACY_REQ_RE.search(text):
                self._memory().remember(chat_id, "user", text)
                return self._remember_reply(self._result(cards.privacy_refuse_card()), chat_id)
            # 附件消息：不擅自处理 → 先弄清意图（暂存附件 + 询问「要怎么处理」）
            if has_att:
                return self._attachment_intake_or_ask(ev, text)
            if not text:
                return DispatchResult()
            # 有待处理附件时：先把用户这句话理解为「对这份材料怎么办」的指令
            if self._memory().pending(chat_id):
                act, ref = _attachment_instruction(text)
                if act == "ask":
                    # 含糊表达（仅「提到材料 + 分析动作」）→ 不擅自写入，回显理解请确认
                    self._memory().remember(chat_id, "user", text)
                    return self._remember_reply(self._result(self._confirm_intake(chat_id, "new")), chat_id)
                if act:
                    self._memory().remember(chat_id, "user", text)
                    name = {"new": "intake_confirm", "cancel": "intake_cancel",
                            "merge": "intake_merge"}[act]
                    return self._remember_reply(
                        self._dispatch_command(self._bind(Command(name=name, args=ref), ev)), chat_id)
                # 规则判不出 → 交 LLM 判断这句话是否在说这份材料；无 LLM 则重发意图卡
                client = self._llm_ready()
                if client is not None:
                    return self._dispatch_attachment_llm(text, ev, client)
                self._memory().remember(chat_id, "user", text)
                return self._result(self._reask_intake(chat_id))
            self._memory().remember(chat_id, "user", text)
            # 规则路由：动作明确 → 直接执行；引用不明 → 先让 LLM / agent 理解（规则结果仅兜底）
            it = intent.route(text)
            if it is not None and it.confident:
                cmd = Command(name=it.name, args=it.args, value=dict(it.value))
                return self._remember_reply(self._dispatch_command(self._bind(cmd, ev)), chat_id)
            client = self._llm_ready()
            if client is not None:
                return self._dispatch_llm(text, ev, client, fallback=it)
            if self._agent_ready():
                return self._dispatch_agent(text, ev, fallback=it)
            if it is not None:
                cmd = Command(name=it.name, args=it.args, value=dict(it.value))
                return self._remember_reply(self._dispatch_command(self._bind(cmd, ev)), chat_id)
            return self._remember_reply(self._result(cards.guide_card(self.bot_name)), chat_id)

        if kind == "card":
            payload = cards.parse_action(ev.get("action") or {})
            cmd = Command(name=str(payload["action"]))
            cmd.value = payload.get("value") or {}
            cmd.form = payload.get("form") or {}
            return self._dispatch_command(self._bind(cmd, ev))

        return DispatchResult()

    def handle_message(
        self, message: str, *, open_id: str = "", chat_id: str = "", chat_type: str = ""
    ) -> str:
        """文本模式（本地调试 / 无卡片通道）：执行命令并把卡片降级为文本。"""
        self._memory().remember(chat_id, "user", message)
        cmd = parse_text(message)
        if cmd is None:
            it = intent.route(message)
            if it is not None and it.confident:
                cmd = self._cmd_of(it)
        if cmd is None:
            reply = self._free_text_reply(message, open_id, chat_id, chat_type)
            self._memory().remember(chat_id, "assistant", self._reply_text(reply))
            return self._reply_text(reply)
        cmd.open_id, cmd.chat_id, cmd.chat_type = open_id, chat_id, chat_type
        result = self._dispatch_command(cmd)
        reply = result.immediate
        if result.deferred is not None:
            try:
                reply = result.deferred(None) or reply
            except Exception as e:  # noqa: BLE001
                logger.exception("异步任务失败")
                reply = Reply(kind="text", text=self._format_error(self._business_error(e)))
        text = self._reply_text(reply)
        self._memory().remember(chat_id, "assistant", text)
        return text

    def _free_text_reply(self, message: str, open_id: str, chat_id: str, chat_type: str) -> Reply:
        """文本模式的自由输入链路：规则（高置信）→ A（LLM 意图）→ B（ReAct agent）→ 规则兜底 → 引导卡。"""
        # 隐私红线：索取批量个人敏感信息 → 明确拒绝（与卡片通道一致）
        if message and _PRIVACY_REQ_RE.search(message):
            return Reply(kind="card", card=cards.privacy_refuse_card())
        it = intent.route(message)
        if it is not None and it.confident:
            return self._run_cmd_reply(self._cmd_of(it), open_id, chat_id, chat_type)
        client = self._llm_ready()
        if client is not None:
            it2 = intent.route_llm(message, client, context=self._context_for(chat_id))
            if it2 is not None:
                return self._run_intent_reply(it2, open_id, chat_id, chat_type, client)
        if self._agent_ready():
            ev = {"open_id": open_id, "chat_id": chat_id, "chat_type": chat_type, "message_id": "local"}
            return self._agent_task(message, ev, None, fallback=it)
        if it is not None:
            return self._run_cmd_reply(self._cmd_of(it), open_id, chat_id, chat_type)
        return Reply(kind="text", text=cards.flatten_text(cards.guide_card(self.bot_name)))

    def _run_cmd_reply(self, cmd: Command, open_id: str, chat_id: str, chat_type: str) -> Reply:
        """文本模式下执行一条命令并把结果压成一条 Reply。"""
        cmd.open_id, cmd.chat_id, cmd.chat_type = open_id, chat_id, chat_type
        out = self._dispatch_command(cmd)
        reply = out.immediate
        if out.deferred is not None:
            reply = out.deferred(None) or reply
        return reply

    def _run_intent_reply(self, it, open_id: str, chat_id: str, chat_type: str, client) -> Reply:
        """执行 A 路由出的意图，并在卡片标注来源。"""
        cmd = Command(name=it.name, args=it.args, value=dict(it.value))
        cmd.open_id, cmd.chat_id, cmd.chat_type = open_id, chat_id, chat_type
        out = self._dispatch_command(cmd)
        reply = out.immediate
        if out.deferred is not None:
            reply = out.deferred(None) or reply
        if reply.card:
            self._mark_llm_source(reply, client)
        return reply

    # ---------- 内部：绑定 / 分发 ----------

    @staticmethod
    def _bind(cmd: Command, ev: dict) -> Command:
        cmd.open_id = ev.get("open_id") or ""
        cmd.chat_id = ev.get("chat_id") or ""
        cmd.chat_type = ev.get("chat_type") or ""
        cmd.message_id = ev.get("message_id") or ""
        cmd.mentions = ev.get("mentions") or []
        return cmd

    @staticmethod
    def _result(card_json: dict) -> DispatchResult:
        return DispatchResult(immediate=Reply(kind="card", card=card_json))

    def _dispatch_command(self, cmd: Command) -> DispatchResult:
        required = ROLE_REQUIRED.get(cmd.name)
        if required is None:
            return self._result(cards.guide_card(self.bot_name))
        role = self._role_of(cmd)
        if ROLE_LEVELS.get(role, -1) < ROLE_LEVELS[required]:
            return self._result(cards.error_card(
                f"权限不足：`/case {cmd.name}` 需要 **{required}** 角色（当前 **{role}**）"
            ))
        handler = getattr(self, f"_op_{cmd.name}", None)
        if handler is None:
            return self._result(cards.error_card(f"命令未实现: {cmd.name}"))
        try:
            out = handler(cmd)
        except Exception as e:  # noqa: BLE001
            logger.exception("命令执行失败: %s", cmd.name)
            return self._result(cards.error_card(self._business_error(e)))
        if isinstance(out, DispatchResult):
            return out
        return self._result(out)

    def _role_of(self, cmd: Command) -> str:
        if self.identity is None:
            # 本地/CLI 单用户模式：无飞书网关注入，取默认角色（远端部署须注入 LARK_ROLE_MAP）
            return os.environ.get("LARK_DEFAULT_ROLE") or "admin"
        try:
            return self.identity.role_of(cmd.open_id, cmd.chat_id)
        except Exception:  # noqa: BLE001
            logger.exception("角色解析失败，降级 readonly")
            return "readonly"

    def _ignore_group(self, ev: dict) -> bool:
        """群聊默认须 @Bot 才响应（可配 LARK_REQUIRE_MENTION=0 关闭）。"""
        if (ev.get("chat_type") or "") != "group":
            return False
        if os.environ.get("LARK_REQUIRE_MENTION", "1") in ("0", "false", "False"):
            return False
        return not (ev.get("mentions") or [])

    def _reply_text(self, reply: Reply) -> str:
        if reply.kind in ("card", "card_update") and reply.card:
            text = cards.flatten_text(reply.card)
        else:
            text = reply.text or ""
        if reply.followup:                        # 追加卡（如案件要点）也计入文本回执
            extra = cards.flatten_text(reply.followup)
            text = f"{text}\n\n{extra}".strip() if text else extra
        return text

    # ---------- 会话记忆（C：指代补全） ----------

    def _memory(self):
        """惰性创建 SessionStore（无用例不触碰 .run/）；可注入 fake。"""
        if self._memory_store is None:
            from .lark_memory import SessionStore
            self._memory_store = SessionStore(enabled=self.memory_enabled)
        return self._memory_store

    def _remember_reply(self, result: DispatchResult, chat_id: str) -> DispatchResult:
        """把即时回执摘要记入会话；异步回执（deferred）由其自身在完成后记录。"""
        if result.deferred is not None:
            return result
        reply = result.immediate
        if reply and reply.kind in ("card", "text"):
            summary = self._reply_text(reply)
            if summary:
                self._memory().remember(chat_id, "assistant", summary)
        return result

    def _note_case(self, chat_id: str, case_id: str) -> None:
        """记住最近提及的案件 → 下一轮指代（「它的提取物呢」）可补全。"""
        self._memory().set_last_case(chat_id, case_id)

    def _ref_of(self, cmd: Command) -> str:
        """案件引用：显式 ref 优先；纯指代（它 / 这个 / 刚才那个）与口语填充词回退最近案件。"""
        ref = cmd.ref()
        if ref and not _is_pronoun(ref) and not _is_filler(ref):
            return ref
        return self._memory().last_case(cmd.chat_id)

    # ---------- LLM 兜底意图（A） ----------

    def _llm(self):
        """LLM 客户端：未启用返回 None（调度方据此直接回引导卡）。"""
        if not self.llm_enabled:
            return None
        if self.llm is None:
            from .lark_llm import LLMClient
            self.llm = LLMClient()
        return self.llm

    def _llm_ready(self):
        """可用才走 A 兜底（不可用 → 直接回引导卡，不浪费一次网络往返）。"""
        client = self._llm()
        if client is None:
            return None
        try:
            return client if client.available() else None
        except Exception:  # noqa: BLE001
            logger.exception("LLM 可用性探测失败")
            return None

    def _dispatch_llm(self, text: str, ev: dict, client, fallback=None) -> DispatchResult:
        """A：规则未命中 → LLM 兜底意图。异步（先回「想一下」，再替换为结果卡）。

        LLM 理解可能引入偏差 → 结果卡底部标注来源，提示用户核对。
        fallback：规则路由出的低置信意图（动作明确但引用不明）——LLM 也理解不了时用它兜底。
        """
        chat_id = ev.get("chat_id") or ""
        context = self._context_for(chat_id)

        def task(ack_message_id: Optional[str]) -> Reply:
            it = intent.route_llm(text, client, context=context)
            if it is None:
                # A 理解不了 → 升级到 B（多步 ReAct）；B 也不可用才回引导卡
                if self._agent_ready():
                    return self._agent_task(text, ev, ack_message_id, fallback=fallback)
                if fallback is not None:
                    return self._finalize(
                        self._dispatch_command(self._bind(self._cmd_of(fallback), ev)),
                        ack_message_id)
                self._memory().remember(chat_id, "assistant", "（未理解，回引导卡）")
                return self._card_update(cards.guide_card(self.bot_name), ack_message_id)
            cmd = self._bind(self._cmd_of(it), ev)
            reply = self._finalize(self._dispatch_command(cmd), ack_message_id)
            if reply.card:
                self._mark_llm_source(reply, client)
            self._memory().remember(chat_id, "assistant", self._reply_text(reply))
            return reply

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card("🕒 让我想一下…", "正在理解你的意思")),
            deferred=task,
        )

    @staticmethod
    def _cmd_of(it) -> Command:
        """Intent → Command。"""
        return Command(name=it.name, args=it.args, value=dict(it.value))

    def _finalize(self, out: DispatchResult, ack_message_id: Optional[str]) -> Reply:
        """把（可能带 deferred 的）命令结果压成一条可替换「处理中」卡的最终 Reply。"""
        reply = out.immediate
        if out.deferred is not None:
            reply = out.deferred(ack_message_id) or reply
        if reply.kind == "card_update" or not reply.card:
            return reply
        return self._card_update(reply.card, ack_message_id)

    def _dispatch_attachment_llm(self, text: str, ev: dict, client) -> DispatchResult:
        """待处理附件 + 规则判不出 → LLM 判断这句话是否在说「这份材料怎么办」（异步）。"""
        chat_id = ev.get("chat_id") or ""
        context = self._context_for(chat_id)

        def task(ack_message_id: Optional[str]) -> Reply:
            act, ref = intent.classify_attachment(text, client, context=context)
            self._memory().remember(chat_id, "user", text)
            if act in ("new", "merge"):
                # LLM 的写入判断也只是「理解」，不擅自执行 → 回显理解请确认
                card = self._confirm_intake(chat_id, act, ref)
                self._mark_llm_source(Reply(kind="card", card=card), client)
                self._memory().remember(chat_id, "assistant", self._reply_text(Reply(kind="card", card=card)))
                return self._card_update(card, ack_message_id)
            if act == "cancel":
                cmd = self._bind(Command(name="intake_cancel"), ev)
            else:
                # 与这份材料无关 → 回退常规意图链路（保留待处理附件）
                cmd = _intent_to_command(text)
                if cmd is None:
                    if self._agent_ready():
                        return self._agent_task(text, ev, ack_message_id)
                    self._memory().remember(chat_id, "assistant", "（未理解，回引导卡）")
                    return self._card_update(cards.guide_card(self.bot_name), ack_message_id)
                cmd = self._bind(cmd, ev)
            reply = self._finalize(self._dispatch_command(cmd), ack_message_id)
            if reply.card:
                self._mark_llm_source(reply, client)
            self._memory().remember(chat_id, "assistant", self._reply_text(reply))
            return reply

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card(
                "🕒 让我看看…", "正在理解你对这份材料的处理意图")),
            deferred=task,
        )

    def _reask_intake(self, chat_id: str) -> dict:
        """再问一次处理方式（无法判断用户意图时；不落乱码检索）。"""
        atts = (self._memory().pending(chat_id) or {}).get("attachments") or []
        if not atts:
            return cards.guide_card(self.bot_name)
        names = [a.get("file_name") or a.get("file_key") or "" for a in atts]
        return cards.intake_intent_card(len(atts), names, self.bot_name)

    def _confirm_intake(self, chat_id: str, act: str, ref: str = "") -> dict:
        """回显 Bot 对暂存材料的理解并请确认（含糊表达时；不擅自建案/并入）。"""
        atts = (self._memory().pending(chat_id) or {}).get("attachments") or []
        if not atts:
            return cards.guide_card(self.bot_name)
        names = [a.get("file_name") or a.get("file_key") or "" for a in atts]
        return cards.intake_confirm_card(len(atts), names, act=act, ref=ref, bot_name=self.bot_name)

    def _context_for(self, chat_id: str) -> str:
        """最近对话 + 当前案件 ID（截断）——供 LLM 理解「它 / 刚才那个」等指代。"""
        turns = self._memory().history(chat_id, limit=6)
        lines = [
            f"{'用户' if t.role == 'user' else '助手'}：{t.text[:120]}"
            for t in turns[:-1]                                  # 末轮即本次输入，勿重复
        ]
        case_id = self._memory().last_case(chat_id)
        if case_id:
            lines.append(f"（当前正操作的案件：{case_id}）")
        return "\n".join(lines[-5:])

    def _last_user_text(self, chat_id: str) -> str:
        """会话中最近一条用户输入（advise 未带显式 question 时的兜底）。"""
        try:
            for turn in reversed(self._memory().history(chat_id, limit=8)):
                if turn.role == "user" and turn.text.strip():
                    return turn.text.strip()
        except Exception:  # noqa: BLE001
            logger.exception("读取会话最近输入失败")
        return ""

    def _llm_note(self, client=None) -> str:
        return "🧠 由 AI 理解，请核对结果"

    @staticmethod
    def _mark_llm_source(reply: Reply, client) -> None:
        """卡片标注 AI 来源——**已有来源标记则不重复追加**（避免同屏两个 🧠）。"""
        if not reply.card:
            return
        text = cards.flatten_text(reply.card)
        if "🧠" in text:
            return
        cards.append_note(reply.card, CaseBot._llm_note(client))

    # ---------- ReAct agent（B） ----------

    def _agent_ready(self) -> bool:
        """廉价就绪判定：注入的 graph 直接可用；否则需 MINIMAX_API_KEY。"""
        if not self.agent_enabled:
            return False
        if self.agent_graph is not None:
            return True
        return bool(os.environ.get("MINIMAX_API_KEY"))

    def _registry(self):
        if self._registry_store is None:
            self._registry_store = agent.build_registry(self)
        return self._registry_store

    def _dispatch_agent(self, text: str, ev: dict, fallback=None) -> DispatchResult:
        """B：多步 agent。异步——先回「处理中」，再把结果替换上去。"""
        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card("🕒 正在处理…", "多步推理中，请稍候")),
            deferred=lambda ack: self._agent_task(text, ev, ack, fallback=fallback),
        )

    def _agent_task(self, text: str, ev: dict, ack_message_id: Optional[str], fallback=None) -> Reply:
        """执行一次 ReAct；失败/无回答 → 规则兜底 → 引导卡（不报「处理失败」）。"""
        chat_id = ev.get("chat_id") or ""
        cmd = self._bind(Command(name="agent"), ev)
        res = agent.run_agent(
            text,
            registry=self._registry(),
            role=self._role_of(cmd),
            cmd=cmd,
            history=self._context_for(chat_id),
            max_steps=self.agent_max_steps,
            graph=self.agent_graph,
        )
        if not res.ok:
            logger.info("agent 降级：%s", res.error)
            if fallback is not None:
                return self._finalize(
                    self._dispatch_command(self._bind(self._cmd_of(fallback), ev)),
                    ack_message_id)
            self._memory().remember(chat_id, "assistant", "（agent 未能处理，回引导卡）")
            return self._card_update(cards.guide_card(self.bot_name), ack_message_id)
        if policy.contains_leak(res.text):
            logger.warning("agent 输出命中保密红线，降级引导卡")
            self._memory().remember(chat_id, "assistant", "（agent 输出含非业务信息，回引导卡）")
            return self._card_update(cards.guide_card(self.bot_name), ack_message_id)
        self._memory().remember(chat_id, "assistant", res.text)
        return self._card_update(cards.agent_reply_card(
            res.text, res.steps, source="🤖 由 AI 助手生成",
        ), ack_message_id)

    # ---------- 案件引用解析（ID/案号精确 → 名称模糊） ----------

    def _resolve(self, ref: str, cmd: Optional[Command] = None) -> tuple:
        """ref → (case, candidates)：精确命中即返回；否则按名称模糊搜索（唯一命中直接采用）。

        命中即记入会话记忆（cmd 非空时），供下一轮指代补全。
        """
        case = svc.resolve_case(ref, self.db_path)
        if not case:
            case = self._find_by_normalized_number(ref)
        if not case:
            hits = svc.query_cases(search=ref, limit=8, db_path=self.db_path)
            if not hits and " " in ref:
                # 多词引用（案名含空格 / 案号格式有差异）→ 退化为按最长词搜索
                hits = svc.query_cases(search=max(ref.split(), key=len), limit=8, db_path=self.db_path)
            if not hits:
                # 案号前缀匹配：用户常只打前半截（「…23751号」vs「…23751号和23752号」）
                hits = self._find_by_number_prefix(ref)
            if not hits:
                # 模糊引用（「腾讯音乐那个案子」）→ 语料关键词找候选，避免死路
                hits = self._fuzzy_candidates(ref)
            if len(hits) != 1:
                return None, hits
            case = hits[0]
        if cmd is not None:
            self._note_case(cmd.chat_id, case["id"])
        return case, []

    def _fuzzy_candidates(self, ref: str, limit: int = 6) -> list:
        """模糊引用的候选案件：按语料关键词（「腾讯音乐」）检索去重后的案件。

        直接检索无果时兜底——比「没找到案件」死胡同友好：给出可点选的候选。
        """
        from . import corpus
        if not (ref or "").strip():
            return []
        try:
            hits = corpus.search(ref, limit=limit * 3, db_path=self.db_path)
        except Exception:  # noqa: BLE001
            logger.exception("语料候选检索失败")
            return []
        out: list = []
        seen: set = set()
        for h in hits:
            cid = h.get("case_id") or ""
            if not cid or cid in seen:
                continue
            case = svc.resolve_case(cid, self.db_path)
            if not case:
                continue
            seen.add(cid)
            out.append(case)
            if len(out) >= limit:
                break
        return out

    def _find_by_normalized_number(self, ref: str) -> Optional[dict]:
        """案号归一化比对：兜住空格 / 全半角 / 括号差异（如 `（2025）川 0193 民初 13392 号`）。"""
        norm = _normalize_ref(ref)
        if not norm or not re.search(r"\d", norm):
            return None
        for c in svc.query_cases(db_path=self.db_path):
            for key in ("case_number", "case_name"):
                if _normalize_ref(c.get(key) or "") == norm:
                    return c
        return None

    def _find_by_number_prefix(self, ref: str) -> list:
        """案号**前缀**匹配：用户只打前半截案号时也能定位（如 `…23751号` → `…23751号和23752号`）。"""
        key = _number_key(ref)
        if not key or not re.search(r"\d", key) or len(key) < 6:
            return []
        out = []
        for c in svc.query_cases(db_path=self.db_path):
            for field in ("case_number", "case_name"):
                ck = _number_key(c.get(field) or "")
                if ck and (ck.startswith(key) or key.startswith(ck)):
                    out.append(c)
                    break
        return out

    def _ask_case_card(self, cmd: Optional[Command] = None) -> dict:
        """缺案件引用：正常追问（非报错），给自然语言示例。

        上一轮刚给了候选清单时 → 重发候选卡（可点选 / 回序号），而不是再问一遍「哪一案」。
        """
        cand = self._memory().candidates(cmd.chat_id) if cmd is not None else {}
        items = cand.get("items") or []
        if items:
            hits = [svc.resolve_case(i.get("case_id") or "", self.db_path) or i for i in items]
            hits = [h for h in hits if h]
            if hits:
                return cards.candidate_card(
                    hits, cand.get("action") or "",
                    f"❓ 找到 {len(hits)} 个相关案件",
                )
        return self._recent_cases_card(cmd)

    def _recent_cases_card(self, cmd: Optional[Command] = None, limit: int = 3) -> dict:
        """没有线索时给「最近案件」快捷入口（可点选），而不是让人从零描述。"""
        try:
            recent = svc.query_cases(limit=limit, db_path=self.db_path)
        except Exception:  # noqa: BLE001
            logger.exception("最近案件查询失败")
            recent = []
        return cards.ask_case_card(recent)

    def _ref_miss_card(self, ref: str, hits: list, cmd: Optional[Command] = None,
                       action: str = "") -> dict:
        """未命中 / 命中多个时的回执：多个给**可点选**候选卡，零个给友好提示（非「处理失败」）。

        引用过长（整句啰嗦话）时不回显——避免「没找到「结合原告文件 让你 …」」这类乱码串。
        """
        if hits:
            if cmd is not None:
                self._memory().set_candidates(cmd.chat_id, hits, action)
            uniq, merged = _dedupe_cases(hits)
            note = f"已合并 {merged} 条同案号的重复登记" if merged else ""
            return cards.candidate_card(uniq, action, f"❓ 找到 {len(uniq)} 个相关案件",
                                        note=note)
        shown = ref if 0 < len(ref.strip()) <= 20 else ""
        body = (f"没找到「{shown}」。换个案件名或案号试试？"
                if shown else "没听清你要查哪个案件，请提供**案件名称或案号**。")
        return cards.notice_card(
            "🔍 未找到案件",
            body + " 也可以先说「登记一个新案件」。",
            template=cards.ORANGE,
        )

    # ---------- 只读命令 ----------

    def _op_list(self, cmd: Command) -> dict:
        year = intent.normalize_year(cmd.args.strip()) if cmd.args.strip() else None
        cases = svc.query_cases(filters={"year": year} if year else None, db_path=self.db_path)
        # 列表同样可回序号（「第3个」）→ 记候选，选中后出该案详情
        self._memory().set_candidates(cmd.chat_id, cases, "detail")
        ordered = _sort_cases_by_meaning(cases)
        shells = len(cases) - len([c for c in cases if not _is_shell_case(c)])
        title = f"📋 案件列表 · {year}年" if year else "📋 案件列表"
        if shells:
            title += f"（{shells} 条无案号记录已排到末尾）"
        return cards.case_list_card(ordered[:PAGE_SIZE], title, total=len(cases))

    def _op_search(self, cmd: Command) -> dict:
        keyword = cmd.args.strip()
        if not keyword:
            return cards.error_card("请提供搜索关键词，如 `/case search 腾讯`")
        cases = svc.query_cases(search=keyword, limit=10, db_path=self.db_path)
        if not cases:
            # 法条 / 法规类关键词 → 引导到法规检索（本地库优先），而不是死路
            if intent.is_law_topic(keyword):
                return self._op_law_lookup(cmd)            # 本地语料检索：可能命中的是**提取物正文**而非案件字段
            from . import corpus
            try:
                hits = corpus.search(keyword, limit=5, db_path=self.db_path)
            except Exception:  # noqa: BLE001
                logger.exception("语料检索失败")
                hits = []
            if hits:
                els = [cards.div(f"案件字段里没有「{keyword}」，但**提取物正文**里有相关记录："), cards.hr()]
                for i, h in enumerate(hits, 1):
                    src = " ".join(x for x in (h.get("case_name") or "", h.get("case_number") or "") if x)
                    els.append(cards.div(
                        f"**[{i}] {src or '（未命名案件）'}**"
                        + (f" · {h.get('artifact_title')}" if h.get("artifact_title") else "")
                        + f"\n{(h.get('snippet') or '')[:200]}"
                    ))
                return cards.card("🔍 搜索结果 · 提取物正文", *els)
            return cards.notice_card(
                "🔍 未找到相关记录",
                f"本地案件库与提取物正文中都没有「{keyword}」。\n"
                "换个关键词试试，或把材料发到会话，我先按五维提取再分析。",
                template=cards.ORANGE,
            )
        # 搜索结果同样可回序号（「第3个」）→ 记候选，选中后出该案详情
        uniq, merged = _dedupe_cases(cases)
        self._memory().set_candidates(cmd.chat_id, uniq, "detail")
        title = f"🔍 搜索结果 · {keyword}"
        if merged:
            title += f"（已合并 {merged} 条同案号重复登记）"
        return cards.case_list_card(uniq, title, total=len(uniq))

    def _op_detail(self, cmd: Command) -> dict:
        ref = self._ref_of(cmd)
        if not ref:
            return self._ask_case_card(cmd)
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._ref_miss_card(ref, hits, cmd, "detail")
        detail = svc.get_case_detail(case["id"], self.db_path)
        return cards.case_detail_card(detail, mask=self._mask_for(cmd))

    def _op_artifacts(self, cmd: Command) -> dict:
        """提取物列表（含正文摘要）——不再是「只有维度名」的干巴巴列表。"""
        ref = self._ref_of(cmd)
        if not ref:
            return self._ask_case_card(cmd)
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._ref_miss_card(ref, hits, cmd, "artifacts")
        artifacts = svc.list_artifacts(case["id"], self.db_path)
        if not artifacts:
            return cards.notice_card(
                "📦 该案暂无提取物",
                f"**{case.get('case_name')}** 还没有做五维提取，暂时没有可看的材料分析。\n"
                "可在案件详情里点「提取五维」，或把材料发到会话后说「提取一下」。",
                template=cards.ORANGE,
            )
        return cards.artifacts_card(case, artifacts, mask=self._mask_for(cmd))

    def _op_artifact_content(self, cmd: Command) -> dict:
        """提取物**正文**（各维度详细分析）——用户要「详细信息」时给正文，而非维度名。"""
        ref = self._ref_of(cmd)
        if not ref:
            return self._ask_case_card(cmd)
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._ref_miss_card(ref, hits, cmd, "artifact_content")
        bundle = svc.case_bundle(case["id"], db_path=self.db_path) or {}
        artifacts = bundle.get("artifacts") or []
        if not artifacts:
            return cards.notice_card(
                "📦 该案暂无提取物",
                f"**{case.get('case_name')}** 还没有做五维提取，暂时没有可看的正文。\n"
                "可在案件详情里点「提取五维」，或把材料发到会话后说「提取一下」。",
                template=cards.ORANGE,
            )
        idx = 0
        try:
            idx = int(cmd.value.get("index") or 0)
        except (TypeError, ValueError):
            idx = 0
        if idx and 1 <= idx <= len(artifacts):
            return cards.artifact_detail_card(case, artifacts[idx - 1], mask=self._mask_for(cmd))
        # 未指定维度 → 给出全部维度正文（过长则截断，标注重续）
        els = [cards.div(f"**{case.get('case_name')}** 共 {len(artifacts)} 份提取物正文"), cards.hr()]
        for i, a in enumerate(artifacts, 1):
            label = cards.artifact_label(a.get("type") or a.get("artifact_type") or "")
            title = cards.clean_artifact_title(a.get("title") or "")
            head = f"{i}. {label}" + (f" · {title}" if title and title != label else "")
            body = (a.get("content") or "").strip() or "（该维度暂无正文）"
            if len(body) > 800:
                body = body[:800].rstrip() + "…"
            els.append(cards.div(f"**{head}**\n{body}"))
        return cards.card("📄 提取物正文", *els)

    # ---------- 候选消歧（点选 / 序号） ----------

    def _op_select(self, cmd: Command) -> dict:
        """序号选中候选案件（「第3个」）→ 记入会话并**续跑**原动作。"""
        try:
            idx = int((cmd.args or "").strip())
        except (TypeError, ValueError):
            idx = 0
        if not idx:
            return cards.notice_card(
                "🔎 请给出序号",
                "请回复候选序号（如「第3个」），或直接点击上方候选案件。",
            )
        cand = self._memory().candidates(cmd.chat_id) or {}
        items = cand.get("items") or []
        if not items:
            return cards.notice_card(
                "🔎 没有待选的候选案件", "请先说出要查的案件名称或案号。")
        if idx < 1 or idx > len(items):
            return cards.notice_card(
                "🔎 序号超出范围", f"当前共有 {len(items)} 个候选，请回复 1~{len(items)} 之间的序号。")
        item = items[idx - 1]
        return self._select_case(cmd, str(item.get("case_id") or ""), str(cand.get("action") or ""))

    def _op_select_case(self, cmd: Command) -> dict:
        """候选卡按钮点选 → 续跑原动作。"""
        case_id = str(cmd.value.get("case_id") or "")
        if not case_id:
            return cards.error_card("候选信息已失效，请重新检索一次。")
        return self._select_case(cmd, case_id, str(cmd.value.get("next") or ""))

    def _select_case(self, cmd: Command, case_id: str, action: str) -> dict:
        """选中案件：写会话记忆 → 按原动作续跑（没有原动作则回案件详情）。"""
        case = svc.resolve_case(case_id, self.db_path)
        if not case:
            self._memory().clear_candidates(cmd.chat_id)
            return cards.error_card("该案件不存在或已被删除，请重新检索一次。")
        self._note_case(cmd.chat_id, case_id)
        self._memory().clear_candidates(cmd.chat_id)
        name = action if action.startswith("_op_") else f"_op_{action}"
        handler = getattr(self, name, None) if action else None
        if handler is None:
            handler = self._op_detail
        sub = replace(cmd, name=handler.__name__[4:], args="",
                      value={**cmd.value, "case_id": case_id})
        return handler(sub)

    def _op_report(self, cmd: Command) -> dict:
        return cards.report_card(svc.summary(self.db_path))

    def _op_stats(self, cmd: Command) -> dict:
        """维度化统计（聚合问法）：年份分布 / 无案号计数 / 提取进度 / 案由 / 法院 / 质量。"""
        dim = str((cmd.value or {}).get("dim") or "year").strip().lower()
        try:
            data = svc.stats(dim, self.db_path)
        except Exception:  # noqa: BLE001
            logger.exception("维度统计失败")
            return cards.notice_card(
                "📊 统计",
                "统计时出现异常，请稍后再试，或说「统计一下」看总体报告。",
                template=cards.ORANGE,
            )
        return cards.stats_card(data)

    def _op_web_search(self, cmd: Command) -> dict:
        """业务相关的联网检索（法律法规 / 司法解释 / 赔偿标准等）；失败优雅降级。

        🔴 本地优先：联网不可用（网络受限）或无结果时，回退到**本地案例库**证据，
        绝不以「处理失败」结束。
        """
        from . import corpus, lark_websearch as ws

        query = (cmd.args or cmd.ref() or "").strip() or self._last_user_text(cmd.chat_id)
        if not query:
            return cards.notice_card(
                "🌐 联网检索",
                "请说明要检索的内容，例如「最新的人身损害赔偿标准」。",
                template=cards.ORANGE,
            )
        results = ws.search(query)
        if results:
            return cards.web_search_card(query, results)
        ev = corpus.evidence(query, db_path=self.db_path)
        if ev.get("hits"):
            return cards.corpus_answer_card(
                "联网检索当前不可用，以下是**本地案例库**中的相关记录（未作解读，请核对原文）。",
                ev,
                source="📚 来自本地案例库，请核对",
            )
        return cards.notice_card(
            "🌐 联网检索",
            f"联网检索当前不可用，本地案例库也未命中「{query}」。\n"
            "可换个关键词，或把相关材料发我，入库后再行分析。",
            template=cards.ORANGE,
        )

    def _op_law_lookup(self, cmd: Command) -> dict:
        """法规检索：先查**本地法规库**（离线、不外传）；未命中再联网检索；都空则如实告知。

        🔴 不臆造法条：本地命中即回原文（标注「本地法规库」）；未命中只给联网结果 / 友好提示。
        """
        from . import lark_websearch as ws
        from . import legal_kb

        query = (cmd.args or cmd.ref() or "").strip() or self._last_user_text(cmd.chat_id)
        if not query:
            return cards.notice_card(
                "📚 法规检索",
                "请说明要查的法条或关键词，例如「著作权法第24条」「信息网络传播权 合理使用」。",
            )
        hits = legal_kb.search(query, limit=5)
        if hits:
            body = "\n\n".join(f"**【{h.article}】**\n{h.text}" for h in hits)
            return cards.answer_card(
                f"📚 {self.bot_name} · 法规检索", body,
                source="📚 来自本地法规库，请以官方文本为准",
            )
        results = ws.search(query)
        if results:
            return cards.web_search_card(
                query, results, source="🌐 本地法规库未收录，已联网检索；请核对官方文本",
            )
        return cards.notice_card(
            "📚 法规检索",
            f"本地法规库与联网检索都未命中「{query}」。\n"
            "可换个关键词，或把该法规原文发我，导入后即可离线查询。",
            template=cards.ORANGE,
        )

    def _op_compare(self, cmd: Command) -> dict:
        """两案对比：「对比一下 A 和 B」→ 并排呈现两案的档案 + 提取物要点。

        引用拆分失败（说不清是哪两案）→ 回追问卡，不瞎猜。
        """
        text = (cmd.args or cmd.ref() or "").strip()
        parts = _split_compare_refs(text)
        if len(parts) != 2:
            return cards.notice_card(
                "🔀 案件对比",
                "请明确要对比的**两个**案件，例如「对比一下腾讯案和纽凯诉雷客案」。",
                template=cards.ORANGE,
            )
        a, hits_a = self._resolve(parts[0], cmd)
        b, hits_b = self._resolve(parts[1])
        if a and b:
            ba = svc.case_bundle(a["id"], db_path=self.db_path) or {}
            bb = svc.case_bundle(b["id"], db_path=self.db_path) or {}
            return cards.compare_card(a, ba, b, bb)
        # 一方未命中：说清**缺哪一方**、另一方是否已匹配，并给可操作出路
        if not a:
            missing_ref, missing_hits, other_ref, other, other_hits = parts[0], hits_a, parts[1], b, hits_b
        else:
            missing_ref, missing_hits, other_ref, other, other_hits = parts[1], hits_b, parts[0], a, hits_a
        if missing_hits:                      # 多命中：给可点选候选
            return self._ref_miss_card(missing_ref, missing_hits, cmd, "compare")
        body = f"未找到案件「{missing_ref}」，无法完成对比。"
        if other:
            body += (f"另一方已匹配：**{other.get('case_name') or ''}**"
                     f"（{other.get('case_number') or '无案号'}）。\n")
        elif other_hits:
            body += f"另一方「{other_ref}」匹配到 {len(other_hits)} 个案件，请先指明其一。\n"
        body += ("请给出准确的案件名称或案号（如「(2024)京0491民初123号」）；"
                 "若该案尚未入库，可先把材料发到会话建案。")
        return cards.notice_card("🔀 案件对比", body, template=cards.ORANGE)

    def _op_corpus(self, cmd: Command) -> dict:
        """本地案例库经验问答：检索库内证据 → LLM **基于证据**作答 → 标注出处。

        🔴 不编造：无命中即如实告知；LLM 不可用时只列证据（不给结论）。
        """
        from . import corpus

        question = (cmd.args or cmd.ref() or "").strip() or self._last_user_text(cmd.chat_id)
        if not question:
            return cards.corpus_empty_card("（未识别到问题）")
        try:
            ev = corpus.evidence(question, db_path=self.db_path)
        except Exception:  # noqa: BLE001
            logger.exception("本地语料检索失败")
            return cards.notice_card(
                "📚 本地案例库检索失败",
                "检索本地案例库时出现异常，请稍后再试，或直接指定案件名称 / 案号。",
                template=cards.ORANGE,
            )
        hits = (ev or {}).get("hits") or []
        if not hits:
            return cards.corpus_empty_card(question)
        client = self._llm_ready()
        answer = ""
        if client is not None:
            answer = intent.corpus_llm(
                question, corpus.evidence_text(ev), client, context=self._context_for(cmd.chat_id)
            ) or ""
            if answer and policy.contains_leak(answer):
                logger.warning("corpus 输出命中保密红线，降级为纯证据")
                answer = ""
        if not answer:
            # 无 AI 解读也要「有理有据」：只给可核查的证据清单
            answer = "本地案例库检索到以下相关记录（未做 AI 解读，可按需继续下钻）："
        return cards.corpus_answer_card(answer, ev)

    def _op_templates(self, cmd: Command) -> dict:
        args = cmd.args.strip()
        if args.startswith("show "):
            template = svc.get_template(args[5:].strip(), self.db_path)
            if not template:
                return cards.error_card(f"未找到模板: {args[5:].strip()}")
            return cards.template_detail_card(template)
        if args.startswith("search "):
            query = args[7:].strip()
            items = svc.search_templates(query, self.db_path)
            return cards.templates_card(items, f"🗂 模板搜索 · {query}")
        return cards.templates_card(svc.list_templates(db_path=self.db_path))

    def _op_match(self, cmd: Command) -> dict:
        tokens = cmd.args.split()
        limit = 5
        if tokens and tokens[-1].isdigit():
            limit = max(1, min(20, int(tokens[-1])))
            ref = " ".join(tokens[:-1])
        else:
            ref = self._ref_of(cmd)
        if not ref:
            return self._ask_case_card(cmd)
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._ref_miss_card(ref, hits, cmd, "match")
        return cards.match_card(case, svc.match_cases(case["id"], limit=limit, db_path=self.db_path))

    def _op_help(self, cmd: Command) -> dict:
        return cards.help_card(self.bot_name)

    def _op_say(self, cmd: Command) -> dict:
        """LLM 兜底的自然语言回复（tool=none）——非业务命令，只回话。

        输出侧再兜一道：命中保密红线（系统 / 技术 / 他人信息等）→ 降级引导卡。
        """
        text = (cmd.args or cmd.ref() or "").strip()
        if not text:
            return cards.greeting_card(self.bot_name)
        if policy.contains_leak(text):
            logger.warning("say 输出命中保密红线，降级引导卡")
            return cards.guide_card(self.bot_name)
        return cards.answer_card(f"💬 {self.bot_name}", text)

    def _op_advise(self, cmd: Command) -> DispatchResult:
        """业务方法性咨询（怎么做 / 需要什么材料 / 流程）：优先 LLM 结合本模块能力作答；
        不可用或输出越界 → 回静态「业务指南」卡。异步（先「让我看看」，再替换结果）。"""
        question = (cmd.args or cmd.ref() or "").strip() or self._last_user_text(cmd.chat_id)
        chat_id = cmd.chat_id or ""

        def task(ack_message_id: Optional[str]) -> Reply:
            client = self._llm_ready()
            text = ""
            if client is not None:
                text = intent.advise_llm(question, client, context=self._context_for(chat_id)) or ""
            if text and not policy.contains_leak(text):
                self._memory().remember(chat_id, "assistant", text)
                return self._card_update(
                    cards.answer_card(f"💬 {self.bot_name}", text, source="🧠 由 AI 生成，请核对"),
                    ack_message_id,
                )
            card = cards.advise_fallback_card(self.bot_name)
            self._memory().remember(chat_id, "assistant", cards.flatten_text(card))
            return self._card_update(card, ack_message_id)

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card("🕒 让我看看…", "正在整理相关说明")),
            deferred=task,
        )

    def _op_discuss(self, cmd: Command) -> DispatchResult:
        """就某案件开放式提问 / 讨论：基于该案**证据包**有据作答（不编造）。

        证据包由 case_service.case_bundle 生成（案件字段 + 提取物正文），LLM 只做推理与表达；
        无案件 → 追问；无提取物 → 提示先提取；LLM 不可用 / 输出越界 → 提示卡降级。
        """
        question = (cmd.value.get("question") or "").strip() or self._last_user_text(cmd.chat_id) \
            or (cmd.args or "").strip()
        ref = self._ref_of(cmd)
        if not ref:
            return self._result(self._ask_case_card(cmd))
        chat_id = cmd.chat_id or ""

        def task(ack_message_id: Optional[str]) -> Reply:
            case, hits = self._resolve(ref, cmd)
            if not case:
                return self._card_update(self._ref_miss_card(ref, hits, cmd, "discuss"), ack_message_id)
            bundle = svc.case_bundle(case["id"], db_path=self.db_path) or {}
            if not bundle.get("artifacts"):
                card = cards.notice_card(
                    "📄 该案还没有提取物",
                    f"{case.get('case_name')} 尚未做五维提取，暂时没有可分析的材料。\n"
                    "可先执行提取（`/case extract`），完成后再说「分析一下…」。",
                )
                self._memory().remember(chat_id, "assistant", cards.flatten_text(card))
                return self._card_update(card, ack_message_id)
            client = self._llm_ready()
            text = ""
            if client is not None:
                text = intent.discuss_llm(
                    question, bundle.get("text", ""), client, context=self._context_for(chat_id)
                ) or ""
            if text and not policy.contains_leak(text):
                self._memory().remember(chat_id, "assistant", text)
                return self._card_update(
                    cards.answer_card(f"💬 {self.bot_name} · 分析", text,
                                      source="🧠 基于该案材料的 AI 分析，请核对"),
                    ack_message_id,
                )
            card = cards.notice_card(
                "🤔 暂时无法展开分析",
                "AI 分析当前不可用。可先自行查看该案提取物（`/case artifacts`），稍后再试。",
                template=cards.ORANGE,
            )
            self._memory().remember(chat_id, "assistant", cards.flatten_text(card))
            return self._card_update(card, ack_message_id)

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card("🕒 正在翻材料…", "基于该案证据做分析")),
            deferred=task,
        )

    def _mask_for(self, cmd: Command) -> bool:
        return (cmd.chat_type or "") == "group"

    # ---------- 管理（admin） ----------

    def _audit(self, cmd: Command, action: str, case_id: str = "", result: str = "") -> None:
        """写审计（SPEC §8）：写入 / 生成 / 删除必录；失败不阻断业务。"""
        ident.record_audit(
            action=action,
            open_id=cmd.open_id or "(local)",
            role=self._role_of(cmd),
            case_id=case_id,
            result=result,
            db_path=self.db_path,
        )

    def _op_roles(self, cmd: Command) -> dict:
        if self.identity is None:
            return cards.notice_card(
                "🔐 角色映射",
                "当前为**本地单用户模式**（未注入 Identity）：全部命令按 "
                f"`LARK_DEFAULT_ROLE`（{os.environ.get('LARK_DEFAULT_ROLE') or 'admin'}）放行。\n"
                "远端部署请配置 `LARK_ROLE_MAP` 或 `.run/bot/roles.json`。",
            )
        return cards.roles_card(self.identity.snapshot())

    def _op_role_set(self, cmd: Command) -> dict:
        tokens = cmd.args.split()
        if len(tokens) < 2:
            return cards.error_card("用法：`/case role ＜open_id＞ ＜readonly|writer|generator|admin＞`")
        if self.identity is None:
            return cards.error_card("当前为本地单用户模式，未配置 Identity，无法维护角色映射")
        try:
            self.identity.set_role(tokens[0], tokens[1])
        except ValueError as e:
            return cards.error_card(str(e))
        self._audit(cmd, "role_set", result=f"{tokens[0]}→{tokens[1].lower()}")
        return cards.roles_card(self.identity.snapshot())

    def _op_audit(self, cmd: Command) -> dict:
        tokens = cmd.args.split()
        limit = int(tokens[0]) if tokens and tokens[0].isdigit() else 20
        return cards.audit_card(ident.list_audit(max(1, min(200, limit)), self.db_path))

    def _op_delete(self, cmd: Command) -> dict:
        ref = self._ref_of(cmd)
        if not ref:
            return self._ask_case_card(cmd)
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._ref_miss_card(ref, hits, cmd, "delete")
        svc.delete_case(case["id"], purge_files=True, db_path=self.db_path)
        self._audit(cmd, "delete", case["id"], "deleted")
        self._memory().clear_last_case(cmd.chat_id)
        return cards.notice_card(
            "🗑 案件已删除",
            f"{case.get('case_name')}\nID: {case.get('id')}（含提取物文件）",
            template=cards.ORANGE,
        )

    # ---------- 登记（表单卡 / 确认卡 / 结果卡） ----------

    def _insight_card(self, case_id: str, *, with_llm: bool = False):
        """案件要点卡（主动反馈，SPEC §5.6）：任何失败静默返回 None，不阻断主流程。"""
        if not case_id:
            return None
        try:
            insight = svc.case_insight(case_id, db_path=self.db_path)
            if not insight:
                return None
            notes, source = "", ""
            client = self._llm_ready() if with_llm else None
            if client is not None:
                bundle = svc.case_bundle(case_id, db_path=self.db_path) or {}
                text = intent.insight_llm(insight, bundle.get("text", ""), client) or ""
                if text and not policy.contains_leak(text):
                    notes, source = text, "🧠 由 AI 生成，请核对"
            return cards.insight_card(insight, notes, source=source)
        except Exception:  # noqa: BLE001
            logger.exception("案件要点卡生成失败（已跳过）")
            return None

    def _result_with_insight(self, card_json: dict, case_id: str) -> DispatchResult:
        """主结果卡 + 追加「案件要点」卡（规则摘要，同步、无 LLM，不拖慢回执）。"""
        out = self._result(card_json)
        out.immediate.followup = self._insight_card(case_id)
        return out

    def _op_register(self, cmd: Command) -> Union[dict, DispatchResult]:
        prefill = parse_fields(cmd.args)
        if prefill.get("case_number") and (prefill.get("plaintiff") or prefill.get("case_name")):
            return self._op_register_submit(replace(cmd, name="register_submit", form=prefill))
        return cards.register_form_card(prefill)

    def _op_register_submit(self, cmd: Command) -> Union[dict, DispatchResult]:
        fields = dict(cmd.form or cmd.value.get("fields") or {})
        fields = {k: (v.strip() if isinstance(v, str) else v) for k, v in fields.items()}
        if not (fields.get("case_number") or fields.get("plaintiff") or fields.get("case_name")):
            return cards.error_card("请至少填写案号，或原告与被告")
        fields["case_name"] = (fields.get("case_name") or "").strip() or _derive_case_name(fields)
        fields["entry_method"] = fields.get("entry_method") or "Bot"

        dup = svc.check_duplicate(fields, self.db_path)
        # 硬命中（案号/当事人）→ 先确认；仅案由相近 → 登记后在结果卡提示
        if dup.get("exact") or dup.get("partial"):
            return cards.duplicate_confirm_card(fields, dup)

        case = svc.register_case(fields, self.db_path)
        self._note_case(cmd.chat_id, case["id"])
        self._audit(cmd, "register", case["id"], f"案号={case.get('case_number') or '-'}")
        similar = dup.get("cause_fuzzy") or []
        hint = f"另有 {len(similar)} 个案由相近的案件，可用 `/case match` 查看" if similar else ""
        return self._result_with_insight(cards.register_result_card(case, hint=hint), case["id"])

    def _op_register_confirm(self, cmd: Command) -> Union[dict, DispatchResult]:
        fields = dict(cmd.value.get("fields") or cmd.form or {})
        if not fields:
            return cards.error_card("登记信息已丢失，请重新填写 `/case register`")
        fields.setdefault("entry_method", "Bot")
        fields.setdefault("case_name", _derive_case_name(fields))
        case = svc.register_case(fields, self.db_path)
        self._note_case(cmd.chat_id, case["id"])
        self._audit(cmd, "register_confirm", case["id"], "forced")
        return self._result_with_insight(
            cards.register_result_card(case, hint="（已确认：识别到疑似重复，仍按新案登记）"), case["id"])

    def _op_register_cancel(self, cmd: Command) -> dict:
        return cards.notice_card("已取消登记", "未写入任何数据。")

    # ---------- 写入（异步） ----------

    def _op_extract(self, cmd: Command) -> DispatchResult:
        ref = self._ref_of(cmd)
        if not ref:
            return self._result(self._ask_case_card(cmd))
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._result(self._ref_miss_card(ref, hits, cmd, "extract"))
        source_path = (case.get("source_path") or "").strip()
        if not source_path or not Path(source_path).is_dir():
            return self._result(cards.notice_card(
                "📄 该案暂无可提取的原始材料",
                f"**{case.get('case_name') or '该案件'}** 还没有关联到可用的材料文件，"
                "因此暂时无法做五维提取。\n"
                "把起诉状 / 证据材料（PDF、DOCX）直接发到会话，我会自动补进这个案件，再执行提取。",
                template=cards.ORANGE,
            ))
        engine = cmd.value.get("engine") or self.engine
        case_id = case["id"]

        def task(ack_message_id: Optional[str]) -> Reply:
            try:
                report = svc.extract_into_case(case_id, engine=engine, db_path=self.db_path)
            except Exception as e:  # noqa: BLE001
                self._audit(cmd, "extract", case_id, f"失败: {e}")
                raise
            self._audit(cmd, "extract", case_id, f"提取物={len(report.get('artifact_ids') or [])}")
            reply = self._card_update(cards.extract_result_card(case, report), ack_message_id)
            reply.followup = self._insight_card(case_id, with_llm=True)
            return reply

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card(
                "🕒 提取中…", f"案件：{case.get('case_name') or case_id}　方式：{cards.engine_label(engine)}"
            )),
            deferred=task,
        )

    def _op_generate(self, cmd: Command) -> dict:
        doc_type = cmd.value.get("doc_type") or ""
        engine = cmd.value.get("engine") or ""
        tokens = cmd.args.split()
        ref = self._ref_of(cmd)
        # 文本形式 `/case generate ＜案件＞ ＜doc_type＞ ＜engine＞`：仅当第 2 个 token 是已知类型才切分
        if not doc_type and len(tokens) > 1 and tokens[1] in _doc_types():
            doc_type = tokens[1]
            engine = engine or (tokens[2] if len(tokens) > 2 else "")
            ref = tokens[0]
        if not ref:
            return self._ask_case_card(cmd)
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._ref_miss_card(ref, hits, cmd, "generate")
        if doc_type not in _doc_types():
            return cards.generate_form_card(case, _doc_types(), _engines())
        return self._run_generate(cmd, case, doc_type, engine)

    def _op_generate_run(self, cmd: Command) -> DispatchResult:
        case_id = cmd.value.get("case_id") or ""
        case = svc.resolve_case(case_id, self.db_path)
        if not case:
            return self._result(cards.error_card(f"未找到案件: {case_id}"))
        self._note_case(cmd.chat_id, case_id)
        return self._run_generate(cmd, case, cmd.value.get("doc_type") or "", cmd.value.get("engine") or "")

    def _run_generate(self, cmd: Command, case: dict, doc_type: str, engine: str) -> DispatchResult:
        doc_type = doc_type or _doc_types().get("defense", "defense")
        engine = engine or self.engine
        case_id = case["id"]

        def task(ack_message_id: Optional[str]) -> Reply:
            result = svc.generate_document(case_id, doc_type, engine=engine, db_path=self.db_path)
            ok = bool(getattr(result, "success", False))
            self._audit(cmd, "generate", case_id,
                        f"{doc_type}/{'ok' if ok else 'fail'}/source={getattr(result, 'source', '')}")
            if ok:
                # 全文入会话记忆 → 用户问「怎么看完整内容」时可分段续看（pos 从预览末尾接续）
                content = getattr(result, "content", "") or ""
                self._memory().set_last_doc(cmd.chat_id, content, case_id=case_id)
                if len(content) > DOC_CHUNK_CHARS:
                    self._memory().set_doc_pos(cmd.chat_id, DOC_CHUNK_CHARS)
            return self._card_update(cards.generate_result_card(result, case), ack_message_id)

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card(
                "🕒 生成中…",
                f"{case.get('case_name') or case_id} · {_doc_types().get(doc_type, doc_type)} · `{engine}`",
            )),
            deferred=task,
        )

    def _op_doc_more(self, cmd: Command) -> dict:
        """文书续看：按会话记忆里的最近文书逐段发全文（不再让用户去 CLI/UI 看）。"""
        doc = self._memory().last_doc(cmd.chat_id)
        text = str((doc or {}).get("text") or "")
        if not text:
            return cards.notice_card(
                "📄 暂无待续看的文书",
                "先生成一份文书（例如「起草腾讯案的答辩状」），内容较长时我会分多段发送，"
                "说「**继续看**」即可逐段查看全文。",
                template=cards.ORANGE,
            )
        pos = int((doc or {}).get("pos") or 0)
        if pos >= len(text):
            return cards.doc_more_card("（全文已全部显示）", len(text), len(text))
        chunk = text[pos:pos + DOC_CHUNK_CHARS]
        end = pos + len(chunk)
        self._memory().set_doc_pos(cmd.chat_id, end)
        return cards.doc_more_card(chunk, end, len(text))

    def _op_scan(self, cmd: Command) -> DispatchResult:
        """`/case scan`：材料由「把图片/PDF 发进会话」触发（见 _attachment_intake_or_ask）。"""
        ready = "可直接发附件，Bot 会先确认处理方式" if self.downloader is not None else "（附件链路未启用，缺飞书凭证）"
        return self._result(cards.notice_card(
            "📥 材料录入",
            f"把**PDF / DOCX / TXT / MD 直接发到会话里**即可（可多张）——{ready}。\n"
            "收到后 Bot 会询问处理方式（录入新案件 / 并入已有案件 / 暂不处理）；确认后自动："
            "下载 → 落盘 `.run/bot/intake/` → 扫描提取 → 建案入库，并回写材料目录。\n"
            "图片类暂需 OCR（未启用）。也可用 `/case register` 先建案，再在详情卡点「提取五维」。",
        ))

    def _attachment_intake_or_ask(self, ev: dict, text: str) -> DispatchResult:
        """附件消息（纯附件或「文本 + 附件」）：**不擅自处理** → 暂存附件并询问要做什么。

        用户附带文本仅作上下文记录，不作为自动执行依据——避免「发来一份 PDF 就被
        当成新案录入」，而用户本意可能是并入已有案件或只是想了解内容。
        """
        chat_id = ev.get("chat_id") or ""
        mtype = ev.get("message_type") or ""
        attachments = ev.get("attachments") or []
        if text:
            self._memory().remember(chat_id, "user", text)
        if self.downloader is None:
            return self._result(cards.notice_card(
                "📥 已收到附件",
                f"类型：`{mtype}`。文件下载链路未启用（缺飞书凭证或未注入 downloader）；"
                "当前可用 `/case register` 登记 + `/case extract` 提取。",
            ))
        if not attachments:
            return self._result(cards.error_card("未能从消息中解析出附件，请重发图片或 PDF"))

        cmd = self._bind(Command(name="scan"), ev)
        role = self._role_of(cmd)
        if ROLE_LEVELS.get(role, -1) < ROLE_LEVELS["writer"]:
            return self._result(cards.error_card(
                f"权限不足：材料录入需要 **writer** 角色（当前 **{role}**）"
            ))

        pending = {"message_id": ev.get("message_id") or "", "attachments": attachments}
        self._memory().set_pending(chat_id, pending)
        names = [a.get("file_name") or a.get("file_key") or "" for a in attachments]
        return self._result(cards.intake_intent_card(len(attachments), names, self.bot_name))

    def _op_intake_confirm(self, cmd: Command) -> DispatchResult:
        """确认「录入新案件」：消费暂存附件 → 下载 → 落盘 → 扫描提取 → 建案入库（异步）。"""
        pending = self._memory().pending(cmd.chat_id)
        attachments = pending.get("attachments") or []
        if not attachments:
            return self._result(cards.error_card("待处理附件已过期，请重新发送材料后再录入"))
        ev = {
            "message_id": pending.get("message_id") or "",
            "chat_id": cmd.chat_id, "open_id": cmd.open_id,
            "chat_type": cmd.chat_type, "attachments": attachments,
        }
        self._memory().clear_pending(cmd.chat_id)
        scan_cmd = replace(cmd, name="scan")

        def task(ack_message_id: Optional[str]) -> Reply:
            card, case_id = self._run_intake(scan_cmd, ev, attachments)
            reply = self._card_update(card, ack_message_id)
            reply.followup = self._insight_card(case_id, with_llm=True)
            return reply

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card(
                "🕒 材料录入中…", f"{len(attachments)} 个附件 · 引擎 `{self.engine}`"
            )),
            deferred=task,
        )

    def _op_intake_cancel(self, cmd: Command) -> dict:
        self._memory().clear_pending(cmd.chat_id)
        return cards.notice_card("已忽略附件", "未做任何处理。需要时可重新发送材料。")

    def _op_intake_merge(self, cmd: Command) -> DispatchResult:
        """把暂存附件**并入已有案件**：追加到该案材料目录 → 重跑五维提取（异步）。

        目标目录优先用该案已登记的 `source_path`；未登记时以本次暂存目录作为材料目录。
        """
        ref = (cmd.args or "").strip() or cmd.value.get("case_id") or self._memory().last_case(cmd.chat_id)
        if not ref:
            return self._result(cards.error_card("请指明要并入的案件，例如「并入 腾讯案」"))
        case, hits = self._resolve(ref, cmd)
        if not case:
            return self._result(self._ref_miss_card(ref, hits, cmd, "intake_merge"))
        pending = self._memory().pending(cmd.chat_id)
        attachments = pending.get("attachments") or []
        if not attachments:
            return self._result(cards.error_card("没有待并入的附件（可能已过期），请重新发送材料"))

        case_id = case["id"]
        message_id = pending.get("message_id") or ""

        def task(ack_message_id: Optional[str]) -> Reply:
            staging, saved, failed = self._download_attachments(message_id, attachments)
            if not saved:
                self._audit(cmd, "intake_merge", case_id, f"下载失败={len(failed)}")
                return self._card_update(
                    cards.error_card(f"附件下载失败（0 个成功），请重试；失败 {len(failed)} 个"), ack_message_id
                )
            src = (case.get("source_path") or "").strip()
            target = Path(src) if src else Path()
            if src and target.is_dir():
                for name in saved:
                    try:
                        shutil.copy2(staging / name, target / name)
                    except Exception:  # noqa: BLE001
                        logger.exception("并入材料复制失败：%s", name)
            else:
                target = staging          # 该案无材料目录 → 以本次暂存目录登记为材料目录
                svc.update_case(case_id, {"source_path": str(target)}, self.db_path)
            parsable = [n for n in saved if Path(n).suffix.lower() in _parsable_suffixes()]
            if not parsable:
                self._memory().clear_pending(cmd.chat_id)
                self._audit(cmd, "intake_merge", case_id, f"无可解析文件 saved={len(saved)}")
                return self._card_update(cards.notice_card(
                    "📥 材料已并入（未提取）",
                    f"已保存 {len(saved)} 个附件，但无一为可解析类型"
                    f"（{'、'.join(sorted(_parsable_suffixes()))}）。图片类材料需 OCR（未启用）。",
                    template=cards.ORANGE,
                ), ack_message_id)
            try:
                report = svc.extract_into_case(case_id, engine=self.engine, db_path=self.db_path)
            except Exception as e:  # noqa: BLE001
                logger.exception("并入后提取失败")
                self._audit(cmd, "intake_merge", case_id, f"提取失败: {e}")
                return self._card_update(cards.error_card(f"材料已并入，但提取失败：{e}"), ack_message_id)
            refreshed = svc.resolve_case(case_id, self.db_path) or case
            self._note_case(cmd.chat_id, case_id)
            self._memory().clear_pending(cmd.chat_id)
            self._audit(cmd, "intake_merge", case_id,
                        f"补充={len(saved)} 提取物={len(report.get('artifact_ids') or [])}")
            reply = self._card_update(cards.extract_result_card(refreshed, report), ack_message_id)
            reply.followup = self._insight_card(case_id, with_llm=True)
            return reply

        return DispatchResult(
            immediate=Reply(kind="card", card=cards.processing_card(
                "🕒 并入处理中…",
                f"{case.get('case_name') or case_id} · {len(attachments)} 个附件 · 引擎 `{self.engine}`",
            )),
            deferred=task,
        )

    def _download_attachments(self, message_id: str, attachments: list[dict]) -> tuple:
        """下载附件到消息专属暂存目录 → (staging, saved, failed)。"""
        staging = self._staging_dir(message_id)
        staging.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        failed: list[str] = []
        for i, att in enumerate(attachments, 1):
            label = att.get("file_name") or att.get("file_key") or f"#{i}"
            data = self.downloader(message_id, att.get("file_key") or "", att.get("type") or "file")
            if not data:
                failed.append(label)
                continue
            name = _safe_filename(
                att.get("file_name") or "", att.get("file_key") or "", i, att.get("type") or "file"
            )
            try:
                (staging / name).write_bytes(data)
            except Exception:  # noqa: BLE001
                logger.exception("附件落盘失败: %s", name)
                failed.append(label)
                continue
            saved.append(name)
        return staging, saved, failed

    def _run_intake(self, cmd: Command, ev: dict, attachments: list[dict]) -> tuple:
        """下载附件 → 落盘 → import_scan → 回写 source_path；返回 (结果卡, case_id)。"""
        message_id = ev.get("message_id") or ""
        staging, saved, failed = self._download_attachments(message_id, attachments)

        if not saved:
            self._audit(cmd, "scan", "", f"下载失败={len(failed)}")
            return cards.error_card(
                "附件下载失败（0 个成功），请重试；也可用 `/case register` 先登记再 `/case extract`。"
            ), ""

        # 只有可解析类型（PDF/DOCX/TXT/MD）才入库；纯图片需 OCR（未启用）
        parsable = [n for n in saved if Path(n).suffix.lower() in _parsable_suffixes()]
        if not parsable:
            self._audit(cmd, "scan", "", f"无可解析文件 saved={len(saved)}")
            return cards.notice_card(
                "📥 材料已存盘（未入库）",
                f"已保存 {len(saved)} 个附件，但无一为可解析类型（{'、'.join(sorted(_parsable_suffixes()))}）。\n"
                "图片类材料需 OCR（未启用），请改发 PDF / DOCX / TXT / MD。",
                template=cards.ORANGE,
            ), ""

        try:
            report = svc.import_scan(staging, engine=self.engine, db_path=self.db_path)
        except Exception as e:  # noqa: BLE001
            logger.exception("材料提取失败")
            self._audit(cmd, "scan", "", f"提取失败: {e}")
            return cards.error_card(f"材料已存盘（{len(saved)} 个），但提取失败：{e}"), ""

        case_id = report.get("case_id") or ""
        if case_id:
            # 回写材料目录，供后续 `/case extract` 重跑（CLI link 同口径）
            svc.update_case(case_id, {"source_path": str(staging)}, self.db_path)
            self._note_case(cmd.chat_id, case_id)
        self._audit(cmd, "scan", case_id,
                    f"saved={len(saved)}/failed={len(failed)}/imported={bool(case_id)}")
        return cards.intake_result_card(report, saved, failed, str(staging)), case_id

    def _staging_dir(self, message_id: str) -> Path:
        """附件落盘目录：`.run/bot/intake/<message_id>/`（已 gitignore，禁用 data/）。"""
        safe = re.sub(r"[^A-Za-z0-9_-]", "", message_id or "") or "unknown"
        return self.intake_dir / safe

    @staticmethod
    def _card_update(card_json: dict, ack_message_id: Optional[str]) -> Reply:
        return Reply(kind="card_update", message_id=ack_message_id or "", card=card_json)

    # ---------- 兼容旧接口 ----------

    def _format_error(self, message: str) -> str:
        # 输出侧兜底：错误信息可能夹带路径 / 技术细节 → 命中保密红线即换安全话术
        return policy.scrub(f"❌ {message}")

    @staticmethod
    def _business_error(exc: Exception) -> str:
        """对外只给业务口径的错误说明；技术异常（数据库 / 路径 / 内部键名）不外泄。"""
        if isinstance(exc, ValueError):
            msg = str(exc)
            for internal, friendly in (("source_path", "原始材料目录"), ("case_name", "案件名称"),
                                       ("case_id", "案件"), ("artifact_id", "提取物"),
                                       ("db_path", "数据文件")):
                msg = msg.replace(internal, friendly)
            return msg
        return "操作未能完成，请稍后重试，或换一种说法。"


def _doc_types() -> dict:
    from .document_generator import DocumentGenerator
    return DocumentGenerator.DOC_TYPES


def _engines() -> list:
    from .extractor import SUPPORTED_ENGINES
    return [e for e in SUPPORTED_ENGINES if e not in ("mock", "basic")] or list(SUPPORTED_ENGINES)


def _parsable_suffixes() -> set:
    """可解析类型唯一真值在 scanner.SUPPORTED_TYPES（避免两处枚举漂移）。"""
    from .scanner import SUPPORTED_TYPES
    return SUPPORTED_TYPES


_EXT_BY_TYPE = {"image": ".jpg", "file": ".bin", "media": ".mp4", "audio": ".mp3"}


def _safe_filename(name: str, file_key: str, idx: int, mtype: str = "file") -> str:
    """附件名净化：去目录、去危险字符；无扩展名时按类型兜底（files 落盘用）。"""
    base = re.sub(r"[^\w.\-]", "_", Path((name or "").strip()).name).strip("._")
    suffix = Path(base).suffix.lower()
    if base and suffix:
        return base
    stem = base or f"attachment-{idx}"
    key_suffix = Path(file_key or "").suffix.lower()
    if key_suffix and key_suffix in (_parsable_suffixes() | {".jpg", ".jpeg", ".png", ".bmp", ".gif"}):
        return f"{stem}{key_suffix}"
    return f"{stem}{_EXT_BY_TYPE.get(mtype, '.bin')}"


# =============================================
# 旧式 webhook 薄封装（msg_type/content → 文本）
# 正式链路：lark_transport.LarkTransport.handle_webhook（验签 + 卡片 + 去重）
# =============================================

class LarkWebhookHandler:
    """把旧式 webhook 事件（msg_type/content）转成一条文本命令并回文本。"""

    def __init__(self, bot: CaseBot):
        self.bot = bot

    def handle_event(self, event_data: dict) -> Optional[dict]:
        try:
            event = (event_data or {}).get("event") or {}
            content = event.get("content")
            text = ""
            if event.get("msg_type") == "text":
                text = json.loads(content).get("text", "")
            elif isinstance(content, str):
                text = content
            response = self.bot.handle_message(text)
            return {
                "status_code": 0,
                "status_message": "success",
                "data": {"content": response},
            }
        except Exception as e:  # noqa: BLE001
            logger.error("处理事件失败: %s", e)
            return {"status_code": 1, "status_message": str(e)}


# =============================================
# 工厂
# =============================================

def create_bot(
    db_path: Optional[Path] = None,
    identity=None,
    engine: Optional[str] = None,
    downloader=None,
    intake_dir: Optional[Path] = None,
    memory=None,
    llm=None,
    agent_graph=None,
) -> CaseBot:
    return CaseBot(
        db_path=db_path, identity=identity, engine=engine,
        downloader=downloader, intake_dir=intake_dir, memory=memory, llm=llm,
        agent_graph=agent_graph,
    )


def create_dispatcher(bot: Optional[CaseBot] = None):
    """给 lark_transport 注入的 dispatcher（bot.dispatch）。"""
    bot = bot or create_bot()
    return bot.dispatch


def create_webhook_handler(bot: Optional[CaseBot] = None) -> LarkWebhookHandler:
    return LarkWebhookHandler(bot or create_bot())


# =============================================
# CLI 模式（本地调试，无飞书凭证）
# =============================================

if __name__ == "__main__":
    bot = create_bot()
    print("=" * 50)
    print(f"{bot.bot_name} 飞书案件 Bot（文本模式）")
    print("=" * 50)
    print("直接说人话（如「看看 2024 年的案件」「腾讯案的详情」）；/case help 看能力；exit 退出。\n")
    while True:
        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break
        if user_input.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if not user_input:
            continue
        print()
        print(bot.handle_message(user_input))
        print()
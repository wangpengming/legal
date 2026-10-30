#!/usr/bin/env python3
# =============================================
# lark_agent.py - B：工具注册表 + LangGraph ReAct agent
#
# 定位：A（单步 LLM 意图）之后的**多步兜底** —— 用户一句话需要「先找案件再取提取物
#   再总结」这类串联动作时，交给 ReAct agent 自主调工具。
#
# 两层：
#   1. ToolRegistry —— 把 case_service 的操作包装成「带角色的工具」；执行=走
#      bot._dispatch_command（与命令/卡片同一管线，唯一真值）；写类工具落 bot_audit。
#   2. run_agent —— LangGraph create_react_agent + minimax（OpenAI 兼容）。
#      🔴 懒加载：缺 langgraph / 缺 MINIMAX_API_KEY → 返回 error 而非抛，
#      主链路降级到引导卡；`graph` 可注入 → 单测用 fake graph，不出网。
#
# 见 docs/SPEC-feishu-bot.md §5.4。
# =============================================
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from . import lark_identity as ident
from .lark_intent import DOC_TYPES
from .lark_policy import CONFIDENTIALITY_RULES

logger = logging.getLogger(__name__)

ROLE_LEVELS = {"readonly": 0, "writer": 1, "generator": 2, "admin": 3}

MAX_OBS = 1200          # 工具观察文本截断（防上下文爆炸）
DEFAULT_MAX_STEPS = 6
DEFAULT_MODEL = "MiniMax-M3.1-Flash"
DEFAULT_BASE_URL = "https://api.minimax.cn/v1"

# ReAct agent 的系统提示：业务边界 + 保密红线（对外只谈业务，不问不答非业务信息）
AGENT_SYSTEM_PROMPT = (
    "你是法务案例智能助手「案小智」，通过调用工具帮助用户完成案件相关任务"
    "（查案件 / 看案卷 / 提五维 / 出文书 / 出统计 / 登记新案）。\n"
    "· 先理解用户意图，再选择合适工具；必要时串联多步（例如先检索案件、再取其提取物）。\n"
    "· 用户要看提取物的**内容**（不只是维度清单）→ 用 artifact_content 读取正文；\n"
    "  要案件档案（案号 / 当事人 / 案由 / 法院 / 结果）→ 用 case_material；\n"
    "  要比较两个案子 → 用 compare。\n"
    "· 需要**外部**法律信息（法条 / 司法解释 / 赔偿标准 / 裁判规则 / 公开判例）时，"
    "可用 web_search 联网检索；翻查本地案件时不要用它。\n"
    "· 回答**业务经验问题**（「这类案子一般判多少钱」「类似案件怎么判」「赔偿标准是多少」）"
    "→ 先用 corpus_search 检索本地案例库，答案必须建立在其返回的证据之上并标注来源；\n"
    "  检索无命中就如实说本地库没有相关记录，不要凭记忆写法条或编造金额。\n"
    "· 回答**具体法条内容** → 用 law_lookup（本地法规库优先，未命中再联网）；不要凭记忆写条文原文。\n"
    "· 最终用**简洁的中文**回答，只呈现与案件业务相关的结论，不要罗列工具名或内部执行过程。\n"
    "· 若请求与案件业务无关（闲聊、探询系统 / 技术 / 配置 / 他人信息等），"
    "不要调用工具、也不要编造，直接友好说明你能做什么并引导回案件。\n"
    + CONFIDENTIALITY_RULES
)


# =============================================
# 工具目录
# =============================================

@dataclass(frozen=True)
class Tool:
    """一个可被 agent 调用的工具：name 与 lark_bot 的 _op_* 对齐。"""
    name: str
    description: str
    role: str = "readonly"
    ref_desc: str = "案件名或案号；也可用「它」指上一轮提到的案件（无参工具留空）"
    extra_desc: str = "附加参数（一般留空）"


TOOLS: tuple[Tool, ...] = (
    Tool("list", "列出案件，可按年份筛选", ref_desc="四位年份，可留空"),
    Tool("search", "按关键词搜索案件", ref_desc="搜索关键词"),
    Tool("detail", "查看某个案件的详情"),
    Tool("artifacts", "查看某案件的提取物 / 材料清单"),
    Tool("artifact_content", "读取某案件提取物的**正文**（各维度详细分析；清单只有维度名，正文才有内容）"),
    Tool("case_material", "读取某案件的案件档案（案号、当事人、案由、法院、结果、提取物目录）"),
    Tool("compare", "对比两个案件的提取物要点（ref 填案件 A，extra 填案件 B）",
         ref_desc="案件 A 的名称或案号", extra_desc="案件 B 的名称或案号"),
    Tool("match", "查找与某案件相似的案件"),
    Tool("report", "案件统计总览", ref_desc="留空"),
    Tool("web_search", "联网检索与法务业务相关的公开资料（法律法规 / 司法解释 / 裁判规则 / 公开案例）"
                       "——仅在需要外部法律信息时用，翻查本地案件不要用",
         ref_desc="检索关键词"),
    Tool("law_lookup", "查具体法条：先查本地法规库（离线、权威），未命中再联网检索",
         ref_desc="法条名 / 条号 / 关键词，如「著作权法第24条 合理使用」"),
    Tool("templates", "文书模板列表", ref_desc="留空列出全部；或填 `search ＜关键词＞`"),
    Tool("corpus_search", "检索**本地案例库**（案件字段 + 提取物正文）里的同类案件经验，"
                          "返回带出处的证据片段与金额统计——回答「这类案子一般判多少 / 怎么判」类问题必用",
         ref_desc="检索关键词或问题原话，如「惩罚性赔偿」「法定赔偿 赔偿标准」"),
    Tool("register", "登记一个新案件", role="writer", ref_desc="留空",
         extra_desc="`键: 值` 多行，键可用 案号 / 原告 / 被告 / 案由 / 案件名称"),
    Tool("extract", "对某案件执行五维提取", role="writer"),
    Tool("discuss", "就某个案件做开放式分析 / 讨论（争议焦点、风险、应对思路；只依据该案材料，不编造）",
         extra_desc="用户的问题原话（留空则用引用）"),
    Tool("generate", "为某案件生成文书", role="generator",
         extra_desc="文书类型：答辩状 / 质证意见 / 当庭陈述 / 证据目录"),
)


def _fmt_args(args: Any) -> str:
    if not args:
        return ""
    if isinstance(args, dict):
        return " ".join(f"{k}={v}" for k, v in args.items() if v)
    return str(args)


def _truncate(text: str, limit: int = MAX_OBS) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…（已截断）"


class ToolRegistry:
    """工具注册表：按角色过滤 + 执行（走 bot 管线）+ 写类工具落审计。"""

    def __init__(self, bot, tools: tuple[Tool, ...] = TOOLS):
        self.bot = bot
        self._tools = {t.name: t for t in tools}

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def enabled(self, role: str) -> list[Tool]:
        """该角色可用的工具（readonly 用不到写/生成工具）。"""
        level = ROLE_LEVELS.get(role, -1)
        return [t for t in self._tools.values() if ROLE_LEVELS.get(t.role, 0) <= level]

    def call(self, name: str, args: dict, *, role: str, cmd) -> str:
        """执行工具 → 观察文本。拒绝/参数不足也返回文本，供模型自我纠正。"""
        from .lark_bot import Command, parse_fields      # 延迟导入：破循环依赖

        tool = self._tools.get(name)
        if tool is None:
            return f"[拒绝] 未知工具：{name}"
        if ROLE_LEVELS.get(role, -1) < ROLE_LEVELS.get(tool.role, 0):
            return f"[拒绝] 权限不足：`{name}` 需要 {tool.role} 角色（当前 {role}）"

        ref = str((args or {}).get("ref") or "").strip()
        extra = str((args or {}).get("extra") or "").strip()
        if tool.name == "web_search":                    # 非本地命令：直接走联网检索
            return self._web_search(ref or extra)
        if tool.name == "case_material":
            return self._case_material(ref, cmd)
        if tool.name == "artifact_content":
            return self._artifact_content(ref, cmd)
        if tool.name == "compare":
            return self._compare(ref, extra, cmd)
        if tool.name == "corpus_search":
            return self._corpus_search(ref or extra)
        built = self._build(tool.name, ref, extra, Command, parse_fields)
        if built is None:
            return "[提示] 参数不足：请补充案件名或案号后再试"

        for attr in ("open_id", "chat_id", "chat_type", "message_id"):
            setattr(built, attr, getattr(cmd, attr, ""))
        result = self.bot._dispatch_command(built)
        reply = result.immediate
        if result.deferred is not None:
            reply = result.deferred(None) or reply
        obs = _truncate(self.bot._reply_text(reply))
        if tool.role != "readonly":                      # 写/生成才落审计（与 Bot 口径一致）
            self._audit(tool.name, role, cmd, obs)
        return obs

    def _corpus_search(self, query: str) -> str:
        """本地案例语料检索 → 带出处的证据文本（agent 的主要知识来源）。"""
        from . import corpus
        q = (query or "").strip()
        if not q:
            return "[提示] 请给出检索关键词，如「惩罚性赔偿」「法定赔偿」"
        db_path = getattr(self.bot, "db_path", None)
        try:
            ev = corpus.evidence(q, db_path=db_path)
        except Exception:  # noqa: BLE001
            logger.exception("本地语料检索失败")
            return "[提示] 本地案例库检索失败，请稍后再试"
        text = corpus.evidence_text(ev, max_chars=3000)
        return text or "[提示] 本地案例库未检索到相关记录，请换个关键词或直接给出案件名"

    @staticmethod
    def _web_search(query: str) -> str:
        from . import lark_websearch as ws
        q = (query or "").strip()
        if not q:
            return "[提示] 请提供检索关键词"
        results = ws.search(q)
        if not results:
            return "[提示] 未检索到相关公开资料（或联网检索当前不可用）"
        return "\n".join(
            f"{i}. {r.get('title')} — {r.get('url')}\n   {r.get('snippet')}"
            for i, r in enumerate(results, 1)
        )

    # ---------- 案件档案 / 提取物正文 / 两案对比（agent 的「知识面」） ----------

    def _find_case(self, ref: str, cmd):
        """ref → (case, hits)：精确命中优先；名称模糊命中唯一时直接采用。"""
        from . import case_service as svc
        db_path = getattr(self.bot, "db_path", None)
        ref = (ref or "").strip()
        if not ref:
            case_id = ""
            try:
                case_id = self.bot._memory().last_case(getattr(cmd, "chat_id", "") or "")
            except Exception:  # noqa: BLE001
                logger.exception("读取会话最近案件失败")
            if not case_id:
                return None, []
            return svc.resolve_case(case_id, db_path), []
        case = svc.resolve_case(ref, db_path)
        if case:
            return case, []
        hits = svc.query_cases(search=ref, limit=8, db_path=db_path)
        if len(hits) == 1:
            return hits[0], []
        return None, hits

    def _bundle(self, case: dict) -> dict:
        from . import case_service as svc
        return svc.case_bundle(case["id"], db_path=getattr(self.bot, "db_path", None)) or {}

    def _case_material(self, ref: str, cmd) -> str:
        case, hits = self._find_case(ref, cmd)
        if not case:
            if hits:
                names = "、".join((c.get("case_name") or c.get("case_number") or "") for c in hits[:5])
                return f"[提示] 「{ref}」匹配到多个案件，请指明其一：{names}"
            return "[提示] 未找到该案件，请提供案件名称或案号。"
        arts = self._bundle(case).get("artifacts") or []
        lines = [
            f"案件：{case.get('case_name') or ''}（{case.get('case_number') or '无案号'}）",
            f"案由：{case.get('cause') or '未登记'}",
            f"原告：{case.get('plaintiff') or '未登记'}　被告：{case.get('defendant') or '未登记'}",
            f"法院：{case.get('court') or '未登记'}　结果：{case.get('result') or '未登记'}",
            f"提取物：{len(arts)} 份" + (
                "（" + "、".join((a.get('title') or a.get('type') or '') for a in arts) + "）" if arts else ""),
        ]
        return _truncate("\n".join(lines), 1500)

    def _artifact_content(self, ref: str, cmd) -> str:
        case, hits = self._find_case(ref, cmd)
        if not case:
            if hits:
                names = "、".join((c.get("case_name") or c.get("case_number") or "") for c in hits[:5])
                return f"[提示] 「{ref}」匹配到多个案件，请指明其一：{names}"
            return "[提示] 未找到该案件，请提供案件名称或案号。"
        arts = self._bundle(case).get("artifacts") or []
        if not arts:
            return f"[提示] 「{case.get('case_name')}」还没有提取物，无法读取正文。"
        lines = [f"案件：{case.get('case_name')}"]
        for a in arts:
            lines.append(f"\n## {a.get('title') or a.get('type')}")
            lines.append((a.get("content") or "").strip() or "（该维度暂无正文）")
        return _truncate("\n".join(lines), 4000)

    def _compare(self, ref_a: str, ref_b: str, cmd) -> str:
        case_a, hits_a = self._find_case(ref_a, cmd)
        if not case_a:
            return f"[提示] 未找到案件 A「{ref_a}」，请提供准确的案件名称或案号。"
        case_b, hits_b = self._find_case(ref_b, cmd)
        if not case_b:
            return f"[提示] 未找到案件 B「{ref_b}」，请提供准确的案件名称或案号。"
        arts_a = {a.get("type") or a.get("artifact_type"): (a.get("content") or "")
                  for a in (self._bundle(case_a).get("artifacts") or [])}
        arts_b = {a.get("type") or a.get("artifact_type"): (a.get("content") or "")
                  for a in (self._bundle(case_b).get("artifacts") or [])}
        lines = [
            f"案件 A：{case_a.get('case_name')}（{case_a.get('case_number') or '无案号'}）",
            f"案件 B：{case_b.get('case_name')}（{case_b.get('case_number') or '无案号'}）",
        ]
        for key in sorted(set(arts_a) | set(arts_b)):
            lines.append(f"\n## {key}")
            lines.append(f"[A] {arts_a.get(key) or '（无）'}")
            lines.append(f"[B] {arts_b.get(key) or '（无）'}")
        return _truncate("\n".join(lines), 4000)

    @staticmethod
    def _build(name: str, ref: str, extra: str, Command, parse_fields):
        """工具名 + 参数 → Command（与命令管线同一结构）。"""
        if name in ("list", "search", "detail", "artifacts", "match", "report", "templates"):
            return Command(name=name, args=ref)
        if name == "extract":
            return Command(name="extract", args=ref)
        if name == "law_lookup":
            return Command(name="law_lookup", args=ref or extra)
        if name == "discuss":
            # ref 可空：交给 bot 用会话记忆（last_case）补全
            return Command(name="discuss", args=ref, value={"question": extra})
        if name == "register":
            fields = parse_fields(extra or ref)
            return Command(name="register_submit", form=fields) if fields else Command(name="register")
        if name == "generate":
            # ref 可空：交给 bot 用会话记忆（last_case）补全，或回「选案件」追问卡
            return Command(name="generate", args=ref, value={"doc_type": DOC_TYPES.get(extra, "")})
        return None

    def _audit(self, name: str, role: str, cmd, obs: str) -> None:
        try:
            ident.record_audit(
                action=f"agent:{name}", open_id=cmd.open_id or "(local)", role=role,
                case_id="", result=obs[:200], db_path=self.bot.db_path,
            )
        except Exception:  # noqa: BLE001
            logger.exception("agent 审计写入失败（不阻断）")


def build_registry(bot, tools: tuple[Tool, ...] = TOOLS) -> ToolRegistry:
    return ToolRegistry(bot, tools)


# =============================================
# LangGraph ReAct 运行器（懒加载 + 可注入 fake graph）
# =============================================

@dataclass
class AgentResult:
    text: str = ""
    steps: list = field(default_factory=list)
    model: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text.strip()) and not self.error


def build_model():
    """minimax（OpenAI 兼容）聊天模型；缺库或缺密钥返回 None（调用方降级）。"""
    try:
        from langchain_openai import ChatOpenAI
    except Exception as e:  # noqa: BLE001
        logger.warning("langchain_openai 不可用：%s", e)
        return None
    api_key = os.environ.get("MINIMAX_API_KEY") or ""
    if not api_key:
        logger.warning("缺 MINIMAX_API_KEY → agent 降级")
        return None
    return ChatOpenAI(
        model=os.environ.get("LARK_AGENT_MODEL") or DEFAULT_MODEL,
        base_url=os.environ.get("LARK_AGENT_BASE_URL") or DEFAULT_BASE_URL,
        api_key=api_key,
        temperature=0.0,
        timeout=float(os.environ.get("LARK_AGENT_TIMEOUT") or 60),
        max_retries=1,
    )


def _lc_tools(registry: ToolRegistry, role: str, cmd):
    """注册表 → LangChain StructuredTool（统一 ref/extra 双参数 schema）。"""
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model

    out = []
    for tool in registry.enabled(role):
        def _runner(tool_name: str = tool.name):
            def _fn(ref: str = "", extra: str = "") -> str:
                return registry.call(tool_name, {"ref": ref, "extra": extra}, role=role, cmd=cmd)
            return _fn

        schema = create_model(
            f"{tool.name}_args",
            ref=(str, Field(default="", description=tool.ref_desc)),
            extra=(str, Field(default="", description=tool.extra_desc)),
        )
        out.append(StructuredTool.from_function(
            func=_runner(), name=tool.name, description=tool.description, args_schema=schema,
        ))
    return out


def build_graph(registry: ToolRegistry, role: str, cmd, *, max_steps: int = DEFAULT_MAX_STEPS, model=None):
    """构建 ReAct 图；缺 langgraph / 缺模型 / 无可用工具 → None（调用方降级）。"""
    try:
        from langgraph.prebuilt import create_react_agent
    except Exception as e:  # noqa: BLE001
        logger.warning("langgraph 不可用：%s", e)
        return None
    model = model or build_model()
    if model is None:
        return None
    tools = _lc_tools(registry, role, cmd)
    if not tools:
        return None
    try:
        return create_react_agent(model, tools, prompt=AGENT_SYSTEM_PROMPT)
    except TypeError:
        # 兼容不支持 prompt 参数的旧签名（不因提示词注入失败而丢失 B）
        return create_react_agent(model, tools)


def _extract(state) -> AgentResult:
    """从图输出里取「最后一条有正文的 AI 回复」+ 工具调用轨迹。"""
    messages = state.get("messages") if isinstance(state, dict) else None
    if not messages:
        return AgentResult(error="agent 无输出")

    text, steps = "", []
    for m in messages:
        kind = m.get("type") if isinstance(m, dict) else getattr(m, "type", "")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")

        if kind in ("ai", "assistant"):
            if isinstance(content, list):
                content = "".join(
                    (b.get("text") or "") if isinstance(b, dict) else str(b) for b in content
                )
            if str(content or "").strip():
                text = str(content).strip()
            calls = (m.get("tool_calls") if isinstance(m, dict) else getattr(m, "tool_calls", None)) or []
            for tc in calls:
                if isinstance(tc, dict):
                    steps.append({"tool": tc.get("name") or "", "args": _fmt_args(tc.get("args")), "observation": ""})
        elif kind in ("tool", "tool_result"):
            if isinstance(content, list):
                content = "".join(
                    (b.get("text") or "") if isinstance(b, dict) else str(b) for b in content
                )
            if steps:
                steps[-1]["observation"] = _truncate(str(content or ""))

    if not text:
        return AgentResult(steps=steps, error="agent 未给出最终回答")
    return AgentResult(text=text, steps=steps)


def run_agent(
    query: str,
    *,
    registry: ToolRegistry,
    role: str = "readonly",
    cmd=None,
    history: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
    graph=None,
    model=None,
) -> AgentResult:
    """跑一次 ReAct；任何失败都返回带 error 的 AgentResult（不抛）。"""
    prompt = f"最近对话（供理解指代）：\n{history.strip()}\n\n现在用户说：{query.strip()}" if history.strip() else query.strip()
    if not prompt:
        return AgentResult(error="空输入")

    g = graph or build_graph(registry, role, cmd, max_steps=max_steps, model=model)
    if g is None:
        return AgentResult(error="agent 不可用（缺 langgraph 或模型凭证）")
    try:
        state = g.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"recursion_limit": max_steps * 2 + 3},
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("agent 执行失败")
        return AgentResult(error=str(e))
    result = _extract(state)
    result.model = os.environ.get("LARK_AGENT_MODEL") or DEFAULT_MODEL
    return result


__all__ = [
    "Tool", "TOOLS", "ToolRegistry", "build_registry",
    "AgentResult", "build_model", "build_graph", "run_agent",
    "ROLE_LEVELS", "MAX_OBS", "DEFAULT_MAX_STEPS",
]
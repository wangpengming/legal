#!/usr/bin/env python3
# =============================================
# lark_cards.py - 飞书交互卡片模板（纯函数，无外部依赖）
#
# 职责：
#   1. 构建飞书 v1 交互卡片 JSON（结果卡 / 表单卡 / 处理中卡 / 确认卡）
#   2. 归一化卡片回调 payload（按钮 value / 表单 form_value）
#   3. flatten_text()：把卡片降级为纯文本（CLI 模式 / 文本回执）
#
# 不直接调 SDK，不碰 DB —— 卡片只是"表现层"，业务数据由 case_service 提供。
# 见 docs/SPEC-feishu-bot.md §5 / §10。
# =============================================
from __future__ import annotations

import json
import re
from typing import Any, Optional

# 卡片主题色（飞书 v1 卡片的 header.template 取值）
BLUE = "blue"
GREEN = "green"
RED = "red"
ORANGE = "orange"
GREY = "grey"

# 卡片按钮 payload 的动作名（与 lark_bot 的命令管线一一对应）
ACT_REGISTER_SUBMIT = "register_submit"
ACT_REGISTER_CONFIRM = "register_confirm"
ACT_REGISTER_CANCEL = "register_cancel"
ACT_DETAIL = "detail"
ACT_EXTRACT = "extract"
ACT_GENERATE = "generate"
ACT_GENERATE_RUN = "generate_run"
ACT_MATCH = "match"
ACT_HELP = "help"
ACT_INTAKE_CONFIRM = "intake_confirm"
ACT_INTAKE_CANCEL = "intake_cancel"
ACT_INTAKE_MERGE = "intake_merge"
ACT_DOC_MORE = "doc_more"
ACT_SELECT_CASE = "select_case"

_FORM_ACTION = "register_submit"


# =============================================
# 基础元素
# =============================================

def _md(content: str) -> dict:
    return {"tag": "lark_md", "content": content}


def div(content: str) -> dict:
    return {"tag": "div", "text": _md(content)}


def hr() -> dict:
    return {"tag": "hr"}


def note(content: str) -> dict:
    return {"tag": "note", "elements": [{"tag": "plain_text", "content": content}]}


def button(text: str, value: dict, type_: str = "default") -> dict:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": type_,
        "value": value,
    }


def actions(*btns: dict) -> dict:
    return {"tag": "action", "actions": list(btns)}


def fields(pairs: list[tuple[str, str]], is_short: bool = True) -> dict:
    # 飞书卡片 v1：分栏字段必须挂在 div 元素下（tag="div" + fields），
    # 顶层 tag="fields" 不被支持（会报 11310 unsupported type of block）。
    return {
        "tag": "div",
        "fields": [
            {"is_short": is_short, "text": _md(f"**{k}**：{v}")} for k, v in pairs
        ],
    }


def input_field(name: str, label: str, placeholder: str, default: str = "") -> dict:
    el = {
        "tag": "input",
        "name": name,
        "label": {"tag": "plain_text", "content": label},
        "placeholder": {"tag": "plain_text", "content": placeholder},
    }
    if default:
        el["default_value"] = default
    return el


def form(name: str, *elements: dict) -> dict:
    return {"tag": "form", "name": name, "elements": list(elements)}


def card(title: str, *elements: dict, template: str = BLUE, note_text: str = "") -> dict:
    """组装一张卡片：header + elements（+ 可选 note）。"""
    els: list[dict] = [e for e in elements if e]
    if note_text:
        els.append(hr())
        els.append(note(note_text))
    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": {"template": template, "title": {"tag": "plain_text", "content": title}},
        "elements": els,
    }


# =============================================
# 业务名映射（去技术标识：卡片不展示内部英文键 / 维度代号 / 引擎名 / 生成方式）
# 单一真值在 src/database.py（ARTIFACT_TYPE_NAMES）；此处为展示层，测试断言二者一致
# =============================================

_ARTIFACT_LABELS = {
    "case_key_facts": "事实认定",
    "legal_reasoning_chain": "法律依据",
    "defense_argument_chain": "攻防策略",
    "evidence_structure": "证据体系",
    "liability_calculation": "赔偿裁量",
    "quantitative_analysis": "量化分析",
    "cross_exam_strategy": "质证策略",
    "contingency_response": "应变话术",
    "reverse_strategy": "反向维权路径",
    "court_statement": "当庭陈述",
}

_DIM_LABELS = {
    "D1": "事实认定", "D2": "法律依据", "D3": "攻防策略", "D4": "证据体系", "D5": "赔偿裁量",
}

_ENGINE_LABELS = {"minimax": "云端", "openai": "云端", "ollama": "本地", "basic": "基础", "mock": "演示"}

# 文书生成来源（document_generator.result.source）→ 业务口径
_SOURCE_LABELS = {
    "llm": "AI 起草",
    "langchain_llm": "AI 起草",
    "template": "模板生成",
    "template+llm": "模板 + AI 润色",
    "fallback": "基础生成",
}

_DIM_PREFIX_RE = re.compile(r"^D[1-5][:：]\s*")


def artifact_label(artifact_type: str) -> str:
    """提取物内部键 → 业务名（未知键按维度代号兜底，再退原值）。"""
    key = (artifact_type or "").strip()
    return _ARTIFACT_LABELS.get(key) or _DIM_LABELS.get(key.upper()) or key


def clean_artifact_title(title: str) -> str:
    """去掉内部维度代号前缀（'D1: 事实认定' → '事实认定'）。"""
    return _DIM_PREFIX_RE.sub("", (title or "").strip())


def engine_label(engine: str) -> str:
    """引擎内部名 → 业务口径（不暴露厂商/技术栈）。"""
    key = (engine or "").strip().lower()
    return _ENGINE_LABELS.get(key, "标准" if key else "默认")


def source_label(source: str) -> str:
    """文书生成来源内部名 → 业务口径。"""
    key = (source or "").strip().lower()
    return _SOURCE_LABELS.get(key, "自动生成")


# =============================================
# PII 脱敏（群聊可见 → 遮罩，SPEC §11）
# =============================================

_ID_CARD_RE = re.compile(r"(?<!\d)(\d{4})\d{10}(\d{3}[\dXx])(?!\d)")
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")


def append_note(card_json: dict, text: str) -> dict:
    """在卡片底部追加一行 note（用于标注「由云端模型理解」等来源信息）。"""
    if not isinstance(card_json, dict) or not text:
        return card_json
    els = list(card_json.get("elements") or [])
    els.extend([hr(), note(text)])
    card_json["elements"] = els
    return card_json


def mask_pii(text: str) -> str:
    """遮罩身份证（前4****后4）与手机号（前3****后4）。非字符串原样返回。"""
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""
    text = _ID_CARD_RE.sub(r"\1**********\2", text)
    return _PHONE_RE.sub(r"\1****\2", text)


# =============================================
# 结果卡
# =============================================

DEFAULT_BOT_NAME = "案小智"

# 能力清单：按「建案 → 查看 → 提五维 → 出文书 → 统计」的依赖与顺序组织（非平铺、非命令手册）
_CAPABILITIES = (
    "**① 建案**（材料自动入库）　把 PDF/DOCX/TXT/MD 发到会话即录入；或说「登记一个新案件」\n"
    "**② 查与看**　「看看 2024 年的著作权案件」「搜一下腾讯」「腾讯案的详情」「腾讯案有哪些提取物」\n"
    "**③ 提五维**（建议在建案后）　「把腾讯案的材料提取一下」\n"
    "**④ 出文书**（需先有案件）　「起草腾讯案的答辩状」「生成质证意见」\n"
    "**⑤ 统计**　「统计一下」「今年收了多少案」\n"
    "**⑥ 经验问答**（依据本地案例库）　「这类案子一般判多少钱」「赔偿标准是多少」「对比一下 A 案和 B 案」"
)


def help_card(bot_name: str = DEFAULT_BOT_NAME) -> dict:
    """能力清单 + 示例问句（按业务流程序），而非 CLI 手册。"""
    return card(
        f"📖 {bot_name} · 能帮你做什么",
        div(f"**{bot_name}是您的案件智能助手。用自然语言描述需求即可，无需记命令。**"),
        div(_CAPABILITIES),
        hr(),
        div("**高级用法（命令）**：`/case list` · `/case search` · `/case help` · `/case match`"),
        actions(
            button("📋 案件列表", {"action": "list"}, "primary"),
            button("📊 统计", {"action": "report"}),
            button("📝 登记新案", {"action": "register"}),
        ),
        note_text="发 PDF/DOCX 到会话即可建案并录入材料",
    )


# 业务指南：方法性问题的**静态兜底**（LLM 不可用时）——直接给步骤/清单，而非只罗列能力
_ADVISE_GUIDE = (
    "**起草文书需要先有案件**，按下面三步准备即可：\n"
    "**① 案件基础信息**　案号、原告、被告、案由、涉案场景、双方授权状态\n"
    "**② 案件材料**　起诉状 / 证据清单 / 对方证据 / 判决或裁定等（PDF/DOCX 发到会话即自动录入）\n"
    "**③ 按文书类型的补充材料**\n"
    "　· 答辩状：起诉状副本 + 证据材料\n"
    "　· 质证意见：对方证据清单与证据材料\n"
    "　· 当庭陈述：案件经过与争议焦点\n"
    "　· 证据目录：本方证据材料\n"
    "**标准流程**：发材料建案 → 说「提取一下」→ 说「起草 ＜案件＞ 的答辩状」"
)


def advise_fallback_card(bot_name: str = DEFAULT_BOT_NAME) -> dict:
    """方法性问题的静态业务指南（LLM 不可用时兜底）：给步骤/清单 + 能力清单。"""
    return card(
        f"📝 {bot_name} · 业务指引",
        div(_ADVISE_GUIDE),
        hr(),
        div(_CAPABILITIES),
        actions(
            button("📝 登记新案", {"action": "register"}, "primary"),
            button("📋 案件列表", {"action": "list"}),
            button("📊 统计", {"action": "report"}),
        ),
        note_text="把案件材料（PDF/DOCX）发到会话即可建案并录入",
    )


def guide_card(bot_name: str = DEFAULT_BOT_NAME) -> dict:
    """未识别输入 → 友好引导卡（灰色），不用「处理失败」。"""
    return card(
        f"👋 我是{bot_name}",
        div("抱歉，我没有理解这句话。您可以这样对我说："),
        div(_CAPABILITIES),
        actions(
            button("📖 使用帮助", {"action": "help"}, "primary"),
            button("📋 案件列表", {"action": "list"}),
            button("📊 统计", {"action": "report"}),
        ),
        template=GREY,
        note_text="也可以直接把案件材料（PDF/DOCX）发给我",
    )


def greeting_card(bot_name: str = DEFAULT_BOT_NAME) -> dict:
    """问候 / 闲聊 → 友好回应 + 引导回业务（不是冷冰冰的「未识别」）。"""
    return card(
        f"👋 {bot_name} 在",
        div(f"您好，我是{bot_name}，法务案件智能助手。\n"
            "直接说要做什么即可，比如「腾讯案的详情」「2024 年的案件」「这类案子一般判多少钱」。"),
        div(_CAPABILITIES),
        actions(
            button("📖 使用帮助", {"action": "help"}, "primary"),
            button("📋 案件列表", {"action": "list"}),
            button("📊 统计", {"action": "report"}),
        ),
        template=GREY,
        note_text="发 PDF/DOCX 到会话即可建案并录入材料",
    )


def error_card(message: str) -> dict:
    return card("❌ 处理失败", div(message or "未知错误"), template=RED)


def notice_card(title: str, message: str = "", template: str = BLUE) -> dict:
    return card(title, div(message) if message else None, template=template)


def answer_card(title: str, body: str, *, source: str = "") -> dict:
    """模型生成的自然语言回答卡（左下标注来源，便于核对与审计）。"""
    return card(title, div(body or "（空）"), template=BLUE, note_text=source)


def insight_card(insight: dict, notes: str = "", *, source: str = "") -> dict:
    """案件要点卡（主动反馈）：有 AI 摘要则展示，否则回规则摘要（完整度 + 缺失维度）。"""
    title = f"💡 案件要点 · {insight.get('case_name') or ''}".strip()
    els: list[dict] = []
    if notes:
        els.append(div(notes))
    else:
        filled = sum(1 for v in (insight.get("dims") or {}).values() if v)
        els.append(div(f"**五维完整度：{filled}/5**"))
        hints = insight.get("hints") or []
        if hints:
            els.append(div("**建议补充：**\n" + "\n".join(f"· {h}" for h in hints)))
        else:
            els.append(div("五维信息齐备，可继续出文书或做深入分析。"))
    if insight.get("basic_missing"):
        els.append(div("基础信息待补：" + "、".join(insight["basic_missing"])))
    return card(title, *els, template=BLUE, note_text=source)


def welcome_card(bot_name: str = DEFAULT_BOT_NAME) -> dict:
    return card(
        f"👋 {bot_name} 已就位",
        div(_CAPABILITIES),
        actions(
            button("📖 使用帮助", {"action": "help"}, "primary"),
            button("📋 案件列表", {"action": "list"}),
        ),
        note_text="用自然语言描述需求即可；发 PDF/DOCX 自动录入案件",
    )


_INTERNAL_ID_RE = re.compile(r"^(om|oc|ou|cli|msg|tmp|rec)_[A-Za-z0-9]{6,}$")


def _safe_case_name(name: str) -> str:
    """案件名去内部标识：飞书消息 id / 会话 id 被当成案件名时显示为「未命名案件」。"""
    text = (name or "").strip()
    if not text:
        return "未命名案件"
    if _INTERNAL_ID_RE.match(text):
        return "未命名案件"
    return text


def _case_line(idx: int, case: dict) -> str:
    return (
        f"**{idx}. {case.get('case_number') or '无案号'}**\n"
        f"📝 {_safe_case_name(case.get('case_name') or '')}"
        + (f"\n👤 {case.get('plaintiff')}" if case.get("plaintiff") else "")
        + (f"\n📌 {case.get('status') or 'pending'}" if case.get("status") else "")
    )


def _excerpt(content: str, limit: int = 120) -> str:
    """提取物正文摘要：去 markdown 记号、压空白、截断。"""
    text = (content or "").strip()
    if not text:
        return ""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def candidate_card(
    cases: list[dict], action: str = "", title: str = "", total: Optional[int] = None,
    note: str = "",
) -> dict:
    """候选案件卡（多命中消歧）：可**点选**，也可回复「第3个」。"""
    if not cases:
        return notice_card("🔍 未找到案件", "没有匹配的案件，请换个案件名或案号。", template=ORANGE)
    shown = len(cases)
    real_total = total if total is not None else shown
    header = (f"找到 **{real_total}** 个相关案件" if real_total <= shown
              else f"找到 **{real_total}** 个相关案件（显示前 {shown} 个）")
    els = [div(header + "，请点击下方案件，或直接回复序号（如「第3个」）：")]
    if note:
        els.append(div(f"*{note}*"))
    els.append(hr())
    for i, c in enumerate(cases, 1):
        els.append(div(_case_line(i, c)))
    btns = []
    for i, c in enumerate(cases[:5], 1):
        btns.append(button(
            f"{i}. {_safe_case_name(c.get('case_name') or '')}"
            if (c.get("case_name") or c.get("case_number")) else "案件",
            {"action": ACT_SELECT_CASE, "case_id": c.get("id", ""), "index": i, "next": action or ""},
        ))
    return card(title or "❓ 请选择案件", *els, actions(*btns))


def ask_case_card(cases: list, title: str = "🤔 请问要处理哪一案？", body: str = "") -> dict:
    """追问卡：说明缺什么线索，并给**最近案件**快捷入口（可点选），不让用户从零描述。"""
    body = body or "请提供案件名称或案号，例如「腾讯案的详情」「(2024)京0491民初123号 有哪些提取物」。"
    els = [div(body)]
    btns = []
    if cases:
        els.append(hr())
        els.append(div("**最近处理过的案件**（点击即可继续）："))
        for i, c in enumerate(cases[:5], 1):
            btns.append(button(
                f"{i}. {_safe_case_name(c.get('case_name') or '')}" if c.get("case_name") else f"案件 {i}",
                {"action": ACT_SELECT_CASE, "case_id": c.get("id", ""), "index": i, "next": ""},
                "primary" if i == 1 else "",
            ))
    return card(title, *els, actions(*btns) if btns else ())

def case_list_card(
    cases: list[dict], title: str = "📋 案件列表", total: Optional[int] = None
) -> dict:
    """案件列表卡。total 为筛选后的真实总数（cases 可能是被截断的前 N 条）。"""
    if not cases:
        return card(title, div("暂无案件记录"))
    shown = len(cases)
    real_total = total if total is not None else shown
    header = (
        f"共 **{real_total}** 个案件："
        if real_total <= shown
        else f"共 **{real_total}** 个案件（显示前 {shown} 个）："
    )
    els = [div(header), hr()]
    for i, c in enumerate(cases, 1):
        els.append(div(_case_line(i, c)))
    return card(title, *els)


def case_detail_card(detail: dict, mask: bool = False) -> dict:
    case = detail.get("case") or {}
    artifacts = detail.get("artifacts") or []
    health = detail.get("health") or {}

    def v(key: str, dash: str = "无") -> str:
        raw = case.get(key) or dash
        if key == "case_name":
            raw = _safe_case_name(raw)
        return mask_pii(raw) if mask else raw

    pairs = [
        ("案号", v("case_number")),
        ("名称", v("case_name")),
        ("原告", v("plaintiff")),
        ("被告", v("defendant")),
        ("案由", v("cause")),
        ("法院", v("court")),
        ("状态", v("status", "pending")),
        ("完整度", _health_text(health)),
    ]
    art_names = "、".join(artifact_label(a.get("artifact_type")) for a in artifacts) or "无"
    return card(
        "📋 案件详情",
        fields(pairs),
        hr(),
        div(f"**提取物**（{len(artifacts)}）：{art_names}"),
        actions(
            button("提取五维", {"action": ACT_EXTRACT, "case_id": case.get("id", "")}, "primary"),
            button("生成文书", {"action": ACT_GENERATE, "case_id": case.get("id", "")}),
        ),
        note_text="可继续说「提取物」「提取物的详细内容」或「起草答辩状」",
    )


def _health_text(health: dict) -> str:
    """完整度文案（口径单一真值在 ui.utils.compute_health：键为 health / passed / total）。"""
    h = health or {}
    pct = h.get("health")
    if pct is None:
        pct = 0
    passed, total = h.get("passed"), h.get("total")
    if passed is not None and total:
        return f"{pct}%（{passed}/{total} 项已就绪）"
    return f"{pct}%"


def artifacts_card(case: dict, artifacts: list[dict], mask: bool = False) -> dict:
    """提取物列表卡：维度名 + **正文摘要**（不止维度名）。"""
    name = case.get("case_name") or case.get("id", "")
    if not artifacts:
        return card("📦 提取物列表", div(f"**{name}** 暂无提取物"))
    els = [div(f"**{case.get('case_name') or case.get('id', '')}** 共 {len(artifacts)} 项"), hr()]
    for i, a in enumerate(artifacts, 1):
        label = artifact_label(a.get("artifact_type"))
        title = clean_artifact_title(a.get("title") or "")
        line = f"**{i}. {label}**" + (f" — {title}" if title and title != label else "")
        excerpt = _excerpt(a.get("content") or "")
        if excerpt:
            line += f"\n{excerpt}"
        els.append(div(mask_pii(line) if mask else line))
    return card("📦 提取物列表", *els)


def artifact_detail_card(case: dict, artifact: dict, mask: bool = False) -> dict:
    """单个提取物的正文详情卡。"""
    label = artifact_label(artifact.get("artifact_type") or artifact.get("type") or "")
    title = clean_artifact_title(artifact.get("title") or "")
    head = f"{label}" + (f" · {title}" if title and title != label else "")
    body = (artifact.get("content") or "").strip() or "（该维度暂无正文）"
    els = [div(f"**{case.get('case_name') or case.get('id', '')}**"), hr(), div(head), div(body)]
    return card("📄 提取物详情", *els)


def web_search_card(query: str, results: list[dict], *, source: str = "🌐 联网检索结果，请自行核实") -> dict:
    """联网检索结果卡（标题 + 链接 + 摘要）。无结果时给友好提示（不报错）。"""
    if not results:
        return card(
            "🌐 联网检索",
            div(f"没有检索到与「{query}」相关的公开资料。换种说法，或先看看本地案件。"),
            template=ORANGE,
            note_text=source,
        )
    els: list[dict] = [div(f"**「{query}」** 的相关公开资料："), hr()]
    for i, r in enumerate(results[:5], 1):
        title = r.get("title") or "（无标题）"
        url = r.get("url") or ""
        line = f"**{i}. [{title}]({url})**" if url else f"**{i}. {title}**"
        if r.get("snippet"):
            line += f"\n{r['snippet']}"
        els.append(div(line))
    return card("🌐 联网检索", *els, template=BLUE, note_text=source)


def corpus_answer_card(answer: str, ev: dict, *, source: str = "📚 基于本地案例库作答，请核对") -> dict:
    """语料问答卡：AI 答案 + **可核查的证据清单**（案件名 / 案号 / 维度 / 原文片段）。"""
    els: list[dict] = [div(answer or "（空）")]
    hits = (ev or {}).get("hits") or []
    if hits:
        els.append(hr())
        els.append(div(f"**依据（本地案例库 {len(hits)} 条）**："))
        for i, h in enumerate(hits, 1):
            src = " ".join(x for x in (h.get("case_name") or "", h.get("case_number") or "") if x)
            src = src or "（未命名案件）"
            dim = h.get("artifact_title") or ""
            snippet = (h.get("snippet") or "").strip()
            line = f"**[{i}] {src}**" + (f" · {dim}" if dim else "")
            if snippet:
                line += f"\n{snippet[:200]}"
            els.append(div(line))
    amt = (ev or {}).get("amounts") or {}
    if amt.get("count"):
        els.append(note(
            f"💰 样本金额：{amt['count']} 处，最低 {amt['min']/10000:.1f} 万元，"
            f"中位 {amt['median']/10000:.1f} 万元，最高 {amt['max']/10000:.1f} 万元"
        ))
    return card("📚 本地案例库 · 同类案件经验", *els, template=BLUE, note_text=source)


def corpus_empty_card(question: str) -> dict:
    """本地语料无命中：如实说「库里没有」，并给可操作的下一步（不编造）。"""
    return card(
        "📚 本地案例库暂无对应记录",
        div(f"围绕「{question}」在本地案例库与提取物正文中未检索到相关记载。\n\n"
            "可以换个更具体的关键词试试，例如：\n"
            "· 带上案由或权利类型（如「信息网络传播权 赔偿」「合理使用 抗辩」）\n"
            "· 直接指定案件或案号（如「(2024)京0491民初123号」）\n"
            "· 把材料发到会话，我按五维提取后再分析"),
        template=ORANGE,
        note_text="未检索到本地证据，故不给出结论",
    )


def privacy_refuse_card() -> dict:
    """明确拒绝索取个人敏感信息（PII 批量导出）——给出替代路径。"""
    return card(
        "🔒 无法提供该信息",
        div("批量导出当事人身份证号、手机号等个人敏感信息不在本助手的服务范围内。\n\n"
            "如确有办案需要，请通过内部合规流程在案件系统中按权限调取。"),
        template=ORANGE,
        note_text="个人信息保护：不批量导出个人敏感信息",
    )


def report_card(summary: dict) -> dict:
    pairs = [
        ("案件总数", str(summary.get("total_cases", 0))),
        ("已提取", str(summary.get("extracted_cases", 0))),
        ("待提取", str(summary.get("pending_cases", 0))),
        ("提取物", str(summary.get("total_artifacts", 0))),
        ("模板", str(summary.get("total_templates", 0))),
    ]
    els: list[dict] = [fields(pairs)]
    by_year = summary.get("by_year") or []
    if by_year:
        els.append(hr())
        els.append(div("**年度分布**\n" + "\n".join(
            f"· {r.get('year')}年：{r.get('count')}" for r in by_year[:8]
        )))
    by_cause = summary.get("by_cause") or []
    if by_cause:
        els.append(hr())
        els.append(div("**案由 Top**\n" + "\n".join(
            f"· {(r.get('cause') or '未知')[:20]}：{r.get('count')}" for r in by_cause[:5]
        )))
    return card("📊 案例库统计报告", *els)


def stats_card(stats: dict) -> dict:
    """维度化统计卡（聚合问法：年份分布 / 无案号计数 / 提取进度…）。

    要点：**给数字与口径**，不给清单——「有多少没案号」回 20 条案件等于没答。
    """
    rows = stats.get("rows") or []
    title = stats.get("title") or "📊 统计"
    total = stats.get("total")
    els: list[dict] = []
    if total is not None:
        els.append(div(f"库内案件总数：**{total}**"))
    if rows:
        els.append(hr())
        els.append(div("\n".join(f"· {r.get('label')}：**{r.get('count')}**" for r in rows)))
    else:
        els.append(div("暂无可统计的数据。"))
    note = stats.get("note")
    if note:
        els.append(hr())
        els.append(div(f"*{note}*"))
    els.append(actions(
        button("📋 案件列表", {"action": "list"}),
        button("📊 总体报告", {"action": "report"}),
    ))
    return card(title, *els, note_text="统计口径见卡片底部，可继续追问核对")


def templates_card(items: list[dict], title: str = "🗂 模板列表") -> dict:
    if not items:
        return card(title, div("暂无模板"))
    els = [div(f"共 **{len(items)}** 个模板："), hr()]
    for i, t in enumerate(items, 1):
        els.append(div(
            f"**{i}. {t.get('name') or '未命名'}**（{t.get('category') or '未分类'}）"
        ))
    return card(title, *els)


def template_detail_card(template: dict) -> dict:
    content = (template.get("content") or "").strip()
    if len(content) > 1200:
        content = content[:1200] + "\n…（已截断）"
    return card(
        f"🗂 {template.get('name') or '未命名'}",
        div(f"**分类**：{template.get('category') or '未分类'}"),
        hr(),
        div(content or "（空模板）"),
    )


def compare_card(case_a: dict, bundle_a: dict, case_b: dict, bundle_b: dict) -> dict:
    """两案对比卡：并排展示基础信息 + 各维度要点（有据可查，不臆造）。"""
    def _line(c: dict, bundle: dict, tag: str) -> str:
        arts = (bundle or {}).get("artifacts") or []
        dims = "、".join(
            (artifact_label(a.get("type") or "") or (a.get("title") or ""))
            for a in arts
        ) or "（无提取物）"
        return (
            f"**{tag} {c.get('case_name') or c.get('id', '')}**\n"
            f"案号：{c.get('case_number') or '无'}\n"
            f"案由：{c.get('cause') or '未登记'}\n"
            f"原告：{c.get('plaintiff') or '未登记'}　被告：{c.get('defendant') or '未登记'}\n"
            f"法院：{c.get('court') or '未登记'}　结果：{c.get('result') or '未登记'}\n"
            f"提取物：{dims}"
        )

    els = [div(_line(case_a, bundle_a, "【A】")), hr(), div(_line(case_b, bundle_b, "【B】"))]
    return card("🔀 案件对比", *els, note_text="基于两案已登记信息与提取物清单")


def match_card(base_case: dict, items: list[dict]) -> dict:
    head = f"**基准**：{base_case.get('case_name') or base_case.get('id', '')}"
    if not items:
        return card("🔗 相似案件", div(head), hr(), div("未找到相似案件"))
    els = [div(head), hr()]
    for i, m in enumerate(items, 1):
        reasons = "、".join(m.get("reasons") or []) or "-"
        els.append(div(
            f"**{i}. {m.get('case_name') or m.get('id', '')}**  相似度 {m.get('score', 0)}\n"
            f"   案号：{m.get('case_number') or '无'}\n"
            f"   依据：{reasons}"
        ))
    return card("🔗 相似案件", *els)


# =============================================
# 登记：表单卡 / 确认卡 / 结果卡
# =============================================

REGISTER_INPUTS = (
    ("case_number", "案号", "如 (2024)京0491民初123号"),
    ("plaintiff", "原告", "原告名称"),
    ("defendant", "被告", "被告名称"),
    ("cause", "案由", "如 著作权侵权"),
    ("court", "法院", "留空则按案号自动派生"),
)


def register_form_card(prefill: Optional[dict] = None) -> dict:
    prefill = prefill or {}
    els = []
    for name, label, ph in REGISTER_INPUTS:
        els.append(input_field(name, label, ph, default=str(prefill.get(name) or "")))
    els.append(hr())
    els.append(button("提交登记", {"action": ACT_REGISTER_SUBMIT}, "primary"))
    return card(
        "📝 登记新案件",
        form("register_form", *els),
        note_text="提交后自动查重；命中相似案件需二次确认",
    )


def duplicate_confirm_card(fields: dict, matches: dict) -> dict:
    els = [
        div("⚠️ **疑似重复案件**，请确认是否继续登记"),
        hr(),
        div("**待登记**\n" + "\n".join(
            f"· {k}：{v}" for k, v in fields.items() if v
        )),
    ]
    exact = (matches or {}).get("exact")
    partial = (matches or {}).get("partial") or []
    cause_fuzzy = (matches or {}).get("cause_fuzzy") or []
    els.append(hr())
    lines = ["**命中**"]
    if exact:
        c = exact.get("case") or {}
        lines.append(f"· 案号精确：{c.get('case_number') or ''} {c.get('case_name') or ''}")
    for m in partial[:3]:
        c = (m.get("case") if isinstance(m, dict) else None) or {}
        lines.append(f"· 当事人相近：{c.get('case_name') or ''}")
    for m in cause_fuzzy[:3]:
        c = (m.get("case") if isinstance(m, dict) else None) or {}
        lines.append(f"· 案由相近：{c.get('case_name') or ''}")
    if len(lines) == 1:
        lines.append("· （无详细命中信息）")
    els.append(div("\n".join(lines)))
    els.append(actions(
        button("仍然登记", {"action": ACT_REGISTER_CONFIRM, "fields": fields}, "danger"),
        button("取消", {"action": ACT_REGISTER_CANCEL}, "default"),
    ))
    return card("⚠️ 确认登记", *els, template=ORANGE)


def register_result_card(case: dict, hint: str = "") -> dict:
    els = [
        fields([
            ("案号", case.get("case_number") or "无"),
            ("名称", case.get("case_name") or "无"),
            ("法院", case.get("court") or "无"),
            ("年度", str(case.get("year") or "-")),
        ]),
    ]
    if hint:
        els.append(div(f"ℹ️ {hint}"))
    els.append(actions(
        button("查看详情", {"action": ACT_DETAIL, "case_id": case.get("id", "")}, "primary"),
        button("提取五维", {"action": ACT_EXTRACT, "case_id": case.get("id", "")}),
    ))
    return card(
        "✅ 案件登记成功",
        *els,
        template=GREEN,
        note_text=f"ID: {case.get('id', '')}（落库口径与 UI/CLI 一致）",
    )


_STEP_LABELS = {
    "list": "列出案件", "search": "搜索案件", "detail": "查看案件详情",
    "artifacts": "查看提取物", "match": "查找相似案件", "report": "统计总览",
    "templates": "查看文书模板", "register": "登记案件", "extract": "执行五维提取",
    "generate": "生成文书",
}


def agent_reply_card(answer: str, steps: Optional[list] = None, *, source: str = "",
                     title: str = "🤖 处理结果") -> dict:
    """ReAct agent 的最终回答卡：正文 + 执行步骤轨迹（便于核对「它到底做了什么」）。

    步骤以**业务动作**呈现（查案件 / 看案卷 / 提五维 …），不外露工具名等技术标识。
    """
    els = [div(answer or "（空）")]
    lines = [
        f"· {_STEP_LABELS.get(s.get('tool'), '处理')}{'：' + s['args'] if s.get('args') else ''}"
        for s in (steps or []) if s.get("tool")
    ]
    if lines:
        els += [hr(), div("**执行步骤**\n" + "\n".join(lines))]
    return card(title, *els, template=BLUE, note_text=source)


# =============================================
# 异步：处理中 / 提取结果 / 生成
# =============================================

def processing_card(title: str = "🕒 处理中…", detail: str = "") -> dict:
    body = "任务已受理，完成后会自动更新本卡片。" + (f"\n\n{detail}" if detail else "")
    return card(title, div(body), template=GREY)


def extract_result_card(case: dict, report: dict) -> dict:
    dims = report.get("dims") or {}
    dim_line = "  ".join(
        f"{'✅' if dims.get(k) else '⬜'} {_DIM_LABELS[k]}" for k in ("D1", "D2", "D3", "D4", "D5")
    )
    els = [
        div(f"**{case.get('case_name') or case.get('id', '')}**"),
        hr(),
        div(f"文件 {report.get('file_count', 0)} / 解析 {report.get('parsed_count', 0)}"),
        div(f"五维：{dim_line}"),
    ]
    if report.get("skipped"):
        els.append(div(f"⏭ 跳过：{report.get('reason', '')}"))
    elif report.get("imported"):
        els.append(div(f"✅ 已入库：`{report.get('case_id', '')}`，提取物 {len(report.get('artifact_ids') or [])} 个"))
    else:
        els.append(div(f"ℹ️ {report.get('reason', '仅提取未入库')}"))
    case_id = report.get("case_id") or case.get("id", "")
    els.append(actions(
        button("查看详情", {"action": ACT_DETAIL, "case_id": case_id}, "primary"),
        button("生成文书", {"action": ACT_GENERATE, "case_id": case_id}),
    ))
    tpl = GREEN if report.get("imported") else ORANGE
    return card("🧠 提取完成", *els, template=tpl)


def generate_form_card(case: dict, doc_types: dict, engines: list[str]) -> dict:
    btns = [
        button(name, {"action": ACT_GENERATE_RUN, "case_id": case.get("id", ""),
                      "doc_type": key, "engine": engines[0]}, "primary" if i == 0 else "default")
        for i, (key, name) in enumerate(doc_types.items())
    ]
    return card(
        f"📄 生成文书 · {case.get('case_name') or ''}",
        div(f"默认：{engine_label(engines[0])}"
            f"（可选：{'、'.join(engine_label(e) for e in engines) or '无'}）"),
        hr(),
        div("选择文书类型："),
        actions(*btns),
        note_text="生成较慢，先回处理中卡，完成后更新本卡",
    )


def generate_result_card(result: Any, case: dict, preview_chars: int = 1500,
                         *, truncated: bool = False) -> dict:
    ok = bool(getattr(result, "success", False))
    content = getattr(result, "content", "") or ""
    source = getattr(result, "source", "")
    error = getattr(result, "error", "")
    if len(content) > preview_chars:
        content = content[:preview_chars]
        truncated = True
    if not ok:
        return card("❌ 生成失败", div(error or "未知错误"), template=RED)
    els = [div(f"**来源**：{source_label(source)}"), hr(), div(content or "（空内容）")]
    if truncated:
        els.append(hr())
        els.append(div("内容较长，已分多段发送。说「**继续看**」或点下方按钮可逐段查看全文。"))
        els.append(actions(button("📄 继续看", {"action": ACT_DOC_MORE}, "primary")))
    return card(
        f"📄 生成完成 · {case.get('case_name') or ''}",
        *els,
        template=GREEN,
    )


def doc_more_card(chunk: str, pos: int, total: int) -> dict:
    """文书续看卡：给出下一段 + 进度 + 续看按钮。"""
    more = pos < total
    els = [div(chunk or "（空内容）")]
    if more:
        els.append(hr())
        els.append(div(f"已显示约 {pos}/{total} 字。说「**继续看**」或点下方按钮继续。"))
        els.append(actions(button("📄 继续看", {"action": ACT_DOC_MORE}, "primary")))
    else:
        els.append(hr())
        els.append(div("**已到全文末尾。**"))
    return card("📄 文书（续）", *els, template=GREEN)


def intake_intent_card(count: int, names: Optional[list[str]] = None,
                       bot_name: str = DEFAULT_BOT_NAME) -> dict:
    """收到附件但意图不明 → 先询问处理方式（不擅自录入）。"""
    names = [n for n in (names or []) if n]
    els = [
        div(f"已收到 **{count}** 个附件" + ("：" + "、".join(names[:5]) if names else "")),
        div(
            "请告知处理方式：\n"
            "**① 录入新案件**　建立案件档案，并将材料提取为五维（推荐）\n"
            "**② 并入已有案件**　回复「并入 ＜案件名或案号＞」，将材料补充进该案\n"
            "**③ 暂不处理**　保留附件，稍后再决定"
        ),
        actions(
            button("📥 录入新案件", {"action": ACT_INTAKE_CONFIRM}, "primary"),
            button("🚫 暂不处理", {"action": ACT_INTAKE_CANCEL}),
        ),
    ]
    return card(f"📎 {bot_name} · 收到材料，请确认处理方式", *els,
                note_text="附件已暂存 30 分钟；超时请重新发送")


def intake_confirm_card(count: int, names: Optional[list[str]] = None, act: str = "new",
                        ref: str = "", bot_name: str = DEFAULT_BOT_NAME) -> dict:
    """自然语言表达了对暂存材料的处置意图 → 回显 Bot 的理解，请其一键确认（不擅自写入）。

    与 intake_intent_card 的区别：本卡**已知 Bot 的判断**（录入新案 / 并入 X），
    把「确认」做成按钮，用户一键即可执行，无需再输入。
    """
    names = [n for n in (names or []) if n]
    head = f"已收到 **{count}** 个附件" + ("：" + "、".join(names[:5]) if names else "")
    if act == "merge":
        target = f"**{ref}**" if ref else "**已有案件**"
        guess = f"我理解为：把这份材料**并入 {target}**。"
        confirm = button("✅ 确认并入", {"action": ACT_INTAKE_MERGE, "case_id": ref}, "primary")
    else:
        guess = "我理解为：把这份材料**录入为新案件**（建案 + 提五维）。"
        confirm = button("✅ 确认录入", {"action": ACT_INTAKE_CONFIRM}, "primary")
    els = [
        div(head),
        div(guess + "　理解有误可改选其它："),
        actions(confirm, button("🚫 暂不处理", {"action": ACT_INTAKE_CANCEL})),
    ]
    return card(f"📎 {bot_name} · 请确认处理方式", *els,
                note_text="附件已暂存 30 分钟；超时请重新发送")


def intake_result_card(
    report: dict, saved: list[str], failed: list[str], staging: str = ""
) -> dict:
    """材料录入（附件 → 落盘 → 提取入库）结果卡。"""
    case_id = report.get("case_id") or ""
    dims = report.get("dims") or {}
    dim_line = "  ".join(
        f"{'✅' if dims.get(k) else '⬜'} {_DIM_LABELS[k]}" for k in ("D1", "D2", "D3", "D4", "D5")
    )
    els = [
        div(f"**已存盘** {len(saved)} 个附件" + (f"，失败 {len(failed)} 个" if failed else "")),
    ]
    if saved:
        els.append(div("\n".join(f"· {name}" for name in saved[:10])))
    if failed:
        els.append(div("⚠️ 下载失败：" + "、".join(failed[:10])))
    els.append(hr())
    if report.get("skipped"):
        els.append(div(f"⏭ 跳过入库：{report.get('reason', '')}"))
    elif report.get("imported"):
        els.append(div(
            f"文件 {report.get('file_count', 0)} / 解析 {report.get('parsed_count', 0)}\n"
            f"五维：{dim_line}"
        ))
        els.append(div(f"✅ 已入库：`{case_id}`，提取物 {len(report.get('artifact_ids') or [])} 个"))
    else:
        els.append(div(f"❌ 提取失败：{report.get('reason', '未知原因')}"))
    if case_id:
        els.append(actions(
            button("查看详情", {"action": ACT_DETAIL, "case_id": case_id}, "primary"),
            button("生成文书", {"action": ACT_GENERATE, "case_id": case_id}),
        ))
    tpl = GREEN if report.get("imported") else RED
    return card("📥 材料录入完成", *els, template=tpl, note_text=f"材料目录：{staging}" if staging else "")


def roles_card(snapshot: dict) -> dict:
    roles = snapshot.get("roles") or {}
    els = [div(
        f"**默认角色**：{snapshot.get('default_role') or '-'}\n"
        f"**白名单外**：{snapshot.get('unknown_policy') or '-'}\n"
        f"**映射文件**：{snapshot.get('roles_path') or '-'}"
    ), hr()]
    if roles:
        els.append(div("\n".join(f"· {k} → **{v}**" for k, v in roles.items())))
    else:
        els.append(div("白名单为空（未配置 LARK_ROLE_MAP，roles.json 不存在）"))
    return card("🔐 角色映射", *els)


def audit_card(rows: list[dict]) -> dict:
    if not rows:
        return card("🧾 Bot 审计", div("暂无审计记录"))
    els = [div(f"最近 **{len(rows)}** 条："), hr()]
    for r in rows:
        els.append(div(
            f"{r.get('ts') or '-'}　**{r.get('action') or '-'}**　{r.get('role') or '-'}\n"
            f"　案：{r.get('case_id') or '-'}　{r.get('result') or ''}"
        ))
    return card("🧾 Bot 审计", *els)


# =============================================
# 回调归一化（按钮 value / 表单 form_value）
# =============================================

def parse_action(action: dict) -> dict:
    """归一化卡片回调 payload → {action, value, form}。

    - 按钮点击：action = value["action"]
    - 表单提交：action = value["action"]（提交按钮的 value），form = form_value
    """
    action = action or {}
    value = action.get("value") or {}
    if not isinstance(value, dict):
        value = {}
    form_value = action.get("form_value") or {}
    if not isinstance(form_value, dict):
        form_value = {}
    name = value.get("action")
    if not name and form_value:
        name = _FORM_ACTION
    return {"action": name or "unknown", "value": value, "form": form_value}


def to_command_text(action: dict) -> str:
    """卡片回调 → 合成命令串（与文本命令同管线，SPEC §5）。"""
    payload = parse_action(action)
    return "/card " + json.dumps(payload, ensure_ascii=False, sort_keys=True)


# =============================================
# 降级为文本（CLI 模式 / 文本回执）
# =============================================

_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_HEAD = re.compile(r"^#+\s*", re.MULTILINE)


def flatten_text(card_json: dict) -> str:
    """把卡片 JSON 降级为纯文本（保留关键子串，便于 CLI/测试断言）。"""
    lines: list[str] = []
    header = card_json.get("header") or {}
    title = (header.get("title") or {}).get("content")
    if title:
        lines.append(title)
        lines.append("")
    for el in card_json.get("elements") or []:
        tag = el.get("tag")
        if tag == "div":
            if el.get("fields"):
                for f in el.get("fields") or []:
                    lines.append((f.get("text") or {}).get("content", ""))
            else:
                lines.append((el.get("text") or {}).get("content", ""))
        elif tag == "hr":
            lines.append("---")
        elif tag == "note":
            lines.append(" ".join(
                e.get("content", "") for e in el.get("elements") or [] if e.get("tag") == "plain_text"
            ))
        elif tag == "action":
            lines.append("[" + " · ".join(
                (b.get("text") or {}).get("content", "") for b in el.get("actions") or []
            ) + "]")
        elif tag == "form":
            for sub in el.get("elements") or []:
                if sub.get("tag") == "input":
                    label = (sub.get("label") or {}).get("content", "")
                    ph = (sub.get("placeholder") or {}).get("content", "")
                    lines.append(f"[{label}] {ph}")
                elif sub.get("tag") == "button":
                    lines.append("[" + (sub.get("text") or {}).get("content", "") + "]")
    text = "\n".join(line for line in lines if line is not None)
    text = _MD_BOLD.sub(r"\1", text).replace("`", "")
    return _MD_HEAD.sub("", text).strip()


__all__ = [
    "BLUE", "GREEN", "RED", "ORANGE", "GREY",
    "ACT_REGISTER_SUBMIT", "ACT_REGISTER_CONFIRM", "ACT_REGISTER_CANCEL",
    "ACT_DETAIL", "ACT_EXTRACT", "ACT_GENERATE", "ACT_GENERATE_RUN",
    "ACT_MATCH", "ACT_HELP",
    "div", "hr", "note", "button", "actions", "fields", "input_field", "form", "card",
    "artifact_label", "clean_artifact_title", "engine_label", "source_label",
    "mask_pii",
    "help_card", "error_card", "notice_card", "welcome_card", "guide_card",
    "DEFAULT_BOT_NAME",
    "case_list_card", "case_detail_card", "artifacts_card", "report_card",
    "templates_card", "template_detail_card", "match_card", "web_search_card",
    "register_form_card", "duplicate_confirm_card", "register_result_card",
    "processing_card", "extract_result_card", "generate_form_card", "generate_result_card",
    "intake_result_card", "roles_card", "audit_card",
    "parse_action", "to_command_text", "flatten_text",
]
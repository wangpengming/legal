#!/usr/bin/env python3
# =============================================
# lark_intent.py - 规则优先的意图路由（自然语言 → 命令）
#
# 目标：让 Bot 像「对话」而不是 CLI —— 用户说
#   「看看 2024 年的著作权案件」→ list 2024
#   「腾讯案的提取物」           → artifacts 腾讯
#   「帮我起草答辩状」           → generate（默认引擎）
#
# 原则：纯规则、无 LLM、确定性高、零成本；识别不了返回 None，
# 由 lark_bot 回「引导卡」而非报错。见 SPEC-feishu-bot §5。
#
# A（兜底）：规则确实没命中时，可由 `route_llm` 问一次云端 LLM（见文件下半部）。
#
# 与 lark_bot 解耦：只返回轻量 Intent，不依赖 Command（避免循环 import）。
# =============================================
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from .lark_policy import CONFIDENTIALITY_RULES

# 文书类型：中文名 → 内部 key（与 document_generator.DOC_TYPES 对齐）
DOC_TYPES = {
    "答辩状": "defense",
    "质证意见": "evidence_objection",
    "当庭陈述": "court_statement",
    "证据目录": "evidence_index",
}

# 抖动词 / 语气词：去掉后剩下的即案件引用或关键词
_NOISE = (
    "帮我", "帮忙", "请问", "麻烦你", "麻烦", "我想", "我要", "给我", "麻烦帮",
    "看一下", "看看", "看下", "瞅瞅", "查一下", "查查", "搜一下", "搜索", "搜搜",
    "找一下", "找找", "列出", "列一下", "翻一下", "来一份", "出一份",
    "一份", "一个", "一下", "这个", "那个", "这里的", "的资料", "的信息",
    "有哪些", "是什么", "怎么样", "如何", "什么",
    "呢", "吗", "吧", "啊", "呀", "哦", "嘛", "的话",
    "案子", "案件", "的案", "案", "的", "把",
)


@dataclass
class Intent:
    """识别出的意图：name 对应 lark_bot 的操作名，args 为引用/关键词。

    confident=False 表示「动作清楚但案件引用不明」——交给 LLM / agent 先理解，
    规则结果仅作兜底（避免把整句吐槽当成案件名硬查）。
    """
    name: str
    args: str = ""
    value: dict = field(default_factory=dict)
    confident: bool = True


_YEAR4_RE = re.compile(r"(19|20)\d{2}")
_YEAR2_RE = re.compile(r"(?<!\d)(\d{2})\s*年")
# 有信息量的引用：含 ≥2 连续汉字 / 指代词 / ≥4 位字母数字串（案号、ID）
_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_PRONOUN_RE = re.compile(r"[它他她其这那]")
_ALNUM_RE = re.compile(r"[A-Za-z0-9]{4,}")

# 案号识别——用于把「对(2024)京0105民初20921号案 的五维提取物」这类
# 带前后缀的句子中的**案号原样抽出来**（前后缀「对 / 案 / 的 / 五维」不参与匹配）：
#   仲裁：京朝劳人仲字（2023）第14652号
#   括号：(2024)京0491民初123号 / （2023）北互预民字第92799号
#   无括号：2024京0491民初7776号
_CASENO_RE = re.compile(
    r"[\u4e00-\u9fff]{2,10}仲字\s*[（(【\[]\s*\d{4}\s*[)）】\]]\s*第?\s*\d+[、，,\d]*号"
    r"|[（(【\[]\s*(?:19|20)\d{2}\s*[)）】\]]"
    r"|(?:19|20)\d{2}\s*[\u4e00-\u9fff]{1,2}\d{2,}"
)
# 向右扫描的截断符：遇到句读即止（不截「、」「,」——多案号形如 2332、2335、197号）
_CASENO_TAIL_STOP = set("？?！!。；;：:\n\t")

# 「方法性提问」标记：问到做法 / 需要什么 / 流程 → 应回 help（能力说明），勿当动作执行
_METHOD_Q_RE = re.compile(r"(需要|哪些|什么|怎么|如何|流程|步骤|要求|准备|注意事项)")

# 开放式分析 / 讨论标记：就某个案件问看法、风险、思路（≠ 重跑提取）
_DISCUSS_RE = re.compile(
    r"(分析|讨论|评估|怎么看|如何看|怎么样|评价|站不站得住|站得住|能不能赢|胜诉|赢面|"
    r"抗辩|答辩思路|风险|思路|策略|方案|建议|漏洞|弱点|应对|怎么打|如何打|是否有理|主张是否|"
    r"争议焦点|争点|焦点是什么|关键点)"
)
_DISCUSS_STRIP = (
    "分析", "讨论", "评估", "怎么看", "如何看", "怎么样", "评价", "站不站得住", "站得住",
    "能不能赢", "胜诉", "赢面", "可能性", "有多大", "抗辩", "答辩思路", "风险", "思路",
    "策略", "方案", "建议", "漏洞", "弱点", "应对", "怎么打", "如何打", "是否有理", "主张是否",
    "争议焦点", "争点", "焦点", "帮我", "请", "结合", "根据", "看看", "看下", "一下", "有什么", "有哪些", "吗",
)


def normalize_year(text: str) -> Optional[str]:
    """从文本取年份并归一为 4 位：'2024' → '2024'，'24年' → '2024'，'98年' → '1998'。"""
    m = _YEAR4_RE.search(text or "")
    if m:
        return m.group(0)
    m = _YEAR2_RE.search(text or "")
    if m:
        n = int(m.group(1))
        return str(2000 + n) if n <= 40 else str(1900 + n)
    return None


def _meaningful(ref: str) -> bool:
    """引用是否有信息量（避免把「查 24 年 件情况」这类削噪残渣当案名）。"""
    if not ref:
        return False
    return bool(_CJK_RE.search(ref) or _PRONOUN_RE.search(ref) or _ALNUM_RE.search(ref))


# 引用质量门禁——判「像案件名/案号」还是「整句啰嗦话」。
# 「案件引用」应短且干净；长度或对话噪声越界即视为**不可信**，不冒充命中，
# 交由 LLM 理解（否则会把整句当案名去检索，回「未找到案件」乱码）。
_REF_MAX = 16
_REF_NOISE_RE = re.compile(
    r"(我|你|他|她|咱|请|麻烦|需要|要求|以上|以下|结合|根据|想让|让你|帮我|关于|怎么|如何|流程|步骤|"
    r"一下|这个|那个|这份|那份)"
)
# 元评论残渣：用户吐槽式表述（「不是简单的列表」「怎么回事」）不是案件名。
# 命中即视为**无引用**——交由会话记忆 / 追问，绝不当案名去检索。
_REF_META_RE = re.compile(
    r"(不是|而是|而不是|简单|列表|正文|全文|具体内容|详细信息|怎么回事|什么意思|之类|等等|来看|说说)"
)

# 指代 + 案件（「那一个案子」「这个案件」「此案」）——引用应归零，交会话记忆补全
_PRONOUN_CASE_RE = re.compile(
    r"(那一个|这一个|那个|这个|那一宗|这一宗|那一案|这一案|那一件|这一件|那一笔|这一笔|此案|该案|本案|上述案件|前述案件)"
)

# 泛化知识 / 经验问题（「这类案子一般判多少钱」「有没有类似案件」）→ 走语料检索（corpus）
#   · 有具体案件指向（「腾讯案的争议焦点」）→ discuss（基于该案证据包）
#   · 泛指同类问题 → corpus：先查本地案例语料（带出处），再考虑联网
_CORPUS_RE = re.compile(
    r"(这类|此类|类似案件|类似案|相似案件|一般判|通常判|判多少|赔多少|赔偿多少|赔偿标准|"
    r"裁判标准|司法解释|裁判规则|行业惯例|一般标准|都是多少|通常多少|标准是多少|"
    r"赔偿数额|赔偿区间|一般能判|能判多少)"
)
# 泛指 + 问判法（「…一般怎么判」「…通常怎么赔」）——带泛指词才是**经验问题**，
# 否则「腾讯案怎么判」这类带具体案件的问法不该被当成语料泛问。
_CORPUS_GENERIC_RE = re.compile(
    r"(一般|通常|这类|此类|类似|相似|平常).{0,8}"
    r"(怎么判|如何判|怎么赔|如何赔|判多少|赔多少|怎么计算|如何计算|怎么处理|怎么认定)"
)
# 「找相似案件」是**动作**（走 match），与「同类案件一般怎么判」的经验问题区分开
_FIND_SIMILAR_RE = re.compile(
    r"(找|搜|搜索|查询|查一下|查下|看看|列出|匹配|推荐|推).{0,6}(相似|类似|相近|同类)"
)
# 概念 / 计算类问句（「什么是惩罚性赔偿」「法定赔偿怎么计算」）→ 也要查本地语料，
#   但须同时命中**法律领域词**，避免「今天什么是好天气」误入。
_CONCEPT_Q_RE = re.compile(r"(什么是|怎么计算|如何计算|怎么算|如何算|怎么赔偿|如何赔偿|标准是什么|依据是什么)")
_LEGAL_TOPIC_WORD_RE = re.compile(
    r"(赔偿|侵权|著作权|作品|信息网络传播权|合理使用|法定|惩罚性|举证|责任|抗辩|时效|"
    r"管辖|著作权法|民法典|商标|专利|不正当竞争|损失|违约|合同|劳务|劳动)"
)

# 聚合统计问法（「案件都有哪些年份」「有多少没案号」）——**须先于案件列表判定**，
# 否则「有多少没案号」会被降级成「列 20 条案件」——机械且答非所问。
_COUNT_Q_RE = re.compile(r"(有多少|多少[个件起条]?|几件|几个|数量|占比)")
# 「相关 / 匹配 / 类似」+ 计数 = **带条件的检索**，不是全库统计
_RELATIVE_COUNT_RE = re.compile(r"(相关|匹配|类似|相似|同名)")
_STATS_DIM_RULES: tuple = (
    ("no_number", re.compile(r"(没有|无|缺|未填|没填|未登记).{0,4}案号|案号.{0,4}(没有|无|为空|缺失|未登记)")),
    ("extracted", re.compile(r"(已提取|提取过|有提取物|做过提取|提取完成)")),
    ("pending", re.compile(r"(未提取|没提取|待提取|没做提取|没有提取|未做提取)")),
    ("year", re.compile(r"(年份|年度|哪一年|哪些年|哪几年)")),
    ("cause", re.compile(r"(案由|事由|什么类型|哪类案件|哪类案子)")),
    ("court", re.compile(r"(法院|哪家法院|哪个法院)")),
    ("status", re.compile(r"(状态|提取进度|提取情况|提取了多少)")),
    ("quality", re.compile(r"(质量|完整度|完备程度|A级|B级|C级)")),
)


def _stats_dim(text: str) -> str:
    """从问句里判定统计维度（无维度线索 → 年份分布）。"""
    t = text or ""
    for dim, pat in _STATS_DIM_RULES:
        if pat.search(t):
            return dim
    return "year"


def _is_stats_query(text: str) -> bool:
    """是否是**聚合统计**问法（要数字 / 分布，不要逐条列表）。"""
    t = text or ""
    dist = bool(
        re.search(r"(都有哪些|有哪几|哪些|哪几|分别有|各有哪些).{0,6}"
                  r"(年份|年度|案由|法院|类型|状态|质量)", t)
        or re.search(r"(年份|年度|案由|法院|类型|状态|质量).{0,3}(分布|构成|统计|占比)", t)
        or re.search(r"(分布|构成).{0,4}(年份|年度|案由|法院)", t)
    )
    if not _COUNT_Q_RE.search(t):
        return dist
    if _RELATIVE_COUNT_RE.search(t):
        return False                      # 带条件的检索（「有多少相关的案子」）
    if dist:
        return True
    # 计数问法里带「找 / 搜 / 检索」的是**检索**（要匹配的案子），不是全库统计
    return not re.search(r"(找|搜|检索|匹配|推荐)", t)


# 法规 / 法条 / 司法解释类问题 → 不查案例，走法规库 + 联网（law_lookup）
_LAW_TOPIC_RE = re.compile(
    r"(第\s*\d+\s*条|法条|司法解释|法规原文|法律原文|规范性文件|实施细则|批复)"
)

# 与案件业务无关的闲聊 → 直接友好回应，别当案件检索
_CHITCHAT_RE = re.compile(
    r"(天气|气温|下雨|股票|股价|基金|彩票|菜谱|做饭|讲个笑话|笑话|唱歌|唱首|"
    r"写首诗|写诗|首诗|情话|星座|运势|足球|篮球|游戏|电影推荐)"
)


# 口语填充残渣（「刚才 后来 了」）——剔除后为空即视为**无引用**，交会话记忆 / 追问
_FILLER_REF_RE = re.compile(
    r"(刚才|刚刚|之前|上次|先前|后来|然后|接着|最后|到底|究竟|那会儿|这会儿|的话|了|的|嘛|呢|吧|呀|啊)"
)


def is_law_topic(text: str) -> bool:
    """文本是否是法规 / 法条类问题（应走法规库 + 联网，而不是案件检索）。"""
    return bool(_LAW_TOPIC_RE.search(text or ""))


def _corpus_query(t: str) -> bool:
    """是否是「同类案件经验 / 裁判标准」类问题（走本地语料检索，有据作答）。

    「找相似案件」是检索动作（match），「类似案件一般怎么判」是经验问题（corpus）。
    """
    if _FIND_SIMILAR_RE.search(t or ""):
        return False
    return bool(
        _CORPUS_RE.search(t or "")
        or _CORPUS_GENERIC_RE.search(t or "")
        or (_CONCEPT_Q_RE.search(t or "") and _LEGAL_TOPIC_WORD_RE.search(t or ""))
    )


def _filler_only(ref: str) -> bool:
    """引用是否**只有**口语填充词（「刚才 后来 了」）——是则当作指代，交会话记忆补全。"""
    r = (ref or "").strip()
    if not r:
        return False
    return not _FILLER_REF_RE.sub("", r).strip()


def _ref_ok(ref: str) -> bool:
    """引用是否可信（像案件名/案号/指代）；长句或含对话噪声 → False（交 LLM 理解）。"""
    r = (ref or "").strip()
    if not r:
        return False
    if _extract_case_number(r):                       # 案号：放行
        return True
    if all(ch in "它他她牠这那该此其之" for ch in r):  # 纯指代：放行（交会话记忆补全）
        return True
    if len(r) > 3 and not _FILLER_REF_RE.sub("", r).strip():
        return False                                   # 全是口语填充残渣：无引用
    if len(r) > _REF_MAX:                             # 过长：多是整句
        return False
    if _REF_NOISE_RE.search(r):                       # 含对话/语气噪声：不可靠
        return False
    if _REF_META_RE.search(r):                        # 元评论残渣：不是案件名
        return False
    return _meaningful(r)


def _extract_case_number(text: str) -> str:
    """从自由文本抽取案号（原样返回，含括号 / 内部空格）；无则 ""。

    只在确实「像案号」时才命中——`2024 年的案件` 这类年份闲聊不会被误当案号
    （无括号分支要求「年份 + 地区字 + 数字」，`2024年` 不满足）。
    """
    t = text or ""
    m = _CASENO_RE.search(t)
    if not m:
        return ""
    if m.group(0).endswith("号"):
        return m.group(0).strip()
    # 从匹配起点向右扫到「号」；含空格（案号常写成「（2025）鲁 0281 民初 13392 号」）
    buf = []
    for ch in t[m.start():]:
        if ch in _CASENO_TAIL_STOP:
            break
        buf.append(ch)
        if ch == "号" or len(buf) >= 48:
            break
    return "".join(buf).strip()


def _strip_noise(text: str, extra: tuple = ()) -> str:
    """剔除抖动词，返回纯净的引用 / 关键词（长词优先，避免误切）。

    🔴 保留 `()`/`（）` 与 `、`：案号形如 `(2025)川0193民初17630号`，
    案名形如 `纽凯诉雷客、金麦客著作权纠纷`——被换成空格即切成多 token，引用失效。
    🔴 文本含案号时**直接返回案号**（前后缀「对…案 的五维」等一律丢弃）。
    """
    caseno = _extract_case_number(text)
    if caseno:
        return caseno
    out = text
    for word in sorted(set(extra) | set(_NOISE), key=len, reverse=True):
        out = out.replace(word, " ")
    out = re.sub(r"[？?！!。，,；;：:\s]+", " ", out)
    return out.strip().strip("、,，。；;：: ")


def _join(*parts: str) -> str:
    return " ".join(p for p in (s.strip() for s in parts) if p)


# 候选序号（「第3个」「第三个」「3」）——多命中时用来点选
_ORDINAL_RE = re.compile(
    r"^(?:选|要|就|取|看|用)?\s*(?:第)?\s*([0-9０-９]{1,3}|[一二三四五六七八九十]{1,3})\s*(?:个|号|条|项|款)?$"
)
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}


def parse_ordinal(text: str) -> int:
    """把「第3个」「第三个」「3」解析成序号（1 起）；解析不出返回 0。"""
    m = _ORDINAL_RE.match((text or "").strip())
    if not m:
        return 0
    tok = m.group(1)
    if tok.isdigit():
        return int(tok)
    if tok == "十":
        return 10
    if len(tok) == 1:
        return _CN_DIGITS.get(tok, 0)
    if len(tok) == 2 and tok[0] == "十":          # 十一 ~ 十九
        return 10 + _CN_DIGITS.get(tok[1], 0)
    if len(tok) == 2 and tok[1] == "十":          # 二十 ~ 九十
        return _CN_DIGITS.get(tok[0], 0) * 10
    if len(tok) == 3 and tok[1] == "十":          # 二十一 ~ 九十九
        return _CN_DIGITS.get(tok[0], 0) * 10 + _CN_DIGITS.get(tok[2], 0)
    return 0


def _lite(text: str) -> str:
    """归一化用于「参数是否出自用户原话」比对：NFKC + 去非字母数字/汉字 + 小写。"""
    s = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[^0-9a-z一-鿿]+", "", s)


# 无需案件引用的工具（args 自由：内部填 / 无参）
_ARG_FREE_TOOLS = {"report", "templates", "help", "register", "advise", "say", "list"}


def args_provable(args: str, raw: str) -> bool:
    """LLM 给的 args 是否**出自用户本轮原话**。

    🔴 自证机制：模型常把历史对话里的案件名当成用户这轮给的引用（实测「提取物」→ 臆造
    「腾讯案」）。args 必须在原话里找得到，否则视为臆造 → 清空，交会话记忆 / 追问。
    """
    a = (args or "").strip()
    if not a:
        return True
    if a in _ARG_FREE_TOOLS:
        return True
    la, lr = _lite(a), _lite(raw)
    if not la:
        return False
    if la in lr:
        return True
    if re.fullmatch(r"(19|20)\d{2}", a):            # 年份：「24年」→ 2024
        return normalize_year(raw) == a
    cn = _extract_case_number(raw)                 # 案号：括号全半角差异
    if cn and _lite(cn) == la:
        return True
    return False


def route(text: str) -> Optional[Intent]:
    """自然语言 → Intent；识别不了返回 None。"""
    raw = (text or "").strip()
    if not raw:
        return None
    t = raw
    low = raw.lower()

    # 候选序号选择（「第3个」「第三个」）——多命中后的消歧动作
    ordinal = parse_ordinal(raw)
    if ordinal:
        return Intent("select", str(ordinal))

    # 帮助 / 能力询问
    if "help" in low or re.search(r"(帮助|怎么用|怎么使用|使用方法|能做什么|能干什么|有什么功能|功能列表)", t):
        return Intent("help")

    # 闲聊（天气 / 写诗 / 股票…）——与案件业务无关，别当案件检索
    if _CHITCHAT_RE.search(t) and not re.search(r"(案件|案子|案由|提取物|文书)", t):
        return Intent("say", "", confident=True)

    # 法规 / 法条 / 司法解释 → 法规库 + 联网（不查案例）
    if _LAW_TOPIC_RE.search(t) and not re.search(r"(提取物|我的案件|这个案件|该案件)", t):
        return Intent("law_lookup", raw, confident=True)

    # 统计报告
    if re.search(r"(统计|报告|概览|汇总|总览|总共|一共|合计|整体情况)", t) or \
       re.search(r"有多少(个)?(案件|案子)", t):
        return Intent("report")

    # 聚合统计问法（「都有哪些年份」「有多少没案号」）——须先于**案件列表**判定，
    # 否则会退化成「列 20 条案件」：数量问题给清单 = 答非所问
    if _is_stats_query(t) and not _corpus_query(t) and re.search(
            r"(案件|案子|案例|卷宗|多少|年份|年度|案由|法院|提取|状态|质量|类型)", t):
        return Intent("stats", raw, {"dim": _stats_dim(t)}, confident=True)

    # 登记新案（表单卡）——「怎么登记 / 需要什么」这类方法性提问 → advise（业务化解答，勿当动作执行）
    if re.search(r"(登记|新建|录入|添加|新增|创建|报个|立个)", t) and re.search(r"(案件|案子|案|新案)", t):
        return Intent("advise", raw) if _METHOD_Q_RE.search(t) else Intent("register")

    # 生成文书（含类型）
    dm = re.search(r"(答辩状|质证意见|当庭陈述|证据目录)", t)
    if dm and re.search(r"(生成|起草|写|拟|出具|整一份|来一份|出一份|弄一份)", t):
        doc = DOC_TYPES[dm.group(1)]
        ref = _strip_noise(
            t.replace(dm.group(1), " "),
            ("生成", "起草", "写", "拟", "出具", "整一份", "来一份", "出一份", "弄一份", "文书"),
        )
        ok = _ref_ok(ref)
        return Intent("generate", ref if ok else "", {"doc_type": doc}, confident=ok)

    # 泛泛的「起草 / 生成文书」（未指明文书类型）：
    #   问做法 / 需要什么 → advise（业务化解答，勿当动作执行）；否则 → generate（再追问案件）
    if re.search(r"(起草|生成|写|拟|出具)", t) and re.search(r"文书", t):
        if _METHOD_Q_RE.search(t):
            return Intent("advise", raw)
        ref = _strip_noise(t, ("起草", "生成", "写", "拟", "出具", "法律文书", "文书"))
        ok = _ref_ok(ref)
        return Intent("generate", ref if ok else "", confident=ok)

    # 泛化知识 / 经验问题（「这类案子一般判多少钱」「有没有类似案件的做法」）→ corpus
    #   （有具体案件指向时由下面的 discuss 分支接手）
    #   ⚠️ 须先于「相似案件」判定：「类似案件一般怎么判」是经验问题，不是找相似案
    if _corpus_query(t):
        return Intent("corpus", raw, confident=True)

    # 相似案件
    if re.search(r"(相似|类似|相近|同类)", t):
        ref = _strip_noise(t, ("相似", "类似", "相近", "同类", "找", "看看", "看"))
        ok = _ref_ok(ref)
        return Intent("match", ref if ok else "", confident=ok)

    # 两案对比（「对比一下百度和腾讯那个著作权案子」）——拆成两个引用，交 compare 执行
    if re.search(r"(对比|比较|相比|区别|差异)", t):
        return Intent("compare", raw, confident=True)

    # 文书模板列表
    if "模板" in t and re.search(r"(有哪些|列表|列出|所有|全部|哪些|多少)", t):
        return Intent("templates")

    # 提取物正文 / 详细内容（「提取物的详细信息」「把事实认定展开」）——须先于「提取物列表」判定
    if re.search(r"(提取物|材料清单|卷宗|证据材料)", t) and \
            re.search(r"(正文|内容|详细|全文|展开|具体)", t):
        ref = _strip_noise(t, ("提取物", "材料清单", "卷宗", "证据材料", "正文", "内容",
                               "详细", "全文", "展开", "具体", "看看", "看一下", "查看", "看"))
        return Intent("artifact_content", ref if _ref_ok(ref) else "", confident=_ref_ok(ref))

    # 提取物 / 材料清单——命中即返回（引用不可信则留空，交会话记忆 / 追问，勿再往下掉）
    if re.search(r"(提取物|材料清单|卷宗|证据材料)", t):
        ref = _strip_noise(t, ("提取物", "材料清单", "卷宗", "证据材料", "列出", "看看", "看"))
        ok = _ref_ok(ref)
        return Intent("artifacts", ref if ok else "", confident=ok)

    # 开放式分析 / 讨论（基于该案材料有据作答）——须先于「提取」判定：
    # 「分析腾讯案的风险」是讨论，不是重跑提取；含「提取 / 五维 / 解析」才是提取动作
    if _DISCUSS_RE.search(t) and not re.search(r"(提取|五维|解析|材料清单)", t):
        ref = _strip_noise(t, _DISCUSS_STRIP)
        if _filler_only(ref):
            # 「刚才那个案子后来怎么样了」→ 纯指代：引用归零，交会话记忆补全
            return Intent("discuss", "", {"question": raw}, confident=True)
        ok = _ref_ok(ref)
        return Intent("discuss", ref if ok else "", {"question": raw}, confident=ok)

    # 触发提取（分析材料）——方法性提问（「提取需要准备什么」）→ advise
    if re.search(r"(提取|解析|分析)", t) and re.search(r"(五维|材料|案|卷)", t):
        if _METHOD_Q_RE.search(t):
            return Intent("advise", raw)
        ref = _strip_noise(t, ("提取", "解析", "分析", "五维", "内容",
                               "材料", "文件", "文档", "附件", "这份", "该材料"))
        # 引用不可信（整句/啰嗦）→ 不冒充命中，交 LLM / 会话记忆
        ok = _ref_ok(ref)
        return Intent("extract", ref if ok else "", confident=ok)

    # 文书续看（「怎么才能看完整的内容」「继续看」「下一段」）——按「上一份文书」分段续发
    if not _extract_case_number(t) and not re.search(r"(案件|案子|提取物|材料清单|案卷)", t) \
            and re.search(r"(继续看|接着看|下一段|下一部分|下一批|剩下的|剩余|看完整|完整内容|全文|没看完|还没看完|继续发)", t):
        return Intent("doc_more", raw)

    # 指代 + 案件（「我只看那一个案子的情况」）——引用归零，交会话记忆补全最近案件
    if _PRONOUN_CASE_RE.search(t) and re.search(r"(案件|案子|案卷|材料|提取物|情况|详情|内容)", t):
        return Intent("detail", "", confident=True)

    # 案件列表（强标记：年份 / 所有 / 全部 / 列表 / 有哪些）——须先于「详情」判定
    # 🔴 文本含案号时不得走列表：「查看（2023）京0491民初23751号完整案件详情」里的年份
    #    来自案号本身，走列表会返回一批无关案件。
    ym = normalize_year(t)
    if not _extract_case_number(t) and re.search(r"(案件|案子|案)", t) and (
        ym or re.search(r"(列表|列出|所有|全部|有哪些|哪些|多少|浏览|翻)", t)
    ) and not (_RELATIVE_COUNT_RE.search(t) and _COUNT_Q_RE.search(t)):
        return Intent("list", ym or "")

    # 案件详情
    if re.search(r"(详情|详细信息|具体情况|看看|看一下|查看|打开|了解|介绍)", t):
        ref = _strip_noise(t, ("详情", "详细信息", "具体情况", "看看", "看一下", "查看", "打开", "了解", "介绍"))
        ok = _ref_ok(ref)
        return Intent("detail", ref if ok else "", confident=ok)

    # 案件列表（弱标记：查/看/列 + 案件）——含案号或指代时不得走列表
    if not _extract_case_number(t) and not _PRONOUN_CASE_RE.search(t) \
            and re.search(r"(案件|案子)", t) and re.search(r"(查|看|列)", t):
        return Intent("list")

    # 搜索（关键词）
    sm = re.search(r"(搜索|搜|查找|查|找)\s*(一下|一找)?\s*(.+)", t)
    if sm:
        kw = _strip_noise(sm.group(3))
        if _ref_ok(kw) or (kw and not _REF_NOISE_RE.search(kw)):
            return Intent("search", kw)

    return None


# =============================================
# A：LLM 兜底意图（规则未命中时才调用）
# =============================================

# 工具目录：规则路由与 LLM 提示词共用的**唯一真值**（名字须与 lark_bot 的 _op_* 对齐）
TOOL_SPECS = (
    ("list", "列出案件（可按年份筛选）", "看看 2024 年的案件"),
    ("search", "按关键词搜索案件", "搜一下腾讯"),
    ("detail", "查看某个案件的详情", "腾讯案的详情"),
    ("artifacts", "查看某案件的提取物 / 材料清单", "腾讯案有哪些提取物"),
    ("artifact_content", "查看某案件提取物的**正文内容**（各维度的详细分析）",
     "腾讯案提取物的详细内容"),
    ("doc_more", "继续查看**上一份文书**被截断的剩余内容（逐段续看）", "继续看"),
    ("report", "案件统计总览", "统计一下"),
    ("stats", "**按维度统计**（要数字/分布，不要清单）：年份分布 / 无案号计数 / 提取进度 / "
              "案由或法院分布（args 填用户原话）", "案件都有哪些年份的"),
    ("templates", "文书模板列表，或 `search ＜关键词＞`", "有哪些文书模板"),
    ("match", "查找相似案件", "有没有跟腾讯案相似的案件"),
    ("compare", "对比两个案件（args 填「A 和 B」形式的两个案件引用）",
     "对比一下腾讯案和纽凯诉雷客案"),
    ("register", "登记一个新案件", "登记一个新案件"),
    ("extract", "对某案件执行五维提取", "把腾讯案的材料提取一下"),
    ("discuss", "就某个案件做开放式分析 / 讨论（争议焦点、风险、应对思路；只依据该案材料，不编造）",
     "腾讯案的抗辩思路怎么看"),
    ("generate", "为某案件生成文书（可指定 答辩状/质证意见/当庭陈述/证据目录）", "帮我起草腾讯案的答辩状"),
    ("web_search", "联网检索与法务业务相关的公开资料（法律法规 / 司法解释 / 裁判规则 / 公开案例）；"
                   "仅在需要外部信息时用，翻查本地案件不要用", "最新的人身损害赔偿标准是多少"),
    ("law_lookup", "查具体法条：先查**本地法规库**（离线、权威），未命中再联网检索"
                   "（args 填法条名 / 条号 / 关键词，如「著作权法第24条 合理使用」）",
     "著作权法第24条是怎么规定的"),
    ("corpus", "就**本地案例库**里的同类案件经验提问（这类案子一般判多少 / 同类案件怎么判 / 赔偿标准是多少）；"
               "基于库内既有案件与提取物作答并标注出处，不凭记忆写法条",
     "这类案子一般判多少钱"),
    ("advise", "就「怎么做 / 需要准备什么材料 / 流程步骤」等**业务方法性**问题给出具体解答"
               "（args 填用户问题原话）", "起草答辩状需要准备哪些材料"),
    ("help", "说明 Bot 能做什么", "你能做什么"),
)

_TOOL_NAMES = tuple(name for name, _desc, _ex in TOOL_SPECS)

SYSTEM_PROMPT = (
    "你是法务案例智能助手「案小智」的意图解析器：把用户的一句话映射为**一个**工具调用。\n"
    "可选工具（tool 取其一）：\n"
    + "\n".join(f"- {name}：{desc}　例：{ex}" for name, desc, ex in TOOL_SPECS)
    + "\n- none：没有合适工具时用（闲聊 / 与案件和法务业务都无关），并在 say 字段给出**简短友好**的中文回复。\n"
    "判定原则：\n"
    "· 只要与「案件 / 案卷 / 提取物 / 文书 / 统计」相关，**必须**选一个工具，不要用 none。\n"
    "· 「看看某年的案件 / 某年有哪些案子 / 24 年的案件情况」→ list（args 填四位年份，如 2024）。\n"
    "· 「统计 / 报告 / 汇总 / 一共多少」→ report。\n"
    "· 用户要看提取物的**正文内容 / 详细分析**（「提取物详细信息」「展开事实认定」）→ artifact_content。\n"
    "· 问到**外部**法律知识（法条、司法解释、赔偿标准、裁判规则、公开判例等）→ web_search。\n"
    "· 问**具体法条内容 / 条号**（「著作权法第24条怎么说」）→ law_lookup（先本地法规库，未命中再联网）。\n"
    "· 问**同类案件的经验 / 通常判多少 / 一般怎么判**（含「这类」「类似案件」「一般判」"
    "「判多少」「赔偿标准是多少」）→ corpus（基于本地案例库作答并给出处）。\n"
    "· 询问「怎么做 / 需要什么 / 有什么要求 / 流程」这类**方法性、咨询性**问题 → advise"
    "（args 填用户问题原话），不要映射为 artifacts / generate 等动作工具。\n"
    "· 就**某个具体案件**问看法 / 风险 / 抗辩思路 / 怎么应对 → discuss（args 填案件引用，"
    "不要映射为 extract）。\n"
    "· 只有明确的**非业务**话题（闲聊、探询系统/配置/他人信息等）才用 none。\n"
    "只输出 JSON，不要解释、不要代码围栏：\n"
    '{"tool": "＜工具名或 none＞", "args": "＜案件引用 / 关键词 / 四位年份；无参工具留空＞", "say": "＜仅 tool=none 时填＞"}\n'
    "args 只填用户说出的**案件名称或案号**（照抄，勿改写/翻译/补全）；"
    "**用户没给出可识别的案件时，args 必须留空**（由 Bot 追问），"
    "切勿把整句话、语气词或叙述当引用。\n"
    "say（仅 tool=none）**只谈法务案件业务**：友好说明能做什么并引导回案件，"
    "绝不透露任何非业务内部信息。\n"
    + CONFIDENTIALITY_RULES
)


def route_llm(text: str, client, *, context: str = "") -> Optional[Intent]:
    """规则未命中时的 LLM 兜底：单工具 JSON 决策 → Intent。

    失败即降级（返回 None → 调用方回引导卡）：
      client 为空 / 不可用 / 非 JSON / 工具名非法 → None
      tool=none 且给了 say → Intent("say", say)，由 Bot 直接回话
    """
    if client is None:
        return None
    try:
        if hasattr(client, "available") and not client.available():
            return None
    except Exception:  # noqa: BLE001
        return None
    raw = (text or "").strip()
    if not raw:
        return None
    user = f"最近对话（供理解指代）：\n{context.strip()}\n\n用户刚才说：{raw}" if context.strip() else raw
    obj = client.chat_json([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])
    if not isinstance(obj, dict):
        return None
    tool = str(obj.get("tool") or "").strip().lower()
    if tool == "none":
        say = str(obj.get("say") or "").strip()
        return Intent("say", say) if say else None
    if tool not in _TOOL_NAMES:
        return None
    args = obj.get("args")
    if isinstance(args, (list, tuple)):
        args = " ".join(str(a) for a in args)
    args = str(args or "").strip()
    extra: dict = {}
    if tool == "discuss":
        extra["question"] = raw
    elif tool == "advise":
        args = raw                                  # 方法性问题：参数即用户原话
    elif tool == "list" and args:
        args = normalize_year(raw) or ""           # 只认年份，不认模型改写
    elif tool == "doc_more":
        args = ""                                  # 续看对象取会话记忆，无需参数
    elif not args and tool in ("web_search", "corpus", "law_lookup"):
        # 🔴 检索类问题模型常不给检索词（args 空）——用**用户原话**当检索串，
        # 否则检索会拿到空串，直接变成「处理失败」。
        args = raw
    if not args_provable(args, raw):
        # 🔴 参数无法在用户本轮原话中找到 → 判为臆造（实测会把历史案件名当成本轮引用）→ 清空
        args = ""
    return Intent(tool, args, extra)


# =============================================
# advise：业务方法性问题的 LLM 解答（比静态能力清单更「懂业务」）
# =============================================

# 本模块真实能力 + 「起草需要哪些材料」的领域知识——B 唯一真值，供提示词引用（勿臆造功能）
_BIZ_KNOWLEDGE = (
    "本模块（案小智）的真实能力：\n"
    "· 建案：把 PDF/DOCX/TXT/MD 材料发到会话即自动入库；或说「登记一个新案件」填表登记。\n"
    "· 提取（五维）：对已有案件的材料提炼事实认定 / 权利基础 / 侵权行为 / 抗辩事由 / 损失赔偿等维度。\n"
    "· 出文书：支持 答辩状 / 质证意见 / 当庭陈述 / 证据目录 四类，**须先有案件**（案件信息 + 提取物）。\n"
    "· 查与看：按年份 / 关键词检索案件、看详情、看提取物；统计总览。\n"
    "起草一份文书通常需要：\n"
    "① 案件基础信息——案号、原告、被告、案由、涉案场景、双方授权状态；\n"
    "② 案件材料——起诉状 / 证据清单 / 对方证据 / 判决或裁定等（PDF/DOCX 发到会话即可录入）；\n"
    "③ 按文书类型的补充材料——答辩状：起诉状副本 + 证据材料；质证意见：对方证据清单与证据材料；"
    "当庭陈述：案件经过与争议焦点；证据目录：本方证据材料。\n"
    "标准流程：发材料建案 → 说「提取一下」→ 说「起草 ＜案件＞ 的答辩状」。"
)

ADVISE_SYSTEM_PROMPT = (
    "你是法务案例智能助手「案小智」。用户提出了一个**业务方法性**问题"
    "（要做什么 / 需要准备哪些材料 / 流程步骤等）。\n"
    "请**直接、具体**地回答：给出可执行的步骤或清单，而不是罗列功能名字。\n"
    "回答必须严格贴合下列本模块真实能力，**不要臆造**未提供的功能：\n"
    + _BIZ_KNOWLEDGE + "\n"
    "要求：中文；简明分点；不超过 12 行；不复述用户原话；只谈与「案件 / 案卷 / 提取物 / 文书 / 统计」"
    "相关的业务；不提系统 / 技术 / 配置 / 内部实现细节。\n"
    "若问题与法务案件业务无关，礼貌说明你能做什么并引导回案件。\n"
    + CONFIDENTIALITY_RULES
)


def advise_llm(question: str, client, *, context: str = "") -> Optional[str]:
    """业务方法性问题的 LLM 解答；client 为空 / 不可用 / 失败 → None（调用方降级静态指南卡）。"""
    if client is None:
        return None
    try:
        if hasattr(client, "available") and not client.available():
            return None
    except Exception:  # noqa: BLE001
        return None
    q = (question or "").strip()
    if not q:
        return None
    user = f"最近对话（供理解指代）：\n{context.strip()}\n\n用户问题：{q}" if context.strip() else q
    return client.chat([
        {"role": "system", "content": ADVISE_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])


# =============================================
# discuss：就某个具体案件做开放式分析 / 讨论（证据约束）
# =============================================

# 🔴 事实只来自 case_service.case_bundle 喂进来的材料——LLM 只做推理与表达
DISCUSS_SYSTEM_PROMPT = (
    "你是法务案例智能助手「案小智」。用户就**下面这个案件**向你提问或想与你讨论。\n"
    "🔴 事实约束：当事人、案号、金额、日期、证据、法院、结果等**只能来自「案件材料」**，"
    "不得编造，也不得按常识补全；材料里没有的，明确写「现有材料未涉及」。\n"
    "可以做的分析：梳理争议焦点、比较双方主张的强弱、指出证据薄弱环节与风险、"
    "给出应对思路或方案要点（均标注为**基于现有材料的初步判断**，提醒以核实原件为准）。\n"
    "涉及**外部**法律知识（具体法条、司法解释、赔偿标准、裁判规则）而材料未提供时，"
    "说明需要另行查法规核对，**不要凭记忆写条文原文或条号**。\n"
    "格式：中文；分点 3-6 条；简明，不超过 15 行；不复述用户原话；不谈系统 / 技术 / 内部实现。\n"
    "若问题与案件业务无关，礼貌说明你能做什么并引导回案件。\n"
    + CONFIDENTIALITY_RULES
)


def discuss_llm(question: str, bundle_text: str, client, *, context: str = "") -> Optional[str]:
    """案件分析 / 讨论的 LLM 作答；client 空 / 不可用 / 空材料 → None（调用方降级提示卡）。"""
    if client is None:
        return None
    try:
        if hasattr(client, "available") and not client.available():
            return None
    except Exception:  # noqa: BLE001
        return None
    q = (question or "").strip()
    materials = (bundle_text or "").strip()
    if not q or not materials:
        return None
    user = f"案件材料：\n{materials}\n\n"
    if context.strip():
        user += f"最近对话（供理解指代）：\n{context.strip()}\n\n"
    user += f"用户问题：{q}"
    return client.chat([
        {"role": "system", "content": DISCUSS_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])


# =============================================
# corpus：基于本地案例库的经验问答（有据作答）
# =============================================

# 🔴 事实只来自本地案例库检索出的证据（案件字段 + 提取物片段 + 金额统计）
CORPUS_SYSTEM_PROMPT = (
    "你是法务案例智能助手「案小智」。用户问的是**本地案例库里同类案件的经验**"
    "（一般判多少 / 同类怎么判 / 赔偿标准 / 常见裁判尺度等）。\n"
    "🔴 事实约束：金额、结论、当事人、案号、法院等**只能来自下面给出的「本地证据」**，"
    "不得编造，也不得按常识或记忆补全；证据里没有的，明确写「本地案例库中未见相关记载」。\n"
    "· 需要给区间 / 中位数的，直接引用证据里的金额统计；样本少的要说明「样本仅 N 例」。\n"
    "· 引用具体案件时用证据里的编号（如 [1]、[2]），让用户能回查。\n"
    "· 可以给**实务提示**（例如证据强弱对结果的影响），但须标注为基于库内样本的观察，"
    "提醒以个案核实与现行规定为准。\n"
    "· 涉及**具体法条、司法解释原文**而证据未提供时，说明需另行查法规，"
    "**不要凭记忆写条文原文或条号**。\n"
    "格式：中文；分点 3-6 条；简明，不超过 15 行；不复述用户原话；不谈系统 / 技术 / 内部实现。\n"
    "若问题与案件业务无关，礼貌说明你能做什么并引导回案件。\n"
    + CONFIDENTIALITY_RULES
)


def corpus_llm(question: str, evidence_text: str, client, *, context: str = "") -> Optional[str]:
    """基于本地案例库证据的 LLM 作答；client 空 / 不可用 / 无证据 → None（调用方降级）。"""
    if client is None:
        return None
    try:
        if hasattr(client, "available") and not client.available():
            return None
    except Exception:  # noqa: BLE001
        return None
    q = (question or "").strip()
    evidence = (evidence_text or "").strip()
    if not q or not evidence:
        return None
    user = f"本地证据：\n{evidence}\n\n"
    if context.strip():
        user += f"最近对话（供理解指代）：\n{context.strip()}\n\n"
    user += f"用户问题：{q}"
    return client.chat([
        {"role": "system", "content": CORPUS_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])


# =============================================
# insight：提取完成后的主动摘要（要点 / 风险 / 建议补充；证据约束）
# =============================================

INSIGHT_SYSTEM_PROMPT = (
    "你是法务案例智能助手「案小智」。下面是一个刚完成五维提取的案件材料，"
    "请给用户一段**主动摘要**，严格基于给定材料：\n"
    "① **案件要点**：1-3 条最关键的事实与争议焦点；\n"
    "② **风险提示**：1-3 条证据薄弱 / 主张难获支持之处；\n"
    "③ **建议补充**：1-3 条还需补的证据或信息。\n"
    "🔴 事实只能来自材料，不得编造；材料未涉及的写「材料未涉及」，不要臆测。\n"
    "中文；三段小标题；总计不超过 12 行；不谈系统 / 技术 / 内部实现。\n"
    + CONFIDENTIALITY_RULES
)


def insight_llm(insight: dict, bundle_text: str, client) -> Optional[str]:
    """案件要点 LLM 摘要；client 空 / 不可用 / 无材料 → None（调用方回规则摘要）。"""
    if client is None:
        return None
    try:
        if hasattr(client, "available") and not client.available():
            return None
    except Exception:  # noqa: BLE001
        return None
    materials = (bundle_text or "").strip()
    if not materials:
        return None
    name = str((insight or {}).get("case_name") or "").strip()
    user = f"案件：{name or '（未命名）'}\n\n案件材料：\n{materials}\n\n请给出要点 / 风险 / 建议补充。"
    return client.chat([
        {"role": "system", "content": INSIGHT_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])


# =============================================
# 待处理附件的处置指令分类（LLM 兜底，规则判不出时用）
# =============================================

ATTACHMENT_ROUTING_PROMPT = (
    "用户在会话里上传了案件材料（附件），但还没确认怎么处理。现在用户回了一句话。\n"
    "请判断这句话**想让这些附件怎么处理**，只输出 JSON：\n"
    '{"action": "new_case|merge|cancel|other", "ref": "＜并入时填案件名或案号，否则留空＞"}\n'
    "· new_case：把附件作为**新材料建立新案件**并分析——「新建 / 录入 / 登记 / 立案 / 归档 / 入库」"
    "「分析一下这份材料」「提取这份材料」等；只要意图是让这些材料进入系统被分析，就选 new_case。\n"
    "· merge：把附件**补充进某个已有案件**（「并入腾讯案」「补充到××案」）——ref 填案件名/案号。\n"
    "· cancel：暂不处理（「先放着」「不用了」「忽略」）。\n"
    "· other：用户没在说这份材料怎么办（在问别的事 / 查别的案件 / 闲聊）。\n"
    "拿不准时，若用户提到材料 / 文件 / 分析 / 录入，倾向 new_case。\n"
    "只输出 JSON，不要解释、不要代码围栏。"
)

_ATT_ACTION_MAP = {"new_case": "new", "merge": "merge", "cancel": "cancel", "other": "other"}


def classify_attachment(text: str, client, *, context: str = "") -> tuple:
    """待处理附件的处置意图分类（LLM 兜底）→ (act, ref)。

    act ∈ {"new","merge","cancel","other"}；client 不可用 / 失败 / 非法 → ("", "")。
    """
    if client is None:
        return "", ""
    try:
        if hasattr(client, "available") and not client.available():
            return "", ""
    except Exception:  # noqa: BLE001
        return "", ""
    raw = (text or "").strip()
    if not raw:
        return "", ""
    user = f"最近对话（供理解指代）：\n{context.strip()}\n\n用户刚才说：{raw}" if context.strip() else raw
    obj = client.chat_json([
        {"role": "system", "content": ATTACHMENT_ROUTING_PROMPT},
        {"role": "user", "content": user},
    ])
    if not isinstance(obj, dict):
        return "", ""
    act = str(obj.get("action") or "").strip().lower()
    if act not in _ATT_ACTION_MAP:
        return "", ""
    ref = str(obj.get("ref") or "").strip()
    return _ATT_ACTION_MAP[act], ref


__all__ = ["Intent", "DOC_TYPES", "TOOL_SPECS", "SYSTEM_PROMPT",
           "ADVISE_SYSTEM_PROMPT", "DISCUSS_SYSTEM_PROMPT", "INSIGHT_SYSTEM_PROMPT",
           "CORPUS_SYSTEM_PROMPT",
           "route", "route_llm", "advise_llm", "discuss_llm", "insight_llm", "corpus_llm",
           "is_law_topic",
           "ATTACHMENT_ROUTING_PROMPT", "classify_attachment", "normalize_year", "parse_ordinal",
           "args_provable", "_extract_case_number"]
# =============================================
# extractor.py - AI 提取器
# 调用 LLM 按 D1-D5 维度提取结构化信息
# =============================================
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .parser import ParsedContent

logger = logging.getLogger(__name__)


@dataclass
class Party:
    """当事人"""
    name: str
    role: str  # 原告/被告/第三人
    company: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None  # 脱敏存储
    auth_level: Optional[str] = None  # 授权层级


@dataclass
class KeyFact:
    """关键事实"""
    description: str
    source: str  # 来源文件
    status: str = "已证"  # 已证/待核/推论


@dataclass
class LegalBasis:
    """法律依据"""
    law_name: str
    article: str  # 条款
    content: str
    applicability: str  # 适用说明


@dataclass
class DefenseArgument:
    """抗辩论点"""
    rank: int
    argument_type: str
    content: str
    evidence: str
    priority: str  # 主力/辅助/备用


@dataclass
class Evidence:
    """证据"""
    seq: int
    name: str
    purpose: str  # 证明目的
    evidence_type: str  # 原件/复印件/电子数据
    status: str  # 有效/存疑


@dataclass
class DamageClaim:
    """赔偿主张"""
    claim_type: str  # 实际损失/违法所得/许可费/法定赔偿
    plaintiff_amount: str
    defendant_argument: str
    reasonable_range: str


@dataclass
class DFacts:
    """D1: 事实认定"""
    background: str
    dispute_points: list[str]
    key_facts: list[KeyFact]
    rights_basis: str
    behavior: str  # 行为定性


@dataclass
class DLegal:
    """D2: 法律依据"""
    laws: list[LegalBasis]
    legal_relationship: str  # 法律关系定性
    rights_analysis: str
    defense_feasibility: str  # 抗辩法律可行性


@dataclass
class DStrategy:
    """D3: 攻防策略"""
    plaintiff_claims: str
    defenses: list[DefenseArgument]
    argument_chain: str  # 抗辩论证结构
    main_battlefield: str  # 主战场决策


@dataclass
class DEvidence:
    """D4: 证据体系"""
    plaintiff_evidence: list[Evidence]
    defendant_evidence: list[Evidence]
    cross_exam_points: str  # 质证要点
    burden_of_proof: str  # 举证责任分配


@dataclass
class DDamages:
    """D5: 赔偿裁量"""
    total_claim: str
    defense_arguments: str
    calculation: list[DamageClaim]
    factors: str  # 裁量因素
    estimate: str  # 预估结论


@dataclass
class ExtractedCase:
    """AI 提取的结构化案件信息"""
    # 基本信息
    case_number: Optional[str] = None
    case_name: str = ""
    court: Optional[str] = None
    cause: str = ""
    filing_date: Optional[str] = None
    result: str = ""
    scene: str = ""
    year: Optional[int] = None
    quality: str = ""
    defendant_auth_status: str = ""
    
    # 当事人
    plaintiffs: list[Party] = field(default_factory=list)
    defendants: list[Party] = field(default_factory=list)
    
    # D1-D5 维度
    d1_facts: Optional[DFacts] = None
    d2_legal: Optional[DLegal] = None
    d3_strategy: Optional[DStrategy] = None
    d4_evidence: Optional[DEvidence] = None
    d5_damages: Optional[DDamages] = None
    
    # 元数据
    source_files: list[str] = field(default_factory=list)
    confidence: float = 0.0
    extracted_at: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        def _serialize(obj):
            if hasattr(obj, "__dataclass_fields__"):
                result = {}
                for name, field in obj.__dataclass_fields__.items():
                    value = getattr(obj, name)
                    result[name] = _serialize(value) if value else None
                return result
            elif isinstance(obj, list):
                return [_serialize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            else:
                return obj
        
        return _serialize(self)

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"# {self.case_name}",
            "",
            f"**案号**: {self.case_number or '待补充'}",
            f"**法院**: {self.court or '待补充'}",
            f"**案由**: {self.cause}",
            f"**提取时间**: {self.extracted_at}",
            "",
            "---",
            "",
            "## 当事人",
            "",
        ]
        
        # 原告
        if self.plaintiffs:
            lines.append("### 原告")
            lines.append("| 序号 | 名称 | 公司 | 授权层级 |")
            lines.append("|------|------|------|---------|")
            for i, p in enumerate(self.plaintiffs, 1):
                lines.append(f"| {i} | {p.name} | {p.company or '-'} | {p.auth_level or '-'} |")
            lines.append("")
        
        # 被告
        if self.defendants:
            lines.append("### 被告")
            lines.append("| 序号 | 名称 | 公司 |")
            lines.append("|------|------|------|")
            for i, p in enumerate(self.defendants, 1):
                lines.append(f"| {i} | {p.name} | {p.company or '-'} |")
            lines.append("")
        
        # D1-D5
        if self.d1_facts:
            lines.append("---")
            lines.append("")
            lines.append("## D1: 事实认定")
            lines.append("")
            lines.append(f"**背景**: {self.d1_facts.background}")
            lines.append("")
            lines.append("**争议焦点**:")
            for i, point in enumerate(self.d1_facts.dispute_points, 1):
                lines.append(f"{i}. {point}")
            lines.append("")
            lines.append("**关键事实**:")
            lines.append("| # | 事实描述 | 来源 | 状态 |")
            lines.append("|---|---------|------|------|")
            for i, fact in enumerate(self.d1_facts.key_facts, 1):
                lines.append(f"| {i} | {fact.description} | {fact.source} | {fact.status} |")
        
        if self.d2_legal:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## D2: 法律依据")
            lines.append("")
            lines.append("| 法律 | 条款 | 内容 | 适用 |")
            lines.append("|------|------|------|------|")
            for law in self.d2_legal.laws:
                lines.append(f"| {law.law_name} | {law.article} | {law.content[:50]}... | {law.applicability} |")
        
        if self.d3_strategy:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## D3: 攻防策略")
            lines.append("")
            lines.append(f"**原告诉请**: {self.d3_strategy.plaintiff_claims}")
            lines.append("")
            lines.append("**抗辩排序**:")
            lines.append("| 排序 | 类型 | 内容 | 优先级 |")
            lines.append("|------|------|------|--------|")
            for d in self.d3_strategy.defenses:
                lines.append(f"| {d.rank} | {d.argument_type} | {d.content[:50]}... | {d.priority} |")
        
        if self.d4_evidence:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## D4: 证据体系")
            lines.append("")
            lines.append(f"**举证责任**: {self.d4_evidence.burden_of_proof}")
        
        if self.d5_damages:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## D5: 赔偿裁量")
            lines.append("")
            lines.append(f"**总诉求**: {self.d5_damages.total_claim}")
            lines.append(f"**预估区间**: {self.d5_damages.estimate}")
        
        return "\n".join(lines)


# =============================================
# 提取提示词（MiniMax / Ollama 共用，唯一真值）
# 字段集对齐 prompts/提取/1_新案材料提取_D1-D5.md（含 result/scene/year）
# =============================================

EXTRACTION_JSON_TEMPLATE = """{{
  "case_number": "案号（如 (2024)京0491民初7776号）",
  "case_name": "案件名称",
  "court": "受理法院全称",
  "cause": "案由",
  "result": "案件结果（判决/调解/撤诉/驳回），未知留空",
  "scene": "涉案场景（实体KTV/车载KTV/线上平台/实体场所/线上应用/混合场景/其他），未知留空",
  "year": 2024,
  "defendant_auth_status": "被告授权状态（已获音集协+音著协双授权/已获音集协授权/已获音著协授权/部分授权/未获授权/待核实）",
  "plaintiffs": [{{"name": "原告名称", "role": "原告", "company": "所属公司", "auth_level": "授权层级（原始权利人/独家被授权方/间接授权(2级)/间接授权(3级+)/集体管理组织/待核实）"}}],
  "defendants": [{{"name": "被告名称", "role": "被告", "company": "所属公司"}}],
  "d1_facts": {{
    "background": "案件背景（起因/经过/时间线）",
    "dispute_points": ["争议焦点1", "争议焦点2"],
    "key_facts": [{{"description": "事实描述", "source": "来源文件或段落", "status": "已证/待核/推论"}}],
    "rights_basis": "1.5 权利基础分析（权属链是否完整）",
    "behavior": "1.6 行为定性（行为内容/是否落入权利范围）"
  }},
  "d2_legal": {{
    "laws": [{{"law_name": "法律名称", "article": "条款号", "content": "条款内容", "applicability": "适用说明"}}],
    "legal_relationship": "2.2 法律关系定性",
    "rights_analysis": "2.3 权利基础分析",
    "defense_feasibility": "2.4 被告抗辩的法律可行性"
  }},
  "d3_strategy": {{
    "plaintiff_claims": "3.1 原告诉请",
    "defenses": [{{"rank": 1, "argument_type": "抗辩类型", "content": "抗辩内容", "evidence": "证据支撑", "priority": "主力/辅助/备用"}}],
    "argument_chain": "3.3 抗辩论证结构（论点→事实→法条→结论）",
    "main_battlefield": "3.4 主战场决策"
  }},
  "d4_evidence": {{
    "plaintiff_evidence": [{{"seq": 1, "name": "证据名称", "purpose": "证明目的", "evidence_type": "原件/复印件/电子数据", "status": "有效/存疑"}}],
    "defendant_evidence": [{{"seq": 1, "name": "证据名称", "purpose": "证明目的", "evidence_type": "原件/复印件/电子数据", "status": "有效/存疑"}}],
    "cross_exam_points": "4.3 证据质证要点（四性：真实/合法/关联/证明力）",
    "burden_of_proof": "4.4 举证责任分配"
  }},
  "d5_damages": {{
    "total_claim": "5.1 赔偿请求（金额+依据）",
    "defense_arguments": "5.2 被告对赔偿数额的抗辩",
    "calculation": [{{"claim_type": "实际损失/违法所得/许可费倍数/法定赔偿", "plaintiff_amount": "原告主张", "defendant_argument": "被告抗辩", "reasonable_range": "合理区间"}}],
    "factors": "5.4 裁量因素（传播范围/持续时间/获利/过错程度）",
    "estimate": "5.5 预估结论（预计支持的赔偿区间）"
  }}
}}"""


def build_extraction_prompt(case_name: str, text: str, max_chars: int = 15000) -> str:
    """构建提取 prompt（全字段集，MiniMax/Ollama 共用，避免各自精简导致空壳）。"""
    return f"""你是一位资深民商法律师，擅长从案件材料中提取结构化的法律分析要素。
你必须严格遵循"5 维度提取法"，覆盖 D1-D5 全部维度，不可遗漏。

案件名称: {case_name}

材料内容:
{text[:max_chars]}

请严格按以下 JSON 结构输出（字段名不可改；无信息时该字段留空字符串 ""，不得整段省略）：
{EXTRACTION_JSON_TEMPLATE}

强制要求：
1. 5 个维度全部覆盖；叙述型字段（rights_basis/behavior/rights_analysis/defense_feasibility/argument_chain/main_battlefield/cross_exam_points/burden_of_proof/factors/estimate）必须写完整句子，禁止留空
2. 表格类字段（key_facts/laws/defenses/原告与被告证据/calculation）必须有数据行，禁止只有表头
3. 关键论点必须有原文支撑；事实与推论分离（标注 status）
4. 只返回纯 JSON，不含 markdown 代码块或额外说明
"""


def _coerce_year(value) -> Optional[int]:
    """宽松把 year 字段转 int（容忍 '2024' / '2024年' / 2024）。"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group(0)) if m else None


def _party_list(items, default_role: str) -> list[Party]:
    """把 LLM 返回的当事人列表稳健转成 Party（容忍缺失/多余字段）。"""
    out = []
    for p in items or []:
        if not isinstance(p, dict):
            continue
        out.append(Party(
            name=str(p.get("name", "") or ""),
            role=str(p.get("role") or default_role),
            company=p.get("company"),
            id_type=p.get("id_type"),
            id_number=p.get("id_number"),
            auth_level=p.get("auth_level"),
        ))
    return out


def _apply_case_scalars(case: ExtractedCase, data: dict) -> ExtractedCase:
    """把基本信息字段写入 ExtractedCase（含 result/scene/year/auth）。"""
    case.case_number = data.get("case_number") or case.case_number
    case.case_name = data.get("case_name") or case.case_name
    case.court = data.get("court") or case.court
    case.cause = data.get("cause") or case.cause
    case.filing_date = data.get("filing_date") or case.filing_date
    case.result = str(data.get("result") or "")
    case.scene = str(data.get("scene") or "")
    case.defendant_auth_status = str(data.get("defendant_auth_status") or "")
    case.year = _coerce_year(data.get("year")) or case.year
    return case


def _apply_dims(case: ExtractedCase, data: dict) -> ExtractedCase:
    """解析 D1-D5 五个维度（MiniMax/Ollama 共用）。"""
    if "d1_facts" in data and data["d1_facts"]:
        d1 = data["d1_facts"]
        case.d1_facts = DFacts(
            background=d1.get("background", ""),
            dispute_points=d1.get("dispute_points", []),
            key_facts=[KeyFact(
                description=kf.get("description", ""),
                source=kf.get("source", ""),
                status=kf.get("status", "已证"),
            ) for kf in d1.get("key_facts", []) if isinstance(kf, dict)],
            rights_basis=d1.get("rights_basis", ""),
            behavior=d1.get("behavior", ""),
        )
    if "d2_legal" in data and data["d2_legal"]:
        d2 = data["d2_legal"]
        case.d2_legal = DLegal(
            laws=[LegalBasis(
                law_name=lb.get("law_name", ""),
                article=lb.get("article", ""),
                content=lb.get("content", ""),
                applicability=lb.get("applicability", ""),
            ) for lb in d2.get("laws", []) if isinstance(lb, dict)],
            legal_relationship=d2.get("legal_relationship", ""),
            rights_analysis=d2.get("rights_analysis", ""),
            defense_feasibility=d2.get("defense_feasibility", ""),
        )
    if "d3_strategy" in data and data["d3_strategy"]:
        d3 = data["d3_strategy"]
        case.d3_strategy = DStrategy(
            plaintiff_claims=d3.get("plaintiff_claims", ""),
            defenses=[DefenseArgument(
                rank=da.get("rank", 0),
                argument_type=da.get("argument_type", ""),
                content=da.get("content", ""),
                evidence=da.get("evidence", ""),
                priority=da.get("priority", "辅助"),
            ) for da in d3.get("defenses", []) if isinstance(da, dict)],
            argument_chain=d3.get("argument_chain", ""),
            main_battlefield=d3.get("main_battlefield", ""),
        )
    if "d4_evidence" in data and data["d4_evidence"]:
        d4 = data["d4_evidence"]
        def _ev(items):
            return [Evidence(
                seq=e.get("seq", 0),
                name=e.get("name", ""),
                purpose=e.get("purpose", ""),
                evidence_type=e.get("evidence_type", "原件"),
                status=e.get("status", "有效"),
            ) for e in items or [] if isinstance(e, dict)]
        case.d4_evidence = DEvidence(
            plaintiff_evidence=_ev(d4.get("plaintiff_evidence")),
            defendant_evidence=_ev(d4.get("defendant_evidence")),
            cross_exam_points=d4.get("cross_exam_points", ""),
            burden_of_proof=d4.get("burden_of_proof", ""),
        )
    if "d5_damages" in data and data["d5_damages"]:
        d5 = data["d5_damages"]
        case.d5_damages = DDamages(
            total_claim=d5.get("total_claim", ""),
            defense_arguments=d5.get("defense_arguments", ""),
            calculation=[DamageClaim(
                claim_type=dc.get("claim_type", ""),
                plaintiff_amount=dc.get("plaintiff_amount", ""),
                defendant_argument=dc.get("defendant_argument", ""),
                reasonable_range=dc.get("reasonable_range", ""),
            ) for dc in d5.get("calculation", []) if isinstance(dc, dict)],
            factors=d5.get("factors", ""),
            estimate=d5.get("estimate", ""),
        )
    return case


def _strip_json_fence(text: str) -> str:
    """从 LLM 文本中抽出 JSON 主体：去 ``` 围栏 → 截取首个 `{` 到末个 `}`。

    LLM 常在 JSON 前后夹带说明文字（或用 ```json 围栏包裹），直接 json.loads
    会失败；这里做容错抽取，尽量拿到真正的 JSON 对象。
    """
    t = (text or "").strip()
    if "```" in t:
        parts = t.split("```")
        inner = parts[1] if len(parts) >= 3 else (parts[-1] if len(parts) == 2 else t)
        inner = inner.strip()
        if inner[:4].lower() == "json":
            inner = inner[4:]
        t = inner.strip()
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        t = t[i:j + 1]
    return t.strip()


def _dim_substantive(dim) -> bool:
    """维度是否含实质内容（任一字符串字段非空，或任一列表字段有元素）。"""
    if dim is None:
        return False
    for name in getattr(dim, "__dataclass_fields__", {}):
        value = getattr(dim, name)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and any(value):
            return True
    return False


def dim_flags(case) -> dict:
    """五维是否有实质内容 → {"D1".."D5": bool}（按实质判断，非简单 bool()）。"""
    return {
        "D1": _dim_substantive(getattr(case, "d1_facts", None)),
        "D2": _dim_substantive(getattr(case, "d2_legal", None)),
        "D3": _dim_substantive(getattr(case, "d3_strategy", None)),
        "D4": _dim_substantive(getattr(case, "d4_evidence", None)),
        "D5": _dim_substantive(getattr(case, "d5_damages", None)),
    }


def extraction_is_empty(case) -> bool:
    """提取结果是否为空壳：五维全无实质内容且无案号（用于拦截「0 提取物」的空案件）。"""
    return not (getattr(case, "case_number", "") or "").strip() and not any(dim_flags(case).values())


def derive_quality(case: "ExtractedCase") -> str:
    """按 D1-D5 完整度 + 基本信息评质量等级 A/B/C（AI 与规则引擎共用唯一真值）。

    A：5 个维度均有实质内容（LLM 全维提取）
    B：≥3 个维度有内容，或案号已识别（基本身份可定）
    C：其余
    """
    dims = (case.d1_facts, case.d2_legal, case.d3_strategy, case.d4_evidence, case.d5_damages)
    filled = sum(1 for d in dims if _dim_substantive(d))
    if filled >= 5:
        return "A"
    if filled >= 3 or case.case_number:
        return "B"
    return "C"


def _parse_llm_json(text: str, contents: list, confidence: float) -> ExtractedCase:
    """把 LLM 返回的 JSON 文本解析为 ExtractedCase（MiniMax/Ollama/OpenAI 共用）。"""
    from datetime import datetime, timezone

    raw = _strip_json_fence(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        if os.environ.get("LARK_DEBUG_LLM") == "1":
            logger.warning("提取响应无法解析为 JSON（长度=%d）：%s", len(text or ""), (text or "")[:300])
        else:
            logger.warning(
                "提取响应无法解析为 JSON（长度=%d，含花括号=%s）", len(text or ""), "{" in (text or "")
            )
        raise ExtractionError("AI 未返回可解析的五维 JSON（模型响应格式异常）")

    case = ExtractedCase(
        source_files=[c.file_info.path.name for c in contents],
        confidence=confidence,
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )
    _apply_case_scalars(case, data)
    case.plaintiffs = _party_list(data.get("plaintiffs"), "原告")
    case.defendants = _party_list(data.get("defendants"), "被告")
    _apply_dims(case, data)
    case.quality = derive_quality(case)
    return case


# =============================================
# AI 引擎接口
# =============================================

# 支持引擎（单一真值：UI 下拉 ENGINE_OPTIONS / CLI --engine choices 均引用此表）
SUPPORTED_ENGINES = ("minimax", "ollama", "openai", "mock", "basic")


class AIEngine(ABC):
    """AI 引擎基类"""
    
    @abstractmethod
    def extract(self, contents: list[ParsedContent], case_name: str) -> ExtractedCase:
        """提取案件信息"""
        pass


class MiniMaxAdapter(AIEngine):
    """MiniMax 引擎适配器（使用 ai_engine.py）"""

    # 🔴 结构化提取用**非推理模型**：推理模型（MiniMax-M3.1-Flash）会把 max_tokens
    # 全部耗在 reasoning_content 上，正文为空 → 「AI 未返回可解析的五维 JSON」。
    # 实测：Text-01 → 合法 JSON（66s）；M3.1-Flash@8192 → 正文空（finish_reason=length）。
    EXTRACT_MODEL = os.environ.get("MINIMAX_EXTRACT_MODEL", "MiniMax-Text-01")
    REASONING_MODEL = os.environ.get("MINIMAX_REASONING_MODEL", "MiniMax-M3.1-Flash")
    REASONING_MAX_TOKENS = int(os.environ.get("MINIMAX_REASONING_MAX_TOKENS", "32768"))

    def __init__(self, engine_manager):
        self.manager = engine_manager

    def extract(self, contents: list[ParsedContent], case_name: str) -> ExtractedCase:
        """调用 MiniMax 提取案件信息"""
        from .langchain_llm import get_llm_service

        llm = get_llm_service()
        if not llm.is_available():
            # 降级到 BasicEngine
            return BasicEngine().extract(contents, case_name)

        # 合并文本
        combined_text = "\n\n".join(
            f"=== {c.file_info.name} ===\n{c.text[:5000]}"
            for c in contents
        )

        # 构建 prompt
        prompt = self._build_prompt(combined_text, case_name)

        sys_prompt = "你是一位专业的法律案件分析专家，擅长从案件材料中提取结构化的案件信息。"
        only_json = "\n\n重要：请**只输出 JSON 对象本身**，不要任何解释文字、不要 Markdown 代码围栏。"
        response = llm.generate_document(prompt=prompt, system_prompt=sys_prompt,
                                         model=self.EXTRACT_MODEL)
        try:
            return self._parse_response(response, contents)
        except ExtractionError:
            # 一次修复重试：模型输出夹带解释文字 / 围栏 → 明确要求「只输出 JSON」
            logger.info("提取响应非合法 JSON，执行一次修复重试")
            retry = llm.generate_document(prompt=prompt + only_json, system_prompt=sys_prompt,
                                          model=self.EXTRACT_MODEL)
            try:
                return self._parse_response(retry, contents)
            except ExtractionError:
                # 最后兜底：换推理模型（额度给足）——推理模型可能给出更完整的五维
                logger.info("非推理模型两次未产出合法 JSON，改用推理模型兜底")
                last = llm.generate_document(
                    prompt=prompt + only_json, system_prompt=sys_prompt,
                    model=self.REASONING_MODEL, max_tokens=self.REASONING_MAX_TOKENS,
                )
                return self._parse_response(last, contents)
    
    def _build_prompt(self, text: str, case_name: str) -> str:
        """构建提取 prompt（与 Ollama 共用完整字段集，避免精简导致空壳）"""
        return build_extraction_prompt(case_name, text, max_chars=8000)

    def _parse_response(self, response: str, contents: list) -> ExtractedCase:
        """解析 LLM 响应（与 Ollama/OpenAI 共用字段解析）。

        解析失败**如实抛出**（不再静默返回空案件）——否则会建出「0 提取物」的空壳案件
        并回成功卡，让用户误以为分析完成。
        """
        return _parse_llm_json(response, contents, 0.7)


class OpenAIAdapter(AIEngine):
    """OpenAI 引擎适配器（无 key / 不可用时降级 BasicEngine）"""

    def __init__(self, engine_manager):
        self.manager = engine_manager

    def extract(self, contents: list[ParsedContent], case_name: str) -> ExtractedCase:
        """调用 OpenAI 提取案件信息"""
        engine = self.manager.get_engine("openai")
        if engine is None:
            return BasicEngine().extract(contents, case_name)

        combined_text = "\n\n".join(
            f"=== {c.file_info.name} ===\n{c.text[:5000]}"
            for c in contents
        )
        prompt = build_extraction_prompt(case_name, combined_text, max_chars=8000)
        try:
            response = engine.chat([{"role": "user", "content": prompt}])
            return _parse_llm_json(response, contents, 0.7)
        except Exception:
            return BasicEngine().extract(contents, case_name)


class OllamaEngine:
    """Ollama 本地引擎"""
    
    def __init__(self, model: str = "qwen2.5", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
    
    def extract(self, contents: list[ParsedContent], case_name: str) -> ExtractedCase:
        """调用 Ollama 提取"""
        import requests
        
        # 合并文本
        combined_text = "\n\n".join(
            f"=== {c.file_info.name} ===\n{c.text[:5000]}"
            for c in contents
        )
        
        # 构建 prompt
        prompt = self._build_prompt(combined_text, case_name)
        
        # 调用 API
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("response", "")
            
            # 解析 JSON
            return self._parse_response(text, contents)
        except Exception as e:
            raise ExtractionError(f"Ollama 调用失败: {e}") from e
    
    def _build_prompt(self, text: str, case_name: str) -> str:
        """构建提取 prompt（与 MiniMax 共用完整字段集）"""
        return build_extraction_prompt(case_name, text, max_chars=15000)

    def _parse_response(self, text: str, contents: list[ParsedContent]) -> ExtractedCase:
        """解析 AI 响应（与 MiniMax/OpenAI 共用字段解析）"""
        return _parse_llm_json(text, contents, 0.8)


class BasicEngine:
    """基于规则的提取引擎（无需 LLM）"""
    
    def extract(self, contents: list[ParsedContent], case_name: str) -> ExtractedCase:
        """从文件内容中提取结构化信息"""
        from datetime import datetime, timezone
        
        # 合并所有文本
        combined_text = "\n".join(c.text for c in contents if c.text)
        
        # 从目录名解析基本信息（优先）
        dir_info = self._parse_directory_name(case_name)
        
        # 提取基本信息
        # 案号优先从目录名获取，目录名更可靠
        case_number = dir_info.get("case_number") or self._extract_case_number(combined_text)
        plaintiffs, defendants = self._extract_parties(combined_text, dir_info)
        cause = dir_info.get("cause") or self._extract_cause(combined_text, case_name)
        court = dir_info.get("court") or self._extract_court(combined_text)
        result = self._extract_result(combined_text)
        year = dir_info.get("year") or _coerce_year(case_number)
        scene = self._extract_scene(case_name, combined_text)
        auth_status = self._extract_auth_status(combined_text)
        
        # 提取 D3 攻防策略（从答辩状中）
        defenses = self._extract_defenses(contents)
        
        # 提取证据（从质证意见中）
        evidence_points = self._extract_evidence_points(contents)
        
        case = ExtractedCase(
            case_number=case_number,
            case_name=dir_info.get("full_name", case_name),
            court=court,
            cause=cause,
            result=result or "",
            scene=scene,
            year=year,
            defendant_auth_status=auth_status,
            plaintiffs=plaintiffs,
            defendants=defendants,
            source_files=[c.file_info.path.name for c in contents],
            confidence=0.8 if dir_info.get("case_number") else 0.7,
            extracted_at=datetime.now(timezone.utc).isoformat(),
            d3_strategy=DStrategy(
                plaintiff_claims="从答辩状中提取",
                defenses=defenses,
                argument_chain="从答辩状中提取",
                main_battlefield="待分析",
            ),
            d4_evidence=DEvidence(
                plaintiff_evidence=[],
                defendant_evidence=[],
                cross_exam_points=evidence_points,
                burden_of_proof="待补充",
            ),
        )
        case.quality = derive_quality(case)
        return case

    def _extract_scene(self, case_name: str, text: str) -> str:
        """推断涉案场景（映射到 SCENE 词表；未知留空）。"""
        hay = f"{case_name} {text[:3000]}"
        rules = [
            ("车载KTV", ("车载", "车机", "汽车KTV")),
            ("线上平台", ("线上平台", "网站", "APP", "app", "小程序", "网络平台")),
            ("线上应用", ("线上应用", "在线", "云KTV")),
            ("实体KTV", ("KTV", "ktv", "歌房", "包厢")),
            ("实体场所", ("实体场所", "门店", "商场", "酒吧", "酒店")),
        ]
        for scene, keys in rules:
            if any(k in hay for k in keys):
                return scene
        return ""

    def _extract_auth_status(self, text: str) -> str:
        """从材料推断被告授权状态（未知返回空，不猜）。"""
        has_jy = "音集协" in text
        has_zx = "音著协" in text
        if has_jy and has_zx:
            return "已获音集协+音著协双授权"
        if has_jy:
            return "已获音集协授权"
        if has_zx:
            return "已获音著协授权"
        if "合法来源" in text or "授权" in text:
            return "部分授权"
        return ""
    
    def _parse_directory_name(self, case_name: str) -> dict:
        """从目录名解析案件信息
        
        目录名格式：{日期}-{案号}-{原告简称}诉{被告简称}-{案由}-{法院}-{负责人}
        示例：240507-2024京0491民初7776号-广州繁星诉雷石信息网络传播权纠纷-北互-HS
        """
        info = {
            "case_number": None,
            "plaintiff": None,
            "defendant": None,
            "cause": None,
            "court": None,
            "year": None,
            "full_name": case_name,
        }
        
        # 法院名称映射
        court_mapping = {
            "北互": "北京互联网法院",
            "北京互联网法院": "北京互联网法院",
            "北京市朝阳区人民法院": "北京市朝阳区人民法院",
            "朝阳法院": "北京市朝阳区人民法院",
            "朝阳": "北京市朝阳区人民法院",
            "北京知识产权法院": "北京知识产权法院",
            "北京知产法院": "北京知识产权法院",
            "上海浦东": "上海市浦东新区人民法院",
            "浦东新区法院": "上海市浦东新区人民法院",
            "上海浦东新区法院": "上海市浦东新区人民法院",
            "天津法院": "天津市相关法院",
            "天津和平区": "天津市和平区人民法院",
            "天津": "天津市相关法院",
            "广州互法院": "广州互联网法院",
            "广州互联网法院": "广州互联网法院",
            "广州白云区法院": "广州市白云区人民法院",
            "珠海法院": "珠海市相关法院",
            "深圳宝安区法院": "深圳市宝安区人民法院",
            "梅州法院": "梅州市相关法院",
            "四川": "四川省相关法院",
            "四川自由贸易试验区": "四川自由贸易试验区人民法院",
            "四川自贸区": "四川自由贸易试验区人民法院",
            "内蒙古赤峰红山区法院": "内蒙古自治区赤峰市红山区人民法院",
            "内蒙古": "内蒙古自治区相关法院",
            "山西忻州": "山西省忻州市中级人民法院",
            "山西": "山西省相关法院",
            "山东滕州": "山东省滕州市人民法院",
            "滕州": "山东省滕州市人民法院",
            "山东": "山东省相关法院",
            "广东高院": "广东省高级人民法院",
            "广州知产法院": "广州知识产权法院",
            "浙江广电": "浙江省相关法院",
            "盐城": "江苏省盐城市相关法院",
            "青岛": "山东省青岛市相关法院",
            "广西": "广西壮族自治区相关法院",
            "深圳龙岗区法院": "深圳市龙岗区人民法院",
            "梅州": "广东省梅州市相关法院",
            "梅州法院": "广东省梅州市相关法院",
            "四川": "四川省相关法院",
            "四川法院": "四川省相关法院",
        }
        
        # 案由关键词映射
        cause_mapping = {
            "信网权": "侵害作品信息网络传播权纠纷",
            "信息网络传播权": "侵害作品信息网络传播权纠纷",
            "著作权": "著作权纠纷",
            "著作权纠纷": "著作权纠纷",
            "著作权权属": "著作权权属纠纷",
            "放映权": "侵害作品放映权纠纷",
            "录音录像制作者权": "侵害录音录像制作者权纠纷",
            "肖像权": "肖像权纠纷",
            "不正当竞争": "不正当竞争纠纷",
            "劳动争议": "劳动争议",
            "合同纠纷": "合同纠纷",
            "执行异议": "执行异议之诉",
            "再审": "再审案件",
            "撤诉": "撤诉案件",
            "仲裁": "仲裁案件",
        }
        
        # 原告简称映射
        plaintiff_mapping = {
            "广州繁星": "广州繁星互娱信息科技有限公司",
            "繁星": "广州繁星互娱信息科技有限公司",
            "广州立峰": "广州市立峰音乐传播有限公司",
            "立峰": "广州市立峰音乐传播有限公司",
            "深圳启韵": "深圳启韵文化传媒有限公司",
            "启韵": "深圳启韵文化传媒有限公司",
            "北京潮石": "北京潮石音乐科技有限公司",
            "潮石": "北京潮石音乐科技有限公司",
            "纽凯": "纽凯文化传播（宜昌）有限公司",
            "纽凯文化": "纽凯文化传播（宜昌）有限公司",
            "腾讯": "腾讯音乐娱乐（珠海）有限公司",
            "腾讯音乐": "腾讯音乐娱乐（珠海）有限公司",
            "TME": "腾讯音乐娱乐（珠海）有限公司",
            "传世乐坊": "传世乐坊文化传媒（北京）有限责任公司",
            "四季唱片": "四季唱片有限公司",
            "广西唱作者": "广西唱作者文化传播有限公司",
            "祺峰": "祺峰（广州）文化传媒有限公司",
            "华声时代": "华声时代（北京）文化传播有限公司",
            "南京新航道": "南京新航道教育科技有限公司",
            "太阳红": "太阳红文化传媒有限公司",
            "浙江广电": "浙江广播电视集团",
            "广州宝生": "广州宝生音乐文化传播有限公司",
            "宝生": "广州宝生音乐文化传播有限公司",
            "启韵": "深圳启韵文化传媒有限公司",
            "雷石": "北京雷石天地电子技术有限公司",
            "雷客": "北京雷客天地科技有限公司",
        }
        
        # 被告简称映射
        defendant_mapping = {
            "雷石": "北京雷石天地电子技术有限公司",
            "雷客": "北京雷客天地科技有限公司",
            "特斯拉": "特斯拉汽车销售服务（北京）有限公司",
            "理想": "理想汽车销售服务有限公司",
            "埃安": "广汽埃安新能源汽车有限公司",
            "比亚迪": "比亚迪股份有限公司",
            "联通": "联通视频科技有限公司",
            "移动": "中国移动通信集团有限公司",
            "金麦客": "天津金麦客科技有限公司",
            "成都金麦客": "成都金麦客科技有限公司",
            "天津金麦客": "天津金麦客科技有限公司",
            "广州宝生": "广州宝生音乐文化传播有限公司",
            "镭海": "镭海（北京）信息技术有限公司",
            "毕滢": "毕滢（自然人）",
            "刘杰": "刘杰（自然人）",
            "崔天竺": "崔天竺（自然人）",
            "赵丹丹": "赵丹丹（自然人）",
            "张璟": "张璟（自然人）",
            "苗椿馀": "苗椿馀（自然人）",
            "王亮": "王亮（自然人）",
            "酷狗": "广州酷狗计算机科技有限公司",
        }
        
        try:
            # 尝试分割目录名
            parts = case_name.split("-")
            
            # 1. 提取日期（第一个部分，6位数字）
            date_part = None
            for i, part in enumerate(parts):
                if re.match(r"^\d{6,8}$", part.strip()):
                    date_part = part.strip()
                    break

            # 1.1 目录日期前缀 → 年份（240507 → 2024）
            if date_part:
                if len(date_part) == 8:
                    info["year"] = int(date_part[:4])
                elif len(date_part) == 6:
                    yy = int(date_part[:2])
                    info["year"] = 2000 + yy if yy <= 60 else 1900 + yy
            
            # 2. 提取案号（包含特定关键词的部分）
            # 优先从目录名提取，目录名格式：日期-案号-其他
            for part in parts:
                # 跳过纯日期部分
                if re.match(r"^\d{6,8}$", part.strip()):
                    continue
                # 跳过负责人缩写（通常是2-3个大写字母）
                if re.match(r"^[A-Z]{2,4}$", part.strip()):
                    continue
                # 匹配标准案号格式
                # 格式：(年份)省/市名+民终/民初+序号+号
                case_num_match = re.search(
                    r"[（\(]\d{4}[）\)]\S{1,10}\d{3,6}号",
                    part
                )
                if case_num_match:
                    info["case_number"] = case_num_match.group(0)
                    break
            
            # 3. 提取"诉"字前后的原告和被告
            for i, part in enumerate(parts):
                if "诉" in part:
                    # 分割原告和被告
                    sides = part.split("诉")
                    if len(sides) >= 1 and sides[0]:
                        plaintiff_short = sides[0].strip()
                        # 查找简称映射
                        for short, full in plaintiff_mapping.items():
                            if short in plaintiff_short:
                                info["plaintiff"] = full
                                break
                        if not info["plaintiff"]:
                            # 尝试使用第一个词作为简称
                            first_word = plaintiff_short.split("、")[0].strip()
                            if first_word:
                                info["plaintiff"] = plaintiff_mapping.get(first_word, first_word)
                    if len(sides) >= 2 and sides[1]:
                        defendant_short = sides[1].split("、")[0].split(",")[0].split("-")[0].strip()
                        # 查找简称映射
                        for short, full in defendant_mapping.items():
                            if short in defendant_short:
                                info["defendant"] = full
                                break
                        if not info["defendant"]:
                            info["defendant"] = defendant_mapping.get(defendant_short, defendant_short)
                    break
            
            # 3.1 如果没有找到原告/被告，尝试从非案号、非日期的部分提取
            if not info["plaintiff"] or not info["defendant"]:
                for part in parts:
                    # 跳过日期和案号部分
                    if re.match(r"^\d{6,8}$", part.strip()):
                        continue
                    if re.search(r"\d{4}.*民.*号", part):
                        continue
                    # 尝试匹配原告简称
                    for short, full in plaintiff_mapping.items():
                        if short in part and not info.get("plaintiff"):
                            info["plaintiff"] = full
                            break
                    # 尝试匹配被告简称
                    for short, full in defendant_mapping.items():
                        if short in part and not info.get("defendant"):
                            info["defendant"] = full
                            break
            
            # 4. 提取案由
            for part in parts:
                for keyword, cause in cause_mapping.items():
                    if keyword in part:
                        info["cause"] = cause
                        break
                if info["cause"]:
                    break
            
            # 5. 提取法院
            for part in parts:
                for short, full in court_mapping.items():
                    if short in part:
                        info["court"] = full
                        break
                if info["court"]:
                    break
            
        except Exception as e:
            pass
        
        return info
    
    def _extract_case_number(self, text: str) -> Optional[str]:
        """提取案号"""
        patterns = [
            r"[（\(]\d{4}[）\)]\S{2,4}\d{2,4}\S{0,3}\d+\S*[民初号]*",
            r"\d{4}京\d{4}民初\d+号",
            r"\d{4}\S{1,2}\d{4,6}\S{0,3}\d+\S*[民初]*号",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)[:50]  # 限制长度
        return None
    
    def _extract_parties(self, text: str, dir_info: dict = None) -> tuple[list, list]:
        """提取当事人"""
        plaintiffs = []
        defendants = []
        
        # 如果目录名解析有原告/被告，优先使用
        if dir_info:
            if dir_info.get("plaintiff"):
                plaintiffs.append(Party(name=dir_info["plaintiff"], role="原告"))
            if dir_info.get("defendant"):
                defendants.append(Party(name=dir_info["defendant"], role="被告"))
        
        # 如果已有当事人，不再从文本提取
        if plaintiffs and defendants:
            return plaintiffs[:1], defendants[:1]
        
        # 从文本中提取原告
        py_patterns = [
            r"原告[：:]\s*([^，,\n]+?公司)",
            r"原告[：:]\s*([^，,\n]+?)",
            r"([\S公司]{2,20}公司)\s*(?:诉|起诉)",
        ]
        for pattern in py_patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip()
                if name and len(name) > 3 and "公司" in name:
                    plaintiffs.append(Party(name=name, role="原告"))
                    break
            if plaintiffs:
                break
        
        # 从文本中提取被告
        df_patterns = [
            r"被告[：:]\s*([^，,\n]+?公司)",
            r"被告[：:]\s*([^，,\n]+?)",
            r"(?:诉|起诉)\s*([\S公司]{2,20}公司)",
        ]
        for pattern in df_patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip()
                if name and len(name) > 3 and "公司" in name:
                    defendants.append(Party(name=name, role="被告"))
                    break
            if defendants:
                break
        
        return plaintiffs[:1], defendants[:1]  # 只取第一个
    
    def _extract_cause(self, text: str, case_name: str) -> str:
        """提取案由"""
        # 从文件名推断（优先）
        if "信息网络传播权" in case_name or "信网权" in case_name:
            return "侵害作品信息网络传播权纠纷"
        if "著作权" in case_name:
            return "著作权纠纷"
        
        # 从文本中提取
        cause_patterns = [
            r"案由[：:]\s*([^\n]+)",
            r"(侵害[^\n]{0,5}权纠纷)",
            r"(著作权[^\n]{0,5}纠纷)",
        ]
        for pattern in cause_patterns:
            match = re.search(pattern, text)
            if match:
                cause = match.group(1).strip()
                if len(cause) > 3:  # 过滤太短的匹配
                    return cause
        
        return "待补充"
    
    def _extract_court(self, text: str) -> Optional[str]:
        """提取法院"""
        court_patterns = [
            r"([一-龥]{2,10}法院)",
            r"([一-龥]{2,10}人民法院)",
        ]
        for pattern in court_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_result(self, text: str) -> Optional[str]:
        """提取案件结果"""
        result_keywords = ["驳回", "撤诉", "调解", "判决", "结案", "胜诉", "败诉"]
        for keyword in result_keywords:
            if keyword in text:
                return keyword
        return None
    
    def _extract_defenses(self, contents: list[ParsedContent]) -> list[DefenseArgument]:
        """从答辩状中提取抗辩要点"""
        defenses = []
        
        for c in contents:
            if "答辩" in c.file_info.name.lower() and c.text:
                # 提取关键抗辩点
                text = c.text[:3000]  # 只取前3000字
                
                # 主体不适格
                if "主体不适格" in text or "主体不适" in text:
                    defenses.append(DefenseArgument(
                        rank=len(defenses)+1,
                        argument_type="主体不适格",
                        content="原告主体不适格，权属不清",
                        evidence="答辩状",
                        priority="主力",
                    ))
                
                # ISRC编码问题
                if "ISRC" in text or "编码" in text:
                    defenses.append(DefenseArgument(
                        rank=len(defenses)+1,
                        argument_type="权属不清",
                        content="涉案作品ISRC编码登记主体非原告",
                        evidence="ISRC查询结果",
                        priority="主力",
                    ))
                
                # 合法来源
                if "合法来源" in text or "授权" in text:
                    defenses.append(DefenseArgument(
                        rank=len(defenses)+1,
                        argument_type="合法来源",
                        content="经音集协授权，具有合法来源",
                        evidence="授权协议",
                        priority="辅助",
                    ))
        
        return defenses[:5]  # 最多5个
    
    def _extract_evidence_points(self, contents: list[ParsedContent]) -> str:
        """从质证意见中提取质证要点"""
        points = []
        
        for c in contents:
            if "质证" in c.file_info.name.lower() and c.text:
                text = c.text[:500]
                points.append(text)
        
        return " | ".join(points[:2]) if points else "待提取"


class MockEngine:
    """模拟引擎（测试用）"""
    
    def extract(self, contents: list[ParsedContent], case_name: str) -> ExtractedCase:
        """返回模拟数据"""
        from datetime import datetime, timezone
        
        return ExtractedCase(
            case_number="2026京XX民初XXXXX号",
            case_name=case_name,
            court="北京市XX区人民法院",
            cause="侵害作品信息网络传播权纠纷",
            plaintiffs=[Party(name="腾讯音乐娱乐（珠海）有限公司", role="原告", company="腾讯音乐", auth_level="独家被授权方")],
            defendants=[Party(name="北京雷石天地电子技术有限公司", role="被告", company="雷石集团")],
            source_files=[c.file_info.path.name for c in contents],
            confidence=0.95,
            extracted_at=datetime.now(timezone.utc).isoformat(),
            d1_facts=DFacts(
                background="原告主张被告未经授权在其运营的KTV点播系统中播放原告享有著作权的音乐作品",
                dispute_points=["被告是否实施了侵权行为", "原告权利基础是否完整", "赔偿数额如何确定"],
                key_facts=[
                    KeyFact(description="被告运营KTV点播系统", source="起诉状第2段", status="已证"),
                    KeyFact(description="原告享有涉案歌曲著作权", source="授权书", status="已证"),
                ],
                rights_basis="原告经授权享有涉案音乐作品的放映权和信息网络传播权",
                behavior="被告在其KTV系统中提供涉案歌曲的放映服务",
            ),
            d2_legal=DLegal(
                laws=[
                    LegalBasis(law_name="著作权法", article="第10条", content="放映权、广播权、信息网络传播权", applicability="被告行为落入信息网络传播权控制范围"),
                ],
                legal_relationship="著作权侵权纠纷",
                rights_analysis="原告授权链完整",
                defense_feasibility="需审查被告是否已获授权",
            ),
            d3_strategy=DStrategy(
                plaintiff_claims="停止侵权、赔偿损失",
                defenses=[
                    DefenseArgument(rank=1, argument_type="主体不适格", content="原告授权链不完整", evidence="授权书", priority="主力"),
                ],
                argument_chain="如授权链完整，则侵权成立",
                main_battlefield="授权链是否完整",
            ),
            d4_evidence=DEvidence(
                plaintiff_evidence=[
                    Evidence(seq=1, name="授权书", purpose="证明原告权利基础", evidence_type="原件", status="有效"),
                ],
                defendant_evidence=[],
                cross_exam_points="真实性、合法性、关联性审查",
                burden_of_proof="原告对侵权事实负举证责任",
            ),
            d5_damages=DDamages(
                total_claim="人民币50万元",
                defense_arguments="赔偿数额过高",
                calculation=[
                    DamageClaim(claim_type="法定赔偿", plaintiff_amount="50万", defendant_argument="过高", reasonable_range="10-30万"),
                ],
                factors="传播范围、持续时间、过错程度",
                estimate="法院可能在10-30万元区间内酌定",
            ),
        )


class ExtractionError(Exception):
    """提取错误"""
    pass


# =============================================
# 引擎工厂
# =============================================

def get_engine(engine_type: str = "basic") -> AIEngine:
    """获取 AI 引擎"""
    if engine_type == "ollama":
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaEngine(model=model, base_url=base_url)
    elif engine_type == "mock":
        return MockEngine()
    elif engine_type == "minimax":
        # 使用 ai_engine.py 中的 MiniMax 引擎
        try:
            from .ai_engine import get_engine_manager
            manager = get_engine_manager()
            return MiniMaxAdapter(manager)
        except ImportError:
            # 降级到 basic
            return BasicEngine()
    elif engine_type == "openai":
        try:
            from .ai_engine import get_engine_manager
            return OpenAIAdapter(get_engine_manager())
        except ImportError:
            return BasicEngine()
    elif engine_type == "basic":
        return BasicEngine()
    else:
        raise ValueError(
            f"不支持的引擎类型: {engine_type}（支持: {', '.join(SUPPORTED_ENGINES)}）"
        )


# =============================================
# 便捷函数
# =============================================

def extract_case(
    contents: list[ParsedContent],
    case_name: str,
    engine_type: str = "mock",
) -> ExtractedCase:
    """提取案件信息"""
    engine = get_engine(engine_type)
    return engine.extract(contents, case_name)


def extracted_from_dict(case_data: dict) -> ExtractedCase:
    """从 JSON dict 构建 ExtractedCase（字段解析与 AI 提取共用）。"""
    extracted = ExtractedCase()
    _apply_case_scalars(extracted, case_data)
    extracted.source_files = case_data.get("source_files", [])
    extracted.plaintiffs = _party_list(case_data.get("plaintiffs"), "原告")
    extracted.defendants = _party_list(case_data.get("defendants"), "被告")
    _apply_dims(extracted, case_data)
    if case_data.get("quality"):
        extracted.quality = str(case_data.get("quality"))
    return extracted

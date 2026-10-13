# =============================================
# importer.py - 数据导入器
# 将提取的结构化信息入库（cases 表 + artifacts 表）
# =============================================
import json
from pathlib import Path
from typing import Optional

from . import database as db
from . import artifact_store
from .extractor import ExtractedCase
from .court_resolver import resolve_court, year_from_case_number as _year_from_case_number
from .markdown_utils import strip_empty_sections


class ImportError(Exception):
    """导入错误"""
    pass


class CaseImporter:
    """案件导入器"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
    
    def import_case(self, extracted: ExtractedCase) -> str:
        """
        导入案件到数据库
        
        Returns:
            case_id: 新创建的案件 ID
        """
        # 检查是否重复
        if extracted.case_number:
            existing = db.get_case_by_number(extracted.case_number, self.db_path)
            if existing:
                raise ImportError(
                    f"案号已存在: {extracted.case_number}\n"
                    f"现有案件: {existing['case_name']} (ID: {existing['id']})"
                )

        # 法院：优先用提取器结果（目录名/LLM 更可靠），回落案号派生
        court = (extracted.court or "").strip() or resolve_court(extracted.case_number)
        # 年份：优先提取器结果，回落案号派生
        year = extracted.year or _year_from_case_number(extracted.case_number)

        # 创建案件
        case = db.create_case(
            case_name=extracted.case_name,
            case_number=extracted.case_number,
            plaintiff=", ".join(p.name for p in extracted.plaintiffs),
            defendant=", ".join(p.name for p in extracted.defendants),
            cause=extracted.cause,
            court=court,
            year=year,
            result=extracted.result,
            source_path="",  # 待设置
            source_files=", ".join(extracted.source_files),
            notes="",
            entry_method="AI",
            scene=extracted.scene,
            plaintiff_auth_level=extracted.plaintiffs[0].auth_level if extracted.plaintiffs else "",
            defendant_auth_status=extracted.defendant_auth_status,
            quality=extracted.quality,
            db_path=self.db_path,
        )

        return case["id"]
    
    def import_artifacts(
        self,
        case_id: str,
        extracted: ExtractedCase,
        generation_method: str = "",
        model_version: str = "",
    ) -> list[str]:
        """
        导入提取物到数据库
        
        Args:
            generation_method: 生成方式（llm / rule-based / mock / import-json）
            model_version: 模型版本（如 MiniMax-Text-01）
        
        Returns:
            artifact_ids: 创建的提取物 ID 列表
        """
        artifact_ids = []
        source_ref = ", ".join(extracted.source_files)
        common = dict(
            source_ref=source_ref,
            db_path=self.db_path,
            generation_method=generation_method or None,
            model_version=model_version or None,
        )

        # D1: 事实认定 -> case_key_facts
        if extracted.d1_facts:
            artifact = artifact_store.create_artifact(
                case_id=case_id,
                artifact_type="case_key_facts",
                title="D1: 事实认定",
                content=self._format_d1(extracted.d1_facts),
                **common,
            )
            artifact_ids.append(artifact["id"])

        # D2: 法律依据 -> legal_reasoning_chain
        if extracted.d2_legal:
            artifact = artifact_store.create_artifact(
                case_id=case_id,
                artifact_type="legal_reasoning_chain",
                title="D2: 法律依据",
                content=self._format_d2(extracted.d2_legal),
                **common,
            )
            artifact_ids.append(artifact["id"])

        # D3: 攻防策略 -> defense_argument_chain
        if extracted.d3_strategy:
            artifact = artifact_store.create_artifact(
                case_id=case_id,
                artifact_type="defense_argument_chain",
                title="D3: 攻防策略",
                content=self._format_d3(extracted.d3_strategy),
                **common,
            )
            artifact_ids.append(artifact["id"])

        # D4: 证据体系 -> evidence_structure
        if extracted.d4_evidence:
            artifact = artifact_store.create_artifact(
                case_id=case_id,
                artifact_type="evidence_structure",
                title="D4: 证据体系",
                content=self._format_d4(extracted.d4_evidence),
                **common,
            )
            artifact_ids.append(artifact["id"])

        # D5: 赔偿裁量 -> liability_calculation
        if extracted.d5_damages:
            artifact = artifact_store.create_artifact(
                case_id=case_id,
                artifact_type="liability_calculation",
                title="D5: 赔偿裁量",
                content=self._format_d5(extracted.d5_damages),
                **common,
            )
            artifact_ids.append(artifact["id"])

        return artifact_ids
    
    def import_full(
        self,
        extracted: ExtractedCase,
        generation_method: str = "",
        model_version: str = "",
    ) -> dict:
        """
        完整导入（案件 + 提取物）
        
        Args:
            generation_method: 生成方式（llm / rule-based / mock / import-json）
            model_version: 模型版本
        
        Returns:
            {"case_id": ..., "artifact_ids": [...]}
        """
        # 导入案件
        case_id = self.import_case(extracted)
        
        # 导入提取物（含 Markdown 文件落盘）
        artifact_ids = self.import_artifacts(
            case_id, extracted,
            generation_method=generation_method,
            model_version=model_version,
        )
        
        # 标记为已提取
        db.update_case_status(case_id, "extracted", self.db_path)
        
        return {
            "case_id": case_id,
            "artifact_ids": artifact_ids,
        }
    
    def _format_d1(self, d1) -> str:
        """格式化 D1 事实认定"""
        lines = [
            "## 1. 案件背景",
            d1.background,
            "",
            "## 2. 争议焦点",
        ]
        for i, point in enumerate(d1.dispute_points, 1):
            lines.append(f"{i}. {point}")
        lines.extend([
            "",
            "## 3. 关键事实",
            "| # | 事实描述 | 来源 | 状态 |",
            "|---|---------|------|------|",
        ])
        for i, fact in enumerate(d1.key_facts, 1):
            lines.append(f"| {i} | {fact.description} | {fact.source} | {fact.status} |")
        lines.extend([
            "",
            "## 4. 权利基础分析",
            d1.rights_basis,
            "",
            "## 5. 行为定性",
            d1.behavior,
        ])
        return strip_empty_sections("\n".join(lines))
    
    def _format_d2(self, d2) -> str:
        """格式化 D2 法律依据"""
        lines = [
            "## 1. 适用法律",
            "| 法律 | 条款 | 内容 | 适用 |",
            "|------|------|------|------|",
        ]
        for law in d2.laws:
            lines.append(f"| {law.law_name} | {law.article} | {law.content} | {law.applicability} |")
        lines.extend([
            "",
            "## 2. 法律关系定性",
            d2.legal_relationship,
            "",
            "## 3. 权利基础分析",
            d2.rights_analysis,
            "",
            "## 4. 被告抗辩的法律可行性",
            d2.defense_feasibility,
        ])
        return strip_empty_sections("\n".join(lines))
    
    def _format_d3(self, d3) -> str:
        """格式化 D3 攻防策略"""
        lines = [
            "## 1. 原告诉请",
            d3.plaintiff_claims,
            "",
            "## 2. 被告抗辩（按优先级排序）",
            "| 排序 | 类型 | 内容 | 证据 | 优先级 |",
            "|------|------|------|------|--------|",
        ]
        for d in d3.defenses:
            lines.append(f"| {d.rank} | {d.argument_type} | {d.content} | {d.evidence} | {d.priority} |")
        lines.extend([
            "",
            "## 3. 抗辩论证结构",
            d3.argument_chain,
            "",
            "## 4. 主战场决策",
            d3.main_battlefield,
        ])
        return strip_empty_sections("\n".join(lines))
    
    def _format_d4(self, d4) -> str:
        """格式化 D4 证据体系"""
        lines = [
            "## 1. 原告证据清单",
            "| 序号 | 证据名称 | 证明目的 | 类型 | 状态 |",
            "|------|---------|---------|------|------|",
        ]
        for e in d4.plaintiff_evidence:
            lines.append(f"| {e.seq} | {e.name} | {e.purpose} | {e.evidence_type} | {e.status} |")
        
        if d4.defendant_evidence:
            lines.extend([
                "",
                "## 2. 被告证据清单",
                "| 序号 | 证据名称 | 证明目的 | 类型 | 状态 |",
                "|------|---------|---------|------|------|",
            ])
            for e in d4.defendant_evidence:
                lines.append(f"| {e.seq} | {e.name} | {e.purpose} | {e.evidence_type} | {e.status} |")
        
        lines.extend([
            "",
            "## 3. 质证要点",
            d4.cross_exam_points,
            "",
            "## 4. 举证责任分配",
            d4.burden_of_proof,
        ])
        return strip_empty_sections("\n".join(lines))
    
    def _format_d5(self, d5) -> str:
        """格式化 D5 赔偿裁量"""
        lines = [
            "## 1. 赔偿请求",
            d5.total_claim,
            "",
            "## 2. 被告抗辩理由",
            d5.defense_arguments,
            "",
            "## 3. 计算方式分析",
            "| 计算方式 | 原告主张 | 被告抗辩 | 合理区间 |",
            "|---------|---------|---------|---------|",
        ]
        for c in d5.calculation:
            lines.append(f"| {c.claim_type} | {c.plaintiff_amount} | {c.defendant_argument} | {c.reasonable_range} |")
        lines.extend([
            "",
            "## 4. 裁量因素",
            d5.factors,
            "",
            "## 5. 预估结论",
            d5.estimate,
        ])
        return strip_empty_sections("\n".join(lines))


# =============================================
# 便捷函数
# =============================================

def import_extracted_case(
    extracted: ExtractedCase,
    db_path: Optional[Path] = None,
    generation_method: str = "",
    model_version: str = "",
) -> dict:
    """导入提取的案件"""
    importer = CaseImporter(db_path)
    return importer.import_full(
        extracted, generation_method=generation_method, model_version=model_version
    )


def preview_import(extracted: ExtractedCase) -> str:
    """预览导入信息"""
    lines = [
        "📋 导入预览",
        "=" * 50,
        "",
        f"案件名称: {extracted.case_name}",
        f"案号: {extracted.case_number or '(待补充)'}",
        f"法院: {extracted.court or '(待补充)'}",
        f"案由: {extracted.cause}",
        "",
        "当事人:",
    ]
    
    for p in extracted.plaintiffs:
        lines.append(f"  原告: {p.name} ({p.company})")
    for p in extracted.defendants:
        lines.append(f"  被告: {p.name} ({p.company})")
    
    lines.extend([
        "",
        "提取维度:",
    ])
    
    dims = []
    if extracted.d1_facts:
        dims.append("D1 事实认定")
    if extracted.d2_legal:
        dims.append("D2 法律依据")
    if extracted.d3_strategy:
        dims.append("D3 攻防策略")
    if extracted.d4_evidence:
        dims.append("D4 证据体系")
    if extracted.d5_damages:
        dims.append("D5 赔偿裁量")
    
    lines.extend([f"  - {d}" for d in dims])
    
    return "\n".join(lines)

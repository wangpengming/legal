# =============================================
# test_extraction_prompt.py - 提取提示词完整性 + 共用解析助手（纯逻辑）
# 可 pytest 收集，亦可直接运行: python3 tests/test_extraction_prompt.py
# =============================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extractor import (  # noqa: E402
    build_extraction_prompt,
    _coerce_year,
    _party_list,
    _strip_json_fence,
    derive_quality,
    ExtractedCase,
    DFacts,
    DLegal,
    DStrategy,
    DEvidence,
    DDamages,
    LegalBasis,
    DefenseArgument,
    Evidence,
)

# 叙述型字段（历史空壳高发区）必须出现在 prompt 字段集中
_NARRATIVE_FIELDS = [
    "rights_basis", "behavior", "rights_analysis", "defense_feasibility",
    "argument_chain", "main_battlefield", "cross_exam_points",
    "burden_of_proof", "factors", "estimate",
]
_SCALAR_FIELDS = ["case_number", "court", "result", "scene", "year", "defendant_auth_status"]
_DIM_FIELDS = ["d1_facts", "d2_legal", "d3_strategy", "d4_evidence", "d5_damages"]


def test_prompt_covers_all_narrative_fields():
    """P3：共用提示词必须覆盖叙述型字段（空壳根因是精简 prompt）。"""
    p = build_extraction_prompt("测试案", "材料正文")
    for f in _NARRATIVE_FIELDS + _SCALAR_FIELDS + _DIM_FIELDS:
        assert f in p, f"prompt 缺字段: {f}"


def test_prompt_truncates_text_to_max_chars():
    p = build_extraction_prompt("案", "x" * 100, max_chars=10)
    assert "x" * 10 in p and "x" * 11 not in p


def test_strip_json_fence_removes_code_block():
    assert _strip_json_fence('```json\n{"a":1}\n```') == '{"a":1}'
    assert _strip_json_fence('{"a":1}') == '{"a":1}'


def test_coerce_year_tolerates_formats():
    assert _coerce_year(2024) == 2024
    assert _coerce_year("2024年") == 2024
    assert _coerce_year("无") is None
    assert _coerce_year(None) is None


def test_party_list_defaults_role_and_skips_non_dict():
    got = _party_list([{"name": "甲公司"}, "bad", {"name": "乙", "role": "被告"}], "原告")
    assert [p.name for p in got] == ["甲公司", "乙"]
    assert got[0].role == "原告" and got[1].role == "被告"


def _case_with_dims(n):
    """构造含 n 个（有实质内容的）维度的 ExtractedCase。"""
    c = ExtractedCase()
    if n >= 1:
        c.d1_facts = DFacts(background="法院认定…", dispute_points=[], key_facts=[], rights_basis="权属链完整", behavior="")
    if n >= 2:
        c.d2_legal = DLegal(laws=[LegalBasis(law_name="著作权法", article="第十条", content="…", applicability="适用")], legal_relationship="", rights_analysis="", defense_feasibility="")
    if n >= 3:
        c.d3_strategy = DStrategy(plaintiff_claims="停止侵权并赔偿", defenses=[DefenseArgument(rank=1, argument_type="合理使用", content="…", evidence="", priority="主力")], argument_chain="", main_battlefield="")
    if n >= 4:
        c.d4_evidence = DEvidence(plaintiff_evidence=[Evidence(seq=1, name="权属证据", purpose="证明权属", evidence_type="原件", status="有效")], defendant_evidence=[], cross_exam_points="", burden_of_proof="")
    if n >= 5:
        c.d5_damages = DDamages(total_claim="10万", defense_arguments="", calculation=[], factors="传播范围广", estimate="")
    return c


def test_derive_quality_full_five_dims_is_A():
    c = _case_with_dims(5)
    assert derive_quality(c) == "A"


def test_derive_quality_partial_and_identity():
    # 无案号：3 维 → B；2 维 → C；1 维 → C
    assert derive_quality(_case_with_dims(3)) == "B"
    assert derive_quality(_case_with_dims(2)) == "C"
    assert derive_quality(_case_with_dims(1)) == "C"
    # 有案号：即便维度少也至少 B（基本身份可定）
    c = _case_with_dims(2)
    c.case_number = "(2024)京0491民初1号"
    assert derive_quality(c) == "B"


def test_derive_quality_empty_dim_not_counted():
    # 存在但全空的维度不计入实质内容
    c = ExtractedCase(d1_facts=DFacts(background="", dispute_points=[], key_facts=[], rights_basis="", behavior=""))
    assert derive_quality(c) == "C"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
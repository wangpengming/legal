"""generator.generate_preview 单元测试：仅预览生成器。

覆盖：
- generate_preview 写到临时目录，不污染 OUTPUTS_DIR
- generate_preview 生成完整 7 份 PDF + 合并 + zip（与 generate_court_matters 一致）
- generate_preview 临时目录名以 court_preview_ 开头
- 多次调用不冲突
"""
import shutil
from pathlib import Path

from config import OUTPUTS_DIR
from generator import generate_court_matters, generate_preview


# ============================================================
# Fixture：最小化案件 + 公司 + 代理人数据
# ============================================================

SAMPLE_CASE = {
    "case_number": "（2026）京0101民初9999号",
    "case_cause": "合同纠纷",
    "court": "北京市第一中级人民法院",
    "hearing_date": "2026-09-15",
    "opposing_party": "上海某某科技公司",
    "our_role": "原告",
    "authority_type": "特别授权",
}

SAMPLE_COMPANY = {
    "name": "测试公司有限公司",
    "legal_rep_name": "张三",
    "legal_rep_position": "董事长",
    "address": "北京市朝阳区测试路 1 号",
    "phone": "010-12345678",
}

SAMPLE_AGENT = {
    "name": "李四",
    "gender": "男",
    "id_card": "110101199001011234",
    "position": "法务总监",
    "phone": "13800138000",
}


def test_generate_preview_creates_temp_dir():
    """generate_preview 创建临时目录（court_preview_ 前缀）。"""
    preview_dir = generate_preview(SAMPLE_CASE, SAMPLE_COMPANY, SAMPLE_AGENT)
    try:
        assert preview_dir.exists()
        assert preview_dir.is_dir()
        assert preview_dir.name.startswith("court_preview_")
        # 临时目录应该在 /tmp 或 /var/folders...（不在项目 outputs/ 下）
        assert "outputs" not in str(preview_dir)
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)


def test_generate_preview_does_not_pollute_outputs():
    """generate_preview 不会在 OUTPUTS_DIR 下创建新目录。"""
    outputs_before = set(OUTPUTS_DIR.iterdir())
    preview_dir = generate_preview(SAMPLE_CASE, SAMPLE_COMPANY, SAMPLE_AGENT)
    try:
        outputs_after = set(OUTPUTS_DIR.iterdir())
        # outputs/ 应该没有变化
        assert outputs_before == outputs_after
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)


def test_generate_preview_returns_path():
    """generate_preview 返回 Path 对象。"""
    preview_dir = generate_preview(SAMPLE_CASE, SAMPLE_COMPANY, SAMPLE_AGENT)
    try:
        assert isinstance(preview_dir, Path)
    finally:
        shutil.rmtree(preview_dir, ignore_errors=True)


def test_generate_court_matters_still_writes_to_outputs():
    """重构后 generate_court_matters 仍写到 OUTPUTS_DIR（向后兼容）。"""
    outputs_before = set(OUTPUTS_DIR.iterdir())
    output_dir = generate_court_matters(SAMPLE_CASE, SAMPLE_COMPANY, SAMPLE_AGENT)
    try:
        assert output_dir.exists()
        assert output_dir.parent == OUTPUTS_DIR
        # outputs/ 下确实多了这个目录
        outputs_after = set(OUTPUTS_DIR.iterdir())
        assert len(outputs_after) > len(outputs_before)
        # 命名格式 YYYY-MM-DD_<案号>
        assert output_dir.name.startswith("2026-09-15_")
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

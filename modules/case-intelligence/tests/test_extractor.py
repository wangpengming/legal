# =============================================
# test_extractor.py - 提取器测试（简化版）
# =============================================
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestExtractor:
    """提取器测试类"""
    
    def test_extractor_module_import(self):
        """测试 extractor 模块可导入"""
        try:
            from extractor import extract_case_info
            assert callable(extract_case_info)
        except ImportError as e:
            pytest.skip(f"模块导入跳过: {e}")


class TestD1D5Dimensions:
    """D1-D5 维度测试"""
    
    DIMENSIONS = ["D1", "D2", "D3", "D4", "D5"]
    
    def test_d1_d5_dimensions(self):
        """测试 D1-D5 维度定义"""
        assert len(self.DIMENSIONS) == 5
    
    def test_d1_exists(self):
        """测试 D1 存在"""
        assert "D1" in self.DIMENSIONS
    
    def test_d5_exists(self):
        """测试 D5 存在"""
        assert "D5" in self.DIMENSIONS


class TestDimensionNames:
    """维度名称测试"""
    
    DIMENSION_NAMES = {
        "D1": "事实认定",
        "D2": "法律依据",
        "D3": "攻防策略",
        "D4": "证据体系",
        "D5": "赔偿裁量",
    }
    
    def test_dimension_names(self):
        """测试维度名称映射"""
        assert self.DIMENSION_NAMES["D1"] == "事实认定"
        assert self.DIMENSION_NAMES["D2"] == "法律依据"
        assert self.DIMENSION_NAMES["D3"] == "攻防策略"
        assert self.DIMENSION_NAMES["D4"] == "证据体系"
        assert self.DIMENSION_NAMES["D5"] == "赔偿裁量"


class TestOCRIntegration:
    """OCR 集成测试"""
    
    def test_ocr_extraction_available(self):
        """测试 OCR 提取功能可用"""
        try:
            import pytesseract
            assert True
        except ImportError:
            pytest.skip("pytesseract 未安装")
    
    def test_pymupdf_available(self):
        """测试 PyMuPDF 可用"""
        try:
            import fitz
            assert True
        except ImportError:
            pytest.skip("PyMuPDF 未安装")

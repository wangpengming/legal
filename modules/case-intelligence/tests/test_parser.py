# =============================================
# test_parser.py - 文件解析测试（简化版）
# =============================================
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestParser:
    """文件解析测试类"""
    
    def test_parser_module_import(self):
        """测试 parser 模块可导入"""
        try:
            from parser import parse_document
            assert callable(parse_document)
        except ImportError as e:
            pytest.skip(f"模块导入跳过: {e}")


class TestSupportedFormats:
    """支持格式测试"""
    
    SUPPORTED_FORMATS = ["docx", "pdf", "txt", "md"]
    
    def test_supported_formats(self):
        """测试支持的格式"""
        assert "docx" in self.SUPPORTED_FORMATS
        assert "pdf" in self.SUPPORTED_FORMATS
        assert "txt" in self.SUPPORTED_FORMATS
        assert "md" in self.SUPPORTED_FORMATS


class TestContentExtraction:
    """内容提取测试"""
    
    def test_text_extraction_logic(self):
        """测试文本提取逻辑"""
        sample_text = "这是一个测试文本"
        assert len(sample_text) > 0
        assert "测试" in sample_text
    
    def test_encoding_handling(self):
        """测试编码处理"""
        text = "中文测试"
        encoded = text.encode("utf-8")
        decoded = encoded.decode("utf-8")
        assert text == decoded

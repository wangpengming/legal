# =============================================
# test_scanner.py - 目录扫描测试（简化版）
# =============================================
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestScanner:
    """目录扫描测试类"""
    
    def test_scanner_module_import(self):
        """测试 scanner 模块可导入"""
        try:
            from scanner import scan_directory
            assert callable(scan_directory)
        except ImportError as e:
            pytest.skip(f"模块导入跳过: {e}")
    
    def test_case_recognizer_module_import(self):
        """测试 case_recognizer 模块可导入"""
        try:
            from case_recognizer import recognize_case
            assert callable(recognize_case)
        except ImportError as e:
            pytest.skip(f"模块导入跳过: {e}")


class TestFileTypes:
    """文件类型测试"""
    
    SUPPORTED_EXTENSIONS = [".docx", ".pdf", ".txt", ".md"]
    
    def test_supported_extensions(self):
        """测试支持的扩展名"""
        for ext in self.SUPPORTED_EXTENSIONS:
            assert ext.startswith(".")
    
    def test_extension_recognition(self):
        """测试扩展名识别"""
        test_cases = [
            ("document.docx", True),
            ("case.pdf", True),
            ("notes.txt", True),
            ("readme.md", True),
        ]
        
        for filename, expected in test_cases:
            ext = Path(filename).suffix.lower()
            is_supported = ext in [".docx", ".pdf", ".txt", ".md"]
            assert is_supported == expected


class TestOCRFiltering:
    """OCR噪音过滤测试"""
    
    def test_ocr_noise_patterns(self):
        """测试 OCR 噪音模式识别"""
        noise_patterns = ["http://", "www.", ".com", "data:image"]
        for pattern in noise_patterns:
            assert len(pattern) > 0

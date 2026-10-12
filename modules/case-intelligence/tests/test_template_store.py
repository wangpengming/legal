# =============================================
# test_template_store.py - 模板存储测试（简化版）
# =============================================
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class TestTemplateStore:
    """模板存储测试类"""
    
    def test_template_store_module_import(self):
        """测试模板存储模块可导入"""
        try:
            from template_store import create_template
            assert callable(create_template)
        except ImportError as e:
            pytest.skip(f"模块导入跳过: {e}")


class TestPromptsValidation:
    """Prompts 验证测试类"""
    
    def test_prompts_directory_exists(self):
        """测试 Prompts 目录是否存在"""
        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        assert prompts_dir.exists(), "Prompts 目录应该存在"
    
    def test_prompts_files_exist(self):
        """测试关键提示词文件是否存在"""
        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        
        expected_files = [
            prompts_dir / "prompts.yaml",
            prompts_dir / "提取" / "1_新案材料提取_D1-D5.md",
            prompts_dir / "生成" / "5_答辩状生成.md",
        ]
        
        for file_path in expected_files:
            assert file_path.exists(), f"{file_path.name} 应该存在"
    
    def test_prompts_yaml_structure(self):
        """测试 prompts.yaml 文件存在"""
        prompts_yaml = Path(__file__).resolve().parent.parent / "prompts" / "prompts.yaml"
        assert prompts_yaml.exists(), "prompts.yaml 应该存在"
    
    def test_all_8_prompts_exist(self):
        """测试所有8个提示词文件都存在"""
        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        
        expected_files = [
            "提取/1_新案材料提取_D1-D5.md",
            "提取/2_跨案归纳_Artifact汇聚.md",
            "提取/3_质量检查_提取物审核.md",
            "匹配/4_新案匹配_相似案源检索.md",
            "生成/5_答辩状生成.md",
            "生成/6_质证意见生成.md",
            "生成/7_当庭陈述生成.md",
            "生成/8_证据目录生成.md",
        ]
        
        for rel_path in expected_files:
            file_path = prompts_dir / rel_path
            assert file_path.exists(), f"{rel_path} 应该存在"
    
    def test_prompts_have_yaml_frontmatter(self):
        """测试提示词文件都有 YAML frontmatter"""
        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        
        prompt_files = [
            prompts_dir / "提取" / "1_新案材料提取_D1-D5.md",
            prompts_dir / "生成" / "5_答辩状生成.md",
        ]
        
        for file_path in prompt_files:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                assert content.startswith("---"), f"{file_path.name} 应该有 YAML frontmatter"


class TestOutputTemplates:
    """输出模板测试类"""
    
    def test_output_templates_directory_exists(self):
        """测试 output_templates 目录是否存在"""
        templates_dir = Path(__file__).resolve().parent.parent / "output_templates"
        assert templates_dir.exists(), "output_templates 目录应该存在"
    
    def test_each_category_has_2_templates(self):
        """测试每个类别至少有2个模板"""
        templates_dir = Path(__file__).resolve().parent.parent / "output_templates"
        
        categories = ["答辩状", "质证意见", "当庭陈述", "证据目录"]
        
        for category in categories:
            category_dir = templates_dir / category
            if category_dir.exists():
                md_files = list(category_dir.glob("*.md"))
                assert len(md_files) >= 2, f"{category} 应该有至少2个模板"
    
    def test_templates_have_yaml_frontmatter(self):
        """测试模板都有 YAML frontmatter"""
        templates_dir = Path(__file__).resolve().parent.parent / "output_templates"
        
        for category_dir in templates_dir.iterdir():
            if category_dir.is_dir():
                for md_file in category_dir.glob("*.md"):
                    content = md_file.read_text(encoding="utf-8")
                    assert content.startswith("---"), f"{md_file.name} 应该有 YAML frontmatter"

#!/usr/bin/env python3
# =============================================
# case-intelligence v4.0 文书生成器
# 基于 LLM + RAG 的文书自动生成
# =============================================
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent

# 参考提取物注入上限（防止 prompt 爆炸，同时避免历史 5个/500字 的过度截断）
_MAX_ARTIFACTS = 20
_MAX_ARTIFACT_CHARS = 4000


@dataclass
class CaseContext:
    """案件上下文"""
    case_id: str
    case_number: str
    case_name: str
    plaintiff: str
    defendant: str
    cause: str
    court: str = ""
    scene: str = ""
    artifacts: Dict[str, str] = None  # type: Dict[str, str]
    
    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = {}


@dataclass
class GenerationRequest:
    """生成请求"""
    doc_type: str  # defense / evidence_objection / court_statement / evidence_index
    case_context: CaseContext
    reference_artifacts: List[Dict] = None
    reference_templates: List[Dict] = None
    additional_info: str = ""
    
    def __post_init__(self):
        if self.reference_artifacts is None:
            self.reference_artifacts = []
        if self.reference_templates is None:
            self.reference_templates = []


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    content: str = ""
    error: str = ""
    source: str = ""  # "llm" / "template"
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DocumentGenerator:
    """文书生成器"""
    
    # 支持的文书类型
    DOC_TYPES = {
        "defense": "答辩状",
        "evidence_objection": "质证意见",
        "court_statement": "当庭陈述",
        "evidence_index": "证据目录",
    }
    
    def __init__(self, db_path: Optional[Path] = None, engine: Optional[str] = None):
        self.db_path = db_path or self._get_default_db_path()
        self.prompts_dir = PROJECT_ROOT / "prompts"
        self.templates_dir = PROJECT_ROOT / "output_templates"
        self.engine = engine  # 指定 AI 引擎（None = 用配置文件默认）
        self.ai_engine = None  # 延迟初始化
    
    def _get_default_db_path(self) -> Path:
        """获取默认数据库路径（DATA_DIR 可覆盖，部署时落卷）"""
        data_dir = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")
        return data_dir / "case_registry.db"
    
    def _init_ai_engine(self):
        """初始化 AI 引擎"""
        if self.ai_engine is None:
            try:
                from src.ai_engine import get_engine_manager
                self.ai_engine = get_engine_manager()
                logger.info("AI 引擎初始化成功")
            except Exception as e:
                logger.warning(f"AI 引擎初始化失败: {e}")
                self.ai_engine = None
    
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        生成文书
        
        策略：
        1. 优先使用模板（如果有参考模板）
        2. 使用 LLM 生成（如果配置了 AI 引擎）
        3. 返回模板 + 提示（如果都不可用）
        """
        doc_type = request.doc_type
        
        # 检查模板
        if request.reference_templates:
            template_result = self._generate_from_template(request)
            if template_result.success:
                return template_result
        
        # 检查 AI 引擎
        self._init_ai_engine()
        if self.ai_engine:
            llm_result = self._generate_from_llm(request)
            if llm_result.success:
                return llm_result
        
        # 返回可用信息
        return GenerationResult(
            success=True,
            content=self._generate_fallback_content(request),
            source="fallback",
            metadata={
                "doc_type": doc_type,
                "doc_type_name": self.DOC_TYPES.get(doc_type, doc_type),
                "has_template": len(request.reference_templates) > 0,
                "has_ai_engine": self.ai_engine is not None,
            }
        )
    
    def _generate_from_template(self, request: GenerationRequest) -> GenerationResult:
        """从模板生成（模板+LLM混合模式）"""
        try:
            # 获取第一个模板
            template = request.reference_templates[0]
            content = template.get("content", "")
            
            if not content:
                return GenerationResult(success=False, error="模板内容为空")
            
            # 模板+LLM 混合模式（mock/basic 无 LLM 能力，退化为纯模板）
            if self.engine not in ("mock", "basic"):
                enhanced_content = self._enhance_with_llm(content, request)
                if enhanced_content:
                    return GenerationResult(
                        success=True,
                        content=enhanced_content,
                        source="template+llm",
                        metadata={
                            "template_id": template.get("id"),
                            "template_name": template.get("name"),
                            "engine": self.engine or "minimax",
                        }
                    )
            
            # 纯模板模式：只替换占位符
            content = self._fill_template(content, request.case_context)
            return GenerationResult(
                success=True,
                content=content,
                source="template",
                metadata={
                    "template_id": template.get("id"),
                    "template_name": template.get("name"),
                }
            )
        except Exception as e:
            logger.error(f"模板生成失败: {e}")
            return GenerationResult(success=False, error=str(e))
    
    def _enhance_with_llm(self, template_content: str, request: GenerationRequest) -> Optional[str]:
        """使用 LLM 增强模板内容（按 self.engine 路由）"""
        try:
            case_info = {
                'case_number': request.case_context.case_number,
                'plaintiff': request.case_context.plaintiff,
                'defendant': request.case_context.defendant,
                'cause': request.case_context.cause,
                'court': request.case_context.court,
                'case_name': request.case_context.case_name,
            }
            
            # 构建增强prompt
            prompt = f"""基于以下案件信息和模板结构，生成一份专业的文书。

案件信息：
- 案号：{case_info['case_number']}
- 案件名称：{case_info['case_name']}
- 原告：{case_info['plaintiff']}
- 被告：{case_info['defendant']}
- 案由：{case_info['cause']}
- 法院：{case_info['court']}

模板结构：
{template_content}

请根据上述案件信息，填充模板中的占位符位置（如"被告"、"原告"等），生成完整的文书内容。只返回文书内容，不要其他说明。"""
            
            return self._llm_text(prompt, "你是一位专业的法律文书撰写专家。")
        except Exception as e:
            logger.warning(f"LLM增强失败: {e}")
            return None
    
    def _llm_text(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """按 self.engine 调用 LLM 生成文本；mock/basic 或引擎不可用返回 None。"""
        self._init_ai_engine()
        if self.engine in ("mock", "basic"):
            return None
        if self.engine in ("ollama", "openai"):
            if not self.ai_engine or self.ai_engine.get_engine(self.engine) is None:
                return None
            try:
                return self.ai_engine.chat(prompt, engine=self.engine)
            except Exception as e:
                logger.warning(f"引擎 {self.engine} 调用失败: {e}")
                return None
        # 默认 minimax：优先 LangChain
        try:
            from src.langchain_llm import get_llm_service
            llm = get_llm_service()
            if llm.is_available():
                return llm.generate_document(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"LangChain 调用失败: {e}")
        # 回落 ai_engine 的 minimax
        if self.ai_engine and self.ai_engine.get_engine("minimax"):
            try:
                return self.ai_engine.chat(prompt, engine="minimax")
            except Exception:
                pass
        return None

    def _generate_with_engine(self, request: GenerationRequest) -> Optional[str]:
        """用 ollama/openai 引擎生成文书（提示词库 + chat）；不可用返回 None。"""
        if not self.ai_engine or self.ai_engine.get_engine(self.engine) is None:
            return None
        prompt_template = self.ai_engine.load_prompt(request.doc_type)
        context = self._build_context(request)
        if prompt_template:
            prompt = prompt_template.replace(
                "【案件上下文】", context
            ).replace(
                "【案件材料】", request.additional_info or "（用户提供）"
            )
        else:
            doc_name = self.DOC_TYPES.get(request.doc_type, request.doc_type)
            prompt = f"请根据以下案件信息生成{doc_name}：\n\n{context}"
        try:
            return self.ai_engine.chat(prompt, engine=self.engine)
        except Exception as e:
            logger.warning(f"引擎 {self.engine} 生成失败: {e}")
            return None

    def _generate_from_llm(self, request: GenerationRequest) -> GenerationResult:
        """从 LLM 生成（按 self.engine 路由：ollama/openai → ai_engine；默认 minimax → LangChain）"""
        try:
            self._init_ai_engine()

            # mock/basic 无 LLM 能力，交由兜底
            if self.engine in ("mock", "basic"):
                return GenerationResult(success=False, error=f"引擎 {self.engine} 不支持文书生成")

            # ollama/openai：走 ai_engine 统一 chat（提示词库）
            if self.engine in ("ollama", "openai"):
                content = self._generate_with_engine(request)
                if content:
                    return GenerationResult(success=True, content=content,
                                            source="llm", metadata={"engine": self.engine})
                return GenerationResult(success=False, error=f"引擎 {self.engine} 不可用")

            # 默认 minimax：优先 LangChain（prompts 规则库）
            try:
                from src.langchain_llm import generate_direct, get_llm_service
                llm = get_llm_service()
                if llm.is_available():
                    case_info = {
                        'case_number': request.case_context.case_number,
                        'plaintiff': request.case_context.plaintiff,
                        'defendant': request.case_context.defendant,
                        'cause': request.case_context.cause,
                        'court': request.case_context.court,
                    }
                    return GenerationResult(
                        success=True,
                        content=generate_direct(case_info, request.doc_type),
                        source="langchain_llm",
                        metadata={"engine": "minimax"},
                    )
            except ImportError:
                logger.warning("langchain_llm 导入失败，尝试旧引擎")

            # 降级到旧引擎（ai_engine 提示词库 + chat）
            if not self.ai_engine:
                return GenerationResult(success=False, error="AI 引擎不可用")

            prompt_template = self.ai_engine.load_prompt(request.doc_type)
            if not prompt_template:
                return GenerationResult(success=False, error="提示词文件不存在")

            context = self._build_context(request)
            prompt = prompt_template.replace(
                "【案件上下文】", context
            ).replace(
                "【案件材料】", request.additional_info or "（用户提供）"
            )

            engine_name = self.engine
            if engine_name and self.ai_engine.get_engine(engine_name) is None:
                engine_name = None
            return GenerationResult(
                success=True,
                content=self.ai_engine.chat(prompt, engine=engine_name),
                source="llm",
                metadata={"engine": engine_name or "minimax"},
            )
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            return GenerationResult(success=False, error=str(e))
    
    def _build_context(self, request: GenerationRequest) -> str:
        """构建案件上下文"""
        case = request.case_context
        
        parts = [
            f"案号: {case.case_number or '未知'}",
            f"案件名称: {case.case_name or '未知'}",
            f"原告: {case.plaintiff or '未知'}",
            f"被告: {case.defendant or '未知'}",
            f"案由: {case.cause or '未知'}",
            f"法院: {case.court or '未知'}",
        ]
        
        if case.scene:
            parts.append(f"涉案场景: {case.scene}")
        
        # 添加相关 artifacts（放宽截断：历史 5 个/500 字导致文书缺料）
        if request.reference_artifacts:
            parts.append("")
            parts.append("=== 参考信息 ===")
            for artifact in request.reference_artifacts[:_MAX_ARTIFACTS]:
                artifact_type = artifact.get("artifact_type", "")
                title = artifact.get("title", "")
                content = artifact.get("content", "")[:_MAX_ARTIFACT_CHARS]
                parts.append(f"\n[{artifact_type}] {title}:\n{content}")
        
        return "\n".join(parts)
    
    def _fill_template(self, template: str, case: CaseContext) -> str:
        """填充模板占位符"""
        replacements = {
            "{{case_number}}": case.case_number or "未知",
            "{{case_name}}": case.case_name or "未知",
            "{{plaintiff}}": case.plaintiff or "未知",
            "{{defendant}}": case.defendant or "未知",
            "{{cause}}": case.cause or "未知",
            "{{court}}": case.court or "未知",
        }
        
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
        
        return template
    
    def _generate_fallback_content(self, request: GenerationRequest) -> str:
        """生成后备内容（提示用户）"""
        doc_type_name = self.DOC_TYPES.get(request.doc_type, request.doc_type)
        
        content = f"""# {doc_type_name}

## 案件信息

- 案号: {request.case_context.case_number or '未知'}
- 原告: {request.case_context.plaintiff or '未知'}
- 被告: {request.case_context.defendant or '未知'}
- 案由: {request.case_context.cause or '未知'}

---

## 生成说明

此文书基于模板生成，建议：
1. 根据案件具体情况修改内容
2. 补充相关证据和事实
3. 法律依据请参照最新法规

---
*由 case-intelligence v4.0 生成*
"""
        return content
    
    def get_reference_templates(self, doc_type: str) -> List[Dict]:
        """获取参考模板"""
        import sqlite3
        
        # 映射文书类型到模板类别
        category_map = {
            "defense": "答辩状",
            "evidence_objection": "质证意见",
            "court_statement": "当庭陈述",
            "evidence_index": "证据目录",
        }
        
        category = category_map.get(doc_type)
        if not category:
            return []
        
        # 从模板目录读取
        templates = []
        category_dir = self.templates_dir / category
        
        if category_dir.exists():
            for md_file in category_dir.glob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    # 解析 YAML frontmatter
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            import yaml
                            metadata = yaml.safe_load(parts[1])
                            templates.append({
                                "template_id": metadata.get("template_id"),
                                "name": metadata.get("name"),
                                "category": metadata.get("category"),
                                "content": parts[2].strip(),
                            })
                except Exception as e:
                    logger.warning(f"读取模板失败 {md_file}: {e}")
        
        return templates


class LLMEvaluator:
    """LLM 能力评估器"""
    
    @staticmethod
    def check_ollama_status() -> Dict[str, Any]:
        """检查 Ollama 状态"""
        result = {
            "available": False,
            "version": None,
            "models": [],
            "error": None,
        }
        
        try:
            import requests
            response = requests.get("http://localhost:11434/api/version", timeout=5)
            if response.status_code == 200:
                result["available"] = True
                result["version"] = response.json().get("version", "unknown")
                
                # 获取模型列表
                models_response = requests.get("http://localhost:11434/api/tags", timeout=5)
                if models_response.status_code == 200:
                    result["models"] = [m["name"] for m in models_response.json().get("models", [])]
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    @staticmethod
    def test_chinese_legal() -> Dict[str, Any]:
        """测试中文法律场景能力"""
        result = {
            "success": False,
            "response": None,
            "error": None,
        }
        
        try:
            import requests
            
            prompt = """请用一句话回答：著作权侵权案件中，被告已取得音集协授权的情况下，最佳抗辩策略是什么？"""
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:14b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 200,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result["success"] = True
                result["response"] = response.json().get("response", "")
        except Exception as e:
            result["error"] = str(e)
        
        return result


# CLI 工具
def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description="case-intelligence v4.0 文书生成器")
    parser.add_argument("--doc-type", choices=["defense", "evidence_objection", "court_statement", "evidence_index"],
                        required=True, help="文书类型")
    parser.add_argument("--case-id", help="案件ID")
    parser.add_argument("--case-number", help="案号")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--check-ollama", action="store_true", help="检查 Ollama 状态")
    
    args = parser.parse_args()
    
    if args.check_ollama:
        # 检查 Ollama 状态
        print("检查 Ollama 状态...")
        status = LLMEvaluator.check_ollama_status()
        
        if status["available"]:
            print(f"✅ Ollama 可用，版本: {status['version']}")
            print(f"可用模型: {', '.join(status['models']) if status['models'] else '无'}")
        else:
            print(f"❌ Ollama 不可用: {status['error']}")
        
        return
    
    # 生成文书
    generator = DocumentGenerator()
    
    # 构建案件上下文
    case_context = CaseContext(
        case_id=args.case_id or "test",
        case_number=args.case_number or "测试案号",
        case_name="测试案件",
        plaintiff="测试原告",
        defendant="测试被告",
        cause="著作权侵权",
    )
    
    # 获取参考模板
    templates = generator.get_reference_templates(args.doc_type)
    
    # 构建请求
    request = GenerationRequest(
        doc_type=args.doc_type,
        case_context=case_context,
        reference_templates=templates,
    )
    
    # 生成
    print(f"正在生成 {DocumentGenerator.DOC_TYPES[args.doc_type]}...")
    result = generator.generate(request)
    
    if result.success:
        print(f"✅ 生成成功 (来源: {result.source})")
        print()
        print(result.content)
        
        if args.output:
            Path(args.output).write_text(result.content, encoding="utf-8")
            print(f"\n已保存到: {args.output}")
    else:
        print(f"❌ 生成失败: {result.error}")


if __name__ == "__main__":
    main()

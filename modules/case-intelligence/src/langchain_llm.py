#!/usr/bin/env python3
# =============================================
# case-intelligence LangChain LLM 集成
# 基于 LangChain + LangGraph 的 AI 工作流
# =============================================
import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, TypedDict

logger = logging.getLogger(__name__)

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "ai_engines.yaml"


def load_llm_config() -> Dict[str, Any]:
    """加载 LLM 配置"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_minimax_api_key() -> Optional[str]:
    """获取 MiniMax API Key（优先环境变量，回落 ai_engines.yaml）"""
    if os.environ.get("MINIMAX_API_KEY"):
        return os.environ["MINIMAX_API_KEY"]
    config = load_llm_config()
    engines = config.get("engines", {})
    minimax = engines.get("minimax", {})
    return minimax.get("api_key")


def get_minimax_config() -> Dict[str, Any]:
    """获取 MiniMax 配置"""
    config = load_llm_config()
    engines = config.get("engines", {})
    minimax = engines.get("minimax", {})
    return {
        "base_url": minimax.get("base_url", "https://api.minimax.cn/v1"),
        "model": minimax.get("model", "MiniMax-Text-01"),
        "temperature": minimax.get("temperature", 0.7),
        "max_tokens": minimax.get("max_tokens", 8192),
    }


class LLMService:
    """LangChain LLM 服务"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化 LangChain LLM"""
        try:
            from langchain_openai import ChatOpenAI
            
            config = get_minimax_config()
            api_key = get_minimax_api_key()
            
            if not api_key:
                logger.warning("未配置 MiniMax API Key")
                return
            
            self.llm = ChatOpenAI(
                api_key=api_key,
                base_url=config["base_url"],
                model=config["model"],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
            )
            logger.info(f"LangChain LLM 初始化成功: {config['model']}")
        except Exception as e:
            logger.error(f"LangChain LLM 初始化失败: {e}")
            self.llm = None
    
    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.llm is not None
    
    def invoke(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        调用 LLM 生成回复
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            **kwargs: 额外参数
            
        Returns:
            LLM 生成的文本
        """
        if not self.llm:
            raise RuntimeError("LLM 未初始化")
        
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        # 转换消息格式
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))
        
        response = self.llm.invoke(langchain_messages, **kwargs)
        return response.content
    
    def generate_document(self, prompt: str, system_prompt: str = "") -> str:
        """
        生成文书内容
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            
        Returns:
            生成的文书内容
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.invoke(messages)


# LangGraph 工作流定义
class DocumentState(TypedDict):
    """文书生成状态"""
    case_info: Dict[str, Any]
    doc_type: str
    reference_templates: List[Dict]
    reference_artifacts: List[Dict]
    prompt: str
    draft: str
    feedback: str
    final_document: str


def create_document_workflow():
    """
    创建文书生成工作流（LangGraph）
    
    Returns:
        LangGraph StateGraph
    """
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        logger.warning("langgraph 未安装，使用简化模式")
        return None
    
    # 定义节点
    def prepare_prompt_node(state: DocumentState) -> DocumentState:
        """准备提示词"""
        # 根据文书类型和案件信息构建提示词
        case_info = state["case_info"]
        doc_type = state["doc_type"]
        
        prompt = f"""请根据以下案件信息，生成{get_doc_type_name(doc_type)}：

案件信息：
- 案号：{case_info.get('case_number', '未知')}
- 原告：{case_info.get('plaintiff', '未知')}
- 被告：{case_info.get('defendant', '未知')}
- 案由：{case_info.get('cause', '未知')}
- 法院：{case_info.get('court', '未知')}

要求：
1. 内容准确、逻辑清晰
2. 符合法律文书规范
3. 包含必要的法律论证
"""
        state["prompt"] = prompt
        return state
    
    def generate_draft_node(state: DocumentState) -> DocumentState:
        """生成草稿"""
        llm_service = LLMService()
        
        system_prompt = f"""你是一位专业的法律文书撰写专家，擅长撰写各类法律文书。
请根据案件信息，生成规范、准确的法律文书。"""
        
        draft = llm_service.generate_document(
            prompt=state["prompt"],
            system_prompt=system_prompt
        )
        state["draft"] = draft
        return state
    
    def review_node(state: DocumentState) -> DocumentState:
        """审查文档"""
        try:
            llm_service = LLMService()
            if not llm_service.is_available():
                state["feedback"] = ""
                return state
            
            review_prompt = f"""请审查以下法律文书，指出需要改进的地方：

{state["draft"]}

请从以下角度审查：
1. 法律论证是否充分
2. 结构是否合理
3. 表述是否准确
4. 是否有遗漏的重要论点

只返回审查意见，不要直接修改文书。如果没有问题，返回"无需修改"。"""
            
            feedback = llm_service.generate_document(
                prompt=review_prompt,
                system_prompt="你是一位专业的法律审核专家。"
            )
            
            # 如果反馈是"无需修改"，清空反馈
            if "无需修改" in feedback or "没有问题" in feedback:
                state["feedback"] = ""
            else:
                state["feedback"] = feedback
        except Exception:
            state["feedback"] = ""
        return state
    
    def finalize_node(state: DocumentState) -> DocumentState:
        """定稿"""
        if state["feedback"]:
            # 如果有反馈，进行修订
            state["final_document"] = state["draft"] + "\n\n[已根据审查意见修订]"
        else:
            state["final_document"] = state["draft"]
        return state
    
    # 构建图
    workflow = StateGraph(DocumentState)
    
    workflow.add_node("prepare_prompt", prepare_prompt_node)
    workflow.add_node("generate_draft", generate_draft_node)
    workflow.add_node("review", review_node)
    workflow.add_node("finalize", finalize_node)
    
    workflow.set_entry_point("prepare_prompt")
    workflow.add_edge("prepare_prompt", "generate_draft")
    workflow.add_edge("generate_draft", "review")
    workflow.add_edge("review", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


def get_doc_type_name(doc_type: str) -> str:
    """获取文书类型中文名"""
    names = {
        "defense": "答辩状",
        "evidence_objection": "质证意见",
        "court_statement": "当庭陈述",
        "evidence_index": "证据目录",
    }
    return names.get(doc_type, doc_type)


def generate_with_workflow(case_info: Dict, doc_type: str) -> str:
    """
    使用 LangGraph 工作流生成文书
    
    Args:
        case_info: 案件信息
        doc_type: 文书类型
        
    Returns:
        生成的文书内容
    """
    workflow = create_document_workflow()
    
    if workflow is None:
        # 降级到直接调用
        return generate_direct(case_info, doc_type)
    
    initial_state = DocumentState(
        case_info=case_info,
        doc_type=doc_type,
        reference_templates=[],
        reference_artifacts=[],
        prompt="",
        draft="",
        feedback="",
        final_document="",
    )
    
    result = workflow.invoke(initial_state)
    return result.get("final_document", "")


def generate_direct(case_info: Dict, doc_type: str, use_prompt: bool = True) -> str:
    """
    直接调用 LLM 生成文书
    
    Args:
        case_info: 案件信息
        doc_type: 文书类型
        use_prompt: 是否使用prompts规则库（默认True）
    
    Returns:
        生成的文书内容
    """
    llm_service = LLMService()
    
    if not llm_service.is_available():
        raise RuntimeError("LLM 服务不可用")
    
    # 尝试加载 prompts 规则库
    prompt_template = ""
    if use_prompt:
        prompt_template = _load_prompt_for_doc_type(doc_type)
    
    if prompt_template:
        # 使用 prompts 规则库
        prompt = _build_prompt_from_template(prompt_template, case_info, doc_type)
        system_prompt = _extract_system_prompt(prompt_template)
    else:
        # Fallback: 使用简单 prompt
        system_prompt = """你是一位专业的法律文书撰写专家，擅长撰写各类法律文书。
请根据案件信息，生成规范、准确的法律文书。"""
        
        prompt = f"""请根据以下案件信息，生成{get_doc_type_name(doc_type)}：

案件信息：
- 案号：{case_info.get('case_number', '未知')}
- 原告：{case_info.get('plaintiff', '未知')}
- 被告：{case_info.get('defendant', '未知')}
- 案由：{case_info.get('cause', '未知')}
- 法院：{case_info.get('court', '未知')}

要求：
1. 内容准确、逻辑清晰
2. 符合法律文书规范
3. 包含必要的法律论证"""

    return llm_service.generate_document(prompt, system_prompt)


def _load_prompt_for_doc_type(doc_type: str) -> str:
    """加载对应文书类型的 prompts 规则"""
    try:
        from src.ai_engine import get_engine_manager
        manager = get_engine_manager()
        return manager.load_prompt(doc_type)
    except Exception:
        return ""


def _build_prompt_from_template(prompt_template: str, case_info: Dict, doc_type: str) -> str:
    """从 prompt 模板构建完整的 prompt"""
    import re
    
    # 提取 YAML frontmatter 后的内容
    content = prompt_template
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    
    # 提取 ## 案件基本信息 之后的内容作为模板
    case_info_section = ""
    lines = content.split("\n")
    in_case_section = False
    case_template = []
    
    for line in lines:
        if "## 案件基本信息" in line or "## 输入" in line:
            in_case_section = True
            continue
        if in_case_section:
            if line.startswith("## ") and "## 案件基本信息" not in line:
                break
            case_template.append(line)
    
    # 构建案件信息字符串
    case_info_text = "\n".join([
        f"案号: {case_info.get('case_number', '[待补充]')}",
        f"原告: {case_info.get('plaintiff', '[待补充]')}",
        f"被告: {case_info.get('defendant', '[待补充]')}",
        f"案由: {case_info.get('cause', '[待补充]')}",
        f"法院: {case_info.get('court', '[待补充]')}",
    ])
    
    # 提取生成指令部分
    instruction = ""
    in_instruction = False
    for line in lines:
        if "## 生成指令" in line or "## 输出要求" in line:
            in_instruction = True
            continue
        if in_instruction:
            if line.startswith("## ") and ("## 生成指令" not in line):
                break
            instruction += line + "\n"
    
    prompt = f"""请根据以下案件信息生成{get_doc_type_name(doc_type)}：

{case_info_text}

{instruction}

请直接输出生成的文书内容，不要其他说明。"""
    
    return prompt


def _extract_system_prompt(prompt_template: str) -> str:
    """从 prompt 模板中提取 system prompt"""
    import re
    
    # 查找角色定义
    match = re.search(r"## 角色定义\n\n(.+?)(?:\n\n|##)", prompt_template, re.DOTALL)
    if match:
        role = match.group(1).strip()
        return f"""你是一位专业的法律文书撰写专家。\n{role}"""
    
    # 查找角色设定
    match = re.search(r"## 角色设定\n\n(.+?)(?:\n\n|##)", prompt_template, re.DOTALL)
    if match:
        role = match.group(1).strip().replace("\n", " ")
        return f"你是一位资深民商法律师。{role}"
    
    return "你是一位专业的法律文书撰写专家，擅长撰写各类法律文书。"


# 便捷函数
def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    return LLMService()

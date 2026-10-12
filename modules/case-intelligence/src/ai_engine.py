# =============================================
# case-intelligence AI 引擎层
# 支持 Ollama / OpenAI / Anthropic 多引擎
# =============================================
import os
import json
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "ai_engines.yaml"


@dataclass
class EngineConfig:
    """引擎配置"""
    enabled: bool
    base_url: Optional[str] = None
    model: str = "gpt-4o"
    timeout: int = 60
    max_tokens: int = 4096
    temperature: float = 0.7
    retry: int = 3
    retry_delay: int = 2
    api_key: Optional[str] = None
    use_cases: list = None  # 适用场景列表
    pros: list = None  # 优点
    cons: list = None  # 缺点
    
    def __post_init__(self):
        if self.use_cases is None:
            self.use_cases = []
        if self.pros is None:
            self.pros = []
        if self.cons is None:
            self.cons = []


class AIEngine:
    """AI 引擎基类"""
    
    def __init__(self, config: EngineConfig):
        self.config = config
    
    def chat(self, messages: list, **kwargs) -> str:
        """发送聊天请求"""
        raise NotImplementedError
    
    def load_prompt(self, prompt_path: str) -> str:
        """加载提示词文件"""
        full_path = PROJECT_ROOT / prompt_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        logger.warning(f"提示词文件不存在: {prompt_path}")
        return ""


class OllamaEngine(AIEngine):
    """Ollama 本地模型引擎"""
    
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self.model = config.model
        self.timeout = config.timeout
    
    def chat(self, messages: list, **kwargs) -> str:
        """发送聊天请求到 Ollama"""
        import requests
        
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            }
        }
        
        for attempt in range(self.config.retry):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "")
            except Exception as e:
                logger.warning(f"Ollama 请求失败 (尝试 {attempt + 1}/{self.config.retry}): {e}")
                if attempt < self.config.retry - 1:
                    import time
                    time.sleep(self.config.retry_delay)
        
        raise RuntimeError(f"Ollama 请求失败，已重试 {self.config.retry} 次")


class OpenAIEngine(AIEngine):
    """OpenAI API 引擎"""
    
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.model = config.model
        self.timeout = config.timeout
    
    def chat(self, messages: list, **kwargs) -> str:
        """发送聊天请求到 OpenAI"""
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        
        for attempt in range(self.config.retry):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=kwargs.get("temperature", self.config.temperature),
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"OpenAI 请求失败 (尝试 {attempt + 1}/{self.config.retry}): {e}")
                if attempt < self.config.retry - 1:
                    import time
                    time.sleep(self.config.retry_delay)
        
        raise RuntimeError(f"OpenAI 请求失败，已重试 {self.config.retry} 次")


class MiniMaxEngine(AIEngine):
    """MiniMax API 引擎（OpenAI 兼容接口）"""
    
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = config.base_url or "https://api.minimax.cn/v1"
        self.model = config.model or "MiniMax-Text-01"
        self.timeout = config.timeout
    
    def chat(self, messages: list, **kwargs) -> str:
        """发送聊天请求到 MiniMax"""
        import requests
        
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        
        for attempt in range(self.config.retry):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                response.raise_for_status()
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            except Exception as e:
                logger.warning(f"MiniMax 请求失败 (尝试 {attempt + 1}/{self.config.retry}): {e}")
                if attempt < self.config.retry - 1:
                    import time
                    time.sleep(self.config.retry_delay)
        
        raise RuntimeError(f"MiniMax 请求失败，已重试 {self.config.retry} 次")


class AIEngineManager:
    """AI 引擎管理器"""
    
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
        self.config = self._load_config()
        self.engines: Dict[str, AIEngine] = {}
        self._init_engines()
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {"engines": {}, "default_engine": "ollama"}
    
    def _init_engines(self):
        """初始化引擎"""
        engines_config = self.config.get("engines", {})
        
        # Ollama
        if engines_config.get("ollama", {}).get("enabled"):
            self.engines["ollama"] = OllamaEngine(
                EngineConfig(**engines_config["ollama"])
            )
        
        # OpenAI
        if engines_config.get("openai", {}).get("enabled"):
            self.engines["openai"] = OpenAIEngine(
                EngineConfig(**engines_config["openai"])
            )
    
    def get_engine(self, name: Optional[str] = None) -> Optional[AIEngine]:
        """获取引擎"""
        if name is None:
            name = self.config.get("default_engine", "ollama")
        return self.engines.get(name)
    
    def chat(self, prompt: str, engine: Optional[str] = None, **kwargs) -> str:
        """发送聊天请求"""
        ai_engine = self.get_engine(engine)
        if ai_engine is None:
            raise RuntimeError(f"引擎 {engine} 不可用")
        
        messages = [{"role": "user", "content": prompt}]
        return ai_engine.chat(messages, **kwargs)
    
    def get_prompt_path(self, prompt_key: str) -> str:
        """获取提示词文件路径"""
        prompts_config = self.config.get("prompts", {})
        for category in ["extraction", "matching", "generation"]:
            if category in prompts_config:
                if prompt_key in prompts_config[category]:
                    return prompts_config[category][prompt_key]
        return ""
    
    def load_prompt(self, prompt_key: str) -> str:
        """加载提示词文件"""
        path = self.get_prompt_path(prompt_key)
        if path:
            full_path = PROJECT_ROOT / path
            if full_path.exists():
                return full_path.read_text(encoding="utf-8")
        return ""


# 全局实例
_engine_manager = None

def get_engine_manager() -> AIEngineManager:
    """获取引擎管理器单例"""
    global _engine_manager
    if _engine_manager is None:
        _engine_manager = AIEngineManager()
    return _engine_manager


def chat_with_ai(prompt: str, engine: Optional[str] = None, **kwargs) -> str:
    """快捷函数：发送聊天请求"""
    return get_engine_manager().chat(prompt, engine, **kwargs)

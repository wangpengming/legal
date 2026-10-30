#!/usr/bin/env python3
# =============================================
# lark_llm.py - 飞书 Bot 的 LLM 客户端（A 兜底意图 / B ReAct agent 共用）
#
# 定位：把「调云端 LLM」收敛成一个小契约 —— messages 进、str/JSON 出。
#   - 引擎复用 `ai_engine.AIEngineManager`（默认 minimax：OpenAI 兼容，见 ai_engines.yaml）
#   - 🔴 失败一律**返回 None 不抛**：Bot 主链路必须能降级到规则路由 / 引导卡
#   - 可注入 fake engine → 单测纯 stdlib、无需 MINIMAX_API_KEY / 不出网
#
# 见 docs/SPEC-feishu-bot.md §5.4。
# =============================================
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_ENGINE = "minimax"
# 🔴 推理模型（MiniMax M3.1-Flash）会先产出 reasoning_content 再给正文；
# 上限太小会让**正文被推理段吃光**（实测 800 → content 空、finish_reason=length），
# 表现为「空响应」→ 静默降级为无解读的证据清单。故留足推理 + 正文余量。
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.2
_JSON_FENCE_RE = re.compile(r"\{.*\}", re.S)


def strip_json_fence(text: str) -> str:
    """去掉 ```json ... ``` 围栏，返回纯文本（与 extractor 同口径）。"""
    t = (text or "").strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()


def parse_json_object(text: str) -> Optional[dict]:
    """从 LLM 输出里抠出一个 JSON 对象；失败返回 None（不抛）。"""
    t = strip_json_fence(text)
    if not t:
        return None
    candidates = [t]
    m = _JSON_FENCE_RE.search(t)
    if m:
        candidates.append(m.group(0))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


class LLMClient:
    """LLM 调用薄封装：可用性探测 + 失败降级 + JSON 解析。"""

    def __init__(
        self,
        engine=None,
        engine_name: Optional[str] = None,
        *,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enabled: bool = True,
    ):
        self.engine_name = engine_name or os.environ.get("LARK_LLM_ENGINE") or DEFAULT_ENGINE
        self._engine = engine
        self.max_tokens = int(max_tokens or os.environ.get("LARK_LLM_MAX_TOKENS") or DEFAULT_MAX_TOKENS)
        self.temperature = float(
            temperature if temperature is not None else os.environ.get("LARK_LLM_TEMPERATURE") or DEFAULT_TEMPERATURE
        )
        self.enabled = enabled and os.environ.get("LARK_LLM_ENABLED", "1") not in ("0", "false", "False")
        self.last_error = ""

    # ---------- 引擎解析 ----------

    def _resolve(self):
        """惰性解析引擎（注入优先）；失败缓存 None，避免每轮重试。"""
        if self._engine is not None:
            return self._engine
        try:
            from .ai_engine import get_engine_manager
            self._engine = get_engine_manager().get_engine(self.engine_name)
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 引擎初始化失败（%s）：%s", self.engine_name, e)
            self.last_error = str(e)
            self._engine = None
        return self._engine

    def available(self) -> bool:
        """引擎可解析且未禁用——调度方据此决定是否走 LLM 兜底。"""
        return bool(self.enabled and self._resolve() is not None)

    # ---------- 调用 ----------

    def chat(self, messages: list, *, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> Optional[str]:
        """messages → 文本；任何失败（无引擎 / 网络 / 空响应）返回 None。"""
        if not self.enabled:
            self.last_error = "LLM 已禁用"
            return None
        engine = self._resolve()
        if engine is None:
            self.last_error = self.last_error or f"引擎不可用: {self.engine_name}"
            return None
        try:
            out = engine.chat(
                list(messages),
                max_tokens=max_tokens or self.max_tokens,
                temperature=self.temperature if temperature is None else temperature,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 调用失败：%s", e)
            self.last_error = str(e)
            return None
        text = (out or "").strip()
        if not text:
            self.last_error = "空响应"
            return None
        self.last_error = ""
        return text

    def chat_json(self, messages: list, **kwargs) -> Optional[dict]:
        """messages → JSON 对象；非 JSON 或失败返回 None。"""
        text = self.chat(messages, **kwargs)
        if not text:
            return None
        obj = parse_json_object(text)
        if obj is None:
            self.last_error = "非 JSON 响应"
        return obj


__all__ = ["LLMClient", "parse_json_object", "strip_json_fence", "DEFAULT_ENGINE"]
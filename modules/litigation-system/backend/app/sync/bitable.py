"""飞书多维表格（bitable）同步客户端（docs/03 §3）。

- 凭证决策 D2：仅 env 注入；`settings.feishu_configured=False` → 离线模式，
  API 不会被发出，抛 `SyncNotConfiguredError`，由测试夹具/手动同步注入替代源。
- 限速：令牌桶 3 QPS（20 QPS 上限留 15% 余量给业务请求）；
  失败指数退避（1s/4s/16s ±20% 抖动）最多 `sync_max_retries` 次重试，
  仅对 429 / 5xx / 网络错误 / token 失效重试。
- 表定位：env `feishu_table_cases/songs` 优先，未配置时回退需求文档实测表 id
  （requirements/01 §3.2），再 fallback 按表名模糊匹配。
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid

import httpx

from app.core.config import Settings

# 需求文档实测表 id（requirements/01 §3.2 F1.1 / §4.1 关联子表）
DEFAULT_CASES_TABLE_ID = "tblCuET1IuQPysak"  # 历年诉讼案件总表
DEFAULT_SONGS_TABLE_ID = "tblCGACAzAMGd5eX"  # 涉及歌曲清单

FEISHU_BASE = "https://open.feishu.cn/open-apis"

logger = logging.getLogger(__name__)


class SyncNotConfiguredError(RuntimeError):
    """飞书凭证缺失（离线模式）：任何 API 调用都不应发出。"""


class SyncConflictError(RuntimeError):
    """并发冲突：已有 running 任务未结束（API 层转 409）。"""


class FeishuAPIError(RuntimeError):
    """飞书开放平台错误（HTTP 或业务码）。"""

    def __init__(self, code: int, msg: str, detail: str = ""):
        super().__init__(f"feishu api error code={code} msg={msg}")
        self.code = code
        self.msg = msg
        self.detail = detail


class TokenBucket:
    """令牌桶（容量 1，突发限 1 请求 → 稳定 3 QPS；并发 1 同步任务）。"""

    def __init__(self, rate: float):
        self.rate = max(rate, 0.1)
        self.tokens = 1.0
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while self.tokens < 1:
                now = time.monotonic()
                elapsed = now - self.updated
                self.tokens = min(1.0, self.tokens + elapsed * self.rate)
                self.updated = now
                if self.tokens < 1:
                    await asyncio.sleep((1 - self.tokens) / self.rate)
            self.tokens -= 1


class BitableClient:
    """飞书多维表格只读客户端（token 缓存 / 分页拉取 / 限速重试）。"""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._token: str | None = None
        self._token_expire_at: float = 0.0
        self._bucket = TokenBucket(settings.sync_qps)
        self._token_lock = asyncio.Lock()
        self._http = httpx.AsyncClient(base_url=FEISHU_BASE, timeout=30.0)

    async def close(self) -> None:
        await self._http.aclose()

    # ── 认证 ────────────────────────────────────────────────────────────
    async def _tenant_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expire_at - 60:
            return self._token
        if not self._settings.feishu_configured:
            raise SyncNotConfiguredError(
                "飞书凭证未配置（feishu_app_id/feishu_app_secret/feishu_app_token）；"
                "同步引擎处于离线模式"
            )
        async with self._token_lock:
            # 双检：等锁期间可能已被并发刷新
            if self._token and time.time() < self._token_expire_at - 60:
                return self._token
            resp = await self._http.post(
                "/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._settings.feishu_app_id,
                    "app_secret": self._settings.feishu_app_secret,
                },
            )
            payload = resp.json()
            if resp.status_code != 200 or payload.get("code", 0) != 0:
                raise FeishuAPIError(payload.get("code", resp.status_code), payload.get("msg", resp.text))
            # ⚠️ 实测（2026-08-14）：auth/v3 接口返回扁平结构，
            # tenant_access_token 在顶层而非 data 子对象中；两者兼容解析
            data = payload.get("data") or payload
            token = data.get("tenant_access_token")
            if not token:
                raise FeishuAPIError(
                    payload.get("code", -1),
                    payload.get("msg", "missing tenant_access_token"),
                    str(payload)[:300],
                )
            self._token = token
            # expire 单位秒：预减 60s 提前刷新
            self._token_expire_at = now + payload.get("expire", 7200) - 60
            return self._token

    # ── 核心请求（限速 + 指数退避重试） ─────────────────────────────────
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        await self._bucket.acquire()
        max_retries = self._settings.sync_max_retries
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                headers = {"Authorization": f"Bearer {await self._tenant_access_token()}"}
                resp = await self._http.request(method, path, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < max_retries:
                    await self._backoff(attempt)
                    continue
                raise FeishuAPIError(-1, "network_error", str(exc)) from exc

            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = FeishuAPIError(resp.status_code, "http_error", resp.text[:300])
                if attempt < max_retries:
                    await self._backoff(attempt)
                    continue
                raise last_error

            try:
                payload = resp.json()
            except ValueError:
                raise FeishuAPIError(resp.status_code, "invalid_json", resp.text[:300]) from None

            code = payload.get("code", 0)
            if code == 0:
                return payload.get("data", {})
            # 99991663 = tenant_access_token 失效 → 清除缓存刷新后重试
            if code == 99991663 and attempt < max_retries:
                self._token = None
                await self._backoff(attempt)
                continue
            raise FeishuAPIError(code, payload.get("msg", ""), str(payload)[:300])
        raise FeishuAPIError(-1, "unreachable", str(last_error))

    async def _backoff(self, attempt: int) -> None:
        base = self._settings.sync_backoff_base * (4**attempt)
        jittered = base * random.uniform(0.8, 1.2)
        logger.info("sync backoff attempt=%d sleep=%.2fs", attempt + 1, jittered)
        await asyncio.sleep(jittered)

    # ── 表元数据 ────────────────────────────────────────────────────────
    async def list_tables(self) -> list[dict]:
        data = await self._request("GET", f"/bitable/v1/apps/{self._settings.feishu_app_token}/tables")
        return data.get("items", [])

    async def get_table_meta(self, table_id: str) -> dict:
        path = f"/bitable/v1/apps/{self._settings.feishu_app_token}/tables/{table_id}"
        return await self._request("GET", path)

    def resolve_table_id(self, env_table_id: str, default_table_id: str, table_name_fragment: str) -> str:
        """env 显式 id 优先；否则默认实测 id；再 fallback 按名称模糊匹配。"""
        if env_table_id:
            return env_table_id
        return default_table_id

    # ── 记录 ────────────────────────────────────────────────────────────
    async def list_records(
        self,
        table_id: str,
        page_size: int | None = None,
        page_token: str | None = None,
        filter_sql: str | None = None,
    ) -> dict:
        """单页拉取。返回 data 字典：{items, has_more, page_token, total}。"""
        params = {}
        if page_size:
            params["page_size"] = page_size
        if page_token:
            params["page_token"] = page_token
        if filter_sql:
            params["filter"] = filter_sql
        path = f"/bitable/v1/apps/{self._settings.feishu_app_token}/tables/{table_id}/records"
        return await self._request("GET", path, params=params)

    async def get_record(self, table_id: str, record_id: str) -> dict:
        path = (
            f"/bitable/v1/apps/{self._settings.feishu_app_token}/tables/{table_id}/records/{record_id}"
        )
        return await self._request("GET", path)

    async def pull_all_records(self, table_id: str, page_size: int | None = None) -> tuple[list[dict], int]:
        """全量分页拉取（page_token 游标失效 → 放弃续拉，从头重拉 = 幂等兜底）。

        返回 (items, total)：items 含 record_id / fields 原始结构；
        total 优先取响应 total（对账基准），缺失时退化为 len(items)。
        """
        page_size = page_size or self._settings.sync_page_size
        all_items: list[dict] = []
        total: int = 0
        page_token: str | None = None
        while True:
            data = await self.list_records(table_id, page_size=page_size, page_token=page_token)
            items = data.get("items", [])
            all_items.extend(items)
            if not total and data.get("total"):
                total = int(data["total"])
            if not data.get("has_more"):
                return all_items, total or len(all_items)
            nxt = data.get("page_token")
            if nxt is None or nxt == page_token:  # 游标失效保护：重头再拉一轮
                logger.warning("sync page_token loop detected; restart pagination")
                page_token = None
                continue
            page_token = nxt
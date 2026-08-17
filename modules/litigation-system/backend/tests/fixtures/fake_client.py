"""FakeBitableClient（t08-3 夹具）：离线注入替代真实飞书客户端。

与 BitableClient 同构（list_records 分页 + pull_all_records 游标循环），
便于验证引擎的分页路径；提供 mutate() 模拟远端数据变更（幂等/变更检测用）。
"""
from __future__ import annotations

from app.sync.bitable import DEFAULT_CASES_TABLE_ID, DEFAULT_SONGS_TABLE_ID


class FakeBitableClient:
    def __init__(self, cases: list[dict], songs: list[dict], default_page_size: int = 2):
        self._cases = list(cases)
        self._songs = list(songs)
        self.default_page_size = default_page_size
        self.pull_calls: list[tuple[str, int | None]] = []  # (table_id, page_size)
        self.page_requests: list[tuple[str, int | None, str | None]] = []  # (table_id, page_size, page_token)

    # ── 与 BitableClient 对齐的接口 ────────────────────────────────────
    def resolve_table_id(self, env_table_id: str, default_table_id: str, _name_fragment: str) -> str:
        return env_table_id or default_table_id

    async def list_records(self, table_id: str, page_size: int | None = None, page_token: str | None = None, filter_sql: str | None = None) -> dict:
        self.page_requests.append((table_id, page_size, page_token))
        items = self._cases if table_id == DEFAULT_CASES_TABLE_ID else self._songs
        ps = page_size or self.default_page_size
        start = 0
        if page_token:
            try:
                start = int(page_token.rsplit("-", 1)[1])
            except (ValueError, IndexError):
                start = 0
        chunk = items[start : start + ps]
        has_more = start + ps < len(items)
        return {
            "items": chunk,
            "has_more": has_more,
            "page_token": f"tok-{start + ps}" if has_more else None,
            "total": len(items) if start == 0 else None,  # 飞书行为：total 仅首页返回
        }

    async def pull_all_records(self, table_id: str, page_size: int | None = None) -> tuple[list[dict], int]:
        self.pull_calls.append((table_id, page_size))
        all_items: list[dict] = []
        total = 0
        page_token: str | None = None
        while True:
            data = await self.list_records(table_id, page_size=page_size, page_token=page_token)
            all_items.extend(data.get("items", []))
            if not total and data.get("total"):
                total = int(data["total"])
            if not data.get("has_more"):
                return all_items, total or len(all_items)
            page_token = data.get("page_token")
            if page_token is None:  # 游标失效保护（与 BitableClient 一致）
                break
        return all_items, total or len(all_items)

    async def get_record(self, table_id: str, record_id: str) -> dict:
        items = self._cases if table_id == DEFAULT_CASES_TABLE_ID else self._songs
        for rec in items:
            if rec.get("record_id") == record_id:
                return {"record": rec}
        return {"record": {}}

    # ── 测试辅助 ───────────────────────────────────────────────────────
    def mutate(self, record_id: str, field: str, value) -> None:
        """模拟远端某记录字段变更（变更检测断言用）。"""
        for rec in self._cases:
            if rec.get("record_id") == record_id:
                rec.setdefault("fields", {})[field] = value
                return
        raise KeyError(f"record {record_id} not found")
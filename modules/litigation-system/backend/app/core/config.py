"""应用配置。

决策 D2：飞书凭证 / APP_TOKEN 仅通过环境变量注入（或项目根 .env），
绝不写入代码库与文档。docs/01 仅保存非密元数据（App ID、Base Token、表 ID）。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[3] = 仓库根（litigation-system/）
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 飞书凭证（决策 D2：仅 env；空值 → 同步引擎处于「离线模式」，测试用夹具） ──
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_app_token: str = ""  # Base App Token（bascn...）
    feishu_table_cases: str = ""  # 案件表 table_id
    feishu_table_songs: str = ""  # 歌曲表 table_id

    # ── API 认证（docs/03 §6.1：单用户 Token；未配置 APP_TOKEN 时不启用鉴权） ──
    app_token: str = ""

    # ── 数据库（SQLite WAL 单文件，位于仓库根 data/ 卷外保存） ──
    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"

    # ── 同步引擎（docs/03 §3.3：20 QPS 上限留 15% 余量 → 令牌桶 3 QPS） ──
    sync_qps: float = 3.0
    sync_page_size: int = 100
    sync_max_retries: int = 3
    sync_backoff_base: float = 1.0  # 指数退避 1s/4s/16s（±20% 抖动）

    # ── 调度（与 10-sync 页 cron 一致；字符串 cron 表达式，可被 env 覆盖） ──
    cron_incremental: str = "0 3 * * *"  # 每日 03:00 增量同步
    cron_clean: str = "0 3 * * *"  # 03:00 清洗管道全量重跑（紧随增量）
    cron_metrics: str = "40 3 * * *"  # 03:40 指标重算 + 报表刷新
    cron_casebase: str = "0 22 * * 1"  # 每周一 22:00 案例库快照（Phase 2 接入）

    # ── 检索（容量兜底：FTS5 上限 10 万行） ──
    search_default_page_size: int = 20

    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    @property
    def feishu_configured(self) -> bool:
        """凭证齐备才允许访问飞书；否则同步引擎走离线/夹具模式。"""
        return all([self.feishu_app_id, self.feishu_app_secret, self.feishu_app_token])


@lru_cache
def get_settings() -> Settings:
    return Settings()
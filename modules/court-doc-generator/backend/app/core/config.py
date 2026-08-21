"""应用配置（参考 litigation-system 模式）。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = True

    # 路径（向上四级到模块根：backend/app/core/config.py → court-doc-generator/）
    MODULE_ROOT: Path = Path(__file__).parent.parent.parent.parent
    DATA_DIR: Path = MODULE_ROOT / "data"
    WORKSPACES_DIR: Path = DATA_DIR / "workspaces"
    STATIC_DIR: Path = MODULE_ROOT / "static"
    TEMPLATES_DIR: Path = MODULE_ROOT / "templates"
    OUTPUTS_DIR: Path = MODULE_ROOT / "outputs"

    # CORS（开发时全开）
    CORS_ORIGINS: list[str] = ["http://localhost:18502", "http://localhost:3000"]

    @property
    def workspaces_dir(self) -> Path:
        self.WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        return self.WORKSPACES_DIR


settings = Settings()

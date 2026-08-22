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
    CORS_ORIGINS: list[str] = ["http://localhost:18502", "http://localhost:3000"]

    # 派生路径必须用 property：pydantic 字段默认值在类定义时求值，
    # 若写成 `X: Path = DATA_DIR / "x"`，DATA_DIR 被环境变量覆盖后 X 仍指向旧目录
    #（2026-08-22 事故：pytest 隔离 DATA_DIR 后业务库仍写入生产 data/workspaces）
    @property
    def WORKSPACES_DIR(self) -> Path:
        return self.DATA_DIR / "workspaces"

    @property
    def STATIC_DIR(self) -> Path:
        return self.MODULE_ROOT / "static"

    @property
    def FRONTEND_DIST_DIR(self) -> Path:
        """前端 build 产物目录（生产形态由后端统一托管）。"""
        return self.MODULE_ROOT / "frontend" / "dist"

    @property
    def TEMPLATES_DIR(self) -> Path:
        return self.MODULE_ROOT / "templates"

    @property
    def OUTPUTS_DIR(self) -> Path:
        return self.MODULE_ROOT / "outputs"

    @property
    def workspaces_dir(self) -> Path:
        self.WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        return self.WORKSPACES_DIR


settings = Settings()

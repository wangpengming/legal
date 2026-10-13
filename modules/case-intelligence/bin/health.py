#!/usr/bin/env python3
# =============================================
# case-intelligence 健康检查（轻量 /health 探针）
# 输出 JSON：模块版本 + UI 健康（Streamlit /_stcore/health）+ DB 统计
# 退出码：0 = 健康 / 1 = 异常
# 用途：portal 子系统健康轮询 / 运维探测 / CI 冒烟检查
# 说明：本模块为 CLI + Streamlit 形态，HTTP 健康端点由 Streamlit 内置
#       提供（GET /_stcore/health → 200 ok）；本脚本在此之上补充版本与
#       数据库维度，供无 HTTP 依赖的集成方使用。
# =============================================
import json
import os
import socket
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULE_NAME = "case-intelligence"
UI_PORTS = [18503, 18504]
UI_HEALTH_PATH = "/_stcore/health"
# 与 src/database.py 一致：DATA_DIR 可覆盖（部署时指向卷挂载点）
DATA_DIR = Path(os.environ.get("DATA_DIR") or PROJECT_ROOT / "data")


def _module_version() -> str:
    try:
        text = (PROJECT_ROOT / "module.yaml").read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    for line in text.splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("localhost", port)) == 0


def _ui_health() -> dict:
    for port in UI_PORTS:
        if not _port_listening(port):
            continue
        result = {
            "running": True,
            "port": port,
            "endpoint": UI_HEALTH_PATH,
            "http_status": None,
            "ok": False,
        }
        try:
            resp = urllib.request.urlopen(
                f"http://localhost:{port}{UI_HEALTH_PATH}", timeout=3
            )
            result["http_status"] = resp.status
            result["ok"] = resp.status == 200
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        return result
    return {"running": False, "port": None, "endpoint": UI_HEALTH_PATH, "ok": False}


def _db_health() -> dict:
    db_file = DATA_DIR / "case_registry.db"
    if not db_file.exists():
        # 只读探针：不因健康检查而创建数据库
        return {"ok": True, "initialized": False, "note": "数据库尚未创建"}
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        import database  # noqa: WPS433
        return {"ok": True, "initialized": True, **database.get_summary()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def collect_health() -> dict:
    ui = _ui_health()
    db = _db_health()
    return {
        "status": "ok" if db["ok"] else "error",
        "module": MODULE_NAME,
        "version": _module_version(),
        "ui": ui,
        "db": db,
    }


def main() -> int:
    health = collect_health()
    print(json.dumps(health, ensure_ascii=False, indent=2))
    return 0 if health["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
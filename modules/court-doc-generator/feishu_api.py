"""飞书集成接口（MVP 预留）。

设计原则：
1. MVP 阶段不依赖飞书 SDK，使用纯 HTTP 调用 + lark-mcp。
2. 提供异步/同步两套接口骨架，供后续扩展。
3. 配置文件 feishu_config.json 缺失时全部接口降级为 no-op。

未来扩展方向：
- 案件信息同步至飞书多维表格（lark-base）
- 生成文件上传至飞书云盘（lark-drive）
- 飞书审批流触发（lark-approval）
- 在线协作生成（部门同事可在线调用）
"""
import json
from pathlib import Path
from typing import Optional

from .config import CONFIG_DIR


FEISHU_CONFIG_PATH = CONFIG_DIR / "feishu_config.json"


def load_feishu_config() -> dict:
    """加载飞书配置（app_id, app_secret, base_token 等）。"""
    if not FEISHU_CONFIG_PATH.exists():
        return {"enabled": False}
    try:
        with open(FEISHU_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"enabled": False}


def is_feishu_enabled() -> bool:
    """检查飞书集成是否已启用。"""
    cfg = load_feishu_config()
    return bool(cfg.get("enabled")) and bool(cfg.get("app_id"))


# ============================================================
# 案件同步（预留）
# ============================================================

def sync_case_to_bitable(case: dict, company: dict, agent: dict) -> Optional[str]:
    """将案件信息同步到飞书多维表格。

    MVP 状态：占位实现，仅返回 None。可用 lark-mcp 的 bitable_v1_appTableRecord_create 实现。

    返回：飞书记录 ID（成功）/ None（未启用或失败）
    """
    if not is_feishu_enabled():
        return None
    # TODO: 接入 lark-mcp
    # 示例：
    #   from lark_mcp import call_tool
    #   res = call_tool("bitable_v1_appTableRecord_create", {
    #       "app_token": cfg["bitable_app_token"],
    #       "table_id": cfg["bitable_table_id"],
    #       "fields": {
    #           "案号": case["case_number"],
    #           "案由": case["case_cause"],
    #           "法院": case["court"],
    #           ...
    #       }
    #   })
    #   return res["data"]["record"]["record_id"]
    return None


# ============================================================
# 文件上传（预留）
# ============================================================

def upload_files_to_drive(folder_path: str, case_number: str) -> Optional[str]:
    """将生成的文件上传到飞书云盘。

    MVP 状态：占位实现。可用 lark-mcp 的 drive_v1_permissionMember_create + 文件分块上传 API。
    """
    if not is_feishu_enabled():
        return None
    # TODO: 接入 lark-mcp
    return None


# ============================================================
# 飞书通知（预留）
# ============================================================

def notify_via_lark(user_open_id: str, message: str) -> bool:
    """通过飞书 IM 发送消息通知。

    MVP 状态：占位实现。可用 lark-mcp 的 im_v1_message_create。
    """
    if not is_feishu_enabled():
        return False
    # TODO: 接入 lark-mcp
    return False


# ============================================================
# 配置写入辅助
# ============================================================

def save_feishu_config(config: dict) -> None:
    """保存飞书配置（用于未来设置界面）。"""
    with open(FEISHU_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_feishu_status() -> dict:
    """获取飞书集成状态（用于界面展示）。"""
    cfg = load_feishu_config()
    return {
        "enabled": cfg.get("enabled", False),
        "app_id": cfg.get("app_id", ""),
        "bitable_app_token": cfg.get("bitable_app_token", ""),
        "bitable_table_id": cfg.get("bitable_table_id", ""),
        "drive_folder_token": cfg.get("drive_folder_token", ""),
    }

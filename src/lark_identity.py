#!/usr/bin/env python3
# =============================================
# lark_identity.py - 飞书身份 / 角色 / 审计
#
# 角色模型（SPEC-feishu-bot §8）：
#   readonly < writer < generator < admin
#
# 映射来源（后者覆盖前者）：
#   1. 环境变量 LARK_ROLE_MAP   "ou_x:writer,ou_y:admin"
#   2. 环境变量 LARK_DEFAULT_ROLE（白名单外默认角色，缺省 readonly）
#   3. 文件 .run/bot/roles.json {"ou_x": "admin"}（可热改，支持 mtime 热加载）
#
# 状态落 .run/bot/（已 gitignore）——**不得落 data/**，避免误入提交。
# =============================================
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from . import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_DIR = PROJECT_ROOT / ".run" / "bot"

ROLES = ("readonly", "writer", "generator", "admin")
DENY_ROLE = "deny"          # 白名单策略 = deny 时的返回值（层级最低 → 全部拒绝）


def default_roles_path() -> Path:
    return Path(os.environ.get("LARK_STATE_DIR") or DEFAULT_STATE_DIR) / "roles.json"


def _parse_env_map(raw: str) -> dict[str, str]:
    """`open_id:role,open_id:role` → dict（非法项忽略）。"""
    out: dict[str, str] = {}
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        open_id, _, role = chunk.partition(":")
        open_id, role = open_id.strip(), role.strip().lower()
        if open_id and role in ROLES:
            out[open_id] = role
    return out


class Identity:
    """open_id → 角色映射（env + roles.json 热加载）。"""

    def __init__(
        self,
        env_map: Optional[str] = None,
        roles_path: Optional[Path] = None,
        default_role: Optional[str] = None,
        unknown_policy: Optional[str] = None,
    ):
        raw = env_map if env_map is not None else os.environ.get("LARK_ROLE_MAP", "")
        self._env_map = _parse_env_map(raw)
        self.roles_path = Path(roles_path) if roles_path else default_roles_path()
        self.default_role = (default_role or os.environ.get("LARK_DEFAULT_ROLE") or "readonly").lower()
        self.unknown_policy = (
            unknown_policy or os.environ.get("LARK_UNKNOWN_ROLE_POLICY") or "readonly"
        ).lower()
        self._file_map: dict[str, str] = {}
        self._file_mtime: Optional[float] = None
        self._lock = threading.Lock()
        self._reload()

    # ---------- 映射 ----------

    def _reload(self) -> None:
        """文件存在则按 mtime 热加载（改文件即生效，无需重启）。"""
        try:
            if not self.roles_path.exists():
                self._file_map, self._file_mtime = {}, None
                return
            mtime = self.roles_path.stat().st_mtime
            if self._file_mtime == mtime:
                return
            data = json.loads(self.roles_path.read_text(encoding="utf-8") or "{}")
            self._file_map = {
                str(k): str(v).lower() for k, v in (data or {}).items()
                if str(v).lower() in ROLES
            }
            self._file_mtime = mtime
        except Exception:  # noqa: BLE001
            logger.exception("roles.json 读取失败，忽略文件映射")

    def role_of(self, open_id: str, chat_id: str = "") -> str:
        with self._lock:
            self._reload()
            open_id = (open_id or "").strip()
            if open_id and open_id in self._file_map:
                return self._file_map[open_id]
            if open_id and open_id in self._env_map:
                return self._env_map[open_id]
        if self.unknown_policy == "deny":
            return DENY_ROLE
        return self.default_role if self.default_role in ROLES else "readonly"

    def roles(self) -> dict[str, str]:
        """合并后的映射快照（文件覆盖 env）。"""
        with self._lock:
            self._reload()
            return {**self._env_map, **self._file_map}

    def set_role(self, open_id: str, role: str) -> None:
        """写 roles.json（admin 操作；原子写 + 立即生效）。"""
        open_id, role = (open_id or "").strip(), (role or "").strip().lower()
        if not open_id:
            raise ValueError("open_id 不能为空")
        if role not in ROLES:
            raise ValueError(f"非法角色: {role}（可选：{'/'.join(ROLES)}）")
        with self._lock:
            self._reload()
            data = dict(self._file_map)
            data[open_id] = role
            self.roles_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.roles_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.roles_path)
            self._file_mtime = None
            self._reload()

    def snapshot(self) -> dict:
        return {
            "default_role": self.default_role,
            "unknown_policy": self.unknown_policy,
            "roles_path": str(self.roles_path),
            "roles": self.roles(),
        }


# =============================================
# 审计（委托 database.bot_audit；失败不抛）
# =============================================

def record_audit(
    action: str,
    open_id: str = "",
    role: str = "",
    case_id: str = "",
    result: str = "",
    db_path: Optional[Path] = None,
) -> None:
    try:
        db.record_audit(
            action=action, open_id=open_id, role=role,
            case_id=case_id, result=result, db_path=db_path,
        )
    except Exception:  # noqa: BLE001
        logger.exception("审计写入失败（已忽略）")


def list_audit(limit: int = 50, db_path: Optional[Path] = None) -> list[dict]:
    try:
        return db.list_audit(limit=limit, db_path=db_path)
    except Exception:  # noqa: BLE001
        logger.exception("审计读取失败")
        return []


__all__ = [
    "ROLES", "DENY_ROLE", "Identity", "default_roles_path",
    "record_audit", "list_audit",
]
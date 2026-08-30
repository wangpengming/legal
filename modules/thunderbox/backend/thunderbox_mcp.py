"""
Thunderbox MCP 封装层
===================
直接调用 MCP 工具，无需 AI Agent 介入。

使用方法：
    from thunderbox_mcp import ThunderboxMCP
    tbox = ThunderboxMCP(token="<Bearer token>")
    apps = tbox.list_apps()

所有方法均为确定性调用，返回 Python 原生对象（dict/list/str）。
"""

from __future__ import annotations

import json
import http.client
import os
import logging
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------

class MCPError(Exception):
    """MCP 调用错误"""
    def __init__(self, msg: str, code: int = -1, tool: str = ""):
        super().__init__(msg)
        self.code = code
        self.tool = tool


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class App:
    """Thunderbox 应用"""
    id: int
    app_id: str
    project_id: str
    name: str
    domain: str
    owner_email: str
    source_type: str          # "git_repo" | "docker_image"
    source_url: str
    ref: Optional[str]       # 分支（git_repo 时有）
    is_public: int           # 0=internal, 1=public
    build_pack: Optional[str] # "dockerfile" | "nixpacks" | "spa" | "static"
    status: str              # "running" | "stopped" | "building" | "deploying"
    created_at: str
    updated_at: str
    volumes: Optional[str]   # JSON string, 需解析
    bypass_trusted_ips: int
    last_build_seconds: Optional[int]
    database: Optional[dict] = None   # 非 API 原生，手动注入

    @classmethod
    def from_dict(cls, d: dict) -> "App":
        return cls(
            id=d["id"],
            app_id=d["app_id"],
            project_id=d["project_id"],
            name=d["name"],
            domain=d["domain"],
            owner_email=d["owner_email"],
            source_type=d["source_type"],
            source_url=d["source_url"],
            ref=d.get("ref"),
            is_public=d["is_public"],
            build_pack=d.get("build_pack"),
            status=d["status"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            volumes=d.get("volumes"),
            bypass_trusted_ips=d.get("bypass_trusted_ips", 0),
            last_build_seconds=d.get("last_build_seconds"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_id": self.app_id,
            "project_id": self.project_id,
            "name": self.name,
            "domain": self.domain,
            "owner_email": self.owner_email,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "ref": self.ref,
            "is_public": self.is_public,
            "build_pack": self.build_pack,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "volumes": self.volumes,
            "bypass_trusted_ips": self.bypass_trusted_ips,
            "last_build_seconds": self.last_build_seconds,
            "database": self.database,
        }

    @property
    def access_mode(self) -> str:
        """兼容旧字段映射"""
        return "public" if self.is_public else "internal"


@dataclass
class DomainCheckResult:
    subdomain: str
    domain: str
    available: bool


@dataclass
class AppConfig:
    ref: str
    access_mode: str
    bypass_trusted_ips: bool
    env_vars: list
    volumes: list
    managers: list


# ---------------------------------------------------------------------------
# MCP 核心客户端
# ---------------------------------------------------------------------------

class ThunderboxMCP:
    """
    Thunderbox MCP 客户端

    封装 MCP JSON-RPC 协议，提供确定性 API 调用。
    内部维护 HTTP 持久连接和 session_id，无需每次手动管理。
    """

    def __init__(
        self,
        token: Optional[str] = None,
        host: str = "api-box.tbox.ktvsky.com",
        path: str = "/mcp",
    ):
        """
        Args:
            token: Bearer token，从环境变量 THUNDERBOX_TOKEN 或参数传入
            host: MCP API host
            path: MCP API path
        """
        self._token = token or os.environ.get("THUNDERBOX_TOKEN")
        if not self._token:
            raise ValueError(
                "THUNDERBOX_TOKEN not set. "
                "Pass token=... or set env THUNDERBOX_TOKEN"
            )
        self._host = host
        self._path = path
        self._conn: Optional[http.client.HTTPSConnection] = None
        self._session_id: Optional[str] = None
        self._protocol_version = "2024-11-05"
        self._initialized = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def connect(self) -> "ThunderboxMCP":
        """建立 MCP session（幂等，可多次调用）"""
        if self._initialized and self._conn:
            return self
        self._conn = http.client.HTTPSConnection(self._host, timeout=30)
        self._initialize()
        return self

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            self._session_id = None
            self._initialized = False

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # MCP 协议层
    # ------------------------------------------------------------------

    def _headers(self, include_session: bool = False) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self._token}",
        }
        if include_session and self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _initialize(self):
        """发送 initialize 请求"""
        data, sid = self._rpc_call({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": self._protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "thunderbox-console", "version": "1.0"},
            },
            "id": 1,
        })
        self._session_id = sid
        self._check_error(data)
        log.info("MCP initialized: %s", data["result"]["serverInfo"])

        # 发送 initialized 通知
        self._rpc_call({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }, include_session=True)
        self._initialized = True

    def _rpc_call(
        self,
        payload: dict,
        include_session: bool = False,
    ) -> tuple[dict, Optional[str]]:
        """
        发送单个 MCP JSON-RPC 请求。
        返回 (parsed_result, session_id)
        """
        if not self._conn:
            raise MCPError("Not connected. Call connect() first.")

        body = json.dumps(payload).encode()
        self._conn.request(
            "POST", self._path,
            body=body,
            headers=self._headers(include_session),
        )
        resp = self._conn.getresponse()
        sid = resp.getheader("mcp-session-id")
        raw_body = resp.read().decode()

        # 解析 SSE body（MCP 响应格式：event: message\ndata: {...}\n\n）
        # 跳过空行和 event: 行，只处理 data: 行
        for line in raw_body.split("\n"):
            line = line.strip()
            if not line or line.startswith("event:"):
                continue
            if line.startswith("data: "):
                data = json.loads(line[6:])
                return data, sid
        # 通知类请求（无 id）返回空 body，属于正常
        return None, sid

    def _call_tool(
        self,
        tool: str,
        arguments: Optional[dict] = None,
    ) -> dict:
        """
        调用单个 MCP tool，返回解析后的结果（Python 原生对象）。
        """
        if not self._initialized:
            self.connect()

        data, _ = self._rpc_call(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments or {}},
                "id": 2,
            },
            include_session=True,
        )
        self._check_error(data)

        # 提取 text 类型 content
        # MCP tool 响应：{"result": {"content": [...]}}（JSON-RPC 2.0 标准格式）
        result = data.get("result", {})
        content = result.get("content")
        if not content:
            # 工具不存在或返回空，视为成功但无数据
            return {}
        for item in content:
            if item.get("type") == "text":
                text = item["text"]
                # JSON string → Python object
                try:
                    parsed = json.loads(text)
                    # 应用层错误（thunderbox API 返回 {"error": "...", "message": "..."}）
                    if isinstance(parsed, dict) and "error" in parsed:
                        raise MCPError(
                            parsed.get("message", parsed["error"]),
                            tool=tool,
                        )
                    return parsed
                except json.JSONDecodeError:
                    return text
        return {}

    def _check_error(self, data: dict):
        if data is None:
            return  # 通知类请求无响应，正常
        if "error" in data:
            e = data["error"]
            raise MCPError(
                f"MCP error: {e.get('message', e)}",
                code=e.get("code", -1),
                tool=e.get("tool", ""),
            )

    # ------------------------------------------------------------------
    # 工具方法（确定性 API）
    # ------------------------------------------------------------------

    def list_apps(self) -> list[App]:
        """列出所有应用"""
        raw = self._call_tool("thunderbox_query", {})
        return [App.from_dict(a) for a in raw]

    def get_app(self, app_id: str) -> Optional[App]:
        """获取单个应用（通过 app_id 或 domain）"""
        apps = self.list_apps()
        for a in apps:
            if a.app_id == app_id or a.domain == app_id or str(a.id) == app_id:
                return a
        return None

    def get_app_config(self, app_id: str) -> AppConfig:
        """获取应用配置"""
        raw = self._call_tool("thunderbox_config", {"app_id": app_id})
        return AppConfig(
            ref=raw.get("ref", "main"),
            access_mode=raw.get("access", {}).get("mode", "internal"),
            bypass_trusted_ips=raw.get("access", {}).get("bypass_trusted_ips", False),
            env_vars=raw.get("env_vars", []),
            volumes=raw.get("volumes", []),
            managers=raw.get("managers", []),
        )

    def get_app_logs(
        self,
        app_id: str,
        since: Optional[str] = None,
    ) -> str:
        """获取运行时日志"""
        args = {"app_id": app_id}
        if since:
            args["since"] = since
        return self._call_tool("thunderbox_query", {"app_id": app_id, "logs": True, "since": since})

    def get_build_logs(self, app_id: str) -> str:
        """获取构建日志"""
        return self._call_tool("thunderbox_query", {"app_id": app_id, "build_logs": True})

    def get_health(self, app_id: str) -> dict:
        """健康检查"""
        return self._call_tool("thunderbox_query", {"app_id": app_id, "health": True})

    def check_domain(self, subdomain: str) -> DomainCheckResult:
        """检测域名是否可用"""
        raw = self._call_tool("thunderbox_check", {"target": "domain", "value": subdomain})
        return DomainCheckResult(
            subdomain=raw["subdomain"],
            domain=raw["domain"],
            available=raw["available"],
        )

    def create_app(
        self,
        name: str,
        source_type: str,
        source_url: str,
        build_pack: Optional[str] = None,
        port: Optional[int] = None,
        ref: str = "main",
        git_token: Optional[str] = None,
        volumes: Optional[list] = None,
    ) -> dict:
        """
        创建应用。

        Args:
            name: 应用名（用于子域名）
            source_type: "git_repo" | "docker_image"
            source_url: 仓库 URL 或镜像名
            build_pack: "dockerfile" | "nixpacks" | "spa" | "static"（git_repo 时）
            port: 监听端口
            ref: 分支（git_repo 时）
            git_token: Git token（私有仓库）
            volumes: 数据卷列表
        """
        args = {
            "name": name,
            "source_type": source_type,
            "source_url": source_url,
        }
        if build_pack:
            args["build_pack"] = build_pack
        if port:
            args["port"] = port
        if ref:
            args["ref"] = ref
        if git_token:
            args["git_token"] = git_token
        if volumes:
            args["volumes"] = volumes

        return self._call_tool("thunderbox_create", args)

    def deploy_app(self, app_id: str, ref: Optional[str] = None) -> dict:
        """部署/更新应用"""
        args = {"app_id": app_id}
        if ref:
            args["ref"] = ref
        return self._call_tool("thunderbox_deploy", args)

    def control_app(self, app_id: str, action: str) -> dict:
        """
        控制应用（启/停/取消）

        Args:
            action: "start" | "stop" | "cancel"
        """
        return self._call_tool("thunderbox_control", {"app_id": app_id, "action": action})

    def rollback_app(self, app_id: str, target: Optional[int] = None) -> dict:
        """
        回滚应用。

        Args:
            target: 部署历史 ID（不传则查询历史）
        """
        args = {"app_id": app_id}
        if target:
            args["target"] = target
        return self._call_tool("thunderbox_rollback", args)

    def get_rollback_history(self, app_id: str) -> list[dict]:
        """获取部署历史"""
        raw = self._call_tool("thunderbox_rollback", {"app_id": app_id})
        return raw.get("history", [])

    def update_config(
        self,
        app_id: str,
        access_mode: Optional[str] = None,
        ref: Optional[str] = None,
        env_vars: Optional[list] = None,
        volumes: Optional[list] = None,
        add_emails: Optional[list] = None,
        remove_emails: Optional[list] = None,
        manager_email: Optional[str] = None,
        manager_action: Optional[str] = None,  # "add" | "remove"
        bypass_trusted_ips: Optional[bool] = None,
    ) -> dict:
        """
        更新应用配置。
        所有参数都是可选的，仅传需要修改的字段。
        """
        args = {"app_id": app_id}
        if access_mode:
            args["access_mode"] = access_mode
        if ref:
            args["ref"] = ref
        if env_vars:
            args["env_vars"] = env_vars
        if volumes:
            args["volumes"] = volumes
        if add_emails:
            args["add_emails"] = add_emails
        if remove_emails:
            args["remove_emails"] = remove_emails
        if manager_email:
            args["manager_email"] = manager_email
            args["manager_action"] = manager_action
        if bypass_trusted_ips is not None:
            args["bypass_trusted_ips"] = bypass_trusted_ips

        return self._call_tool("thunderbox_config", args)

    def add_database(
        self,
        app_id: str,
        database: str = "postgres",
    ) -> dict:
        """挂载数据库"""
        return self._call_tool("thunderbox_db_add", {"app_id": app_id, "database": database})

    def remove_database(self, app_id: str) -> dict:
        """卸载数据库"""
        return self._call_tool("thunderbox_db_remove", {"app_id": app_id})

    def list_tables(self, app_id: str) -> dict:
        """列出数据库表"""
        raw = self._call_tool("thunderbox_list_tables", {"app_id": app_id})
        # raw 可能是 {"tables": [...]} 或直接是 [...]
        if isinstance(raw, dict):
            return raw
        return {"tables": raw if isinstance(raw, list) else []}

    def describe_schema(self, app_id: str) -> dict:
        """获取数据库表结构"""
        return self._call_tool("thunderbox_describe_schema", {"app_id": app_id})

    def execute_sql(self, app_id: str, sql: str) -> dict:
        """执行 SQL 查询"""
        return self._call_tool("thunderbox_sql", {"app_id": app_id, "sql": sql})

    def apply_migration(self, app_id: str, migration_name: str, sql: str) -> dict:
        """执行 SQL 迁移（幂等）"""
        return self._call_tool(
            "thunderbox_apply_migration",
            {"app_id": app_id, "name": migration_name, "sql": sql},
        )

    def stop_app(self, app_id: str) -> dict:
        """停止应用（快捷方法）"""
        return self.control_app(app_id, "stop")

    def start_app(self, app_id: str) -> dict:
        """启动应用（快捷方法）"""
        return self.control_app(app_id, "start")

    def set_public(self, app_id: str) -> dict:
        """设为公开访问"""
        return self.update_config(app_id, access_mode="public")

    def set_internal(self, app_id: str) -> dict:
        """设为内部访问"""
        return self.update_config(app_id, access_mode="internal")


# ---------------------------------------------------------------------------
# 模块级便捷函数（单例模式）
# ---------------------------------------------------------------------------

_default_client: Optional[ThunderboxMCP] = None


def get_client() -> ThunderboxMCP:
    """获取全局单例客户端（线程不安全，仅用于简单场景）"""
    global _default_client
    if _default_client is None:
        _default_client = ThunderboxMCP()
        _default_client.connect()
    return _default_client


def list_apps() -> list[App]:
    return get_client().list_apps()


def get_app(app_id: str) -> Optional[App]:
    return get_client().get_app(app_id)

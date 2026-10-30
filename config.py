# UI 配置
import os

# 端口配置（与 shared/config/ports.yaml 保持一致）
PORT = 18503
FALLBACK_PORT = 18504


def _parse_users(raw: str) -> dict:
    """解析 AUTH_USERS（格式：user:pass,user2:pass2）。"""
    users = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        username, password = pair.split(":", 1)
        if username.strip():
            users[username.strip()] = password.strip()
    return users


# 认证配置：优先读 AUTH_USERS 环境变量，默认值仅本地使用（生产由部署注入）
# 与 shared/config/deploy.yaml env_required 对齐（§6.2 密钥不明文入库）
_DEFAULT_USERS = "admin:admin123,test:test123"
USERS = _parse_users(os.environ.get("AUTH_USERS") or _DEFAULT_USERS)

# 分页配置（单一真值：列表页与 config 共用）
PAGE_SIZE = 20
# UI 配置
import os

# 端口配置（与 shared/config/ports.yaml 保持一致）
PORT = 18503
FALLBACK_PORT = 18504

# 认证配置
USERS = {
    "admin": "admin123",
    "test": "test123",
}

# 分页配置
PAGE_SIZE = 20

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

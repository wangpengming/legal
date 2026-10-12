#!/usr/bin/env python3
# 启动 case-intelligence UI
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)

# 端口
DEFAULT_PORT = 18503
FALLBACK_PORT = 18504

def check_port(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def get_free_port():
    """获取可用端口"""
    if not check_port(DEFAULT_PORT):
        return DEFAULT_PORT
    if not check_port(FALLBACK_PORT):
        return FALLBACK_PORT
    return None

def start():
    import subprocess
    import time
    
    port = get_free_port()
    if not port:
        print(f"❌ 端口 {DEFAULT_PORT} 和 {FALLBACK_PORT} 都被占用")
        print("请先释放端口: lsof -i :18503 或 :18504")
        return False
    
    print(f"""
============================================================
case-intelligence · Web UI
============================================================
端口: {port}
PID 文件: {RUN_DIR}/case-intelligence-ui.pid
日志文件: {RUN_DIR}/case-intelligence-ui.log

启动中...
""")
    
    # 启动 Streamlit - 使用 court-doc-generator 的 venv
    venv_python = PROJECT_ROOT / "../court-doc-generator/.venv/bin/python3"
    if not venv_python.exists():
        venv_python = sys.executable  # fallback to current python
    
    cmd = [
        str(venv_python), "-m", "streamlit", "run",
        str(PROJECT_ROOT / "app.py"),
        "--server.port", str(port),
        "--server.headless", "true",
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    
    log_file = RUN_DIR / "case-intelligence-ui.log"
    with open(log_file, 'w') as f:
        proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env, stdout=f, stderr=subprocess.STDOUT)
    
    # 等待启动
    time.sleep(3)
    
    # 检查是否成功
    if check_port(port):
        print(f"✅ 启动成功!")
        print(f"   访问 http://localhost:{port}")
        print(f"   停止: python3 bin/stop_ui.py")
        return True
    else:
        print(f"❌ 启动失败，请查看日志: {log_file}")
        return False

if __name__ == "__main__":
    start()

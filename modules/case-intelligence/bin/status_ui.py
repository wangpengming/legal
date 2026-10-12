#!/usr/bin/env python3
# case-intelligence UI 状态检查
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
LOG_FILE = RUN_DIR / "case-intelligence-ui.log"
PID_FILE = RUN_DIR / "case-intelligence-ui.pid"

def check_port(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def status():
    print("""
📊 case-intelligence · UI 服务状态
==================================================""")
    
    # 端口检查
    port_ok = check_port(18503) or check_port(18504)
    port = 18503 if check_port(18503) else 18504 if check_port(18504) else "未监听"
    
    if port_ok:
        print(f"🔌 端口 {port}: ✅ 已监听")
    else:
        print(f"🔌 端口 18503/18504: ❌ 未监听")
    
    # PID文件
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        print(f"📄 PID 文件: {pid}")
    else:
        print("📄 PID 文件: 无")
    
    # 健康检查
    if port_ok:
        import urllib.request
        try:
            resp = urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=3)
            if resp.status == 200:
                print(f"💚 健康检查: ✅ 通过")
            else:
                print(f"💚 健康检查: ⚠️ 状态码 {resp.status}")
        except Exception as e:
            print(f"💚 健康检查: ⚠️ {e}")
    else:
        print("💚 健康检查: ❌ 服务未运行")
    
    # 日志
    if LOG_FILE.exists():
        size = LOG_FILE.stat().st_size
        print(f"📋 日志文件: {LOG_FILE} ({size/1024:.1f} KB)")
        # 最后几行
        lines = LOG_FILE.read_text().strip().split('\n')
        if lines:
            print("\n--- 最近日志 ---")
            for line in lines[-5:]:
                print(line)
    else:
        print("📋 日志文件: 无")
    
    print("""
==================================================""")
    
    if port_ok:
        print(f"✅ 服务正常运行")
        print(f"   访问 http://localhost:{port}")
        return 0
    else:
        print("❌ 服务未运行")
        print("   启动: python3 bin/start_ui.py")
        return 1

if __name__ == "__main__":
    sys.exit(status())

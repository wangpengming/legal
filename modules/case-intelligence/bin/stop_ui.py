#!/usr/bin/env python3
# 停止 case-intelligence UI
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RUN_DIR = PROJECT_ROOT / ".run"
PID_FILE = RUN_DIR / "case-intelligence-ui.pid"

def stop():
    import os
    import signal
    
    # 三重定位停止
    pids = []
    
    # 1. PID文件
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        pids.append(pid)
    
    # 2. 端口
    try:
        result = subprocess.run(
            ["lsof", "-i", ":18503", "-t"],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            pids.append(int(result.stdout.strip()))
    except:
        pass
    
    # 3. 端口备用
    try:
        result = subprocess.run(
            ["lsof", "-i", ":18504", "-t"],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            pids.append(int(result.stdout.strip()))
    except:
        pass
    
    if not pids:
        print("❌ 未找到运行中的进程")
        return False
    
    killed = set()
    for pid in pids:
        if pid in killed:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed.add(pid)
            print(f"✅ 已停止 PID {pid}")
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"⚠️ 停止 PID {pid} 失败: {e}")
    
    # 清理PID文件
    if PID_FILE.exists():
        PID_FILE.unlink()
    
    print("✅ 停止完成")
    return True

if __name__ == "__main__":
    stop()

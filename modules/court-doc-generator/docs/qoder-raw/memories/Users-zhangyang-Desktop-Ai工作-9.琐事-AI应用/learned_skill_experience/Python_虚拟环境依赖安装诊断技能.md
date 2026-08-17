---
title: "Python 虚拟环境依赖安装诊断技能"
usage_scenario:
    - "虚拟环境中 pip 安装无反应或失败"
    - "导入模块时报 ModuleNotFoundError"
    - "不确定当前环境 Python 路径是否正确"
keywords:
    - "pip"
    - "venv"
    - "python -m"
    - "依赖安装"
    - "诊断"
source: "auto"
---

## 输入
- Python 虚拟环境目录（如 .venv）
- 需要安装的包名（如 PyMuPDF）

## 步骤
1. 尝试标准安装：`.venv/bin/pip install <包名>`
2. 若失败或无输出，检查 Python 路径：`.venv/bin/python --version`
3. 显式调用 Python 解释器执行 pip：`.venv/bin/python -m pip install <包名>`
4. 验证安装：`.venv/bin/python -c "import <模块名>; print(版本)"`
5. 若仍失败，检查系统全局 pip：`/usr/local/bin/pip3 install --user <包名>`

## 输出
成功安装并导入模块，无报错

## 注意事项
- macOS 上某些虚拟环境 pip 可能不自动激活，必须用 `-m pip` 显式调用
- PyMuPDF 旧版 API 为 `fitz`，新版推荐 `pymupdf`，避免未来兼容性问题

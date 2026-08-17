---
title: "PyMuPDF 安装与导入修正"
usage_scenario:
    - "Python 环境安装 PyMuPDF 失败或导入错误"
    - "运行脚本报 fitz 模块未找到或 API 废弃警告"
keywords:
    - "PyMuPDF"
    - "pymupdf"
    - "fitz"
    - "venv"
    - "pip"
source: "auto"
---

PyMuPDF 的 `fitz` 模块已废弃，新代码应使用 `import pymupdf`。在 macOS 虚拟环境中安装时，若 `.venv/bin/pip` 无响应，需显式指定 Python 解释器路径：`.venv/bin/python -m pip install PyMuPDF`。安装成功后验证命令：`.venv/bin/python -c "import pymupdf; print(pymupdf.__version__)"`。（来源：Bash）

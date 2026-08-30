# Thunderbox Console Dockerfile
# 单容器部署：python:3.11-slim + uvicorn + nginx:alpine 静态托管
FROM python:3.11-slim AS base

# 安装系统依赖（procps 用于 lsof，tesseract 用于 OCR）
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖（PyPI 清华镜像，避免大包超时）
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /app/requirements.txt

# 复制源码
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY bin/ /app/bin/

ENV PORT=18502
EXPOSE 18502

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:18502/health')"

# 启动：uvicorn 托管 FastAPI 后端（前端由 /static 路由）
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "18502"]

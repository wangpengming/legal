# =============================================
# court-doc-generator 容器化构建（v2.2.5）
# 多阶段：前端构建（node）→ 运行时（python）
# 部署：docker build -t court-doc-generator:2.2.5 .
# =============================================

# ---------- 阶段 1：前端构建 ----------
FROM node:20-alpine AS fe
WORKDIR /build
COPY modules/court-doc-generator/frontend/package*.json ./
RUN npm ci
COPY modules/court-doc-generator/frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行环境 ----------
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# 系统依赖：OCR（chi_sim 中文识别）+ 中文字体（文泉驿微米黑，fonts-noto-cjk ≈90MB 下载不稳，改用 ~2MB 方案）
# 换阿里云源（国内加速）；DNS 走 --add-host（buildx 内 /etc/resolv.conf 只读）
RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# 应用目录：CWD 在 backend/（与 bin/start.py 一致，uvicorn 从 backend/ 启动）
WORKDIR /app/backend

# 两个 requirements 都要装：模块根那份供 generator/docx_to_pdf/pdf_merger（sys.path 引用），backend 那份供 FastAPI
COPY modules/court-doc-generator/requirements.txt /app/
COPY modules/court-doc-generator/backend/requirements.txt .
RUN pip install --no-cache-dir -r /app/requirements.txt -r requirements.txt

# 应用代码（排除清单见 .dockerignore）
COPY modules/court-doc-generator/ /app/
# 前端 build 产物（阶段 1）
COPY --from=fe /build/dist /app/frontend/dist

# 运行时目录（卷挂载 data/ outputs/）
RUN mkdir -p /app/data /app/outputs

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
# =============================================
# case-intelligence 部署镜像（thunderbox build_pack=dockerfile）
#
# 数据持久化约定：
#   - 镜像内 data/ 作为「首次种子」拷到 /app/seed-data
#   - 运行期 DATA_DIR=/data（挂卷）；首启空卷则从 seed-data 播种
#   - 新增案例写入 /data，重新部署不丢（docker-entrypoint.sh）
# =============================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PORT=18503 \
    STREAMLIT_SERVER_HEADLESS=true

# OCR 需要系统级 tesseract（含中文包）；python 侧走 pytesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
# 🔴 构建服务器在境内，直连 PyPI 常超时（实测 ReadTimeoutError: files.pythonhosted.org）
#    → 优先走阿里云镜像 + 加长超时/重试；镜像失败再回落官方源
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        -r requirements.txt \
    || pip install --no-cache-dir --timeout 180 --retries 5 -r requirements.txt

COPY . .

# 种子数据（首启播种用）
RUN cp -r /app/data /app/seed-data

EXPOSE 18503

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
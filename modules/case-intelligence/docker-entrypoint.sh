#!/bin/sh
# 容器入口：卷空则从镜像内种子播种，再启动 Streamlit
set -e

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

# 空卷 = 首次部署：从镜像内 /app/seed-data 播种（含提炼数据 / 模板 / 案库）
if [ -z "$(ls -A "$DATA_DIR" 2>/dev/null)" ]; then
  if [ -d /app/seed-data ]; then
    echo "[entrypoint] 空卷检测：从 /app/seed-data 播种 → $DATA_DIR"
    cp -a /app/seed-data/. "$DATA_DIR"/
  fi
else
  echo "[entrypoint] 卷已有数据，保留（新增案例不受重新部署影响）"
fi

exec streamlit run app.py \
  --server.port "${PORT:-18503}" \
  --server.address 0.0.0.0 \
  --server.headless true
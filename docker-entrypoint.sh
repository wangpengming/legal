#!/bin/sh
# 容器入口：卷空则从镜像内种子播种 → 启动飞书 Bot（有凭证时）→ 启动 Streamlit
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

# 飞书 Bot：WebSocket 长连接（主动外连，无入站端口，不占用域名/PORT）
# 缺凭证则跳过；配好后崩溃自动重启（同一容器内与 Streamlit 并存）
if [ -n "$LARK_APP_ID" ] && [ -n "$LARK_APP_SECRET" ]; then
  echo "[entrypoint] 启动飞书 Bot（后台，崩溃 5s 重启）"
  (
    while true; do
      python -u bin/bot_run.py
      echo "[entrypoint] bot 退出（code=$?），5s 后重启"
      sleep 5
    done
  ) &
else
  echo "[entrypoint] 未配置 LARK_APP_ID/LARK_APP_SECRET → 跳过飞书 Bot"
fi

exec streamlit run app.py \
  --server.port "${PORT:-18503}" \
  --server.address 0.0.0.0 \
  --server.headless true
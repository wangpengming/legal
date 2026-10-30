#!/usr/bin/env python3
# =============================================
# case-intelligence 飞书 Bot 运行入口（前台进程，由 bot_start.py 后台拉起）
#
# 装配（SPEC-feishu-bot §3）：
#   LarkTransport（通道：WS 默认 / webhook 可选）
#     └─ CaseBot（身份 + 卡片 + 命令管线，走 case_service）
#          └─ transport.download_resource（附件下载，注入为 downloader）
#
# 环境变量（仅 .env；禁入库）：
#   LARK_APP_ID / LARK_APP_SECRET   飞书自建应用凭证（必填）
#   LARK_CONNECTION_MODE            websocket（默认）| webhook
#   LARK_VERIFY_TOKEN / LARK_ENCRYPT_KEY   webhook 模式校验用
#   LARK_ROLE_MAP / LARK_DEFAULT_ROLE / LARK_UNKNOWN_ROLE_POLICY  角色
#   LARK_REQUIRE_MENTION            群聊须 @Bot（默认 1）
#   LARK_BOT_ENGINE                 提取/生成引擎（默认 minimax）
#   LARK_BOT_NAME / LARK_INTAKE_DIR 展示名 / 材料落盘目录
# =============================================
import logging
import os
import signal
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import lark_bot  # noqa: E402
from src import lark_identity  # noqa: E402
from src import lark_transport  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [case-intelligence.bot] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_transport():
    """装配 transport（通道） + bot（业务），返回 (transport, bot)。"""
    app_id = os.environ.get("LARK_APP_ID") or ""
    app_secret = os.environ.get("LARK_APP_SECRET") or ""
    mode = os.environ.get("LARK_CONNECTION_MODE") or "websocket"

    identity = lark_identity.Identity()
    transport = lark_transport.LarkTransport(
        app_id=app_id,
        app_secret=app_secret,
        mode=mode,
        verify_token=os.environ.get("LARK_VERIFY_TOKEN") or "",
        encrypt_key=os.environ.get("LARK_ENCRYPT_KEY") or "",
    )
    bot = lark_bot.create_bot(
        identity=identity,
        engine=os.environ.get("LARK_BOT_ENGINE") or None,
        downloader=transport.download_resource,
    )
    transport.dispatcher = lark_bot.create_dispatcher(bot)
    return transport, bot


def main() -> int:
    app_id = os.environ.get("LARK_APP_ID") or ""
    app_secret = os.environ.get("LARK_APP_SECRET") or ""
    if not app_id or not app_secret:
        logger.error("缺少 LARK_APP_ID / LARK_APP_SECRET —— 请写入 .env（禁入库）")
        return 1

    transport, bot = build_transport()
    logger.info("bot 启动：name=%s mode=%s engine=%s", bot.bot_name, transport.mode, bot.engine)
    logger.info("心跳/去重/材料落盘：%s", transport.state_dir)

    try:
        transport.start()
    except Exception as e:  # noqa: BLE001
        logger.exception("通道启动失败")
        logger.error("提示：WS 模式需 `pip install websockets`（lark-oapi 依赖）")
        print(f"启动失败: {e}", file=sys.stderr)
        return 1

    stopping = {"flag": False}

    def _shutdown(signum, frame):  # noqa: ARG001
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # 长连接模式下 SDK 自行维持线程；主线程保持存活 + 心跳兜底
    while not stopping["flag"]:
        transport.heartbeat.touch()
        time.sleep(5)

    logger.info("收到退出信号，停止中…")
    transport.stop()
    logger.info("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
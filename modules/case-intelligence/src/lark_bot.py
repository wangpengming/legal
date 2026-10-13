#!/usr/bin/env python3
# =============================================
# case-intelligence 飞书 Bot
# 支持案件查询/搜索/登记等命令
# =============================================
import re
import json
import logging
import os
from typing import Optional, Dict, Any, List
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 尝试导入飞书 SDK
try:
    from lark_oapi.api.im.v1 import *
    from lark_oapi.api.drive.v1 import *
    LARK_SDK_AVAILABLE = True
except ImportError:
    LARK_SDK_AVAILABLE = False
    logger.warning("飞书 SDK 未安装，使用模拟模式")


class CaseCommand:
    """案件命令"""
    LIST = "list"
    SEARCH = "search"
    REGISTER = "register"
    DETAIL = "detail"
    ARTIFACTS = "artifacts"
    REPORT = "report"
    HELP = "help"


class CaseBot:
    """飞书案件 Bot"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or self._get_default_db_path()
    
    def _get_default_db_path(self) -> Path:
        """获取默认数据库路径（DATA_DIR 可覆盖，部署时落卷）"""
        project_root = Path(__file__).parent.parent
        data_dir = Path(os.environ.get("DATA_DIR") or project_root / "data")
        return data_dir / "case_registry.db"
    
    def handle_message(self, message: str) -> str:
        """
        处理用户消息，返回响应文本
        
        支持的命令：
        - /case list - 案件列表
        - /case search <关键词> - 搜索案件
        - /case register <信息> - 登记新案
        - /case detail <case_id> - 案件详情
        - /case artifacts <case_id> - 提取物列表
        - /case help - 帮助
        """
        message = message.strip()
        
        # 解析命令
        if message.startswith("/case "):
            parts = message[6:].split(maxsplit=1)
            command = parts[0] if parts else ""
            args = parts[1] if len(parts) > 1 else ""
        elif message.startswith("/case"):
            command = "list"
            args = ""
        else:
            return self._format_error("未知命令，请使用 /case help 查看帮助")
        
        # 执行命令
        try:
            if command == CaseCommand.LIST:
                return self._handle_list(args)
            elif command == CaseCommand.SEARCH:
                return self._handle_search(args)
            elif command == CaseCommand.REGISTER:
                return self._handle_register(args)
            elif command == CaseCommand.DETAIL:
                return self._handle_detail(args)
            elif command == CaseCommand.ARTIFACTS:
                return self._handle_artifacts(args)
            elif command == CaseCommand.REPORT:
                return self._handle_report()
            elif command == CaseCommand.HELP:
                return self._get_help_text()
            else:
                return self._format_error(f"未知命令: {command}")
        except Exception as e:
            logger.error(f"处理命令失败: {e}")
            return self._format_error(f"处理失败: {str(e)}")
    
    def _handle_list(self, args: str) -> str:
        """处理案件列表命令"""
        import sqlite3
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 解析参数
        year_filter = None
        quality_filter = None
        
        if args:
            if "2024" in args:
                year_filter = 2024
            elif "2025" in args:
                year_filter = 2025
            elif "2026" in args:
                year_filter = 2026
            
            if "A级" in args or "A" in args:
                quality_filter = "A"
            elif "B级" in args or "B" in args:
                quality_filter = "B"
        
        # 查询
        if year_filter:
            cursor.execute(
                "SELECT id, case_number, case_name, plaintiff, defendant, status, year, quality FROM cases WHERE year = ? ORDER BY created_at DESC LIMIT 20",
                (year_filter,)
            )
        else:
            cursor.execute(
                "SELECT id, case_number, case_name, plaintiff, defendant, status, year, quality FROM cases ORDER BY created_at DESC LIMIT 20"
            )
        
        cases = cursor.fetchall()
        conn.close()
        
        if not cases:
            return "📋 暂无案件记录"
        
        # 格式化输出
        lines = ["📋 **案件列表**", ""]
        lines.append(f"共 {len(cases)} 个案件：")
        lines.append("")
        
        for i, case in enumerate(cases, 1):
            case_num = case["case_number"] or "无案号"
            name = case["case_name"] or "未知"
            plaintiff = case["plaintiff"] or ""
            status = case["status"] or "pending"
            
            status_icon = {
                "pending": "⏳",
                "extracted": "✅",
                "completed": "🎉"
            }.get(status, "📌")
            
            lines.append(f"{i}. {status_icon} **{case_num}**")
            lines.append(f"   📝 {name}")
            if plaintiff:
                lines.append(f"   👤 {plaintiff}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _handle_search(self, keyword: str) -> str:
        """处理搜索命令"""
        if not keyword:
            return self._format_error("请提供搜索关键词")
        
        import sqlite3
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, case_number, case_name, plaintiff, defendant, cause, status
            FROM cases
            WHERE case_name LIKE ? OR plaintiff LIKE ? OR defendant LIKE ? OR cause LIKE ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        )
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return f"🔍 未找到包含「{keyword}」的案件"
        
        lines = [f"🔍 **搜索结果：** 共 {len(results)} 个"]
        lines.append("")
        
        for i, case in enumerate(results, 1):
            case_num = case["case_number"] or "无案号"
            name = case["case_name"] or "未知"
            
            lines.append(f"{i}. **{case_num}**")
            lines.append(f"   📝 {name}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _handle_register(self, info: str) -> str:
        """处理登记命令"""
        if not info:
            return self._format_error("请提供案件信息")
        
        # 解析案件信息（简化版：支持 key:value 格式）
        case_data = {}
        for line in info.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if "案号" in key or "case_number" in key:
                    case_data["case_number"] = value
                elif "原告" in key or "plaintiff" in key:
                    case_data["plaintiff"] = value
                elif "被告" in key or "defendant" in key:
                    case_data["defendant"] = value
                elif "案由" in key or "cause" in key:
                    case_data["cause"] = value
                elif "法院" in key or "court" in key:
                    case_data["court"] = value
        
        if not case_data:
            return self._format_error("无法解析案件信息，请使用格式：\n案号: xxx\n原告: xxx\n被告: xxx")
        
        # 生成案件名称
        plaintiff = case_data.get("plaintiff", "")
        defendant = case_data.get("defendant", "")
        cause = case_data.get("cause", "纠纷")
        
        if plaintiff and defendant:
            case_data["case_name"] = f"{plaintiff}诉{defendant}{cause}"
        else:
            case_data["case_name"] = info[:50]
        
        # 写入数据库
        import sqlite3
        from datetime import datetime
        import re
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        case_id = f"bot-{now}"
        
        # 从案号推断年份
        case_number = case_data.get("case_number", "")
        year = None
        year_match = re.search(r'20(\d{2})', case_number)
        if year_match:
            year = 2000 + int(year_match.group(1))
        
        try:
            cursor.execute(
                """
                INSERT INTO cases (id, case_number, case_name, plaintiff, defendant, cause, court, year, status, created_at, entry_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 'Bot')
                """,
                (
                    case_id,
                    case_data.get("case_number"),
                    case_data.get("case_name"),
                    case_data.get("plaintiff"),
                    case_data.get("defendant"),
                    case_data.get("cause"),
                    case_data.get("court"),
                    year,
                    now
                )
            )
            conn.commit()
            conn.close()
            
            return f"✅ **案件登记成功**\n\n📋 案件ID: `{case_id}`\n📝 案件名称: {case_data['case_name']}"
        except Exception as e:
            conn.close()
            return self._format_error(f"登记失败: {str(e)}")
    
    def _handle_detail(self, case_id: str) -> str:
        """处理案件详情命令"""
        if not case_id:
            return self._format_error("请提供案件ID")
        
        import sqlite3
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 支持按ID或案号查询
        cursor.execute(
            "SELECT * FROM cases WHERE id = ? OR case_number LIKE ? LIMIT 1",
            (case_id, f"%{case_id}%")
        )
        
        case = cursor.fetchone()
        conn.close()
        
        if not case:
            return f"❌ 未找到案件: {case_id}"
        
        # 格式化详情
        lines = ["📋 **案件详情**", ""]
        lines.append(f"**案号:** {case['case_number'] or '无'}")
        lines.append(f"**名称:** {case['case_name'] or '无'}")
        lines.append(f"**原告:** {case['plaintiff'] or '无'}")
        lines.append(f"**被告:** {case['defendant'] or '无'}")
        lines.append(f"**案由:** {case['cause'] or '无'}")
        lines.append(f"**法院:** {case['court'] or '无'}")
        lines.append(f"**状态:** {case['status'] or 'pending'}")
        lines.append(f"**ID:** `{case['id']}`")
        
        return "\n".join(lines)
    
    def _handle_artifacts(self, case_id: str) -> str:
        """处理提取物列表命令"""
        if not case_id:
            return self._format_error("请提供案件ID")
        
        import sqlite3
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 先获取案件
        cursor.execute(
            "SELECT id FROM cases WHERE id = ? OR case_number LIKE ? LIMIT 1",
            (case_id, f"%{case_id}%")
        )
        case = cursor.fetchone()
        
        if not case:
            return f"❌ 未找到案件: {case_id}"
        
        # 获取提取物
        cursor.execute(
            "SELECT id, artifact_type, title, version FROM artifacts WHERE case_id = ? ORDER BY artifact_type",
            (case["id"],)
        )
        
        artifacts = cursor.fetchall()
        conn.close()
        
        if not artifacts:
            return "📦 暂无提取物"
        
        lines = ["📦 **提取物列表**", ""]
        
        for i, artifact in enumerate(artifacts, 1):
            lines.append(f"{i}. **{artifact['artifact_type']}** - {artifact['title']}")
            lines.append(f"   ID: `{artifact['id']}`")
        
        return "\n".join(lines)
    
    def _handle_report(self) -> str:
        """处理统计报告命令"""
        import sqlite3
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 基础统计
        total_cases = cursor.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        extracted_cases = cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'extracted'").fetchone()[0]
        pending_cases = cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'pending'").fetchone()[0]
        total_artifacts = cursor.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
        total_templates = cursor.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        
        # 按年份统计
        year_stats = cursor.execute("""
            SELECT year, COUNT(*) as count 
            FROM cases 
            WHERE year IS NOT NULL 
            GROUP BY year 
            ORDER BY year DESC
        """).fetchall()
        
        # 按案由统计
        cause_stats = cursor.execute("""
            SELECT cause, COUNT(*) as count 
            FROM cases 
            WHERE cause IS NOT NULL AND cause != ''
            GROUP BY cause 
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()
        
        conn.close()
        
        # 格式化输出
        lines = ["📊 **案例库统计报告**", ""]
        lines.append(f"**案件总数:** {total_cases}")
        lines.append(f"**已提取:** {extracted_cases} 个")
        lines.append(f"**待提取:** {pending_cases} 个")
        lines.append(f"**提取物总数:** {total_artifacts} 个")
        lines.append(f"**模板总数:** {total_templates} 个")
        lines.append("")
        
        if year_stats:
            lines.append("**年度分布:**")
            for stat in year_stats:
                lines.append(f"  - {stat['year']}年: {stat['count']} 个")
            lines.append("")
        
        if cause_stats:
            lines.append("**案由分布 (Top 5):**")
            for stat in cause_stats:
                cause_name = stat['cause'][:20] if stat['cause'] else '未知'
                lines.append(f"  - {cause_name}: {stat['count']} 个")
        
        return "\n".join(lines)
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """
📖 **case-intelligence 案件机器人帮助**

**可用命令：**

🔍 `/case list` - 查看案件列表
   示例：`/case list 2024` - 查看2024年案件

🔎 `/case search <关键词>` - 搜索案件
   示例：`/case search 腾讯`

📝 `/case register` - 登记新案件
   示例：
   ```
   /case register
   案号: (2024)京0491民初123号
   原告: 腾讯音乐
   被告: 雷石公司
   案由: 著作权侵权
   ```

📋 `/case detail <案件ID或案号>` - 查看案件详情
   示例：`/case detail (2024)京0491民初123`

📦 `/case artifacts <案件ID>` - 查看案件提取物
   示例：`/case artifacts xxx-xxx-xxx`

📊 `/case report` - 查看统计报告

❓ `/case help` - 显示帮助
"""
    
    def _format_error(self, message: str) -> str:
        """格式化错误消息"""
        return f"❌ {message}"


# Webhook 处理器
class LarkWebhookHandler:
    """飞书 Webhook 事件处理器"""
    
    def __init__(self, bot: CaseBot):
        self.bot = bot
    
    def handle_event(self, event_data: dict) -> Optional[dict]:
        """
        处理飞书事件
        
        Args:
            event_data: 飞书事件数据
            
        Returns:
            响应数据
        """
        try:
            # 解析消息事件
            event_type = event_data.get("event", {})
            msg_type = event_type.get("msg_type", "")
            content = event_type.get("content", {})
            
            # 解析文本内容
            if msg_type == "text":
                text = json.loads(content).get("text", "")
            else:
                text = str(content)
            
            # 处理消息
            response = self.bot.handle_message(text)
            
            # 返回响应
            return {
                "status_code": 0,
                "status_message": "success",
                "data": {
                    "content": response
                }
            }
        except Exception as e:
            logger.error(f"处理事件失败: {e}")
            return {
                "status_code": 1,
                "status_message": str(e)
            }


def create_bot(db_path: Optional[Path] = None) -> CaseBot:
    """创建案件 Bot 实例"""
    return CaseBot(db_path)


def create_webhook_handler(bot: Optional[CaseBot] = None) -> LarkWebhookHandler:
    """创建 Webhook 处理器"""
    if bot is None:
        bot = create_bot()
    return LarkWebhookHandler(bot)


# CLI 模式
if __name__ == "__main__":
    import sys
    
    bot = create_bot()
    
    print("=" * 50)
    print("case-intelligence 飞书案件 Bot")
    print("=" * 50)
    print()
    print("输入命令进行测试（输入 exit 退出）：")
    print()
    
    while True:
        try:
            user_input = input("> ").strip()
            
            if user_input.lower() in ["exit", "quit", "q"]:
                print("再见！")
                break
            
            if not user_input:
                continue
            
            response = bot.handle_message(user_input)
            print()
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"错误: {e}")

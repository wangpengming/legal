"""配置管理：加载项目配置和静态信息。"""
import json
from pathlib import Path

# 项目根目录（本模块所在目录：court-doc-generator/）
# v1.1.3 修复：config.py 位于 court-doc-generator/ 下，parent.parent 会解析到 modules/，
# 导致 TEMPLATES_DIR/STATIC_DIR 指向空目录（模板文件已按 a61a41c 整理到本模块内）
PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# 确保必要目录存在
for d in [TEMPLATES_DIR, STATIC_DIR, CONFIG_DIR, DATA_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 数据库路径
DB_PATH = DATA_DIR / "court_matters.db"

# 模板文件清单
TEMPLATE_FILES = {
    "legal_rep_cert": "2.法定代表人证明.docx",
    "power_of_attorney": "4.授权委托书.docx",
    "recommendation": "5.推荐信.docx",
}

# F-033 多代理人材料动态绑定：静态文件拆分为公司级与代理人级
# 公司级静态（与具体代理人无关，所有案件共用）
COMPANY_STATIC = [
    "1.营业执照复印件.pdf",
    "法人身份证.pdf",
]
# 代理人级静态 fallback（未上传个人材料时使用默认文件）
# key: 输出文件名，value: 默认 fallback 文件名（位于 STATIC_DIR/）
AGENT_STATIC_FALLBACK = {
    "06_代理人劳动合同.pdf": "代理人劳动合同.pdf",
    "07_代理人身份证.pdf": "代理人身份证.pdf",
}

# 静态 PDF 文件清单（按出庭提交顺序）— 向后兼容保留
STATIC_FILES = COMPANY_STATIC + list(AGENT_STATIC_FALLBACK.values())


def get_template_path(key: str) -> Path:
    """获取模板文件路径。"""
    if key not in TEMPLATE_FILES:
        raise ValueError(f"未知模板: {key}")
    return TEMPLATES_DIR / TEMPLATE_FILES[key]


def get_static_files() -> list:
    """获取所有静态文件路径（按出庭顺序）。"""
    files = []
    # 营业执照
    biz_license = STATIC_DIR / "1.营业执照复印件.pdf"
    if biz_license.exists():
        files.append(biz_license)
    # 法人身份证
    legal_id = STATIC_DIR / "法人身份证.pdf"
    if legal_id.exists():
        files.append(legal_id)
    # 劳动合同
    labor_contract = STATIC_DIR / "代理人劳动合同.pdf"
    if labor_contract.exists():
        files.append(labor_contract)
    # 代理人身份证
    agent_id = STATIC_DIR / "代理人身份证.pdf"
    if agent_id.exists():
        files.append(agent_id)
    return files


def load_json_config(filename: str) -> dict:
    """加载 JSON 配置文件。"""
    config_path = CONFIG_DIR / filename
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_json_config(filename: str, data: dict) -> None:
    """保存 JSON 配置文件。"""
    config_path = CONFIG_DIR / filename
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

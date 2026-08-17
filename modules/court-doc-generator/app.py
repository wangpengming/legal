"""出庭手续生成器 - Streamlit 主界面。

启动方式：
    streamlit run app.py
或双击 `启动.command`
"""
from datetime import date, datetime
from pathlib import Path

import streamlit as st

import database as db
from config import OUTPUTS_DIR, save_json_config
from generator import generate_court_matters, open_in_finder, sanitize_filename
from feishu_api import get_feishu_status, is_feishu_enabled
from pdf_viewer_component import is_pdfjs_ready, render_pdf_viewer


# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="出庭手续生成器",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 全局 CSS（Vercel / Linear 风格）
# ============================================================

st.markdown(
    """
    <style>
    /* 全局字体 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "PingFang SC",
                     "Microsoft YaHei", "Segoe UI", sans-serif;
    }
    /* 主按钮（生成） */
    button[kind="primary"] {
        background-color: #0a0a0a;
        border: 1px solid #0a0a0a;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    button[kind="primary"]:hover {
        background-color: #262626;
        border-color: #262626;
    }
    /* 二级按钮 */
    button:not([kind="primary"]) {
        border-radius: 8px;
        border: 1px solid #d4d4d4;
        transition: all 0.2s ease;
    }
    button:not([kind="primary"]):hover {
        border-color: #0a0a0a;
    }
    /* 输入框 */
    input, textarea, [data-baseweb="select"] {
        border-radius: 8px !important;
    }
    /* Expander */
    [data-testid="stExpander"] {
        border: 1px solid #e5e5e5;
        border-radius: 8px;
    }
    /* Divider */
    hr {
        margin: 1.5rem 0;
        border-color: #f5f5f5;
    }
    /* Tab */
    [data-baseweb="tab-list"] {
        gap: 8px;
    }
    [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
    }
    /* 容器边框 */
    [data-testid="stContainer"][data-border="true"] {
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        padding: 16px;
        background: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 初始化
# ============================================================

@st.cache_resource
def initialize():
    """初始化数据库。"""
    db.init_db()
    return True


initialize()


# ============================================================
# 工具函数
# ============================================================

def ensure_default_company_and_agent():
    """首次启动时，仅创建空公司/代理人记录，UI 引导用户填写真实信息。

    设计原则（v1.1+）：
    - 严禁硬编码真实 PII（身份证号 / 手机号 / 公司全称）
    - 默认数据仅作占位，提示用户必须填写真实信息
    - 由 main() 调用，不是模块级副作用（避免 import 时写库）
    """
    if not db.list_companies():
        # 仅创建一条空记录，UI 会提示“请填公司全称”并校验
        db.upsert_company({
            "name": "",  # 占位：用户必须填写真实公司全称
            "credit_code": "",
            "legal_rep_name": "",
            "legal_rep_position": "",
            "legal_rep_id_card": "",
            "address": "",
            "phone": "",
        })

    if not db.list_agents():
        # 仅创建一条空记录，UI 会提示并要求补全
        db.upsert_agent({
            "name": "",  # 占位：用户必须填写真实姓名
            "gender": "男",
            "id_card": "",
            "position": "",
            "phone": "",
            "company_id": None,
        })


# ============================================================
# 侧边栏：信息管理
# ============================================================

def render_sidebar():
    """侧边栏：信息管理 + 飞书状态。"""
    with st.sidebar:
        st.title("⚖️ 出庭手续生成器")
        st.caption("法务出庭 7 份材料一键生成")
        st.divider()

        # ========== 公司/法人管理 ==========
        st.subheader("🏢 委托单位（公司）")
        companies = db.list_companies()
        company_options = {f"{c['name']}" + (" [默认]" if c['is_default'] else ""): c for c in companies}
        if company_options:
            selected_label = st.selectbox(
                "当前公司",
                list(company_options.keys()),
                key="selected_company",
            )
            current_company = company_options[selected_label]
        else:
            current_company = None

        with st.expander("➕ 添加/编辑公司"):
            with st.form("add_company"):
                c_name = st.text_input("公司全称*", value=current_company["name"] if current_company else "")
                c_credit = st.text_input("统一社会信用代码", value=current_company.get("credit_code", "") if current_company else "")
                c_legal = st.text_input("法定代表人姓名*", value=current_company.get("legal_rep_name", "") if current_company else "")
                c_position = st.text_input("法人职务", value=current_company.get("legal_rep_position", "") if current_company else "")
                c_idcard = st.text_input(
                                    "法人身份证号",
                                    value=current_company.get("legal_rep_id_card", "") if current_company else "",
                                    max_chars=18,
                                    help="可选·18 位·将出现在《法定代表人证明》中。请认真核对。",
                                )
                c_address = st.text_input("公司地址", value=current_company.get("address", "") if current_company else "")
                c_phone = st.text_input("公司电话", value=current_company.get("phone", "") if current_company else "")
                submitted = st.form_submit_button("保存")
                if submitted and c_name and c_legal:
                    db.upsert_company({
                        "name": c_name,
                        "credit_code": c_credit,
                        "legal_rep_name": c_legal,
                        "legal_rep_position": c_position,
                        "legal_rep_id_card": c_idcard,
                        "address": c_address,
                        "phone": c_phone,
                    })
                    st.success(f"✅ 已保存：{c_name}")
                    st.rerun()

        st.divider()

        # ========== 代理人管理 ==========
        st.subheader("👤 代理人（法务/律师）")
        agents = db.list_agents()
        agent_options = {f"{a['name']} - {a.get('position', '')}" + (" [默认]" if a['is_default'] else ""): a for a in agents}
        if agent_options:
            selected_agent_label = st.selectbox(
                "当前代理人",
                list(agent_options.keys()),
                key="selected_agent",
            )
            current_agent = agent_options[selected_agent_label]
        else:
            current_agent = None

        with st.expander("➕ 添加/编辑代理人"):
            with st.form("add_agent"):
                a_name = st.text_input("代理人姓名*", value=current_agent["name"] if current_agent else "")
                a_gender = st.selectbox("性别", ["男", "女"], index=1 if (current_agent and current_agent.get("gender") == "女") else 0)
                a_idcard = st.text_input(
                                    "身份证号",
                                    value=current_agent.get("id_card", "") if current_agent else "",
                                    max_chars=18,
                                    help="可选·18 位·将出现在《授权委托书》中。",
                                )
                a_position = st.text_input("职务", value=current_agent.get("position", "") if current_agent else "")
                a_phone = st.text_input("电话", value=current_agent.get("phone", "") if current_agent else "")
                submitted_a = st.form_submit_button("保存")
                if submitted_a and a_name:
                    db.upsert_agent({
                        "name": a_name,
                        "gender": a_gender,
                        "id_card": a_idcard,
                        "position": a_position,
                        "phone": a_phone,
                        "company_id": current_company["id"] if current_company else None,
                    })
                    st.success(f"✅ 已保存代理人：{a_name}")
                    st.rerun()

        st.divider()

        # ========== 飞书集成状态 ==========
        st.subheader("📡 飞书集成")
        feishu_status = get_feishu_status()
        if feishu_status["enabled"]:
            st.success("✅ 飞书集成已启用（MVP 预留接口）")
        else:
            st.info("ℹ️ 飞书集成未启用（未来可配置）")

    return current_company, current_agent


# ============================================================
# 主区域：案件信息填写 + 生成
# ============================================================

def render_main(current_company, current_agent):
    """主区域。"""
    st.title("📋 生成出庭手续")

    if not current_company:
        st.error("⚠️ 请先在左侧添加委托单位信息")
        return
    if not current_agent:
        st.error("⚠️ 请先在左侧添加代理人信息")
        return

    # ========== Tab 切换：新建 / 历史 ==========
    tab_new, tab_history = st.tabs(["🆕 新建案件", "📜 历史案件"])

    with tab_new:
        render_new_case_form(current_company, current_agent)

    with tab_history:
        render_case_history(current_company, current_agent)


def render_new_case_form(current_company, current_agent):
    """新建案件表单。"""
    st.subheader(f"当前：{current_company['name']} × {current_agent['name']}")

    # 初始化 session state
    if "form_case_number" not in st.session_state:
        st.session_state.form_case_number = ""
    if "last_output_dir" not in st.session_state:
        st.session_state.last_output_dir = None

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 📌 案件基本信息")
        case_number = st.text_input(
            "案号 *",
            value=st.session_state.form_case_number,
            placeholder="（2026）京0101民初1234号",
            help="如：（2026）京0101民初1234号",
        )
        case_cause = st.text_input(
            "案由 *",
            placeholder="合同纠纷 / 著作权侵权 / 劳动争议...",
            help="如：合同纠纷、服务合同纠纷、知识产权纠纷",
        )
        court = st.text_input(
            "审理法院 *",
            placeholder="北京市第一中级人民法院",
        )
        hearing_date = st.date_input(
            "开庭日期 *",
            value=date.today(),
            min_value=date(2020, 1, 1),
        )

    with col2:
        st.markdown("##### 👥 当事人 & 权限")
        opposing_party = st.text_input(
            "对方当事人",
            placeholder="如：北京XX科技有限公司",
        )
        our_role = st.radio(
            "我方身份 *",
            ["原告", "被告", "第三人"],
            horizontal=True,
        )
        authority_type = st.radio(
            "代理权限 *",
            ["特别授权", "一般授权"],
            horizontal=True,
            help="特别授权：可代为承认/放弃/变更请求、和解、上诉等\n一般授权：仅普通程序行为",
        )
        notes = st.text_area("备注（可选）", height=80)

    st.divider()

    # 生成预览
    st.markdown("##### 📄 预览案由描述")
    if case_cause:
        preview_parts = []
        if our_role == "原告":
            preview_parts.append(f"我方诉{opposing_party or '对方'}")
        elif our_role == "被告":
            preview_parts.append(f"{opposing_party or '对方'}诉我方")
        else:
            preview_parts.append(f"{opposing_party or '对方'}与我方")
        preview_parts.append(case_cause)
        st.code(f"📌 {' '.join(preview_parts)}（案号：{case_number or '（待填）'}）", language="text")

    st.divider()

    # 生成按钮
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])

    with col_btn1:
        generate_btn = st.button(
            "🚀 生成出庭手续（7 份文件）",
            type="primary",
            use_container_width=True,
            disabled=not (case_number and case_cause and court),
        )

    with col_btn2:
        preview_btn = st.button("👁 仅预览", use_container_width=True)

    # ========== 生成逻辑 ==========
    if generate_btn or preview_btn:
        # 校验
        if not (case_number and case_cause and court):
            st.error("❌ 请填写：案号、案由、审理法院（标 * 为必填）")
            return

        # 构造案件数据
        case_data = {
            "case_number": case_number.strip(),
            "case_cause": case_cause.strip(),
            "court": court.strip(),
            "hearing_date": hearing_date.strftime("%Y-%m-%d"),
            "opposing_party": opposing_party.strip(),
            "our_role": our_role,
            "authority_type": authority_type,
            "company_id": current_company["id"],
            "agent_id": current_agent["id"],
            "notes": notes.strip(),
        }

        if preview_btn:
            st.info(f"📝 预览模式：上述信息将生成 7 份出庭手续文件（点击「生成」执行）")
            return

        # 写入数据库
        case_id = db.create_case(case_data)

        # 获取完整案件（含公司/代理人信息）
        full_case = db.get_case(case_id)

        # 生成
        try:
            with st.spinner("⏳ 正在生成出庭手续..."):
                output_dir = generate_court_matters(
                    full_case, current_company, current_agent
                )
            # 记录历史
            file_count = sum(1 for _ in output_dir.iterdir() if _.suffix in (".docx", ".pdf"))
            db.add_history(case_id, case_number, str(output_dir), file_count)

            st.session_state.last_output_dir = output_dir
            st.session_state.form_case_number = ""  # 清空案号便于下一个案件

            st.success(f"✅ 已生成 {file_count} 份文件！")

            # ===== PDF 浏览器内预览（PDF.js 全内联）=====
            merged_pdf = output_dir / f"00_合并出庭手续_{sanitize_filename(case_number)}.pdf"
            if merged_pdf.exists() and is_pdfjs_ready():
                with st.expander("📺 浏览器内预览 · 合并 PDF（推荐）", expanded=True):
                    st.caption("使用 PDF.js 全内联渲染·可缩放/翻页/打印全部")
                    render_pdf_viewer(merged_pdf, height=720, key=f"preview_{case_id}")
            elif merged_pdf.exists() and not is_pdfjs_ready():
                with st.info("📺 PDF 浏览器内预览需要 PDF.js 库。请联系相关人员下载 `pdf.min.js` + `pdf.worker.min.js` 到 `static/pdfjs/`。"):

                    pass  # 占位

            # 列出生成的文件
            st.markdown("##### 📂 生成文件清单")
            files = sorted(output_dir.iterdir(), key=lambda x: x.name)
            for f in files:
                size_kb = f.stat().st_size / 1024
                col_f1, col_f2 = st.columns([3, 1])
                with col_f1:
                    st.text(f"📄 {f.name}  ({size_kb:.1f} KB)")
                with col_f2:
                    with open(f, "rb") as fp:
                        st.download_button(
                            label="下载",
                            data=fp.read(),
                            file_name=f.name,
                            mime="application/octet-stream",
                            key=f"dl_{f.name}_{case_id}",
                        )

            st.divider()
            col_open1, col_open2 = st.columns(2)
            with col_open1:
                if st.button("📁 在 Finder 中打开", use_container_width=True):
                    open_in_finder(output_dir)
            with col_open2:
                zip_files = list(output_dir.glob("*.zip"))
                if zip_files:
                    with open(zip_files[0], "rb") as zf:
                        st.download_button(
                            label="📦 下载完整 zip 包",
                            data=zf.read(),
                            file_name=zip_files[0].name,
                            mime="application/zip",
                            use_container_width=True,
                        )

        except Exception as e:
            st.error(f"❌ 生成失败：{e}")
            import traceback
            with st.expander("🔍 查看错误详情"):
                st.code(traceback.format_exc())


def render_case_history(current_company, current_agent):
    """历史案件列表。"""
    st.subheader("📜 历史案件")
    search = st.text_input("🔍 搜索（案号/案由/对方当事人）", "")
    if search:
        cases = db.search_cases(search)
    else:
        cases = db.list_cases(limit=50)

    if not cases:
        st.info("暂无案件记录")
        return

    for case in cases:
        with st.container(border=True):
            col_a, col_b, col_c = st.columns([3, 1, 1])
            with col_a:
                st.markdown(f"**📋 {case['case_number']}**")
                st.caption(
                    f"{case['case_cause']} | {case['court']} | "
                    f"开庭：{case.get('hearing_date', '未定')} | "
                    f"我方：{case['our_role']} | 对方：{case.get('opposing_party', '-')}"
                )
            with col_b:
                if case.get('created_at'):
                    st.caption(f"创建：{case['created_at'][:10]}")
            with col_c:
                if st.button("🔄 重新生成", key=f"regen_{case['id']}", use_container_width=True):
                    full_case = db.get_case(case["id"])
                    if not full_case:
                        st.error("案件信息不完整")
                        continue
                    company = {
                        "name": full_case.get("company_name"),
                        "legal_rep_name": full_case.get("legal_rep_name"),
                        "legal_rep_position": full_case.get("legal_rep_position"),
                        "address": full_case.get("company_address"),
                        "phone": full_case.get("company_phone"),
                    }
                    agent = {
                        "name": full_case.get("agent_name"),
                        "gender": full_case.get("agent_gender"),
                        "id_card": full_case.get("agent_id_card"),
                        "position": full_case.get("agent_position"),
                        "phone": full_case.get("agent_phone"),
                    }
                    try:
                        with st.spinner("⏳ 重新生成中..."):
                            output_dir = generate_court_matters(full_case, company, agent)
                        file_count = sum(1 for _ in output_dir.iterdir() if _.suffix in (".docx", ".pdf"))
                        db.add_history(case["id"], case["case_number"], str(output_dir), file_count)
                        st.success(f"✅ 已重新生成 {file_count} 份文件")
                        open_in_finder(output_dir)
                    except Exception as e:
                        st.error(f"❌ 生成失败：{e}")


# ============================================================
# 入口
# ============================================================

def main():
    """Streamlit 主入口。

    注意：
    - ensure_default_company_and_agent() 必须在这里调用，避免模块级副作用
    - 测试场景下 import app 不会创建默认记录
    """
    ensure_default_company_and_agent()
    current_company, current_agent = render_sidebar()
    render_main(current_company, current_agent)


if __name__ == "__main__":
    main()

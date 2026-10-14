# 案件列表页
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth
from ui.nav import render_sidebar
from ui.utils import compute_health, get_artifact_counts
from config import PAGE_SIZE
from src import database as db

require_auth()

st.set_page_config(
    page_title="案例分析 - 案件列表",
    page_icon="📋",
    layout="wide"
)

render_sidebar()

st.title("📋 案件列表")

# ========== 新建案件（A1 register 等价） ==========
with st.expander("➕ 新建案件", expanded=False):
    with st.form("new_case_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            f_name = st.text_input("案件名称 *")
            f_number = st.text_input("案号")
            f_cause = st.text_input("案由")
            f_court = st.text_input("法院")
        with c2:
            f_plaintiff = st.text_input("原告")
            f_defendant = st.text_input("被告")
            f_year = st.number_input("年份", min_value=0, max_value=2100, value=0, step=1)
            f_scene = st.text_input("涉案场景")
        f_notes = st.text_area("备注", height=60)
        if st.form_submit_button("✅ 创建", type="primary"):
            if not f_name.strip():
                st.error("案件名称必填")
            else:
                try:
                    case = db.create_case(
                        case_name=f_name.strip(),
                        case_number=(f_number.strip() or None),
                        plaintiff=f_plaintiff.strip(),
                        defendant=f_defendant.strip(),
                        cause=f_cause.strip(),
                        court=f_court.strip(),
                        year=(int(f_year) or None),
                        scene=f_scene.strip(),
                        notes=f_notes.strip(),
                        entry_method="UI",
                    )
                    st.success(f"✅ 已创建：{case['case_name']}")
                except ValueError as e:
                    st.error(f"创建失败：{e}")

# ========== 顶部工具栏 ==========
toolbar_col1, toolbar_col2, toolbar_col3 = st.columns([2, 1, 1])

with toolbar_col1:
    search = st.text_input(
        "🔍 搜索",
        placeholder="输入案号/原告/被告/案由搜索...",
        label_visibility="collapsed"
    )

with toolbar_col2:
    status_filter = st.selectbox(
        "状态",
        options=["全部", "待提取", "已提取", "已归档"],
        index=0,
        label_visibility="collapsed"
    )

with toolbar_col3:
    sort_by = st.selectbox(
        "排序",
        options=["最新创建", "案号", "案由", "健康度"],
        index=0,
        label_visibility="collapsed"
    )

st.divider()

# ========== 获取数据 ==========
all_cases = db.search_cases(search) if search else db.list_cases()

if status_filter == "待提取":
    all_cases = [c for c in all_cases if c.get('status') == 'pending']
elif status_filter == "已提取":
    all_cases = [c for c in all_cases if c.get('status') == 'extracted']
elif status_filter == "已归档":
    all_cases = [c for c in all_cases if c.get('status') == 'archived']

artifact_counts = get_artifact_counts()

if sort_by == "案号":
    all_cases.sort(key=lambda x: x.get('case_number', ''), reverse=True)
elif sort_by == "案由":
    all_cases.sort(key=lambda x: x.get('cause', ''))
elif sort_by == "健康度":
    all_cases.sort(
        key=lambda x: compute_health(x, artifact_counts.get(x['id'], 0))["health"],
        reverse=True,
    )

total = len(all_cases)
st.caption(f"共找到 **{total}** 个案件")

# ========== 分页（C1 修复：统一 session_state.page + 单一 PAGE_SIZE） ==========
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
if "page" not in st.session_state:
    st.session_state.page = 1
st.session_state.page = min(max(1, st.session_state.page), total_pages)

page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
with page_col1:
    if total_pages > 1:
        page = st.number_input(
            "页码", min_value=1, max_value=total_pages, step=1,
            key="page", label_visibility="collapsed"
        )
    else:
        page = 1

with page_col2:
    if total_pages > 1:
        st.markdown(
            f"<div style='text-align: center; padding-top: 5px;'>第 {page} / {total_pages} 页</div>",
            unsafe_allow_html=True,
        )

with page_col3:
    if total_pages > 1:
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button("◀ 上一页", disabled=(page <= 1), use_container_width=True):
                st.session_state.page = page - 1
                st.rerun()
        with col_next:
            if st.button("下一页 ▶", disabled=(page >= total_pages), use_container_width=True):
                st.session_state.page = page + 1
                st.rerun()

start = (page - 1) * PAGE_SIZE
cases = all_cases[start:start + PAGE_SIZE]

# ========== 案件卡片列表 ==========
if not cases:
    st.info("暂无案件")
else:
    for case in cases:
        case_id = case['id']
        artifact_count = artifact_counts.get(case_id, 0)
        health_pct = compute_health(case, artifact_count)["health"]

        status = case.get('status', 'pending')
        status_emoji = "✅" if status == 'extracted' else "📦" if status == 'archived' else "⏳"

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])

            with col1:
                st.subheader(f"{case.get('case_name', '未命名案件')[:50]}")
                st.caption(f"📋 {case.get('case_number', '无案号')}")
                st.caption(f"👤 原告: {case.get('plaintiff', '未知') or '未知'} | 被告: {case.get('defendant', '未知') or '未知'}")
                if case.get('cause'):
                    st.caption(f"⚖️ {case.get('cause')}")

            with col2:
                st.metric("健康度", f"{health_pct}%")

            with col3:
                st.metric("提取物", artifact_count)

            with col4:
                st.markdown(f"**{status_emoji} {status}**")
                if st.button("查看详情", key=f"detail_{case_id}", use_container_width=True):
                    st.session_state.detail_case_id = case_id
                    st.switch_page("pages/2_案件详情.py")

            with col5:
                if status != 'extracted':
                    if st.button("✅ 完成", key=f"complete_{case_id}", use_container_width=True):
                        db.update_case_status(case_id, "extracted")
                        st.rerun()

            st.divider()
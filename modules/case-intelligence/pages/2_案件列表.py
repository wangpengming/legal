# 案件列表页
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth, logout
from src import database as db

require_auth()

st.set_page_config(
    page_title="案例分析 - 案件列表",
    page_icon="📋",
    layout="wide"
)

# 侧边栏
with st.sidebar:
    st.title("📋 导航")
    st.page_link("pages/2_案件列表.py", label="案件列表", icon="📋")
    st.page_link("pages/3_扫描录入.py", label="扫描录入", icon="📁")
    st.page_link("pages/4_文书生成.py", label="文书生成", icon="📝")
    st.page_link("pages/5_统计看板.py", label="统计看板", icon="📊")
    st.divider()
    if st.button("退出登录"):
        logout()
        st.rerun()

st.title("📋 案件列表")

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
all_cases = db.list_cases()
if search:
    all_cases = db.search_cases(search)

if status_filter == "待提取":
    all_cases = [c for c in all_cases if c.get('status') == 'pending']
elif status_filter == "已提取":
    all_cases = [c for c in all_cases if c.get('status') == 'extracted']
elif status_filter == "已归档":
    all_cases = [c for c in all_cases if c.get('status') == 'archived']

if sort_by == "案号":
    all_cases.sort(key=lambda x: x.get('case_number', ''), reverse=True)
elif sort_by == "案由":
    all_cases.sort(key=lambda x: x.get('cause', ''))
elif sort_by == "健康度":
    def calc_health(case):
        score = 0
        if case.get('case_number'): score += 1
        if case.get('plaintiff'): score += 1
        if case.get('defendant'): score += 1
        if case.get('cause'): score += 1
        if case.get('court'): score += 1
        return score
    all_cases.sort(key=calc_health, reverse=True)

total = len(all_cases)
st.caption(f"共找到 **{total}** 个案件")

# ========== 分页 ==========
PAGE_SIZE = 15
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
with page_col1:
    if total_pages > 1:
        page = st.number_input("页码", min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")
    else:
        page = 1

with page_col2:
    if total_pages > 1:
        st.markdown(f"<div style='text-align: center; padding-top: 5px;'>第 {page} / {total_pages} 页</div>", unsafe_allow_html=True)

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
end = start + PAGE_SIZE
cases = all_cases[start:end]

# ========== 案件卡片列表 ==========
if not cases:
    st.info("暂无案件")
else:
    for case in cases:
        case_id = case['id']
        artifacts = db.list_artifacts_by_case(case_id)
        artifact_count = len(artifacts) if artifacts else 0
        
        # 健康度
        score = 0
        if case.get('case_number'): score += 1
        if case.get('plaintiff'): score += 1
        if case.get('defendant'): score += 1
        if case.get('cause'): score += 1
        if case.get('court'): score += 1
        health_pct = int((score / 5) * 100)
        
        status = case.get('status', 'pending')
        status_emoji = "✅" if status == 'extracted' else "📦" if status == 'archived' else "⏳"
        
        with st.container():
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            
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
            
            st.divider()

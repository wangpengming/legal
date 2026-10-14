# 案件匹配页
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth
from ui.nav import render_sidebar
from src import database as db
from src.case_matcher import match_cases

require_auth()

st.set_page_config(
    page_title="案例分析 - 案件匹配",
    page_icon="🔗",
    layout="wide"
)

render_sidebar()

st.title("🔗 案件匹配")
st.caption("基于案由 / 年份 / 场景 / D1–D5 维度覆盖的规则打分（无向量检索）。")

cases = db.list_cases()
case_options = {c['id']: f"{c.get('case_name', '未命名')[:30]} ({c.get('case_number', '无')})" for c in cases}

if not case_options:
    st.info("暂无案件")
    st.stop()

default_case = st.session_state.get("match_case_id")
default_index = list(case_options.keys()).index(default_case) if default_case in case_options else 0

col1, col2 = st.columns([3, 1])
with col1:
    base_id = st.selectbox("📋 基准案件", options=list(case_options.keys()),
                           index=default_index, format_func=lambda x: case_options[x])
with col2:
    limit = st.number_input("返回条数", min_value=1, max_value=50, value=5, step=1)

if st.button("🔍 查找相似案件", type="primary", use_container_width=True):
    st.session_state.match_results = {
        "base_id": base_id,
        "items": match_cases(base_id, limit=int(limit)),
    }

results = st.session_state.get("match_results")
if results and results.get("base_id") == base_id:
    items = results["items"]
    if not items:
        st.info("未找到相似案件（无案由/年份/场景/维度重合信号）")
    else:
        for m in items:
            with st.container():
                c1, c2, c3 = st.columns([5, 1, 1])
                with c1:
                    st.subheader(f"{m['case_name']}")
                    st.caption(f"📋 {m.get('case_number') or '无案号'} | ⚖️ {m.get('cause') or '未知'} | 🗓️ {m.get('year') or '未知'}")
                    if m.get("reasons"):
                        st.caption("匹配依据：" + "；".join(m["reasons"]))
                with c2:
                    st.metric("相似度", f"{m['score']}%")
                with c3:
                    if st.button("查看详情", key=f"mdetail_{m['id']}", use_container_width=True):
                        st.session_state.detail_case_id = m['id']
                        st.switch_page("pages/2_案件详情.py")
                st.divider()
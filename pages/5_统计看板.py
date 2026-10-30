# 统计看板页
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth
from ui.nav import render_sidebar
from ui.utils import get_summary, get_cause_distribution, get_pending_cases
from src import case_service as svc

require_auth()

st.set_page_config(
    page_title="案例分析 - 统计看板",
    page_icon="📊",
    layout="wide"
)

render_sidebar()

st.title("📊 统计看板")

# 统计卡片
summary = get_summary()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📁 案件总数", summary.get('total_cases', 0))
with col2:
    st.metric("✅ 已提取", summary.get('extracted_cases', 0), delta="完整")
with col3:
    st.metric("⏳ 待提取", summary.get('pending_cases', 0), delta="需处理")

st.divider()

# 案由分布
st.subheader("📈 案由分布")
cause_data = get_cause_distribution()

if cause_data:
    max_cnt = max(r[1] for r in cause_data)
    for cause, cnt in cause_data[:10]:
        bar_len = int((cnt / max_cnt) * 30)
        bar = '█' * bar_len
        st.write(f"`{cause[:20]:<20}` {bar} {cnt}")
else:
    st.info("暂无数据")

st.divider()

# 待提取案件
st.subheader("⏳ 待提取案件")
pending = get_pending_cases(10)

if pending:
    for case in pending:
        st.write(f"- **{case.get('case_name', '未命名')[:40]}**")
        st.caption(f"  案号: {case.get('case_number', '无')}")
else:
    st.success("🎉 所有案件已提取完成！")

st.divider()

# 最近操作记录（按入库时间倒序取案件 + 最近写入的提取物）
st.subheader("🕒 最近操作记录")
recent_cases = svc.query_cases(limit=5)
if recent_cases:
    for case in recent_cases:
        st.write(f"- 🗂️ **{case.get('case_name', '未命名')[:40]}** ｜ {case.get('created_at', '')[:19]}")
else:
    st.caption("暂无记录")

recent_artifacts = svc.list_all_artifacts()[:5]
if recent_artifacts:
    st.caption("最近写入的提取物：")
    for art in recent_artifacts:
        st.write(f"  - 📦 {art.get('title', art.get('artifact_type'))}（{art.get('artifact_type')}）｜ {art.get('created_at', '')[:19]}")

st.divider()

# 扫描历史（本次会话，最近 5 条）
st.subheader("📁 扫描历史（本次会话）")
history = st.session_state.get("scan_history", [])
if history:
    for h in history[:5]:
        st.write(f"- {h.get('time', '')} ｜ {h.get('case_name', '未命名')} ｜ {h.get('path', '')}")
else:
    st.caption("暂无扫描记录")

st.divider()

# 提取物统计
st.subheader("📦 提取物统计")
st.write(f"提取物总数: {summary.get('total_artifacts', 0)}")
st.write(f"模板总数: {summary.get('total_templates', 0)}")
# 统计看板页
import streamlit as st
from ui.auth import require_auth, logout
from ui.utils import get_summary, get_cause_distribution, get_pending_cases

require_auth()

st.set_page_config(
    page_title="案例分析 - 统计看板",
    page_icon="📊",
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

# 提取物统计
st.subheader("📦 提取物统计")
st.write(f"提取物总数: {summary.get('total_artifacts', 0)}")
st.write(f"模板总数: {summary.get('total_templates', 0)}")

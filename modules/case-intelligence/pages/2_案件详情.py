# 案件详情页
import streamlit as st
from ui.auth import require_auth, logout

require_auth()

st.set_page_config(
    page_title="案例分析 - 案件详情",
    page_icon="📄",
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

# 获取案件ID
if 'detail_case_id' not in st.session_state:
    st.error("未指定案件，请从案件列表进入")
    st.stop()

case_id = st.session_state.detail_case_id

# 获取案件信息
from src import database as db
case = db.get_case(case_id)

if not case:
    st.error("案件不存在")
    st.stop()

# 页面标题
st.title(f"📄 {case.get('case_name', '案件详情')}")

# 基本信息
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("基本信息")
    st.write(f"**案号**: {case.get('case_number', '无') or '无'}")
    st.write(f"**案由**: {case.get('cause', '无') or '无'}")
    st.write(f"**法院**: {case.get('court', '无') or '无'}")
    st.write(f"**状态**: {case.get('status', 'pending')}")

with col2:
    st.subheader("当事人")
    st.write(f"**原告**: {case.get('plaintiff', '无') or '无'}")
    st.write(f"**被告**: {case.get('defendant', '无') or '无'}")

with col3:
    st.subheader("操作")
    if st.button("📝 生成文书", type="primary", use_container_width=True):
        st.session_state.generate_case_id = case_id
        st.switch_page("pages/4_文书生成.py")
    if st.button("📋 返回列表", use_container_width=True):
        st.switch_page("pages/2_案件列表.py")

st.divider()

# 提取物
st.subheader("📦 提取物 (D1-D5)")
artifacts = db.list_artifacts_by_case(case_id)

if artifacts:
    for art in artifacts:
        art_type = art.get('artifact_type', '未知')
        title = art.get('title', art_type)
        content = art.get('content', '')
        source = art.get('source_ref', '')
        
        with st.expander(f"📋 {title} ({art_type})"):
            st.markdown(content)
            if source:
                st.caption(f"来源: {source[:100]}...")
else:
    st.info("暂无提取物。可通过「扫描录入」功能提取。")

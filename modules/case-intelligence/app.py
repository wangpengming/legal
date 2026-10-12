#!/usr/bin/env python3
# Streamlit 多页应用入口
import streamlit as st
from ui.auth import check_auth

# 页面配置
st.set_page_config(
    page_title="案例分析系统",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 检查登录状态，未登录则跳转登录页
if not check_auth():
    # 直接重定向到登录页
    st.switch_page("pages/1_登录.py")

# 主页面 - 重定向到案件列表
st.title("⚖️ 案例分析系统")
st.success(f"已登录: {st.session_state.username}")

st.info("请从侧边栏选择功能")

# 导航链接
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.page_link("pages/2_案件列表.py", label="📋 案件列表")
with col2:
    st.page_link("pages/3_扫描录入.py", label="📁 扫描录入")
with col3:
    st.page_link("pages/4_文书生成.py", label="📝 文书生成")
with col4:
    st.page_link("pages/5_统计看板.py", label="📊 统计看板")

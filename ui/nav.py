# 页面侧边栏导航（7 页统一入口）
import streamlit as st

from ui.auth import logout

# (页面路径, 标签, 图标)，顺序即展示顺序
NAV_PAGES = [
    ("pages/2_案件列表.py", "案件列表", "📋"),
    ("pages/3_扫描录入.py", "扫描录入", "📁"),
    ("pages/4_文书生成.py", "文书生成", "📝"),
    ("pages/6_模板管理.py", "模板管理", "🧩"),
    ("pages/7_案件匹配.py", "案件匹配", "🔗"),
    ("pages/5_统计看板.py", "统计看板", "📊"),
]


def render_sidebar() -> None:
    """渲染统一侧边栏（导航 + 退出登录）。"""
    with st.sidebar:
        st.title("📋 导航")
        for path, label, icon in NAV_PAGES:
            st.page_link(path, label=label, icon=icon)
        st.divider()
        if st.button("退出登录", use_container_width=True):
            logout()
            st.rerun()
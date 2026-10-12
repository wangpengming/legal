# 登录页
import streamlit as st
from ui.auth import login, check_auth, logout

st.set_page_config(
    page_title="案例分析 - 登录",
    page_icon="🔐",
    layout="centered"
)

# 检查是否已登录
if check_auth():
    st.success(f"已登录: {st.session_state.username}")
    if st.button("退出登录"):
        logout()
        st.rerun()
    st.switch_page("pages/2_案件列表.py")

st.title("🔐 案例分析系统")

with st.form("login_form"):
    username = st.text_input("用户名", placeholder="admin")
    password = st.text_input("密码", type="password", placeholder="admin123")
    submit = st.form_submit_button("登录")
    
    if submit:
        if not username or not password:
            st.error("请输入用户名和密码")
        elif login(username, password):
            st.success("登录成功")
            st.rerun()
        else:
            st.error("用户名或密码错误")

st.divider()
st.caption("默认账号: admin/admin123 或 test/test123")

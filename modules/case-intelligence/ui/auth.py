# 登录认证模块
import streamlit as st
from config import USERS

def check_auth():
    """检查是否已登录"""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
    return st.session_state.logged_in

def require_auth():
    """要求登录，未登录则跳转登录页"""
    if not check_auth():
        st.warning("请先登录")
        st.switch_page("pages/1_登录.py")

def login(username: str, password: str) -> bool:
    """验证登录"""
    if username in USERS and USERS[username] == password:
        st.session_state.logged_in = True
        st.session_state.username = username
        return True
    return False

def logout():
    """登出"""
    st.session_state.logged_in = False
    st.session_state.username = None

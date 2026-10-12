# 文书生成页
import streamlit as st
import sys
from pathlib import Path
from ui.auth import require_auth, logout
from src import database as db

require_auth()

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="案例分析 - 文书生成",
    page_icon="📝",
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

st.title("📝 文书生成")

# 文书类型
DOC_TYPES = {
    "defense": "答辩状",
    "evidence_objection": "质证意见",
    "court_statement": "当庭陈述",
    "evidence_index": "证据目录",
}

# 获取案件列表
cases = db.list_cases()
case_options = {c['id']: f"{c.get('case_name', '未命名')[:30]} ({c.get('case_number', '无')})" for c in cases}

col1, col2 = st.columns([1, 1])
with col1:
    selected_case_id = st.selectbox("📋 选择案件", options=list(case_options.keys()), format_func=lambda x: case_options[x])

with col2:
    doc_type = st.selectbox("📄 文书类型", options=list(DOC_TYPES.keys()), format_func=lambda x: DOC_TYPES[x])

# 生成按钮
if st.button("🤖 生成文书", type="primary", use_container_width=True):
    if not selected_case_id:
        st.error("请选择案件")
    else:
        case = db.get_case(selected_case_id)
        if not case:
            st.error("案件不存在")
        else:
            with st.spinner("🤖 AI生成中..."):
                try:
                    from src.langchain_llm import generate_direct
                    
                    case_info = {
                        'case_number': case.get('case_number', ''),
                        'plaintiff': case.get('plaintiff', ''),
                        'defendant': case.get('defendant', ''),
                        'cause': case.get('cause', ''),
                        'court': case.get('court', ''),
                    }
                    
                    content = generate_direct(case_info, doc_type)
                    
                    # 保存到session
                    st.session_state.generated_content = content
                    st.session_state.generated_case = case
                    st.session_state.generated_doc_type = doc_type
                    
                    st.success("✅ 生成成功！")
                    
                except Exception as e:
                    st.error(f"生成失败: {str(e)}")

# 预览区域
if 'generated_content' in st.session_state:
    st.divider()
    st.subheader(f"📄 {DOC_TYPES.get(st.session_state.generated_doc_type, '文书')} 预览")
    
    # 预览
    st.markdown(st.session_state.generated_content)
    
    # 导出
    st.divider()
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("📥 导出为DOCX", use_container_width=True):
            try:
                from docx import Document
                import tempfile
                
                doc = Document()
                doc.add_heading(DOC_TYPES.get(st.session_state.generated_doc_type, '文书'), 0)
                doc.add_paragraph(st.session_state.generated_content)
                
                # 保存到临时文件
                with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
                    doc.save(f.name)
                    st.session_state.download_file = f.name
                
                with open(f.name, 'rb') as f:
                    st.download_button(
                        "⬇️ 下载DOCX",
                        f.read(),
                        file_name=f"{st.session_state.generated_case.get('case_number', '文书')}_{DOC_TYPES.get(st.session_state.generated_doc_type, '文书')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                
            except Exception as e:
                st.error(f"导出失败: {str(e)}")
    
    with col2:
        st.download_button(
            "📄 导出为MD",
            st.session_state.generated_content,
            file_name=f"{st.session_state.generated_case.get('case_number', '文书')}_{DOC_TYPES.get(st.session_state.generated_doc_type, '文书')}.md",
            mime="text/markdown",
            use_container_width=True
        )

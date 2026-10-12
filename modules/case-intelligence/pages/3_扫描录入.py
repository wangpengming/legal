# 扫描录入页
import streamlit as st
from ui.auth import require_auth, logout
from ui.utils import scan_and_import

require_auth()

st.set_page_config(
    page_title="案例分析 - 扫描录入",
    page_icon="📁",
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

st.title("📁 扫描录入")

st.info("""
**使用说明：**
1. 输入案件材料所在目录路径
2. 点击"开始扫描"按钮
3. 系统将自动解析文件并调用AI提取
4. 确认无误后点击"确认导入"
""")

# 路径输入
path = st.text_input("📂 案件目录路径", placeholder="/Users/xxx/案件材料/2024粤0305民初1234号")

col1, col2 = st.columns([1, 1])
with col1:
    scan_button = st.button("🔍 开始扫描", type="primary", use_container_width=True)
with col2:
    st.button("📁 选择文件夹", disabled=True)

# 扫描结果展示
if 'scan_result' in st.session_state:
    result = st.session_state.scan_result
    st.success(f"✅ 扫描完成，发现 {len(result.get('files', []))} 个文件")
    
    with st.expander("📄 文件列表", expanded=True):
        for f in result.get('files', [])[:10]:
            st.write(f"- {f.get('name', '未知')} ({f.get('category', '其他')})")
        if len(result.get('files', [])) > 10:
            st.write(f"... 还有 {len(result.get('files', [])) - 10} 个文件")

# 扫描并导入
if scan_button and path:
    if not path.strip():
        st.error("请输入目录路径")
    else:
        with st.spinner("🔍 扫描中..."):
            try:
                # 扫描
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from src import scanner, parser, extractor, importer
                
                scan_path = Path(path).resolve()
                if not scan_path.exists():
                    st.error(f"目录不存在: {path}")
                else:
                    # 扫描目录
                    scan_result = scanner.scan_directory(scan_path)
                    
                    # 解析文件
                    parsed = parser.parse_files(scan_result.files)
                    
                    if not parsed:
                        st.warning("未发现可解析的文件")
                    else:
                        # AI提取
                        with st.spinner("🤖 AI提取中..."):
                            extracted = extractor.extract_case(
                                contents=parsed,
                                case_name=scan_result.case_name,
                                engine_type="minimax"
                            )
                        
                        st.session_state.scan_result = {
                            'files': scan_result.files,
                            'case_name': scan_result.case_name,
                            'extracted': extracted,
                            'path': path
                        }
                        st.rerun()
                        
            except Exception as e:
                st.error(f"扫描失败: {str(e)}")

# 确认导入
if 'scan_result' in st.session_state and st.session_state.scan_result:
    result = st.session_state.scan_result
    
    st.divider()
    st.subheader("📋 导入预览")
    
    extracted = result.get('extracted')
    if extracted:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.write(f"**案件名称**: {extracted.case_name or '未命名'}")
            st.write(f"**案号**: {extracted.case_number or '待补充'}")
        with col2:
            st.write(f"**案由**: {extracted.cause or '待补充'}")
            st.write(f"**法院**: {extracted.court or '待补充'}")
        
        if st.button("✅ 确认导入", type="primary", use_container_width=True):
            with st.spinner("📥 导入中..."):
                try:
                    sys.path.insert(0, str(Path(__file__).parent.parent))
                    from src import importer
                    
                    imp = importer.CaseImporter()
                    import_result = imp.import_full(extracted)
                    
                    st.success(f"✅ 导入成功！案件ID: {import_result['case_id']}")
                    del st.session_state.scan_result
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败: {str(e)}")
        
        if st.button("❌ 取消", use_container_width=True):
            del st.session_state.scan_result
            st.rerun()

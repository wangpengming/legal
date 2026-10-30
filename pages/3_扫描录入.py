# 扫描录入页
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth
from ui.nav import render_sidebar
from ui.utils import ENGINE_OPTIONS, DEFAULT_ENGINE
from src import scanner, parser, extractor, importer
from src import case_service as svc

require_auth()

st.set_page_config(
    page_title="案例分析 - 扫描录入",
    page_icon="📁",
    layout="wide"
)

render_sidebar()

st.title("📁 扫描录入")

st.info("""
**使用说明：**
1. 输入案件材料所在目录路径
2. 点击"开始扫描"按钮
3. 系统将自动解析文件并调用AI提取
4. 确认无误后点击"确认导入"
""")

# 路径输入
path = st.text_input("📂 案件目录路径", placeholder="/path/to/案件材料/2024粤0305民初1234号")
st.caption("提示：请直接粘贴服务器上可访问的绝对路径（浏览器无法读取本地文件夹）。")

col1, col2 = st.columns([1, 1])
with col1:
    scan_button = st.button("🔍 开始扫描", type="primary", use_container_width=True)
with col2:
    engine = st.selectbox("🤖 AI 引擎", options=ENGINE_OPTIONS,
                          index=ENGINE_OPTIONS.index(DEFAULT_ENGINE))

# 扫描并解析 + AI 提取 + 查重
if scan_button and path:
    if not path.strip():
        st.error("请输入目录路径")
    else:
        with st.spinner("🔍 扫描中..."):
            try:
                scan_path = Path(path).resolve()
                if not scan_path.exists():
                    st.error(f"目录不存在: {path}")
                else:
                    scan_result = scanner.scan_directory(scan_path)
                    parsed = parser.parse_files(scan_result.files)
                    if not parsed:
                        st.warning("未发现可解析的文件")
                    else:
                        with st.spinner("🤖 AI提取中..."):
                            extracted = extractor.extract_case(
                                contents=parsed,
                                case_name=scan_result.case_name,
                                engine_type=engine,
                            )
                        # C3 查重（案号/当事人/案由）
                        plaintiff = extracted.plaintiffs[0].name if extracted.plaintiffs else ""
                        defendant = extracted.defendants[0].name if extracted.defendants else ""
                        dupe = svc.check_duplicate({
                            "case_number": extracted.case_number,
                            "plaintiff": plaintiff,
                            "defendant": defendant,
                            "cause": extracted.cause or "",
                        })
                        st.session_state.scan_result = {
                            'files': scan_result.files,
                            'case_name': scan_result.case_name,
                            'extracted': extracted,
                            'path': path,
                            'engine': engine,
                            'dupe': dupe,
                        }
                        # 记录扫描历史（本次会话，看板展示）
                        hist = st.session_state.get("scan_history", [])
                        hist.insert(0, {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "case_name": scan_result.case_name,
                            "path": path,
                        })
                        st.session_state.scan_history = hist[:10]
                        st.rerun()
            except Exception as e:
                st.error(f"扫描失败: {str(e)}")

# 扫描结果展示
if 'scan_result' in st.session_state:
    result = st.session_state.scan_result
    st.success(f"✅ 扫描完成，发现 {len(result.get('files', []))} 个文件")
    with st.expander("📄 文件列表", expanded=True):
        for f in result.get('files', [])[:10]:
            st.write(f"- {f.get('name', '未知')} ({f.get('category', '其他')})")
        if len(result.get('files', [])) > 10:
            st.write(f"... 还有 {len(result.get('files', [])) - 10} 个文件")

# 确认导入
if 'scan_result' in st.session_state and st.session_state.scan_result:
    result = st.session_state.scan_result
    extracted = result.get('extracted')

    st.divider()
    st.subheader("📋 导入预览")

    if extracted:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.write(f"**案件名称**: {extracted.case_name or '未命名'}")
            st.write(f"**案号**: {extracted.case_number or '待补充'}")
        with col2:
            st.write(f"**案由**: {extracted.cause or '待补充'}")
            st.write(f"**法院**: {extracted.court or '待补充'}")

        dupe = result.get('dupe') or {}
        allow_import = True
        if dupe.get('exact'):
            c = dupe['exact']
            st.error(f"⚠️ 案号已存在：{c['case_name']}（{c['case_number']}）")
            allow_import = st.checkbox("仍要导入为新案件")
        elif dupe.get('partial'):
            names = "、".join(x['case_name'] for x in dupe['partial'][:3])
            st.warning(f"⚠️ 当事人匹配到已有案件：{names}")
            allow_import = st.checkbox("仍要导入为新案件")

        if st.button("✅ 确认导入", type="primary", use_container_width=True,
                     disabled=not allow_import):
            with st.spinner("📥 导入中..."):
                try:
                    imp = importer.CaseImporter()
                    import_result = imp.import_full(
                        extracted,
                        generation_method=svc.ENGINE_GENERATION_METHOD.get(result.get('engine', ''), ""),
                    )
                    st.success(f"✅ 导入成功！案件ID: {import_result['case_id']}")
                    del st.session_state.scan_result
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败: {str(e)}")

        if st.button("❌ 取消", use_container_width=True):
            del st.session_state.scan_result
            st.rerun()
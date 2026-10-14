# 扫描录入页
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth
from ui.nav import render_sidebar
from ui.utils import ENGINE_OPTIONS, DEFAULT_ENGINE
from src import scanner, parser, extractor, importer, case_recognizer as cr, upload_ingest

require_auth()

st.set_page_config(
    page_title="案例分析 - 扫描录入",
    page_icon="📁",
    layout="wide"
)

render_sidebar()

st.title("📁 扫描录入")

# 引擎 → generation_method（与 bin/extract.py 对齐）
ENGINE_GENERATION_METHOD = {
    "minimax": "llm", "ollama": "llm", "openai": "llm",
    "mock": "mock", "basic": "rule-based",
}


def run_scan(scan_path: Path, engine: str, source_desc: str) -> None:
    """扫描 + 解析 + AI 提取 + 查重，结果写入 session_state（上传/路径双源共用）。"""
    scan_result = scanner.scan_directory(scan_path)
    parsed = parser.parse_files(scan_result.files)
    if not parsed:
        st.warning(f"未发现可解析的文件（支持 pdf/docx/txt/md）: {scan_path}")
        return
    with st.spinner("🤖 AI提取中..."):
        extracted = extractor.extract_case(
            contents=parsed,
            case_name=scan_result.case_name,
            engine_type=engine,
        )
    # C3 查重（案号/当事人/案由）
    plaintiff = extracted.plaintiffs[0].name if extracted.plaintiffs else ""
    defendant = extracted.defendants[0].name if extracted.defendants else ""
    dupe = cr.recognize_case(
        case_number=extracted.case_number,
        plaintiff=plaintiff,
        defendant=defendant,
        cause=extracted.cause or "",
    )
    st.session_state.scan_result = {
        'files': scan_result.files,
        'case_name': scan_result.case_name,
        'extracted': extracted,
        'path': str(scan_path),
        'engine': engine,
        'dupe': dupe,
    }
    # 记录扫描历史（本次会话，看板展示）
    hist = st.session_state.get("scan_history", [])
    hist.insert(0, {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "case_name": scan_result.case_name,
        "path": source_desc,
    })
    st.session_state.scan_history = hist[:10]
    st.rerun()


# 引擎选择（上传/路径双签共用）
engine = st.selectbox("🤖 AI 引擎", options=ENGINE_OPTIONS,
                      index=ENGINE_OPTIONS.index(DEFAULT_ENGINE))

# 待生成引导（F2：导入成功 → 一键去生成）
if st.session_state.get("pending_generate"):
    pg = st.session_state.pending_generate
    card = st.container(border=True)
    with card:
        st.success(f"✅ 案件已导入：{pg.get('case_name') or pg.get('case_id')}")
        c1, c2 = st.columns([1, 3])
        with c1:
            st.page_link("pages/4_文书生成.py", label="📝 去生成文书", icon="📝")
        with c2:
            if st.button("✖ 关闭提示"):
                st.session_state.pop("pending_generate", None)
                st.rerun()

tab_upload, tab_path = st.tabs(["📤 上传文件（推荐）", "📂 服务器路径"])

with tab_upload:
    st.info("""
**上传说明：**
1. 上传案件材料文件（pdf / docx / txt / md），可多选
2. 文件夹请打包成 ZIP 后上传（系统自动解压识别）
3. 点击"开始扫描"，系统自动解析并调用 AI 提取
""")
    uploaded_files = st.file_uploader(
        "选择文件（多选）或 ZIP 包",
        type=["pdf", "docx", "doc", "txt", "md", "zip"],
        accept_multiple_files=True,
    )
    if st.button("🔍 开始扫描（上传）", type="primary", use_container_width=True):
        if not uploaded_files:
            st.error("请先选择要上传的文件")
        else:
            try:
                items = [upload_ingest.UploadItem(name=f.name, data=f.getvalue())
                         for f in uploaded_files]
                with st.spinner("📥 上传解压中..."):
                    batch = upload_ingest.ingest_uploads(items)
                with st.spinner("🔍 扫描中..."):
                    run_scan(batch, engine, "上传: " + ", ".join(f.name for f in uploaded_files))
            except upload_ingest.UploadError as e:
                st.error(f"上传处理失败: {e}")
            except Exception as e:
                st.error(f"扫描失败: {str(e)}")

with tab_path:
    st.info("""
**路径说明（管理员兜底）：**
1. 输入案件材料所在目录的服务器绝对路径
2. 点击"开始扫描"按钮
""")
    path = st.text_input("📂 案件目录路径", placeholder="/data/案件材料/2024粤0305民初1234号",
                         key="server_path_input")
    st.caption("提示：浏览器无法读取本地文件夹，此方式需文件已在服务器上。")
    if st.button("🔍 开始扫描（路径）", use_container_width=True):
        if not path.strip():
            st.error("请输入目录路径")
        else:
            try:
                scan_path = Path(path).resolve()
                if not scan_path.exists():
                    st.error(f"目录不存在: {path}")
                else:
                    with st.spinner("🔍 扫描中..."):
                        run_scan(scan_path, engine, path)
            except Exception as e:
                st.error(f"扫描失败: {str(e)}")

# 扫描结果展示
if 'scan_result' in st.session_state:
    result = st.session_state.scan_result
    st.success(f"✅ 扫描完成，发现 {len(result.get('files', []))} 个文件")
    with st.expander("📄 文件列表", expanded=True):
        for f in result.get('files', [])[:10]:
            # 兼容 FileInfo 对象（scanner）与 dict（历史 session 数据）
            if isinstance(f, dict):
                name, cat = f.get('name', '未知'), f.get('category', '其他')
            else:
                name = getattr(f, 'name', '未知')
                cat_enum = getattr(f, 'category', None)
                cat = getattr(cat_enum, 'value', '其他') if cat_enum else '其他'
            st.write(f"- {name} ({cat})")
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
                        generation_method=ENGINE_GENERATION_METHOD.get(result.get('engine', ''), ""),
                    )
                    # F2：携带 case_id 直达文书生成页（session_state 传递，勿用全局变量）
                    st.session_state.generate_case_id = import_result['case_id']
                    st.session_state.pending_generate = {
                        "case_id": import_result['case_id'],
                        "case_name": extracted.case_name,
                    }
                    st.success(f"✅ 导入成功！案件ID: {import_result['case_id']}")
                    del st.session_state.scan_result
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败: {str(e)}")

        if st.button("❌ 取消", use_container_width=True):
            del st.session_state.scan_result
            st.rerun()
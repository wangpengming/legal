"""Streamlit 浏览器内 PDF 预览组件（PDF.js 全内联方案）。

技术选型理由（SPEC §9）：
- Streamlit SPA 路由拦截所有 /static/ 路径 → 直接 HTTP 加载 PDF.js 失败
- sandboxed iframe 不能访问外部 CDN → PDF.js CDN 不可用
- 唯一可行：把 PDF.js + PDF 文件都用 base64 data URI 内联到 HTML

关键陷阱（必须必须遵守，参考 common_pitfalls/Streamlit_components.html_PDF.js_三重根因）：
- ❌ 不能用 `new Function(mainCode)` → `var pdfjsLib` 不会泄漏到外层作用域
- ✅ 必须用 inline `<script>eval(atob(mainB64))</script>` → 让 var 暴露到当前作用域

降级方案：browser 渲染失败时，提供"系统 Preview 打开"按钮（macOS 走 open 命令）。
"""
import base64
import platform
import subprocess
from functools import lru_cache
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# PDF.js 库路径（必须由相关人员下载到此处）
PDFJS_DIR = Path(__file__).resolve().parent / "static" / "pdfjs"
PDFJS_MAIN = PDFJS_DIR / "pdf.min.js"
PDFJS_WORKER = PDFJS_DIR / "pdf.worker.min.js"


# ============================================================
# PDF.js 库加载（base64 缓存）
# ============================================================

@st.cache_resource(show_spinner=False)
def _load_pdfjs_libs() -> tuple[str, str] | None:
    """加载 PDF.js 主库 + worker 的 base64 字符串。

    返回 (main_b64, worker_b64) 或 None（库文件未就位时）。

    用 @st.cache_resource：
    - 进程内只编码一次（避免每次重编码 320KB+1MB 文本）
    - 文件变更时需重启服务才会刷新
    """
    if not (PDFJS_MAIN.exists() and PDFJS_WORKER.exists()):
        return None
    main_b64 = base64.b64encode(PDFJS_MAIN.read_bytes()).decode("ascii")
    worker_b64 = base64.b64encode(PDFJS_WORKER.read_bytes()).decode("ascii")
    return main_b64, worker_b64


def is_pdfjs_ready() -> bool:
    """检查 PDF.js 库是否就绪（用于 UI 提示）。"""
    return _load_pdfjs_libs() is not None


# ============================================================
# 系统 PDF 阅读器降级（macOS Preview / Windows 默认 / Linux xdg-open）
# ============================================================

def open_in_system_viewer(pdf_path: Path) -> None:
    """调用系统默认 PDF 阅读器。

    安全：使用列表参数而非 shell=True，避免命令注入。
    macOS: open
    Windows: os.startfile（走 ShellExecute，绕开 shell 解析）
    Linux: xdg-open
    """
    import os

    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", str(pdf_path)])
    elif system == "Windows":
        os.startfile(str(pdf_path))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(pdf_path)])


# ============================================================
# Streamlit 组件：渲染 PDF 预览
# ============================================================

def render_pdf_viewer(pdf_path: Path, height: int = 800, key: str | None = None) -> None:
    """在 Streamlit 中渲染 PDF 预览（缩放/翻页/打印）。

    参数：
        pdf_path: PDF 文件路径
        height: iframe 高度（px）
        key: 组件唯一 key（多次渲染同一 PDF 时需要不同 key）
    """
    libs = _load_pdfjs_libs()
    if libs is None:
        st.error(
            "❌ PDF.js 库未就绪。请先到 `static/pdfjs/` 下载 pdf.min.js + pdf.worker.min.js\n\n"
            "详见 [static/README.md](../README.md) §4"
        )
        _render_fallback_button(pdf_path)
        return

    if not pdf_path.exists():
        st.error(f"❌ PDF 文件不存在：{pdf_path}")
        return

    main_b64, worker_b64 = libs
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")

    # ⚠️ 关键：HTML 中嵌入 PDF 内容（浏览器内完整渲染）
    html = _build_pdf_html(main_b64, worker_b64, pdf_b64, height)
    components.html(html, height=height + 80, scrolling=False)

    # 降级按钮：浏览器内渲染失败时可手动打开系统阅读器
    _render_fallback_button(pdf_path)


def _build_pdf_html(
    main_b64: str,
    worker_b64: str,
    pdf_b64: str,
    height: int,
) -> str:
    """构建 PDF.js 全内联 HTML 字符串。

    ⚠️ 修改时必须遵守的三条铁律（参考 SPEC §9.3）：
    1. Worker 用 Blob URL 注入（不是 src URL，否则跨域 CSP 拦截）
    2. 主库必须 `<script>eval(atob(mainB64))</script>`（不能 new Function）
    3. PDF 数据用 `atob()` 传入（不能 URL 走 HTTP，否则 SPA 拦截）
    """
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f5f5f5;
  }}
  #toolbar {{
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px;
    background: #ffffff;
    border-bottom: 1px solid #e5e5e5;
    position: sticky; top: 0; z-index: 10;
  }}
  #toolbar button {{
    padding: 4px 12px;
    border: 1px solid #d4d4d4;
    background: #ffffff;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
  }}
  #toolbar button:hover {{ background: #f0f0f0; border-color: #0a0a0a; }}
  #toolbar button:active {{ background: #e5e5e5; }}
  #page-info {{ font-size: 13px; color: #525252; min-width: 70px; text-align: center; }}
  #toolbar .spacer {{ flex: 1; }}
  #toolbar .print-btn {{
    background: #0a0a0a; color: white; border-color: #0a0a0a;
  }}
  #toolbar .print-btn:hover {{ background: #262626; }}
  #pdf-container {{
    overflow: auto;
    height: {height}px;
    background: #525252;
    padding: 16px;
  }}
  .page-wrap {{
    margin: 0 auto 16px;
    background: white;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    display: flex; justify-content: center;
  }}
  canvas {{ display: block; max-width: 100%; }}
  @media print {{
    #toolbar {{ display: none !important; }}
    body {{ background: white; }}
    #pdf-container {{ overflow: visible; height: auto; background: white; padding: 0; }}
    .page-wrap {{ box-shadow: none; margin: 0; page-break-after: always; }}
    .page-wrap:last-child {{ page-break-after: auto; }}
  }}
</style>
</head>
<body>

<div id="toolbar">
  <button onclick="zoom(-0.1)" title="缩小">➖</button>
  <button onclick="zoom(0.1)" title="放大">➕</button>
  <span class="spacer"></span>
  <button onclick="printAll()" class="print-btn" title="打印整套 PDF（弹系统打印界面）">🖨 打印全部</button>
</div>

<div id="pdf-container"></div>

<!-- 1️⃣ Worker Blob URL 注入（避开 CDN/CSP 拦截） -->
<script>
  const workerBlob = new Blob(
    [Uint8Array.from(atob('{worker_b64}'), c => c.charCodeAt(0))],
    {{ type: 'application/javascript' }}
  );
  window.__pdfjsWorkerUrl = URL.createObjectURL(workerBlob);
</script>

<!-- 2️⃣ ⚠️ 主库必须用 eval(atob(...))，不能用 new Function（var pdfjsLib 泄漏） -->
<!-- noqa: S102  # 安全：PDF.js 库来自项目内 static/pdfjs/ 目录，受版本控制，非用户输入 -->
<script>eval(atob('{main_b64}'))</script>

<!-- 3️⃣ PDF 数据 atob() 传入（不走 URL，避开 SPA 路由） -->
<script>
  let pdfDoc = null;
  let currentPage = 1;
  let scale = 1.2;
  const container = document.getElementById('pdf-container');
  const pageInfo = document.getElementById('page-info');

  // 把 Worker URL 注入 pdfjsLib
  if (window.pdfjsLib && window.__pdfjsWorkerUrl) {{
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = window.__pdfjsWorkerUrl;
  }}

  function renderPage(num) {{
    if (!pdfDoc) return;
    pdfDoc.getPage(num).then(page => {{
      const viewport = page.getViewport({{ scale: scale }});
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const wrap = document.createElement('div');
      wrap.className = 'page-wrap';
      wrap.id = 'page-' + num;
      wrap.appendChild(canvas);
      container.innerHTML = '';
      container.appendChild(wrap);
      page.render({{ canvasContext: ctx, viewport: viewport }});
      pageInfo.textContent = num + ' / ' + pdfDoc.numPages;
    }});
  }}

  function renderAllPages() {{
    // 整篇 PDF 连续滚动（一次性渲染所有页）
    if (!pdfDoc) return;
    container.innerHTML = '';
    const promises = [];
    for (let i = 1; i <= pdfDoc.numPages; i++) {{
      promises.push(renderPageToContainer(i));
    }}
    Promise.all(promises).then(() => {{}});
  }}

  function renderPageToContainer(num) {{
    return pdfDoc.getPage(num).then(page => {{
      const viewport = page.getViewport({{ scale: scale }});
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const wrap = document.createElement('div');
      wrap.className = 'page-wrap';
      wrap.id = 'page-' + num;
      wrap.appendChild(canvas);
      container.appendChild(wrap);
      return page.render({{ canvasContext: ctx, viewport: viewport }}).promise;
    }});
  }}

  function zoom(delta) {{
    scale = Math.max(0.5, Math.min(3.0, scale + delta));
    renderPage(currentPage);
  }}

  function prevPage() {{
    if (currentPage > 1) {{ currentPage--; renderPage(currentPage); }}
  }}

  function nextPage() {{
    if (pdfDoc && currentPage < pdfDoc.numPages) {{ currentPage++; renderPage(currentPage); }}
  }}

  function printAll() {{
    // 渲染所有页到隐藏 iframe，触发打印
    // 简化：用 window.print()，CSS @media print 已隐藏工具栏
    window.print();
  }}

  // 启动
  // v1.1.3：PDF 二进制转 Uint8Array（与 worker Blob 一致），避免部分版本字符串载入异常
  // 注意：{{ }} 是 f-string 转义，避免被误当作格式规范（见 v1.1.3 修复 NameError: data）
  const pdfBytes = Uint8Array.from(atob('{pdf_b64}'), c => c.charCodeAt(0));
  window.pdfjsLib.getDocument({{ data: pdfBytes }}).promise
    .then(pdf => {{
      pdfDoc = pdf;
      currentPage = 1;
      renderAllPages();
    }})
    .catch(err => {{
      container.innerHTML = '<div style="padding:40px;color:#ef4444;font-size:14px;">'
        + '❌ PDF 加载失败：' + (err && err.message ? err.message : err)
        + '</div>';
    }});
</script>

</body>
</html>"""


def _render_fallback_button(pdf_path: Path) -> None:
    """降级按钮：调系统 PDF 阅读器。"""
    btn_label = {
        "Darwin": "🖥 系统 Preview 打开（macOS）",
        "Windows": "🖥 系统阅读器打开（Windows）",
        "Linux": "🖥 系统阅读器打开（Linux）",
    }.get(platform.system(), "🖥 系统阅读器打开")

    if st.button(btn_label, key=f"open_sys_{pdf_path.name}"):
        try:
            open_in_system_viewer(pdf_path)
            st.success(f"✅ 已调用系统阅读器：{pdf_path.name}")
        except Exception as e:  # noqa: BLE001
            st.error(f"❌ 系统阅读器启动失败：{e}")
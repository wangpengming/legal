# =============================================
# test_scan_page_pipeline.py — 上传 → 管道 → 入库集成测试
# 对应 SPEC：docs/SPEC-ui-upload.md §8（全链 mock 引擎）
# =============================================
import io
import sys
import zipfile
from pathlib import Path

import pytest

# 包导入（parser/importer 内部使用相对导入，顶层名加载会失败）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.upload_ingest import UploadItem, ingest_uploads
from src.scanner import scan_directory
from src.parser import parse_files
from src.extractor import extract_case
from src.case_recognizer import recognize_case
from src.importer import CaseImporter
from src.database import get_case

PLIFFING_TEXT = """民事起诉状

原告：张三
被告：李四

原告与被告因合同纠纷一案，现提起诉讼。
请求判令被告支付货款人民币 10 万元。
事实与理由：被告于 2024 年 3 月与原告签订供货合同，
原告已依约交付货物，被告拒不付款。
案号：（2024）京0105民初12345号
"""


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_full_pipeline_from_uploaded_zip(tmp_path):
    """上传 ZIP → 落盘 → 扫描 → 解析 → 提取(mock) → 查重 → 导入 → 可检索。"""
    zip_bytes = _make_zip({"(2024)京0105民初12345号/起诉状.txt": PLIFFING_TEXT.encode("utf-8")})

    # 步骤 1-2：上传落盘（产出与服务器路径一致的普通目录）
    batch = ingest_uploads(
        [UploadItem(name="案件材料.zip", data=zip_bytes)],
        base_dir=tmp_path / "inbox",
    )

    # 步骤 3-4：扫描 + 解析
    scan = scan_directory(batch)
    assert len(scan.files) == 1
    parsed = parse_files(scan.files)
    assert len(parsed) == 1
    assert "起诉" in parsed[0].text  # 内容如实解析

    # 步骤 5：AI 提取（mock 引擎）
    extracted = extract_case(contents=parsed, case_name=scan.case_name, engine_type="mock")
    assert extracted.case_number == "2026京XX民初XXXXX号"
    assert extracted.d1_facts is not None  # 五维度齐全

    # 步骤 6：查重（复用页面同款参数）
    plaintiff = extracted.plaintiffs[0].name if extracted.plaintiffs else ""
    defendant = extracted.defendants[0].name if extracted.defendants else ""
    dupe = recognize_case(
        case_number=extracted.case_number,
        plaintiff=plaintiff,
        defendant=defendant,
        cause=extracted.cause or "",
    )
    assert isinstance(dupe, dict)

    # 步骤 7：导入（隔离库）
    db_path = tmp_path / "pipeline.db"
    result = CaseImporter(db_path=db_path).import_full(extracted, generation_method="mock")
    assert result["case_id"]

    # 步骤 8：可检索
    case = get_case(result["case_id"], db_path)
    assert case is not None
    assert case["case_number"] == "2026京XX民初XXXXX号"
    assert "腾讯音乐" in case["plaintiff"]


def test_pipeline_rejects_empty_zip_gracefully(tmp_path):
    """空 ZIP → 落盘成功但扫描无文件，管道不崩溃。"""
    batch = ingest_uploads(
        [UploadItem(name="空.zip", data=_make_zip({}))],
        base_dir=tmp_path / "inbox",
    )
    scan = scan_directory(batch)
    assert scan.files == []


def test_page_renders_file_list_for_fileinfo_objects(monkeypatch):
    """页面文件列表渲染兼容 FileInfo 对象（回归：AttributeError 'FileInfo' object has no attribute 'get'）。"""
    from datetime import datetime

    from streamlit.testing.v1 import AppTest
    from src.scanner import FileCategory, FileInfo, FileType

    # AppTest 无多页 entrypoint，st.page_link 不可用 → 跳过侧边栏渲染
    import ui.nav as nav_module
    monkeypatch.setattr(nav_module, "render_sidebar", lambda: None)

    at = AppTest.from_file(
        str(_PROJECT_ROOT / "pages" / "3_扫描录入.py"),
        default_timeout=30,
    )
    at.session_state["logged_in"] = True
    at.session_state["username"] = "e2e_test"
    at.session_state["scan_result"] = {
        "files": [
            FileInfo(
                path=Path("/tmp/起诉状.txt"),
                type=FileType.TXT,
                category=FileCategory.PLIFFING_STATEMENT,
                size=1024,
                modified=datetime(2026, 1, 1),
            )
        ],
        "case_name": "测试案件",
        "extracted": None,
        "path": "/tmp",
        "engine": "mock",
        "dupe": {},
    }
    at.run()
    assert not at.exception
    names = [el.value for el in at.markdown if isinstance(el.value, str)]
    assert any("起诉状.txt" in n for n in names)

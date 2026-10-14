# =============================================
# test_upload_ingest.py — 上传落盘/ZIP 解压安全（TDD）
# 对应 SPEC：docs/SPEC-ui-upload.md §3 / §8
# =============================================
import io
import zipfile
from pathlib import Path

import pytest

from upload_ingest import (
    SizeLimitExceededError,
    UploadError,
    UploadItem,
    ZipExtractError,
    PathTraversalError,
    ingest_uploads,
)

SUPPORTED = {".pdf", ".doc", ".docx", ".txt", ".md"}


# ---------- helpers ----------

def make_zip_bytes(entries: dict[str, bytes], *, unix_symlink: str | None = None) -> bytes:
    """构造 ZIP bytes。unix_symlink 传入 entry 名，写为符号链接。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
        if unix_symlink:
            info = zipfile.ZipInfo(unix_symlink)
            info.create_system = 3  # unix
            info.external_attr = 0o120777 << 16  # symlink 文件权限
            z.writestr(info, "/etc/passwd")
    return buf.getvalue()


def _files_under(root: Path) -> set[Path]:
    """root 下所有文件的相对路径集合。"""
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


# ---------- 单文件落盘 ----------

def test_single_file_lands_in_batch_dir(tmp_path):
    base = tmp_path / "inbox"
    batch = ingest_uploads([UploadItem(name="起诉状.pdf", data=b"%PDF-1.4 fake")], base_dir=base)

    assert batch.exists()
    assert _files_under(batch) == {Path("起诉状.pdf")}


def test_single_file_rejects_non_whitelist_ext(tmp_path):
    with pytest.raises(UploadError):
        ingest_uploads([UploadItem(name="evil.exe", data=b"MZ")], base_dir=tmp_path)


def test_single_file_name_strips_parent_traversal(tmp_path):
    """上传文件名含 ../ 时只取 basename，不得写出 base_dir 之外。"""
    batch = ingest_uploads([UploadItem(name="../escaping.pdf", data=b"x")], base_dir=tmp_path / "inbox")
    assert _files_under(batch) == {Path("escaping.pdf")}
    assert not (tmp_path / "escaping.pdf").exists()


def test_multiple_mixed_files_shared_batch_dir(tmp_path):
    base = tmp_path / "inbox"
    batch = ingest_uploads(
        [
            UploadItem(name="起诉状.pdf", data=b"a"),
            UploadItem(name="证据材料.zip", data=make_zip_bytes({"账单.txt": b"b", "合同.pdf": b"c"})),
        ],
        base_dir=base,
    )
    assert _files_under(batch) == {Path("起诉状.pdf"), Path("账单.txt"), Path("合同.pdf")}
    # ZIP 原料文件解压后应删除，batch 内不残留
    assert not list(batch.glob("*.zip"))


# ---------- ZIP 解压 ----------

def test_zip_flat_and_nested_extract(tmp_path):
    entries = {
        "起诉状.pdf": b"a",
        "证据/合同.pdf": b"b",
        "证据/账单/明细.txt": b"c",
    }
    batch = ingest_uploads(
        [UploadItem(name="材料.zip", data=make_zip_bytes(entries))], base_dir=tmp_path / "inbox"
    )
    assert _files_under(batch) == {Path("起诉状.pdf"), Path("证据/合同.pdf"), Path("证据/账单/明细.txt")}


def test_zip_filters_non_whitelist_entries(tmp_path):
    """zip 内 .exe/.zip 等非白名单文件应被跳过不解压。"""
    entries = {"正常.pdf": b"a", "病毒.exe": b"b", "内嵌.zip": make_zip_bytes({"nested.pdf": b"d"})}
    batch = ingest_uploads([UploadItem(name="x.zip", data=make_zip_bytes(entries))], base_dir=tmp_path / "inbox")
    assert _files_under(batch) == {Path("正常.pdf")}


def test_zip_empty_is_ok(tmp_path):
    batch = ingest_uploads([UploadItem(name="空.zip", data=make_zip_bytes({}))], base_dir=tmp_path / "inbox")
    assert batch.exists()
    assert _files_under(batch) == set()


def test_zip_uppercase_extension(tmp_path):
    batch = ingest_uploads(
        [UploadItem(name="材料.ZIP", data=make_zip_bytes({"a.md": b"x"}))], base_dir=tmp_path / "inbox"
    )
    assert _files_under(batch) == {Path("a.md")}


# ---------- 安全校验 ----------

def test_zip_rejects_parent_traversal(tmp_path):
    """ZIP 内 entry 含 ../ 时整包拒绝，且不留残留目录。"""
    data = make_zip_bytes({"../evil.txt": b"x", "正常.pdf": b"y"})
    base = tmp_path / "inbox"
    with pytest.raises(PathTraversalError):
        ingest_uploads([UploadItem(name="x.zip", data=data)], base_dir=base)
    assert not list(base.iterdir())  # 失败后清理
    assert not (tmp_path / "evil.txt").exists()


def test_zip_rejects_absolute_path(tmp_path):
    data = make_zip_bytes({"/abs/evil.txt": b"x"})
    with pytest.raises(PathTraversalError):
        ingest_uploads([UploadItem(name="x.zip", data=data)], base_dir=tmp_path / "inbox")
    assert not (tmp_path / "abs").exists()


def test_zip_rejects_symlink(tmp_path):
    data = make_zip_bytes({"正常.pdf": b"y"}, unix_symlink="link.txt")
    with pytest.raises(UploadError):
        ingest_uploads([UploadItem(name="x.zip", data=data)], base_dir=tmp_path / "inbox")


def test_zip_total_size_limit(tmp_path):
    data = make_zip_bytes({"a.pdf": b"x" * 100, "b.pdf": b"y" * 100})
    # 注入小上限（内部参数），总解压大小 200 > 150 → 拒绝
    from upload_ingest import _extract_zip

    zip_path = tmp_path / "big.zip"
    zip_path.write_bytes(data)
    with pytest.raises(SizeLimitExceededError):
        _extract_zip(zip_path, tmp_path / "out", max_size=150, max_files=10)


def test_zip_file_count_limit(tmp_path):
    data = make_zip_bytes({f"f{i}.txt": b"x" for i in range(5)})
    from upload_ingest import _extract_zip

    zip_path = tmp_path / "many.zip"
    zip_path.write_bytes(data)
    with pytest.raises(SizeLimitExceededError):
        _extract_zip(zip_path, tmp_path / "out", max_size=10 * 1024 * 1024, max_files=3)


def test_zip_extract_failure_cleans_batch(tmp_path):
    """解压阶段异常（如目标不可写 → 此处用穿越条目模拟）应清理 batch 目录。"""
    base = tmp_path / "inbox"
    with pytest.raises(PathTraversalError):
        ingest_uploads(
            [UploadItem(name="bad.zip", data=make_zip_bytes({"a/../b.txt": b"x"}))],
            base_dir=base,
        )
    assert not list(base.iterdir())
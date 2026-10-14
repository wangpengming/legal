# =============================================
# upload_ingest.py — 上传物落盘 / ZIP 安全解压
# 将浏览器上传的文件（单文件或多文件/ZIP）落为普通目录，
# 供 scanner/parser/extractor/importer 既有管道消费。
# 规格：docs/SPEC-ui-upload.md §3（安全校验 / 目录约定 / 清理）
# =============================================
import secrets
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Optional

# ---------- 常量 ----------

SUPPORTED_EXTS = {".pdf", ".doc", ".docx", ".txt", ".md"}
MAX_ZIP_TOTAL = 512 * 1024 * 1024  # ZIP 解压后总大小上限（512MB）
MAX_ZIP_FILES = 200                # ZIP 内文件数上限（防 ZIP 炸弹）

# ---------- 异常族 ----------


class UploadError(Exception):
    """上传落盘错误基类"""
    pass


class ZipExtractError(UploadError):
    """ZIP 解压失败（坏包 / 编码异常）"""
    pass


class PathTraversalError(UploadError):
    """ZIP 内条目路径穿越（../ 或绝对路径），整包拒绝"""
    pass


class SizeLimitExceededError(UploadError):
    """解压后总大小或文件数超限"""
    pass


# ---------- 数据类型 ----------


@dataclass
class UploadItem:
    """单个上传物（与 Streamlit UploadedFile 解耦，便于测试）。"""
    name: str    # 原始文件名（含扩展名），如 "原告证据.zip"
    data: bytes  # 文件内容


# ---------- 默认落盘根 ----------


def _default_inbox() -> Path:
    """默认 base_dir：data/inbox（与 src/database.py 的 DATA_DIR 单一真值保持一致）。

    惰性加载：包模式（from src import upload_ingest）走相对导入，
    测试顶层模式（sys.path=src）走绝对导入。
    """
    try:
        from . import database as db
    except ImportError:
        import database as db
    return db.DATA_DIR / "inbox"


# ---------- 工具 ----------

def _safe_basename(name: str) -> str:
    """剥离路径成分与穿越片段，只保留文件名本体。"""
    cleaned = Path(name.replace("\\", "/")).name
    return cleaned or "unnamed_file"


def _is_zip(name: str) -> bool:
    return Path(name).suffix.lower() == ".zip"


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    """依据 unix 权限位判定符号链接。"""
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _is_supported_entry(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED_EXTS


def _validate_entry_name(info: zipfile.ZipInfo) -> None:
    """路径穿越校验：拒绝绝对路径与含 .. 段的条目（整包拒绝）。"""
    if info.is_dir():
        return
    p = PurePosixPath(info.filename)
    if p.is_absolute() or ".." in p.parts:
        raise PathTraversalError(f"ZIP 条目路径非法: {info.filename!r}")


# ---------- 核心 API ----------

def ingest_uploads(items: list[UploadItem], base_dir: Optional[Path] = None) -> Path:
    """落盘上传物并解压 ZIP，返回 batch 目录。

    - batch 目录：<base_dir>/<YYYYmmdd_HHMMSS>_<rand4>/
    - 单文件：直接落入 batch 目录（文件名取 basename）
    - ZIP：解压到 batch 目录后删除 ZIP 原料；zip 内 zip 不解压
    - 任何异常 → 清理 batch 目录（不留残留）后重抛
    """
    if not items:
        raise UploadError("没有可处理的上传文件")

    base = Path(base_dir) if base_dir else _default_inbox()
    base.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch = base / f"{stamp}_{secrets.token_hex(2)}"
    batch.mkdir(mode=0o700, parents=True, exist_ok=False)

    try:
        for item in items:
            name = _safe_basename(item.name)
            if _is_zip(name):
                zip_path = batch / name
                zip_path.write_bytes(item.data)
                try:
                    _extract_zip(zip_path, batch)
                finally:
                    zip_path.unlink(missing_ok=True)  # 原料不残留
            else:
                if not _is_supported_entry(name):
                    raise UploadError(f"不支持的文件类型: {name}（仅支持 {', '.join(sorted(SUPPORTED_EXTS))}）")
                (batch / name).write_bytes(item.data)
    except Exception:
        shutil.rmtree(batch, ignore_errors=True)
        raise

    return batch


def _extract_zip(
    zip_path: Path,
    dest_dir: Path,
    *,
    max_size: int = MAX_ZIP_TOTAL,
    max_files: int = MAX_ZIP_FILES,
) -> None:
    """安全解压 ZIP 到 dest_dir（先全量校验，再逐条提取）。

    校验规则：
    - 路径穿越（绝对路径 / .. 段）→ PathTraversalError（整包拒绝）
    - 符号链接 → UploadError（不落链接）
    - 解压总大小 / 文件数超限 → SizeLimitExceededError
    - 非白名单扩展名（含嵌套 zip）→ 跳过不解压
    """
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as e:
        raise ZipExtractError(f"ZIP 文件损坏: {e}") from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    total_size = 0
    file_count = 0

    try:
        with zf:
            # 阶段一：全量校验
            for info in zf.infolist():
                _validate_entry_name(info)
                if info.is_dir():
                    continue
                if _is_symlink(info):
                    raise UploadError(f"ZIP 内不允许符号链接: {info.filename!r}")
                if not _is_supported_entry(info.filename):
                    continue
                file_count += 1
                if file_count > max_files:
                    raise SizeLimitExceededError(f"ZIP 内文件数超过上限 {max_files}")
                total_size += info.file_size
                if total_size > max_size:
                    raise SizeLimitExceededError(f"ZIP 解压后总大小超过上限 {max_size} 字节")

            # 阶段二：逐条提取（仅白名单文件；父目录由 extract 自动创建，保留层级）
            for info in zf.infolist():
                if info.is_dir() or not _is_supported_entry(info.filename):
                    continue
                zf.extract(info, dest_dir)
    except UploadError:
        raise
    except (zipfile.BadZipFile, OSError, UnicodeDecodeError, NotImplementedError) as e:
        raise ZipExtractError(f"ZIP 解压失败: {e}") from e
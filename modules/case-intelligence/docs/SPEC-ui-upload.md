# SPEC — UI 上传提取与生成链路（v3.4.1 增补）

> 适用范围：case-intelligence v3.4.1 新增的「浏览器文件/文件夹上传」能力。
> 主规格见 [`SPEC.md`](./SPEC.md)（三对象模型、D1-D5 维度、流程A/流程B、数据库 schema）。
> 本文件聚焦：上传入口、管道复用、目录约定、安全校验、密钥治理、部署约束。

---

## 1. 背景与决策

| 项 | 结论 |
|----|------|
| 对外界面 | 仅 Streamlit UI（:18503）。**不新增 REST API、不引入 nginx/FastAPI** |
| 上传形态 | `st.file_uploader(accept_multiple_files=True)`，接受 pdf/docx/doc/txt/md/zip |
| 文件夹上传 | 浏览器无法读取本地文件夹 → **ZIP 传目录**；ZIP 解压后走与服务器路径完全相同的管道 |
| 飞书 Bot | 整体后置（见 backlog 新条目），本 SPEC 不覆盖 |
| 版本 | 3.4.1（补丁级：UX 补全 + 安全治理，无协议变更） |

## 2. 上传链路

```
浏览器 file_uploader（多文件 / ZIP）
   │  st.file_uploader(accept_multiple_files=True)
   ▼
src/upload_ingest.py  ingest_uploads(items: list[UploadItem], base_dir) -> Path
   │  ① 单文件 → 直接落入 batch 目录    ② zip → _extract_zip 解压（防穿越）
   ▼
data/inbox/<timestamp>_<rand4>/（batch 目录，权限 0700）
   │  与「服务器路径」输入指向的任意目录结构完全一致
   ▼
scanner.scan_directory(batch_dir)          # 已有，不改
   ▼
parser.parse_files(files)                  # 已有，不改
   ▼
extractor.extract_case(contents, name, engine)   # 已有，不改
   ▼
case_recognizer.recognize_case(...) 查重    # 已有，不改（页内二次确认）
   ▼
importer.CaseImporter.import_full(...) 入库  # 已有，不改
```

**关键不变式**：`upload_ingest` 只负责「上传物 → 目录」一段，产出**普通目录**；其后全部复用现有管道，杜绝双路径逻辑。

## 3. upload_ingest.py 契约

```python
@dataclass
class UploadItem:
    name: str                 # 原始文件名（含扩展名），如 "原告证据.zip"
    data: bytes               # 文件内容

INGEST_ERRORS: 模块内异常族 UploadError / ZipExtractError / PathTraversalError / SizeLimitExceededError

def ingest_uploads(items: list[UploadItem], base_dir: Path | None = None) -> Path:
    """落盘上传物并解压 ZIP，返回 batch 目录。base_dir 缺省 = data/inbox（随 DATA_DIR）。"""

def _extract_zip(zip_path: Path, dest_dir: Path, *, max_size: int = MAX_ZIP_TOTAL,
                 max_files: int = MAX_ZIP_FILES) -> None:
    """安全解压：逐 entry 校验 arcname 后 extract"""
```

### 3.1 安全校验（强制，TDD 覆盖）

| 规则 | 说明 |
|------|------|
| 路径穿越 | entry 名必须相对、无 `..`、非绝对（`PurePosixPath` 检查 `is_absolute` / `..` 段）；违规 → `PathTraversalError`，**整包拒绝** |
| 目录项/符号链接 | 跳过纯目录 entry；`external_attr` 判定 symlink → 拒绝（容器内不落链接） |
| 大小上限 | `MAX_ZIP_TOTAL = 512MB`（解压前累计 uncompressed_size 校验）+ Streamlit 层 `server.maxUploadSize = 500` |
| 文件数上限 | `MAX_ZIP_FILES = 200`，防 ZIP 炸弹 |
| 扩展名白名单 | 仅解压/落盘 SUPPORTED_EXTS（`pdf doc docx txt md`）；zip 内 zip 视为普通文件、不解压 |
| 编码 | `zipfile` 默认解码；中文文件名异常时 `extract` 失败由 `UnicodeDecodeError` 捕获并报可读错误 |

### 3.2 目录与清理

- batch 目录：`DATA_DIR/inbox/<YYYYmmdd_HHMMSS>_<rand4>/`，`inbox/` 在 seeding/volume 内（data/ 已在 volume 契约中）
- 失败清理：解压中途异常 → 删 batch 目录（`shutil.rmtree`，best-effort）
- 绝不删除用户提供的原始上传对象（由 Streamlit 会话回收）

## 4. 密钥 env 化（§6.2 红线）

- `ai_engines.yaml` 中 `MINIMAX` 的 `api_key` 由明文改为 `env://MINIMAX_API_KEY`
- `src/ai_engine.py` 新增 `_resolve_env_ref(value: str) -> str`：
  - `env://VAR` → `os.environ[VAR]`；变量缺失 → `KeyError` 带提示「请设置环境变量 VAR 或修改 ai_engines.yaml」
  - 其他字符串原样直通
- 解析时机：引擎加载时（惰性，首次调用 `get_engine`）
- 新增 `.env.example`：`MINIMAX_API_KEY=`、`MINIMAX_MODEL=`（占位，不写入真实值）
- 部署契约（deploy.yaml env_required）已含 `MINIMAX_API_KEY`，Thunderbox `env_vars` 注入

## 5. UI 变更（pages/3_扫描录入.py）

- 页首形态：`st.tabs` 双签「📤 上传文件（推荐） / 📂 服务器路径」
  - **上传签**：`st.file_uploader` + 「🔍 开始扫描（上传）」按钮 → `ingest_uploads` → 复用原扫描逻辑（引擎选择共用）
  - **路径签**：现有 text_input + 按钮，行为不变（管理员兜底，不回退）
- 支持类型：`["pdf", "docx", "doc", "txt", "md", "zip"]`
- 导入成功卡片附加「📝 去生成文书」按钮：
  - `st.session_state["generate_case_id"] = import_result["case_id"]`（**String 键经 session_state 传递，禁止模块级全局变量**）
  - `st.page_link("pages/4_文书生成.py")` 引导跳转；4_文书生成页已有 `st.session_state.get("generate_case_id")` 读取逻辑，仅联调核实

## 6. 配置新增

- `.streamlit/config.toml`（新建，模块根）：

```toml
[server]
maxUploadSize = 500          # MB；ZIP 总体积上限的 Streamlit 侧守护
```

- `config.py`：经 `od -c` 证实无损坏（此前终端输出 `20%` 系 shell 提示符残留），**不改代码**，以 `pytest tests/test_ui.py` 回归确认

## 7. 部署约束（Thunderbox 就绪）

- 单进程不变：`docker-entrypoint.sh` 仍 `streamlit run app.py --server.port 18503`
- volumes 契约不变：`["case-data:/data"]`；inbox 位于 `/data/inbox/`（volume 内，持久）
- 播种逻辑：inbox 不需要种子（上传目标目录，运行时创建）
- `MINIMAX_API_KEY` 由 Thunderbox `env_vars` 注入（`thunderbox_config`）；`ai_engines.yaml` 不再含任何真实密钥

## 8. 测试清单（TDD）

| 测试 | 断言点 |
|------|--------|
| `tests/test_upload_ingest.py` | 单文件落盘；ZIP 嵌套/顶层变体；`../evil.txt` 拒绝；绝对路径拒绝；symlink 拒绝；zip 大小/文件数超限；非白名单扩展名过滤；空 ZIP；解压失败清理 |
| `tests/test_ai_engine_env.py` | `env://` 有值解析；缺变量可读错误；普通串直通；引擎默认配置完整性 |
| `tests/test_scan_page_pipeline.py` | `ingest_uploads` 产物目录 → scan→parse→extract(mock)→recognize→import 全链（mock 引擎）；页面文件列表渲染兼容 `FileInfo` 对象（AppTest 回归，2026-10-14 浏览器 E2E 发现的 AttributeError） |
| 回归 | `pytest tests/ -v` 全量（20+ 文件）不回归 |

## 9. 明确不做

- ❌ REST API / FastAPI / nginx 反代 / 新端口
- ❌ 飞书 Bot 任何代码改动（仅 backlog 回填）
- ❌ `thunderbox_create/deploy` 实际执行（Push 红线，待授权）
- ❌ `ai_engines.yaml` 之外新增配置面
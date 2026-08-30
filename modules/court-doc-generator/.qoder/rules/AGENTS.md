# Court Generator — AI 代理工程行动约束

> **适用对象**：所有 AI 代理（Qoder / Claude / Cursor / 其他）在 `court-generator/` 工作时必读。
>
> **配套文档**：
> - `docs/SPEC.md` — 系统规格 v2.x（架构、模块、需求、安全红线）
> - `docs/DEPLOYMENT-THUNDERBOX.md` — Thunderbox 部署指南
> - `module.yaml` — 模块注册元数据
> - 本文件 — **工程行动约束与红线**

---

## 1. 项目定位

**出庭手续生成器**（court-doc-generator）：React + FastAPI 全栈应用，让法务人员在 5 分钟内独立完成 7 份出庭材料的生成、合并、在线预览与打印。

**四大原则**：

1. **本地优先** — 数据不外传，离线可用
2. **AI 可解析** — 所有规范以 Markdown + YAML 头部编写
3. **workspace 隔离** — 多用户独立数据目录
4. **演进可追溯** — 所有变更登记 `CHANGELOG.md`

---

## 2. 技术栈

| 层 | 选型 | 端口 |
|----|------|------|
| 前端 | React 18 + TypeScript + Vite | 18502 |
| 后端 | FastAPI + Uvicorn | 8001 |
| 数据库 | SQLite (workspace 隔离) | - |
| PDF 预览 | PDF.js 全内联 base64 | - |
| OCR | Tesseract CLI | - |

---

## 3. 目录结构

```
court-generator/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 入口 + /health
│   │   ├── api/            # REST API 路由
│   │   │   ├── auth.py     # 注册/登录
│   │   │   ├── cases.py    # 案件 CRUD
│   │   │   ├── generate.py # 材料生成
│   │   │   ├── scan.py     # OCR 扫描
│   │   │   └── ...
│   │   └── core/           # 配置 + 数据库
│   ├── bin/                # 启动/停止/状态/重启
│   ├── tests/              # 后端测试
│   └── requirements.txt
│
├── frontend/               # React + Vite 前端
│   ├── src/
│   │   ├── pages/         # 页面组件
│   │   ├── components/    # 共享组件
│   │   └── lib/           # 工具函数
│   ├── bin/               # 启动/停止/状态/重启
│   └── package.json
│
├── bin/                   # 项目级脚本（统一启动）
├── templates/             # Word 模板（中文全角【】占位符）
├── static/               # 静态 PDF + PDF.js
├── tests/                # 根级测试
├── docs/                 # 设计文档
├── .qoder/rules/         # 本文件（AI 代理规则）
├── module.yaml           # 模块注册元数据
├── config.py             # 路径常量
├── generator.py          # 核心生成逻辑
├── docx_to_pdf.py        # DOCX → PDF
├── pdf_merger.py         # PDF 合并
├── scan_service.py       # OCR 扫描服务
└── workspace.py          # Workspace 管理
```

---

## 4. 开发流程（5 步强制）

| 步骤 | 动作 | 产出 |
|------|------|------|
| ① 需求登记 | 在 `docs/SPEC.md` 或对应增量规格文档新增条目 | 需求条目 |
| ② 评审 | 与用户确认优先级 + 验收标准 | 标准明确 |
| ③ 开发 | 在对应目录下实现，遵循模块自身规范 | 可运行的代码 + 单测 |
| ④ 测试 | pytest 通过 + tsc 零错误 | 测试通过 |
| ⑤ 归档 | 更新 `CHANGELOG.md` | 完成记录 |

---

## 5. 命名规范（强制）

| 元素 | ✅ 正确 | ❌ 错误 |
|------|---------|--------|
| 目录名 | `backend/app/api/` | `后端/接口/` |
| 文件名 | `pdf_merger.py` | `PDF合并器.py` |
| 函数名 | `def merge_pdfs()` | `def 合并PDF()` |
| 变量名 | `case_number` | `案件案号` |
| 组件名 | `CaseDetailModal` | `案件详情弹窗` |

**中文仅出现在**：`*.md` 文档 / 注释 / UI 文案。

---

## 6. 数据安全红线 🔴

### 6.1 PII（个人敏感信息）

| 红线 | 措施 |
|------|------|
| ❌ 严禁硬编码真实身份证号 / 手机号 / 真实姓名 | 默认数据全部留空（`""`），由用户在 UI 填写真实信息 |
| ❌ 严禁将真实 PII 写入代码 / 注释 / 测试 fixture | 测试用 `000000000000000000` 等占位符 |
| ❌ 严禁在日志中打印完整身份证 / 手机号 | 必要时用 `mask_id_card()` 遮罩（`前4位****后4位`） |

### 6.2 密钥管理

- `.env` — 私有配置（gitignore 屏蔽）
- 飞书 `app_id` / `app_secret` 等走 `.env`，调飞书 API 时不回显

### 6.3 .gitignore 强制项

```
data/             SQLite（含敏感数据）
outputs/          生成结果
.run/             PID + 日志
.pytest-data/     测试数据隔离目录
.venv/ venv/     虚拟环境
.env              环境变量
*.zip             生成产物
__pycache__/      编译缓存
```

---

## 7. Word 模板占位符规范

### 7.1 格式

**使用中文全角【】**（U+3010 U+3011），区别于英文 `[]`。

### 7.2 替换规则

> **按【】在文档中的物理出现顺序依次消费 values 列表。**
>
> **必须从后往前替换，避免位置偏移！**

```python
PLACEHOLDER_PATTERN = re.compile(r"【】")

def replace_placeholders_by_position(paragraph, values):
    # 1. 合并段落所有 runs
    full_text = "".join(run.text for run in paragraph.runs)
    
    # 2. 找出所有【】位置
    matches = list(PLACEHOLDER_PATTERN.finditer(full_text))
    
    # 3. 从后往前替换
    for i in range(len(matches) - 1, -1, -1):
        match = matches[i]
        value = str(values[i]) if values[i] is not None else ""
        new_text = new_text[:match.start()] + value + new_text[match.end():]
    
    # 4. 写回 paragraph.runs[0]，其余清空
    if new_text != full_text:
        paragraph.runs[0].text = new_text
        for run in paragraph.runs[1:]:
            run.text = ""
```

### 7.3 各模板占位符清单

| 模板 | 数量 | 替换内容（按顺序） |
|------|------|-------------------|
| 法定代表人证明 | 3 | 年、月、日 |
| 授权委托书 | 5 | 案由描述、案号、年、月、日 |
| 推荐信 | 6 | 法院、案由描述、案号、年、月、日 |

---

## 8. PDF.js 浏览器预览规范

### 8.1 必须使用 base64 内联

**SPA 路由拦截问题**：Streamlit / Vite dev server 的路由会拦截 `/static/` 路径返回 HTML，导致 PDF.js 无法加载。

| 方案 | 结果 |
|------|------|
| `/static/pdfjs/pdf.min.js` | ❌ SPA 返回 HTML，MIME 错误 |
| CDN URL | ❌ CSP 跨域拦截 |
| **base64 内联** | ✅ 绕过所有拦截 |

### 8.2 关键陷阱

> ⚠️ **绝对不能使用 `new Function(mainCode)`**：`var pdfjsLib` 不会泄漏到外层作用域。
>
> ✅ **必须使用 `<script>eval(atob(mainB64))</script>`**：让 `var` 暴露到全局。

```javascript
// ❌ 错误
pdfjsLib = new Function(atob(mainB64));

// ✅ 正确
eval(atob(mainB64));
```

### 8.3 Worker 注入

```javascript
const workerBlob = new Blob(
  [Uint8Array.from(atob(workerB64), c => c.charCodeAt(0))],
  { type: 'application/javascript' }
);
pdfjsLib.GlobalWorkerOptions.workerSrc = URL.createObjectURL(workerBlob);
```

---

## 9. Thunderbox 部署规范 🔴

### 9.1 源码仓库

| 平台 | 是否支持 |
|------|---------|
| GitHub 公开仓库 | ✅ 可用 |
| GitLab 公开仓库 | ✅ 可用 |
| Gitee | ❌ 不支持（URL 解析丢弃域名） |

### 9.2 git_token 陷阱

- **公开仓库不传 `git_token`** — Thunderbox 将其当作 GitLab CI token，GitHub 不认
- URL 格式：`https://github.com/owner/repo`（不带 `.git`，不带 token）

### 9.3 Dockerfile 必须项

```dockerfile
# 系统依赖（OCR 必需）
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# PyPI 清华镜像（25MB 大包超时）
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 9.4 Volumes 必须挂载

```json
{
  "volumes": ["court-data:/app/data", "court-outputs:/app/outputs"]
}
```

> ⚠️ Thunderbox 容器文件系统是 ephemeral 的 — **不挂载 volumes 每次重部署数据清零**。

### 9.5 部署后必做

- [ ] `thunderbox_config(access_mode="public")` — 否则外部 `no available server`
- [ ] `curl https://<domain>/health` — 外部验证 200
- [ ] `curl https://<domain>/` — 前端 SPA 200

---

## 10. scan_service.py 惰性初始化 🔴

### 10.1 问题根因

`scan_service.py` 在模块导入时执行 `_detect_lang()`：

```python
# ❌ 当前写法：模块导入时立即执行
_TESSERACT = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
_LANG = _detect_lang()  # 崩溃点：shutil.which(None) → TypeError
```

Linux 容器中 `shutil.which("tesseract")` 返回 `None`，然后 `shutil.which("/opt/homebrew/bin/tesseract")` 也返回 `None`，导致 `Path(None).parent` 崩溃。

### 10.2 修复方案

```python
# ✅ 惰性求值 + fallback
_LANG: Optional[str] = None

def get_lang() -> str:
    global _LANG
    if _LANG is None:
        try:
            _LANG = _detect_lang()
        except Exception:
            _LANG = "chi_sim"  # fallback
    return _LANG
```

---

## 11. 测试数据隔离（强制）

| 场景 | 要求 |
|------|------|
| pytest / 单测 | 全局 `DATA_DIR` 指向 `.pytest-data`（已 gitignore） |
| 浏览器 E2E | 使用专用验证账号（命名 `e2e_*` / `verify_*`），验证完毕即删 |
| 数据清理 | 以注册表 `data/workspaces.db` 为准，白名单法 |

---

## 12. 服务管理脚本

每个子目录（`bin/`）必须提供：

```
bin/
├── start.py / start.sh / start.bat     # 后台启动
├── stop.py  / stop.sh  / stop.bat      # 三重定位停止
├── restart.py / restart.sh / restart.bat
└── status.py / status.sh / status.bat  # 健康检查
```

### 12.1 健康检查端点

| 服务 | 端点 | 返回 |
|------|------|------|
| 后端 | `GET /health` | `{"status": "ok", "version": "x.y.z"}` |
| 前端 | Vite dev server | HTML 200 |

---

## 13. AI 代理特定指令

### 13.1 必须做的事

| 场景 | 动作 |
|------|------|
| 接到新需求 | 查 `docs/SPEC.md` 是否已有同主题需求 |
| 修改核心逻辑 | 先读 `docs/SPEC.md` 对应章节 |
| 涉及安全 | 查 §6 数据安全红线 |
| 测试相关 | 查 §11 测试隔离要求 |
| Thunderbox 部署 | 查 §9 部署规范 |

### 13.2 严禁做的事

| 禁止 | 原因 |
|------|------|
| ❌ 硬编码中文文件名 / 函数名 | 违反 §5 命名规范 |
| ❌ 把真实 PII / 密钥写入文件 | 违反 §6 安全红线 |
| ❌ 直接 `git push --force` | 高危操作需用户确认 |
| ❌ 🔴 未经用户明确允许执行 `git push` | Push 红线：必须用户逐次授权 |
| ❌ 使用 `new Function()` 加载 PDF.js | 违反 §8.2，会导致 `var` 不泄漏 |
| ❌ scan_service.py 模块级依赖外部二进制 | 违反 §10，容器中崩溃 |
| ❌ 部署时不挂载 volumes | 数据每次重置 |

---

## 14. 关联文档速查

| 文档 | 何时读 |
|------|--------|
| `docs/SPEC.md` | 架构 / 模块 / 接口 / 安全 |
| `docs/DEPLOYMENT-THUNDERBOX.md` | Thunderbox 部署 / 排查 |
| `module.yaml` | 模块元数据 |
| 本文件 | 工程行动约束 |

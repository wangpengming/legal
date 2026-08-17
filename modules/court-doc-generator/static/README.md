# 📂 静态资源目录

> 本目录存放 **4 份固定不变** 的出庭材料 PDF + 浏览器内 PDF 预览所需的 PDF.js 库。

---

## 一、必放文件清单（4 份固定 PDF）

| 文件名（严格一致） | 材料 | 提供方 |
|-------------------|------|--------|
| `1.营业执照复印件.pdf` | 公司营业执照复印件 | 法务部向工商/行政索取 |
| `法人身份证.pdf` | 法定代表人身份证正反面 | 法务部向法人索取 |
| `代理人劳动合同.pdf` | 代理人与公司签订的劳动合同 | 法务部从 HR 调档 |
| `代理人身份证.pdf` | 代理人身份证正反面 | 代理人本人提供 |

> ⚠️ 文件名按出庭材料 **提交顺序** 编号（1-7），其中 1/3/6/7 是固定证件，直接复制到 `outputs/<日期>_<案号>/`。

---

## 二、命名与编码要求

- 文件名严格匹配上表（含中文与 `.pdf` 后缀）
- 编码：**UTF-8**（确保 macOS / Windows / Linux 三端文件名一致）
- PDF 版本：建议 **PDF 1.4+**，避免加密（部分合并工具不支持）
- 文件大小：单份建议 ≤ 5 MB（过大导致浏览器内 base64 加载慢）

---

## 三、4 份 PDF 的来源与提交要求

### 3.1 营业执照复印件

- 来源：国家企业信用信息公示系统下载 PDF 版，或扫描纸质执照
- 要求：
  - **清晰可读**（不要拍照后未矫正）
  - **加盖公司公章**（出庭材料必须）
  - 复印件首页即可（如多页合并为 1 份 PDF）

### 3.2 法人身份证

- 要求：
  - **正反面**在同一份 PDF 内（首页正面，第二页反面）
  - 复印时清晰可辨，无遮挡
  - 出庭前 **加盖公司公章**（部分地区法院要求）

### 3.3 代理人劳动合同

- 来源：HR 部门调取
- 要求：
  - 包含**首页（双方信息）**+ **签字盖章页**
  - 复印时清晰
  - 加盖公司公章或人事章

### 3.4 代理人身份证

- 要求：同法人身份证（正反面 + 清晰 + 必要时加盖公章）

---

## 四、PDF.js 库（浏览器内 PDF 预览）

`pdfjs/` 子目录存放 Mozilla PDF.js 的两个 JS 文件，用于实现**浏览器内 PDF 预览 + 缩放 + 翻页 + 打印**。

### 4.1 当前状态

```
static/pdfjs/
├── pdf.min.js         ← ⚠️ 待下载（约 320 KB）
└── pdf.worker.min.js  ← ⚠️ 待下载（约 1 MB）
```

### 4.2 下载方式

#### 方式 A：CDN 下载（推荐）

```bash
cd /Users/pengming/code/me/legal/modules/court-doc-generator/static/pdfjs

# 主库
curl -L -o pdf.min.js \
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.min.js"

# Worker（必须与主库同版本！）
curl -L -o pdf.worker.min.js \
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.worker.min.js"
```

#### 方式 B：npm 安装后拷贝

```bash
npm install pdfjs-dist@4.0.379

# 拷贝到本目录
cp node_modules/pdfjs-dist/build/pdf.min.js .
cp node_modules/pdfjs-dist/build/pdf.worker.min.js .
```

#### 方式 C：官方 GitHub Release

```bash
VERSION="4.0.379"
curl -L -o pdf.min.js \
  "https://github.com/mozilla/pdf.js/releases/download/v${VERSION}/pdf.min.js"
curl -L -o pdf.worker.min.js \
  "https://github.com/mozilla/pdf.js/releases/download/v${VERSION}/pdf.worker.min.js"
```

### 4.3 验证下载成功

```bash
# 确认文件大小合理
ls -lh pdf.min.js pdf.worker.min.js
# 期望：pdf.min.js ~320KB，pdf.worker.min.js ~1MB

# 确认不是 HTML 错误页（CDN 偶尔会返回 404 页面）
head -c 200 pdf.min.js | head -1
# 期望：不是 <!DOCTYPE 或 <html
```

### 4.4 版本兼容性

- 主库和 worker **必须严格同版本**（不匹配会报 `Setting up fake worker` 警告）
- 推荐锁定版本：`pdfjs-dist==4.0.379` 或更新稳定版
- 升级前需在 `tests/test_pdf_viewer.py` 增加回归测试

---

## 五、避坑指南

| 坑 | 现象 | 解决 |
|----|------|------|
| PDF 是加密的 | 合并时 `pypdf` 抛 `FileEncryptedError` | 用 Adobe Acrobat 去除密码 |
| PDF 是扫描件（非文本） | 浏览器预览可看，但不能复制文字 | 正常，预览功能不受影响 |
| 文件名含空格 | `shutil.copy2` 在某些 shell 报错 | **已避免**，文件名无空格 |
| 浏览器内 PDF 预览空白 | PDF.js 没加载 / worker 路径错 / sandbox 拦截 | 见 [SPEC.md §9](../SPEC.md) 全内联方案 |
| 主库与 worker 版本不一致 | `Setting up fake worker` 警告 / 性能差 | 严格锁定同版本号 |

---

## 六、当前状态

```
static/
├── 1.营业执照复印件.pdf   ← ⚠️ 待补充
├── 法人身份证.pdf        ← ⚠️ 待补充
├── 代理人劳动合同.pdf    ← ⚠️ 待补充
├── 代理人身份证.pdf      ← ⚠️ 待补充
└── pdfjs/
    ├── pdf.min.js         ← ⚠️ 待下载
    └── pdf.worker.min.js  ← ⚠️ 待下载
```

---

## 七、隐私与安全

> 🔒 这 4 份 PDF 都是 **敏感证件**（身份证、合同），严禁提交到 git！

`.gitignore` 已自动屏蔽以下路径：

```
static/*.pdf        # 静态 PDF
static/pdfjs/*.js   # PDF.js 库（体积大，不入 git）
```

但本地打包分发时 **必须包含** `static/pdfjs/`（否则浏览器内 PDF 预览无法工作）。
4 份静态 PDF 由各使用方根据案件需要自行准备，**不放入分发包**。
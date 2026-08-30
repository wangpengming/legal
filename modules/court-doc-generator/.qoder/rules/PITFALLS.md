# Court Generator — 已知坑与修复方案

> 记录开发过程中遇到的已知问题及解决方案。

---

## 1. PDF.js 加载问题

### 问题：SPA 路由拦截导致 PDF.js 无法加载

**现象**：`/static/pdfjs/pdf.min.js` 返回 HTML 而不是 JavaScript。

**根因**：Vite dev server / Streamlit 的路由将所有路径当作 SPA 路由处理。

**解决方案**：使用 base64 内联，**禁止使用 `new Function()`**。

```javascript
// ❌ 错误：var 不会泄漏到外层作用域
pdfjsLib = new Function(atob(mainB64));

// ✅ 正确：eval 让 var 暴露到全局
eval(atob(mainB64));
```

**Worker 注入**：

```javascript
const workerBlob = new Blob(
  [Uint8Array.from(atob(workerB64), c => c.charCodeAt(0))],
  { type: 'application/javascript' }
);
pdfjsLib.GlobalWorkerOptions.workerSrc = URL.createObjectURL(workerBlob);
```

---

## 2. scan_service.py 模块级初始化

### 问题：容器中 `shutil.which("tesseract")` 返回 None 导致崩溃

**现象**：`TypeError: argument should be a string, bytes or os.PathLike object, not 'NoneType'`

**根因**：

```python
# ❌ 当前写法
_TESSERACT = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
_LANG = _detect_lang()  # 第 36 行，模块导入时立即执行
```

在 Linux 容器中：
1. `shutil.which("tesseract")` → `None`
2. 短路求值后 `_TESSERACT = "/opt/homebrew/bin/tesseract"`
3. `shutil.which("/opt/homebrew/bin/tesseract")` → `None`
4. `Path(None).parent.parent` → **TypeError**

**修复方案**：惰性求值 + fallback

```python
# ✅ 正确写法
_LANG: Optional[str] = None

def get_lang() -> str:
    global _LANG
    if _LANG is None:
        try:
            _LANG = _detect_lang()
        except Exception:
            _LANG = "chi_sim"
    return _LANG
```

---

## 3. 测试数据污染

### 问题：pytest 使用真实生产数据

**现象**：测试后 `.pytest-data` 目录产生大量 `TestUser` workspace。

**根因**：`conftest.py` 未正确设置 `DATA_DIR` 隔离。

**修复**：在 `backend/tests/conftest.py` 全局设置：

```python
import os
os.environ["DATA_DIR"] = ".pytest-data"
```

同时确保配置中派生路径使用 `property` 而非类体求值。

---

## 4. 浏览器缓存旧生成结果

### 问题：预览/下载显示旧的合并 PDF

**根因**：生成产物 URL 无语义变化，浏览器启发式缓存。

**修复**：
1. files API 响应加 `Cache-Control: no-store`
2. 前端预览/下载 URL 带时间戳参数

---

## 5. 并发生成竞态

### 问题：同一案号并发生成导致 rmtree 竞态

**现象**：生成失败，目录被其他进程删除。

**修复**：
1. 使用进程级互斥锁
2. 抢锁失败提示「正在生成中」

---

## 6. agents 表唯一性 bug

### 问题：`UNIQUE(name, id_card)` 当 id_card 为空时不同人变同一人

**修复**：改为 `UNIQUE(name, company_id)`

---

## 7. Thunderbox git_token 陷阱

### 问题：公开仓库传了 git_token 导致 403

**根因**：Thunderbox 将 git_token 当作 GitLab CI token。

**修复**：公开仓库不传 `git_token`。

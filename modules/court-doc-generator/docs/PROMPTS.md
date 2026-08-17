# 🎯 出庭手续生成器 · 提示词反推指南

> **设计原则**：每个提示词都是"可独立发出去让 AI 执行"的；法务小白可以按顺序一步步推进，不必理解所有技术细节。
>
> **适用场景**：从 0 复刻 / 二次开发 / 借鉴到其他法务工具 / 培训新人。

---

## 📍 阶段 0：业务理解（最重要）

> 这阶段不写代码，先让 AI 理解业务场景。

### 提示词 0.1 · 项目立项

```text
【角色】你是公司内部法务/律师的 AI 助理，熟悉中国法院出庭流程。

【背景】
我是一家公司的法务，每次需要派人出庭时，要向法院提交 7 份材料：
- 3 份需要根据案件信息填写的：法定代表人证明、授权委托书、推荐信
- 4 份固定不变的：公司营业执照、法人身份证、劳动合同、代理人身份证

每次出庭前都要手动在 Word 里改日期、改案号、改案由，效率极低，且容易填错。

【目标】
为我设计一个本地工具，一键生成 7 份材料 + 合并成 1 份 PDF + 一键打包 ZIP。
要求：法务小白能直接使用，不需要懂代码。

【约束】
- 公司内部使用，不上云
- 必须是本地部署，数据不能外传
- 跨平台优先（macOS / Windows / Linux）
- 出庭材料包含敏感信息（身份证、合同），必须安全

【输出】
1. 功能列表（按优先级）
2. 技术选型建议（前端框架 + Word 处理 + PDF 处理）
3. 项目目录结构初稿
4. MVP 范围（什么先做，什么后做）
```

**验收**：AI 输出 1 份 1-2 页的方案文档，能直接拿来做立项汇报。

---

## 📍 阶段 1：MVP 启动（最小可用）

### 提示词 1.1 · 技术选型与项目初始化

```text
【上下文】
我已确定要做"出庭手续生成器"，目标用户是法务小白。

【技术选型要求】
- 前端：Streamlit（法务小白能改）
- Word 处理：python-docx
- PDF 处理：pypdf + PyMuPDF（合并 + 缩略图）
- 数据库：SQLite（无需安装）
- 服务端口：必须避开 8501/8080 等常用端口

【任务】
1. 创建项目目录结构（src/、templates/、static/、outputs/、data/、bin/）
2. 写 requirements.txt（streamlit>=1.28.0、python-docx>=1.1.0、pymupdf、pymdf）
3. 创建 .venv 虚拟环境
4. 写最简 app.py：能跑起来 + 显示 "Hello 出庭手续生成器"
5. 验证：在浏览器能访问 http://localhost:18501

【避坑】
- 端口必须改成 18501（避开通用端口），否则容易冲突
- 不要用 Flask/Django，Streamlit 一行代码搞定 Web 界面
```

**验收**：`bash bin/start.sh` 后浏览器能看到 Streamlit 默认页面。

### 提示词 1.2 · 数据建模

```text
【上下文】
我现在做法务工具，需要存：委托单位（公司）、代理人、案件。

【任务】
用 SQLite 设计 4 张表，写在 src/database.py：

1. companies（委托单位）
   - 必填：公司全称、法人姓名、法人职务
   - 选填：信用代码、地址、电话、法人身份证号

2. agents（代理人）
   - 必填：姓名、性别
   - 选填：身份证号、职务、电话

3. cases（案件）
   - 必填：案号、案由、审理法院、开庭日期
   - 选填：对方当事人、我方身份、代理权限

4. histories（历史记录）
   - 关联案件 ID、案号、输出目录路径、文件数

【要求】
- 用 streamlit 自带的 sqlite3 连接
- 提供 CRUD 函数：upsert_company、list_companies、create_case、search_cases
- 首次启动自动建表 + 预填默认值（北京雷石天地 + 张洋）
- 用 @st.cache_resource 缓存数据库连接
```

**验收**：能从 Streamlit 页面新增公司、查看列表。

### 提示词 1.3 · 模板占位符规范

```text
【上下文】
我有 3 个 Word 模板（法定代表人证明/授权委托书/推荐信），需要程序自动填字段。

【关键设计】
模板里用中文全角【】作为占位符：
- 【】年【】月【】日 → 开庭日期
- 【】纠纷 → 案由描述（自动生成"我方诉XX纠纷"等）
- 【】人民法院 → 审理法院
- 【】 → 案号

【任务】
1. 在 templates/ 放 3 个 Word 模板，每个含【】占位符
2. 写 src/generator.py 的 replace_placeholders() 函数
3. python-docx 自动合并同一段落 runs，无需手动处理
4. 案由描述生成规则：
   - 原告：我方诉{对方}{案由}
   - 被告：{对方}诉我方{案由}
   - 第三人：{对方}与我方{案由}

【避坑】
- 不要用英文 []，必须是中文全角【】
- 如果 Word 把【】拆成几段，python-docx 会自动处理，不用管
```

**验收**：传入案号 "（2026）京0101民初1234号" + 日期 "2026-08-14"，能生成正确的 Word 文件。

---

## 📍 阶段 2：核心功能实现

### 提示词 2.1 · Word → PDF 转换

```text
【任务】
把生成的 docx 转 PDF。我有 2 个选项，选 1 个：

方案 A：libreoffice 命令行（推荐）
- `libreoffice --headless --convert-to pdf input.docx --outdir output/`
- 转换质量好，但需装 LibreOffice
- 跨平台

方案 B：docx2pdf（仅 Windows/macOS）
- pip install docx2pdf
- 调用 Word/WPS 应用
- 仅限有 Office 的电脑

【要求】
1. 优先方案 A，提供 fallback 方案 B
2. 在 src/docx_to_pdf.py 实现 docx_to_pdf() 函数
3. 处理转换超时（30 秒）和失败情况
4. 中文 PDF 字体不能丢（用 STSong-Light）

【避坑】
- 不要尝试用 reportlab 从零生成 PDF（会丢失 Word 模板格式）
- docx2pdf 在 Linux 上不可用
```

**验收**：生成 1 个 docx + 1 个对应 PDF，内容一致。

### 提示词 2.2 · PDF 合并与缩略图

```text
【任务】
1. 用 pypdf 把 7 份 PDF 合并成 1 份，按出庭顺序：
   01_营业执照.pdf → 02_法人身份证.pdf → 03_劳动合同.pdf → 04_代理人身份证.pdf
   → 05_法定代表人证明.pdf → 06_授权委托书.pdf → 07_推荐信.pdf

2. 用 PyMuPDF 生成每页缩略图（base64 PNG）
   - 缩放 0.4x，高质量小图
   - 用于在 Streamlit 卡片展示

3. 在 src/pdf_merger.py 和 src/pdf_thumb.py 实现

【避坑】
- 缩略图不要存文件，直接 base64 内联到 HTML
- 缩略图大小控制在 50KB/页以内（否则 streamlit 卡）
```

**验收**：合并后的 PDF 页数 = 7 份 PDF 总页数；缩略图能在页面显示。

### 提示词 2.3 · ZIP 打包

```text
【任务】
1. 把 outputs/2026-08-13_1/ 整个文件夹打成 ZIP
2. ZIP 内保留原始目录结构
3. 文件名编码用 UTF-8（中文不乱码）
4. 在 src/generator.py 添加 zip_outputs() 函数

【避坑】
- 用 zipfile.ZIP_DEFLATED 压缩
- 中文文件名要 arcname.encode('utf-8').decode('utf-8')，别用 cp936
```

**验收**：下载 ZIP 后解压，中文文件名不乱码，结构完整。

---

## 📍 阶段 3：服务化与部署

### 提示词 3.1 · 服务管理脚本（关键！）

```text
【背景】
法务小白不懂命令行，需要"双击启动"。但直接 nohup 启动服务容易出现：
- 端口被占用
- 多个进程并存
- 关闭终端后服务停了
- 不知道服务有没有在跑

【任务】
写 5 个脚本到 bin/：
1. manage.sh（统一入口：start|stop|restart|status）
2. start.sh（启动）
3. stop.sh（停止，三重验证）
4. restart.sh（重启）
5. status.sh（查看状态）

【关键设计】
- 三重定位进程：PID 文件 + 端口 + 进程名匹配
- 健康检查：curl http://localhost:18501/_stcore/health
- 兼容 macOS bash 3.2（不支持数组+=语法）
- 端口固定 18501（如冲突明确报错，不要自动换端口）
- 颜色输出（GREEN/YELLOW/RED）
- 启动成功后自动 open http://localhost:18501

【避坑】
- 不要用 bash 4 数组语法（macOS 自带 3.2 会报错）
- 不要用 pid 单一验证（进程可能已死但 pid 文件残留）
- 日志写到 .run/streamlit.log，方便调试
- PID 文件路径 .run/streamlit.pid
```

**验收**：`bash bin/manage.sh status` 能完整显示 PID/端口/健康状态。

### 提示词 3.2 · macOS 启动入口

```text
【任务】
写"启动.command"，双击即用：

内容：
```bash
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "$SCRIPT_DIR/bin/manage.sh" start
```

【要求】
- 文件放在项目根目录（用户熟悉的位置）
- 第一行必须有 #!/bin/bash
- 文件可执行权限：chmod +x 启动.command
- 关闭终端窗口不会停止服务（因为用了 nohup）

【避坑】
- 不要用 osascript 弹窗（复杂且不稳定）
- 不要直接 streamlit run（无法后台运行）
```

**验收**：双击 `启动.command` → 终端弹出 + 浏览器自动打开 → 服务在后台运行。

---

## 📍 阶段 4：UI 与体验（v0.3.0 重点）

### 提示词 4.1 · 视觉风格

```text
【背景】
法务每天对着工具看 8 小时，UI 太丑会很难受。但花哨反而显得不专业。

【目标】
参考 Vercel / Linear / Stripe Dashboard，做克制的高端感。

【设计原则】
1. 极简渐变（less is more）：浅紫 + 浅灰，不超过 3 个渐变
2. 字体：Inter（西文）+ PingFang SC（中文）
3. 颜色：
   - 主色：#0a0a0a（接近黑）
   - 成功：#10b981（绿）
   - 警告：#f59e0b（橙）
   - 错误：#ef4444（红）
4. 圆角：8px-12px（不尖锐也不过分圆润）
5. 微动画：hover 抬升 + transition 0.15s
6. 暗色模式支持

【避坑】
- 不要用 emoji 当图标（除非作为装饰）
- 不要用 Material Design 风（太大众）
- 不要背景图（影响性能）
- gradient 文字、徽章要克制
```

**验收**：从截图能看出"高端感"，不是普通的 Streamlit 默认样式。

### 提示词 4.2 · PDF 浏览器内预览（最关键！）

```text
【核心问题】
法务需要在出庭前在浏览器内查看 PDF（确认无误后再去打印）。
但直接用 PDF.js 有 3 大坑：

坑 1：Streamlit SPA 路由拦截
- 访问 /static/pdfjs/pdf.min.js → 返回 HTML 不是 JS
- 浏览器报 "Expected JavaScript module but got text/html"

坑 2：sandboxed iframe 不能访问 CDN
- PDF.js 库是 ~1.3MB 不能用 CDN
- iframe sandbox 阻止跨域请求

坑 3：Streamlit 新版 API 变更
- st.image(use_column_width=True) 已废弃
- 应改用 use_container_width=True

【解决方案：PDF.js 全内联 + base64 data URI】
1. 把 pdf.min.js + pdf.worker.min.js 用 base64 内联到 components.html
2. Worker 通过 Blob URL 注入：`URL.createObjectURL(new Blob([Uint8Array.from(atob(workerB64), c=>c.charCodeAt(0))], {type:'application/javascript'}))`
3. 主库用 eval + inline script 执行：`eval(atob(mainB64))` ← 关键！
4. PDF 文件作为 `pdfjsLib.getDocument({data: atob(PDF_B64)})` 传入

【关键陷阱】
- ❌ 不能用 new Function(mainCode)，因为 var pdfjsLib 不会泄漏到外层
- ✅ 必须用 inline <script>eval(atob(mainB64))</script>，让 var 暴露到当前作用域

【实现步骤】
1. src/pdf_viewer_component.py 重写 render_pdf_viewer_component()
2. @st.cache_resource 缓存 PDF.js 库 base64（避免每次重编码）
3. PDF 按需编码（每个 PDF 单独编码一次）
4. 工具栏：缩小/放大/上一页/下一页/打印全部
5. @media print 隐藏工具栏

【降级方案】
保留"系统 Preview 打开"按钮（macOS 原生），调用 subprocess.Popen(["open", pdf])
```

**验收**：浏览器内能正常显示 PDF，中文清晰，缩放/翻页/打印全部可用。

---

## 📍 阶段 5：故障排查与稳定性

### 提示词 5.1 · 故障排查清单

```text
【背景】
项目跑起来后，肯定会遇到问题。需要提前列出排查清单。

【常见问题】
1. PDF.js 显示 "pdfjsLib is not defined"
   → 检查是否用了 new Function()，应改用 eval + inline script

2. 浏览器内 PDF 一直白屏
   → 打开 .run/streamlit.log 看是否有 "use_column_width" 错误
   → 应改用 use_container_width

3. 直接访问 http://localhost:18501/static/merged/*.pdf 拿到 HTML 不是 PDF
   → 这是 Streamlit SPA 路由正常行为，不要用 HTTP URL 加载 PDF

4. 服务启动但浏览器打不开
   → bash bin/manage.sh status 检查 HTTP 状态
   → 不健康时看 .run/streamlit.log 末尾 20 行

5. macOS bash 3.2 报 "syntax error near unexpected token `('"
   → 检查 bin/*.sh 是否用了 bash 4 数组语法（+= 之类）
   → 改用字符串拼接 + tr/sed

【排错模板】
每次出问题，按这个顺序排查：
1. bash bin/manage.sh status（服务在不在）
2. tail -50 .run/streamlit.log（日志说什么）
3. lsof -i :18501（端口被谁占）
4. cat .run/streamlit.pid（PID 文件对不对）
```

---

## 📍 完整推进时间线

| 阶段 | 内容 | 估时 |
|---|---|---|
| 阶段 0 | 业务理解 + 立项 | 1 天 |
| 阶段 1 | MVP（数据 + 模板 + 替换） | 3 天 |
| 阶段 2 | Word/PDF/缩略图/ZIP | 3 天 |
| 阶段 3 | 服务化脚本 + 启动入口 | 1 天 |
| 阶段 4 | UI 风格 + PDF 浏览器预览 | 5 天 |
| 阶段 5 | 故障排查 + 稳定性 | 持续 |

总计：**约 2 周**，从 0 到能用的工具。

---

## 🎯 给小白的核心建议

1. **不要一次性做完所有功能**：先做 MVP（提示词 1.1-1.3），能用就行
2. **每完成一个提示词就测试**：不要憋到最后再调试
3. **服务管理脚本是基础设施**：宁愿花 2 天写好，不要图省事直接 `streamlit run &`
4. **PDF 浏览器内预览是最大坑**：99% 的时间会卡在这里，建议先看完整提示词 4.2 再动手
5. **保留降级方案**：macOS 系统 Preview 是最后的救命稻草，任何时候都不能删

---

## 📝 使用本指南的方式

- **从 0 开始**：按顺序执行阶段 0 → 5 的所有提示词
- **借鉴到其他法务工具**：阶段 0 + 1.1 + 3.1 + 4.1 是核心骨架
- **培训新人**：阶段 1 + 2 是"做什么"，阶段 3 + 4 是"怎么做得专业"
- **二次开发**：从阶段 5（故障排查）开始，能快速定位现有问题
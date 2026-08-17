---
title: "reportlab内置STSong-Light生成中文PDF技能"
usage_scenario:
    - "macOS环境下无LibreOffice时稳定生成含中文的PDF"
    - "需要程序化合并多个docx为单个PDF且保证中文显示"
    - "避免AppleScript或WPS CLI等GUI依赖的自动化PDF输出"
keywords:
    - "reportlab"
    - "STSong-Light"
    - "中文PDF"
    - "macOS PDF生成"
source: "auto"
---

## 输入
- 多个 .docx 文件路径（如 7 份出庭手续模板）
- 目标：生成单个含中文、排版规范的 PDF，并支持后续合并与打印

## 步骤
1. 使用 `reportlab` 的 `UnicodeCIDFont('STSong-Light')` 注册内置中文字体（避免 `STHeiti-Light` 等不支持字体报错）
2. 构建 `ParagraphStyle` 指定 `fontName='STSong-Light'` 及字号、行距、缩进等样式
3. 对每个 docx 文件解析其文本内容（需额外解析逻辑，本技能聚焦 PDF 生成环节）
4. 用 `SimpleDocTemplate` 逐页写入各文档内容，控制页边距（如 `leftMargin=2.5*cm`）
5. 合并多个 PDF 使用 `pypdf.PdfWriter().add_page()` 或 `pypdf.PdfMerger`

## 输出
- 单个 PDF 文件，含正确渲染的中文（宋体）、合规段落缩进、页边距和标题层级
- 文件可被 macOS 预览或系统打印服务直接识别并在线打印

## 注意事项
- `reportlab` 内置仅支持 `'STSong-Light'`（中文字体），其他如 `'STHeiti-Light'` 会触发 `KeyError`；无需下载外部字体文件
- `sips -s format png <pdf> --out <png>` 可快速预览 PDF 渲染效果（macOS 原生命令）
- 若需保留 docx 原格式（表格/图片），应改用 `python-docx` + `reportlab` 组合解析，但纯文本场景 `STSong-Light` 方案最轻量可靠

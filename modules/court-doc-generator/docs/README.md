# 智能出庭文书 · Court Document Generator

> 出庭手续文档生成器 — 从 Qoder 对话记录中恢复（2026-08-14）

## 功能

7份出庭材料一键生成：法定代表人证明、授权委托书、推荐信、营业执照、法人身份证、劳动合同、代理人身份证。

支持：Word模板填充 → DOCX → PDF → 合并PDF → ZIP打包 → 浏览器内预览打印。

## 技术栈

- **前端**：Streamlit（端口18501）
- **Word处理**：python-docx
- **PDF处理**：pypdf + PyMuPDF
- **数据库**：SQLite
- **PDF预览**：PDF.js（全内联 base64 data URI 方案）

## 源码

```
court-doc-generator/
├── app.py              # Streamlit主界面
├── config.py           # 配置
├── database.py         # SQLite数据模型
├── generator.py        # 模板填充+ZIP打包
├── docx_to_pdf.py      # Word转PDF
├── pdf_merger.py       # PDF合并
├── feishu_api.py       # 飞书API
└── docs/
    ├── README.md       # 本文档（中文）
    └── PROMPTS.md      # 完整提示词手册（417行，从Qoder恢复）
```

## 运行

```bash
streamlit run app.py --server.port 18501
```

## 拍照扫描功能

**状态**：规划中（待澄清需求）

- 拍照生成扫描件？
- 拍照后扫描识别内容？
- 用途和场景待确认。

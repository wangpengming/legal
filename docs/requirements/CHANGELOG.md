# 需求变更记录 / Change Log

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2026-08-17 | 1.0.0 | 初始化系统骨架 | zhang yang |
| 2026-08-17 | 1.1.0 | 出庭手续生成器：出 REQUIREMENTS.md（434 行）+ SPEC.md（1262 行），覆盖 23 项 MoSCoW + 5 项关键决策评分 + 7 阶段实施 Checklist | pengming |
| 2026-08-17 | 1.2.0 | 出庭手续生成器全面开发至 v1.1.0：修复 src import 错 + agents 唯一性 + PII 移除；接入 docx_to_pdf + pdf_merger；实现 pdf_viewer_component PDF.js 全内联；bin/ 跨平台脚本（start/stop/restart/status + macOS .command + Windows .bat）；tests/ 5 份单测；README 三平台指引；feishu_api STUB 标注 | pengming |
| 2026-08-17 | 1.2.1 | v1.1.2 修复：仅预览真预览（生成到临时目录 + PyMuPDF 缩略图）；生成后顶部固定结果卡片（7 张缩略图网格 + 文件清单 + 下载按钮 + 浏览器内 PDF.js 预览器）。新增 _scroll_to_top_once()：Streamlit rerun 后自动滚动 [data-testid="stMain"] 到顶部（修复用户卡在表单中段看不到结果卡片的 bug）。pdf_thumb.py 新增；generator.py 拆分 _generate_to_dir / generate_preview 共享内核；tests/ 22→37 PASS | pengming |
| 2026-08-17 | 1.3.0 | 双子模块并入 legal：litigation-system（active v0.2.0，FastAPI+React，128 文件）+ case-intelligence（planning v3.0.0，NocoDB+Paperless-ngx，方案设计）迁入 modules/；补 module.yaml/docs/SPEC.md；index.yaml 注册 3 模块；根 README（目录+关系图）与 docs/README、docs/SPEC v1.1（模块清单/数据流/演进说明）同步更新 | 张洋 - 法务部 |
| 2026-08-17 | 1.4.0 | 全库一致性修复：court-doc-generator 版本统一 v1.1.4，docs/ 83 文件 git restore 恢复；.gitignore 去掉 `.*` 一刀切（.qoder/、.env 允许提交，仅保留 secrets/credentials 密钥红线）；三模块 deps 统一为模块依赖语义；SPEC/README/backlog 声明性修正（shared/tools 标规划中、版本约定统一 semver、case-intelligence 清理不存在的文档引用） | pengming |
| 2026-08-17 | 1.5.0 | AGENTS.md 模块完整性原则升级：新增 §1.5 总纲（7 维表格）、§10.4 模块基础设施规范（脚本 4 件套 + 端口管理 + 路由架构 + 健康检查）、§10.2 补强 4 条禁令、§11.1 端口注册表联动；新建 shared/config/ports.yaml（3 模块 14 个端口统一登记）；三模块 module.yaml 补 port 字段（court-doc-generator 18501/19000、litigation-system 8000/8080/18000、case-intelligence 7 容器端口） | pengming |

# litigation-system 模块文档索引

> 模块：诉讼业务平台 · 集成日期：2026-08-17（并入 legal/modules/）
> 作者：张洋 - 法务部

| 文档 | 说明 |
|------|------|
| [../README.md](../README.md) | 模块总览（启动 / 环境变量 / 测试 / 验证基线） |
| [../spec/SPEC.md](../spec/SPEC.md) | 系统规格 SPEC v0.2（需求 / 实测数据源 / 技术方案 / MCP 报告模板） |
| [../requirements/01-需求规格说明书.md](../requirements/01-需求规格说明书.md) | 需求基线 v1.0（用户画像 / 场景 S1~S10 / 功能模块 F1.1~F6.4 / 口径操作化） |
| [01-飞书应用信息.md](./01-飞书应用信息.md) | 飞书应用与多维表格元数据（App Secret 不落文档） |
| [02-详细设计-前端.md](./02-详细设计-前端.md) | 前端详细设计（双主题 token / 页面 / 组件） |
| [03-详细设计-后端.md](./03-详细设计-后端.md) | 后端详细设计（同步引擎 / 清洗管道 / 指标口径 / API 面） |
| [04-交付物索引.md](./04-交付物索引.md) | 交付物索引 |
| [05-设计验收清单.md](./05-设计验收清单.md) | 验收记录（2026-08-13 签核：79 项 77✓ + 2 豁免） |
| [prototypes/](./prototypes/) | 12 个高保真可交互原型（00~11） |

## 调研资料（research/）

| 文档 | 说明 |
|------|------|
| [research/01](../research/01-网络判决数据源调研.md) | 网上判决数据源选型（裁判文书网萎缩 → 案例库/商业 API） |
| [research/02](../research/02-法务系统产品调研.md) | 大厂法务系统 / 律所平台产品形态 |
| [research/03](../research/03-飞书API能力调研.md) | 飞书 API 细节核验（限频 / 分页 / Formula 返回值） |
| [research/04](../research/04-前端视觉调研.md) | 法务 / B2B 数据产品暗亮主题视觉参考 |

## 其他

- 环境变量：仅存 `.env`（`.gitignore` 防护），模板见 [../.env.example](../.env.example)，字段含义见 [module.yaml](../module.yaml)
- 运行时数据：`data/app.db`（SQLite WAL，`.gitignore` 排除，提交仅源码）
- 后端接口契约：[backend/tests/test_api.py](../backend/tests/test_api.py)
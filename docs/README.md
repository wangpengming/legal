# Legal System 文档索引

## 必读文档

| 文档 | 说明 |
|------|------|
| [../README.md](../README.md) | 项目总览 |
| [SPEC.md](./SPEC.md) | 系统规格 |
| [deployment-thunderbox.md](./deployment-thunderbox.md) | thunderbox（雷石盒子）部署手册（GitHub 通道 / MCP / 域名申请） |
| [requirements/backlog.md](./requirements/backlog.md) | 需求池 |

## 模块文档

各模块文档位于 `modules/<module-name>/docs/`：

| 模块 | 文档入口 | 状态 |
|------|---------|------|
| court-doc-generator | [modules/court-doc-generator/docs/](../modules/court-doc-generator/docs/) | active |
| litigation-system | [modules/litigation-system/docs/](../modules/litigation-system/docs/) | active |
| case-intelligence | [modules/case-intelligence/docs/](../modules/case-intelligence/docs/) | planning |
| portal | [modules/portal/docs/](../modules/portal/docs/) | planning |

## 共享配置（注册表）

| 文件 | 说明 |
|------|------|
| [../shared/config/ports.yaml](../shared/config/ports.yaml) | 模块端口注册表（§10.4.2） |
| [../shared/config/domains.yaml](../shared/config/domains.yaml) | 模块域名注册表（thunderbox · 一模块一域名，§10.4.5） |

## 更新日志

变更记录在 `docs/requirements/CHANGELOG.md`

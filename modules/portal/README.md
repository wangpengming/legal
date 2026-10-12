# Legal Portal · 法务统一门户

> 第 4 模块：注册表驱动的子系统集成框架 + 系统健康监控总览
> 状态：**planning**（原型已交付并自测通过，正式版规划中） · 版本 0.1.0

## 定位

把散落在多个端口的异构子系统（court / litigation / case）收敛为**单一入口**，并提供子系统健康监控总览。通过同源反代（nginx）+ `apps.yaml` 注册表实现「即插即用」：新增模块 = 注册表加一行 + 反代加一段。

**明确不做（v1 边界）**：统一认证/SSO、微前端、案件数据驾驶舱深挖。

## 快速体验

```bash
# 方式一：浏览器直接打开（file://，交互功能完整）
open modules/portal/prototype.html

# 方式二：本地 HTTP 服务（推荐，与生产同源反代路径一致）
python3 -m http.server 8622 --bind 127.0.0.1
# 浏览器访问 http://127.0.0.1:8622/prototype.html
```

## 部署与域名（thunderbox / 雷石盒子）

- **本模块域名（唯一）**：`legal-portal.tbox.ktvsky.com` · `access_mode=internal`
- **代码来源**：**仅支持 GitHub** —— 部署前须先把代码迁移到 GitHub 仓库
- **平台信息**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`
- **生产形态（规划）**：nginx 同源反代 + 静态页面

> 🔴 **域名规则**：每个模块**有且仅有一个域名**，不得随意创建；域名统一登记 `shared/config/domains.yaml`（详见 `AGENTS.md §10.4.5`）。
> 📖 系统级部署手册：[docs/deployment-thunderbox.md](../../docs/deployment-thunderbox.md)

## 文档

- [docs/SPEC.md](docs/SPEC.md) — Portal v0.1 规格（设计语言 / 同源反代架构 / apps.yaml 注册表 / 健康监控协议 / 验收标准）
- [docs/README.md](docs/README.md) — 模块文档索引
- [prototype.html](prototype.html) — 单文件交互原型

## 模块元数据

见 [module.yaml](module.yaml)（含 `domain` 字段）。
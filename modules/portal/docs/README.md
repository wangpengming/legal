# Legal Portal 模块文档

> 第 4 模块：法务部统一门户 —— 注册表驱动的子系统集成框架 + 系统健康监控总览

## 文档

| 文档 | 说明 |
|------|------|
| [SPEC.md](./SPEC.md) | Portal v0.1 规格说明书（设计语言 / 同源反代架构 / apps.yaml 注册表 / 健康监控协议 / 验收标准） |
| [../prototype.html](../prototype.html) | 单文件交互原型（自包含，无外部依赖，浏览器直接打开即可体验） |

## 状态

- **阶段**: planning（原型已交付并自测通过，正式版未开始）
- **版本**: 0.1.0
- **入口**: prototype.html
- **域名（唯一）**: `legal-portal.tbox.ktvsky.com`（`access_mode=internal`，thunderbox）
- **集成对象**: court-doc-generator(:18501) · litigation-system(:8000) · case-intelligence(:18503)

## 部署与域名（thunderbox / 雷石盒子）

- **本模块域名（唯一）**：`legal-portal.tbox.ktvsky.com` · `access_mode=internal`
- **代码来源**：**仅支持 GitHub** —— 部署前须先把代码迁移到 GitHub 仓库
- **平台信息**：控制台 `https://box.tbox.ktvsky.com/` · MCP 端点 `https://api-box.tbox.ktvsky.com/mcp`

> 🔴 **域名规则**：每个模块**有且仅有一个域名**，不得随意创建；域名统一登记 `shared/config/domains.yaml`（详见 `AGENTS.md §10.4.5`）。
> 📖 系统级部署手册：[docs/deployment-thunderbox.md](../../docs/deployment-thunderbox.md)

## 快速体验

```bash
# 方式一：浏览器直接打开（file://，交互功能完整）
open modules/portal/prototype.html

# 方式二：本地 HTTP 服务（推荐，与生产同源反代路径一致）
python3 -m http.server 8622 --bind 127.0.0.1
# 浏览器访问 http://127.0.0.1:8622/prototype.html
```

## 接入新子系统（正式版）

1. `apps.yaml` 注册表新增一行（name / title / path / health / port / version / entry）
2. nginx 反代新增一段 `location /xxx { proxy_pass http://127.0.0.1:PORT; }`
3. 子系统提供健康端点（`/_stcore/health` 或 `/api/health*`），返回 200 即判定在线
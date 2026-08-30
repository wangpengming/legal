# Rules 索引

> AI 代理在此项目工作时必读的规则文件。

| 文件 | 用途 | 优先级 |
|------|------|--------|
| [AGENTS.md](./AGENTS.md) | 工程行动约束、命名规范、安全红线、开发流程 | 🔴 必读 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Thunderbox 部署规范、常见错误速查 | 🔴 必读（部署时） |
| [PITFALLS.md](./PITFALLS.md) | 已知坑与修复方案 | 🟡 查阅 |

---

## 快速索引

### 🔴 安全红线
- **PII 禁止硬编码** — 见 AGENTS.md §6
- **git push 需用户授权** — 见 AGENTS.md §13.2
- **PDF.js 必须用 eval** — 见 PITFALLS.md §1

### 🔴 部署红线
- **tesseract 必须安装** — 见 DEPLOYMENT.md §3.1
- **volumes 必须挂载** — 见 DEPLOYMENT.md §4.2
- **git_token 公开仓库不传** — 见 DEPLOYMENT.md §2.2

### 🟡 常见坑
- **scan_service 惰性初始化** — 见 PITFALLS.md §2
- **测试数据隔离** — 见 PITFALLS.md §3
- **浏览器缓存** — 见 PITFALLS.md §4

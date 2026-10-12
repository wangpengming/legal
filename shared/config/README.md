# Shared Config 共享配置

本目录存放跨模块共享的配置文件与注册表。

## 目录结构

```
shared/config/
├── ports.yaml        # 模块端口注册表（启动前冲突检测，详见 AGENTS.md §10.4.2）
└── domains.yaml      # 模块域名注册表（thunderbox 一模块一域名，详见 AGENTS.md §10.4.5）
```

## 注册表说明

| 文件 | 用途 | 联动规则 |
|------|------|---------|
| `ports.yaml` | 每个模块端口分配（Streamlit/FastAPI/前端/容器等） | `module.yaml` 的 `port` 字段须与本表一致 |
| `domains.yaml` | 每个模块在 thunderbox 上的唯一域名 | `module.yaml` 的 `domain` 字段须与本表一致 |

## 配置规范

- 所有配置使用 YAML 格式
- 敏感信息通过环境变量注入，不硬编码（thunderbox token 严禁写入仓库）
- 遵循 12-Factor App 配置原则

## 关键区别

- **端口**：一个模块可有多个端口（后端 / 前端 / 容器）
- **域名**：一个模块**有且仅有一个域名**，创建即绑定、不得随意新建
# Shared Config 共享配置

本目录存放跨模块共享的配置文件。

## 目录结构

```
shared/config/
├── base.yaml         # 基础配置
├── dev.yaml         # 开发环境配置
└── prod.yaml        # 生产环境配置
```

## 配置规范

- 所有配置使用YAML格式
- 敏感信息通过环境变量注入，不硬编码
- 遵循12-Factor App配置原则

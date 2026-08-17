---
title: "bin目录统一服务管理脚本体系"
usage_scenario:
    - "新增服务管理功能时复用脚本结构"
    - "跨平台部署时参考sh/bat双套实现模式"
    - "排查服务启停异常时查阅脚本逻辑"
keywords:
    - "bin目录"
    - "服务管理脚本"
    - "court-matters"
    - "统一入口"
    - "三重识别"
source: "auto"
---

项目构建与服务管理采用统一脚本体系：
- 脚本存放于`bin/`目录，包含`manage.sh/.bat`（统一入口）、`start.sh/.bat`、`stop.sh/.bat`、`restart.sh/.bat`、`status.sh/.bat`；
- 支持三重服务识别：PID文件、端口占用、进程名；
- 服务名称为`court-matters`；
- 启动脚本保留原`启动.command`位置，实际调用`bin/manage.sh start`。

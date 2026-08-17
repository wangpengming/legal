---
title: "macOS bash 3.2 不支持数组+=语法及修复方案"
usage_scenario:
    - "在macOS上编写可移植shell脚本时出现unexpected token错误"
    - "部署脚本到未升级bash的macOS机器时报语法错误"
    - "需要兼容bash 3.2的跨平台服务管理脚本"
keywords:
    - "bash 3.2"
    - "macOS"
    - "数组语法"
    - "stop.sh"
source: "auto"
---

macOS 自带 bash 版本为 3.2，不支持 `pids+=($pid)` 这类数组追加语法，导致 `stop.sh` 执行报错 `syntax error near unexpected token 'fi'`。修复方式：改用空格分隔字符串拼接（`pids="$pids $pid"`），配合 `case " $pids " in ...` 去重逻辑，并用 `echo "$pids" | tr ' ' '\n' | grep -v '^$' | sort -u` 输出唯一 PID 列表。（来源：Bash）

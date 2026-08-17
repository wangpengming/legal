---
title: "使用 Cloudflare Tunnel 实现本地服务公网访问技能"
usage_scenario:
    - "需要将本地开发的服务分享给外部同事试用"
    - "公司内网无法直接访问但允许 HTTPS 出站"
    - "快速搭建临时公网入口进行演示"
keywords:
    - "Cloudflare Tunnel"
    - "本地服务共享"
    - "内网穿透"
    - "brew install"
source: "auto"
---

## 输入
- 本地运行的服务端口（如 18501）
- 已安装 Homebrew 的 macOS/Linux 环境

## 步骤
1. **诊断网络环境**：使用 `curl` 测试本机真实 IP、外网访问能力（如 `baidu.com`, `trycloudflare.com`），确认公司防火墙是否允许 HTTPS 出网。
2. **安装工具**：通过 `brew install cloudflared` 安装 Cloudflare Tunnel 客户端。
3. **编写启动脚本**：创建脚本自动检查依赖、启动本地服务（若未运行）、并执行 `cloudflared tunnel --url http://localhost:{端口}`。
4. **获取公网 URL**：运行脚本后，从终端输出中复制生成的 `https://xxx.trycloudflare.com` 地址。
5. **分享与验证**：将 URL 发送给同事，确保其浏览器可访问；关闭时按 Ctrl+C。

## 输出
一个临时的公网 HTTPS 访问链接，同事无需配置即可在浏览器中使用本地服务。

## 注意事项
- **临时性**：每次重启隧道，域名会变化；需保持终端窗口打开。
- **网络依赖**：依赖公司网络允许 HTTPS 出站（Cloudflare 域名通常可通）。
- **适用场景**：适合短期试用或演示；长期部署建议自建账号或使用内网穿透方案。
- **扩展资源**：Cloudflare Tunnel 官方文档：https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/run-tunnel/

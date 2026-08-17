---
title: "Cloudflare Tunnel 公网共享方案"
usage_scenario:
    - "需要让外部同事试用本地运行的 Web 应用时"
    - "排查网络连通性问题导致内网 IP 无法访问时"
keywords:
    - "Cloudflare Tunnel"
    - "公网 URL"
    - "临时隧道"
source: "auto"
---

项目对外共享时，不直接使用内网 IP（如 192.168.x.x），而是通过 Cloudflare Tunnel 生成临时公网 URL（https://xxx.trycloudflare.com）供同事访问

# Legal Portal 规格说明书 v0.1（原型阶段）

> 法务部门统一门户与子系统集成框架
> 状态：**planning** · 交付物：`prototype.html` 单文件交互原型
> 更新时间：2026-08-17

## 1. 定位与目标

Legal Portal 是 legal monorepo 的第 4 个组成模块，承担：

1. **统一入口**：把散落在 4 个端口的异构子系统收敛为单一域名/路径
2. **门面**：符合法务部门气质（庄重、商务蓝、稳重大气）的品牌界面
3. **集成框架**：以注册表（YAML）驱动的"即插即用"子系统挂载标准
4. **健康监控**（v1 核心功能）：三子系统在线状态、版本、心跳、一键跳转

**明确不做**（v1 边界）：统一认证/SSO、微前端（qiankun/Module Federation）、案件数据驾驶舱深挖。

## 2. 设计语言

### 2.1 视觉基调

法务的庄重 + 商务蓝 + 浅色 · 稳重大气耐看。克制的高级感，拒绝炫彩。

### 2.2 色板

| 角色 | 色值 | 用途 |
|------|------|------|
| 主色-司法深蓝 | `#1F3A93` | 品牌核心、欢迎页渐变基底 |
| 辅色-商务蓝 | `#2B5BCE` | 主按钮、激活态、数据强调 |
| 辅色-浅蓝 | `#6C8CD5` / `#8FA8E0` | 渐变过渡、小图标 |
| 点缀-金色 | `#B7984D` | 徽标细线、分隔线、法徽质感（克制使用） |
| 警示-印章红 | `#C0392B` | 仅用于离线/告警状态 |
| 背景 | `#F5F7FA` | 主框架底色（浅灰蓝） |
| 卡片 | `#FFFFFF` | 内容容器 |
| 分隔线 | `#E3E9F2` | 1px 细线 |
| 文字主/次 | `#1F2A44` / `#5A6A8C` | 正文层级 |

### 2.3 字体与组件语言

- 中文：苹方（macOS）/ 思源黑体（Linux）；系统回退 sans-serif
- 数字/端口/版本：等宽字体 `ui-monospace / SFMono / Consolas`
- 圆角 8~10px、1px 细线分隔、柔和极浅阴影、大面积留白
- 动效：`transition 0.2s`、hover 轻微上浮；状态点呼吸动画；数字跳动反馈

### 2.4 页面结构（原型）

```
欢迎页（门面，可选登录）
├── 深蓝渐变背景 + 金色细线天平徽标（SVG 内联）
├── 三张子系统玻璃卡片（名称 / 简介 / 在线状态点）
└── 进入工作台

主框架
├── 顶栏：徽标 + Legal Portal + 实时时钟 + 返回欢迎页
├── 侧栏：总览 / 三个子系统 / 日志
└── 内容区（四视图之一）
    ├── Dashboard 总览：统计条 + 健康监控卡片
    ├── 子系统视图：同源 iframe 嵌入（原型中用模拟窗口占位）
    └── 日志面板：模拟 tail 输出
```

## 3. 系统架构

### 3.1 同源反代（nginx）

```
浏览器 ─→ Portal (React 18 · :3000)
             │
             ├─ /            → Portal 主框架
             ├─ /court       → nginx 反代 ─→ court-doc-generator     (:18501 · Streamlit)
             ├─ /litigation  → nginx 反代 ─→ litigation-system       (FastAPI + React)
             ├─ /case        → nginx 反代 ─→ case-intelligence       (:8090 · NocoDB)
             └─ /api/heartbeat → Portal 后端聚合三系统健康状态
```

同源反代三大收益：iframe 无跨域、健康轮询无 CORS、URL 由 4 端口收敛为 1 入口。

### 3.2 反代要点

- Streamlit 需配置 `X-Frame-Options: ALLOWALL`（或反代层去掉该头）方可被 iframe 嵌入；WebSocket（`ws://.../court/_stcore`）需 `Upgrade` 头透传
- litigation-system 静态资源走 `/litigation/static` 相对路径，避免绝对路径破链
- 后端服务仅绑定内网（10.10.11.37），Portal 不暴露公网

## 4. 注册表驱动框架（核心）

### 4.1 apps.yaml schema

```yaml
apps:
  - name: court-doc-generator
    title: 出庭手续生成器
    description: 7 份出庭材料一键生成
    color: "#2B5BCE"          # 品牌主色（用于徽章/强调）
    path: /court              # nginx 反代路径
    health: /court/_stcore/health
    version: 1.1.4
    port: 18501
    entry: app.py
  - name: litigation-system
    title: 诉讼业务平台
    description: 案件台账 / 飞书同步 / 文书管理
    color: "#1F3A93"
    path: /litigation
    health: /litigation/api/health
    version: 0.2.0
    port: 8000
    entry: backend 服务 + frontend 构建
  - name: case-intelligence
    title: 卷宗检索与规则
    description: 同质化案件检索 / 文档规则化
    color: "#B7984D"
    path: /case
    health: /case/api/healthz
    version: 3.0.0
    ports: [8090, 8091]       # NocoDB / Paperless
    entry: docker compose
```

### 4.2 驱动规则

- 侧栏导航、欢迎页卡片、健康总览卡片、子系统视图**全部由 apps.yaml 动态渲染**
- 新增模块 = 在 `apps.yaml` 加一行 + nginx 加一段反代 → 即插即用
- 原型中 APPS 数组即 apps.yaml 的 JS 映射，后续正式实现按同一 schema 对接

## 5. 健康监控协议（v1 核心功能）

### 5.1 端点约定

| 子系统 | 健康端点 | 期望响应 |
|--------|----------|----------|
| court-doc-generator | `/_stcore/health` | 200 JSON |
| litigation-system | `/api/health`（待补） | `{"status":"ok","version":"0.2.0"}` |
| case-intelligence | `/api/healthz`（待补） | `{"status":"ok"}` |

### 5.2 状态机

```
online   = 最近 2 次心跳成功
degraded = 心跳失败 1 次（抖动）
offline  = 连续 3 次心跳失败 / 超时
```

- 轮询间隔：10~30s（原型中 3~6s 加速演示）
- 状态灯：绿(online) / 琥珀(degraded) / 红(offline)，呼吸动画

### 5.3 总览卡片字段

`状态灯 · 子系统名 · 版本 chip · 端口（等宽）· 上次心跳 · 在线时长 · 一键进入 · 刷新`

## 6. 首版功能范围

### P0（原型已含）

1. 欢迎页（品牌门面）
2. 主框架（顶栏 / 侧栏 / 内容区）
3. Dashboard 健康监控总览（全真数据设计，原型为模拟心跳）

### P1（原型演示 + 后续 React 正式版）

4. heartbeat 历史趋势图（近 24h uptime）
5. 一键启停（后端代理调用 `bin/start.sh` / `docker compose`）
6. 日志面板

### 边界外：认证 / SSO、态势驾驶舱深挖、微前端

## 7. 验收标准

- [x] `prototype.html` 单文件自包含（内联 CSS/JS，无外部依赖）可离线打开
- [x] 商务蓝浅色庄重视觉：主色/辅色/金色点缀/印章红告警全部落地
- [x] 欢迎页 → 工作台 → 子系统视图 → 日志 全链路可交互
- [x] 注册表 APPS 数组驱动导航与卡片（演示 "加一行即加一模块"）
- [x] 健康状态模拟：在线/降级/离线状态点可切换、心跳时间刷新
- [x] 浏览器实测无控制台报错、无图片素材依赖
- [ ] React 正式版（后续）按 SPEC → 接入 apps.yaml + nginx 反代（未开始）

## 8. 演进路线

- **v0.2（正式版）**：React 18 + Vite + Tailwind 实现，nginx 反代上线，接入真实健康端点
- **v0.3**：飞书免登（与 litigation-system 飞书生态衔接）、心跳趋势图、一键启停
- **v0.4（可选）**：案件态势驾驶舱（调 litigation-system 数据）

## 9. 安全与风险

1. 无认证 → 仅内网部署；健康/日志数据同为敏感信息，勿暴露公网
2. Streamlit iframe 需要 X-Frame-Options / WebSocket 透传实测验证
3. 微前端路线演进时，litigation-system 迁入留灰度窗口
4. 心跳频率控制（10~30s），避免打挂子系统
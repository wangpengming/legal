# Thunderbox Console · Design System Specification

> Version: 1.2 · 2026-08-26
> 状态：原型阶段 · 实现版同步本规范

---

## 1. 设计原则

1. **三层 Token 架构**（Primitive → Semantic → Component），主题切换仅改 Semantic 层
2. **暗色优先**，商务白为辅，系统跟随可选
3. **零伪造数据**：所有模拟数据标注 API 来源，实现版替换为真实调用
4. **静态 HTML 原型**：无需 HTTP 服务，直接浏览器打开即可

---

## 2. 三层 Token 模型

### Tier 1 — Primitive（原子值）

不直接被组件引用。同一 Token 在所有主题中值相同（如 `--accent: #3B82F6` 始终是蓝色）。

```css
/* 暗色主题 Primitive */
:root, [data-theme="dark"] {
  --p-bg-0:    #070B14;
  --p-bg-1:    #0B111E;
  --p-bg-2:    #0F1728;
  --p-bg-card: #121B2D;
  --p-bg-c2:   #0E1523;
  --p-bg-c3:   #182338;
  --p-line:    #1D2A42;
  --p-line2:   #28384F;
  --p-txt:     #E6ECF5;
  --p-txt2:    #93A3BC;
  --p-txt3:    #5B6B85;
  --p-blue:    #3B82F6;
  --p-blue2:   #60A5FA;
  --p-cyan:    #22D3EE;
  --p-green:   #10B981;
  --p-amber:   #F59E0B;
  --p-red:     #EF4444;
  --p-violet:  #8B5CF6;
  --p-term-bg: #090E1A;
  --p-term-txt:#B8C6DC;
  --p-term-ln: #4B5C76;
  --p-shadow:  0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
  --p-glow:    0 0 0 1px rgba(59,130,246,.35), 0 8px 30px rgba(59,130,246,.18);
}
```

### Tier 2 — Semantic（主题感）

组件引用这一层。**主题切换只改这里**。

```css
/* 暗色 Semantic */
:root, [data-theme="dark"] {
  --bg-base:    var(--p-bg-0);      /* 页面底色 */
  --bg-base2:   var(--p-bg-1);      /* 侧栏背景 */
  --bg-base3:   var(--p-bg-2);      /* 输入框背景 */
  --bg-surface: var(--p-bg-card);   /* 卡片背景 */
  --bg-surface2: var(--p-bg-c2);    /* 次级卡片 */
  --bg-surface3: var(--p-bg-c3);    /* 高亮背景 */
  --border:     var(--p-line);      /* 主边框 */
  --border2:    var(--p-line2);     /* 次级边框 */
  --text:       var(--p-txt);       /* 主文字 */
  --text2:      var(--p-txt2);      /* 次级文字 */
  --text3:      var(--p-txt3);      /* 占位/提示文字 */
  --accent:     var(--p-blue);      /* 主按钮/链接 */
  --accent2:    var(--p-blue2);     /* 主文字链接 hover */
  --accent3:    var(--p-cyan);      /* 强调色 */
  --grad:       linear-gradient(135deg,#3B82F6 0%,#22D3EE 100%);
  --grad-soft:  linear-gradient(135deg,rgba(59,130,246,.16),rgba(34,211,238,.10));
  --shadow:     var(--p-shadow);
  --shadow-glow: var(--p-glow);
  --term-bg:    var(--p-term-bg);
  --term-txt:   var(--p-term-txt);
  --term-ln:    var(--p-term-ln);
  /* 状态色不随主题变 */
  --green:  #10B981;
  --amber:  #F59E0B;
  --red:    #EF4444;
  --violet: #8B5CF6;
}

/* 亮色主题：仅覆盖 Semantic 层 */
[data-theme="light"] {
  --p-bg-0:    #FFFFFF;
  --p-bg-1:    #F8FAFC;
  --p-bg-2:    #F1F5F9;
  --p-bg-card: #FFFFFF;
  --p-bg-c2:   #F8FAFC;
  --p-bg-c3:   #EEF2FF;
  --p-line:    #E2E8F0;
  --p-line2:   #CBD5E1;
  --p-txt:     #0F172A;
  --p-txt2:    #475569;
  --p-txt3:    #94A3B8;
  --p-shadow:  0 1px 2px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.08);
  --p-glow:    0 0 0 1px rgba(59,130,246,.3), 0 4px 20px rgba(59,130,246,.12);
  /* Semantic 层同步更新 */
  --bg-base: #FFFFFF;
  --bg-base2: #F8FAFC;
  --bg-base3: #F1F5F9;
  --bg-surface: #FFFFFF;
  --bg-surface2: #F8FAFC;
  --bg-surface3: #EEF2FF;
  --border: #E2E8F0;
  --border2: #CBD5E1;
  --text: #0F172A;
  --text2: #475569;
  --text3: #94A3B8;
  --accent: #3B82F6;
  --accent2: #2563EB;
  --accent3: #0EA5E9;
  --grad: linear-gradient(135deg,#3B82F6 0%,#2563EB 100%);
  --grad-soft: linear-gradient(135deg,rgba(59,130,246,.1),rgba(37,99,235,.06));
  --shadow: 0 1px 2px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.08);
  --shadow-glow: 0 0 0 1px rgba(59,130,246,.3), 0 4px 20px rgba(59,130,246,.12);
  --term-bg: #F8FAFC;
  --term-txt: #334155;
  --term-ln: #94A3B8;
}
```

### Tier 3 — Component（组件样式）

**永远不直接引用 Primitive**。引用 Semantic，模式如下：

```css
/* ✅ 正确：引用 Semantic */
body { background: var(--bg-base); color: var(--text); }
.card { background: var(--bg-surface); border: 1px solid var(--border); }
input { background: var(--bg-base3); border: 1px solid var(--border2); }
.btn-primary { background: var(--grad); }

/* ❌ 错误：直接引用 Primitive */
body { background: var(--p-bg-0); }  /* 禁止 */
.card { border-color: var(--p-line); } /* 禁止 */
```

### 命名对照表

| 旧名（废弃） | 新 Semantic 名 | 用途 |
|---|---|---|
| `--bg0` | `--bg-base` | 页面底色 |
| `--bg1` | `--bg-base2` | 侧栏/顶栏背景 |
| `--bg2` | `--bg-base3` | 输入框/代码块背景 |
| `--card` | `--bg-surface` | 卡片背景 |
| `--card2` | `--bg-surface2` | 次级卡片/表单背景 |
| `--card3` | `--bg-surface3` | 选中态/标签背景 |
| `--line` | `--border` | 主边框 |
| `--line2` | `--border2` | 次级边框/分割线 |
| `--txt` | `--text` | 主文字 |
| `--txt2` | `--text2` | 次级文字/说明 |
| `--txt3` | `--text3` | 占位/禁用文字 |
| `--blue` | `--accent` | 主按钮/链接色 |
| `--blue2` | `--accent2` | 链接 hover |
| `--cyan` | `--accent3` | 强调色/光标 |

---

## 3. 主题切换机制

### 实现方式

`data-theme` 属性 + CSS 层叠优先级。`<html data-theme="dark|light">` 决定哪套 Primitive 值生效。

```javascript
// JS 切换函数
function setTheme(mode) {
  const html = document.documentElement;
  if (mode === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    html.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    localStorage.removeItem('tb-theme');
  } else {
    html.setAttribute('data-theme', mode);
    localStorage.setItem('tb-theme', mode);
  }
  // 更新按钮激活态
  ['dark', 'light', 'system'].forEach(m => {
    const btn = $(`tbtn-${m}`);
    if (btn) btn.classList.toggle('active', m === mode);
  });
}

// 初始化优先级：localStorage > 系统偏好 > 默认暗色
(function initTheme() {
  const saved = localStorage.getItem('tb-theme');
  if (saved) { setTheme(saved); return; }
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(prefersDark ? 'dark' : 'dark'); // 默认暗色
})();
```

### 切换按钮 UI

位于顶栏右侧，三按钮横排（pill 容器）：

- 🌙 深色主题（`data-theme="dark"`）
- ☀️ 商务白（`data-theme="light"`）
- 💻 跟随系统（`prefers-color-scheme`）

激活态：渐变背景 + 白色文字。

### 持久化

- `localStorage.setItem('tb-theme', mode)` 存储用户选择
- 页面加载时按 `localStorage → 系统偏好 → 默认暗色` 顺序初始化

---

## 4. 亮色主题配色决策

| 场景 | 暗色值 | 亮色值 | 决策理由 |
|---|---|---|---|
| 页面底色 | `#070B14` | `#FFFFFF` | 纯白符合商务文档习惯 |
| 侧栏背景 | `#0B111E` | `#F8FAFC` | 轻灰蓝，避免纯白刺眼 |
| 主边框 | `#1D2A42` | `#E2E8F0` | 亮色用浅灰，符合现代 UI 趋势 |
| 主文字 | `#E6ECF5` | `#0F172A` | 高对比度，确保 WCAG AA |
| 卡片背景 | `#121B2D` | `#FFFFFF` | 纯白卡片，与底色形成层次 |
| Logo 文字 | 渐变色文字 | `#1D4ED8` | 亮色下用实心蓝取代透明渐变 |
| 阴影 | 深色投影 | 轻量浅影 | 亮色不适合厚重阴影 |

---

## 5. 实现版 API 数据来源

原型中所有模拟数据标注实现版来源，切换主题时**不影响数据层**：

| 原型数据 | 实现版来源 | API |
|---|---|---|
| 应用列表 | `thunderbox_query()` | 返回 `id, app_id, name, domain, status` 等 |
| 健康状态 | `thunderbox_query(health:true)` | 返回 `healthy, http_status, response_time_ms` |
| 域名可用性 | `thunderbox_check()` | 返回 `subdomain, domain, available` |
| 回滚历史 | `thunderbox_rollback(history:true)` | 返回 `app_id, history[]` |
| 数据库状态 | `thunderbox_db_list()` | 返回附加的数据库 |

---

## 6. 设计演进记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-08 | 深色科技风原型（单主题） |
| v1.1 | 2026-08 | 增加跳转链接、命令面板、通知中心等交互增强 |
| v1.2 | 2026-08-26 | 三层 Token 重构 + 亮色主题 + 主题切换按钮 |

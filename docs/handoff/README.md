# docs/handoff — 异地测试交接闭环（air-gap）

> 场景：**代码在本机修改，测试在另一环境（网络不通、无法直连）**，只靠 git 双向同步。
> 目的：把「改动意图 / 需要对方做什么 / 要收集哪些反馈 / 数据怎么回传」**全部写进仓库**，让异地的人或 AI 无需沟通即可执行并回传。

---

## 1. 一句话机制

**一张交接单 = 一次交接**，随代码提交；异地 `git pull` → 执行 → 在**同一张单子的「回执」区**填写 + 提交 → 本机 `git pull` 读取。

```
本机：写卡(H-*.md) → commit → push
异地：pull → 按卡执行 → 填回执 + （可选）提交审计产物 → commit → push
本机：pull → 读回执 → 处理 → 写下一张卡（R2…）
```

---

## 2. 目录结构

```
docs/handoff/
├── README.md              本文件（机制说明）
├── _TEMPLATE.md           交接单模板（复制新建 H-*.md）
├── _FEEDBACK_TEMPLATE.md  回执模板（附在交接单尾部「回执」区）
├── H-<date>-<slug>.md     具体交接单（含回执区）
└── artifacts/             异地回传的机读产物（audit JSON 等，随 git 走）
```

---

## 3. 交接单必备三段

| 段 | 作用 | 要点 |
|----|------|------|
| **① 意图与改动** | 让对方知道"我为什么改、改了啥" | 引用 backlog 条目号 + 涉及文件/提交 |
| **② 请执行**（命令） | 可复制的精确命令，避免猜测 | 每个命令附**预期输出**；全为只读/本地，**不含部署** |
| **③ 请回传**（回执） | 结构化字段，便于本机解析 | 每条给**采集方式**（跑哪个脚本/看哪个路径）；大产物落到 `artifacts/` |

> 回执区由异地填写；本机**只读不改**（下一轮另起新卡）。

---

## 4. 数据回传通道（关键）

异地**不要手工整理数据**——跑机读脚本，把输出粘回执 / 存 `artifacts/`：

| 脚本 | 产出 | 用途 |
|------|------|------|
| `modules/case-intelligence/scripts/audit_extraction.py` | JSON + Markdown 指标 | 提取质量体检（空小节率 / court 缺失 / 孤儿 / 命名分布 / 代字清单） |

```bash
# 异地执行（只读，不写业务数据）
cd modules/case-intelligence
python3 scripts/audit_extraction.py --out docs/handoff/artifacts/R<n>-audit.json
```

---

## 5. 红线

- 交接单**不得包含密钥**（token / app_secret / 明文 key）。
- 卡内命令**一律不含部署**（AGENTS §10.2：未经授权不得部署）。
- 回传数据**不得含真实 PII**（姓名/身份证/手机号），必要时脱敏（AGENTS §6.1）。
- 异地填回执后**必须 commit + push**，否则本机读不到。

---

## 6. 相关

- `AGENTS.md §13` — 异地测试交接规则（强制）
- `docs/requirements/backlog.md` — 交接单对应的需求条目
- `modules/case-intelligence/scripts/audit_extraction.py` — 审计脚本
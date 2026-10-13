# H-20261013-extraction · 提取功能缺陷修复 · 首轮验证

| 项 | 值 |
|----|----|
| 轮次 | R1 + R2（续） |
| 日期 | 2026-10-13 |
| 发起 | 本机（修复方） |
| 执行 | 异地（测试方） |
| 关联 backlog | 「case-intelligence 提取功能缺陷修复与验证闭环」 |
| 关联提交 | R1 `7fceaeb` · R2 `ef45de3`（异地复测）→ 本机修复（本卡 R2 段） |

---

## ① 意图与改动（对方只需读）

**背景**：对 `data/` 产物回归发现提取功能是"骨架填充器"，五维度提取**50%+ 小节近乎为空**，
且手工精提炼的提取物孤立在文件层（DB 无），无法支撑下游文书生成。详见 `docs/requirements/backlog.md` 同条目。

**本轮改了什么**（本机，均通过本地单测）：

| 改动 | 文件 | 效果 |
|------|------|------|
| 空壳小节抑制 | `src/markdown_utils.py`（新）+ `src/importer.py` | 入库时删除空小节/空表格（宁缺毋滥） |
| 案号派生法院/年份 | `src/court_resolver.py`（新）+ `src/importer.py` | `cases.court` 从案号代字派生（未知留空）；`year` 回填 |
| 建表/迁移修复 | `src/database.py` | 全新建库即可写全字段；老库幂等补列（修「fresh DB 一建就报错」） |
| 提取字段补全落库 | `src/extractor.py` + `src/importer.py` | court/result/scene/year/授权状态/quality 全链透传 |
| 提示词统一 | `src/extractor.py` | MiniMax/Ollama 共用**全字段** prompt（空壳根因是精简 prompt） |
| 命名唯一真值 | `src/database.py` + `bin/extract.py` | D1-D5↔语义名唯一映射，CLI 支持 `--type D1` |
| 治理字段 | `src/importer.py` | `generation_method`(=llm/rule-based/manual) + `model_version` 落库 + MD 文件双写 |
| 回填脚本 | `scripts/backfill_cases.py`（新） | 存量回填 court/year/scene（dry-run 默认） |
| 空壳回洗脚本 | `scripts/rescrub_artifacts.py`（新） | 存量提取物套用空壳抑制 + 回填 generation_method |
| 归位脚本 | `scripts/relink_artifacts.py`（新） | 报告孤儿 + bigram 匹配分级（exact 自动 / strong·ambiguous 需 --map） |
| 审计脚本 | `scripts/audit_extraction.py`（新） | 机读指标（回传通道） |
| 提取提示词增强 | `prompts/提取/1_新案材料提取_D1-D5.md` | 强制填满叙述型小节 + 表格需有数据行 |
| 自检提示词 | `prompts/提取/4_提取质量自检.md`（新） | 供异地判读回传 |
| 单测 | `tests/test_*.py`（新增 3 个 stdlib 可跑） | schema/迁移/字段透传/命名/提示词/匹配 |

**本机（修复方）本地库已 `--apply` 的结果**：空小节率 **49% → 0%**；court 可派生 0 → 50/104；
`generation_method` 514 条回填为 `ai`；广电案孤儿 5 条已归位（→ 97686b3a）、文件层同步迁移。

---

## ② 请执行（精确命令 · 只读/本地，不含部署）

> 在本机无 pytest 环境下全部以 `python3 <file>` 直接运行（stdlib）。

```bash
cd modules/case-intelligence

# 1) 新单测（预期：database_schema 4 / extraction_prompt 5 / relink_match 5 全 PASS）
python3 tests/test_database_schema.py
python3 tests/test_extraction_prompt.py
python3 tests/test_relink_match.py

# 2) 提取质量审计（预期：输出报告；--out 落 JSON 供回传）
python3 scripts/audit_extraction.py
python3 scripts/audit_extraction.py --out docs/handoff/artifacts/R1-audit.json

# 3) 存量回填 court/year/scene（预期：dry-run 打印待更新行；确认后 --apply）
python3 scripts/backfill_cases.py            # 预览
python3 scripts/backfill_cases.py --apply    # 写库

# 4) 存量空壳回洗（预期：dry-run 打印将变更行；确认后 --apply）
python3 scripts/rescrub_artifacts.py
python3 scripts/rescrub_artifacts.py --apply

# 5) 孤儿提取物归位（预期：列出孤儿 + 匹配候选；exact 自动，strong/ambiguous 需 --map）
python3 scripts/relink_artifacts.py

# 6) 用增强版提取提示词，对 1-2 个真实案件重跑提取（异地环境）
#    参照 prompts/提取/1_新案材料提取_D1-D5.md + 4_提取质量自检.md 判读
```

---

## ③ 请回传（回执，异地填写）

> 填完 **commit + push**。大产物放 `docs/handoff/artifacts/`。

### 回执 · R1

- [ ] 命令 1-5 均可执行（否则注明卡在哪一步 + 报错原文）
- **审计关键数字**（照抄，勿手改）：
  - 空小节率 = ______% （本机修复后 0%）
  - court 可派生案件数 = ______ / 104 （本机 50）
  - 孤儿案件目录 = ______ 个；已在DB = ______ 条
  - generation_method 分布 = ____________
  - 长度分桶 = ____________
- **court 代字全量清单**（`audit_extraction.py` 输出的 unmapped 代字 → 权威法院名）：
  ```
  代字        法院名（请法律同事确认）
  津0101      ?
  川0104      ?
  琼0271      ?
  …（照抄审计输出）
  ```
  > 用途：本机据此扩充 `src/court_resolver.py` 的映射表。
- **孤儿归位意见**（`relink_artifacts.py` 输出）：
  - 广电案孤儿（5 条）：本机已归位到 `97686b3a`（浙江广播电视集团诉雷石、广汽埃安…），异地请确认一致。
  - 腾讯音乐案孤儿（7 条）：匹配到 `9ba215f8`（腾讯音乐…特斯拉案）cov=0.88，但内容多为**通用方法**（源引用多写"从广电案…提炼"），是否应挂该案、或另建"通用方法库"？ ________
- **提取质量判读**（用 `4_提取质量自检.md`）：
  ```
  <粘贴判读表 + 结论>
  ```
- 产物路径：`docs/handoff/artifacts/R1-audit.json`（已提交？✅/❌）
- 观察/异常：__________
- 结论：**通过 / 部分通过 / 阻塞**

<!-- 提示：本卡不含密钥、不含部署；回执勿贴真实姓名/身份证/手机号。 -->

---

# R2 · 异地复测后残留缺陷修复（本机）

> 异地 `ef45de3` 重跑提取（167 案 / 834 artifact / D1–D5 全部有实质内容）后，本机回归发现 3 个残留缺陷并已全部修复。

## ① R2 改了什么

| 缺陷 | 根因 | 修复 |
|------|------|------|
| `quality` 全空（0/167） | LLM 路径（MiniMax/Ollama `_parse_response`）**从不设 quality**，仅规则引擎设 → 经 LLM 提取的案件 quality 恒空 | 抽出 **`derive_quality(ExtractedCase)`** 单一真值（按 D1–D5 实质完整度 A/B/C）；三条路径统一调用；存量回填 **167 行（A:160 / B:6 / C:1）** |
| `court` 可派生仅 64/167 | 代字映射表偏小；且 `extract_court_token` 存在**空格 bug**（`（2025）鲁 0281…` 尾段未 lstrip，误判为省高院，会覆盖正确 LLM 值） | 补 **10 条已核验映射**（沪0112/津0101/川0104/川0193/豫0191/鲁0481/琼0271/粤0115/粤0192/粤0402）；修 `.lstrip()`；court 可派生 **64→106/167** |
| 腾讯案孤儿未归位 + 回填/归位有副作用 | 孤儿目录 1 个未处理；`backfill_cases` 原会**覆盖更优 LLM 值**；`relink` 会**插入重复 (case_id, artifact_type)** | 孤儿 apply 归位（1→0）；`backfill` 改**非破坏式**（only-when-empty + 差异报告）；`relink` 按 type **去重**（补 4 / 跳 3 重复） |

**本机修复后关键指标**：空小节率 **0%**；court 可派生 **106/167**、缺失 43（25%）；quality 缺失 **0/167**；孤儿 **0**；artifacts **838**；`generation_method` 分布 `{ai:514, llm:315, manual:9}`。

## ② R2 请执行（本机已跑，异地复核）

```bash
cd modules/case-intelligence

# 单测（预期全 PASS：database_schema 4 / extraction_prompt 8 / relink_match 5 / court_resolver 5 / markdown_utils 4）
python3 tests/test_database_schema.py
python3 tests/test_extraction_prompt.py
python3 tests/test_relink_match.py
python3 tests/test_court_resolver.py
python3 tests/test_markdown_utils.py

# 三脚本复核（均默认 dry-run；本机已 apply，异地复核应报「无待更新/无孤儿」）
python3 scripts/backfill_cases.py
python3 scripts/relink_artifacts.py
python3 scripts/audit_extraction.py --out docs/handoff/artifacts/R2-audit.json
```

## ③ R2 请回传（异地）

### 回执 · R2

- [ ] 命令均执行通过（否则注明报错原文）
- **审计关键数字**（照抄）：
  - 空小节率 = ______% （本机 0%）
  - court 可派生 = ______ / ______ （本机 106/167，缺失 43）
  - quality 缺失 = ______ / ______ （本机 0/167）
  - 孤儿 = ______ 个（本机 0）
  - generation_method 分布 = ____________ （本机 `{ai:514, llm:315, manual:9}`）
- **剩余未映射代字**（18 token / 32 案 → 请法律同事给权威法院名，本机据此补表）：
  ```
  代字        出现次数    法院名（请确认）
  鲁0281      n=3        ?
  京0307      n=2        ?
  京0419      n=2        ?
  京仲        n=2        ?（疑仲裁机构代字，非法院）
  内0402      n=2        ?
  津0319      n=2        ?
  渝0192      n=2        ?
  粤0106      n=2        ?
  粤0111      n=2        ?
  粤1403      n=2        ?
  鲁0891      n=2        ?
  鲁1311      n=2        ?
  鲁1691      n=2        ?
  京0103      n=1        ?
  粤0306      n=1        ?
  粤0307      n=1        ?
  鲁0202      n=1        ?
  黔2701      n=1        ?
  ```
- **4 处派生差异裁决**（本机**未覆盖**，保留原 LLM 值，请确认以哪方为准）：
  ```
  case_id    字段   现有值(LLM)    案号派生值
  2bb378ad   year   2024           2023
  31e22b08   year   2024           2023
  eb89a9e7   year   2024           2025
  b68f67a6   court  北京互联网法院（一审），北京知识产权法院（二审）  北京互联网法院
  ```
  > 本机判断：`b68f67a6` 的 LLM 值（含二审）信息量更大，宜保留；3 个 year 差异疑为案号受理年 vs 审理年，请裁决。
- **孤儿归位确认**：
  - 腾讯案 7 条孤儿已重挂 `9ba215f8`（去重跳过 3 条重复 type）；广电案 5 条已于 R1 归位 `97686b3a`。异地请确认 `relink_artifacts.py` 报「孤儿=0」且两条链路可检索到。
  - 遗留：`9ba215f8` 磁盘目录仍有 3 个**重复 type** 的 MD 文件（未删，非破坏保留），是否清理？________
- 产物路径：`docs/handoff/artifacts/R2-audit.json`（已提交？✅/❌）
- 结论：**通过 / 部分通过 / 阻塞**

<!-- 提示：本卡不含密钥、不含部署；回执勿贴真实姓名/身份证/手机号。 -->
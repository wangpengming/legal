# H-20261013-extraction · 提取功能缺陷修复 · 首轮验证

| 项 | 值 |
|----|----|
| 轮次 | R1 |
| 日期 | 2026-10-13 |
| 发起 | 本机（修复方） |
| 执行 | 异地（测试方） |
| 关联 backlog | 「case-intelligence 提取功能缺陷修复与验证闭环」 |
| 关联提交 | `<fill-after-commit>` |

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
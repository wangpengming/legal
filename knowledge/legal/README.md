# 本地法律知识库（knowledge/legal/）

Bot 需要**具体法条**时优先查这里（**离线、不外传**，守工程「本地优先」红线）；未命中才回落联网检索。

## 语料格式

每个主题一个 Markdown 文件（**文件名用英文 / 拼音**，§5 命名规范），内容：

```markdown
---
topic: 著作权法
---
### 著作权法 第10条
著作权包括下列人身权和财产权：（一）发表权……（原文照录）

### 著作权法 第24条
在下列情况下使用作品，可以不经著作权人许可……（合理使用）
```

- `### ` 三级标题 = 一条（`Article`）；标题里的「第N条」用于条号检索。
- 正文为条文 / 裁判要点原文（可截断，单条上限 `legal_kb.MAX_TEXT` 字）。
- 不带 `###` 的文件整体视为一条（标题 = 文件名 / `topic`）。

## 导入方式

🔴 **不臆造法条原文**：语料必须来自**用户提供 / 确认**的文本，用脚本导入：

```bash
cd modules/case-intelligence
python scripts/import_law_text.py --in /path/to/著作权法.txt --topic 著作权法            # 预览
python scripts/import_law_text.py --in /path/to/著作权法.txt --topic 著作权法 --write   # 写入
```

脚本按「第N条」切条；同条号**幂等覆盖**（重复导入不会产生重复条目）。

## 检索

```python
from src import legal_kb
legal_kb.search("著作权法第24条 合理使用")   # → [Article, ...]
legal_kb.lookup("信息网络传播权 合理使用")   # → {"hits": [...], "source": "local"}
```

环境变量：`LEGAL_KB_DIR` 可指向其它目录（默认本目录）。

## 现状

当前**仅机制就绪、语料待导入**：库为空时 Bot 如实回「本地法规库与联网检索都未命中」，
绝不编造条号或条文。
# Qoder 原始对话记录

来源：`~/.qoder/` 目录

## 文件说明

| 文件 | 大小 | 说明 |
|------|------|------|
| task-018.jsonl | 101K | task-018 conversation history（JSONL格式） |
| task-018644d51c9843769588.session.execution.jsonl | 550K | task-018 transcript（完整执行记录，含源码Write内容） |
| task-eff.jsonl | 63K | task-eff conversation history |
| task-eff1d823916f4b939ac6.session.execution.jsonl | 46K | task-eff transcript |
| agent-tools/ | 1MB | 浏览器快照记录（8个txt文件） |
| memories/ | - | Qoder项目记忆文件 |

## 提取工具

```bash
# 提取所有源码文件
python3 -c "
import json
with open('task-018644d51c9843769588.session.execution.jsonl') as f:
    for line in f:
        obj = json.loads(line)
        content = obj.get('message',{}).get('content',[])
        for c in content:
            if isinstance(c,dict) and 'file_content' in c.get('input',{}):
                fp = c['input']['file_path']
                fc = c['input']['file_content']
                if len(fc) > 500 and any(ext in fp for ext in ['.py','.sh','.md']):
                    fname = fp.split('/')[-1]
                    with open(f'extracted/{fname}','w') as out:
                        out.write(fc)
"
```

## 源码恢复情况

已恢复：app.py, config.py, database.py, generator.py, docx_to_pdf.py, pdf_merger.py, feishu_api.py, PROMPTS.md

未找到（用bash命令创建，未进transcript）：bin/manage.sh等脚本, templates/Word模板, static/PDF.js

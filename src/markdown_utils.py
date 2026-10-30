# =============================================
# markdown_utils.py - Markdown 处理纯函数（无 IO / 无第三方依赖）
# =============================================
import re

_SEC_HDR = re.compile(r"^##\s")


def has_substance(body_lines) -> bool:
    """小节是否有实质内容：有非表格文本，或表格有数据行（表头+≥1 数据行）。"""
    pipe_rows = 0
    for ln in body_lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("|"):
            if set(s) <= set("|-: "):   # 分隔行 |---|---|
                continue
            pipe_rows += 1
        else:
            return True                 # 有普通文本
    return pipe_rows > 1                # 仅表头（1 行）视为空


def strip_empty_sections(markdown: str) -> str:
    """去掉正文为空的小节（含空标题），避免"空壳提纲"。

    背景：批量 AI 提取常对叙述性小节（权利基础分析/抗辩论证结构/质证要点…）
    返回空串。宁缺毋滥：无实质内容的小节整节删除（仅表头无数据行的空表格亦视为空）。
    """
    out = []
    lines = (markdown or "").split("\n")
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if _SEC_HDR.match(line):
            j = i + 1
            body = []
            while j < n and not _SEC_HDR.match(lines[j]):
                body.append(lines[j])
                j += 1
            if has_substance(body):
                out.append(line)
                out.extend(body)
            i = j
        else:
            out.append(line)
            i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
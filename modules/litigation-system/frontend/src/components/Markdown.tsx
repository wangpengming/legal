/* 轻量 Markdown 渲染（零依赖）：标题/表格/列表/引用/代码块/粗体/行内码/链接。
   供 AI 对话（/ai）与报告预览（/reports，Mode B 产出）复用；13px 表格排版环境。
   行内内容一律转义后经 React 片段渲染，不注入 HTML。 */
import { Fragment, type ReactNode } from "react";

const H = { fontSize: "inherit" } as const;
const CODE_STYLE = {
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: 5,
  padding: "1px 5px",
  fontSize: 12,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
} as const;

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* 行内语法 → ReactNode[]：`code` / **bold** / [text](url)，其余转义为文本 */
function inline(src: string, keyBase = 0): ReactNode[] {
  const out: ReactNode[] = [];
  let k = keyBase;
  src.split(/(`[^`]+`)/g).forEach((p) => {
    if (!p) return;
    if (p.length > 1 && p.startsWith("`") && p.endsWith("`")) {
      out.push(<code key={k++} style={CODE_STYLE}>{esc(p.slice(1, -1))}</code>);
      return;
    }
    p.split(/(\*\*[^*]+\*\*)/g).forEach((s2) => {
      if (!s2) return;
      if (s2.startsWith("**") && s2.length > 4) {
        out.push(<strong key={k++}>{s2.slice(2, -2)}</strong>);
      } else {
        const m = s2.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
        if (m) {
          out.push(
            <a key={k++} href={m[2]} target="_blank" rel="noreferrer" style={{ color: "var(--primary)" }}>
              {m[1]}
            </a>,
          );
        } else {
          out.push(<Fragment key={k++}>{esc(s2)}</Fragment>);
        }
      }
    });
  });
  return out;
}

type Block =
  | { type: "p"; text: string }
  | { type: "h"; level: number; text: string }
  | { type: "ul"; items: string[] }
  | { type: "quote"; lines: string[] }
  | { type: "code"; lines: string[] }
  | { type: "table"; head: string[]; rows: string[][] };

/* 行序列 → 块序列（合并连续表格行 / 引用行 / 代码行） */
function toBlocks(lines: string[]): Block[] {
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // 代码块 ``` 定界
    if (/^```/.test(line.trim())) {
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        buf.push(lines[i]);
        i += 1;
      }
      i += 1; // 跳过结束定界
      blocks.push({ type: "code", lines: buf });
      continue;
    }
    if (line.trim() === "") {
      i += 1;
      continue;
    }
    if (/^\|.*\|$/.test(line.trim())) {
      const rows: string[][] = [];
      while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
        rows.push(
          lines[i]
            .trim()
            .replace(/^\||\|$/g, "")
            .split("|")
            .map((c) => c.trim()),
        );
        i += 1;
      }
      const body = rows.filter((r, idx) => !(idx === 1 && r.every((c) => /^[-:]+$/.test(c))));
      if (body.length > 0) {
        blocks.push({ type: "table", head: body[0], rows: body.slice(1) });
      }
      continue;
    }
    if (/^#{1,4}\s/.test(line)) {
      const level = line.match(/^#+/)?.[0].length ?? 3;
      blocks.push({ type: "h", level, text: line.replace(/^#+\s*/, "") });
      i += 1;
      continue;
    }
    if (/^>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push({ type: "quote", lines: buf });
      continue;
    }
    if (/^[-*]\s/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        buf.push(lines[i].replace(/^[-*]\s/, ""));
        i += 1;
      }
      blocks.push({ type: "ul", items: buf });
      continue;
    }
    blocks.push({ type: "p", text: line });
    i += 1;
  }
  return blocks;
}

const CELL = {
  padding: "6px 10px",
  borderBottom: "1px solid var(--border)",
  fontSize: 12.5,
  textAlign: "left" as const,
  verticalAlign: "top",
} as const;

export function Markdown({ text }: { text: string }) {
  const blocks = toBlocks(text.split("\n").map((l) => l.replace(/\r$/, "")));
  return (
    <div style={{ display: "grid", gap: 10, fontSize: 13.5, lineHeight: 1.65 }}>
      {blocks.map((b, bi) => {
        switch (b.type) {
          case "h":
            return (
              <div key={bi} style={{ ...H, fontWeight: 700, fontSize: b.level <= 2 ? 15 : 14, marginTop: b.level <= 2 ? 6 : 0 }}>
                {inline(b.text, bi * 10)}
              </div>
            );
          case "p":
            return <p key={bi} style={{ margin: 0 }}>{inline(b.text, bi * 10)}</p>;
          case "ul":
            return (
              <ul key={bi} style={{ margin: 0, paddingLeft: 20 }}>
                {b.items.map((it, j) => (
                  <li key={j} style={{ margin: "3px 0" }}>{inline(it, bi * 100 + j)}</li>
                ))}
              </ul>
            );
          case "quote":
            return (
              <blockquote
                key={bi}
                style={{
                  margin: 0,
                  padding: "8px 12px",
                  borderLeft: "3px solid var(--primary)",
                  background: "var(--surface-2)",
                  borderRadius: 6,
                  fontSize: 12.5,
                  color: "var(--muted)",
                  display: "grid",
                  gap: 4,
                }}
              >
                {b.lines.map((l, j) => (
                  <div key={j}>{inline(l, bi * 100 + j)}</div>
                ))}
              </blockquote>
            );
          case "code":
            return (
              <pre
                key={bi}
                style={{
                  margin: 0,
                  padding: "10px 12px",
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  overflow: "auto",
                  fontSize: 12,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  color: "var(--text)",
                }}
              >
                {b.lines.join("\n")}
              </pre>
            );
          case "table":
            return (
              <div key={bi} style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid var(--border)", borderRadius: 8 }}>
                  <thead>
                    <tr>
                      {b.head.map((c, j) => (
                        <th key={j} style={{ ...CELL, background: "var(--surface-2)", fontWeight: 600, whiteSpace: "nowrap" }}>
                          {inline(c, bi * 1000 + j)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, j) => (
                      <tr key={j}>
                        {r.map((c, k) => (
                          <td key={k} style={CELL}>{inline(c, bi * 10000 + j * 100 + k)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}
import type { QueryResult } from "./api";

function toBusinessTitle(question: string): string {
  let q = question.trim().replace(/[?!.]+$/, "");

  // Transform common question patterns into statement form
  q = q
    .replace(/^what (?:is|are|was|were) (?:the )?/i, "")
    .replace(/^who (?:is|are|was|were) (?:the )?/i, "")
    .replace(/^which (.+?) (?:has|have|had) (?:the )?(?:most|highest|best|largest|biggest) (.+)/i, "Top $1 by $2")
    .replace(/^which (.+?) (?:has|have|had) (?:the )?(?:lowest|worst|fewest|least) (.+)/i, "Bottom $1 by $2")
    .replace(/^which (.+?) (?:has|have|had) (?:the )?(.+)/i, "$1 — $2")
    .replace(/^which /i, "")
    .replace(/^how (?:is|are|was|were) (.+) (?:trending|performing|doing)/i, "$1 Trend")
    .replace(/^how (?:is|are|was|were) (.+)/i, "$1")
    .replace(/^how many (.+?) are there/i, "Number of $1")
    .replace(/^how many /i, "Number of ")
    .replace(/^how much /i, "Total ")
    .replace(/^(?:show|list|find|get|display)(?:\s+me)?(?:\s+all)?(?:\s+the)? /i, "");

  // Strip leading articles left over
  q = q.replace(/^(?:the |a |an )/i, "");

  // Title case — keep small words lowercase unless first word
  const small = new Set(["a","an","and","as","at","but","by","for","in","nor","of","on","or","the","to","up","vs","with","from","into","over","than"]);
  return q
    .split(" ")
    .map((word, i) => {
      const lower = word.toLowerCase();
      if (i === 0 || !small.has(lower)) return word.charAt(0).toUpperCase() + word.slice(1);
      return lower;
    })
    .join(" ");
}

function fmtCol(col: string): string {
  return col.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toLocaleString();
  return String(v);
}

export function generateDocHTML(question: string, result: QueryResult): string {
  const date = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });
  const tableHead = result.columns.map((c) => `<th>${fmtCol(c)}</th>`).join("");
  const tableBody = result.rows
    .map((row) => `<tr>${row.map((v) => `<td>${fmtVal(v)}</td>`).join("")}</tr>`)
    .join("");
  const narrative = result.narrative
    ? `<div class="insight">
        <div class="insight-bar"></div>
        <div class="insight-body">
          <p class="insight-label">Key Insight</p>
          <p class="insight-text">${result.narrative}</p>
        </div>
      </div>`
    : "";

  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,Helvetica,Arial,sans-serif;color:#1a1a2e}
  .header{background:#0b4f8a;color:#fff;padding:24px 32px 20px}
  .header-top{display:flex;justify-content:space-between;align-items:flex-start}
  .logo{font-size:22px;font-weight:700}.sub{font-size:11px;color:#99bbdd;margin-top:2px}
  .date{font-size:11px;color:#99bbdd}.teal-bar{height:3px;background:#00bcd4}
  .body{padding:32px}
  .section-label{font-size:11px;font-weight:700;color:#0b4f8a;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em}
  .question{font-size:15px;color:#333;margin-bottom:24px;line-height:1.5}
  .insight{display:flex;background:#eff6ff;border-radius:6px;margin-bottom:24px;overflow:hidden}
  .insight-bar{width:4px;background:#00bcd4;flex-shrink:0}
  .insight-body{padding:14px 16px}
  .insight-label{font-size:11px;font-weight:700;color:#0b4f8a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
  .insight-text{font-size:13px;color:#333;line-height:1.6}
  .stats{display:flex;gap:12px;margin-bottom:28px}
  .stat{flex:1;background:#0b4f8a;border-radius:6px;padding:12px;text-align:center}
  .stat-value{font-size:18px;font-weight:700;color:#fff}
  .stat-label{font-size:10px;color:#99bbdd;margin-top:3px}
  table{width:100%;border-collapse:collapse;font-size:11px}
  th{background:#0b4f8a;color:#fff;padding:8px 10px;text-align:left;font-weight:600}
  td{padding:7px 10px;border-bottom:1px solid #e5e7eb}
  tr:nth-child(even) td{background:#f0f7ff}
  .footer{margin-top:32px;padding-top:12px;border-top:1px solid #e5e7eb;display:flex;justify-content:space-between}
  .footer-text{font-size:10px;color:#aaa}
  @media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  </style></head><body>
  <div class="header"><div class="header-top">
    <div><div class="logo">AskData</div><div class="sub">Analytics Report</div></div>
    <div class="date">${date}</div>
  </div></div>
  <div class="teal-bar"></div>
  <div class="body">
    <div class="section-label">Question</div>
    <div class="question">${question}</div>
    ${narrative}
    <div class="stats">
      <div class="stat"><div class="stat-value">${result.row_count}</div><div class="stat-label">Records</div></div>
      <div class="stat"><div class="stat-value">${result.columns.length}</div><div class="stat-label">Fields</div></div>
      <div class="stat"><div class="stat-value">${result.execution_ms}ms</div><div class="stat-label">Query Time</div></div>
    </div>
    <div class="section-label" style="margin-bottom:10px">Data</div>
    <table><thead><tr>${tableHead}</tr></thead><tbody>${tableBody}</tbody></table>
    <div class="footer">
      <span class="footer-text">Generated by AskData</span>
      <span class="footer-text">${date}</span>
    </div>
  </div>
  </body></html>`;
}

export function generateSlidesHTML(question: string, result: QueryResult): string {
  const date = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });
  const topRows = result.rows.slice(0, 4);
  const hasHighlights = topRows.length > 0 && result.columns.length >= 2;
  const highlightCards = hasHighlights
    ? topRows.map((row, i) => {
        const val = fmtVal(row[1] ?? row[0]);
        const lbl = String(row[0] ?? "");
        const bg = i === 0 ? "#0b4f8a" : "#f0f5fa";
        const color = i === 0 ? "#fff" : "#0b4f8a";
        const lblColor = i === 0 ? "#99bbdd" : "#666";
        return `<div class="card" style="background:${bg};color:${color}">
          <div class="card-val">${val.length > 16 ? val.slice(0, 16) + "…" : val}</div>
          <div class="card-lbl" style="color:${lblColor}">${lbl.length > 22 ? lbl.slice(0, 22) + "…" : lbl}</div>
        </div>`;
      }).join("")
    : "";
  const tableHead = result.columns.map((c) => `<th>${fmtCol(c)}</th>`).join("");
  const tableBody = result.rows.slice(0, 20)
    .map((row) => `<tr>${row.map((v) => `<td>${fmtVal(v)}</td>`).join("")}</tr>`)
    .join("");
  const narrative = result.narrative ?? "";

  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,Helvetica,Arial,sans-serif}
  .slide{width:100%;aspect-ratio:16/9;padding:36px 48px;position:relative;overflow:hidden;page-break-after:always;break-after:page}
  .slide-1{background:#0b4f8a;color:#fff;display:flex;flex-direction:column}
  .brand{font-size:12px;font-weight:700;color:#00bcd4;letter-spacing:.06em;margin-bottom:18px}
  .title{font-size:28px;font-weight:700;line-height:1.3;max-width:80%;flex:1}
  .divider{height:2px;background:#00bcd4;width:100%;margin:18px 0 12px}
  .date-line{font-size:11px;color:#99bbdd;margin-bottom:16px}
  .stats-row{display:flex;gap:12px}
  .stat-box{background:#0d5faf;border-radius:6px;padding:12px 18px;text-align:center;min-width:110px}
  .stat-box .v{font-size:22px;font-weight:700;color:#fff}
  .stat-box .l{font-size:9px;color:#99bbdd;margin-top:3px}
  .slide-2,.slide-3{background:#fff;display:flex;flex-direction:column}
  .teal-top{position:absolute;top:0;left:0;right:0;height:4px;background:#00bcd4}
  .teal-side{position:absolute;left:36px;top:48px;width:4px;height:44px;background:#00bcd4;border-radius:2px}
  .slide-heading{font-size:20px;font-weight:700;color:#0b4f8a;margin-bottom:14px;padding-left:18px}
  .narr-box{background:#eff6ff;border-radius:6px;padding:16px 18px;margin-bottom:16px;font-size:13px;color:#1a1a2e;line-height:1.6}
  .highlights-label{font-size:9px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
  .cards{display:flex;gap:10px;flex:1}
  .card{flex:1;border-radius:6px;padding:14px;display:flex;flex-direction:column;align-items:center;justify-content:center}
  .card-val{font-size:20px;font-weight:700}
  .card-lbl{font-size:9px;margin-top:5px}
  .meta{font-size:10px;color:#888;margin-bottom:12px;padding-left:18px}
  table{width:100%;border-collapse:collapse;font-size:9px}
  th{background:#0b4f8a;color:#fff;padding:6px 8px;text-align:left;font-weight:600}
  td{padding:4px 8px;border-bottom:1px solid #e5e7eb}
  tr:nth-child(even) td{background:#f0f5fa}
  .slide-footer{position:absolute;bottom:10px;right:48px;font-size:8px;color:#bbb}
  @media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  @media screen{body{background:#e5e7eb;padding:20px}.slide{border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,.15);margin-bottom:20px}}
  </style></head><body>
  <div class="slide slide-1">
    <div class="brand">ASKDATA ANALYTICS</div>
    <div class="title">${toBusinessTitle(question)}</div>
    <div class="divider"></div>
    <div class="date-line">${date}</div>
    <div class="stats-row">
      <div class="stat-box"><div class="v">${result.row_count}</div><div class="l">Records Analyzed</div></div>
      <div class="stat-box"><div class="v">${result.columns.length}</div><div class="l">Data Fields</div></div>
      <div class="stat-box"><div class="v">${result.execution_ms}ms</div><div class="l">Query Time</div></div>
    </div>
    <div class="slide-footer">AskData Analytics</div>
  </div>
  ${narrative ? `<div class="slide slide-2">
    <div class="teal-top"></div><div class="teal-side"></div>
    <div class="slide-heading">Key Insight</div>
    <div class="narr-box">${narrative}</div>
    ${hasHighlights ? `<div class="highlights-label">Highlights</div><div class="cards">${highlightCards}</div>` : ""}
    <div class="slide-footer">AskData Analytics</div>
  </div>` : ""}
  <div class="slide slide-3">
    <div class="teal-top"></div><div class="teal-side"></div>
    <div class="slide-heading">Data Results</div>
    <div class="meta">${result.row_count} records · ${result.execution_ms}ms</div>
    <table><thead><tr>${tableHead}</tr></thead><tbody>${tableBody}</tbody></table>
    ${result.rows.length > 20 ? `<div style="font-size:9px;color:#aaa;margin-top:6px">+ ${result.rows.length - 20} more rows not shown</div>` : ""}
    <div class="slide-footer">AskData Analytics</div>
  </div>
  </body></html>`;
}

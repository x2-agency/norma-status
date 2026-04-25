#!/usr/bin/env python3
"""Generate README.md and index.html from x2-agency GitHub Projects."""
import html
import json
import subprocess
from datetime import datetime, timezone
from collections import defaultdict

OWNER = "x2-agency"
PROJECTS = [
    (9, "Mobile App"),
    (7, "Frontend"),
    (4, "Backend"),
]
DONE_STATUS = "Готово"
TESTING_STATUSES = {"Передано в тестирование", "Тестирование", "Готово к работе"}
STATUS_ORDER_WORK = [
    "В работе", "В разработке", "В процессе",
    "На ревью", "Есть вопросы", "Есть блокеры", "Бэклог",
]
STATUS_ORDER_TEST = [
    "Готово к работе", "Передано в тестирование", "Тестирование",
]


GRAPHQL_QUERY = """
query($org: String!, $num: Int!, $cursor: String) {
  organization(login: $org) {
    projectV2(number: $num) {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          updatedAt
          fieldValues(first: 30) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
          content {
            __typename
            ... on Issue       { title url createdAt }
            ... on PullRequest { title url createdAt }
            ... on DraftIssue  { title createdAt }
          }
        }
      }
    }
  }
}
"""


def fetch(project_number: int) -> list[dict]:
    items: list[dict] = []
    cursor = ""
    while True:
        args = ["gh", "api", "graphql", "-f", f"query={GRAPHQL_QUERY}",
                "-F", f"org={OWNER}", "-F", f"num={project_number}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        proc = subprocess.run(args, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)["data"]["organization"]["projectV2"]["items"]
        items.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return items


def extract_status(node: dict) -> str:
    for fv in node.get("fieldValues", {}).get("nodes", []):
        if fv.get("__typename") == "ProjectV2ItemFieldSingleSelectValue" \
                and (fv.get("field") or {}).get("name") == "Status":
            return fv.get("name") or "Без статуса"
    return "Без статуса"


def collect():
    """Returns (done, work_by_status, testing_by_status)."""
    done = []
    work = defaultdict(list)
    testing = defaultdict(list)
    for number, label in PROJECTS:
        for node in fetch(number):
            content = node.get("content") or {}
            entry = {
                "title": (content.get("title") or "(без названия)").strip(),
                "url": content.get("url"),
                "created": content.get("createdAt"),
                "updated": node.get("updatedAt") or content.get("createdAt"),
                "project": label,
            }
            status = extract_status(node).strip()
            if status == DONE_STATUS:
                done.append(entry)
            elif status in TESTING_STATUSES:
                testing[status].append(entry)
            else:
                work[status].append(entry)
    return done, work, testing


def ordered_statuses(buckets: dict, order: list[str]) -> list[str]:
    seen = set()
    result = []
    for s in order:
        if s in buckets:
            result.append(s); seen.add(s)
    for s in sorted(buckets):
        if s not in seen:
            result.append(s)
    return result


def render_md(done, work, testing, now: str) -> str:
    parts = ["# Norma — статус задач", "", f"_Обновлено: {now}_", ""]
    parts.append(
        f"Источники: "
        f"[Mobile App](https://github.com/orgs/{OWNER}/projects/9) · "
        f"[Frontend](https://github.com/orgs/{OWNER}/projects/7) · "
        f"[Backend](https://github.com/orgs/{OWNER}/projects/4)"
    )
    parts.append("")
    parts.append(f"**Публичная страница:** https://{OWNER}.github.io/norma-status/")
    parts.append("")

    def line(e: dict) -> str:
        title = e["title"].replace("|", "\\|")
        link = f"[{title}]({e['url']})" if e["url"] else title
        date = e["updated"][:10] if e.get("updated") else "—"
        return f"- `{date}` {link} · _{e['project']}_"

    def group(emoji: str, name: str, buckets: dict, order: list[str], is_open: bool) -> None:
        total = sum(len(v) for v in buckets.values())
        opener = "<details open>" if is_open else "<details>"
        parts.append(f"{opener}<summary><b>{emoji} {name} — {total}</b></summary>")
        parts.append("")
        for status in ordered_statuses(buckets, order):
            items = buckets[status]
            parts.append(f"#### {status} ({len(items)})")
            parts.append("")
            parts.extend(line(e) for e in sorted(items, key=lambda x: (x.get("updated") or ""), reverse=True))
            parts.append("")
        parts.append("</details>")
        parts.append("")

    group("🚧", "В работе", work, STATUS_ORDER_WORK, is_open=False)
    group("🧪", "На тестировании", testing, STATUS_ORDER_TEST, is_open=False)

    parts.append(f"<details open><summary><b>✅ Готово — {len(done)}</b></summary>")
    parts.append("")
    parts.extend(line(e) for e in sorted(done, key=lambda x: (x.get("updated") or ""), reverse=True))
    parts.append("")
    parts.append("</details>")
    parts.append("")
    return "\n".join(parts)


def render_html(done, work, testing, now_iso: str) -> str:
    def esc(s: str) -> str:
        return html.escape(s, quote=True)

    proj_class = {"Mobile App": "p-mobile", "Frontend": "p-frontend", "Backend": "p-backend"}

    def li(e: dict) -> str:
        title = esc(e["title"])
        proj = esc(e["project"])
        pcls = proj_class.get(e["project"], "")
        if e["url"]:
            link = f'<a href="{esc(e["url"])}" target="_blank" rel="noopener">{title}</a>'
        else:
            link = f'<span>{title}</span>'
        updated = e.get("updated") or ""
        date = esc(updated[:10]) if updated else "—"
        return (
            f'<li class="task-item" data-updated="{esc(updated)}">'
            f'<span class="bullet"></span>'
            f'<div class="task">'
            f'  <div class="task-title">{link}</div>'
            f'  <div class="task-meta">'
            f'    <span class="date" title="Дата последнего обновления">{date}</span>'
            f'    <span class="tag {pcls}">{proj}</span>'
            f'  </div>'
            f'</div>'
            f'</li>'
        )

    def status_block(status: str, items: list[dict], color_class: str) -> str:
        items_sorted = sorted(items, key=lambda x: (x.get("updated") or ""), reverse=True)
        return (
            f'<section class="status {color_class}">'
            f'<div class="status-head">'
            f'  <h3>{esc(status)}</h3>'
            f'  <span class="status-count">{len(items)}</span>'
            f'</div>'
            f'<ul class="tasks">{"".join(li(e) for e in items_sorted)}</ul>'
            f'</section>'
        )

    status_color = {
        "В работе": "s-active", "В разработке": "s-active", "В процессе": "s-active",
        "На ревью": "s-review", "Передано в тестирование": "s-review", "Тестирование": "s-review",
        "Готово к работе": "s-ready", "Бэклог": "s-backlog",
        "Есть вопросы": "s-blocked", "Есть блокеры": "s-blocked",
    }

    def build_group(buckets: dict, order: list[str]) -> tuple[str, int]:
        blocks = []
        for status in ordered_statuses(buckets, order):
            blocks.append(
                status_block(status, buckets[status], status_color.get(status, "s-default"))
            )
        return "".join(blocks), sum(len(v) for v in buckets.values())

    work_blocks, total_work = build_group(work, STATUS_ORDER_WORK)
    testing_blocks, total_testing = build_group(testing, STATUS_ORDER_TEST)
    done_block = status_block("Готово", done, "s-done")

    actions_url = f"https://github.com/{OWNER}/norma-status/actions/workflows/update.yml"

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Norma — статус задач</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #fafbfc;
    --bg-grad: linear-gradient(180deg, #fafbfc 0%, #f3f5f9 100%);
    --card: #ffffff;
    --card-2: #f7f8fb;
    --border: #e6e8ef;
    --border-strong: #d0d4dd;
    --fg: #131720;
    --fg-2: #3a4151;
    --muted: #6c7388;
    --muted-2: #9aa1b3;
    --accent: #5b6cff;
    --accent-soft: #eef0ff;
    --done: #16a067;
    --done-soft: #e3f6ec;
    --review: #d97706;
    --review-soft: #fdf3e2;
    --yellow: #ca8a04;
    --yellow-soft: #fef9c3;
    --orange: #ea580c;
    --orange-soft: #ffedd5;
    --green: #16a067;
    --green-soft: #d8f5e6;
    --active: #5b6cff;
    --active-soft: #eef0ff;
    --ready: #0891b2;
    --ready-soft: #e1f5fa;
    --backlog: #6c7388;
    --backlog-soft: #eef0f4;
    --blocked: #dc2626;
    --blocked-soft: #fde7e7;
    --shadow: 0 1px 2px rgba(15,20,30,0.04), 0 4px 16px rgba(15,20,30,0.04);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px; line-height: 1.5; -webkit-font-smoothing: antialiased; }}
  body {{ background: var(--bg-grad); min-height: 100vh; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 40px 24px 80px; }}

  /* Header card */
  .header {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px;
    padding: 28px 28px; box-shadow: var(--shadow); margin-bottom: 24px; }}
  .header h1 {{ font-size: 26px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.02em; color: var(--fg); }}
  .header .subtitle {{ color: var(--muted); font-size: 14px; margin-bottom: 20px; }}
  .header-row {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    padding-top: 18px; border-top: 1px solid var(--border); }}
  .updated {{ display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 13px; }}
  .updated .dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--done); display: inline-block; }}
  .updated time {{ font-family: 'JetBrains Mono', ui-monospace, monospace; color: var(--fg-2); font-size: 12.5px; }}
  .updated .rel {{ color: var(--muted-2); }}
  .actions {{ margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }}
  .btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px;
    background: var(--accent); color: #fff !important; border: none; border-radius: 8px;
    font-size: 13.5px; font-weight: 500; text-decoration: none; cursor: pointer;
    transition: filter .15s, transform .05s; font-family: inherit; }}
  .btn:hover {{ filter: brightness(1.08); }}
  .btn:active {{ transform: translateY(1px); }}
  .btn.secondary {{ background: var(--card-2); color: var(--fg-2) !important;
    border: 1px solid var(--border-strong); }}
  .btn svg {{ width: 14px; height: 14px; }}
  .sources {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 14px; }}
  .sources a {{ color: var(--muted); text-decoration: none; font-size: 12.5px;
    padding: 4px 10px; border-radius: 6px; background: var(--card-2);
    border: 1px solid var(--border); transition: all .15s; }}
  .sources a:hover {{ color: var(--accent); border-color: var(--accent); }}

  /* Group cards */
  .group {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px;
    margin-bottom: 20px; box-shadow: var(--shadow); overflow: hidden; }}
  .group > summary {{ list-style: none; cursor: pointer; padding: 22px 28px;
    display: flex; align-items: center; gap: 14px; user-select: none; }}
  .group > summary::-webkit-details-marker {{ display: none; }}
  .chevron {{ width: 18px; height: 18px; color: var(--muted); transition: transform .2s; flex-shrink: 0; }}
  .group[open] .chevron {{ transform: rotate(90deg); }}
  .group-title {{ font-size: 19px; font-weight: 600; letter-spacing: -0.01em; }}
  .group-count {{ margin-left: auto; padding: 4px 12px; border-radius: 999px;
    font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .group.in-progress .group-count {{ background: var(--yellow-soft); color: var(--yellow); }}
  .group.testing .group-count {{ background: var(--orange-soft); color: var(--orange); }}
  .group.done .group-count {{ background: var(--green-soft); color: var(--green); }}
  .group-body {{ border-top: 1px solid var(--border); padding: 8px 0 16px; }}

  /* Status block */
  .status {{ padding: 16px 28px 8px; }}
  .status-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
    padding-bottom: 8px; border-bottom: 1px dashed var(--border); }}
  .status-head h3 {{ margin: 0; font-size: 13px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.08em; color: var(--fg-2);
    padding-left: 10px; border-left: 3px solid var(--muted-2); }}
  .group.in-progress .status-head h3 {{ border-left-color: var(--yellow); color: var(--yellow); }}
  .group.testing .status-head h3 {{ border-left-color: var(--orange); color: var(--orange); }}
  .group.done .status-head h3 {{ border-left-color: var(--green); color: var(--green); }}
  .status-count {{ color: var(--muted); font-size: 12.5px;
    font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }}

  /* Tasks list */
  .tasks {{ list-style: none; padding: 0; margin: 0; }}
  .tasks li {{ display: flex; align-items: flex-start; gap: 12px; padding: 9px 0; }}
  .bullet {{ width: 6px; height: 6px; border-radius: 50%; background: var(--muted-2);
    margin-top: 9px; flex-shrink: 0; }}
  .group.in-progress .bullet {{ background: var(--yellow); }}
  .group.testing .bullet {{ background: var(--orange); }}
  .group.done .bullet {{ background: var(--green); }}
  .task {{ flex: 1; min-width: 0; }}
  .task-title {{ font-size: 14.5px; line-height: 1.45; color: var(--fg); }}
  .task-title a {{ color: var(--fg); text-decoration: none; }}
  .task-title a:hover {{ color: var(--accent); text-decoration: underline; }}
  .task-meta {{ display: flex; gap: 10px; align-items: center; margin-top: 4px; }}
  .date {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11.5px;
    color: var(--muted); font-variant-numeric: tabular-nums; }}
  .tag {{ font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 999px;
    background: var(--backlog-soft); color: var(--muted); letter-spacing: 0.01em; }}
  .tag.p-mobile {{ background: var(--accent-soft); color: var(--accent); }}
  .tag.p-frontend {{ background: var(--ready-soft); color: var(--ready); }}
  .tag.p-backend {{ background: var(--review-soft); color: var(--review); }}

  footer {{ text-align: center; color: var(--muted-2); font-size: 12.5px; margin-top: 32px; }}
  footer a {{ color: var(--muted); }}

  /* Filters */
  .filters {{ margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--border);
    display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .filters-label {{ font-size: 13px; color: var(--muted); margin-right: 4px; }}
  .chip {{ display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px;
    border: 1px solid var(--border-strong); background: var(--card); color: var(--fg-2);
    border-radius: 999px; font-size: 13px; font-weight: 500; cursor: pointer;
    font-family: inherit; transition: all .12s; }}
  .chip:hover {{ border-color: var(--accent); color: var(--accent); }}
  .chip.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .range {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
    background: var(--card-2); border: 1px solid var(--border); border-radius: 999px; }}
  .range input[type=date] {{ border: none; background: transparent; font: inherit;
    color: var(--fg-2); font-size: 13px; padding: 2px 4px; outline: none;
    font-family: 'JetBrains Mono', monospace; }}
  .range input[type=date]::-webkit-calendar-picker-indicator {{ cursor: pointer; opacity: 0.6; }}
  .range span {{ color: var(--muted); font-size: 12px; }}
  .reset {{ color: var(--muted); font-size: 13px; background: none; border: none;
    cursor: pointer; padding: 6px 4px; font-family: inherit; text-decoration: underline;
    text-decoration-style: dotted; text-underline-offset: 3px; }}
  .reset:hover {{ color: var(--accent); }}
  .filter-summary {{ margin-left: auto; font-size: 12.5px; color: var(--muted); }}
  .task-item.hidden {{ display: none; }}
  .status.empty, .group.empty {{ display: none; }}

  @media (max-width: 600px) {{
    .wrap {{ padding: 24px 16px 60px; }}
    .header, .group > summary, .status {{ padding-left: 18px; padding-right: 18px; }}
    .header h1 {{ font-size: 22px; }}
    .group-title {{ font-size: 17px; }}
    .actions {{ margin-left: 0; width: 100%; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="header">
    <h1>Norma — статус задач</h1>
    <div class="subtitle">Прогресс по проекту в реальном времени</div>
    <div class="sources">
      <a href="https://github.com/orgs/{OWNER}/projects/9" target="_blank" rel="noopener">📱 Mobile App</a>
      <a href="https://github.com/orgs/{OWNER}/projects/7" target="_blank" rel="noopener">🖥 Frontend</a>
      <a href="https://github.com/orgs/{OWNER}/projects/4" target="_blank" rel="noopener">⚙ Backend</a>
    </div>
    <div class="filters" id="filters">
      <span class="filters-label">Обновлены:</span>
      <button class="chip active" data-preset="all">Все</button>
      <button class="chip" data-preset="today">Сегодня</button>
      <button class="chip" data-preset="yesterday">Вчера</button>
      <button class="chip" data-preset="7d">7 дней</button>
      <span class="range">
        <input type="date" id="from" aria-label="От">
        <span>—</span>
        <input type="date" id="to" aria-label="До">
      </span>
      <button class="reset" id="reset">Сбросить</button>
      <span class="filter-summary" id="summary"></span>
    </div>
    <div class="header-row">
      <div class="updated">
        <span class="dot"></span>
        <span>Последнее обновление:</span>
        <time datetime="{esc(now_iso)}" id="updated-at">{esc(now_iso[:16].replace("T"," "))} UTC</time>
        <span class="rel" id="rel-time"></span>
      </div>
      <div class="actions">
        <button class="btn secondary" onclick="location.reload()" title="Перезагрузить страницу">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 8a6 6 0 1 1-1.76-4.24M14 2v4h-4"/></svg>
          Перезагрузить
        </button>
        <a class="btn" href="{actions_url}" target="_blank" rel="noopener" title="Запустить обновление данных (требует доступа к репозиторию)">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 8a6 6 0 1 1-1.76-4.24M14 2v4h-4"/></svg>
          Обновить сейчас
        </a>
      </div>
    </div>
  </header>

  <details class="group in-progress">
    <summary>
      <svg class="chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4l4 4-4 4"/></svg>
      <span class="group-title">🚧 В работе</span>
      <span class="group-count">{total_work}</span>
    </summary>
    <div class="group-body">
      {work_blocks}
    </div>
  </details>

  <details class="group testing">
    <summary>
      <svg class="chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4l4 4-4 4"/></svg>
      <span class="group-title">🧪 На тестировании</span>
      <span class="group-count">{total_testing}</span>
    </summary>
    <div class="group-body">
      {testing_blocks}
    </div>
  </details>

  <details class="group done" open>
    <summary>
      <svg class="chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4l4 4-4 4"/></svg>
      <span class="group-title">✅ Готово</span>
      <span class="group-count">{len(done)}</span>
    </summary>
    <div class="group-body">
      {done_block}
    </div>
  </details>

  <footer>Автоматически обновляется каждый час · <a href="https://github.com/{OWNER}/norma-status" target="_blank" rel="noopener">исходник</a></footer>
</div>
<script>
  (function () {{
    // Relative "X min ago" label
    const relEl = document.getElementById('rel-time');
    const t = document.getElementById('updated-at');
    if (relEl && t) {{
      const updated = new Date(t.getAttribute('datetime'));
      const fmt = () => {{
        const diff = Math.max(0, (Date.now() - updated.getTime()) / 1000);
        if (diff < 60) return 'только что';
        if (diff < 3600) return Math.floor(diff/60) + ' мин назад';
        if (diff < 86400) return Math.floor(diff/3600) + ' ч назад';
        return Math.floor(diff/86400) + ' дн назад';
      }};
      relEl.textContent = '· ' + fmt();
      setInterval(() => {{ relEl.textContent = '· ' + fmt(); }}, 60000);
    }}

    // Date filtering
    const items = Array.from(document.querySelectorAll('.task-item'));
    const chips = Array.from(document.querySelectorAll('.chip'));
    const fromI = document.getElementById('from');
    const toI = document.getElementById('to');
    const reset = document.getElementById('reset');
    const summary = document.getElementById('summary');

    const toLocalDate = iso => {{
      if (!iso) return null;
      const d = new Date(iso);
      return new Date(d.getFullYear(), d.getMonth(), d.getDate());
    }};
    const startOfToday = () => {{
      const d = new Date();
      return new Date(d.getFullYear(), d.getMonth(), d.getDate());
    }};
    const fmtDate = d => {{
      const y = d.getFullYear();
      const m = String(d.getMonth()+1).padStart(2,'0');
      const day = String(d.getDate()).padStart(2,'0');
      return `${{y}}-${{m}}-${{day}}`;
    }};
    const parseInputDate = s => {{
      if (!s) return null;
      const [y,m,d] = s.split('-').map(Number);
      return new Date(y, m-1, d);
    }};

    let preset = 'all';

    const applyPreset = p => {{
      preset = p;
      chips.forEach(c => c.classList.toggle('active', c.dataset.preset === p));
      const today = startOfToday();
      if (p === 'today') {{
        fromI.value = fmtDate(today); toI.value = fmtDate(today);
      }} else if (p === 'yesterday') {{
        const y = new Date(today); y.setDate(y.getDate()-1);
        fromI.value = fmtDate(y); toI.value = fmtDate(y);
      }} else if (p === '7d') {{
        const start = new Date(today); start.setDate(start.getDate()-6);
        fromI.value = fmtDate(start); toI.value = fmtDate(today);
      }} else {{
        fromI.value = ''; toI.value = '';
      }}
      apply();
    }};

    const apply = () => {{
      const from = parseInputDate(fromI.value);
      const to = parseInputDate(toI.value);
      const toEnd = to ? new Date(to.getFullYear(), to.getMonth(), to.getDate()+1) : null;
      let visible = 0;

      items.forEach(li => {{
        const d = toLocalDate(li.dataset.updated);
        let show = true;
        if (from && d && d < from) show = false;
        if (toEnd && d && d >= toEnd) show = false;
        if (!d && (from || toEnd)) show = false;
        li.classList.toggle('hidden', !show);
        if (show) visible++;
      }});

      // Hide empty status sections and groups
      document.querySelectorAll('.status').forEach(s => {{
        const has = s.querySelector('.task-item:not(.hidden)');
        s.classList.toggle('empty', !has);
        const cnt = s.querySelectorAll('.task-item:not(.hidden)').length;
        const cntEl = s.querySelector('.status-count');
        if (cntEl) cntEl.textContent = cnt;
      }});
      document.querySelectorAll('.group').forEach(g => {{
        const has = g.querySelector('.task-item:not(.hidden)');
        g.classList.toggle('empty', !has);
        const cnt = g.querySelectorAll('.task-item:not(.hidden)').length;
        const cntEl = g.querySelector('.group-count');
        if (cntEl) cntEl.textContent = cnt;
      }});

      const filtering = preset !== 'all' || fromI.value || toI.value;
      summary.textContent = filtering ? `Найдено: ${{visible}} из ${{items.length}}` : '';

      // Auto-open groups when filtering so user sees results
      if (filtering) {{
        document.querySelectorAll('.group:not(.empty)').forEach(g => g.open = true);
      }}
    }};

    chips.forEach(c => c.addEventListener('click', () => applyPreset(c.dataset.preset)));
    fromI.addEventListener('change', () => {{
      preset = 'custom';
      chips.forEach(c => c.classList.remove('active'));
      apply();
    }});
    toI.addEventListener('change', () => {{
      preset = 'custom';
      chips.forEach(c => c.classList.remove('active'));
      apply();
    }});
    reset.addEventListener('click', () => applyPreset('all'));
  }})();
</script>
</body>
</html>
"""


def main() -> None:
    done, work, testing = collect()
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    now_human = now_dt.strftime("%Y-%m-%d %H:%M UTC")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(render_md(done, work, testing, now_human))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(render_html(done, work, testing, now_iso))


if __name__ == "__main__":
    main()

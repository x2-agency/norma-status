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
STATUS_ORDER = [
    "В работе", "В разработке", "В процессе",
    "На ревью", "Передано в тестирование", "Тестирование",
    "Готово к работе", "Есть вопросы", "Есть блокеры", "Бэклог",
]


def fetch(project_number: int) -> list[dict]:
    proc = subprocess.run(
        [
            "gh", "project", "item-list", str(project_number),
            "--owner", OWNER, "--format", "json", "--limit", "1000",
        ],
        capture_output=True, text=True,
    )
    if proc.stderr:
        print(f"[project {project_number}] gh stderr: {proc.stderr[:300]}", flush=True)
    if not proc.stdout.strip():
        raise RuntimeError(f"No data for project {project_number}; exit={proc.returncode}")
    return json.loads(proc.stdout)["items"]


def collect():
    """Returns (done, in_progress_by_status) — each entry is dict with title/url/project."""
    done = []
    in_progress = defaultdict(list)
    for number, label in PROJECTS:
        for item in fetch(number):
            content = item.get("content") or {}
            entry = {
                "title": (item.get("title") or content.get("title") or "(без названия)").strip(),
                "url": content.get("url"),
                "project": label,
            }
            status = (item.get("status") or "Без статуса").strip()
            (done if status == DONE_STATUS else in_progress[status]).append(entry)
    return done, in_progress


def ordered_statuses(in_progress: dict) -> list[str]:
    seen = set()
    result = []
    for s in STATUS_ORDER:
        if s in in_progress:
            result.append(s); seen.add(s)
    for s in sorted(in_progress):
        if s not in seen:
            result.append(s)
    return result


def render_md(done, in_progress, now: str) -> str:
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
        return f"- {link} · _{e['project']}_"

    total = sum(len(v) for v in in_progress.values())
    parts.append(f"<details><summary><b>🚧 В работе — {total}</b></summary>")
    parts.append("")
    for status in ordered_statuses(in_progress):
        items = in_progress[status]
        parts.append(f"#### {status} ({len(items)})")
        parts.append("")
        parts.extend(line(e) for e in sorted(items, key=lambda x: x["title"].lower()))
        parts.append("")
    parts.append("</details>")
    parts.append("")
    parts.append(f"<details open><summary><b>✅ Готово — {len(done)}</b></summary>")
    parts.append("")
    parts.extend(line(e) for e in sorted(done, key=lambda x: x["title"].lower()))
    parts.append("")
    parts.append("</details>")
    parts.append("")
    return "\n".join(parts)


def render_html(done, in_progress, now: str) -> str:
    def esc(s: str) -> str:
        return html.escape(s, quote=True)

    def li(e: dict) -> str:
        title = esc(e["title"])
        proj = esc(e["project"])
        if e["url"]:
            link = f'<a href="{esc(e["url"])}" target="_blank" rel="noopener">{title}</a>'
        else:
            link = title
        return f'<li>{link} <span class="proj">{proj}</span></li>'

    sections_html = []
    total = sum(len(v) for v in in_progress.values())
    inner = []
    for status in ordered_statuses(in_progress):
        items = in_progress[status]
        items_html = "\n".join(li(e) for e in sorted(items, key=lambda x: x["title"].lower()))
        inner.append(
            f'<h3>{esc(status)} <span class="count">{len(items)}</span></h3>\n'
            f'<ul>{items_html}</ul>'
        )
    sections_html.append(
        f'<details>\n'
        f'<summary><span class="emoji">🚧</span> В работе '
        f'<span class="badge">{total}</span></summary>\n'
        f'<div class="body">{"".join(inner)}</div>\n'
        f'</details>'
    )

    done_html = "\n".join(li(e) for e in sorted(done, key=lambda x: x["title"].lower()))
    sections_html.append(
        f'<details open>\n'
        f'<summary><span class="emoji">✅</span> Готово '
        f'<span class="badge done">{len(done)}</span></summary>\n'
        f'<div class="body"><ul>{done_html}</ul></div>\n'
        f'</details>'
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Norma — статус задач</title>
<style>
  :root {{
    --bg: #0f1115;
    --card: #161922;
    --border: #232838;
    --fg: #e7eaf2;
    --muted: #8a92a6;
    --accent: #4f8cff;
    --done: #3ecf8e;
    --warn: #ffb454;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --bg: #f7f8fa;
      --card: #ffffff;
      --border: #e4e7ee;
      --fg: #1a1d24;
      --muted: #6a7080;
      --accent: #2f6fdb;
      --done: #1faa6b;
      --warn: #c7791a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg);
    font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
  .wrap {{ max-width: 920px; margin: 0 auto; padding: 48px 24px 80px; }}
  h1 {{ font-size: 28px; margin: 0 0 8px; letter-spacing: -0.01em; }}
  .meta {{ color: var(--muted); font-size: 14px; margin-bottom: 4px; }}
  .sources a {{ color: var(--accent); text-decoration: none; margin-right: 12px; }}
  .sources a:hover {{ text-decoration: underline; }}
  details {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    margin-top: 20px; overflow: hidden; }}
  summary {{ list-style: none; cursor: pointer; padding: 18px 20px; font-size: 18px; font-weight: 600;
    display: flex; align-items: center; gap: 10px; user-select: none; }}
  summary::-webkit-details-marker {{ display: none; }}
  summary::before {{ content: "▸"; color: var(--muted); font-size: 14px; transition: transform .15s; }}
  details[open] > summary::before {{ transform: rotate(90deg); }}
  .emoji {{ font-size: 18px; }}
  .badge {{ margin-left: auto; background: rgba(255,180,84,0.15); color: var(--warn);
    padding: 2px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; }}
  .badge.done {{ background: rgba(62,207,142,0.15); color: var(--done); }}
  .body {{ padding: 0 20px 20px; border-top: 1px solid var(--border); }}
  h3 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--muted); margin: 22px 0 8px; font-weight: 600; }}
  .count {{ color: var(--fg); opacity: 0.65; font-weight: 400; }}
  ul {{ list-style: none; padding: 0; margin: 0; }}
  li {{ padding: 10px 0; border-bottom: 1px solid var(--border); display: flex;
    align-items: baseline; gap: 12px; flex-wrap: wrap; }}
  li:last-child {{ border-bottom: none; }}
  li a {{ color: var(--fg); text-decoration: none; flex: 1; min-width: 0; }}
  li a:hover {{ color: var(--accent); }}
  .proj {{ color: var(--muted); font-size: 13px; flex-shrink: 0; }}
  footer {{ color: var(--muted); font-size: 13px; margin-top: 32px; text-align: center; }}
  footer a {{ color: var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Norma — статус задач</h1>
  <div class="meta">Обновлено: {esc(now)}</div>
  <div class="meta sources">
    Источники:
    <a href="https://github.com/orgs/{OWNER}/projects/9" target="_blank" rel="noopener">Mobile App</a>
    <a href="https://github.com/orgs/{OWNER}/projects/7" target="_blank" rel="noopener">Frontend</a>
    <a href="https://github.com/orgs/{OWNER}/projects/4" target="_blank" rel="noopener">Backend</a>
  </div>
  {chr(10).join(sections_html)}
  <footer>Автоматически обновляется каждые 5 минут</footer>
</div>
</body>
</html>
"""


def main() -> None:
    done, in_progress = collect()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(render_md(done, in_progress, now))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(render_html(done, in_progress, now))


if __name__ == "__main__":
    main()

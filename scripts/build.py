#!/usr/bin/env python3
"""Generate README.md from x2-agency GitHub Projects (#9, #7, #4)."""
import json
import os
import subprocess
from datetime import datetime, timezone
from collections import defaultdict

OWNER = "x2-agency"
PROJECTS = [
    (9, "Norma — Mobile App"),
    (7, "Norma — Frontend"),
    (4, "Norma — Backend"),
]
DONE_STATUS = "Готово"


def fetch(project_number: int) -> list[dict]:
    proc = subprocess.run(
        [
            "gh", "project", "item-list", str(project_number),
            "--owner", OWNER, "--format", "json", "--limit", "1000",
        ],
        capture_output=True, text=True,
    )
    if proc.stderr:
        print(f"[project {project_number}] gh stderr: {proc.stderr[:500]}", flush=True)
    if not proc.stdout.strip():
        raise RuntimeError(f"No data for project {project_number}; exit={proc.returncode}")
    return json.loads(proc.stdout)["items"]


def item_line(item: dict, project_label: str) -> str:
    content = item.get("content") or {}
    title = item.get("title") or content.get("title") or "(без названия)"
    url = content.get("url")
    title = title.replace("|", "\\|").replace("\n", " ").strip()
    if url:
        link = f"[{title}]({url})"
    else:
        link = title
    return f"- {link} · _{project_label}_"


def main() -> None:
    done: list[str] = []
    in_progress: dict[str, list[str]] = defaultdict(list)

    for number, label in PROJECTS:
        for item in fetch(number):
            status = (item.get("status") or "Без статуса").strip()
            line = item_line(item, label)
            if status == DONE_STATUS:
                done.append(line)
            else:
                in_progress[status].append(line)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    in_progress_total = sum(len(v) for v in in_progress.values())

    parts: list[str] = []
    parts.append("# Norma — статус задач")
    parts.append("")
    parts.append(f"_Обновлено: {now}_")
    parts.append("")
    parts.append(
        f"Источники: "
        f"[Mobile App](https://github.com/orgs/{OWNER}/projects/9) · "
        f"[Frontend](https://github.com/orgs/{OWNER}/projects/7) · "
        f"[Backend](https://github.com/orgs/{OWNER}/projects/4)"
    )
    parts.append("")

    parts.append(f"<details><summary><b>🚧 В работе — {in_progress_total}</b></summary>")
    parts.append("")
    status_order = [
        "В работе", "В разработке", "В процессе",
        "На ревью", "Передано в тестирование", "Тестирование",
        "Готово к работе", "Есть вопросы", "Есть блокеры", "Бэклог",
    ]
    seen_statuses = set()
    for status in status_order:
        items = in_progress.get(status)
        if not items:
            continue
        seen_statuses.add(status)
        parts.append(f"#### {status} ({len(items)})")
        parts.append("")
        parts.extend(sorted(items, key=str.lower))
        parts.append("")
    for status, items in sorted(in_progress.items()):
        if status in seen_statuses:
            continue
        parts.append(f"#### {status} ({len(items)})")
        parts.append("")
        parts.extend(sorted(items, key=str.lower))
        parts.append("")
    parts.append("</details>")
    parts.append("")

    parts.append(f"<details><summary><b>✅ Готово — {len(done)}</b></summary>")
    parts.append("")
    parts.extend(sorted(done, key=str.lower))
    parts.append("")
    parts.append("</details>")
    parts.append("")

    out_path = os.environ.get("OUT_PATH", "README.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


if __name__ == "__main__":
    main()

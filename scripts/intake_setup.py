#!/usr/bin/env python3
"""Turn a "Propose a better set-up" issue into ``setups/<slug>/setup.json``.

Reads the issue form (``.github/ISSUE_TEMPLATE/propose-setup.yml``), builds the
set-up, checks it with ``benchmark1d2d.setups.check`` and, when it passes,
writes the file for the workflow to commit; the set-ups workflow then re-runs
it. Writes a Markdown reply either way. Exit status 0 when the set-up was
written, 1 when it has problems (the reply lists them).

Usage::

    python scripts/intake_setup.py --issue-body BODY.md --issue-number N --author LOGIN --reply REPLY.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runner" / "python"))
SETUPS = REPO / "setups"


def fields(body: str) -> dict[str, str]:
    out, key = {}, None
    for line in body.splitlines():
        m = re.match(r"^###\s+(.*)$", line)
        if m:
            key = m.group(1).strip().lower()
            out[key] = ""
        elif key is not None:
            out[key] += line + "\n"
    return {k: "\n".join(ln for ln in v.splitlines() if not ln.strip().startswith("```")).strip() for k, v in out.items()}


def slugify(*parts: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", "-".join(parts).lower()).strip("-")[:60]


def build(f: dict[str, str], author: str) -> dict:
    settings = {}
    for line in f.get("settings", "").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        parts = re.split(r"\s*=\s*|\s+", line, maxsplit=1) if "=" not in line else [x.strip() for x in line.split("=", 1)]
        k = parts[0]
        v = parts[1] if len(parts) > 1 else "on"
        settings[k] = v
    tests_txt = f.get("tests", "all").strip()
    tests = "all" if tests_txt.lower() in ("", "all", "_no response_") else [t.strip().upper() for t in re.split(r"[,\s]+", tests_txt) if t.strip()]
    tier = "T1" if "T1" in f.get("kind of set-up", "") else "T2"
    s = {"schema_version": "1.0.0", "base": f.get("model", "").split(" ")[0], "title": f.get("short name", "")[:60],
         "proposed_by": f.get("your name or organisation", "")[:120], "github_user": re.sub(r"[^A-Za-z0-9-]", "", author)[:39] or None,
         "tier": tier, "tests": tests, "settings": settings, "reason": f.get("why these settings", "")[:2000],
         "date": dt.date.today().isoformat()}
    g = f.get("developer's guidance (for t1)", "")
    if g and g != "_No response_":
        s["guidance_source"] = g[:300]
    if "[x]" in f.get("developer", "").lower():
        s["developer"] = True
    return {k: v for k, v in s.items() if v is not None}


def main() -> int:
    from benchmark1d2d import setups

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--issue-body", type=Path, required=True)
    ap.add_argument("--issue-number", required=True)
    ap.add_argument("--author", default="")
    ap.add_argument("--reply", type=Path, required=True)
    a = ap.parse_args()
    s = build(fields(a.issue_body.read_text(encoding="utf-8")), a.author)
    problems = setups.check(s)
    if problems:
        a.reply.write_text("The set-up could not be run yet:\n\n" + "\n".join(f"- {p}" for p in problems)
                           + "\n\nEdit the issue to fix them; the bot checks it again.\n", encoding="utf-8")
        return 1
    slug = slugify(s["base"], s["title"], s.get("github_user", ""))
    folder = SETUPS / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "setup.json").write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    changes = "\n".join(f"- `{k}` = `{v}`" for k, v in s["settings"].items())
    a.reply.write_text(
        f"Thanks. The set-up is saved as `setups/{slug}/setup.json` and the suite is re-running **{s['base']}** with:\n\n{changes}\n\n"
        f"on {'every test it runs' if s['tests'] == 'all' else ', '.join(s['tests'])}. When the run finishes (usually within the hour), "
        f"the results appear on each test page beside the suite's own, as “{s['title']}” by {s['proposed_by']}"
        + (f" (GitHub {s['github_user']})" if s.get("github_user") else "") + ". Nobody approves or holds them back.\n",
        encoding="utf-8")
    print(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

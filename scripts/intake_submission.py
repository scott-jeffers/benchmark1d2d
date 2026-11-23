#!/usr/bin/env python3
"""Turn a submission sent as a GitHub issue into a scored submission folder.

The "Score your model" page makes one zip (``submission.json`` and the
results sheets) and opens a GitHub issue from the *Submit results* form, with
the zip attached. This script, run by ``.github/workflows/submission-intake.yml``:

1. reads the issue's form fields and finds the attached zip (or loose
   ``.csv``/``.parquet`` attachments);
2. downloads it from GitHub's attachment store only, unpacks only results
   sheets and ``submission.json`` (nothing is executed), and builds
   ``submissions/<slug>/`` with a valid ``submission.json``, filling in
   whatever the page did not (the test's current version, which file is
   which grid);
3. scores it with ``scripts/score_submissions.py`` and writes the reply.

With ``--publish`` the folder is left in ``submissions/`` for the workflow to
commit; otherwise it is scored in a scratch copy and removed.

Usage::

    python scripts/intake_submission.py --issue-body body.md --issue-number 12 --reply out/reply.md [--publish]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

SUBMISSIONS = REPO / "submissions"
SITE = "https://scott-jeffers.github.io/benchmark1d2d"
ATTACHMENT = re.compile(r"https://github\.com/(?:user-attachments/files/\d+/[\w.\-%]+|[\w.-]+/[\w.-]+/files/\d+/[\w.\-%]+)")
MAX_BYTES = 60 * 1024 * 1024
KEEP = (".csv", ".parquet", ".txt")


def form_fields(body: str) -> dict[str, str]:
    """GitHub issue forms render as '### Label\\n\\nvalue' blocks."""
    out = {}
    for block in re.split(r"(?m)^### ", body or ""):
        if not block.strip():
            continue
        label, _, value = block.partition("\n")
        value = value.strip()
        out[label.strip().lower()] = "" if value == "_No response_" else value
    return out


def field(f: dict, *names: str) -> str:
    for n in names:
        for k, v in f.items():
            if k.startswith(n):
                return v
    return ""


def slugify(*parts: str) -> str:
    s = "-".join(p for p in parts if p)
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "submission"


def download(url: str) -> bytes:
    if not ATTACHMENT.fullmatch(url):
        raise ValueError(f"not a GitHub attachment: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "benchmark1d2d-intake"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("attachment larger than 60 MB")
    return data


MODEL_DIRS = ("model", "output")  # folders in a submission zip that hold the model files and the solver's outputs
MAX_MODEL_BYTES = 20 * 1024 * 1024  # kept in the repository and on the site, like the suite's own model files


def unpack(blobs: list[tuple[str, bytes]], dest: Path) -> dict | None:
    """Results sheets (flattened, safe names) into dest, model files into dest/model_files/;
    returns submission.json if one came with them."""
    sub = None
    for name, data in blobs:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                total = 0
                for zi in z.infolist():
                    base = Path(zi.filename).name
                    if zi.is_dir() or not base or base.startswith("."):
                        continue
                    total += zi.file_size
                    if total > 4 * MAX_BYTES:
                        raise ValueError("the zip unpacks to more than 240 MB")
                    parts = [x for x in Path(zi.filename).parts if x not in ("", ".")]
                    top = next((i for i, x in enumerate(parts) if x.lower() in MODEL_DIRS), None)
                    if top is not None and ".." not in parts:  # model files and outputs, kept with their folders
                        target = dest / "model_files" / Path(*[re.sub(r"[^\w.\-]", "_", x) for x in parts[top:]])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(z.read(zi))
                        continue
                    if base == "submission.json":
                        sub = json.loads(z.read(zi).decode("utf-8"))
                    elif base.lower().endswith(KEEP) and not base.lower().endswith(".txt"):
                        (dest / re.sub(r"[^\w.\-]", "_", base)).write_bytes(z.read(zi))
        elif name.lower().endswith((".csv", ".parquet")):
            (dest / re.sub(r"[^\w.\-]", "_", Path(name).name)).write_bytes(data)
    return sub


def grid_size(path: Path) -> float | None:
    """The cell size of a results sheet: from its name (…_dx2.5.csv) or from the spacing of its x values."""
    m = re.search(r"_dx([0-9.]+)\.(csv|parquet)$", path.name)
    if m:
        try:
            return float(m.group(1).rstrip("."))
        except ValueError:
            pass
    try:
        from benchmark1d2d.io.results import read_results_parquet
        import numpy as np

        x = np.unique(read_results_parquet(path)["x"].dropna().to_numpy(float))
        d = np.diff(x)
        d = d[d > 1e-9]
        return float(np.median(d)) if len(d) else None
    except Exception:  # noqa: BLE001
        return None


def build_case(m: dict, files: list[Path]) -> tuple[list[str], list[str]]:
    """The results files for one test, coarsest first (the finest is scored); and notes."""
    from benchmark1d2d.catalog import load_manifest  # noqa: F401 - imported for the side effect of the path

    sid = m["test_id"].split("_")[0]
    mine = [f for f in files if f.name.startswith(sid)] or files
    levels = sorted((m["simulation"].get("mesh_refinement") or {}).get("levels") or [], reverse=True)
    notes = []
    if len(levels) > 1:
        sized = []
        for f in mine:
            d = grid_size(f)
            lv = min(levels, key=lambda L: abs(L - d)) if d else None
            if lv is None or abs(lv - d) > 0.05 * lv:
                notes.append(f"`{f.name}`: its spacing ({d}) is not one of the test's grids ({', '.join(f'{v:g}' for v in levels)}); left out")
                continue
            sized.append((lv, f))
        sized.sort(key=lambda p: -p[0])
        if len({lv for lv, _ in sized}) < len(sized):
            notes.append("two sheets have the same grid size; the last one is used")
        by = {lv: f for lv, f in sized}
        return [by[lv].name for lv in sorted(by, reverse=True)], notes
    return [mine[0].name] if mine else [], notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--issue-body", type=Path, required=True)
    ap.add_argument("--issue-number", required=True)
    ap.add_argument("--reply", type=Path, required=True)
    ap.add_argument("--publish", action="store_true", help="keep the folder in submissions/ for the workflow to commit")
    ap.add_argument("--author", default="", help="GitHub login of the issue author (recorded with the results)")
    ap.add_argument("--local-files", nargs="*", type=Path, help="testing: use these files instead of the issue's attachments")
    args = ap.parse_args()

    from benchmark1d2d.catalog import load_manifest
    import score_submissions as ss

    body = args.issue_body.read_text(encoding="utf-8")
    f = form_fields(body)
    reply = []
    try:
        urls = list(dict.fromkeys(ATTACHMENT.findall(body)))
        if args.local_files:
            urls = [str(p) for p in args.local_files]
        if not urls:
            raise ValueError("no attached file was found. Drag the zip the Score page made (or your results sheets) into the issue, then save it.")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            blobs = ([(p.name, p.read_bytes()) for p in args.local_files] if args.local_files
                     else [(u.rsplit("/", 1)[-1], download(u)) for u in urls])
            sub = unpack(blobs, tmp) or {}
            sheets = sorted(p for p in tmp.iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".parquet"))
            if not sheets:
                raise ValueError("the attachment holds no results sheets (.csv or .parquet).")
            software = field(f, "software") or (sub.get("solver") or {}).get("name", "")
            version = field(f, "version") or (sub.get("solver") or {}).get("version", "")
            org = field(f, "organisation", "organization", "who") or sub.get("submitted_by", "")
            settings = field(f, "settings") or (sub.get("solver") or {}).get("options", "")
            licence = "CC0-1.0" if "cc0" in (field(f, "licence", "license") or sub.get("results_licence", "")).lower() else "CC-BY-4.0"
            if not (software and version and org):
                raise ValueError("the software, its version and who ran it are needed (fill them in on the form).")
            tests = [t.strip() for t in re.split(r"[,\s]+", field(f, "test")) if t.strip()] or [c["test_id"] for c in sub.get("cases", [])]
            if not tests:  # from the sheet names
                tests = sorted({re.match(r"^([A-Z0-9]+-[A-Z0-9-]+?)(_dx|\.|_)", p.name).group(1) for p in sheets
                                if re.match(r"^([A-Z0-9]+-[A-Z0-9-]+?)(_dx|\.|_)", p.name)})
            cases, notes = [], []
            for tid in tests:
                try:
                    m = load_manifest(tid, repo=REPO)
                except Exception:  # noqa: BLE001
                    notes.append(f"{tid}: no such test")
                    continue
                files, n = build_case(m, sheets)
                notes += n
                if files:
                    cases.append({"test_id": m["test_id"].split("_")[0], "case_version": m["case_version"], "results": files})
            if not cases:
                raise ValueError("none of the sheets could be matched to a test. " + " ".join(notes))
            slug = slugify(software, version, org)
            submission = {"schema_version": "1.0.0", "solver": {"name": software, "version": version, **({"options": settings} if settings else {})},
                          "submitted_by": org, "date": date.today().isoformat(), "results_licence": licence, "cases": cases,
                          "notes": f"Submitted through issue #{args.issue_number}."}
            author = re.sub(r"[^A-Za-z0-9-]", "", args.author)[:39]
            if author:
                submission["github_user"] = author
            folder = SUBMISSIONS / slug
            existing = json.loads((folder / "submission.json").read_text(encoding="utf-8")) if (folder / "submission.json").is_file() else None
            if existing and author and existing.get("github_user") not in (None, author):
                # someone else already published under this name: keep theirs, file this one separately
                slug = slugify(software, version, org, author)
                folder = SUBMISSIONS / slug
                existing = json.loads((folder / "submission.json").read_text(encoding="utf-8")) if (folder / "submission.json").is_file() else None
            if existing:  # a second batch from the same software and organisation: add or replace its tests
                keep = [c for c in existing["cases"] if c["test_id"] not in {c2["test_id"] for c2 in cases}]
                submission["cases"] = keep + cases
            stage = tmp / "stage" / slug
            stage.mkdir(parents=True)
            if folder.is_dir():
                for p in folder.iterdir():
                    shutil.copy2(p, stage / p.name)
            for c in cases:
                for name in c["results"]:
                    shutil.copy2(tmp / name, stage / name)
            mf = tmp / "model_files"
            if mf.is_dir() and any(mf.rglob("*")):
                from export_inputs import zip_folder

                size = zip_folder(mf, stage / "model_files.zip")
                if size > MAX_MODEL_BYTES:
                    (stage / "model_files.zip").unlink()
                    notes.append(f"the model files are {size / 1e6:.0f} MB, over the {MAX_MODEL_BYTES / 1e6:.0f} MB limit; publish them elsewhere "
                                 "(Zenodo, a release) and give the link in the settings")
                else:
                    submission["model_files"] = "model_files.zip"
            (stage / "submission.json").write_text(json.dumps(submission, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            ss.SUBMISSIONS, ss.OUT = stage.parent, tmp / "cards"
            lines, problems = ss.score_folder(stage, ss._key())
            reply += [f"Thanks! Here are the scores, computed with the suite's own scorer and limits (the same as every other model on the site).", ""]
            reply += lines
            if notes:
                reply += ["**Notes**", ""] + [f"- {n}" for n in notes] + [""]
            if problems:
                reply += ["**Problems**", ""] + [f"- {p}" for p in problems] + ["",
                          "Fix the sheet and attach it again in a new comment or by editing the issue; this reply updates."]
            else:
                reply += [f"No problems found, so the results are published automatically, marked *submitted by {org}*"
                          + (f" (sent from GitHub account {author})" if author else "") + f", under {licence}. "
                          "They are shown as submitted results: the suite scored your files but did not re-run your software. "
                          + ("Your model files are published with them, so anyone with the software can check the result." if submission.get("model_files") else
                             "**No model files came with them**, so they are labelled *results only*. To let others check them, add a `model/` folder "
                             "(the files your software read) and an `output/` folder (what it wrote) to the zip and comment with it here.")]
            if args.publish and not problems:
                if folder.is_dir():
                    shutil.rmtree(folder)
                shutil.copytree(stage, folder)
                reply += ["", f"Published: `submissions/{slug}/`. It appears on {SITE} at the next site build."]
            elif args.publish:
                reply += ["", "Not published: fix the problems above first."]
                args.reply.parent.mkdir(parents=True, exist_ok=True)
                args.reply.write_text("\n".join(reply) + "\n", encoding="utf-8")
                return 2
    except Exception as exc:  # noqa: BLE001 - every failure becomes a reply the submitter can act on
        reply = [f"Could not read this submission: {exc}", "",
                 f"The easiest way is the **Publish** button on {SITE}/score.html, which makes the zip for you."]
        args.reply.parent.mkdir(parents=True, exist_ok=True)
        args.reply.write_text("\n".join(reply) + "\n", encoding="utf-8")
        return 1
    args.reply.parent.mkdir(parents=True, exist_ok=True)
    args.reply.write_text("\n".join(reply) + "\n", encoding="utf-8")
    print("\n".join(reply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

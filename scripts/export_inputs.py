#!/usr/bin/env python3
"""Zip the model files each runner kept (``BENCH_KEEP_INPUTS``), and what the solver wrote back, one zip per test and model.

``benchmark1d2d.keep.inputs`` copies the files a runner writes for a solver
(before the solver runs) to ``out/inputs/<model>/<test>/<level>/``. This
script zips each ``<model>/<test>`` folder to
``out/inputs_zip/<test>.<model>.inputs.zip`` with fixed timestamps and sorted
entries, so the same model gives the same bytes. The result collector files
the zips under ``site/fixtures/inputs/<test>/<model>.zip`` and the site
offers them on each test page ("Check this result").

What the solver wrote (``benchmark1d2d.keep.outputs`` and ``result_file``,
under ``out/outputs/<model>/<test>/``) is zipped the same way to
``out/outputs_zip/<test>.<model>.outputs.zip``. Those can be large, so the
collector publishes them as release files rather than on the website.

Usage::

    python scripts/export_inputs.py [--src out/inputs] [--dest out/inputs_zip] [--local]
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "site" / "fixtures" / "inputs"
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_ZIP_BYTES = 1500 * 1024 * 1024  # a GitHub release file may be up to 2 GB
OUTPUTS_README = """What {model} wrote when it ran {test}

native/   the solver's own output files, as it wrote them (one folder per grid where the test has several)
results/  the results file the suite's scorer read (Parquet; columns t, x, y, h, u, v, p, ...)

With the matching inputs zip (the model files the solver read) and the score card, anyone with the
software can re-run the model and compare. Files too large to publish are listed in NOT_INCLUDED.txt.
SHA256SUMS lists every file's checksum.
"""
STAMP = (2024, 1, 1, 0, 0, 0)


def zip_folder(folder: Path, dest: Path, readme: str | None = None) -> int:
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    lines = []
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as z:
        if readme:
            info = zipfile.ZipInfo("README.txt", STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, readme)
        for p in files:
            rel = p.relative_to(folder).as_posix()
            data = p.read_bytes()
            info = zipfile.ZipInfo(rel, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
            lines.append(f"{hashlib.sha256(data).hexdigest()}  {rel}")
        info = zipfile.ZipInfo("SHA256SUMS", STAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, "\n".join(lines) + "\n")
    return dest.stat().st_size


def export_outputs(src: Path, dest: Path) -> int:
    if not src.is_dir():
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for model in sorted(p for p in src.iterdir() if p.is_dir()):
        for test in sorted(p for p in model.iterdir() if p.is_dir()):
            z = dest / f"{test.name}.{model.name}.outputs.zip"
            size = zip_folder(test, z, OUTPUTS_README.format(model=model.name, test=test.name))
            if size > MAX_OUTPUT_ZIP_BYTES:
                print(f"  {test.name} {model.name}: outputs {size / 1e6:.0f} MB, over the {MAX_OUTPUT_ZIP_BYTES / 1e6:.0f} MB limit; not published")
                z.unlink()
                continue
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", type=Path, default=REPO / "out" / "inputs")
    ap.add_argument("--dest", type=Path, default=REPO / "out" / "inputs_zip")
    ap.add_argument("--local", action="store_true", help="also file the zips in site/fixtures/inputs/")
    ap.add_argument("--outputs", type=Path, default=REPO / "out" / "outputs", help="what the solvers wrote (keep.outputs)")
    ap.add_argument("--outputs-dest", type=Path, default=REPO / "out" / "outputs_zip")
    a = ap.parse_args()
    n_out = export_outputs(a.outputs, a.outputs_dest)
    if n_out:
        print(f"zipped the outputs of {n_out} test/model pairs to {a.outputs_dest}")
    if not a.src.is_dir():
        print(f"no kept inputs in {a.src}")
        return 0
    a.dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for model in sorted(p for p in a.src.iterdir() if p.is_dir()):
        for test in sorted(p for p in model.iterdir() if p.is_dir()):
            z = a.dest / f"{test.name}.{model.name}.inputs.zip"
            size = zip_folder(test, z)
            if size > MAX_ZIP_BYTES:
                print(f"  {test.name} {model.name}: {size / 1e6:.1f} MB, over the {MAX_ZIP_BYTES / 1e6:.0f} MB limit; not published")
                z.unlink()
                continue
            if a.local:
                fx = FIXTURES / test.name / f"{model.name}.zip"
                fx.parent.mkdir(parents=True, exist_ok=True)
                fx.write_bytes(z.read_bytes())
            n += 1
    print(f"zipped the model files of {n} test/model pairs to {a.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

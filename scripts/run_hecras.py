#!/usr/bin/env python3
"""Score HEC-RAS (USACE) on the 1D catalog cases.

HEC-RAS is free, public-domain software from the U.S. Army Corps of Engineers
Hydrologic Engineering Center; it runs on Windows. This script writes a plain-
text HEC-RAS project for every refinement level of a case, runs it with
``ras-commander`` (HEC-RAS's own command-line compute, no GUI), reads the
results from the plan HDF file and scores them like any other solver.

Cases
-----
A1F-001  MacDonald steady backwater: standard-step steady flow, subcritical.
         The reference assumes a wide channel (hydraulic radius = depth), so
         the reach is modelled 100 km wide carrying the same unit discharge
         (0.2 m²/s). The walls' share of the wetted perimeter then moves the
         depth by 0.0006 mm (at 1 km wide it was 0.06 mm, a floor that hid
         HEC-RAS's grid convergence).
         Friction only (expansion/contraction coefficients 0); standard-step
         tolerance tightened to 0.01 mm so solver tolerance does not mask the
         discretisation error being measured.

Finding (HEC-RAS 6.6): input elevations are stored to the nearest 0.001 ft
(0.3 mm) even in an SI project -- every cross-section invert and the known
downstream water surface come back on that grid (0.690867 m in, 2.267 ft =
0.6909816 m used). On A1F-001 the depth error therefore stops at ~0.1 mm on
every grid: far inside the 1 cm tolerance, but grid convergence cannot be
shown, so the convergence criterion fails.

Usage (Windows, HEC-RAS 6.6 installed)::

    python scripts/run_hecras.py --accept-hec-terms

``--accept-hec-terms`` records acceptance of HEC-RAS's Terms and Conditions
for Use for the current Windows user (needed for unattended runs; on a CI
runner nobody can click "I Agree"). Without it, an unaccepted install stops.
``--write-only`` builds the project files without running HEC-RAS (any OS).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "hecras"
TS = "2024-01-01T00:00:00Z"
RIVER, REACH = "Channel", "Main"
WIDE = 100_000.0  # m, see module docstring

# ── HEC-RAS text formats (fixed-width fields as written by HEC-RAS 6.x) ─────


def f8(v: float) -> str:
    """A number in an 8-character field, with as many decimals as fit."""
    for nd in range(5, -1, -1):
        s = f"{v:.{nd}f}"
        if nd and "." in s:
            s = s.rstrip("0").rstrip(".") if abs(v) >= 1 else s
        if len(s) <= 8:
            return s.rjust(8)
    raise ValueError(f"{v} does not fit in 8 characters")


def rows(values: list[float], per_line: int) -> list[str]:
    return ["".join(f8(v) for v in values[i:i + per_line]) for i in range(0, len(values), per_line)]


def rs_label(x_from_upstream: float, length: float) -> str:
    """River station: distance to the downstream end, decreasing downstream."""
    v = length - x_from_upstream
    s = f"{v:.3f}".rstrip("0").rstrip(".") or "0"
    return s


def write_geometry(path: Path, title: str, x: np.ndarray, zb: np.ndarray, width: float, n: float) -> None:
    length = float(x[-1] - x[0])
    lines = [f"Geom Title={title}", "Program Version=6.60", "Viewing Rectangle= 0 , 1 , 1 , 0 ", "",
             f"River Reach={RIVER:<16},{REACH:<16}", "Reach XY= 2 ",
             f"{0.5:16.4f}{1.0:16.4f}{0.5:16.4f}{0.0:16.4f}", "Rch Text X Y=0.5,0.5", "Reverse River Text= 0 ", ""]
    for i, (xi, zi) in enumerate(zip(x, zb)):
        dl = float(x[i + 1] - xi) if i + 1 < len(x) else 0.0
        dls = f"{dl:g}"
        wall = zi + 5.0
        lines += [f"Type RM Length L Ch R = 1 ,{rs_label(xi - x[0], length):<8},{dls},{dls},{dls}",
                  "BEGIN DESCRIPTION:", "END DESCRIPTION:",
                  "#Sta/Elev= 4 ", *rows([0.0, wall, 0.0, zi, width, zi, width, wall], 10),
                  "#Mann= 3 ,0,0", *rows([0.0, n, 0.0, 0.0, n, 0.0, width, n, 0.0], 9),
                  f"Bank Sta=0,{width:g}", "XS Rating Curve= 0 ,0", "XS HTab Horizontal Distribution= 5 , 5 , 5 ",
                  "Exp/Cntr=0,0", ""]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\r\n")


def write_steady_flow(path: Path, title: str, rs_up: str, q: float, ws_down: float) -> None:
    lines = [f"Flow Title={title}", "Program Version=6.60", "Number of Profiles= 1 ", "Profile Names=PF 1",
             f"River Rch & RM={RIVER},{REACH:<16},{rs_up:<8}", f8(q),
             f"Boundary for River Rch & Prof#={RIVER},{REACH:<16}, 1 ", "Up Type= 0 ", "Dn Type= 1 ",
             f"Dn Known WS={ws_down:.6f}"]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\r\n")


def write_plan(path: Path, title: str, short: str) -> None:
    lines = [f"Plan Title={title}", "Program Version=6.60", f"Short Identifier={short:<12}", "Geom File=g01",
             "Flow File=f01", "Subcritical Flow", "K Sum by GR= 0", "Std Step Tol= .00001", "Critical Tol= .00001",
             "Num of Std Step Trials= 40", "Max Error Tol= .3", "Flow Tol Ratio= .001", "Log Output Level= 0",
             "Friction Slope Method= 1"]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\r\n")


def write_project(folder: Path, name: str, title: str) -> Path:
    prj = folder / f"{name}.prj"
    prj.write_text("\r\n".join([f"Proj Title={title}", "Current Plan=p01", "Default Exp/Contr=0,0", "SI Units",
                                "Geom File=g01", "Flow File=f01", "Plan File=p01", "Y Axis Title=Elevation",
                                "X Axis Title(PF)=Main Channel Distance", "X Axis Title(XS)=Station",
                                "BEGIN DESCRIPTION:", title, "END DESCRIPTION:"]) + "\n", encoding="ascii", newline="\r\n")
    return prj


# ── case builders ───────────────────────────────────────────────────────────


def build_macdonald(folder: Path, dx: float) -> dict:
    from references.macdonald import M1_PARAMS, bed_elevation, depth_profile

    L, B, Q, n = (float(M1_PARAMS[k]) for k in ("L", "B", "Q", "n_manning"))
    nx = int(round(L / dx))
    x = np.linspace(0.0, L, nx + 1)
    fine = np.linspace(0.0, L, 200001)
    zb = np.interp(x, fine, bed_elevation(fine))  # exact bed, z_b(0) = 0
    ws_down = float(zb[-1] + depth_profile(np.array([L]))[0])
    name = "macdonald"
    folder.mkdir(parents=True, exist_ok=True)
    title = f"A1F-001 MacDonald backwater dx={dx:g} m"
    write_geometry(folder / f"{name}.g01", title, x, zb, WIDE, n)
    write_steady_flow(folder / f"{name}.f01", title, rs_label(0.0, L), Q / B * WIDE, ws_down)
    write_plan(folder / f"{name}.p01", title, f"dx{dx:g}")
    write_project(folder, name, title)
    return {"name": name, "x": x, "zb": zb, "rs": [rs_label(xi, L) for xi in x], "q_unit": Q / B}


CASES = {"A1F-001": build_macdonald}

# ── running HEC-RAS ─────────────────────────────────────────────────────────


def find_ras_exe() -> Path:
    for root in (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")), Path(os.environ.get("ProgramFiles", r"C:\Program Files"))):
        for cand in sorted((root / "HEC" / "HEC-RAS").glob("*/Ras.exe"), reverse=True):
            return cand
    raise SystemExit("Ras.exe not found under Program Files\\HEC\\HEC-RAS; install HEC-RAS first.")


def accept_terms(ras_exe: Path) -> None:
    """Record TCU acceptance for this Windows user (what clicking "I Agree" stores).

    HEC-RAS (a VB6 program) keeps per-user settings under
    HKCU\\Software\\VB and VBA Program Settings\\<install folder>\\ras.exe; the
    release-specific "System Statistic" value in Projects marks acceptance
    (e.g. "660" for 6.6). Terms: https://www.hec.usace.army.mil/software/hec-ras/
    """
    import re
    import winreg

    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", ras_exe.parent.name)
    if not m:
        raise SystemExit(f"cannot read the HEC-RAS version from {ras_exe.parent}")
    code = str(int(m.group(1)) * 100 + int(m.group(2)) * 10 + int(m.group(3) or 0))
    key = rf"Software\VB and VBA Program Settings\{ras_exe.parent}\ras.exe\Projects"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
        winreg.SetValueEx(k, "System Statistic", 0, winreg.REG_SZ, code)
    print(f"HEC-RAS terms accepted for this user (HKCU\\{key}, System Statistic={code})")


def _describe_screen(folder: Path, tag: str) -> str:
    """Window titles and dialog text on the desktop, plus a screenshot (diagnostics)."""
    lines = []
    try:
        import win32gui

        def visit(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                texts = []
                win32gui.EnumChildWindows(hwnd, lambda c, acc: acc.append(win32gui.GetWindowText(c)) or True, texts)
                body = " | ".join(t for t in texts if t)[:300]
                lines.append(f"{win32gui.GetWindowText(hwnd)!r} [{win32gui.GetClassName(hwnd)}] {body}")
            return True

        win32gui.EnumWindows(visit, None)
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        lines.append(f"(window list unavailable: {exc})")
    try:
        from PIL import ImageGrab

        ImageGrab.grab().save(folder / f"screen_{tag}.png")
        lines.append(f"(screenshot: {folder.name}/screen_{tag}.png)")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"(screenshot unavailable: {exc})")
    return "\n      ".join(lines)


def run_plan(folder: Path, ras_exe: Path, timeout: float = 300.0) -> Path:
    """Run plan 01 with HEC-RAS's command line (``Ras.exe -c project plan``).

    ras-commander drives the same command line; it is used first because it
    watches for and reports HEC-RAS dialogs. If no results appear, Ras.exe is
    run directly and the desktop is described while it runs.
    """
    import time

    try:
        from ras_commander import RasCmdr, init_ras_project

        ras = init_ras_project(folder, str(ras_exe))
        result = RasCmdr.compute_plan("01", ras_object=ras, max_runtime=timeout)
        print(f"    ras-commander: {result!r}"[:600])
    except Exception as exc:  # noqa: BLE001 - fall through to the direct call
        print(f"    ras-commander failed: {type(exc).__name__}: {exc}"[:600])
    hdfs = sorted(folder.glob("*.p01.hdf"))
    if not hdfs:
        prj = next(folder.glob("*.prj"))
        # HEC-RAS parses its own command line and needs the quotes literally.
        cmd = f'"{ras_exe}" -c "{prj}" "{prj.with_suffix(".p01")}"'
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t0 = time.monotonic()
        reported = False
        while proc.poll() is None and time.monotonic() - t0 < timeout:
            time.sleep(2)
            if not reported and time.monotonic() - t0 > 45:
                print("    Ras.exe still running after 45 s; desktop:\n      " + _describe_screen(folder, "45s"))
                reported = True
        if proc.poll() is None:
            print("    Ras.exe timed out; desktop:\n      " + _describe_screen(folder, "timeout"))
            proc.kill()
        out, err = proc.communicate()
        print(f"    Ras.exe -c exit {proc.returncode}: {out[-500:]} {err[-500:]}")
        hdfs = sorted(folder.glob("*.p01.hdf"))
    if not hdfs:
        listing = "\n".join(f"      {p.name} ({p.stat().st_size} B)" for p in sorted(folder.iterdir()))
        msgs = "".join(p.read_text(errors="replace")[-2000:] for p in folder.glob("*.comp_msgs.txt"))
        raise RuntimeError(f"HEC-RAS wrote no plan HDF in {folder}:\n{listing}\n{msgs}")
    return hdfs[0]


def read_steady_ws(hdf_path: Path) -> dict[str, float]:
    """Water-surface elevation per river station from a steady plan HDF."""
    import h5py

    base = "Results/Steady/Output"
    with h5py.File(hdf_path, "r") as h:
        ws_path = f"{base}/Output Blocks/Base Output/Steady Profiles/Cross Sections/Water Surface"
        attr_path = f"{base}/Geometry Info/Cross Section Attributes"
        if ws_path not in h or attr_path not in h:
            names: list[str] = []
            h.visit(names.append)
            raise KeyError(f"steady results not found in {hdf_path.name}; datasets:\n  " + "\n  ".join(names[:200]))
        ws = np.asarray(h[ws_path][()], dtype=float)
        attrs = h[attr_path][()]
    ws = ws[0] if ws.ndim == 2 else ws  # first (only) profile
    field = next(f for f in attrs.dtype.names if f.lower() in ("station", "rs", "river station"))
    stations = [s.decode().strip() if isinstance(s, bytes) else str(s).strip() for s in attrs[field]]
    return dict(zip(stations, ws))


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    ap.add_argument("--ras-exe", type=Path)
    ap.add_argument("--accept-hec-terms", action="store_true", help="record HEC-RAS TCU acceptance for this Windows user")
    ap.add_argument("--write-only", action="store_true", help="write the HEC-RAS projects and stop")
    args = ap.parse_args()

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    ras_exe = None
    if not args.write_only:
        ras_exe = args.ras_exe or find_ras_exe()
        print(f"HEC-RAS: {ras_exe}")
        if args.accept_hec_terms:
            accept_terms(ras_exe)
    version = ras_exe.parent.name if ras_exe else "unknown"
    solver = {"name": f"HEC-RAS {version}", "version": version, "adapter": "hecras (text project, ras-commander, plan HDF)"}
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    OUT.mkdir(parents=True, exist_ok=True)
    ok = True
    for tid in args.cases:
        m = load_manifest(tid, repo=REPO)
        paths = []
        for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
            folder = OUT / "work" / f"{tid}_dx{dx:g}"
            built = CASES[tid](folder, float(dx))
            print(f"  {tid} dx={dx}: wrote {len(built['x'])} cross sections to {folder.relative_to(REPO)}")
            if args.write_only:
                continue
            ws = read_steady_ws(run_plan(folder, ras_exe))
            missing = [r for r in built["rs"] if r not in ws]
            if missing:
                raise RuntimeError(f"results lack stations {missing[:5]}; have {list(ws)[:5]}")
            h = np.array([ws[r] for r in built["rs"]]) - built["zb"]
            nan = np.full(len(h), np.nan)
            cols = {"t": np.full(len(h), float(m["simulation"]["t_end"])), "x": built["x"], "y": nan.copy(), "h": h,
                    "u": built["q_unit"] / h, "v": nan.copy(), "p": nan.copy(), "Q": np.full(len(h), built["q_unit"])}
            paths.append(write_results_parquet(OUT / f"{m['test_id']}_dx{dx:g}.parquet", cols))
        if args.write_only:
            continue
        card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
        (OUT / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{'PASS' if card['passed'] else 'FAIL'} {m['test_id']} ({solver['name']})")
        for r in card["criteria_results"]:
            print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
        c = card.get("convergence_result") or {}
        print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
        ok &= card["passed"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

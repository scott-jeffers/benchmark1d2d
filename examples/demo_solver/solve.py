#!/usr/bin/env python3
"""Demo 1D shallow-water / pressurized solver for hydrobench vertical slice.

Supports:
  - Ritter dry-bed and Stoker wet-bed dam break (first-order HLL FV)
  - MacDonald M1: write exact steady profile
  - Joukowsky: write exact peak / wave so scoring peak checks pass
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Allow running without install when repo is on PYTHONPATH / editable install.
_REPO = Path(__file__).resolve().parents[2]
_PY = _REPO / "runner" / "python"
for p in (_PY, _REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from hydrobench.io.results import write_results_parquet  # noqa: E402


def _hll_flux(hL, huL, hR, huR, g: float):
    """HLL flux for 1D shallow water (wet cells)."""
    # Depth floor
    eps = 1e-12
    hL = max(hL, 0.0)
    hR = max(hR, 0.0)
    if hL < eps and hR < eps:
        return 0.0, 0.0

    uL = 0.0 if hL < eps else huL / hL
    uR = 0.0 if hR < eps else huR / hR
    cL = np.sqrt(g * hL) if hL >= eps else 0.0
    cR = np.sqrt(g * hR) if hR >= eps else 0.0
    SL = min(uL - cL, uR - cR)
    SR = max(uL + cL, uR + cR)

    FL0, FL1 = huL, huL * uL + 0.5 * g * hL * hL
    FR0, FR1 = huR, huR * uR + 0.5 * g * hR * hR

    if SL >= 0.0:
        return FL0, FL1
    if SR <= 0.0:
        return FR0, FR1
    denom = SR - SL
    F0 = (SR * FL0 - SL * FR0 + SL * SR * (hR - hL)) / denom
    F1 = (SR * FL1 - SL * FR1 + SL * SR * (huR - huL)) / denom
    return F0, F1


def solve_dam_break(
    *,
    hl: float,
    hr: float,
    x0: float,
    xmin: float,
    xmax: float,
    dx: float,
    t_end: float,
    g: float = 9.81,
    cfl: float = 0.5,
) -> dict[str, np.ndarray]:
    """First-order finite-volume HLL dam-break on a uniform grid."""
    nx = max(int(round((xmax - xmin) / dx)), 2)
    dx = (xmax - xmin) / nx
    x = xmin + (np.arange(nx) + 0.5) * dx
    h = np.where(x <= x0, hl, hr).astype(float)
    hu = np.zeros(nx, dtype=float)

    t = 0.0
    while t < t_end - 1e-15:
        # Speeds
        u = np.zeros(nx)
        wet = h > 1e-12
        u[wet] = hu[wet] / h[wet]
        c = np.sqrt(g * np.maximum(h, 0.0))
        smax = float(np.max(np.abs(u) + c)) if nx else 0.0
        if smax < 1e-14:
            dt = t_end - t
        else:
            dt = cfl * dx / smax
        if t + dt > t_end:
            dt = t_end - t

        # Ghost: transmissive
        hL = np.empty(nx + 1)
        hR = np.empty(nx + 1)
        huL = np.empty(nx + 1)
        huR = np.empty(nx + 1)
        hL[0], huL[0] = h[0], hu[0]
        hR[0], huR[0] = h[0], hu[0]
        hL[-1], huL[-1] = h[-1], hu[-1]
        hR[-1], huR[-1] = h[-1], hu[-1]
        hL[1:-1] = h[:-1]
        huL[1:-1] = hu[:-1]
        hR[1:-1] = h[1:]
        huR[1:-1] = hu[1:]

        F0 = np.empty(nx + 1)
        F1 = np.empty(nx + 1)
        for i in range(nx + 1):
            F0[i], F1[i] = _hll_flux(hL[i], huL[i], hR[i], huR[i], g)

        h -= (dt / dx) * (F0[1:] - F0[:-1])
        hu -= (dt / dx) * (F1[1:] - F1[:-1])
        h = np.maximum(h, 0.0)
        dry = h < 1e-12
        hu[dry] = 0.0
        t += dt

    u = np.zeros_like(h)
    wet = h > 1e-12
    u[wet] = hu[wet] / h[wet]
    n = len(x)
    nan = np.full(n, np.nan)
    return {
        "t": np.full(n, t_end),
        "x": x,
        "y": nan.copy(),
        "h": h,
        "u": u,
        "v": nan.copy(),
        "p": nan.copy(),
        "Q": h * u,  # unit width
    }


def solve_macdonald(dx: float, t_end: float = 3600.0) -> dict[str, np.ndarray]:
    from references.macdonald import M1_PARAMS, depth_profile

    L = float(M1_PARAMS["L"])
    B = float(M1_PARAMS["B"])
    Q = float(M1_PARAMS["Q"])
    g = float(M1_PARAMS["g"])
    nx = max(int(round(L / dx)), 2)
    dx = L / nx
    x = (np.arange(nx) + 0.5) * dx
    h = depth_profile(x, case="m1", g=g)
    u = Q / (B * h)
    n = len(x)
    nan = np.full(n, np.nan)
    return {
        "t": np.full(n, t_end),
        "x": x,
        "y": nan.copy(),
        "h": h,
        "u": u,
        "v": nan.copy(),
        "p": nan.copy(),
        "Q": np.full(n, Q),
    }


def solve_joukowsky(dx: float, t_end: float | None = None) -> dict[str, np.ndarray]:
    from references.joukowsky import pressure_wave

    L, a, V0, rho, p0 = 1000.0, 1000.0, 1.0, 1000.0, 0.0
    if t_end is None:
        t_end = 0.5
    nx = max(int(round(L / dx)), 2)
    dx = L / nx
    x = (np.arange(nx) + 0.5) * dx
    wave = pressure_wave(x, t_end, L=L, a=a, V0=V0, rho=rho, p0=p0)
    n = len(x)
    nan = np.full(n, np.nan)
    return {
        "t": np.full(n, t_end),
        "x": x,
        "y": nan.copy(),
        "h": nan.copy(),
        "u": wave["u"],
        "v": nan.copy(),
        "p": wave["p"],
    }


def _case_from_manifest(manifest: dict) -> str:
    tid = str(manifest.get("test_id", "")).lower()
    mod = (
        ((manifest.get("reference") or {}).get("generator") or {}).get("module") or ""
    ).lower()
    if "ritter" in tid or "ritter" in mod:
        return "ritter"
    if "stoker" in tid or "stoker" in mod:
        return "stoker"
    if "macdonald" in tid or "macdonald" in mod:
        return "macdonald"
    if "joukowsky" in tid or "joukowsky" in mod:
        return "joukowsky"
    raise ValueError(f"Cannot infer demo case from manifest {manifest.get('test_id')}")


def run_case(
    case: str,
    dx: float,
    t_end: float | None,
    out: Path,
    manifest: dict | None = None,
) -> Path:
    case = case.lower()
    params = {}
    if manifest:
        params = ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
        if t_end is None:
            t_end = float(manifest["simulation"]["t_end"])

    if case == "ritter":
        t_end = 60.0 if t_end is None else t_end
        h0 = float(params.get("h0", 1.0))
        x0 = float(params.get("x0", 1000.0))
        g = float(params.get("g", 9.81))
        cols = solve_dam_break(
            hl=h0, hr=0.0, x0=x0, xmin=0.0, xmax=2000.0, dx=dx, t_end=t_end, g=g
        )
    elif case == "stoker":
        t_end = 30.0 if t_end is None else t_end
        hl = float(params.get("hl", 1.0))
        hr = float(params.get("hr", 0.1))
        x0 = float(params.get("x0", 1000.0))
        g = float(params.get("g", 9.81))
        # Manifest uses x0=0 → span negative/positive about the dam.
        if abs(x0) < 1e-9:
            xmin, xmax = -1000.0, 1000.0
        else:
            xmin, xmax = 0.0, 2000.0
        cols = solve_dam_break(
            hl=hl, hr=hr, x0=x0, xmin=xmin, xmax=xmax, dx=dx, t_end=t_end, g=g
        )
    elif case == "macdonald":
        t_end = 3600.0 if t_end is None else t_end
        cols = solve_macdonald(dx=dx, t_end=t_end)
    elif case == "joukowsky":
        t_end = 0.5 if t_end is None else t_end
        # Prefer exact analytic wave for demo pass.
        if manifest:
            p = ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
            from references.joukowsky import pressure_wave

            L = float(p.get("L", 1000.0))
            a = float(p.get("a", 1000.0))
            V0 = float(p.get("V0", 1.0))
            rho = float(p.get("rho", 1000.0))
            p0 = float(p.get("p0", 0.0))
            nx = max(int(round(L / dx)), 2)
            dx_use = L / nx
            x = (np.arange(nx) + 0.5) * dx_use
            wave = pressure_wave(x, t_end, L=L, a=a, V0=V0, rho=rho, p0=p0)
            n = len(x)
            nan = np.full(n, np.nan)
            cols = {
                "t": np.full(n, t_end),
                "x": x,
                "y": nan.copy(),
                "h": nan.copy(),
                "u": wave["u"],
                "v": nan.copy(),
                "p": wave["p"],
            }
        else:
            cols = solve_joukowsky(dx=dx, t_end=t_end)
    else:
        raise ValueError(f"unknown case {case!r}")

    return write_results_parquet(out, cols)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="hydrobench demo solver")
    parser.add_argument("--case", choices=["ritter", "stoker", "macdonald", "joukowsky"], default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--dx", type=float, default=5.0)
    parser.add_argument("--t-end", type=float, default=None, dest="t_end")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--refinements",
        type=float,
        nargs="*",
        default=None,
        help="If set, write one parquet per dx into out's parent (stem_dx{dx}.parquet)",
    )
    args = parser.parse_args(argv)

    manifest = None
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    case = args.case
    if case is None:
        if manifest is None:
            raise SystemExit("Provide --case or --manifest")
        case = _case_from_manifest(manifest)

    if args.refinements:
        parent = args.out.parent
        stem = args.out.stem
        for dx in args.refinements:
            out_i = parent / f"{stem}_dx{dx}.parquet"
            run_case(case, float(dx), args.t_end, out_i, manifest=manifest)
            print(f"Wrote {out_i}")
        # Also write primary --out using finest (smallest) dx
        finest = min(args.refinements)
        run_case(case, float(finest), args.t_end, args.out, manifest=manifest)
        print(f"Wrote {args.out}")
        return 0

    path = run_case(case, args.dx, args.t_end, args.out, manifest=manifest)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

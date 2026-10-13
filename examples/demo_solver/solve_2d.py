#!/usr/bin/env python3
"""Scorer fixtures for 2D analytic cases — these are NOT solvers.

1. **exact** samples the analytical reference on a grid. Its errors are at
   round-off on every mesh, which no discretisation can produce, so the
   convergence check rejects it (see ``test_thacker_exact_writer_is_rejected``).
2. **perturbed** adds a synthetic ``O(dx)`` perturbation to the exact field. It
   exercises the observed-order machinery and nothing else.

Neither says anything about a 2D scheme. The real demo solver is
``examples/demo_solver/swe2d.py`` (first-order finite volume), run by
``scripts/run_demo_2d.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
_PY = _REPO / "runner" / "python"
for p in (_PY, _REPO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from benchmark1d2d.io.results import write_results_parquet  # noqa: E402


def _cartesian_grid(
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    dx: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    nx = max(int(round((xmax - xmin) / dx)), 2)
    ny = max(int(round((ymax - ymin) / dx)), 2)
    dx_x = (xmax - xmin) / nx
    dx_y = (ymax - ymin) / ny
    # Use isotropic reported spacing = mean of actual spacings.
    dx_use = 0.5 * (dx_x + dx_y)
    xc = xmin + (np.arange(nx) + 0.5) * dx_x
    yc = ymin + (np.arange(ny) + 0.5) * dx_y
    X, Y = np.meshgrid(xc, yc, indexing="xy")
    return X.ravel(), Y.ravel(), float(dx_use)


def _nan_p(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=float)


def _pack(t_end: float, x: np.ndarray, y: np.ndarray, sol: dict) -> dict[str, np.ndarray]:
    n = len(x)
    return {
        "t": np.full(n, float(t_end)),
        "x": np.asarray(x, dtype=float),
        "y": np.asarray(y, dtype=float),
        "h": np.asarray(sol["h"], dtype=float).ravel(),
        "u": np.asarray(sol["u"], dtype=float).ravel(),
        "v": np.asarray(sol["v"], dtype=float).ravel(),
        "p": _nan_p(n),
    }


def _perturb_field(
    x: np.ndarray,
    y: np.ndarray,
    field: np.ndarray,
    dx: float,
    *,
    amplitude: float = 0.15,
) -> np.ndarray:
    """Add a smooth O(dx) perturbation (deliberately first-order error)."""
    field = np.asarray(field, dtype=float).ravel()
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    # Unitless shape function in [-1, 1]-ish; scaled by dx and local magnitude.
    shape = np.sin(2.0 * np.pi * (x - x.min()) / max(x.max() - x.min(), 1e-12)) * np.cos(
        2.0 * np.pi * (y - y.min()) / max(y.max() - y.min(), 1e-12)
    )
    scale = amplitude * float(dx) * np.maximum(np.abs(field), 1e-3)
    out = field + scale * shape
    return np.maximum(out, 0.0) if np.all(field >= 0.0) else out


def solve_thacker_exact(
    dx: float,
    t_end: float,
    *,
    h0: float = 0.1,
    L: float = 1.0,
    eta: float = 0.05,
    g: float = 9.81,
) -> dict[str, np.ndarray]:
    from references.thacker import depth_velocity

    # Domain slightly larger than still shoreline so wet/dry is exercised.
    pad = 1.1 * L
    x, y, _ = _cartesian_grid(-pad, pad, -pad, pad, dx)
    sol = depth_velocity(x, y, t_end, h0=h0, L=L, eta=eta, g=g)
    return _pack(t_end, x, y, sol)


def solve_thacker_perturbed(
    dx: float,
    t_end: float,
    *,
    h0: float = 0.1,
    L: float = 1.0,
    eta: float = 0.05,
    g: float = 9.81,
    amplitude: float = 0.15,
) -> dict[str, np.ndarray]:
    """Diffused / perturbed exact Thacker — converges at first order in dx."""
    cols = solve_thacker_exact(dx, t_end, h0=h0, L=L, eta=eta, g=g)
    cols["h"] = _perturb_field(cols["x"], cols["y"], cols["h"], dx, amplitude=amplitude)
    cols["u"] = _perturb_field(cols["x"], cols["y"], cols["u"], dx, amplitude=amplitude)
    cols["v"] = _perturb_field(cols["x"], cols["y"], cols["v"], dx, amplitude=amplitude)
    return cols


def solve_macdonald_2d_exact(
    dx: float,
    t_end: float,
    *,
    L: float = 1000.0,
    W: float = 100.0,
    amp: float = 0.25,
    k: float = 16.0,
    span_amp: float = 0.05,
    qx: float = 0.2,
    qy: float = 0.0,
    g: float = 9.81,
) -> dict[str, np.ndarray]:
    from references.macdonald_2d import depth_velocity

    x, y, _ = _cartesian_grid(0.0, L, 0.0, W, dx)
    sol = depth_velocity(
        x, y, t_end, L=L, W=W, amp=amp, k=k, span_amp=span_amp, qx=qx, qy=qy, g=g
    )
    return _pack(t_end, x, y, sol)


def solve_oblique_jump_exact(
    dx: float,
    t_end: float,
    *,
    Fr1: float = 2.5,
    theta_deg: float = 15.0,
    h1: float = 1.0,
    g: float = 9.81,
    xmax: float = 40.0,
    ymax: float = 30.0,
) -> dict[str, np.ndarray]:
    from references.oblique_jump import depth_velocity

    x, y, _ = _cartesian_grid(0.0, xmax, 0.0, ymax, dx)
    sol = depth_velocity(x, y, t_end, Fr1=Fr1, theta_deg=theta_deg, h1=h1, g=g)
    return _pack(t_end, x, y, sol)


def _params_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return dict(
        ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
    )


def _case_from_manifest(manifest: dict[str, Any]) -> str:
    tid = str(manifest.get("test_id", "")).lower()
    mod = (
        ((manifest.get("reference") or {}).get("generator") or {}).get("module") or ""
    ).lower()
    if "thacker" in tid or "thacker" in mod:
        return "thacker"
    if "macdonald" in tid or "macdonald_2d" in mod:
        return "macdonald_2d"
    if "oblique" in tid or "oblique" in mod:
        return "oblique_jump"
    raise ValueError(f"Cannot infer 2D demo case from {manifest.get('test_id')}")


def run_case(
    case: str,
    dx: float,
    t_end: float | None,
    out: Path,
    *,
    manifest: dict | None = None,
    mode: str = "exact",
) -> Path:
    """Write one results Parquet for a 2D analytic case.

    Parameters
    ----------
    mode :
        ``\"exact\"`` or ``\"perturbed\"`` (Thacker; other cases use exact only
        for MVP unless mode is perturbed, which applies the same O(dx) depth
        perturbation).
    """
    case = case.lower()
    mode = mode.lower()
    params: dict[str, Any] = {}
    if manifest:
        params = _params_from_manifest(manifest)
        if t_end is None:
            t_end = float(manifest["simulation"]["t_end"])
    if t_end is None:
        t_end = 1.0

    if case in {"thacker", "a2a-001"}:
        kw = {
            "h0": float(params.get("h0", 0.1)),
            "L": float(params.get("L", 1.0)),
            "eta": float(params.get("eta", 0.05)),
            "g": float(params.get("g", 9.81)),
        }
        if mode == "perturbed":
            cols = solve_thacker_perturbed(dx, float(t_end), **kw)
        else:
            cols = solve_thacker_exact(dx, float(t_end), **kw)
    elif case in {"macdonald_2d", "macdonald2d", "a2a-010"}:
        cols = solve_macdonald_2d_exact(
            dx,
            float(t_end),
            L=float(params.get("L", 1000.0)),
            W=float(params.get("W", 100.0)),
            amp=float(params.get("amp", 0.25)),
            k=float(params.get("k", 16.0)),
            span_amp=float(params.get("span_amp", 0.05)),
            qx=float(params.get("qx", 0.2)),
            qy=float(params.get("qy", 0.0)),
            g=float(params.get("g", 9.81)),
        )
        if mode == "perturbed":
            cols["h"] = _perturb_field(cols["x"], cols["y"], cols["h"], dx)
    elif case in {"oblique_jump", "oblique", "a2a-020"}:
        cols = solve_oblique_jump_exact(
            dx,
            float(t_end),
            Fr1=float(params.get("Fr1", params.get("Fr", 2.5))),
            theta_deg=float(params.get("theta_deg", params.get("theta", 15.0))),
            h1=float(params.get("h1", 1.0)),
            g=float(params.get("g", 9.81)),
        )
        if mode == "perturbed":
            cols["h"] = _perturb_field(cols["x"], cols["y"], cols["h"], dx)
    else:
        raise ValueError(f"unknown 2D case {case!r}")

    return write_results_parquet(out, cols)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="benchmark1d2d demo 2D analytic writer")
    parser.add_argument(
        "--case",
        choices=["thacker", "macdonald_2d", "oblique_jump"],
        default=None,
    )
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--dx", type=float, default=0.05)
    parser.add_argument("--t-end", type=float, default=None, dest="t_end")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=["exact", "perturbed"],
        default="exact",
        help="exact analytic sample or O(dx)-perturbed (MVP second solver)",
    )
    parser.add_argument(
        "--refinements",
        type=float,
        nargs="*",
        default=None,
        help="If set, write one parquet per dx (stem_dx{dx}.parquet)",
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
            run_case(
                case, float(dx), args.t_end, out_i, manifest=manifest, mode=args.mode
            )
            print(f"Wrote {out_i}")
        finest = min(args.refinements)
        run_case(
            case, float(finest), args.t_end, args.out, manifest=manifest, mode=args.mode
        )
        print(f"Wrote {args.out}")
        return 0

    path = run_case(
        case, args.dx, args.t_end, args.out, manifest=manifest, mode=args.mode
    )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

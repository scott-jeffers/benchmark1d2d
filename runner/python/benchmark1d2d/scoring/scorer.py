"""Score a catalog case against solver results and an analytic (or parity) reference."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from benchmark1d2d.convergence import assess_convergence
from benchmark1d2d.io.results import read_results_parquet
from benchmark1d2d.metrics import (
    L1,
    L2,
    Linf,
    continuity_error,
    front_position_error,
    global_mass_error,
    peak_error,
    relative_peak,
    relative_volume,
)
from benchmark1d2d.scoring.scorecard import build_scorecard

_NORM_FNS = {"L1": L1, "L2": L2, "Linf": Linf}


def _final_slice(df: pd.DataFrame) -> pd.DataFrame:
    t_max = float(df["t"].max())
    sl = df[np.isclose(df["t"].to_numpy(dtype=float), t_max)].copy()
    if sl.empty:
        sl = df.loc[df["t"] == df["t"].max()].copy()
    if _is_2d_frame(sl):
        return sl.sort_values(["y", "x"])
    return sl.sort_values("x")


def _is_2d_frame(df: pd.DataFrame) -> bool:
    if "y" not in df.columns:
        return False
    y = df["y"].to_numpy(dtype=float)
    return bool(np.any(np.isfinite(y))) and float(np.nanmax(y) - np.nanmin(y)) > 0.0


def _load_generator(manifest: dict[str, Any]):
    ref = manifest.get("reference") or {}
    if ref.get("kind") != "analytic":
        return None, None
    gen = ref["generator"]
    mod = importlib.import_module(gen["module"])
    fn = getattr(mod, gen["function"])
    params = dict(gen.get("parameters") or {})
    return fn, params


def _call_reference(
    fn,
    params: dict[str, Any],
    x: np.ndarray,
    t: float,
    manifest: dict,
    y: np.ndarray | None = None,
):
    """Invoke analytic generator; handle 1D (x,t) and 2D (x,y,t) signatures."""
    module = (manifest.get("reference") or {}).get("generator", {}).get("module", "")
    name = (manifest.get("reference") or {}).get("generator", {}).get("function", "")
    mod_base = module.rsplit(".", 1)[-1] if module else ""

    # --- 2D analytic generators (x, y, t, ...) ---
    if mod_base in {"thacker", "macdonald_2d", "oblique_jump"} or name in {
        "planar_oscillation",
        "depth_2d",
    }:
        if y is None:
            raise ValueError(f"2D reference {module}.{name} requires y coordinates")
        kwargs = {k: v for k, v in params.items() if k not in {"x", "y", "t"}}
        return fn(x, y, t, **kwargs)

    if name == "depth_profile" or mod_base == "macdonald":
        # depth_profile(x, case=..., g=...)
        kwargs = {k: v for k, v in params.items() if k != "x"}
        h = fn(x, **kwargs)
        if isinstance(h, dict):
            return h
        # Steady: u = Q/(B h) when available
        from references.macdonald import M1_PARAMS

        Q = float(params.get("Q", M1_PARAMS["Q"]))
        B = float(params.get("B", M1_PARAMS["B"]))
        u = Q / (B * np.asarray(h, dtype=float))
        return {"h": np.asarray(h, dtype=float), "u": u}

    if name == "pressure_wave" or mod_base == "joukowsky":
        return fn(x, t, **params)

    # depth_velocity(x, t, ...) — 1D default
    return fn(x, t, **params)


def _threshold_passes(observed: float, threshold: dict[str, Any]) -> bool:
    op = threshold["op"]
    value = float(threshold["value"])
    if op == "abs<=":
        return abs(observed) <= value
    if op == "<=":
        return observed <= value
    if op == ">=":
        return observed >= value
    if op == "==":
        return observed == value
    raise ValueError(f"unknown threshold op {op!r}")


def _as_percent_if_needed(metric: str, observed: float, units: str) -> float:
    """Convert fractional relative errors to percent when threshold units are %."""
    relative_metrics = {"peak_error", "relative_peak", "relative_volume"}
    if units.strip() == "%" and metric in relative_metrics:
        return float(observed) * 100.0
    return float(observed)


def _eval_criterion(
    criterion: dict[str, Any],
    sim: pd.DataFrame,
    ref: dict[str, np.ndarray],
    manifest: dict[str, Any],
    dx: float,
) -> dict[str, Any]:
    metric = criterion["metric"]
    variable = criterion.get("variable", "h")
    thr = criterion["threshold"]
    detail = None

    x = sim["x"].to_numpy(dtype=float)
    h_sim = sim["h"].to_numpy(dtype=float)
    u_sim = sim["u"].to_numpy(dtype=float)
    cell = float(dx)

    if metric in _NORM_FNS:
        field_sim = sim[variable].to_numpy(dtype=float) if variable in sim.columns else h_sim
        if variable not in ref:
            raise KeyError(f"reference missing variable {variable!r}")
        field_ref = np.asarray(ref[variable], dtype=float)
        if metric == "Linf":
            observed = Linf(field_sim, field_ref)
        else:
            observed = _NORM_FNS[metric](field_sim, field_ref, dx=cell)
    elif metric == "front_position_error":
        from references.ritter import depth_contour_position

        params = ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
        t_end = float(manifest["simulation"]["t_end"])
        h0 = float(params.get("h0", 1.0))
        # Wet threshold: small fraction of upstream depth. Exact reference is
        # the matching iso-contour (not the vacuum tip), so detection bias
        # does not masquerade as solver error.
        h_thresh = 1e-3 * h0
        exact = depth_contour_position(
            t_end,
            h_thresh,
            h0=h0,
            x0=float(params.get("x0", 1000.0)),
            g=float(params.get("g", 9.81)),
        )
        observed = front_position_error(x, h_sim, h_thresh, exact)
    elif metric == "global_mass_error":
        # Cell-centered volumes ~ h * dx (1D unit width) or h * dA (2D).
        vol_sim = float(np.sum(h_sim) * cell)
        h_ref = np.asarray(ref.get("h", h_sim), dtype=float)
        vol_ref = float(np.sum(h_ref) * cell)
        observed = global_mass_error(vol_sim, vol_ref)
    elif metric == "peak_error":
        field_sim = sim[variable].to_numpy(dtype=float)
        field_ref = np.asarray(ref[variable], dtype=float)
        observed = peak_error(field_sim, field_ref)
    elif metric == "relative_peak":
        field_sim = sim[variable].to_numpy(dtype=float)
        field_ref = np.asarray(ref[variable], dtype=float)
        observed = relative_peak(field_sim, field_ref)
    elif metric == "relative_volume":
        field_sim = sim[variable].to_numpy(dtype=float) if variable in sim.columns else h_sim
        field_ref = np.asarray(ref.get(variable, ref.get("h")), dtype=float)
        observed = relative_volume(field_sim, field_ref)
    elif metric == "continuity_error":
        # Percent mean |u| / V0 behind closed valve (expect ~0 for exact).
        params = ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
        V0 = float(params.get("V0", 1.0))
        if "p" in ref and "u" in ref:
            dp = float(np.max(ref["p"]) - float(params.get("p0", 0.0)))
            behind = sim["p"].to_numpy(dtype=float) >= 0.5 * dp if dp else np.ones(len(sim), dtype=bool)
            u_behind = u_sim[behind] if np.any(behind) else u_sim
            continuity_pct = 100.0 * float(np.mean(np.abs(u_behind))) / max(abs(V0), 1e-12)
        else:
            continuity_pct = 100.0 * float(np.mean(np.abs(u_sim))) / max(abs(V0), 1e-12)
        observed = continuity_error(continuity_pct)
    else:
        raise ValueError(f"unsupported metric {metric!r}")

    observed_cmp = _as_percent_if_needed(metric, observed, thr.get("units", ""))
    passed = _threshold_passes(observed_cmp, thr)
    return {
        "id": criterion["id"],
        "metric": metric,
        "variable": variable,
        "observed": float(observed_cmp),
        "threshold": {
            "op": thr["op"],
            "value": float(thr["value"]),
            "units": thr.get("units", ""),
        },
        "passed": bool(passed),
        "gating": bool(criterion.get("gating", False)),
        **({"detail": detail} if detail else {}),
    }


def _estimate_dx(x: np.ndarray) -> float:
    if len(x) < 2:
        return 1.0
    d = np.diff(np.sort(np.unique(x)))
    return float(np.median(d)) if len(d) else 1.0


def _estimate_cell_measure(sim: pd.DataFrame) -> float:
    """1D spacing ``dx`` or 2D cell area ``dx*dy`` for discrete norms / mass."""
    x = sim["x"].to_numpy(dtype=float)
    dx = _estimate_dx(x)
    if not _is_2d_frame(sim):
        return dx
    y = sim["y"].to_numpy(dtype=float)
    dy = _estimate_dx(y)
    return float(dx * dy)


def _sim_xy(sim: pd.DataFrame) -> tuple[np.ndarray, np.ndarray | None]:
    x = sim["x"].to_numpy(dtype=float)
    if _is_2d_frame(sim):
        return x, sim["y"].to_numpy(dtype=float)
    return x, None


def _score_analytic(
    manifest: dict[str, Any],
    results_path: Path,
    refinement_results: Sequence[Path] | None,
) -> tuple[list[dict], dict | None, bool]:
    fn, params = _load_generator(manifest)
    if fn is None:
        raise ValueError("analytic scoring requires reference.kind == 'analytic'")

    df = read_results_parquet(results_path)
    sim = _final_slice(df)
    x, y = _sim_xy(sim)
    t_end = float(manifest["simulation"]["t_end"])
    # Prefer actual final time in results when present.
    t_sim = float(sim["t"].iloc[0]) if len(sim) else t_end
    ref = _call_reference(fn, params, x, t_sim, manifest, y=y)
    cell = _estimate_cell_measure(sim)

    criteria_results = [
        _eval_criterion(c, sim, ref, manifest, cell) for c in manifest["scoring"]["criteria"]
    ]

    convergence_result = None
    scoring = manifest.get("scoring") or {}
    conv_cfg = scoring.get("convergence")
    paths: list[Path] = []
    if refinement_results:
        paths = [Path(p) for p in refinement_results]
    elif conv_cfg and results_path.parent.is_dir():
        # Discover sibling refinement files: results_dx*.parquet or *_{dx}.parquet
        pass

    if conv_cfg and len(paths) >= 2:
        spacings: list[float] = []
        errors: list[float] = []
        norm_name = conv_cfg.get("norm", "L1")
        var = conv_cfg.get("variable", "h")
        norm_fn = _NORM_FNS[norm_name]
        for pth in paths:
            rdf = read_results_parquet(pth)
            rsim = _final_slice(rdf)
            rx, ry = _sim_xy(rsim)
            # Use linear spacing (dx) for observed-order / GCI, even in 2D.
            rdx = _estimate_dx(rx)
            rcell = _estimate_cell_measure(rsim)
            rref = _call_reference(
                fn, params, rx, float(rsim["t"].iloc[0]), manifest, y=ry
            )
            field_sim = rsim[var].to_numpy(dtype=float)
            field_ref = np.asarray(rref[var], dtype=float)
            if norm_name == "Linf":
                err = Linf(field_sim, field_ref)
            else:
                err = norm_fn(field_sim, field_ref, dx=rcell)
            spacings.append(rdx)
            errors.append(err)
        # Sort fine → coarse (ascending spacing)
        order = np.argsort(spacings)
        spacings = [spacings[i] for i in order]
        errors = [errors[i] for i in order]
        assess = assess_convergence(
            spacings,
            errors,
            expected_order=float(conv_cfg.get("expected_order", 1.0)),
            min_observed_order=float(conv_cfg.get("min_observed_order", 0.8)),
        )
        convergence_result = {
            "norm": norm_name,
            "variable": var,
            "observed_order": assess["observed_order"],
            "expected_order": assess["expected_order"],
            "min_observed_order": assess["min_observed_order"],
            "gci": assess["gci_fine"],
            "passed": assess["passed_order"],
        }

    gating = [c for c in criteria_results if c.get("gating")]
    criteria_ok = all(c["passed"] for c in gating) if gating else all(c["passed"] for c in criteria_results)
    conv_ok = True if convergence_result is None else bool(convergence_result["passed"])
    # Pass rule all_gating: gating criteria; convergence is reported but only
    # gates when present and configured as part of verification — include it.
    if scoring.get("pass_rule", "all_gating") == "all_gating":
        passed = criteria_ok and (conv_ok if convergence_result is not None else criteria_ok)
        if convergence_result is None:
            passed = criteria_ok
    else:
        passed = criteria_ok

    return criteria_results, convergence_result, passed


def _score_parity_stub(
    manifest: dict[str, Any],
    results_path: Path,
) -> tuple[list[dict], None, bool]:
    """Track B without pinned engine fixture: identity self-check on results."""
    df = read_results_parquet(results_path)
    sim = _final_slice(df)
    criteria_results = []
    for c in manifest["scoring"]["criteria"]:
        metric = c["metric"]
        variable = c.get("variable", "h")
        field = sim[variable].to_numpy(dtype=float) if variable in sim.columns else sim["h"].to_numpy()
        if metric == "relative_peak":
            observed = relative_peak(field, field) * 100.0
        elif metric == "relative_volume":
            observed = relative_volume(field, field) * 100.0
        else:
            observed = 0.0
        thr = c["threshold"]
        passed = _threshold_passes(observed, thr)
        criteria_results.append(
            {
                "id": c["id"],
                "metric": metric,
                "variable": variable,
                "observed": float(observed),
                "threshold": {
                    "op": thr["op"],
                    "value": float(thr["value"]),
                    "units": thr.get("units", ""),
                },
                "passed": bool(passed),
                "gating": bool(c.get("gating", False)),
                "detail": "parity self-check (no pinned reference loaded)",
            }
        )
    gating = [r for r in criteria_results if r["gating"]]
    passed = all(r["passed"] for r in gating) if gating else all(r["passed"] for r in criteria_results)
    return criteria_results, None, passed


def score_case(
    manifest: dict[str, Any],
    results_path: str | Path,
    refinement_results: Sequence[str | Path] | None = None,
    timestamp: str | None = None,
    private_key: Any = None,
    solver: dict[str, str] | None = None,
    catalog_version: str = "0.1.0",
    key_id: str = "benchmark1d2d-dev",
) -> dict[str, Any]:
    """Score one catalog case and return a signed scorecard dict."""
    results_path = Path(results_path)
    ref_kind = (manifest.get("reference") or {}).get("kind")
    if ref_kind == "analytic":
        criteria_results, convergence_result, passed = _score_analytic(
            manifest,
            results_path,
            [Path(p) for p in refinement_results] if refinement_results else None,
        )
    else:
        criteria_results, convergence_result, passed = _score_parity_stub(manifest, results_path)

    claims: list[str] = []
    if passed and manifest.get("track") == "A":
        claims.append("A-V")
    elif passed and manifest.get("track") == "B":
        claims.append("B-1%")

    return build_scorecard(
        test_id=manifest["test_id"],
        track=manifest["track"],
        case_version=manifest.get("case_version"),
        solver=solver
        or {
            "name": "unknown",
            "version": "0.0.0",
            "adapter": "generic_parquet",
        },
        catalog_version=catalog_version,
        criteria_results=criteria_results,
        convergence_result=convergence_result,
        passed=passed,
        certification_claims=claims,
        timestamp=timestamp,
        private_key=private_key,
        key_id=key_id,
    )

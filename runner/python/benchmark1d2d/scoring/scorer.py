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
    volume_front_error,
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
    case_dir = manifest.get("_case_dir")
    for k, v in list(params.items()):
        if k.endswith("_path") and isinstance(v, str) and case_dir and not Path(v).is_absolute():
            params[k] = str(Path(case_dir) / v)
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


def _align_elements(sim: pd.DataFrame, ref: dict) -> tuple[pd.DataFrame, dict]:
    """Match a network reference keyed by element id to the solver's rows."""
    if "element_id" not in sim.columns:
        raise ValueError("this case's reference is keyed by node/link id; add an element_id column to your results")
    # Nodes and links have separate namespaces (EPANET allows node "1" and pipe "1").
    types = ref.get("element_type")
    keys = [(str(t) if types is not None else "", str(e)) for t, e in zip(types if types is not None else [""] * len(ref["element_id"]), ref["element_id"])]
    sim = sim.assign(element_id=sim["element_id"].astype(str))
    sim["_k"] = list(zip(sim["element_type"].astype(str) if types is not None and "element_type" in sim.columns else [""] * len(sim), sim["element_id"]))
    missing = [k for k in keys if k not in set(sim["_k"])]
    if missing:
        raise ValueError(f"results lack {len(missing)} reference elements, e.g. {missing[0][0]} {missing[0][1]!r}")
    sim = sim.drop_duplicates("_k").set_index("_k").loc[keys].reset_index(drop=True)
    out = {k: (np.asarray(v, dtype=float) if k not in ("element_id", "element_type") else v) for k, v in ref.items()
           if k in ("element_id", "element_type") or (np.ndim(v) == 1 and len(v) == len(keys))}
    return sim, out


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
        ok = np.isfinite(field_ref)  # element-keyed references leave NaN where a variable does not apply
        field_sim, field_ref = field_sim[ok], field_ref[ok]
        if metric == "Linf":
            observed = Linf(field_sim, field_ref)
        else:
            observed = _NORM_FNS[metric](field_sim, field_ref, dx=cell)
        if thr.get("units", "").strip() == "%":
            # Relative norm: the same norm of the error over the same norm of the reference.
            zero = np.zeros_like(field_ref)
            scale = Linf(field_ref, zero) if metric == "Linf" else _NORM_FNS[metric](field_ref, zero, dx=cell)
            observed = 100.0 * observed / max(scale, 1e-300)
            detail = f"{metric} error relative to the {metric} norm of the reference"
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
    elif metric == "volume_front_error":
        from references.ritter import volume_front_position as exact_volume_front

        params = ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
        t_end = float(manifest["simulation"]["t_end"])
        x0 = float(params.get("x0", 1000.0))
        exact = exact_volume_front(t_end, VOLUME_FRONT_FRACTION, h0=float(params.get("h0", 1.0)), x0=x0,
                                   g=float(params.get("g", 9.81)))
        observed = volume_front_error(x, h_sim, VOLUME_FRONT_FRACTION, x0, exact)
        detail = (f"front holding the last {VOLUME_FRONT_FRACTION:.0%} of the water downstream of the dam: "
                  f"{exact + observed:.2f} m vs exact {exact:.2f} m")
    elif metric == "global_mass_error":
        # Cell-centred integrals: h (water volume) by default, or the named
        # conserved quantity (e.g. tracer concentration c) when given.
        q = variable if variable not in ("volume", "h") and variable in sim.columns else "h"
        q_sim = sim[q].to_numpy(dtype=float)
        q_ref = np.asarray(ref.get(q, q_sim), dtype=float)
        observed = global_mass_error(float(np.sum(q_sim) * cell), float(np.sum(q_ref) * cell))
    elif metric == "relative_head_loss":
        # Head drop from the most upstream to the most downstream point (by x).
        order = np.argsort(x)
        hs = sim[variable].to_numpy(dtype=float)[order]
        hr = np.asarray(ref[variable], dtype=float)[order]
        drop_sim, drop_ref = hs[0] - hs[-1], hr[0] - hr[-1]
        observed = 100.0 * (drop_sim - drop_ref) / max(abs(drop_ref), 1e-300)
        detail = f"head loss {drop_sim:.4f} m vs exact {drop_ref:.4f} m"
    elif metric == "storage_balance_error":
        # Water hammer before the first reflection: the reservoir keeps feeding
        # V0 while the valve is shut, and the pipe stores that volume by
        # compression, so the integral of the pressure rise must equal rho a^2 V0 t.
        params = ((manifest.get("reference") or {}).get("generator") or {}).get("parameters") or {}
        rho, a, V0 = float(params.get("rho", 1000.0)), float(params["a"]), float(params["V0"])
        p0 = float(params.get("p0", 0.0))
        t_now = float(sim["t"].iloc[0])
        order = np.argsort(x)
        dp = sim["p"].to_numpy(dtype=float)[order] - p0
        stored = float(np.trapezoid(dp, x[order]))  # trapezoid: exact for node-based output, O(dx²) for cell centres
        expected = rho * a * a * V0 * t_now
        observed = 100.0 * (stored - expected) / expected
        detail = f"packed volume {stored / (rho * a * a):.6g} m per unit area vs inflow V0 t = {V0 * t_now:.6g} m"
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
    if "element_id" in ref:
        sim, ref = _align_elements(sim, ref)
    cell = _estimate_cell_measure(sim)

    criteria_results = [
        _eval_criterion(c, sim, ref, manifest, cell) for c in manifest["scoring"]["criteria"]
    ]

    convergence_result = None
    scoring = manifest.get("scoring") or {}
    conv_cfg = scoring.get("convergence")
    if conv_cfg and conv_cfg.get("not_applicable"):
        conv_cfg = None
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
            "spacings": [float(v) for v in spacings],
            "errors": [float(v) for v in errors],
            **({"note": assess["note"]} if assess.get("note") else {}),
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


class ReferenceUnavailable(RuntimeError):
    """The case's reference data is missing, so it cannot be scored.

    Raised instead of producing a score card: a case without its reference
    is *not scored*, never passed.
    """


def _case_dir(manifest: dict[str, Any]) -> Path | None:
    d = manifest.get("_case_dir")
    return Path(d) if d else None


def _result_row(criterion: dict[str, Any], observed: float, detail: str | None = None) -> dict[str, Any]:
    thr = criterion["threshold"]
    passed = bool(np.isfinite(observed)) and _threshold_passes(observed, thr)
    row = {
        "id": criterion["id"],
        "metric": criterion["metric"],
        "variable": criterion.get("variable", "h"),
        "observed": float(observed) if np.isfinite(observed) else None,
        "threshold": {"op": thr["op"], "value": float(thr["value"]), "units": thr.get("units", "")},
        "passed": passed,
        "gating": bool(criterion.get("gating", False)),
    }
    if detail:
        row["detail"] = detail
    return row


# ── Track B: parity against a pinned engine's per-element series ────────────


def _element_series(df: pd.DataFrame, variable: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    if "element_id" not in df.columns:
        raise ValueError(
            "parity scoring needs an element_id column (node/link names); "
            "use the swmm5/epanet22 adapters or add element_id to your results"
        )
    col = "Q" if variable in ("Q", "volume") else variable
    if col not in df.columns:
        raise ValueError(f"results have no {col!r} column")
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    sub = df[np.isfinite(df[col].to_numpy(dtype=float))]
    for eid, grp in sub.groupby("element_id", sort=True):
        grp = grp.sort_values("t")
        out[str(eid)] = (grp["t"].to_numpy(dtype=float), grp[col].to_numpy(dtype=float))
    return out


# Fraction of the downstream water that defines the volume front (A1F-010).
VOLUME_FRONT_FRACTION = 0.05


def _parity_metric(metric: str, variable: str, sim: pd.DataFrame, ref: pd.DataFrame) -> tuple[float, str]:
    """Worst-element parity error and a human-readable detail string."""
    return parity_from_series(metric, _element_series(sim, variable), _element_series(ref, variable), variable)


def parity_from_series(metric: str, s_series: dict, r_series: dict, variable: str = "") -> tuple[float, str]:
    """``_parity_metric`` on ``{element: (t, values)}`` maps (elements in name order)."""
    if not r_series:
        raise ReferenceUnavailable(f"reference has no {variable!r} series")
    missing = sorted(set(r_series) - set(s_series))
    if missing:
        return float("inf"), f"{len(missing)} reference elements missing from results (e.g. {missing[0]})"

    if metric == "relative_peak":
        ref_pk = {e: float(np.max(np.abs(v))) for e, (_, v) in r_series.items()}
        sim_pk = {e: float(np.max(np.abs(s_series[e][1]))) for e in r_series}
        floor = 0.01 * max(ref_pk.values()) or 1e-12
        errs = {e: (sim_pk[e] - ref_pk[e]) / max(ref_pk[e], floor) for e in r_series}
        unit = "%"
        scale = 100.0
    elif metric == "relative_volume":
        def vol(t, v):
            return float(np.trapezoid(np.abs(v), t)) if len(t) > 1 else float(np.sum(np.abs(v)))
        ref_v = {e: vol(*r_series[e]) for e in r_series}
        sim_v = {e: vol(*s_series[e]) for e in r_series}
        floor = 0.01 * max(ref_v.values()) or 1e-12
        errs = {e: (sim_v[e] - ref_v[e]) / max(ref_v[e], floor) for e in r_series}
        unit = "%"
        scale = 100.0
    elif metric == "timing_error":
        errs = {}
        for e, (tr, vr) in r_series.items():
            ts, vs = s_series[e]
            errs[e] = float(ts[np.argmax(np.abs(vs))] - tr[np.argmax(np.abs(vr))])
        unit = "s"
        scale = 1.0
    else:
        raise ValueError(f"metric {metric!r} is not a parity metric")
    worst = max(errs, key=lambda e: abs(errs[e]))
    value = errs[worst] * scale
    return float(value), f"worst of {len(errs)} elements: {worst} ({value:+.4g} {unit})"


def _resolve_engine_reference(manifest: dict[str, Any], reference_results: Path | None) -> Path:
    if reference_results is not None:
        path = Path(reference_results)
    else:
        rel = (manifest.get("reference") or {}).get("results_path")
        case_dir = _case_dir(manifest)
        if not rel or case_dir is None:
            raise ReferenceUnavailable(
                f"{manifest['test_id']}: no reference results; run scripts/make_reference.py {manifest['test_id']}"
            )
        path = case_dir / rel
    if not path.is_file():
        raise ReferenceUnavailable(f"{manifest['test_id']}: reference results not found at {path}")
    return path


def _score_parity(manifest: dict[str, Any], results_path: Path, reference_results: Path | None) -> tuple[list[dict], None, bool]:
    ref_path = _resolve_engine_reference(manifest, reference_results)
    sim = read_results_parquet(results_path)
    ref = read_results_parquet(ref_path)
    rows = []
    for c in manifest["scoring"]["criteria"]:
        if c["metric"] in ("relative_peak", "relative_volume", "timing_error"):
            observed, detail = _parity_metric(c["metric"], c.get("variable", "h"), sim, ref)
            rows.append(_result_row(c, observed, detail))
        else:
            rows.append(_result_row(c, float("nan"), f"metric {c['metric']!r} not evaluable for parity; counted as not passed"))
    return rows, None, _passed(rows)


# ── Track A code inter-comparison: objective expected states ────────────────


def _read_asc(path: Path) -> tuple[dict[str, float], np.ndarray]:
    with path.open() as fh:
        hdr = {}
        for _ in range(6):
            k, v = fh.readline().split()
            hdr[k.lower()] = float(v)
        z = np.loadtxt(fh)
    return hdr, z


def _bed_at(manifest: dict[str, Any], x: float, y: float) -> float:
    case_dir = _case_dir(manifest)
    terrain = None
    for entry in manifest.get("inputs") or []:
        if entry.get("role") == "terrain":
            terrain = entry
    if terrain is None:
        return 0.0  # flat bed at datum (e.g. EA Test 4)
    path = case_dir / terrain["path"] if case_dir else None
    if path is None or not path.is_file():
        raise ReferenceUnavailable(f"terrain {terrain['path']} not fetched; run scripts/fetch_inputs.py")
    hdr, z = _read_asc(path)
    cs = hdr["cellsize"]
    j = int((x - hdr["xllcorner"]) // cs)
    i = int(hdr["nrows"] - 1 - (y - hdr["yllcorner"]) // cs)
    return float(z[i, j])


def _probe(manifest: dict[str, Any], pid: str) -> dict[str, Any]:
    for p in (manifest.get("simulation") or {}).get("probes") or []:
        if p["id"] == pid:
            return p
    raise ValueError(f"probe {pid!r} not declared in manifest")


def _series_at(df: pd.DataFrame, x: float, y: float, col: str) -> tuple[np.ndarray, np.ndarray]:
    """Time series at the single cell nearest (x, y).

    A probe on a cell face is equidistant from two (or four) cells; ties are
    broken towards the smallest x, then the smallest y, so depth and bed always
    come from the same cell.
    """
    df = df[np.isfinite(df["x"].to_numpy(dtype=float)) & np.isfinite(df["y"].to_numpy(dtype=float))]
    cells = df[["x", "y"]].drop_duplicates().to_numpy(dtype=float)
    d2 = (cells[:, 0] - x) ** 2 + (cells[:, 1] - y) ** 2
    tied = cells[np.isclose(d2, d2.min(), rtol=1e-12, atol=1e-12)]
    cx, cy = sorted(map(tuple, tied))[0]
    sub = df[np.isclose(df["x"].to_numpy(dtype=float), cx) & np.isclose(df["y"].to_numpy(dtype=float), cy)]
    sub = sub.sort_values("t").drop_duplicates("t")
    return sub["t"].to_numpy(dtype=float), sub[col].to_numpy(dtype=float)


def _expected_state_value(manifest: dict[str, Any], state: dict[str, Any], df: pd.DataFrame) -> float:
    var = state["variable"]
    t_target = float(state.get("time", df["t"].max()))
    if state.get("element"):
        # a network or coupling element: exchange flow (Q) or a volume account (V)
        if "element_id" not in df.columns:
            raise ValueError("this state is keyed by element; add element_id/element_type rows to your results")
        sub = df[df["element_id"].astype(str) == str(state["element"])]
        if var == "V":
            sub = sub[sub["element_type"].astype(str) == "account"] if "element_type" in sub.columns else sub
        elif "element_type" in sub.columns:
            sub = sub[sub["element_type"].astype(str) != "account"]
        sub = sub.sort_values("t").drop_duplicates("t")
        if sub.empty:
            raise ValueError(f"results have no rows for element {state['element']!r}")
        t, v = sub["t"].to_numpy(dtype=float), sub[var].to_numpy(dtype=float)
        return float(np.interp(t_target, t, v)) if "time" in state else float(v[-1])
    if var == "volume":
        times = np.unique(df["t"].to_numpy(dtype=float))
        t_use = times[np.argmin(np.abs(times - t_target))]
        sl = df[np.isclose(df["t"].to_numpy(dtype=float), t_use)]
        return float(np.nansum(sl["h"].to_numpy(dtype=float)) * _estimate_cell_measure(sl))
    if var in ("h+z", "h"):
        values = []
        for pid in str(state.get("where", "")).split(","):
            p = _probe(manifest, pid.strip())
            t, h = _series_at(df, p["x"], p.get("y", 0.0), "h")
            z = 0.0
            if var == "h+z":
                if "z" in df.columns and df["z"].notna().any():
                    # the solver's own bed at the cell holding the probe
                    z = float(np.nanmean(_series_at(df, p["x"], p.get("y", 0.0), "z")[1]))
                else:
                    z = _bed_at(manifest, p["x"], p.get("y", 0.0))
            if "time" in state:
                values.append(float(np.interp(t_target, t, h)) + z)
            else:
                values.append(float(np.max(h)) + z)
        # worst deviation across the listed probes
        return max(values, key=lambda v: abs(v - float(state["value"])))
    raise ValueError(f"expected-state variable {var!r} not supported")


ACCOUNTS = ("surface", "network", "inflow", "outflow")


def _continuity_error(df: pd.DataFrame) -> tuple[float, str]:
    """End-of-run volume imbalance of a coupled model, in % of the water involved.

    The results carry volume accounts (element_type ``account``): ``surface``
    and ``network`` hold the water stored at each time; ``inflow`` and
    ``outflow`` are cumulative volumes in and out of the whole system. The
    imbalance at time t is stored(t) − stored(0) − (inflow(t) − outflow(t));
    the error is its value at the end of the run divided by the larger of the
    total inflow and the initial storage (the usual continuity error). The
    largest imbalance during the run is reported alongside: engines can
    report stored volumes that disagree with their own internal balance while
    pipes are surcharged.
    """
    if "element_type" not in df.columns or "V" not in df.columns:
        raise ValueError("continuity scoring needs volume-account rows (element_type 'account', column V)")
    acc = df[df["element_type"].astype(str) == "account"]
    series = {}
    for name in ACCOUNTS:
        sub = acc[acc["element_id"].astype(str) == name].sort_values("t").drop_duplicates("t")
        if name in ("surface", "network") and sub.empty:
            raise ValueError(f"volume account {name!r} missing")
        series[name] = sub
    t = series["surface"]["t"].to_numpy(dtype=float)
    val = {k: (np.interp(t, v["t"].to_numpy(dtype=float), v["V"].to_numpy(dtype=float)) if not v.empty else np.zeros_like(t))
           for k, v in series.items()}
    stored = val["surface"] + val["network"]
    imbalance = stored - stored[0] - (val["inflow"] - val["inflow"][0]) + (val["outflow"] - val["outflow"][0])
    scale = max(float(val["inflow"][-1] - val["inflow"][0]), float(stored[0]), 1e-12)
    k = int(np.argmax(np.abs(imbalance)))
    return 100.0 * float(imbalance[-1]) / scale, (f"imbalance {imbalance[-1]:+.4g} m³ at the end, of {scale:.6g} m³ "
                                                   f"(inflow {val['inflow'][-1]:.6g}, outflow {val['outflow'][-1]:.6g} m³); "
                                                   f"largest during the run {imbalance[k]:+.4g} m³ at t = {t[k]:g} s")


def _score_expected_states(manifest: dict[str, Any], results_path: Path) -> tuple[list[dict], None, bool]:
    ref = manifest["reference"]
    states = {s["id"]: s for s in ref["expected_states"]}
    df = read_results_parquet(results_path)
    rows = []
    for c in manifest["scoring"]["criteria"]:
        if c["metric"] == "continuity_error":
            observed, detail = _continuity_error(df)
            rows.append(_result_row(c, observed, detail))
            continue
        if c["metric"] != "expected_state_error":
            rows.append(_result_row(c, float("nan"), "only expected_state_error and continuity_error criteria score this case"))
            continue
        st = states[c["against"]]
        got = _expected_state_value(manifest, st, df)
        expected = float(st["value"])
        units = c["threshold"].get("units", "")
        observed = 100.0 * (got - expected) / expected if units == "%" else got - expected
        rows.append(_result_row(c, observed, f"{st['id']}: simulated {got:.6g} vs expected {expected:.6g} {st['units']}"))
    return rows, None, _passed(rows)


# ── Track A validation: measured gauges ─────────────────────────────────────


def _score_measured(manifest: dict[str, Any], results_path: Path) -> tuple[list[dict], None, bool]:
    ref = manifest["reference"]
    case_dir = _case_dir(manifest)
    path = case_dir / ref["data_path"] if case_dir else None
    if path is None or not path.is_file():
        raise ReferenceUnavailable(
            f"{manifest['test_id']}: measured reference {ref['data_path']} is not available "
            f"(availability: {ref.get('availability', 'unknown')})"
        )
    meas = pd.read_parquet(path)  # columns: t, gauge, and measured variables; optionally event
    df = read_results_parquet(results_path)
    if "z" in df.columns:
        df["wse"] = df["h"] + df["z"]  # water-surface level, for gauges that record a level above datum
    probe_map = ref.get("probe_map") or {}
    dt_out = float((manifest.get("simulation") or {}).get("output_interval", 60.0))
    rows = []
    for c in manifest["scoring"]["criteria"]:
        var = c.get("variable", "h")
        absolute = c["threshold"].get("units") == "m"  # peak error in metres rather than per cent
        errs, labels = [], []
        for p in (manifest.get("simulation") or {}).get("probes") or []:
            gauge = probe_map.get(p["id"], p["id"])
            m = meas[meas["gauge"] == gauge].sort_values("t")
            if m.empty or var not in m.columns:
                continue
            if p.get("element"):  # a network node: matched by name, not position
                if "element_id" not in df.columns:
                    raise ValueError("this test's gauges are network nodes; add element_id rows to your results")
                sub = df[df["element_id"].astype(str) == str(p["element"])].sort_values("t").drop_duplicates("t")
                ts, vs = sub["t"].to_numpy(float), sub[var].to_numpy(float)
            else:
                ts, vs = _series_at(df, p["x"], p.get("y", 0.0), var)
            groups = m.groupby("event", sort=True) if "event" in m.columns else [(None, m)]
            for ev, mg in groups:
                tm, obs = mg["t"].to_numpy(float), mg[var].to_numpy(float)
                label = f"{p['id']}" + (f" ({ev})" if ev is not None else "")
                labels.append(label)
                if len(ts) == 0:
                    errs.append(float("nan"))
                    continue
                # a gauge record outside the simulated period is not scored against an extrapolated value
                near = np.abs(ts[np.clip(np.searchsorted(ts, tm), 0, len(ts) - 1)] - tm) <= 2 * dt_out
                near |= np.abs(ts[np.clip(np.searchsorted(ts, tm) - 1, 0, len(ts) - 1)] - tm) <= 2 * dt_out
                if near.mean() < 0.9:
                    errs.append(float("nan"))
                    continue
                tm, obs = tm[near], obs[near]
                sim_on_meas = np.interp(tm, ts, vs)
                if c["metric"] == "NSE":
                    errs.append(1.0 - np.sum((sim_on_meas - obs) ** 2) / np.sum((obs - obs.mean()) ** 2))
                elif c["metric"] in ("peak_error", "relative_peak"):
                    d = sim_on_meas.max() - obs.max()
                    errs.append(float(d) if absolute else 100.0 * d / obs.max())
                elif c["metric"] == "arrival_time_error":
                    thr = 0.05 * obs.max()
                    errs.append(float(tm[np.argmax(sim_on_meas > thr)] - tm[np.argmax(obs > thr)]))
        if not errs:
            rows.append(_result_row(c, float("nan"), "no gauge matched a declared probe"))
            continue
        if any(not np.isfinite(e) for e in errs):
            missing = [lb for lb, e in zip(labels, errs) if not np.isfinite(e)]
            rows.append(_result_row(c, float("nan"), f"not simulated at {len(missing)} of {len(errs)} gauge records: {', '.join(missing[:4])}"))
            continue
        i = int(np.argmin(errs)) if c["metric"] == "NSE" else int(np.argmax(np.abs(errs)))
        rows.append(_result_row(c, float(errs[i]), f"worst of {len(errs)} gauge records: {labels[i]}"))
    return rows, None, _passed(rows)


def _passed(rows: list[dict[str, Any]]) -> bool:
    gating = [r for r in rows if r["gating"]]
    return all(r["passed"] for r in (gating or rows))


_CLASS_CLAIM = {
    "verification_analytic": "A-V",
    "verification_manufactured": "A-V",
    "validation_lab": "A-L",
    "validation_field": "A-F",
    "validation_coupled": "A-L",
    "intercomparison": "A-C",
}


def certification_claims(manifest: dict[str, Any], passed: bool, verified: bool = True) -> list[str]:
    """Claims a passing card may carry, derived from the case's class and tolerance.

    A Track A claim (A-V and the like) needs the result to converge as well
    as pass (scoring method 2.1: ``verified``).
    """
    if not passed:
        return []
    if manifest.get("track") == "A" and not verified:
        return []
    if manifest.get("track") == "A":
        claim = _CLASS_CLAIM.get(str(manifest.get("test_class")))
        return [claim] if claim else []
    pct = [
        float(c["threshold"]["value"])
        for c in manifest["scoring"]["criteria"]
        if c.get("gating") and c["threshold"].get("units") == "%"
    ]
    return [f"B-{max(pct):g}%"] if pct else ["B"]


def score_case(
    manifest: dict[str, Any],
    results_path: str | Path,
    refinement_results: Sequence[str | Path] | None = None,
    timestamp: str | None = None,
    private_key: Any = None,
    solver: dict[str, str] | None = None,
    catalog_version: str = "0.1.0",
    key_id: str = "benchmark1d2d-dev",
    reference_results: str | Path | None = None,
) -> dict[str, Any]:
    """Score one catalog case and return a signed scorecard dict.

    Raises :class:`ReferenceUnavailable` when the case's reference (pinned-engine
    results, measured gauges, fetched terrain) is missing: such a case is not
    scored rather than passed.
    """
    results_path = Path(results_path)
    ref_kind = (manifest.get("reference") or {}).get("kind")
    if ref_kind == "analytic":
        criteria_results, convergence_result, passed = _score_analytic(
            manifest,
            results_path,
            [Path(p) for p in refinement_results] if refinement_results else None,
        )
    elif ref_kind == "pinned_engine":
        criteria_results, convergence_result, passed = _score_parity(
            manifest, results_path, Path(reference_results) if reference_results else None
        )
    elif ref_kind in ("intercomparison", "exact_states"):
        criteria_results, convergence_result, passed = _score_expected_states(manifest, results_path)
    elif ref_kind == "measured":
        criteria_results, convergence_result, passed = _score_measured(manifest, results_path)
    else:
        raise ValueError(f"unknown reference kind {ref_kind!r}")

    # Method 2 (docs/methodology/scoring_v2.md): two verdicts, margins, the convergence
    # rate with its 90 % range, and a third outcome, inconclusive.
    from benchmark1d2d.scoring import method_v2

    judged = method_v2.assess({"criteria_results": criteria_results, "convergence_result": convergence_result,
                               "passed": passed, "solver": solver or {}})
    for row, chk in zip(criteria_results, judged["checks"]):
        row["margin"] = chk["margin"]
    verdict = judged["overall"]
    passed = verdict == "pass"
    claims = certification_claims(manifest, passed, judged["verified"])

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
        scoring_method=method_v2.METHOD,
        verdict=verdict,
        judgement=method_v2.judgement(judged),
        timestamp=timestamp,
        private_key=private_key,
        key_id=key_id,
    )

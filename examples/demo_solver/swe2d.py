"""Demo 2D shallow-water solver for benchmark1d2d (first-order finite volume).

A deliberately plain, readable reference implementation — the kind of solver
the suite exists to test, not a production code:

- Cartesian grid, cell-centred ``h, hu, hv`` and bed ``z``
- HLL Riemann fluxes with the hydrostatic reconstruction of
  Audusse, Bouchut, Bristeau, Klein & Perthame (2004), which keeps lakes at
  rest exactly and depths non-negative across wet/dry fronts
- semi-implicit Manning friction
- closed walls (cells outside the active area act as walls), discharge
  inflow along a polyline (volume source), or a water-level boundary on the
  west edge
- explicit Euler in time, CFL 0.45

First-order in space and time, so smooth solutions converge at ~1 and
solutions with fronts or shocks more slowly. Results are written in the
benchmark1d2d contract with the solver's own bed in ``z``.

References
----------
Audusse, E., Bouchut, F., Bristeau, M.-O., Klein, R., and Perthame, B. (2004).
"A fast and stable well-balanced scheme with hydrostatic reconstruction for
shallow water flows." *SIAM J. Sci. Comput.*, 25(6), 2050–2065.
https://doi.org/10.1137/S1064827503431090
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

G = 9.81
DRY = 1e-6
WALL_Z = 1.0e5


@dataclass
class Grid:
    x: np.ndarray  # cell-centre x (nx)
    y: np.ndarray  # cell-centre y (ny)
    z: np.ndarray  # bed (ny, nx); inactive cells hold WALL_Z
    active: np.ndarray  # bool (ny, nx)

    @property
    def dx(self) -> float:
        return float(self.x[1] - self.x[0])

    @property
    def dy(self) -> float:
        return float(self.y[1] - self.y[0])


@dataclass
class Case:
    grid: Grid
    h: np.ndarray
    hu: np.ndarray
    hv: np.ndarray
    manning_n: float = 0.0
    t_end: float = 1.0
    inflow: Callable[[float], float] | None = None  # Q(t) [m3/s]
    inflow_cells: np.ndarray | None = None  # bool mask
    west_level: Callable[[float], float] | None = None  # water level on west edge
    probes: dict[str, tuple[int, int]] = field(default_factory=dict)  # id -> (j, i)


def _hll(hL, uL, vL, hR, uR, vR):
    """HLL flux normal to the face; returns (F_h, F_hu, F_hv)."""
    cL = np.sqrt(G * hL)
    cR = np.sqrt(G * hR)
    sL = np.minimum(uL - cL, uR - cR)
    sR = np.maximum(uL + cL, uR + cR)
    fL = (hL * uL, hL * uL * uL + 0.5 * G * hL * hL, hL * uL * vL)
    fR = (hR * uR, hR * uR * uR + 0.5 * G * hR * hR, hR * uR * vR)
    qL = (hL, hL * uL, hL * vL)
    qR = (hR, hR * uR, hR * vR)
    denom = np.where(sR - sL == 0.0, 1.0, sR - sL)
    out = []
    for fl, fr, ql, qr in zip(fL, fR, qL, qR):
        fh = (sR * fl - sL * fr + sL * sR * (qr - ql)) / denom
        out.append(np.where(sL >= 0.0, fl, np.where(sR <= 0.0, fr, fh)))
    both_dry = (hL <= DRY) & (hR <= DRY)
    return [np.where(both_dry, 0.0, f) for f in out]


def _face_fluxes(hL, uL, vL, zL, hR, uR, vR, zR):
    """Audusse hydrostatic reconstruction at faces; returns left/right momentum-corrected fluxes."""
    zf = np.maximum(zL, zR)
    hLs = np.maximum(0.0, hL + zL - zf)
    hRs = np.maximum(0.0, hR + zR - zf)
    fh, fu, fv = _hll(hLs, uL, vL, hRs, uR, vR)
    # Pressure corrections that balance the bed source (well-balanced)
    fu_L = fu + 0.5 * G * (hL * hL - hLs * hLs)
    fu_R = fu + 0.5 * G * (hR * hR - hRs * hRs)
    return fh, fu_L, fu_R, fv


def _velocities(h, hu, hv):
    wet = h > DRY
    u = np.where(wet, hu / np.where(wet, h, 1.0), 0.0)
    v = np.where(wet, hv / np.where(wet, h, 1.0), 0.0)
    return u, v


def _pad(a, value):
    return np.pad(a, 1, mode="constant", constant_values=value)


def step(case: Case, h, hu, hv, t: float, cfl: float = 0.45) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    gr = case.grid
    u, v = _velocities(h, hu, hv)
    c = np.abs(u) + np.sqrt(G * h)
    d = np.abs(v) + np.sqrt(G * h)
    smax = max(float(np.max(c)) / gr.dx, float(np.max(d)) / gr.dy, 1e-12)
    dt = min(cfl / smax, case.t_end - t)

    # Ghost ring: walls (high bed, dry) unless a west water-level boundary applies.
    Z = _pad(gr.z, WALL_Z)
    H = _pad(h, 0.0)
    U = _pad(u, 0.0)
    V = _pad(v, 0.0)
    if case.west_level is not None:
        eta = case.west_level(t)
        Z[1:-1, 0] = gr.z[:, 0]
        H[1:-1, 0] = np.maximum(0.0, eta - gr.z[:, 0]) * gr.active[:, 0]
        U[1:-1, 0] = u[:, 0]
        V[1:-1, 0] = 0.0

    # x-faces (ny, nx+1)
    fh, fuL, fuR, fv = _face_fluxes(H[1:-1, :-1], U[1:-1, :-1], V[1:-1, :-1], Z[1:-1, :-1],
                                    H[1:-1, 1:], U[1:-1, 1:], V[1:-1, 1:], Z[1:-1, 1:])
    # y-faces (ny+1, nx): rotate (u <-> v)
    gh, gvL, gvR, gu = _face_fluxes(H[:-1, 1:-1], V[:-1, 1:-1], U[:-1, 1:-1], Z[:-1, 1:-1],
                                    H[1:, 1:-1], V[1:, 1:-1], U[1:, 1:-1], Z[1:, 1:-1])
    a, b = dt / gr.dx, dt / gr.dy
    h_new = h - a * (fh[:, 1:] - fh[:, :-1]) - b * (gh[1:, :] - gh[:-1, :])
    hu_new = hu - a * (fuL[:, 1:] - fuR[:, :-1]) - b * (gu[1:, :] - gu[:-1, :])
    hv_new = hv - a * (fv[:, 1:] - fv[:, :-1]) - b * (gvL[1:, :] - gvR[:-1, :])

    if case.inflow is not None and case.inflow_cells is not None:
        q = 0.5 * (case.inflow(t) + case.inflow(t + dt))
        n = int(case.inflow_cells.sum())
        h_new = h_new + case.inflow_cells * (q * dt / (n * gr.dx * gr.dy))

    h_new = np.where(gr.active, np.maximum(h_new, 0.0), 0.0)
    if case.manning_n > 0.0:
        un, vn = _velocities(h_new, hu_new, hv_new)
        speed = np.sqrt(un * un + vn * vn)
        hh = np.maximum(h_new, DRY)
        k = 1.0 + dt * G * case.manning_n**2 * speed / hh ** (4.0 / 3.0)
        hu_new = hu_new / k
        hv_new = hv_new / k
    dry = h_new <= DRY
    hu_new = np.where(dry, 0.0, hu_new)
    hv_new = np.where(dry, 0.0, hv_new)
    return h_new, hu_new, hv_new, dt


def run(
    case: Case,
    field_times: list[float],
    probe_interval: float | None = None,
    progress: bool = False,
) -> dict[str, np.ndarray]:
    """Integrate to ``t_end``; record full fields at ``field_times`` and probe series.

    Returns columns for ``write_results_parquet`` (t, x, y, h, u, v, p, z).
    Rows at a field time cover every active cell; between field times only
    probe cells are recorded, so each (t, cell) pair appears once.
    """
    gr = case.grid
    X, Y = np.meshgrid(gr.x, gr.y)
    act = gr.active
    h, hu, hv = case.h.copy(), case.hu.copy(), case.hv.copy()
    rows: dict[str, list[np.ndarray]] = {k: [] for k in ("t", "x", "y", "h", "u", "v", "z")}
    pj = np.array([p[0] for p in case.probes.values()], dtype=int)
    pi = np.array([p[1] for p in case.probes.values()], dtype=int)
    targets = sorted(set([0.0] + list(field_times) + [case.t_end]))
    p_next = 0.0 if probe_interval else None

    def record(tt, full):
        u, v = _velocities(h, hu, hv)
        if full:
            sel = act
            rows["x"].append(X[sel]); rows["y"].append(Y[sel]); rows["h"].append(h[sel])
            rows["u"].append(u[sel]); rows["v"].append(v[sel]); rows["z"].append(gr.z[sel])
            rows["t"].append(np.full(int(sel.sum()), tt))
        elif len(pj):
            rows["x"].append(X[pj, pi]); rows["y"].append(Y[pj, pi]); rows["h"].append(h[pj, pi])
            rows["u"].append(u[pj, pi]); rows["v"].append(v[pj, pi]); rows["z"].append(gr.z[pj, pi])
            rows["t"].append(np.full(len(pj), tt))

    t = 0.0
    k = 0
    while True:
        on_field = any(abs(t - ft) < 1e-9 for ft in targets)
        on_probe = p_next is not None and t >= p_next - 1e-9
        if on_field or on_probe:
            record(t, on_field)
            if on_probe:
                p_next += probe_interval
        if t >= case.t_end - 1e-12:
            break
        nxt = min([ft for ft in targets if ft > t + 1e-9] + ([p_next] if p_next is not None else []))
        saved = case.t_end
        case.t_end = nxt  # clip the step to land exactly on the next output time
        h, hu, hv, dt = step(case, h, hu, hv, t)
        case.t_end = saved
        t += dt
        k += 1
        if progress and k % 2000 == 0:
            vol = float(h.sum() * gr.dx * gr.dy)
            print(f"  t={t:9.1f}s  steps={k}  volume={vol:,.1f} m3", flush=True)

    out = {key: np.concatenate(val) for key, val in rows.items()}
    out["p"] = np.full(len(out["t"]), np.nan)
    out["steps"] = k  # type: ignore[assignment]
    return out

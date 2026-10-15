#!/usr/bin/env python3
"""Score HydroNet (Penn State, psu-efd) on the catalog's dam breaks and the Thacker bowl.

`HydroNet <https://github.com/psu-efd/HydroNet>`_ (MIT) is a PyTorch
framework for the 2D shallow-water equations with physics-informed deep
learning. Two of its pieces are scored, as two solvers:

* ``fvm``  — its differentiable, well-balanced **Roe finite-volume solver**
  with Heun RK2 time stepping (``run_fvm_rk2``, the engine behind its
  ``*_fvm_only.py`` drivers and FVM-PINN's residual), CFL 0.3 (its default).
* ``pinn`` — the **FVM-PINN** neural network (``FVM_SWE_PINN``), trained on
  each grid with the recipe of HydroNet's own 1D dam-break example
  (``examples/FVM_PINN/dam_break_1d``): a 64×5 Fourier-feature MLP, 5000 Adam
  epochs, initial-condition and FVM-residual losses, no reference data. The
  trained network is evaluated at the cell centres at the case's end time.

Both are run on HydroNet's own mesh structure (``build_mesh`` from SRH-2D-style
raw data), with the case's grid as quad cells and the bed given at the nodes
(HydroNet averages the four node elevations per cell). Walls are HydroNet's
default reflective boundaries. Wet/dry threshold ``h_dry`` = 1e-4 m, as in the
dam-break example.

Cases: A1F-010 (Ritter), A1F-011 (Stoker) on a one-cell-wide strip; A2A-001
(Thacker bowl). Score cards go to ``out/hydronet/<mode>/``. Usage::

    python scripts/run_hydronet.py --hydronet /path/to/HydroNet [--mode fvm pinn] [CASE ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO)]

OUT = REPO / "out" / "hydronet"
TS = "2024-01-01T00:00:00Z"
G = 9.81
H_DRY = 1.0e-4
CFL = 0.3

# HydroNet's 1D dam-break example recipe (examples/FVM_PINN/dam_break_1d/fvm_pinn_config.yaml)
PINN_CONFIG = """
device: {{type: "cpu", index: 0}}
model:
  name: "FVM_SWE_PINN"
  arch: "mlp"
  hidden_dim: 64
  n_layers: 5
  n_fourier: 32
  fourier_scale: 2.0
  activation: "tanh"
  use_residual: false
physics: {{wse_still: {wse_still}, h_dry: {h_dry}, gravity: 9.81}}
training:
  strategy: "standard"
  t_start: 0.0
  t_end: {t_end}
  adam_epochs: {epochs}
  adam_lr: 1.0e-3
  adam_lr_decay: 0.9
  adam_decay_every: 1000
  lbfgs_epochs: 0
  n_time_samples: 5
  loss_weights: {{lambda_fvm: 1.0, lambda_ic: 20.0, lambda_bc: 5.0, lambda_data: 0.0}}
  logging: {{print_freq: 1000, save_freq: 100000, checkpoint_dir: "{ckpt}"}}
"""


def quad_mesh(xs_nodes: np.ndarray, ys_nodes: np.ndarray, z_nodes: np.ndarray, manning: float = 0.0):
    """HydroNet ``UnstructuredMesh`` of quads on a tensor grid; ``z_nodes[j, i]`` at node (x_i, y_j)."""
    from HydroNet.models.FVM_PINN._internal.mesh.mesh_topology import build_mesh
    from HydroNet.models.FVM_PINN._internal.mesh.srh2d_reader import SRH2DRawData

    nx, ny = xs_nodes.size - 1, ys_nodes.size - 1
    X, Y = np.meshgrid(xs_nodes, ys_nodes)
    raw = SRH2DRawData()
    raw.node_coords = np.column_stack([X.ravel(), Y.ravel(), z_nodes.ravel()])
    node = lambda i, j: j * (nx + 1) + i  # noqa: E731
    raw.elem_nodes = [np.array([node(i, j), node(i + 1, j), node(i + 1, j + 1), node(i, j + 1)])
                      for j in range(ny) for i in range(nx)]
    raw.elem_material = np.zeros(nx * ny, dtype=np.int64)
    raw.manning_n = {0: float(manning)}
    return build_mesh(raw)


def setup(m: dict, tid: str, dx: float):
    """(mesh, h0 at cells, u0, v0, wse_still, t_end, output rows builder)."""
    prm = m["reference"]["generator"]["parameters"]
    t_end = float(m["simulation"]["t_end"])
    if tid.startswith(("A1F-010", "A1F-011")):
        if tid.startswith("A1F-010"):
            xmin, xmax, x0, hl, hr = 0.0, 2000.0, float(prm.get("x0", 1000.0)), float(prm.get("h0", 1.0)), 0.0
        else:
            xmin, xmax, x0, hl, hr = -1000.0, 1000.0, float(prm.get("x0", 0.0)), float(prm.get("hl", 1.0)), float(prm.get("hr", 0.1))
        n = int(round((xmax - xmin) / dx))
        xs = np.linspace(xmin, xmax, n + 1)
        ys = np.array([0.0, dx])
        mesh = quad_mesh(xs, ys, np.zeros((2, n + 1)))
        xc = mesh.cell_center[:, 0]
        h0 = np.where(xc < x0, hl, hr)
        return mesh, h0, 0 * h0, 0 * h0, 0.0, t_end, "strip"
    if tid.startswith("A2A-001"):
        from references.thacker import bed_elevation, depth_velocity

        dom = json.loads((Path(m["_case_dir"]) / "inputs/params.json").read_text())["domain"]
        nx = int(round((dom["xmax"] - dom["xmin"]) / dx))
        ny = int(round((dom["ymax"] - dom["ymin"]) / dx))
        xs = np.linspace(dom["xmin"], dom["xmax"], nx + 1)
        ys = np.linspace(dom["ymin"], dom["ymax"], ny + 1)
        X, Y = np.meshgrid(xs, ys)
        mesh = quad_mesh(xs, ys, bed_elevation(X, Y, prm["h0"], prm["L"]))
        xc, yc = mesh.cell_center[:, 0], mesh.cell_center[:, 1]
        r = depth_velocity(xc, yc, 0.0, h0=prm["h0"], L=prm["L"], eta=prm["eta"], g=prm.get("g", G))
        wet = r["h"] > 0
        # free surface over the cell's own (node-averaged) bed, so the start is the exact one in level
        zc = mesh.bed_elev
        zx = bed_elevation(xc, yc, prm["h0"], prm["L"])
        h0 = np.where(wet, np.maximum(r["h"] + zx - zc, 0.0), 0.0)
        return mesh, h0, np.where(wet, r["u"], 0.0), np.where(wet, r["v"], 0.0), 0.0, t_end, "field"
    raise KeyError(tid)


def to_rows(kind: str, mesh, t: float, h, u, v) -> dict:
    xc, yc = mesh.cell_center[:, 0], mesh.cell_center[:, 1]
    n = len(xc)
    nan = np.full(n, np.nan)
    if kind == "strip":
        return {"t": np.full(n, t), "x": xc, "y": nan.copy(), "h": h, "u": u, "v": nan.copy(), "p": nan.copy(), "Q": h * u}
    return {"t": np.full(n, t), "x": xc, "y": yc, "h": h, "u": u, "v": v, "p": nan.copy(), "z": np.asarray(mesh.bed_elev, float)}


def run_fvm(mesh, h0, u0, v0, wse_still, t_end):
    import torch

    from HydroNet.models.FVM_PINN._internal.fvm import compute_cell_geometry as ccg
    from HydroNet.models.FVM_PINN._internal.fvm import run_fvm_rk2

    md = ccg(mesh, device="cpu")
    bed = md["bed_elev"]
    h_still = (wse_still - bed).clamp(min=0.0).to(torch.float64)
    md["h_still"] = h_still
    md["bc_ghost"] = {}
    h0t = torch.tensor(h0, dtype=torch.float64)
    Q0 = torch.stack([h0t - h_still, h0t * torch.tensor(u0), h0t * torch.tensor(v0)], dim=-1)
    _, Q = run_fvm_rk2(Q0, md, h_still, [0.0, t_end], cfl=CFL, h_dry=H_DRY)
    q = Q[-1].numpy()
    h = np.maximum(q[:, 0] + h_still.numpy(), 0.0)
    wet = h > H_DRY
    u = np.where(wet, q[:, 1] / np.where(wet, h, 1.0), 0.0)
    v = np.where(wet, q[:, 2] / np.where(wet, h, 1.0), 0.0)
    return h, u, v


def run_pinn(mesh, h0, u0, v0, wse_still, t_end, epochs: int, workdir: Path):
    import torch

    from HydroNet import Config, FVM_PINNDataset, FVM_PINNTrainer, FVM_SWE_PINN

    np.random.seed(123456)
    torch.manual_seed(123456)  # as HydroNet's example
    cfg = workdir / "fvm_pinn_config.yaml"
    cfg.write_text(PINN_CONFIG.format(wse_still=wse_still, h_dry=H_DRY, t_end=t_end, epochs=epochs,
                                      ckpt=str(workdir / "checkpoints")), encoding="utf-8")
    config = Config(str(cfg))
    n = mesh.n_cells
    xc, yc = mesh.cell_center[:, 0], mesh.cell_center[:, 1]
    model = FVM_SWE_PINN(config)
    bed = np.asarray(mesh.bed_elev, float)
    h_still = np.maximum(wse_still - bed, 0.0)
    ic = {"xyt": torch.column_stack([torch.tensor(xc), torch.tensor(yc), torch.zeros(n, dtype=torch.float64)]),
          "U_true": torch.stack([torch.tensor(h0 - h_still), torch.tensor(h0 * u0), torch.tensor(h0 * v0)], dim=-1)}
    dataset = FVM_PINNDataset.from_mesh(config, mesh, ic_data=ic)
    trainer = FVM_PINNTrainer(model, dataset, config)
    trainer.train()
    xyt = torch.column_stack([torch.tensor(xc), torch.tensor(yc), torch.full((n,), t_end, dtype=torch.float64)])
    with torch.no_grad():
        q = model(xyt.to(model.get_device())).cpu().numpy()
    h = np.maximum(q[:, 0], 0.0)
    return h, np.where(h > H_DRY, q[:, 1], 0.0), np.where(h > H_DRY, q[:, 2], 0.0)


CASES = ("A1F-010", "A1F-011", "A2A-001")
LABEL = {"fvm": "finite volume (Roe, RK2)", "pinn": "FVM-PINN"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    ap.add_argument("--hydronet", type=Path, required=True, help="HydroNet source checkout")
    ap.add_argument("--mode", nargs="+", choices=list(LABEL), default=list(LABEL))
    ap.add_argument("--epochs", type=int, default=5000, help="FVM-PINN Adam epochs (HydroNet's example: 5000)")
    ap.add_argument("--version", default=None, help="HydroNet commit, for the score card")
    args = ap.parse_args()
    sys.path.insert(0, str(args.hydronet.resolve()))

    import torch
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    torch.set_default_dtype(torch.float64)
    version = args.version or "git"
    key = Ed25519PrivateKey.from_private_bytes(bytes([5] * 32))  # public development key
    for mode in args.mode:
        out = OUT / mode
        out.mkdir(parents=True, exist_ok=True)
        extra = f", {args.epochs} Adam epochs" if mode == "pinn" else f", CFL {CFL}"
        solver = {"name": f"HydroNet {LABEL[mode]} ({version})", "version": version,
                  "adapter": f"hydronet ({mode}; HydroNet dam-break example settings{extra}; h_dry {H_DRY:g} m)"}
        for tid in args.cases:
            m = load_manifest(tid, repo=REPO)
            paths = []
            for dx in sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True):
                t0 = time.perf_counter()
                mesh, h0, u0, v0, wse, t_end, kind = setup(m, tid, float(dx))
                with tempfile.TemporaryDirectory() as td:
                    cwd = os.getcwd()
                    os.chdir(td)
                    try:
                        h, u, v = (run_fvm(mesh, h0, u0, v0, wse, t_end) if mode == "fvm"
                                   else run_pinn(mesh, h0, u0, v0, wse, t_end, args.epochs, Path(td)))
                    finally:
                        os.chdir(cwd)
                print(f"  {mode} {tid} dx={dx}: {mesh.n_cells} cells, {time.perf_counter() - t0:.1f}s", flush=True)
                if not np.isfinite(h).all():
                    print(f"::warning title=HydroNet {mode} {tid}::unstable on the {dx:g} grid "
                          f"({int((~np.isfinite(h)).sum())} of {h.size} cells not finite); no score card", flush=True)
                    paths = []
                    break
                paths.append(write_results_parquet(out / f"{m['test_id']}_dx{dx:g}.parquet", to_rows(kind, mesh, t_end, h, u, v)))
            if not paths:
                continue
            card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{'PASS' if card['passed'] else 'FAIL'} {m['test_id']} ({solver['name']})")
            for r in card["criteria_results"]:
                print(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
            c = card.get("convergence_result") or {}
            print(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

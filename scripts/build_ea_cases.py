#!/usr/bin/env python3
"""Build the Environment Agency (SC120002) cases from the official data archive.

The archive published on GOV.UK (``Benchmarking_Model_Data.zip``) holds the
2010 test specifications, DEMs, boundary tables and output-point lists for
EA Tests 1–7. It holds **no reference results**: Tests 1–5 were judged by
comparing packages against each other, so they enter this suite as
*code inter-comparison* cases (``A2C-``), scored on objective expected states
that follow from the inputs alone:

- Test 1: the pond settles at the 10.25 m sill crest (specification §2);
  peak level 10.35 m while the boundary holds 10.35 m.
- Tests 2, 4, 5: every boundary except the inflow is closed and the bed starts
  dry, so stored volume at the end of the run equals the integral of the
  inflow hydrograph (linear interpolation, as the specification requires).

Test 6A is the UCL laboratory dam break (Soares-Frazão & Zech 2002 / IMPACT);
it enters as a laboratory validation draft (``A2L-EA6A``) whose DEM is real but
whose gauge measurements still have to be obtained.

Small text inputs (boundary tables, output points, case parameters) are
committed under OGL v3.0 with attribution. DEMs are not committed: each is
recorded with the archive URL, archive SHA-256, member path and file SHA-256,
and ``scripts/fetch_inputs.py`` retrieves and verifies them.

Usage::

    python scripts/build_ea_cases.py                     # downloads the archive
    python scripts/build_ea_cases.py --archive path/to/Benchmarking_Model_Data.zip
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
ARCHIVE_URL = (
    "https://assets.publishing.service.gov.uk/media/6033a9bbd3bf7f72182e99ca/"
    "Benchmarking_Model_Data.zip"
)
ARCHIVE_SHA256 = "388c2789570e5975fe909033e34bedbe5d7bde5e6d7f9b7d7c1eaf04e58bc732"
LANDING = (
    "https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/"
    "2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm"
)
REPORT_URL = (
    "https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/"
    "_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf"
)
OUT_ROOT = REPO / "test_catalog" / "track_a"

CITATION_2013 = {
    "authors": ["Néelz, S.", "Pender, G."],
    "year": 2013,
    "title": "Benchmarking the Latest Generation of 2D Hydraulic Modelling Packages",
    "report_number": "SC120002",
    "isbn": "978-1-84911-306-9",
    "url": LANDING,
}
CITATION_2010 = {
    "authors": ["Néelz, S.", "Pender, G."],
    "year": 2010,
    "title": "Benchmarking of 2D Hydraulic Modelling Packages",
    "report_number": "SC080035/SR2",
    "url": "https://assets.publishing.service.gov.uk/media/5a75765c40f0b6360e4744dd/scho0510bsno-e-e.pdf",
}
ENSEMBLE_NOTE = (
    "Published package results exist only as figures in the SC120002 report, whose text "
    "is 'All rights reserved … reproduced with prior permission of the Environment "
    "Agency'. They are shown for context once digitised with EA permission and never gate."
)
LICENSE_NOTE = (
    "Inputs come from the GOV.UK 'Benchmarking model data' archive, published under the "
    "Open Government Licence v3.0 (the page licence; the archive carries no other terms). "
    "Attribution: Environment Agency, SC120002 (2013), test specifications May 2010."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_archive(path: Path | None) -> bytes:
    if path is None:
        req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "benchmark1d2d"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = resp.read()
    else:
        data = path.read_bytes()
    got = sha256_bytes(data)
    if got != ARCHIVE_SHA256:
        raise SystemExit(f"archive SHA-256 mismatch: {got} != {ARCHIVE_SHA256}")
    return data


def member(outer: zipfile.ZipFile, inner_zip: str, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(outer.read(inner_zip))) as inner:
        return inner.read(name)


def read_asc(data: bytes) -> tuple[dict[str, float], np.ndarray]:
    text = data.decode("ascii", errors="replace").splitlines()
    hdr: dict[str, float] = {}
    for line in text[:6]:
        k, v = line.split()
        hdr[k.lower()] = float(v)
    z = np.loadtxt(text[6:])
    return hdr, z


def parse_csv(data: bytes) -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(data.decode("utf-8-sig"))) if row]


def inflow_volume(table: list[list[str]], t_end_s: float) -> float:
    """Integrate a (minutes, m3/s) table, linear interpolation, to t_end."""
    t = np.array([float(r[0]) * 60.0 for r in table[1:]])
    q = np.array([float(r[1]) for r in table[1:]])
    grid = np.union1d(t[t <= t_end_s], [t_end_s])
    return float(np.trapezoid(np.interp(grid, t, q), grid))


def remote_input(path: str, role: str, fmt: str, inner_zip: str, name: str, data: bytes, crs: str | None = None) -> dict:
    entry = {
        "path": path,
        "role": role,
        "format": fmt,
        "sha256": sha256_bytes(data),
        "committed": False,
        "source": {
            "url": ARCHIVE_URL,
            "archive_sha256": ARCHIVE_SHA256,
            "members": [inner_zip, name],
        },
    }
    if crs:
        entry["crs"] = crs
    return entry


def write_text(case_dir: Path, rel: str, data: bytes) -> dict:
    target = case_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": rel, "sha256": sha256_bytes(data)}


def write_json(case_dir: Path, rel: str, obj: dict) -> dict:
    data = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return write_text(case_dir, rel, data)


def probes_from(table: list[list[str]]) -> list[dict]:
    return [
        {"id": f"P{r[0]}" if r[0][0].isdigit() else r[0], "x": float(r[1]), "y": float(r[2]), "variables": ["h", "u", "v"]}
        for r in table[1:]
    ]


def base_manifest(test_id: str, title: str, description: str, test_class: str, status: str) -> dict:
    return {
        "schema_version": "1.1.0",
        "test_id": test_id,
        "case_version": "1.0.0",
        "status": status,
        "track": "A",
        "test_class": test_class,
        "title": title,
        "description": description,
    }


def provenance(extra_note: str) -> dict:
    return {
        "citations": [CITATION_2013, CITATION_2010],
        "license": "OGL-UK-3.0",
        "adaptation_notes": f"{LICENSE_NOTE} {extra_note}".strip(),
    }


def readme(case: dict, lines: list[str]) -> bytes:
    body = [f"# {case['test_id']} — {case['title']}", "", case["description"], ""]
    body += lines
    body += [
        "",
        "## Data and licence",
        "",
        LICENSE_NOTE,
        "",
        f"- Archive: <{ARCHIVE_URL}> (SHA-256 `{ARCHIVE_SHA256}`)",
        f"- Landing page: <{LANDING}>",
        f"- Report: <{REPORT_URL}>",
        "",
        "Fetch the non-committed inputs with `python scripts/fetch_inputs.py " + case["test_id"].split("_")[0] + "`.",
        "",
    ]
    return "\n".join(body).encode("utf-8")


def build(archive: bytes) -> list[str]:
    outer = zipfile.ZipFile(io.BytesIO(archive))
    built: list[str] = []
    ic_dir = OUT_ROOT / "2d_intercomparison"

    # ── Test 1 ──────────────────────────────────────────────────────────────
    z1, base1 = "Test1_dataset_2010.zip", "Test1 dataset 2010/"
    dem1 = member(outer, z1, base1 + "test1DEM.asc")
    bc1 = member(outer, z1, base1 + "Test1BC.csv")
    pts1 = member(outer, z1, base1 + "Test1output.csv")
    hdr, z = read_asc(dem1)
    cs = hdr["cellsize"]
    nr, nc = z.shape
    xc = hdr["xllcorner"] + cs * (np.arange(nc) + 0.5)
    yc = hdr["yllcorner"] + cs * (nr - 1 - np.arange(nr) + 0.5)
    X, Y = np.meshgrid(xc, yc)
    dom = (X > 0) & (X < 700) & (Y > 0) & (Y < 100)
    from scipy import ndimage

    lab, _ = ndimage.label(dom & (z < 10.25))
    pond = lab == lab[np.argmin(abs(yc - 50)), np.argmin(abs(xc - 400))]
    v_pond = float(((10.25 - z) * pond).sum() * cs * cs)
    v_rest = float((np.clip(9.7 - z, 0, None) * (dom & ~pond)).sum() * cs * cs)
    case = base_manifest(
        "A2C-EA1_disconnected_water_body",
        "EA Test 1 — flooding a disconnected water body",
        "700 m × 100 m sloping strip with a depression behind a 10.25 m sill. A water-level "
        "boundary rises from 9.7 m to 10.35 m, holds, then falls back; the pond must fill, "
        "become horizontal, and settle at the sill crest. Tests wetting/drying and "
        "disconnected water bodies.",
        "intercomparison",
        "candidate",
    )
    d = ic_dir / case["test_id"]
    if d.exists():
        shutil.rmtree(d)
    f_bc = write_text(d, "inputs/boundary_level.csv", bc1)
    f_pts = write_text(d, "inputs/output_points.csv", pts1)
    f_case = write_json(d, "inputs/case.json", {
        "domain": {"xmin": 0, "xmax": 700, "ymin": 0, "ymax": 100},
        "manning_n": 0.03, "grid_resolution_m": 10.0, "t_end_s": 72000,
        "initial_condition": {"water_level_m": 9.7},
        "boundaries": {"west": {"type": "water_level", "table": "boundary_level.csv", "time_units": "min"},
                        "others": "closed"},
        "outputs": {"probe_interval_s": 60, "probes": "output_points.csv"},
    })
    case["physics"] = {"dimensionality": "2D", "flow_type": "free_surface",
                       "governing_equations": ["shallow_water_2d"],
                       "phenomena": ["wet_dry", "disconnected_water_body", "inundation"]}
    case["provenance"] = provenance("Committed: boundary table, output points, case.json. DEM fetched by hash.")
    case["inputs"] = [
        remote_input("inputs/terrain.asc", "terrain", "esri_ascii_grid", z1, base1 + "test1DEM.asc", dem1, crs="local"),
        {**f_bc, "role": "boundary_condition", "format": "csv"},
        {**f_pts, "role": "probes", "format": "csv"},
        {**f_case, "role": "case_parameters", "format": "json"},
    ]
    case["reference"] = {
        "kind": "intercomparison",
        "expected_states": [
            {"id": "pond_final_level_p1", "variable": "h+z", "where": "P1", "time": 72000, "value": 10.25, "units": "m",
             "derivation": "Specification §2: after the boundary falls the pond becomes horizontal at the sill elevation, 10.25 m (sill crest at x = 300 m in the DEM)."},
            {"id": "pond_final_level_p2", "variable": "h+z", "where": "P2", "time": 72000, "value": 10.25, "units": "m",
             "derivation": "As P1; both points lie in the same pond."},
            {"id": "peak_level", "variable": "h+z", "where": "P1,P2", "value": 10.35, "units": "m",
             "derivation": "Boundary holds 10.35 m for 10 h (60–660 min), long enough for the whole domain to become horizontal (specification §2)."},
            {"id": "final_stored_volume", "variable": "volume", "time": 72000, "value": round(v_pond + v_rest, 1), "units": "m3",
             "derivation": f"Pond below 10.25 m ({v_pond:.1f} m³) plus water below 9.7 m elsewhere ({v_rest:.1f} m³), integrated on the 2 m EA DEM. Solvers on a 10 m grid sample the DEM differently, so this check does not gate."},
        ],
        "ensemble": {"source": "SC120002 report, Test 1 figures", "availability": "permission_required", "notes": ENSEMBLE_NOTE},
    }
    case["simulation"] = {"t_end": 72000.0, "output_interval": 60.0, "required_outputs": ["h", "u", "v"],
                          "probes": probes_from(parse_csv(pts1))}
    case["scoring"] = {"pass_rule": "all_gating", "criteria": [
        {"id": "final_level_p1", "metric": "expected_state_error", "against": "pond_final_level_p1", "variable": "h", "where": "P1",
         "threshold": {"op": "abs<=", "value": 0.02, "units": "m"}, "gating": True,
         "rationale": "A solver that conserves mass and handles the sill must leave the pond at the crest level; 2 cm allows for slow drainage over the sill by t = 20 h."},
        {"id": "final_level_p2", "metric": "expected_state_error", "against": "pond_final_level_p2", "variable": "h", "where": "P2",
         "threshold": {"op": "abs<=", "value": 0.02, "units": "m"}, "gating": True,
         "rationale": "As P1."},
        {"id": "peak_level", "metric": "expected_state_error", "against": "peak_level", "variable": "h", "where": "P1,P2",
         "threshold": {"op": "abs<=", "value": 0.02, "units": "m"}, "gating": True,
         "rationale": "Hydrostatic plateau level during the 10 h hold."},
        {"id": "final_volume", "metric": "expected_state_error", "against": "final_stored_volume", "variable": "volume",
         "threshold": {"op": "abs<=", "value": 2.0, "units": "%"}, "gating": False,
         "rationale": "Informational: depends on how the solver samples the 2 m DEM onto its own grid."},
    ]}
    (d / "manifest.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "README.md").write_bytes(readme(case, [
        "| Parameter | Value |", "|---|---|", "| Manning's n | 0.03 |", "| Grid | 10 m (DEM 2 m) |",
        "| Run time | 20 h |", "| Initial level | 9.7 m |", f"| Settled pond volume | {v_pond:,.0f} m³ |",
    ]))
    built.append(case["test_id"])

    # ── Tests 2, 4, 5: closed domains, volume = inflow integral ─────────────
    specs = [
        {
            "n": 2, "id": "A2C-EA2_floodplain_depressions", "title": "EA Test 2 — filling of floodplain depressions",
            "desc": "2 km × 2 km floodplain with a 4 × 4 grid of ~0.5 m deep depressions; a 20 m³/s, ~85 min "
                    "hydrograph enters along 100 m of the north-west edge and the run continues to 48 h. "
                    "Tests low-momentum filling and final inundation extent.",
            "zip": "Test2_dataset_2010.zip", "base": "Test2 dataset 2010/", "dem": "test2DEM.asc", "bc": "Test2_BC.csv",
            "pts": "Test2output.csv", "n_mann": 0.03, "grid": 20.0, "t_end": 172800.0, "dt_out": 300.0,
            "inflow_line": [[0.0, 2000.0], [0.0, 1900.0]], "domain": {"xmin": 0, "xmax": 2000, "ymin": 0, "ymax": 2000},
            "phen": ["wet_dry", "storage", "low_momentum_flow", "inundation"], "crs": "local",
        },
        {
            "n": 4, "id": "A2C-EA4_flood_propagation_speed", "title": "EA Test 4 — speed of flood propagation over an extended floodplain",
            "desc": "Flat, horizontal 1000 m × 2000 m floodplain at 0 m; a breach hydrograph peaking at 20 m³/s "
                    "enters along a 20 m line mid-way along the west edge. Tests front celerity and transient "
                    "depths and velocities at the leading edge.",
            "zip": "Test4_dataset_2010.zip", "base": "Test4 dataset 2010/", "dem": None, "bc": "Test4BC.csv",
            "pts": "Test4output.csv", "n_mann": 0.05, "grid": 5.0, "t_end": 18000.0, "dt_out": 20.0,
            "inflow_line": [[0.0, 990.0], [0.0, 1010.0]], "domain": {"xmin": 0, "xmax": 1000, "ymin": 0, "ymax": 2000},
            "phen": ["wet_dry", "front_propagation", "inundation"], "crs": "local",
        },
        {
            "n": 5, "id": "A2C-EA5_valley_flooding", "title": "EA Test 5 — valley flooding",
            "desc": "Dam-failure hydrograph (peak 3000 m³/s) released down a ~17 km valley whose slope eases from "
                    "~0.01 to ~0.001, producing both super- and subcritical flow, run to 30 h. Tests peak levels, "
                    "velocities and travel times.",
            "zip": "Test5_dataset_2010.zip", "base": "Test5 dataset 2010/", "dem": "Test5DEM.asc", "bc": "Test5BC.csv",
            "pts": "Test5output.csv", "n_mann": 0.04, "grid": 50.0, "t_end": 108000.0, "dt_out": 60.0,
            "inflow_line": [[232595.0, 830480.0], [232785.0, 830290.0]], "domain": None,
            "phen": ["wet_dry", "transcritical", "dam_break", "inundation"], "crs": "EPSG:27700",
        },
    ]
    for sp in specs:
        bc = member(outer, sp["zip"], sp["base"] + sp["bc"])
        pts = member(outer, sp["zip"], sp["base"] + sp["pts"])
        vol = inflow_volume(parse_csv(bc), sp["t_end"])
        case = base_manifest(sp["id"], sp["title"], sp["desc"], "intercomparison", "candidate")
        d = ic_dir / case["test_id"]
        if d.exists():
            shutil.rmtree(d)
        f_bc = write_text(d, "inputs/inflow.csv", bc)
        f_pts = write_text(d, "inputs/output_points.csv", pts)
        params = {
            "manning_n": sp["n_mann"], "grid_resolution_m": sp["grid"], "t_end_s": sp["t_end"],
            "initial_condition": "dry bed",
            "boundaries": {"inflow": {"type": "discharge", "table": "inflow.csv", "time_units": "min",
                                      "interpolation": "linear", "line": sp["inflow_line"]}, "others": "closed"},
            "outputs": {"probe_interval_s": sp["dt_out"], "probes": "output_points.csv"},
        }
        if sp["domain"]:
            params["domain"] = sp["domain"]
        if sp["dem"] is None:
            params["terrain"] = {"type": "flat", "elevation_m": 0.0}
        if sp["dem"]:
            shp = member(outer, sp["zip"], sp["base"] + f"Test{sp['n']}ActiveArea_region.shp")
            f_shp = write_text(d, "inputs/active_area.shp", shp)
            params["active_area"] = "active_area.shp (ESRI polygon, same CRS as the DEM)"
        f_case = write_json(d, "inputs/case.json", params)
        inputs = []
        if sp["dem"]:
            dem = member(outer, sp["zip"], sp["base"] + sp["dem"])
            inputs.append(remote_input("inputs/terrain.asc", "terrain", "esri_ascii_grid", sp["zip"], sp["base"] + sp["dem"], dem, crs=sp["crs"]))
        if sp["dem"]:
            inputs.append({**f_shp, "role": "active_area", "format": "shp"})
        inputs += [
            {**f_bc, "role": "boundary_condition", "format": "csv"},
            {**f_pts, "role": "probes", "format": "csv"},
            {**f_case, "role": "case_parameters", "format": "json"},
        ]
        case["physics"] = {"dimensionality": "2D", "flow_type": "free_surface",
                           "governing_equations": ["shallow_water_2d"], "phenomena": sp["phen"]}
        case["provenance"] = provenance(
            "Committed: inflow table, output points, active-area polygon, case.json." + (" DEM fetched by hash." if sp["dem"] else " No DEM: the bed is flat at 0 m (specification §6).")
        )
        case["inputs"] = inputs
        case["reference"] = {
            "kind": "intercomparison",
            "expected_states": [
                {"id": "final_stored_volume", "variable": "volume", "time": sp["t_end"], "value": round(vol, 1), "units": "m3",
                 "derivation": "Closed boundaries and a dry initial bed: stored volume at the end of the run equals the "
                               "linearly interpolated inflow hydrograph integrated to t_end."},
            ],
            "ensemble": {"source": f"SC120002 report, Test {sp['n']} figures", "availability": "permission_required", "notes": ENSEMBLE_NOTE},
        }
        case["simulation"] = {"t_end": sp["t_end"], "output_interval": sp["dt_out"], "required_outputs": ["h", "u", "v"],
                              "probes": probes_from(parse_csv(pts))}
        case["scoring"] = {"pass_rule": "all_gating", "criteria": [
            {"id": "mass_conservation", "metric": "expected_state_error", "against": "final_stored_volume", "variable": "volume",
             "threshold": {"op": "abs<=", "value": 0.1, "units": "%"}, "gating": True,
             "rationale": "The only exact statement the test admits: nothing leaves a closed domain, so any difference is mass created or lost by the scheme (suite target < 0.1 %)."},
        ]}
        (d / "manifest.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (d / "README.md").write_bytes(readme(case, [
            "| Parameter | Value |", "|---|---|", f"| Manning's n | {sp['n_mann']} |", f"| Grid | {sp['grid']:g} m |",
            f"| Run time | {sp['t_end'] / 3600:g} h |", f"| Inflow volume to t_end | {vol:,.0f} m³ |",
            "", "Probe levels and velocities are compared with the published package spread for context only.",
        ]))
        built.append(case["test_id"])

    # ── Test 6A: laboratory dam break (UCL / IMPACT) ────────────────────────
    z6, base6 = "Test6_dataset_2010.zip", "Test6 dataset 2010/"
    dem6 = member(outer, z6, base6 + "Test6ADEM.asc")
    pts6 = member(outer, z6, base6 + "Test6Aoutput.csv")
    case = base_manifest(
        "A2L-EA6A_dambreak_isolated_building",
        "EA Test 6A — dam break past an isolated building (laboratory scale)",
        "UCL laboratory dam break through a 1 m gate against a single idealised building "
        "(Soares-Frazão & Zech 2002, IMPACT), as adopted by the Environment Agency. "
        "Tests hydraulic jumps and the wake behind an obstacle against gauge measurements.",
        "validation_lab",
        "draft",
    )
    d = OUT_ROOT / "2d_laboratory" / case["test_id"]
    if d.exists():
        shutil.rmtree(d)
    f_pts = write_text(d, "inputs/output_points.csv", pts6)
    f_case = write_json(d, "inputs/case.json", {
        "manning_n": 0.01, "grid_resolution_m": 0.1, "t_end_s": 120.0,
        "initial_condition": {"depth_upstream_m": 0.4, "depth_downstream_m": 0.02, "dam_at_x_m": 0.0},
        "boundaries": "all vertical walls",
        "outputs": {"probe_interval_s": 0.1, "probes": "output_points.csv"},
    })
    case["physics"] = {"dimensionality": "2D", "flow_type": "free_surface", "governing_equations": ["shallow_water_2d"],
                       "phenomena": ["dam_break", "hydraulic_jump", "obstacle_wake", "wet_dry"]}
    case["provenance"] = {
        "citations": [
            {"authors": ["Soares-Frazão, S.", "Zech, Y."], "year": 2007,
             "title": "Experimental study of dam-break flow against an isolated obstacle", "doi": "10.1080/00221686.2007.9521830"},
            CITATION_2013,
        ],
        "license": "OGL-UK-3.0",
        "adaptation_notes": LICENSE_NOTE + " Gauge measurements (G1–G6) are not in the EA archive; they come from the "
                            "IMPACT programme / Soares-Frazão & Zech (2007) and need redistribution terms before the case can leave draft.",
    }
    case["inputs"] = [
        remote_input("inputs/terrain.asc", "terrain", "esri_ascii_grid", z6, base6 + "Test6ADEM.asc", dem6, crs="local"),
        {**f_pts, "role": "probes", "format": "csv"},
        {**f_case, "role": "case_parameters", "format": "json"},
    ]
    case["reference"] = {
        "kind": "measured", "data_path": "reference/gauges.parquet", "availability": "request_from_authors",
        "uncertainty": {"type": "absolute", "value": 0.005, "units": "m",
                        "notes": "Provisional: replace with the gauge accuracy stated by Soares-Frazão & Zech (2007)."},
        "include_measurement_uncertainty": True,
    }
    case["simulation"] = {"t_end": 120.0, "output_interval": 0.1, "required_outputs": ["h", "u", "v"],
                          "probes": probes_from(parse_csv(pts6))}
    case["scoring"] = {"pass_rule": "all_gating", "criteria": [
        {"id": "gauge_nse", "metric": "NSE", "variable": "h", "where": "G1-G5", "threshold": {"op": ">=", "value": 0.7, "units": "1"},
         "gating": True, "rationale": "Provisional; set from measurement uncertainty once gauge data are obtained."},
        {"id": "front_arrival", "metric": "arrival_time_error", "variable": "h", "where": "G1-G5",
         "threshold": {"op": "abs<=", "value": 0.5, "units": "s"}, "gating": True,
         "rationale": "Provisional; five output steps at the specified 0.1 s frequency."},
    ]}
    (d / "manifest.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "README.md").write_bytes(readme(case, [
        "| Parameter | Value |", "|---|---|", "| Manning's n | 0.01 |", "| Grid | 0.1 m (DEM 0.05 m) |",
        "| Run time | 2 min |", "| Initial depths | 0.4 m upstream, 0.02 m downstream |",
        "", "**Status: draft** — the DEM and gauge locations are real; gauge measurements still have to be obtained.",
    ]))
    built.append(case["test_id"])
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--archive", type=Path, default=None, help="local copy of Benchmarking_Model_Data.zip")
    args = ap.parse_args()
    for tid in build(load_archive(args.archive)):
        print("built", tid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

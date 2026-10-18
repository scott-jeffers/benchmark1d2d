#!/usr/bin/env python3
"""Score HEC-RAS 2D (USACE) on the dam-break cases, built and run headless.

HEC-RAS 2D needs three things that are normally made by hand in RAS Mapper: a
terrain, a computational mesh and (for a dam break) a water surface that is
not flat at the start. All three are made here without the GUI:

* **Terrain** — a GeoTIFF of the bed is turned into a HEC-RAS terrain with
  HEC-RAS's own ``RasProcess.exe CreateTerrain`` and associated with the
  geometry through RasMapperLib (``ras-commander``).
* **Mesh** — HEC-RAS builds its mesh from the cell-centre seed points stored in
  the geometry text (``Storage Area 2D Points``). Seeds on a regular grid at
  the case's spacing give square cells, the same grid every other solver uses.
* **Initial step** — HEC-RAS 2D starts from one flat water level per area, a
  restart ("hot start") file, or earlier results. A short still-water run
  writes a restart file at the upstream level; the cells downstream of the dam
  are then set to the downstream level (or dry) in that file, and the dam-break
  run starts from it. HEC-RAS's own restart mechanism carries the step in.

The 2D equation set is the full shallow-water one (SWE, HEC-RAS's default
SWE-ELM variant); time step by HEC-RAS's Courant control; friction as close
to the reference's zero as HEC-RAS allows (n = 0.0001). Everything else is HEC-RAS's default.

Usage (Windows, HEC-RAS 6.6, ``ras-commander``, ``pythonnet``)::

    python scripts/run_hecras_2d.py --accept-hec-terms [--probe] [CASE ...]

``--probe`` runs the coarsest level of the first case and prints the files and
HDF layouts HEC-RAS produced at each step (diagnostics for porting to a new
HEC-RAS version).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]

TAG = os.environ.get("HECRAS_TAG", "")  # "" for the current release, "66" for HEC-RAS 6.6 (kept as the previous release)
OUT = REPO / "out" / (f"hecras{TAG}_2d" if TAG else "hecras2d")
from benchmark1d2d.clock import run_timestamp  # noqa: E402

TS = run_timestamp()  # when this run happened (BENCH_TIMESTAMP pins it)
G = 9.81
AREA = "Strip"
# Projected coordinates (UTM 18N, metres); the case's x/y are offsets from here.
X0, Y0 = 500_000.0, 4_000_000.0
EPSG = 26918
PRJ_WKT = ('PROJCS["NAD_1983_UTM_Zone_18N",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
           'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
           'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],'
           'PARAMETER["Central_Meridian",-75.0],PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
           'UNIT["Meter",1.0]]')
START = "01JAN2000"
# HEC-RAS's two full shallow-water options: Eulerian-Lagrangian (the default
# when SWE is chosen) and Eulerian, which HEC recommends for dam breaks.
EQUATIONS = {"elm": (1, "SWE-ELM"), "em": (2, "SWE-EM")}
# HEC-RAS refuses a Manning n of zero ("Face(s) have a zero Manning N value").
# n = 0.0001 adds a friction slope below 1e-7 at the dam breaks' depths and
# speeds: negligible against the tolerances, so the runs stay frictionless.
N_MIN = 0.0001


def log(msg: str) -> None:
    print(msg, flush=True)


def _crlf(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\r\n")


# ── project files ───────────────────────────────────────────────────────────


def write_geotiff(path: Path, z: np.ndarray, xmin: float, ymax: float, cell: float) -> None:
    """Float32 GeoTIFF (north-up) with the projection given by EPSG code."""
    import tifffile

    geokeys = [1, 1, 0, 3,
               1024, 0, 1, 1,      # GTModelTypeGeoKey = projected
               1025, 0, 1, 1,      # GTRasterTypeGeoKey = PixelIsArea
               3072, 0, 1, EPSG]   # ProjectedCSTypeGeoKey
    tifffile.imwrite(
        path, z.astype(np.float32),
        extratags=[(33550, "d", 3, (cell, cell, 0.0), False),
                   (33922, "d", 6, (0.0, 0.0, 0.0, xmin, ymax, 0.0), False),
                   (34735, "H", len(geokeys), geokeys, False)],
    )


def write_project(folder: Path, name: str, title: str, plans: list[str], flows: list[str]) -> Path:
    prj = folder / f"{name}.prj"
    _crlf(prj, [f"Proj Title={title}", f"Current Plan=p{plans[0]}", "Default Exp/Contr=0.3,0.1", "SI Units",
                "Geom File=g01", *[f"Unsteady File=u{u}" for u in flows], *[f"Plan File=p{p}" for p in plans],
                "Y Axis Title=Elevation", "X Axis Title(PF)=Main Channel Distance", "X Axis Title(XS)=Station",
                "BEGIN DESCRIPTION:", title, "END DESCRIPTION:", "DSS Start Date=", "DSS Start Time=",
                "DSS End Date=", "DSS End Time=", "DSS File=dss", "DXF Filename=", "GIS Export Profiles= 0 "])
    return prj


def write_rasmap(folder: Path, name: str) -> None:
    (folder / f"{name}.rasmap").write_text(f"""<RASMapper>
  <Version>2.0.0</Version>
  <RASProjectionFilename Filename=".\\Terrain\\Projection.prj" />
  <Geometries>
    <Layer Name="{name}" Type="RASGeometry" Filename=".\\{name}.g01.hdf">
      <Layer Type="RASD2FlowArea" Checked="True" />
    </Layer>
  </Geometries>
  <Results />
  <MapLayers />
  <Terrains Checked="True">
    <Layer Name="Terrain" Type="TerrainLayer" Checked="True" Filename=".\\Terrain\\Terrain.hdf">
      <ResampleMethod>near</ResampleMethod>
      <Surface On="True" />
    </Layer>
  </Terrains>
  <Units>SI Units</Units>
  <RenderMode>sloping</RenderMode>
</RASMapper>
""", encoding="utf-8")


def _xy16(x: float, y: float) -> str:
    return f"{x:16.6f}{y:16.6f}"


def write_geometry(path: Path, title: str, xmin: float, xmax: float, ymin: float, ymax: float, dx: float, n: float) -> int:
    """One 2D flow area over the rectangle, seeds at the regular cell centres."""
    X0r, X1r, Y0r, Y1r = X0 + xmin, X0 + xmax, Y0 + ymin, Y0 + ymax
    perim = [(X0r, Y1r), (X1r, Y1r), (X1r, Y0r), (X0r, Y0r), (X0r, Y1r)]
    xs = X0 + np.arange(xmin + dx / 2, xmax - dx / 4, dx)
    ys = Y0 + np.arange(ymin + dx / 2, ymax - dx / 4, dx)
    seeds = [(x, y) for y in ys[::-1] for x in xs]
    seed_lines = ["".join(_xy16(*p) for p in seeds[i:i + 2]) for i in range(0, len(seeds), 2)]
    cx, cy = (X0r + X1r) / 2, (Y0r + Y1r) / 2
    lines = [f"Geom Title={title}", "Program Version=6.60",
             f"Viewing Rectangle= {X0r - dx} , {X1r + dx} , {Y1r + dx} , {Y0r - dx} ", "",
             f"Storage Area={AREA:<16},{cx},{cy}", f"Storage Area Surface Line= {len(perim)} ",
             *[_xy16(*p) for p in perim],
             "Storage Area Type= 0 ", "Storage Area Area=", "Storage Area Min Elev=", "Storage Area Is2D=-1",
             f"Storage Area Point Generation Data=,,{dx:g},{dx:g}", f"Storage Area 2D Points= {len(seeds)} ",
             *seed_lines,
             "Storage Area 2D PointsPerimeterTime=01Jan2000 00:00:00", f"Storage Area Mannings={n:g}",
             "2D Cell Volume Filter Tolerance=0.003", "2D Cell Minimum Area Fraction=0.01",
             "2D Face Profile Filter Tolerance=0.003", "2D Face Area Elevation Profile Filter Tolerance=0.003",
             "2D Face Area Elevation Conveyance Ratio=0.02", "2D Face Area Laminar Depth=0.2", "",
             "LCMann Time=Dec/30/1899 00:00:00", "LCMann Region Time=Dec/30/1899 00:00:00", "LCMann Table=0",
             "Chan Stop Cuts=-1", "", ""]
    _crlf(path, lines)
    return len(seeds)


def write_unsteady(path: Path, title: str, ic_level: float | None, restart: str | None) -> None:
    lines = [f"Flow Title={title}", "Program Version=6.60"]
    if restart:
        lines += ["Use Restart=-1 ", f"Restart Filename={restart}"]
    else:
        lines += ["Use Restart= 0 "]
        if ic_level is not None:
            lines += [f"Initial Storage Elev={AREA:<16},{ic_level:g}"]
    lines += ["Precipitation Mode=Disable", "Wind Mode=No Wind Forces", "Air Density Mode=",
              "Met BC=Precipitation|Mode=None", "Met BC=Evapotranspiration|Mode=None"]
    _crlf(path, lines)


def write_plan(path: Path, title: str, short: str, flow: str, t0: str, t1: str, dt: str, out_dt: str,
               write_restart: bool, eq_code: int = 1, end_date: str = START, map_dt: str | None = None) -> None:
    eq = f"UNET D2 Equation= {eq_code} "  # 1 = SWE-ELM, 2 = SWE-EM (full shallow-water equations)
    area_block = ["UNET D2 Coriolis=0", "UNET D2 Theta= 1 ", "UNET D2 Theta Warmup= 1 ", "UNET D2 Z Tol= 0.01 ",
                  "UNET D2 Volume Tol= 0.01 ", "UNET D2 Max Iterations= 20 ", eq, "UNET D2 TotalICTime=",
                  "UNET D2 RampUpFraction=0.1", "UNET D2 TimeSlices= 1 ", "UNET D2 Turbulence Formulation=None",
                  "UNET D2 Eddy Viscosity=", "UNET D2 Transverse Eddy Viscosity=", "UNET D2 Smagorinsky Mixing=",
                  "UNET D2 BCVolumeCheck=0", "UNET D2 Latitude=", "UNET D2 Cores=0",
                  "UNET D2 SolverType=Pardiso (Direct)"]
    lines = [f"Plan Title={title}", "Program Version=6.60", f"Short Identifier={short:<12}",
             f"Simulation Date={START},{t0},{end_date},{t1}", "Geom File=g01", f"Flow File=u{flow}",
             "Subcritical Flow", "K Sum by GR= 0 ", "Std Step Tol= 0.01 ", "Critical Tol= 0.01 ",
             "Num of Std Step Trials= 20 ", "Max Error Tol= 0.3 ", "Flow Tol Ratio= 0.001 ",
             "Split Flow NTrial= 30 ", "Split Flow Tol= 0.02 ", "Split Flow Ratio= 0.02 ", "Log Output Level= 0 ",
             "Friction Slope Method= 1 ", "Unsteady Friction Slope Method= 2 ",
             "Unsteady Bridges Friction Slope Method= 1 ", "Parabolic Critical Depth", "Global Vel Dist= 0 , 0 , 0 ",
             "Global Log Level= 0 ", "CheckData=True", "Encroach Param=-1 ,0,0, 0 ",
             f"Computation Interval={dt}", f"Output Interval={out_dt}", "Instantaneous Interval=1HOUR",
             f"Mapping Interval={map_dt or out_dt}",
             "Computation Time Step Use Courant=        -1", "Computation Time Step Use Time Series=    0",
             "Computation Time Step Max Courant=1", "Computation Time Step Min Courant=0.45",
             "Computation Time Step Count To Double=4", "Computation Time Step Max Doubling=3",
             "Computation Time Step Max Halving=6", "Computation Time Step Residence Courant=0",
             "Run HTab=-1 ", "Run UNet=-1 ", "Run Sediment= 0 ", "Run PostProcess= 0 ", "Run WQNet= 0 ",
             "Run RASMapper= 0 ", "UNET Theta= 1 ", "UNET Theta Warmup= 1 ", "UNET ZTol= 0.02 ", "UNET ZSATol= 0.02 ",
             "UNET QTol=", "UNET MxIter= 20 ", "UNET Max Iter WO Improvement= 0 ", "UNET MaxInSteps= 0 ",
             "UNET DtIC= 0 ", "UNET DtMin= 0 ", "UNET MaxCRTS= 20 ", "UNET WFStab= 2 ", "UNET SFStab= 1 ",
             "UNET WFX= 1 ", "UNET SFX= 1 ", f"UNET Gravity={G}", "UNET 1D Methodology=Finite Difference",
             "UNET DSS MLevel= 4 ", "UNET Pardiso=0", "UNET DZMax Abort= 100 ", "UNET Use Existing IB Tables=-1 ",
             "UNET Froude Reduction=False", "UNET Froude Limit= 1 ", "UNET Froude Power= 10 ", "UNET D1 Cores= 0 ",
             *area_block, f"UNET D2 Name={AREA}", *area_block,
             "UNET D1D2 MaxIter= 0 ", "UNET D1D2 ZTol=0.02", "UNET D1D2 QTol=1", "UNET D1D2 MinQTol=",
             "DSS File=dss",
             f"Write IC File={'-1' if write_restart else ' 0 '}", "Write IC File at Fixed DateTime=0", "IC Time=,,",
             "Write IC File Reoccurance=", f"Write IC File at Sim End={'-1' if write_restart else '0'}",
             "Echo Input=False", "Echo Parameters=False", "Echo Output=False", "Write Detailed= 0 ",
             "HDF Write Warmup=0", "HDF Write Time Slices=0", "HDF Flush=0",
             "HDF Additional Output Variable=Cell Velocity", "HDF Additional Output Variable=Face Flow",
             "HDF Compression= 1 ", "HDF Chunk Size= 1 ", "HDF Spatial Parts= 1 ", "HDF Use Max Rows=0",
             "HDF Fixed Rows= 1 "]
    _crlf(path, lines)


# ── HEC-RAS steps ───────────────────────────────────────────────────────────


def create_terrain(folder: Path, ras_dir: Path, z: np.ndarray, xmin: float, ymax: float, cell: float) -> Path:
    tdir = folder / "Terrain"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "Projection.prj").write_text(PRJ_WKT, encoding="ascii")
    tif = tdir / "bed.tif"
    write_geotiff(tif, z, X0 + xmin, Y0 + ymax, cell)
    out = tdir / "Terrain.hdf"
    cmd = [str(ras_dir / "RasProcess.exe"), "CreateTerrain", "units=Meters", "stitch=true",
           f"prj={(tdir / 'Projection.prj').resolve()}", f"out={out.resolve()}", str(tif.resolve())]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ras_dir), timeout=600)
    log(f"    CreateTerrain exit {p.returncode}: {p.stdout[-800:]} {p.stderr[-800:]}")
    if not out.exists():
        raise RuntimeError("CreateTerrain wrote no terrain HDF")
    return out


def h5_tree(path: Path, limit: int = 400, skip: tuple = ("Geometry",)) -> str:
    import h5py

    rows = []
    with h5py.File(path, "r") as f:
        def visit(name, obj):
            if len(rows) >= limit or name.split("/")[0] in skip:
                return
            if isinstance(obj, h5py.Dataset):
                rows.append(f"      {name} {obj.shape} {obj.dtype}")
            else:
                attrs = {k: (v if np.size(v) < 6 else f'<{np.size(v)}>') for k, v in obj.attrs.items()}
                rows.append(f"      {name}/ {attrs}"[:400])
        f.visititems(visit)
        rows.insert(0, f"      / {dict(f.attrs)}"[:400])
    return "\n".join(rows)


def listing(folder: Path) -> str:
    return "\n".join(f"      {p.relative_to(folder)} ({p.stat().st_size} B)" for p in sorted(folder.rglob("*")) if p.is_file())


def messages(folder: Path) -> str:
    """HEC-RAS's compute messages: text files, the .bco log and the plan HDF summary."""
    import h5py

    out = []
    for p in sorted(folder.glob("*.comp_msgs.txt")) + sorted(folder.glob("*.computeMsgs.txt")) + sorted(folder.glob("*.bco*")):
        out.append(f"    --- {p.name}\n" + p.read_text(errors="replace")[-4000:])
    for p in sorted(folder.glob("*.p0?.hdf")):
        try:
            with h5py.File(p, "r") as f:
                msg = f["Results/Summary/Compute Messages (text)"][0]
                out.append(f"    --- {p.name} compute messages\n" + msg.decode(errors="replace"))
        except Exception as exc:  # noqa: BLE001
            out.append(f"    --- {p.name}: no compute messages ({exc})")
    return "\n".join(out)


def compute(folder: Path, ras_exe: Path, plan: str, timeout: float) -> Path | None:
    from ras_commander import RasCmdr, init_ras_project

    from benchmark1d2d import keep

    tid, _, lvl = folder.name.partition("_dx")
    keep.inputs(f"hecras{TAG}-em" if folder.parent.name == "em" else f"hecras{TAG}", tid, folder, float(lvl) if lvl else None)

    ras = init_ras_project(folder, str(ras_exe))
    try:
        r = RasCmdr.compute_plan(plan, ras_object=ras, max_runtime=timeout)
        log(f"    compute_plan({plan}): {r!r}"[:800])
    except Exception as exc:  # noqa: BLE001
        log(f"    compute_plan({plan}) raised {type(exc).__name__}: {exc}"[:1500])
    hdf = next(iter(sorted(folder.glob(f"*.p{plan}.hdf"))), None)
    return hdf


def preprocess_and_associate(folder: Path, ras_exe: Path, terrain: Path) -> None:
    from ras_commander import init_ras_project

    ras = init_ras_project(folder, str(ras_exe))
    try:
        from ras_commander.geom.GeomPreprocessor import GeomPreprocessor

        r = GeomPreprocessor.run_geometry_preprocessor("01", ras_object=ras, max_wait=600)
        log(f"    geometry preprocessor: success={getattr(r, 'success', '?')} {getattr(r, 'error', '')} "
            f"{getattr(r, 'first_error_line', '')}"[:1500])
    except Exception as exc:  # noqa: BLE001
        log(f"    geometry preprocessor raised {type(exc).__name__}: {exc}"[:1500])
    g = next(iter(folder.glob("*.g01.hdf")), None)
    log(f"    g01.hdf: {g}")
    if g is None:
        return
    try:
        from ras_commander.geom.GeomMesh import GeomMesh

        GeomMesh.set_geometry_association("01", terrain_hdf_path=terrain, ras_object=ras)
        log("    terrain associated")
    except Exception as exc:  # noqa: BLE001
        log(f"    set_geometry_association raised {type(exc).__name__}: {exc}"[:1500])
        import h5py

        with h5py.File(g, "a") as f:
            gg = f.require_group("Geometry")
            gg.attrs["Terrain Filename"] = np.bytes_(".\\Terrain\\Terrain.hdf")
            gg.attrs["Terrain Layername"] = np.bytes_("Terrain")
        log("    terrain association written directly to /Geometry attributes")
    try:
        from ras_commander.geom.GeomMesh import GeomMesh

        ok = GeomMesh.compute_property_tables("01", ras_object=ras)
        log(f"    property tables: {ok}")
    except Exception as exc:  # noqa: BLE001
        log(f"    compute_property_tables raised {type(exc).__name__}: {exc}"[:1500])


# ── dam break ───────────────────────────────────────────────────────────────


def dam_break_params(m: dict, tid: str):
    p = m["reference"]["generator"]["parameters"]
    if tid.startswith("A1F-010"):
        return 0.0, 2000.0, float(p.get("x0", 1000.0)), float(p.get("h0", 1.0)), 0.0
    return -1000.0, 1000.0, float(p.get("x0", 0.0)), float(p.get("hl", 1.0)), float(p.get("hr", 0.1))


def _clock(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:02d}{(s % 3600) // 60:02d}"


def run_dam_break(m: dict, tid: str, dx: float, ras_exe: Path, probe: bool, eq: str = "elm") -> dict:
    import h5py

    xmin, xmax, x0, hl, hr = dam_break_params(m, tid)
    ymin, ymax = 0.0, 2 * dx
    t_end = float(m["simulation"]["t_end"])
    folder = OUT / "work" / eq / f"{tid}_dx{dx:g}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    name = "DamBreak"
    write_project(folder, name, f"{tid} dx={dx:g}", ["01", "02"], ["01", "02"])
    write_rasmap(folder, name)
    nseed = write_geometry(folder / f"{name}.g01", f"{tid} strip", xmin, xmax, ymin, ymax, dx, N_MIN)
    cell = min(dx / 2, 1.0)
    nx, ny = int(round((xmax - xmin + 4 * dx) / cell)), int(round((ymax - ymin + 4 * dx) / cell))
    terrain = create_terrain(folder, ras_exe.parent, np.zeros((ny, nx)), xmin - 2 * dx, ymax + 2 * dx, cell)
    # 1) still water at the upstream level for one minute; restart file written at the end
    write_unsteady(folder / f"{name}.u01", "still water", hl, None)
    write_plan(folder / f"{name}.p01", "Still water (restart)", "init", "01", "0000", "0001", "1SEC", "1MIN", True)
    write_unsteady(folder / f"{name}.u02", "dam break", None, "PLACEHOLDER")
    write_plan(folder / f"{name}.p02", "Dam break", "dambreak", "02", "0001", _clock(60 + max(t_end, 60)),
               "0.1SEC", "1SEC", False, EQUATIONS[eq][0])
    log(f"    project: {nseed} cells, terrain {nx}x{ny} at {cell:g} m")
    preprocess_and_associate(folder, ras_exe, terrain)
    hdf1 = compute(folder, ras_exe, "01", 600)
    rst = sorted(folder.glob("*.rst"))
    if probe or hdf1 is None or not rst:
        log("    files after the still-water run:\n" + listing(folder))
        log(messages(folder))
        if hdf1:
            log("    p01.hdf layout:\n" + h5_tree(hdf1, 200))
        for r in rst:
            log(f"    {r.name}: {r.stat().st_size} bytes, binary; first 64 bytes {r.read_bytes()[:64].hex()}")
    if not rst:
        raise RuntimeError("no restart file written by the still-water run")
    rst = rst[-1]
    # 2) put the dam-break step into the restart file
    with h5py.File(folder / f"{name}.g01.hdf", "r") as g:
        base = f"Geometry/2D Flow Areas/{AREA}"
        centres = g[f"{base}/Cells Center Coordinate"][()]
        zmin = g[f"{base}/Cells Minimum Elevation"][()] if f"{base}/Cells Minimum Elevation" in g else np.zeros(len(centres))
        n_real = int(g["Geometry/2D Flow Areas/Cell Points"].shape[0])
    edited = patch_restart(rst, centres, zmin, hl, hr, x0, n_real)
    log(f"    restart {rst.name}: set the downstream cells in {edited}")
    if not edited:
        raise RuntimeError("no per-cell water surface found in the restart file")
    write_unsteady(folder / f"{name}.u02", "dam break", None, rst.name)
    hdf2 = compute(folder, ras_exe, "02", 1800)
    if probe or hdf2 is None:
        log("    files after the dam-break run:\n" + listing(folder))
        log(messages(folder))
        if hdf2:
            log("    p02.hdf layout:\n" + h5_tree(hdf2, 200))
    if hdf2 is None:
        raise RuntimeError("dam-break run wrote no results")
    import h5py as _h5

    with _h5.File(hdf2, "r") as f:
        msgs = f["Results/Summary/Compute Messages (text)"][0].decode(errors="replace")
    if EQUATIONS[eq][1] not in msgs:
        raise RuntimeError(f"HEC-RAS did not run {EQUATIONS[eq][1]}; its messages say:\n{msgs[:1500]}")
    return read_strip(hdf2, folder / f"{name}.g01.hdf", t_end, x0, xmin, xmax, dx)


def patch_restart(rst: Path, centres: np.ndarray, zmin: np.ndarray, hl: float, hr: float, x0: float, n_real: int | None = None) -> list[str]:
    """Put the dam-break step into HEC-RAS's binary restart file.

    The restart file (HEC-RAS 6.6) is a Fortran unformatted file. After the
    still-water run every cell holds the same water surface, so the per-cell
    water surface is the one run of ``len(cells)`` equal (to round-off), non-zero
    doubles in it (found at whatever byte offset it sits). HEC-RAS stores it in
    its internal units (feet: 1 m reads 3.281), so values are rescaled rather
    than written in metres: downstream cells get ``old * (bed + hr) / hl``, or
    the bed when dry. Velocities were zero and stay zero, as in the exact
    problem.
    """
    buf = bytearray(rst.read_bytes())
    zmin = np.nan_to_num(np.asarray(zmin, dtype=float))
    n_all = len(centres)
    down = (centres[:, 0] - X0) > x0
    target = (zmin + hr) if hr > 0 else zmin
    edited = []
    n_real = int(n_real) if n_real else n_all
    for align in range(8):
        arr = np.frombuffer(bytes(buf[align:align + (len(buf) - align) // 8 * 8]), dtype="<f8")
        ok = np.isfinite(arr) & (np.abs(arr) > 1e-3) & (np.abs(arr) < 1e4)
        i = 0
        while i < len(arr):
            if not ok[i]:
                i += 1
                continue
            v = arr[i]
            j = i
            # the still-water surface is flat to round-off (last bits differ on fine grids)
            while j < len(arr) and ok[j] and abs(arr[j] - v) <= 1e-6 * abs(v):
                j += 1
            run = j - i
            ratio = float(v) / hl  # metres, or HEC-RAS's internal feet
            if run >= n_real and (abs(ratio - 1) < 1e-3 or abs(ratio / 3.280839895 - 1) < 1e-3):
                k = min(run, n_all)
                scale = float(v) / hl
                new = np.where(down[:k], target[:k] * scale, arr[i:i + k]).astype("<f8")
                start = align + i * 8
                buf[start:start + k * 8] = new.tobytes()
                edited.append(f"{run} doubles at byte {start} (stored value {v:.6g} = {hl:g} m), {k} set")
            i = max(j, i + 1)
    if edited:
        rst.write_bytes(bytes(buf))
    return edited


def read_strip(hdf: Path, ghdf: Path, t_end: float, x0: float, xmin: float, xmax: float, dx: float) -> dict:
    import h5py

    with h5py.File(ghdf, "r") as g:
        base = f"Geometry/2D Flow Areas/{AREA}"
        centres = g[f"{base}/Cells Center Coordinate"][()]
        n_real = int(g["Geometry/2D Flow Areas/Cell Points"].shape[0])  # the rest are ghost cells on the perimeter
    with h5py.File(hdf, "r") as f:
        ts = "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series"
        days = f[f"{ts}/Time"][()]
        a = f[f"{ts}/2D Flow Areas/{AREA}"]
        k = int(np.argmin(np.abs((days - days[0]) * 86400.0 - t_end)))
        log(f"    result time {(days[k] - days[0]) * 86400.0:.2f} s (wanted {t_end})")
        ws = a["Water Surface"][k]
        names = list(a.keys())
        log(f"    2D datasets: {names}")
        vx = vy = None
        for key in names:
            kl = key.lower()
            if "cell velocity" in kl and kl.endswith("x"):
                vx = a[key][k]
            if "cell velocity" in kl and kl.endswith("y"):
                vy = a[key][k]
        zb_name = next((n for n in ("Cells Minimum Elevation",) if n in f.get(f"Geometry/2D Flow Areas/{AREA}", {})), None)
        zb = f[f"Geometry/2D Flow Areas/{AREA}/{zb_name}"][()] if zb_name else np.zeros(len(ws))
    n = n_real
    centres = centres[:n]
    ws, zb = ws[:n], np.nan_to_num(zb[:n])
    h = np.maximum(ws - zb, 0.0)
    x = centres[:, 0] - X0
    u = vx[:n] if vx is not None else np.full(n, np.nan)
    xs = np.arange(xmin + dx / 2, xmax - dx / 4, dx)
    hh = np.array([h[np.abs(x - xi) < dx / 4].mean() for xi in xs])
    uu = np.array([u[np.abs(x - xi) < dx / 4].mean() for xi in xs])
    log(f"    {n} cells: depth {np.nanmin(hh):.4f}..{np.nanmax(hh):.4f} m, velocity {np.nanmin(uu):.3f}..{np.nanmax(uu):.3f} m/s, "
        f"volume {np.nansum(h) * dx * dx:.1f} m³")
    nan = np.full(len(xs), np.nan)
    return {"t": np.full(len(xs), t_end), "x": xs, "y": nan.copy(), "h": hh, "u": uu, "v": nan.copy(), "p": nan.copy(), "Q": hh * uu}


CASES = {"A1F-011": run_dam_break, "A1F-010": run_dam_break}


def main() -> int:
    from run_hecras import accept_terms, find_ras_exe

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", default=list(CASES))
    ap.add_argument("--ras-exe", type=Path)
    ap.add_argument("--accept-hec-terms", action="store_true")
    ap.add_argument("--probe", action="store_true", help="coarsest level of the first case, with full diagnostics")
    ap.add_argument("--equations", nargs="+", choices=list(EQUATIONS), default=list(EQUATIONS))
    args = ap.parse_args()

    from benchmark1d2d.signing import private_key as signing_key

    from benchmark1d2d.catalog import load_manifest
    from benchmark1d2d.io.results import write_results_parquet
    from benchmark1d2d.scoring.scorer import score_case

    ras_exe = args.ras_exe or find_ras_exe()
    log(f"HEC-RAS: {ras_exe}")
    if args.accept_hec_terms:
        accept_terms(ras_exe)
    version = ras_exe.parent.name
    key = signing_key()  # BENCH_SIGNING_KEY, else the public development key
    cases = args.cases[:1] if args.probe else args.cases
    failed = 0
    for eq in (["elm"] if args.probe else args.equations):
        label = EQUATIONS[eq][1]
        solver = {"name": f"HEC-RAS {version} 2D {label}", "version": version,
                  "adapter": f"hecras 2D (headless terrain + seeded mesh, restart-file initial step, {label})"}
        out = OUT / eq
        out.mkdir(parents=True, exist_ok=True)
        for tid in cases:
            m = load_manifest(tid, repo=REPO)
            levels = sorted(m["simulation"]["mesh_refinement"]["levels"], reverse=True)
            if args.probe:
                levels = levels[:1]
            paths = []
            for dx in levels:
                t0 = time.perf_counter()
                log(f"  {label} {tid} dx={dx}")
                try:
                    cols = CASES[tid](m, tid, float(dx), ras_exe, args.probe, eq)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                    failed += 1
                    break
                paths.append(write_results_parquet(out / f"{m['test_id']}_dx{dx:g}.parquet", cols, wall_seconds=time.perf_counter() - t0))
                log(f"  {label} {tid} dx={dx}: {time.perf_counter() - t0:.0f}s")
            if len(paths) < len(levels) or len(paths) < 2:
                continue
            card = score_case(m, paths[-1], refinement_results=paths, timestamp=TS, private_key=key, solver=solver)
            (out / f"{m['test_id']}.scorecard.json").write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            log(f"{card.get('verdict', 'pass' if card['passed'] else 'fail').upper()} {m['test_id']} ({solver['name']})")
            for r in card["criteria_results"]:
                log(f"    [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['observed']} {r['threshold']['units']}")
            c = card.get("convergence_result") or {}
            log(f"    convergence p={c.get('observed_order')} errors={c.get('errors')}")
            if not card["passed"]:
                log(f"::warning title=HEC-RAS 2D {label} {m['test_id']}::{'is inconclusive (convergence range straddles the minimum)' if card.get('verdict') == 'inconclusive' else 'fails at least one criterion'} (a finding, not a harness error)")
    return 1 if failed else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())

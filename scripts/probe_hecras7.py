#!/usr/bin/env python3
"""Diagnostics for porting the suite's HEC-RAS runs to HEC-RAS 7 and its pipe networks (Windows).

Writes ``out/hecras7probe/``:

* ``install.txt`` — the files HEC-RAS installed;
* ``types.txt`` — every public .NET type in RasMapperLib (and its sibling
  libraries) whose name mentions pipes, conduits, nodes or inlets, with its
  constructors, methods and properties; and ``RASGeometry``'s members;
* ``rasprocess.txt`` — what ``RasProcess.exe`` offers;
* ``davis/`` — HEC's own pipe-network example (Davis, from the 7.0 example
  projects): run as shipped, and run again after the compiled pipe network
  is removed from its geometry HDF, to learn whether HEC-RAS rebuilds it from
  the node and conduit layers by itself (``davis.txt``: what happened, and the
  HDF layouts of the geometry and the results).

Usage::

    python scripts/probe_hecras7.py --accept-hec-terms
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "runner" / "python"), str(REPO), str(REPO / "scripts")]
OUT = REPO / "out" / "hecras7probe"
EXAMPLES = "https://github.com/HydrologicEngineeringCenter/hec-downloads/releases/download/1.0.45/Example_Projects_7_0.zip"
WORDS = ("Pipe", "Conduit", "Inlet", "Manhole", "StormNode", "NodeLayer", "Drain")


def w(name: str, text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text, encoding="utf-8")
    print(f"--- {name} ({len(text)} chars)\n{text[:3000]}", flush=True)


def h5_tree(path: Path, skip: tuple = ()) -> str:
    import h5py

    lines = []
    with h5py.File(path, "r") as f:
        def visit(name, obj):
            if any(name.startswith(s) for s in skip):
                return
            if isinstance(obj, h5py.Dataset):
                dt = obj.dtype.names or obj.dtype
                lines.append(f"D {name} {obj.shape} {dt}")
            else:
                at = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in list(obj.attrs.items())[:10]}
                lines.append(f"G {name} {at}")
        f.visititems(visit)
    return "\n".join(lines)


def reflect(ras_dir: Path) -> None:
    from ras_commander.geom.GeomMesh import _load_dlls

    _load_dlls(str(ras_dir))
    import clr  # noqa: F401
    import System  # type: ignore
    from System.Reflection import BindingFlags  # type: ignore

    flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly
    out = []
    for dll in sorted(ras_dir.glob("*.dll")):
        if not dll.stem.startswith(("RasMapper", "Geospatial", "H5Assist", "Utility", "Ras")):
            continue
        try:
            asm = System.Reflection.Assembly.LoadFrom(str(dll))
            types = asm.GetTypes()
        except Exception as exc:  # noqa: BLE001
            try:
                types = [t for t in exc.Types if t is not None]  # ReflectionTypeLoadException
            except Exception:  # noqa: BLE001
                out.append(f"## {dll.name}: {exc}"[:300])
                continue
        hits = [t for t in types if t.IsPublic and any(k.lower() in t.FullName.lower() for k in WORDS)]
        if dll.stem == "RasMapperLib":
            hits += [t for t in types if t.FullName == "RasMapperLib.RASGeometry"]
        for t in hits:
            out.append(f"## {dll.name} :: {t.FullName}  (base {t.BaseType.FullName if t.BaseType else '-'})")
            for c in t.GetConstructors():
                out.append("   ctor(" + ", ".join(f"{p.ParameterType.Name} {p.Name}" for p in c.GetParameters()) + ")")
            for p in t.GetProperties(flags):
                out.append(f"   prop {p.PropertyType.Name} {p.Name}")
            for m in t.GetMethods(flags):
                if m.IsSpecialName:
                    continue
                out.append(f"   {'static ' if m.IsStatic else ''}{m.ReturnType.Name} {m.Name}(" +
                           ", ".join(f"{p.ParameterType.Name} {p.Name}" for p in m.GetParameters()) + ")")
    w("types.txt", "\n".join(out))


def run(cmd: list[str], cwd: Path | None = None, timeout: float = 120) -> str:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return f"$ {' '.join(cmd)}\nexit {p.returncode}\n{p.stdout[-4000:]}\n{p.stderr[-2000:]}"
    except Exception as exc:  # noqa: BLE001
        return f"$ {' '.join(cmd)}\n{type(exc).__name__}: {exc}"


def davis(ras_exe: Path) -> None:
    import h5py
    from ras_commander import RasCmdr, init_ras_project

    zp = OUT / "examples.zip"
    if not zp.is_file():
        urllib.request.urlretrieve(EXAMPLES, zp)
    src = OUT / "davis_src"
    with zipfile.ZipFile(zp) as z:
        for i in z.infolist():
            if i.filename.startswith("Pipes/Davis/"):
                z.extract(i, src)
    base = src / "Pipes" / "Davis"
    notes = []
    for tag in ("asis", "stripped"):
        d = OUT / "davis" / tag
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(base, d)
        for p in d.glob("*.p02.hdf"):
            p.unlink()
        g = d / "DavisStormSystem.g02.hdf"
        if tag == "stripped":
            with h5py.File(g, "a") as f:
                gone = [k for k in f["Geometry/Pipe Networks"].keys() if k != "Attributes"]
                for k in gone:
                    del f["Geometry/Pipe Networks"][k]
            for extra in ("DavisStormSystem.g02.edit.hdf", "DavisStormSystem.g02.prev.hdf"):
                (d / extra).unlink(missing_ok=True)
            notes.append(f"[stripped] removed compiled pipe network groups {gone}")
        ras = init_ras_project(d, str(ras_exe))
        notes.append(f"[{tag}] plans: {list(ras.plan_df['plan_number']) if hasattr(ras, 'plan_df') else '?'}")
        if tag == "stripped":
            try:
                from ras_commander.geom.GeomPreprocessor import GeomPreprocessor

                r = GeomPreprocessor.run_geometry_preprocessor("02", ras_object=ras, max_wait=900)
                notes.append(f"[stripped] geometry preprocessor: {getattr(r, 'success', r)!r} {getattr(r, 'error', '')}"[:800])
            except Exception as exc:  # noqa: BLE001
                notes.append(f"[stripped] geometry preprocessor raised {type(exc).__name__}: {exc}"[:800])
            with h5py.File(g, "r") as f:
                notes.append(f"[stripped] after preprocessing, Pipe Networks holds: {list(f['Geometry/Pipe Networks'].keys())}")
        t0 = time.perf_counter()
        try:
            r = RasCmdr.compute_plan("02", ras_object=ras, max_runtime=2400)
            notes.append(f"[{tag}] compute_plan: {r!r}"[:600])
        except Exception as exc:  # noqa: BLE001
            notes.append(f"[{tag}] compute_plan raised {type(exc).__name__}: {exc}"[:800])
        notes.append(f"[{tag}] {time.perf_counter() - t0:.0f} s")
        res = next(iter(d.glob("*.p02.hdf")), None)
        notes.append(f"[{tag}] results: {res}")
        with h5py.File(g, "r") as f:
            notes.append(f"[{tag}] geometry Pipe Networks now: {list(f['Geometry/Pipe Networks'].keys())}")
        for comp in sorted(d.glob("*.p02.computeMsgs.txt")) + sorted(d.glob("*.p02.comp_msgs.txt")):
            notes.append(f"[{tag}] {comp.name}:\n{comp.read_text(errors='replace')[-3000:]}")
        if res:
            try:
                with h5py.File(res, "r") as f:
                    msgs = f.get("Results/Summary/Compute Messages (text)")
                    if msgs is not None:
                        notes.append(f"[{tag}] compute messages:\n{bytes(msgs[()]).decode(errors='replace')[-3000:]}")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"[{tag}] reading messages: {exc}")
            if tag == "asis":
                w("davis_results_tree.txt", h5_tree(res, skip=("Geometry/2D Flow Areas",)))
        if tag == "asis":
            w("davis_geometry_tree.txt", h5_tree(g))
            # the node/conduit/inlet attribute tables, as values, to learn every field
            with h5py.File(g, "r") as f:
                lines = []
                for name in ("Geometry/Pipe Nodes/Attributes", "Geometry/Pipe Conduits/Attributes", "Geometry/Pipe Nodes/Top Inlets/Attributes",
                             "Geometry/Pipe Nodes/Side Inlets/Attributes", "Geometry/Pipe Networks/Attributes",
                             "Geometry/Pipe Networks/Davis/Node Surface Connectivity"):
                    ds = f.get(name)
                    if ds is None:
                        continue
                    lines.append(f"## {name} dtype={ds.dtype}")
                    for row in ds[: min(len(ds), 4)]:
                        lines.append("   " + repr(row))
                for name, ds in f["Geometry/Pipe Networks/Davis"].attrs.items():
                    lines.append(f"attr Pipe Networks/Davis {name} = {ds!r}")
                w("davis_tables.txt", "\n".join(lines))
    w("davis.txt", "\n".join(notes))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept-hec-terms", action="store_true")
    args = ap.parse_args()
    from run_hecras import accept_terms, find_ras_exe

    ras_exe = find_ras_exe()
    print(f"HEC-RAS: {ras_exe}")
    if args.accept_hec_terms:
        accept_terms(ras_exe)
    ras_dir = ras_exe.parent
    w("install.txt", "\n".join(str(p.relative_to(ras_dir)) for p in sorted(ras_dir.rglob("*")) if p.is_file()))
    rp = ras_dir / "RasProcess.exe"
    w("rasprocess.txt", "\n\n".join(run([str(rp), a]) if a else run([str(rp)]) for a in ("", "-?", "/?", "help")))
    for step, fn in (("reflection", lambda: reflect(ras_dir)), ("davis", lambda: davis(ras_exe))):
        try:
            fn()
        except Exception:  # noqa: BLE001
            w(f"{step}_error.txt", traceback.format_exc())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

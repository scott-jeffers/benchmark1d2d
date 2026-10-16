"""How each model was run: the pinned install and the exact command, per test.

Taken from the solver workflows (``.github/workflows``), which are the
record of how every published result was produced. ``recipe(key, sid)``
returns the steps to reproduce one result from a clone of the repository;
the site shows them on each test page with the model files the runner wrote
(``site/fixtures/inputs/<test>/<model>.zip``, see ``scripts/export_inputs.py``).
"""

from __future__ import annotations

REPO_URL = "https://github.com/scott-jeffers/benchmark1d2d"

SUITE = 'python -m pip install -e ".[dev]"'
SWMM = 'python -m pip install -e ".[dev]" swmm-toolkit==0.17.0'
OPENSWMM = ['python -m venv .venv-openswmm', '.venv-openswmm/bin/python -m pip install "openswmm==6.0.0a4.dev1" numpy']
ANUGA = ['conda create -n anuga -c conda-forge anuga=4.0.1 python=3.12 pip scipy', 'conda activate anuga']
TELEMAC = ['conda create -n telemac -c conda-forge opentelemac=v9.1.1 python=3.12']
LISFLOOD = ['# LISFLOOD-FP 8.3 source (Zenodo, MD5 abaa2e41b58f6c7df4443274bf130d4a), built CPU-only in double precision:',
            'sudo apt-get install -y libnetcdf-dev libnuma-dev',
            'cmake -S <lisflood>/source -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target lisflood']
GEOCLAW = ['git clone --depth 1 --branch v5.9.2 --recurse-submodules https://github.com/clawpack/clawpack',
           'conda create -n claw -c conda-forge clawpack=5.9.0 python=3.11 gfortran make pip pyarrow pandas']
HECRAS = ['# Windows: HEC-RAS 6.6 from HEC (HEC-RAS_66_Setup.exe, SHA-256 42A370B1…4715EB), silent install /S /v/qn',
          'python -m pip install -e ".[dev]" "ras-commander==0.105.0" h5py psutil pywin32 pillow pythonnet tifffile']
HYDRONET = ['# HydroNet 0d98ff5 and pyHMT2D 57645ff (github.com/psu-efd), CPU PyTorch:',
            'python -m pip install torch --index-url https://download.pytorch.org/whl/cpu',
            'python -m pip install -e <HydroNet> && python -m pip install -e <pyHMT2D> --no-deps']
HYDRA = ['HYDRA=$(python scripts/fetch_hydra.py .hydra)  # the pinned Hydra 17 CLI']
SWMM51 = ['python3.10 -m venv .venv-swmm51 && .venv-swmm51/bin/python -m pip install "swmm-toolkit==0.10.0"  # EPA SWMM 5.1.15']
TSNET = ['python3 -m venv .venv-tsnet && .venv-tsnet/bin/python -m pip install "numpy<2" "tsnet==0.3.1"']

HECRAS_2D_CASES = ("A2A-010", "A2C-")


def _hecras(sid: str, eq: str) -> tuple[str, str]:
    if sid == "A1F-001":
        return "scripts/run_hecras.py", f"python scripts/run_hecras.py {sid} --accept-hec-terms"
    if sid.startswith(HECRAS_2D_CASES):
        return "scripts/run_hecras_2d_cases.py", f"python scripts/run_hecras_2d_cases.py {sid} --accept-hec-terms --equations {eq}"
    return "scripts/run_hecras_2d.py", f"python scripts/run_hecras_2d.py {sid} --accept-hec-terms --equations {eq}"


def recipe(key: str, sid: str) -> dict | None:
    """{install: [lines], run: [lines], script, workflow, platform} for one model on one test, or None."""
    if key == "telemac":
        return dict(install=[SUITE, *TELEMAC], run=[f'python scripts/run_telemac.py --telemac-prefix "$(conda info --base)/envs/telemac" {sid}'],
                    script="scripts/run_telemac.py", workflow="track-a.yml", platform="Linux")
    if key == "anuga":
        return dict(install=[*ANUGA, SUITE], run=[f"python scripts/run_anuga.py {sid}"], script="scripts/run_anuga.py",
                    workflow="open-solvers.yml", platform="Linux", note="ANUGA builds its mesh and boundaries in Python: the script is the model.")
    if key == "geoclaw":
        return dict(install=[*GEOCLAW, SUITE], run=[f"PYTHONPATH=clawpack python scripts/run_geoclaw.py --claw clawpack {sid}"],
                    script="scripts/run_geoclaw.py", workflow="open-solvers.yml", platform="Linux")
    if key.startswith("lisflood-"):
        sv = key.split("-", 1)[1]
        return dict(install=[*LISFLOOD, SUITE], run=[f"python scripts/run_lisflood.py --exe build/lisflood --solver {sv} {sid}"],
                    script="scripts/run_lisflood.py", workflow="open-solvers.yml", platform="Linux")
    if key in ("hecras", "hecras-em"):
        script, cmd = _hecras(sid, "em" if key == "hecras-em" else "elm")
        return dict(install=HECRAS, run=[cmd], script=script, workflow="hecras.yml", platform="Windows")
    if key in ("epanet22", "hydra-wds", "wntr") and sid.startswith("A1P"):
        flag = {"epanet22": "", "hydra-wds": ' --hydra-exe "$HYDRA"', "wntr": " --wntr"}[key]
        return dict(install=['python -m pip install -e ".[dev,engines]"', *(HYDRA if key == "hydra-wds" else [])],
                    run=[f"python scripts/run_network_cases.py{flag}"], script="scripts/run_network_cases.py", workflow="track-a.yml", platform="Linux",
                    note="The script writes the EPANET input file from the test's inputs; the model files below are that file.")
    if key == "tsnet":
        return dict(install=[SUITE, *TSNET], run=["python scripts/run_tsnet.py --tsnet-python .venv-tsnet/bin/python"],
                    script="scripts/run_tsnet.py", workflow="track-a.yml", platform="Linux")
    if key in ("swmm524", "openswmm-dw", "openswmm-fv", "hydra-uds") and sid == "A1F-100":
        extra = {"swmm524": [], "openswmm-dw": OPENSWMM, "openswmm-fv": OPENSWMM, "hydra-uds": HYDRA, "swmm515": SWMM51}[key]
        flags = {"swmm524": "", "openswmm-dw": " --openswmm-python .venv-openswmm/bin/python",
                 "openswmm-fv": " --openswmm-python .venv-openswmm/bin/python", "hydra-uds": ' --hydra-exe "$HYDRA"',
                 "swmm515": " --swmm51-python .venv-swmm51/bin/python"}[key]
        return dict(install=['python -m pip install -e ".[dev,engines]"', *extra],
                    run=["python scripts/bellinge.py fetch --out out/bellinge",
                         f"python scripts/run_bellinge.py --model-dir out/bellinge/model/7_SWMM --engines {key}{flags}"],
                    script="scripts/run_bellinge.py", workflow="bellinge.yml", platform="Linux",
                    note=("The model files below are the published model with each storm's dates set. The rain-gauge file they "
                          "read (rg_bellinge_Jun2010_Aug2021.dat, 28 MB) is too large to include; the fetch step downloads it with "
                          "the model from DTU Data."))
    if key in ("swmm524", "openswmm-dw", "openswmm-fv", "hydra-uds", "swmm515") and not sid.startswith("B-"):
        drainage = sid.startswith("A1D")
        script = "scripts/run_drainage_cases.py" if drainage else "scripts/run_swmm_track_a.py"
        extra = {"swmm524": [], "openswmm-dw": OPENSWMM, "openswmm-fv": OPENSWMM, "hydra-uds": HYDRA, "swmm515": SWMM51}[key]
        flags = {"swmm524": "", "openswmm-dw": " --openswmm-python .venv-openswmm/bin/python",
                 "openswmm-fv": " --openswmm-python .venv-openswmm/bin/python", "hydra-uds": ' --hydra-exe "$HYDRA"',
                 "swmm515": " --swmm51-python .venv-swmm51/bin/python"}[key]
        return dict(install=['python -m pip install -e ".[dev,engines]"', *extra],
                    run=[f"python {script} {sid} --engines {key}{flags}"], script=script, workflow="track-a.yml", platform="Linux")
    if key in ("hydronet-fvm", "hydronet-pinn"):
        mode = key.split("-")[1]
        return dict(install=[*HYDRONET, SUITE], run=[f"python scripts/run_hydronet.py --hydronet <HydroNet> --mode {mode} {sid}"],
                    script="scripts/run_hydronet.py", workflow="open-solvers.yml", platform="Linux",
                    note="HydroNet's mesh and network are built in Python: the script is the model.")
    if key == "swmm-anuga":
        return dict(install=[*ANUGA, SWMM], run=[f"python scripts/run_coupled_cases.py {sid}"], script="scripts/run_coupled_cases.py",
                    workflow="open-solvers.yml", platform="Linux", note="The suite's own coupler moves the water; its code is the script.")
    if key in ("openswmm-2d", "openswmm-2d-x"):
        mesh = "cross" if key.endswith("-x") else "diagonal"
        return dict(install=[SWMM, *OPENSWMM],
                    run=[f"python scripts/run_openswmm_coupled.py --openswmm-python .venv-openswmm/bin/python --mesh {mesh} {sid}"],
                    script="scripts/run_openswmm_coupled.py", workflow="open-solvers.yml", platform="Linux")
    if key == "demo1d":
        return dict(install=['python -m pip install -e ".[dev,engines]"'], run=["python scripts/run_vertical_slice.py"],
                    script="scripts/run_vertical_slice.py", workflow="track-a.yml", platform="any")
    if key == "demo2d":
        return dict(install=[SUITE], run=["python scripts/run_demo_2d.py"], script="scripts/run_demo_2d.py", workflow="track-a.yml", platform="any")
    return None

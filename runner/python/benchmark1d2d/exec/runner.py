"""Black-box solver execution helpers."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Sequence


def run_solver(
    solver_cmd: str | Sequence[str],
    input_dir: str | Path,
    output_path: str | Path,
    work_dir: str | Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a solver command with cwd ``work_dir``.

    ``solver_cmd`` may be a string (shell-split) or an argv sequence. Placeholders
    ``{input_dir}``, ``{output_path}``, and ``{work_dir}`` are substituted when
    present; otherwise the caller is expected to have already expanded args.
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mapping = {
        "input_dir": str(input_dir),
        "output_path": str(output_path),
        "work_dir": str(work_dir),
    }

    if isinstance(solver_cmd, str):
        try:
            argv = shlex.split(solver_cmd.format(**mapping), posix=False)
        except (KeyError, ValueError):
            argv = shlex.split(solver_cmd, posix=False)
    else:
        argv = []
        for part in solver_cmd:
            try:
                argv.append(str(part).format(**mapping))
            except (KeyError, ValueError):
                argv.append(str(part))

    return subprocess.run(
        argv,
        cwd=str(work_dir),
        check=True,
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def run_container(*_args, **_kwargs) -> None:
    raise NotImplementedError(
        "Container execution is not implemented in benchmark1d2d v0.1; "
        "use run_solver with a local binary or Python demo solver."
    )


def run_wasm(*_args, **_kwargs) -> None:
    raise NotImplementedError(
        "WASM execution is not implemented in benchmark1d2d v0.1; "
        "use run_solver with a local binary or Python demo solver."
    )

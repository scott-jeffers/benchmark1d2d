"""Solver execution backends (subprocess, container, WASM)."""

from hydrobench.exec.runner import run_container, run_solver, run_wasm

__all__ = ["run_solver", "run_container", "run_wasm"]

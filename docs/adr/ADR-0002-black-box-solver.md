# ADR-0002: Solver is a black box

- Status: Accepted
- Date: 2026-10-13

## Context

Solvers arrive as C++, Rust, WASM, containers or neural surrogates. Coupling
the runner to any internal API would lock out new solver classes.

## Decision

The runner only sees: an executable or container, an input bundle, and an
output file that must satisfy the results contract
(`[t, x, y, h, u, v, p]` plus `Q`/`c` for 1D). Thin adapters convert native
output into that contract.

## Consequences

- No in-process linking to solver libraries in the core runner.
- Adapters are the only place native formats are understood.
- Sandboxing (subprocess → container → WASM) can evolve without changing
  the contract.

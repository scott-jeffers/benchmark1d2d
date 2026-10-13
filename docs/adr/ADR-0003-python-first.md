# ADR-0003: Python-first runner; Rust later

- Status: Accepted
- Date: 2026-10-13

## Context

The contract (`schemas/v1`) will iterate during Phases 1–4. Porting a moving
target to Rust doubles the work.

## Decision

Implement the runner, metrics, I/O and CLI in Python for the MVP. Keep empty
Rust crate stubs under `runner/crates/` so the eventual port has a home.
Port metric and I/O cores to Rust only after schema v1.0 is frozen.

## Consequences

- `pyproject.toml` is the install path for v0.1.
- Rust crates are placeholders; do not block releases on them.
- Score-card determinism and signing must be language-agnostic (canonical JSON
  + Ed25519) so a Rust port can reproduce byte-identical cards.

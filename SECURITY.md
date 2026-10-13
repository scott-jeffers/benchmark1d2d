# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (pre-certification) |
| < 0.1   | No |

## Reporting a vulnerability

Please open a private security advisory on the repository, or email the
maintainers listed in [`GOVERNANCE.md`](GOVERNANCE.md). Do **not** file a
public issue for vulnerabilities that could affect scoring integrity
(signature bypass, hash collision in the catalog validator, sandbox escape in
`hb-exec`).

## Sandbox notes

The Phase 2 runner executes solvers via subprocess. Container and WASM
sandboxes are planned in later phases. Treat untrusted solver binaries as
hostile: review them before running outside CI isolation.

# B-EPANET-001 — EPANET Net1 parity

EPA's Example Network 1, run for 24 h. The reference is EPANET 2.2 (the `libepanet22` library bundled with WNTR 1.5.0, SHA-256 recorded in the manifest). Regenerate with `python scripts/make_reference.py B-EPANET-001`.

A candidate passes when every node's peak pressure and every link's 24 h conveyed volume are within 1 % of EPANET 2.2.

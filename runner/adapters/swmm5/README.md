# SWMM 5 `.rpt` adapter

Thin shim that parses EPA SWMM 5.x text report (`.rpt`) summaries into the
benchmark1d2d results Parquet contract (`t, x, y, h, u, v, p` + optional `Q`).

Implementation lives in
[`runner/python/benchmark1d2d/adapters/swmm5.py`](../../python/benchmark1d2d/adapters/swmm5.py).

```bash
# Via registry (CLI)
benchmark1d2d run <TEST_ID> --solver ./swmm5_wrapper.py --adapter swmm5

# Direct
python -c "from benchmark1d2d.adapters.swmm5 import adapt_rpt_to_parquet; \
adapt_rpt_to_parquet('out.rpt', 'out.parquet')"
```

Requires a SWMM run that emits a Node Depth Summary (and optionally Link Flow
Summary) section. Full time-series `.out` binary support is out of scope for
this scaffold.

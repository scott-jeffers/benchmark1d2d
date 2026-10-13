# Contributing

## Adding a test case

1. Pick a free test ID (`A1P-…`, `A1F-…`, `A2A-…`, `A2L-…`, `A2F-…`, `A12-…`, `B-…`).
2. Create `test_catalog/.../<test_id>/` with:
   - `manifest.json` validating against `schemas/v1/test_manifest.schema.json`
   - `inputs/` (hashed files)
   - `reference/` (generator module, measured data + uncertainty, or pinned engine)
   - `README.md` (physics, source citation, known pitfalls)
3. Register the data license in [`DATA_LICENSES.md`](DATA_LICENSES.md).
4. Open a PR using the **New test case** issue template. Start as `status: draft`.

## Adding a solver adapter

1. Implement an adapter under `runner/adapters/<name>/` that writes the
   Arrow/Parquet results contract (`schemas/v1/results.schema.json`).
2. Register it in `runner/python/hydrobench/adapters/__init__.py`.
3. Add a fixture and a unit test.

## Adding a metric

1. Implement the metric in `runner/python/hydrobench/metrics/`.
2. Add it to the closed vocabulary in `test_manifest.schema.json`.
3. Document units and pass/fail semantics in `docs/methodology/`.

## Development setup

```bash
cd hydrobench
python -m pip install -e ".[dev]"
pytest
python tools/validate_catalog.py --allow-placeholder-hash
```

## Code of conduct

Be respectful. Focus review comments on the technical content of the contract,
tolerances and provenance — not on personalities.

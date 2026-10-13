# benchmark1d2d static site

Dependency-light Python generator. No Jinja, Next.js, or Astro — plain HTML
written from catalog manifests and optional scorecards.

## Build

From the repository root:

```bash
python site/build.py
python site/build.py --scorecards out
```

Output lands in `site/dist/`:

- `index.html` — dual-track explanation and **separate** Track A / Track B tables
- `tests/<test_id>.html` — physics, citations, tolerance rationales, status
- `methodology.html` — rendered from `docs/methodology/`
- `style.css` — copied from `site/static/`
- optional `<test_id>.png` plots when a scorecard and results parquet are both present

Open `site/dist/index.html` in a browser after building.

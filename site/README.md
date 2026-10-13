# benchmark1d2d static site

Dependency-light Python generator. No Jinja, Next.js, or Astro — plain HTML
written from catalog manifests, pinned engine metadata, and optional scorecards.

## Build

From the repository root:

```bash
python site/build.py
python site/build.py --scorecards out --scorecards site/fixtures/scorecards
```

By default the builder merges `site/fixtures/scorecards` then `out/`. Repeat
`--scorecards` to add more directories (later directories override earlier keys).

Output lands in `site/dist/`:

| Page | Role |
|------|------|
| `index.html` | Home — brand, dual-track story, how it works, pinned engines |
| `catalog.html` | Separate Track A / Track B result tables |
| `get-started.html` | Install, first run, local site build |
| `engines.html` | SWMM 5.2.4 pin (version, upstream, SHA-256) |
| `methodology.html` | Rendered from `docs/methodology/` |
| `tests/<test_id>.html` | Physics, run commands, citations, tolerances, scorecard |
| `style.css` | Copied from `site/static/` |

Optional `<test_id>.png` plots appear when a scorecard and results parquet are both present.

Open `site/dist/index.html` in a browser after building.

## Fixtures

`site/fixtures/scorecards/` holds published demo scorecards (Track A vertical
slice + SWMM self-parity) so GitHub Pages stays populated without requiring a
local Windows SWMM fetch.

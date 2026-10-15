# OpenHydro Bench site

A dependency-light Python generator: plain HTML written from the catalog
manifests, the score cards and the corpus data. Published by
`.github/workflows/pages.yml`.

## Build

From the repository root:

```bash
python site/build.py
```

The Pages workflow re-runs the suite's demo solvers first, so their score cards
and results are fresh; production solvers (HEC-RAS, TELEMAC-2D, ANUGA,
GeoClaw, LISFLOOD-FP) are read from `site/fixtures/<solver>/` and, when
present, `out/<solver>/`.

Output lands in `site/dist/`:

| Page | Built by | Role |
|------|----------|------|
| `index.html` | `pages.home_page` | Home: the question, findings, featured tests |
| `results.html` | `pages.results_page` | Every test against every model, with a detail panel |
| `tests/<ID>.html` | `pages.case_page` | One test in plain words, chart/replay, each model's checks, technical details |
| `score.html` | `pages.score_page` | Downloads, results templates and the in-browser check |
| `how-it-works.html` | `pages.how_page` | The method in plain words |
| `corpus.html`, `reports.html`, `downloads.html`, `method.html`, `get-started.html` | `build.py` | Reference pages |

## Files

| File | What it holds |
|------|---------------|
| `build.py` | Loading, bundles, server-drawn figures, reference pages, `main()` |
| `pages.py` | Layout and the plain-language pages; solver list and notes |
| `stories.py` | Plain-language text for every test |
| `profiles.py` | Exact curves and model curves along each case chart's line |
| `netcharts.py` | Charts for the drainage, coupled and flood-gauge tests: what to extract from a model's results, and the charts built from it |
| `tiles.py` | The picture tile drawn for every test |
| `checkdata.py` | Report points, exact answers and templates for the in-browser check |
| `static/chart.js` | Case-page chart and replay |
| `static/check.js` | In-browser check; mirrors the scorer's norms, mass, front and observed order |

## Fixtures

`fixtures/scorecards/` holds the demo and compatibility score cards,
`fixtures/<solver>/` the production solvers' cards, `fixtures/profiles/` their
final-state curves, and `fixtures/cross_build/` second builds of the reference
engines. See `fixtures/README.md` for how to refresh them.

## Where the results come from

Results from the per-push workflows (Pages, Track A demo and EPANET runs) are
produced at build time. Results from workflows that only run on a schedule or
on Windows (open-source solvers, slow runs, HEC-RAS, the Track A TELEMAC and
SWMM jobs, nightly corpus parity) are collected into `site/fixtures/` by the
**Collect results** workflow (`scripts/collect_results.py`) after each of
those runs: score cards are verified, filed by the solver named inside them,
committed, and the site is rebuilt; an issue is opened when a pass/fail result
changes. Chart curves travel the same way: every solver workflow runs
`scripts/export_curves.py`, which cuts the few numbers each chart needs from
the model's results (`out/curves/<model>/<test>.curve.json`, stamped with the
case version), and the collector files them under
`fixtures/curves/<test>/<model>.json`, so a chart always matches its score
card. `fixtures/profiles/` holds older curves, used only where no collected
curve exists; `python scripts/export_curves.py --local` refreshes the
collected ones from a local `out/`.

Solver versions are pinned; the weekly **Check solver versions** workflow
(`scripts/check_versions.py`) keeps an issue open listing newer upstream
releases.


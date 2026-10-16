# Submitting results

Anyone can run a test in their own software and put the result on the site.
Commercial codes (TUFLOW, MIKE, InfoWorks ICM, Flood Modeller, XPSWMM, PCSWMM
and others) need a licence, and often a GUI, so their developers or users run
the tests and send the results. The suite scores them with the same scorer and
the same limits as every other model, and shows them marked *submitted by* the
person or organisation that ran them.

## The short way (no git, no terminal, no JSON)

Everything happens on the **Score your model** page:
https://scott-jeffers.github.io/benchmark1d2d/score.html

1. **Pick a test and download it.** The zip has `START_HERE.md` (what to build,
   in plain words), ready-made model files where there is a standard format
   (EPA SWMM or EPANET `.inp`, beds and starting depths as ASCII grids), and
   results sheets in `results/` with every position or element already filled
   in.
2. **Run it** in your software with the settings you would recommend to a
   user, and fill in the sheets.
3. **Drop the sheets on the page.** The score appears at once; nothing is
   uploaded. Column names are read loosely ("Depth (m)" works as well as `h`),
   and file names do not matter: grid sizes are recognised from the positions.
4. **Press Publish**, answer five questions (software, version, who ran it,
   settings, licence) and send the zip it makes through the GitHub form it
   opens (a free GitHub account is needed). A bot scores the zip with the
   suite's own scorer and replies on the issue within minutes. A maintainer
   checks the settings and adds the `publish` label; the bot then adds the
   results to `submissions/` and the next site build shows them.

To fix something, attach a corrected sheet in a comment on the same issue: the
bot scores it again.

## What happens next

* Results are published under the licence you choose (CC BY 4.0 or CC0).
* When a test's version changes (a corrected reference or a new limit), a
  result for the old version is shown as *not scored* until it is rerun.
* You can send a new version of your results at any time; the site shows the
  latest.
* A submitted result counts towards a test's promotion to *frozen* ("two
  independent codes pass") like any other run.

## For developers: the long way

The same thing can be done from a clone of the repository.

Check a score locally:

```bash
git clone https://github.com/scott-jeffers/benchmark1d2d && cd benchmark1d2d
pip install -e .
benchmark1d2d score A1F-010 --results A1F-010_dx1.25.csv \
  --refinement A1F-010_dx10.csv A1F-010_dx5.csv A1F-010_dx2.5.csv A1F-010_dx1.25.csv \
  --solver-name "Your solver" --solver-version X
```

Submit as a pull request: add a folder `submissions/<your-solver>/` with the
results files and a `submission.json` (schema
`schemas/v1/submission.schema.json`; `submissions/_example/` is a worked
example):

```json
{
  "schema_version": "1.0.0",
  "solver": {"name": "Your solver", "version": "2025.1.2", "options": "scheme, wet/dry depth, time-step control"},
  "submitted_by": "Your organisation",
  "date": "2026-10-15",
  "results_licence": "CC-BY-4.0",
  "cases": [
    {"test_id": "A1F-011", "case_version": "1.0.0",
     "results": ["A1F-011_dx10.csv", "A1F-011_dx5.csv", "A1F-011_dx2.5.csv", "A1F-011_dx1.25.csv"]}
  ]
}
```

List grid files coarsest first: the last one is scored and all of them are used
for the convergence rate. The **Submissions** check scores the folder and posts
the scores on the pull request.

Results files follow the results contract (`schemas/v1/results.schema.json`):
CSV or Parquet, SI units, columns `t, x, y, h, u, v, p` plus `Q`, `z`, `V`,
`element_id`, `element_type` where the test uses them. Columns a test does not
use can be left out.

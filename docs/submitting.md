# Submitting results

The suite runs every solver it can obtain and run itself. Commercial codes
(TUFLOW, MIKE, InfoWorks ICM, Flood Modeller, XPSWMM, PCSWMM, and others)
need a licence, and often a GUI, so their developers or users run the tests
and **submit the results**. The suite scores submitted results with the same
scorer and the same limits as everything else, and the site shows them in
their own column, marked *submitted by* the organisation that ran them.

A submission never carries its own pass/fail: it carries results files, and
the score cards are made from them in the open.

## 1. Pick the cases

Every case page on the site has a **Download inputs** link. The zip holds:

| File | What it is |
|---|---|
| `manifest.json` | the case: what to run, the checks and their limits |
| `README.md` | the physics and where the exact answer comes from |
| `inputs/` | the geometry, terrain, boundary data or network |
| `RESULTS_TEMPLATE.csv` | the columns and the rows the scorer expects |
| `HOW_TO_SUBMIT.md` | the run settings, file names, a local scoring command and a `submission.json` to start from |

From a clone of the repository, `benchmark1d2d kit A1F-010 --out kits/`
writes the same folder.

Good first cases by kind of code:

* **2D flood codes**: A2A-001 (moving shoreline), A2A-010 (steady friction
  balance), A2A-020 (oblique jump), the SWASHES bump channel A1F-040 to 043
  (as a narrow strip), the Environment Agency tests A2C-EA1, 2, 4, 5, and the
  dam breaks A1F-010 and 011.
* **1D river codes**: A1F-001, 010, 011, 020 and A1F-040 to 043.
* **Drainage network codes**: A1D-001 to 005 (exact answers), B-EXTRAN-001
  and B-RTC-001 (parity with EPA SWMM 5.2.4).
* **Coupled 1D/2D codes**: A12-010, 011 and 012.
* **Water distribution codes**: A1P-001, A1P-010 and B-EPANET-001.

## 2. Run them

Use the settings you would recommend to a user for that kind of problem, and
record them in `submission.json`; do not tune them to the answer. Where a
case has several grids, run all of them: the finest is scored, and all are
used to measure the order of convergence, which counts on verification
cases.

## 3. Write the results

One file per run, in the results contract (`schemas/v1/results.schema.json`):
CSV or Parquet, SI units, columns `t, x, y, h, u, v, p` plus `Q`, `z`, `V`,
`element_id`, `element_type` where the case uses them. `RESULTS_TEMPLATE.csv`
shows exactly which rows each case needs:

* **channels and 2D fields**: one row per cell centre at the end of the run;
* **probes** (inter-comparison and laboratory cases): a time series at each
  probe, with the bed level `z` of the cell holding it;
* **networks**: one row per node and link, named as in the input;
* **coupled cases**: probe rows, the exchange flow at each manhole and four
  volume accounts (`surface`, `network`, `inflow`, `outflow`).

## 4. Check the scores yourself

```bash
git clone https://github.com/scott-jeffers/benchmark1d2d && cd benchmark1d2d
pip install -e .
benchmark1d2d score A1F-010 --results A1F-010_dx1.25.csv \
  --refinement A1F-010_dx10.csv A1F-010_dx5.csv A1F-010_dx2.5.csv A1F-010_dx1.25.csv \
  --solver-name "Your solver" --solver-version X
```

The scorer prints every check with its value and limit.

## 5. Submit

Add a folder `submissions/<your-solver>/` with your results files and a
`submission.json` (schema: `schemas/v1/submission.schema.json`;
`submissions/_example/` is a worked example):

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

Open a pull request. The **Submissions** check validates the folder, scores
every case and posts the scores on the pull request; a malformed submission
fails the check with the reason. Once merged, the next site build scores it
again and shows it.

If you would rather not use GitHub, email the folder as a zip to the
maintainers (see the repository's contact details) and we will open the pull
request for you.

## What happens next

* Results are published under the licence you choose (CC-BY-4.0 or CC0).
* When a case's version changes (a corrected reference or a new limit), a
  submission for the old version is shown as *not scored* until it is rerun.
* You can update a submission at any time with a new pull request; the site
  shows the latest.
* A submission counts towards a case's promotion to *frozen* ("two
  independent codes pass") like any other run.

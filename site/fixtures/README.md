# Fixture score cards

Score cards from the last local run of the demo solvers (`scripts/run_vertical_slice.py`,
`scripts/run_demo_2d.py`, `scripts/run_track_b.py`). The Pages workflow re-runs all
three and its fresh cards replace these; the fixtures only keep the site populated
if a demo run fails in CI.

Regenerate with:

```bash
python scripts/run_vertical_slice.py
python scripts/run_demo_2d.py
python scripts/run_track_b.py --swmm51-python /path/to/python3.10-with-swmm-toolkit-0.10.0
cp out/vertical_slice/*.scorecard.json out/demo_2d/*.scorecard.json out/track_b/*.scorecard.json site/fixtures/scorecards/
```

## Production solvers

`telemac/`, `hecras/`, `anuga/`, `geoclaw/` and `lisflood/` hold score cards from
production open-source codes run as black boxes with their own defaults
(`scripts/run_telemac.py`, `run_hecras.py`, `run_anuga.py`, `run_geoclaw.py`,
`run_lisflood.py`). Their CI jobs (`track-a.yml`, `hecras.yml`, `open-solvers.yml`)
upload fresh cards as artifacts; copy them here to refresh the site.

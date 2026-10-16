# Submitted results

Developers and users of a solver the suite cannot run itself (commercial
codes, codes that need a licence or a GUI) submit their **results**; the
suite scores them with the same scorer and limits as every other run, and the
site shows them labelled *submitted by …*.

Each submission is a folder `submissions/<slug>/` holding:

* `submission.json` — who ran which solver version, on which cases, with
  which options (schema: `schemas/v1/submission.schema.json`);
* the results files it lists, in the results contract
  (`schemas/v1/results.schema.json`): Parquet, or CSV with the same columns.

The easy way is the **Publish** button on the site's Score page
(https://scott-jeffers.github.io/benchmark1d2d/score.html): it makes the folder
for you and sends it through an issue, and a bot adds it here. Or open a pull
request adding the folder. The `Submissions` check validates it
and posts the scores; once merged, the site picks it up at its next build.
`_example/` is a worked example (the suite's demo solver on A1F-011), skipped
by the site.

Step-by-step instructions, the per-case kit and the column templates are in
[docs/submitting.md](../docs/submitting.md).

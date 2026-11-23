# Run the tests on your own machine

For software the suite cannot run itself (a commercial licence, a
Windows-only installer, a dongle), the owner can run the tests on their own
licensed machine **through the suite's own workflow**. The licence never
leaves your machine. The suite sends each test, your command runs your model,
and the suite scores and publishes the result, labelled *run on the owner's
machine*, with the runner and the workflow run that produced it.

This is stronger evidence than submitting results files: the inputs come from
the suite, the scoring is the suite's, and the run is recorded by GitHub.

## What you need

* A machine with your software and its licence (Windows, Linux or macOS).
* Python 3.10 or later on that machine.
* A command that, given a test's folder, builds and runs your model and fills
  in the results sheets.

## Set it up

1. **Register a self-hosted runner** for the repository (*Settings → Actions →
   Runners → New self-hosted runner*), or for your own fork. Give it a label
   that names your software, for example `tuflow`. The steering group can
   register it on the main repository for you; until then, run it on a fork:
   its score cards are collected the same way when you open a pull request
   that adds them under `site/fixtures/owner/`.
2. **Write your command.** It runs in the unpacked test folder and gets:

   | Placeholder | What it is |
   | --- | --- |
   | `{test}` | The test id, e.g. `A1F-010` |
   | `{kit}` | The test folder: `inputs/` (the test's data), `model/` (model files to start from, where the suite has them), `results/` (the sheets to fill in), `START_HERE.md` |
   | `{results}` | `{kit}/results`: fill in one sheet per grid size |
   | `{repo}` | This repository's checkout, for your own scripts |

   Leave the files your software read in `{kit}/model` and what it wrote in
   `{kit}/output`: they are published with your result, so anyone with a
   licence can check your set-up.
3. **Add a job** to `.github/workflows/owner-run.yml`, copying the `example`
   job: your runner's labels in `runs-on`, your command in `OWNER_COMMAND`, a
   plain description of your settings in `OWNER_SETTINGS`, and your software,
   version, organisation and tests on the `run_owner.py` line.
4. **Run it** from the Actions tab (*Owner-run solvers → Run workflow*). It
   also runs weekly, so your results follow changes to the tests.

`scripts/owner_example.py` is a complete worked example using the suite's
demo solver; the `example` job runs it on a GitHub-hosted machine.

## What is published

* The score card, signed by the suite, with `run_by: owner`, your runner's
  name and the workflow run.
* The results sheets your command filled in.
* The files in `{kit}/model` and `{kit}/output`, zipped with their checksums.

Results are published as they are produced, like every other result. There is
no approval, notice period or embargo (see the automation charter in
[GOVERNANCE.md](../GOVERNANCE.md)). Make sure your licence allows publishing
benchmark results before you run.

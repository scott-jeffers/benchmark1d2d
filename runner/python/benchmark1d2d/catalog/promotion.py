"""What a catalog case still needs before it can be promoted.

Promotion rules (see ``docs/methodology/promotion.md``):

``draft`` → ``candidate``
    1. licence verified (not ``TBD-confirm``)
    2. every input present, or fetchable by hash (nothing ``pending``)
    3. a reference exists (analytic generator, committed reference results,
       pinned engine results or objective expected states)
    4. every gating criterion states why its tolerance is what it is

``candidate`` → ``frozen``
    5. a run that passes the case, with its score card published by CI
    6. verification cases: observed order of accuracy meets the minimum
    7. two independent implementations pass (a second solver or engine,
       written separately from the first), so the case is not tuned to one code;
       for parity cases, a second build of the reference engine reproduces the
       reference (the official EPA binaries, scored by the cross-build job)
    8. a maintainer review recorded in the manifest (``review.by``, ``review.date``)

Everything except 8 is computed from the manifest and the published score
cards, so the site can show each case's blockers without anyone keeping a
list by hand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CANDIDATE_RULES = ("licence", "inputs", "reference", "rationale")
FROZEN_RULES = ("passing_run", "order", "independent", "review")

LABELS = {
    "licence": "Data licence verified",
    "inputs": "All inputs available",
    "reference": "Reference (truth) available",
    "rationale": "Every tolerance justified",
    "passing_run": "A published run passes",
    "order": "Order of accuracy shown",
    "independent": "Two independent codes pass",
    "review": "Maintainer review recorded",
}


def _reference_ok(m: dict[str, Any]) -> tuple[bool, str]:
    ref = m.get("reference") or {}
    kind = ref.get("kind")
    case_dir = Path(m.get("_case_dir", "."))
    if kind == "analytic":
        return bool((ref.get("generator") or {}).get("module")), "analytic generator"
    if kind == "intercomparison":
        return bool(ref.get("expected_states")), "objective expected states"
    if kind == "exact_states":
        return bool(ref.get("expected_states")), "exact states from conservation"
    if kind in ("pinned_engine", "measured"):
        path = ref.get("results_path")
        if ref.get("availability") and ref["availability"] != "committed":
            return False, f"measured data not yet obtained ({ref['availability'].replace('_', ' ')})"
        if path and (case_dir / path).is_file():
            return True, "committed reference results"
        return False, "reference results file missing"
    return False, "no reference defined"


def checklist(manifest: dict[str, Any], cards: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Each rule as ``{id, label, met, detail, stage}``; ``stage`` is the status it unlocks."""
    m = manifest
    cards = [c for c in (cards or []) if c.get("test_id") == m.get("test_id")]
    out: list[dict[str, Any]] = []

    def add(rule: str, met: bool, detail: str) -> None:
        out.append({"id": rule, "label": LABELS[rule], "met": bool(met), "detail": detail,
                    "stage": "candidate" if rule in CANDIDATE_RULES else "frozen"})

    lic = str((m.get("provenance") or {}).get("license", ""))
    add("licence", lic and lic != "TBD-confirm", lic if lic != "TBD-confirm" else "licence not yet confirmed by the rights holder")
    pending = [i["path"] for i in m.get("inputs", []) if i.get("pending")]
    add("inputs", not pending, "all committed or fetched by SHA-256" if not pending else f"pending: {', '.join(pending)}")
    ok, why = _reference_ok(m)
    add("reference", ok, why)
    crit = (m.get("scoring") or {}).get("criteria", [])
    missing = [c["id"] for c in crit if c.get("gating") and len(str(c.get("rationale", ""))) < 20]
    add("rationale", crit and not missing, "each gating criterion has a rationale" if not missing else f"no rationale: {', '.join(missing)}")

    # Score cards from a second build of the reference engine (the cross-build
    # job) are evidence for rule 7 on parity cases, not candidate runs.
    rebuilds = [c for c in cards if "official" in str((c.get("solver") or {}).get("name", ""))]
    passing = [c for c in cards if c.get("passed") and c not in rebuilds]
    add("passing_run", bool(passing), f"{len(passing)} passing score card(s)" if passing else "no passing score card published yet")
    if str(m.get("test_class", "")).startswith("verification"):
        conv = (m.get("scoring") or {}).get("convergence") or {}
        if conv.get("not_applicable"):
            add("order", True, "not applicable: " + conv["not_applicable"])
        else:
            shown = [c for c in passing if (c.get("convergence_result") or {}).get("passed")]
            add("order", bool(shown), "observed order meets the minimum" if shown else "no passing run with multi-grid evidence")
    else:
        add("order", True, "not a verification case")
    if m.get("test_class") == "parity":
        ok_builds = [c for c in rebuilds if c.get("passed")]
        detail = ("the official EPA build reproduces the reference within tolerance" if ok_builds else
                  "the official EPA build differs from the reference beyond tolerance" if rebuilds else
                  "no second build of the reference engine scored yet")
        out.append({"id": "independent", "label": "Reference reproduced by a second build", "met": bool(ok_builds),
                    "detail": detail, "stage": "frozen"})
    else:
        solvers = sorted({_family(c) for c in passing})
        add("independent", len(solvers) >= 2, f"passing codes: {', '.join(solvers) or 'none'}" + ("" if len(solvers) >= 2 else " — needs a second, independently written solver or engine"))
    rv = m.get("review") or {}
    add("review", bool(rv.get("by") and rv.get("date")), f"reviewed by {rv['by']} on {rv['date']}" if rv.get("by") and rv.get("date") else "no maintainer review recorded")
    return out


def _family(card: dict[str, Any]) -> str:
    """Group runs of the same code (different grids or options) as one implementation."""
    name = str((card.get("solver") or {}).get("name", "unknown"))
    return name.split(" (")[0].split(" at ")[0].strip()


def next_stage(manifest: dict[str, Any], cards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The next status the case could reach and what blocks it."""
    status = manifest.get("status", "draft")
    items = checklist(manifest, cards)
    target = {"draft": "candidate", "candidate": "frozen"}.get(status)
    if target is None:
        return {"status": status, "next": None, "blockers": []}
    rules = CANDIDATE_RULES if target == "candidate" else CANDIDATE_RULES + FROZEN_RULES
    return {"status": status, "next": target, "blockers": [i for i in items if i["id"] in rules and not i["met"]]}

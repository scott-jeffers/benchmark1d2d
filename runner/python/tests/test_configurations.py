"""Every published model has a valid configuration record (protocol 4.0)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from benchmark1d2d import configuration

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(configuration.SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_records_validate(validator: Draft202012Validator) -> None:
    paths = sorted(configuration.CONFIG_DIR.glob("*.json"))
    assert paths
    for p in paths:
        rec = json.loads(p.read_text(encoding="utf-8"))
        errors = [e.message for e in validator.iter_errors(rec)]
        assert not errors, f"{p.name}: {errors}"
        assert rec["key"] == p.stem, f"{p.name}: key {rec['key']!r} differs from the file name"


def test_every_site_model_has_a_configuration() -> None:
    sys.path.insert(0, str(REPO / "site"))
    import pages  # noqa: E402

    keys = set(configuration.load())
    missing = sorted(set(pages.SOLVER) - keys)
    assert not missing, f"models without a configuration record: {missing}"


def test_t1_changes_cite_guidance(validator: Draft202012Validator) -> None:
    rec = {"schema_version": "1.0.0", "key": "x", "engine": {"name": "X", "version": "1"}, "tier": "T1",
           "set_by": "suite", "changed_from_default": [{"setting": "theta", "value": 0.6, "reason": "manual says so"}],
           "defaults_audit": "manual"}
    assert list(validator.iter_errors(rec)), "a T1 change without a source must be refused"


def test_submission_configuration_is_t2() -> None:
    rec = configuration.for_submission({"solver": {"name": "My code", "version": "2", "options": "CFL 0.4"},
                                        "submitted_by": "A Person"}, "sub-my-code")
    assert rec["tier"] == "T2" and rec["set_by"] == "A Person"

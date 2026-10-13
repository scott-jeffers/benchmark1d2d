#!/usr/bin/env python3
"""Validate hydrobench test_catalog manifests.

Checks (per case under test_catalog/):
  1. JSON Schema (Draft 2020-12) against schemas/v1/test_manifest.schema.json
  2. Input SHA-256 integrity (paths relative to the case folder)
  3. provenance.license present and listed in DATA_LICENSES.md
  4. TBD-confirm licenses only allowed with status: draft
  5. Optional Crossref DOI resolution (--check-doi)

Placeholder empty-file hash is rejected unless --allow-placeholder-hash is set
and status is draft or candidate. Frozen (and deprecated) always reject
placeholders.

Exit 0 on success, 1 on any failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

PLACEHOLDER_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
DRAFT_OR_CANDIDATE = frozenset({"draft", "candidate"})
CROSSREF_URL = "https://api.crossref.org/works/{doi}"
USER_AGENT = "hydrobench-validate-catalog/0.1 (mailto:openhydro@example.org)"


@dataclass
class CheckResult:
    label: str
    ok: bool
    messages: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.messages.append(msg)

    def warn(self, msg: str) -> None:
        self.messages.append(f"WARN: {msg}")


def discover_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    return Path(__file__).resolve().parents[1]


def load_schema(root: Path) -> Draft202012Validator:
    schema_path = root / "schemas" / "v1" / "test_manifest.schema.json"
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def parse_license_ids(data_licenses_path: Path) -> set[str]:
    """Parse License ID column from the markdown table in DATA_LICENSES.md."""
    text = data_licenses_path.read_text(encoding="utf-8")
    ids: set[str] = set()
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first.lower() in {"license id", "licence id"}:
            in_table = True
            continue
        if re.fullmatch(r":?-+:?", first.replace(" ", "")) or first.startswith("---"):
            continue
        if not in_table:
            continue
        # Strip surrounding backticks if present.
        license_id = first.strip().strip("`").strip()
        if license_id:
            ids.add(license_id)
    if not ids:
        raise RuntimeError(
            f"No license IDs parsed from {data_licenses_path}; "
            "expected a markdown table with a License ID column."
        )
    return ids


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_catalog_manifests(root: Path) -> list[Path]:
    catalog = root / "test_catalog"
    if not catalog.is_dir():
        return []
    return sorted(catalog.rglob("manifest.json"))


def format_schema_error(err: ValidationError) -> str:
    path = ".".join(str(p) for p in err.absolute_path) or "(root)"
    return f"schema: {path}: {err.message}"


def check_doi(doi: str, *, strict: bool) -> tuple[bool, str]:
    """Return (ok, message). Network failures warn unless strict."""
    cleaned = doi.strip()
    if cleaned.lower().startswith("https://doi.org/"):
        cleaned = cleaned[len("https://doi.org/") :]
    elif cleaned.lower().startswith("http://doi.org/"):
        cleaned = cleaned[len("http://doi.org/") :]
    url = CROSSREF_URL.format(doi=urllib.parse.quote(cleaned, safe="/"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = getattr(resp, "status", None) or resp.getcode()
            if 200 <= int(status_code) < 300:
                return True, f"DOI OK ({cleaned})"
            msg = f"Crossref returned HTTP {status_code} for DOI {cleaned}"
    except urllib.error.HTTPError as exc:
        msg = f"Crossref HTTP {exc.code} for DOI {cleaned}"
    except Exception as exc:  # noqa: BLE001 — network/offline must not crash
        msg = f"DOI check failed for {cleaned}: {exc}"
    if strict:
        return False, msg
    return True, f"WARN: {msg} (non-strict; continuing)"


def validate_manifest_dict(
    data: dict[str, Any],
    *,
    validator: Draft202012Validator,
    license_ids: set[str],
    case_dir: Path | None,
    allow_placeholder_hash: bool,
    check_doi_flag: bool,
    label: str,
) -> CheckResult:
    result = CheckResult(label=label, ok=True)

    try:
        validator.validate(data)
    except ValidationError as err:
        result.fail(format_schema_error(err))
    except SchemaError as err:
        result.fail(f"schema definition error: {err.message}")

    status = data.get("status")
    provenance = data.get("provenance") or {}
    license_id = provenance.get("license")

    if not license_id:
        result.fail("provenance.license is missing")
    elif license_id not in license_ids:
        result.fail(
            f"provenance.license {license_id!r} is not listed in DATA_LICENSES.md"
        )
    elif license_id == "TBD-confirm" and status != "draft":
        result.fail(
            "provenance.license is TBD-confirm but status is "
            f"{status!r} (must be draft; refuse promotion)"
        )

    inputs = data.get("inputs") or []
    if case_dir is not None:
        for entry in inputs:
            if not isinstance(entry, dict):
                continue
            rel = entry.get("path")
            expected = entry.get("sha256")
            if not rel or not expected:
                result.fail(f"input entry missing path/sha256: {entry!r}")
                continue
            path = case_dir / rel
            if not path.is_file():
                result.fail(f"input file missing: {rel}")
                continue
            actual = sha256_file(path)
            expected_l = str(expected).lower()
            if actual.lower() != expected_l:
                result.fail(
                    f"SHA-256 mismatch for {rel}: "
                    f"manifest={expected} actual={actual}"
                )
                continue
            if expected_l == PLACEHOLDER_SHA256:
                if status not in DRAFT_OR_CANDIDATE:
                    result.fail(
                        f"placeholder SHA-256 not allowed for status={status!r} "
                        f"({rel})"
                    )
                elif not allow_placeholder_hash:
                    result.fail(
                        f"placeholder SHA-256 rejected for {rel} "
                        "(pass --allow-placeholder-hash for draft/candidate)"
                    )
    else:
        # Fixture-only validation: still enforce placeholder policy on declared hashes.
        for entry in inputs:
            if not isinstance(entry, dict):
                continue
            expected = str(entry.get("sha256", "")).lower()
            rel = entry.get("path", "(unknown)")
            if expected == PLACEHOLDER_SHA256:
                if status not in DRAFT_OR_CANDIDATE:
                    result.fail(
                        f"placeholder SHA-256 not allowed for status={status!r} "
                        f"({rel})"
                    )
                elif not allow_placeholder_hash:
                    result.fail(
                        f"placeholder SHA-256 rejected for {rel} "
                        "(pass --allow-placeholder-hash for draft/candidate)"
                    )

    if check_doi_flag:
        for citation in provenance.get("citations") or []:
            if not isinstance(citation, dict):
                continue
            doi = citation.get("doi")
            if not doi:
                continue
            ok, msg = check_doi(str(doi), strict=True)
            if ok:
                result.messages.append(msg)
            else:
                result.fail(msg)

    return result


def validate_catalog_case(
    manifest_path: Path,
    *,
    root: Path,
    validator: Draft202012Validator,
    license_ids: set[str],
    allow_placeholder_hash: bool,
    check_doi_flag: bool,
) -> CheckResult:
    case_dir = manifest_path.parent
    try:
        label = str(manifest_path.relative_to(root)).replace("\\", "/")
    except ValueError:
        label = str(manifest_path).replace("\\", "/")

    try:
        with manifest_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        result = CheckResult(label=label, ok=False)
        result.fail(f"cannot load JSON: {exc}")
        return result

    return validate_manifest_dict(
        data,
        validator=validator,
        license_ids=license_ids,
        case_dir=case_dir,
        allow_placeholder_hash=allow_placeholder_hash,
        check_doi_flag=check_doi_flag,
        label=label,
    )


def run_self_test(
    root: Path,
    *,
    validator: Draft202012Validator,
    license_ids: set[str],
    allow_placeholder_hash: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    tests_dir = root / "schemas" / "v1" / "tests"
    valid_dir = tests_dir / "valid"
    invalid_dir = tests_dir / "invalid"

    if valid_dir.is_dir():
        for path in sorted(valid_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                r = CheckResult(label=f"self-test valid/{path.name}", ok=False)
                r.fail(f"cannot load: {exc}")
                results.append(r)
                continue
            r = validate_manifest_dict(
                data,
                validator=validator,
                license_ids=license_ids,
                case_dir=None,
                allow_placeholder_hash=allow_placeholder_hash,
                check_doi_flag=False,
                label=f"self-test valid/{path.name}",
            )
            results.append(r)
    else:
        r = CheckResult(label="self-test valid/", ok=True)
        r.warn("schemas/v1/tests/valid/ not present; skipped")
        results.append(r)

    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            label = f"self-test invalid/{path.name}"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                r = CheckResult(label=label, ok=False)
                r.fail(f"cannot load: {exc}")
                results.append(r)
                continue
            try:
                validator.validate(data)
            except ValidationError:
                results.append(
                    CheckResult(
                        label=label,
                        ok=True,
                        messages=["correctly rejected by schema"],
                    )
                )
            else:
                r = CheckResult(label=label, ok=False)
                r.fail("expected schema validation to fail, but it passed")
                results.append(r)
    else:
        r = CheckResult(label="self-test invalid/", ok=True)
        r.warn("schemas/v1/tests/invalid/ not present; skipped")
        results.append(r)

    return results


def print_result(result: CheckResult) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"[{status}] {result.label}")
    for msg in result.messages:
        print(f"       - {msg}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate hydrobench test_catalog manifests."
    )
    p.add_argument(
        "--allow-placeholder-hash",
        action="store_true",
        help=(
            "Allow the empty-file placeholder SHA-256 for draft/candidate "
            "cases only (frozen always requires real hashes)."
        ),
    )
    p.add_argument(
        "--check-doi",
        action="store_true",
        help=(
            "Strict Crossref DOI checks for citations with a doi field "
            "(network required; failures are hard errors)."
        ),
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: parent of tools/).",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Also validate schemas/v1/tests/valid/*.json and confirm "
            "invalid fixtures fail schema validation."
        ),
    )
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = discover_root(args.root)

    try:
        validator = load_schema(root)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        print(f"[FAIL] schema load: {exc}", file=sys.stderr)
        return 1

    licenses_path = root / "DATA_LICENSES.md"
    try:
        license_ids = parse_license_ids(licenses_path)
    except (OSError, RuntimeError) as exc:
        print(f"[FAIL] license register: {exc}", file=sys.stderr)
        return 1

    results: list[CheckResult] = []
    manifests = iter_catalog_manifests(root)
    if not manifests:
        print(f"[FAIL] no manifest.json found under {root / 'test_catalog'}")
        return 1

    for path in manifests:
        results.append(
            validate_catalog_case(
                path,
                root=root,
                validator=validator,
                license_ids=license_ids,
                allow_placeholder_hash=args.allow_placeholder_hash,
                check_doi_flag=args.check_doi,
            )
        )

    if args.self_test:
        results.extend(
            run_self_test(
                root,
                validator=validator,
                license_ids=license_ids,
                allow_placeholder_hash=args.allow_placeholder_hash,
            )
        )

    for r in results:
        print_result(r)

    n_ok = sum(1 for r in results if r.ok)
    n_fail = sum(1 for r in results if not r.ok)
    print(
        f"\nSummary: {n_ok} OK, {n_fail} FAIL "
        f"(placeholder allowed={args.allow_placeholder_hash}, "
        f"check_doi={args.check_doi})"
    )
    if not args.allow_placeholder_hash and n_fail:
        print(
            "Note: placeholder hashes are expected to fail without "
            "--allow-placeholder-hash while inputs are still empty stubs."
        )
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

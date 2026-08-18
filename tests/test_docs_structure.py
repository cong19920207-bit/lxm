from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_legacy_snapshot import build_snapshot
from scripts.verify_docs_structure import load_manifest, run_checks


REPO = Path(__file__).resolve().parents[1]


def test_manifest_is_valid_and_complete():
    manifest = load_manifest(REPO / "docs" / "llm-manifest.json")
    ids = [item["id"] for item in manifest["documents"]]

    assert len(ids) == len(set(ids))
    assert len(manifest["coverage"]["contract_sections"]) == 98
    assert len(set(manifest["coverage"]["contract_sections"])) == 98
    assert len(manifest["coverage"]["tech_debts"]) == 37
    assert set(manifest["coverage"]["tech_debts"]) == {
        f"TD-{number:03d}" for number in range(1, 38)
    }


def test_default_scan_boundaries_exclude_non_authoritative_sources():
    manifest = load_manifest(REPO / "docs" / "llm-manifest.json")
    excluded = set(manifest["exclude_roots"])

    assert ".doc-migration-baseline" in excluded
    assert "docs/contract/history" in excluded
    assert "docs/contract/drafts" in excluded
    assert "docs/tech-debt/archive" in excluded
    assert all(not root.startswith(".doc-migration-baseline") for root in manifest["scan_roots"])


def test_repository_document_checks_pass():
    report = run_checks(REPO)
    assert report["errors"] == [], "\n".join(report["errors"])
    assert report["contract_coverage"] == "98/98"
    assert report["tech_debt_coverage"] == "37/37"


def test_frozen_baseline_hashes_are_unchanged():
    snapshot = REPO / ".doc-migration-baseline" / "snapshots" / "2026-07-19"
    expected = {}
    for line in (snapshot / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, filename = line.split(maxsplit=1)
        expected[filename] = digest

    for filename, digest in expected.items():
        actual = hashlib.sha256((snapshot / filename).read_bytes()).hexdigest()
        assert actual == digest


def test_snapshot_builder_refuses_to_overwrite(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "one.md").write_text("# One\n", encoding="utf-8")
    (docs / "llm-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "documents": [
                    {
                        "id": "contract-one",
                        "path": "docs/one.md",
                        "status": "current",
                        "authority": "canonical",
                        "document_type": "contract",
                        "legacy_order": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    target = build_snapshot(tmp_path, "2026-07-19")
    assert (target / "contract.original.md").is_file()
    with pytest.raises(FileExistsError):
        build_snapshot(tmp_path, "2026-07-19")

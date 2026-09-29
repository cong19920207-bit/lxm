# -*- coding: utf-8 -*-
"""STEP-006 controlled Phase0 evidence import command RED/GREEN tests."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest

import backend.scripts.import_realtime_voice_phase0_evidence as cli_module
from backend.constants.realtime_voice_config import VOICE_CAPABILITY_KEYS
from backend.services.realtime_voice_capability_service import (
    EVIDENCE_FINGERPRINT_FIELDS,
    realtime_voice_capability_service,
)


RUN_ID = "22222222-2222-4222-8222-222222222222"
TESTED_AT = "2026-09-02T01:02:03Z"
SECRET_SENTINEL = "sk-cli-import-secret-1234567890"


def _sha256(value) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _dimensions() -> dict[str, str]:
    return {
        "provider_profile": "doubao-s2s-strong-character",
        "model_version": "2.2.0.0",
        "protocol_profile": "dialogue-v3-binary-gzip-json-pcm16",
        "adapter_version": "b937a78-step004-evidence-v3",
        "sdk_version": "websockets-16.1",
        "evidence_suite_version": "step004-o01-v3",
    }


def _bundle() -> dict:
    dimensions = _dimensions()
    fingerprint = _sha256(
        {field: dimensions[field] for field in EVIDENCE_FINGERPRINT_FIELDS}
    )
    tested_at = datetime.fromisoformat(TESTED_AT.replace("Z", "+00:00"))
    records = []
    for index, capability_key in enumerate(VOICE_CAPABILITY_KEYS):
        result = "passed" if index % 2 == 0 else "failed"
        verified_at = TESTED_AT if result == "passed" else None
        expires_at = (
            (tested_at + timedelta(days=30)).astimezone(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            if result == "passed"
            else None
        )
        without_hash = {
            "evidence_report_id": str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"cli:{RUN_ID}:{capability_key}")
            ),
            "evidence_run_id": RUN_ID,
            "capability_key": capability_key,
            "verification_result": result,
            "source_type": "phase0_import",
            **dimensions,
            "evidence_fingerprint": fingerprint,
            "evidence_payload": {
                "schema_version": "phase0-capability-evidence/v3",
                "capability_status": "verified" if result == "passed" else "failed",
                "reason_code": f"controlled_{result}_conclusion",
                "degradation_mode": "next_turn",
                "event_evidence": [],
                "action_evidence": [],
                "runtime_conditions": {
                    "aec_enabled": True,
                    "background_resume_tested": False,
                    "bluetooth_tested": False,
                    "chrome_desktop": True,
                    "microphone_permission": True,
                    "network_profile": "baseline",
                    "real_provider": True,
                    "speaker_output": True,
                },
                "production_import_ready": False,
            },
            "tested_at": TESTED_AT,
            "verified_at": verified_at,
            "evidence_ttl_days_snapshot": 30,
            "expires_at": expires_at,
        }
        records.append(
            {**without_hash, "report_sha256": _sha256(without_hash)}
        )
    without_hash = {
        "schema_version": "phase0-evidence-bundle/v1",
        "evidence_run_id": RUN_ID,
        "record_count": 6,
        "production_source_of_truth": False,
        "records": records,
    }
    return {**without_hash, "bundle_sha256": _sha256(without_hash)}


def _write_bundle(tmp_path, bundle: dict | None = None):
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(bundle or _bundle(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


class _ForbiddenSessionFactory:
    def __init__(self) -> None:
        self.open_count = 0

    def __call__(self):
        self.open_count += 1
        raise AssertionError("database must not open before input validation")


class _Transaction:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        self.session.begin_entered += 1
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.session.begin_exited += 1
        if self.session.commit_error and exc_type is None:
            raise RuntimeError(SECRET_SENTINEL)
        return False


class _Session:
    def __init__(self, *, commit_error: bool = False) -> None:
        self.commit_error = commit_error
        self.begin_entered = 0
        self.begin_exited = 0
        self.rollback_count = 0
        self.closed = False

    def begin(self):
        return _Transaction(self)

    async def rollback(self):
        self.rollback_count += 1


class _SessionContext:
    def __init__(self, session: _Session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        self.session.closed = True
        return False


class _SessionFactory:
    def __init__(self, *, commit_error: bool = False) -> None:
        self.session = _Session(commit_error=commit_error)
        self.open_count = 0

    def __call__(self):
        self.open_count += 1
        return _SessionContext(self.session)


def _invoke(args, *, session_factory):
    stdout = StringIO()
    stderr = StringIO()
    exit_code = cli_module.main(
        args,
        session_factory=session_factory,
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize(
    "args",
    [
        ["--bundle", "ignored.json", "--operator-id", "1"],
        [
            "--bundle",
            "ignored.json",
            "--operator-id",
            "0",
            "--confirm",
            "CONFIRM",
        ],
        [
            "--bundle",
            "ignored.json",
            "--operator-id",
            "-1",
            "--confirm",
            "CONFIRM",
        ],
    ],
)
def test_cli_requires_exact_confirm_and_positive_operator_before_file_or_db(args):
    factory = _ForbiddenSessionFactory()
    exit_code, stdout, stderr = _invoke(args, session_factory=factory)

    assert exit_code == cli_module.EXIT_INPUT_REJECTED
    assert stdout == ""
    assert json.loads(stderr) == {
        "status": "input_rejected",
        "code": "VOICE_EVIDENCE_IMPORT_ARGUMENT_INVALID",
    }
    assert factory.open_count == 0


def test_cli_rejects_wrong_confirm_with_its_fixed_code_before_file_or_db():
    factory = _ForbiddenSessionFactory()
    exit_code, stdout, stderr = _invoke(
        [
            "--bundle",
            "ignored.json",
            "--operator-id",
            "1",
            "--confirm",
            "WRONG",
        ],
        session_factory=factory,
    )

    assert exit_code == cli_module.EXIT_INPUT_REJECTED
    assert stdout == ""
    assert json.loads(stderr) == {
        "status": "input_rejected",
        "code": "VOICE_EVIDENCE_IMPORT_CONFIRM_INVALID",
    }
    assert factory.open_count == 0


def test_cli_rejects_missing_directory_symlink_and_non_regular_file_before_db(
    tmp_path,
):
    valid = _write_bundle(tmp_path)
    directory = tmp_path / "directory"
    directory.mkdir()
    symlink = tmp_path / "bundle-link.json"
    symlink.symlink_to(valid)
    fifo = tmp_path / "bundle-fifo"
    os.mkfifo(fifo)
    factory = _ForbiddenSessionFactory()

    for path in (tmp_path / "missing.json", directory, symlink, fifo):
        exit_code, stdout, stderr = _invoke(
            [
                "--bundle",
                str(path),
                "--operator-id",
                "1",
                "--confirm",
                "CONFIRM",
            ],
            session_factory=factory,
        )
        assert exit_code == cli_module.EXIT_INPUT_REJECTED
        assert stdout == ""
        assert json.loads(stderr) == {
            "status": "input_rejected",
            "code": "VOICE_EVIDENCE_IMPORT_FILE_INVALID",
        }
    assert factory.open_count == 0


def test_cli_rejects_oversize_invalid_json_and_validator_failure_before_db(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    factory = _ForbiddenSessionFactory()
    monkeypatch.setattr(cli_module, "MAX_BUNDLE_BYTES", 32)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 33)
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{not-json", encoding="utf-8")
    rejected = tmp_path / "rejected.json"
    rejected.write_text("{}", encoding="utf-8")

    cases = (
        (oversized, "VOICE_EVIDENCE_IMPORT_FILE_TOO_LARGE"),
        (invalid_json, "VOICE_EVIDENCE_IMPORT_JSON_INVALID"),
        (rejected, "VOICE_EVIDENCE_IMPORT_BUNDLE_REJECTED"),
    )
    for path, expected_code in cases:
        exit_code, stdout, stderr = _invoke(
            [
                "--bundle",
                str(path),
                "--operator-id",
                "1",
                "--confirm",
                "CONFIRM",
            ],
            session_factory=factory,
        )
        assert exit_code == cli_module.EXIT_INPUT_REJECTED
        assert stdout == ""
        assert json.loads(stderr) == {
            "status": "input_rejected",
            "code": expected_code,
        }
    assert factory.open_count == 0


def test_cli_success_uses_one_session_transaction_and_prints_only_safe_summary(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    # This test owns CLI transaction/output behaviour, not the evidence
    # adjudicator (covered exhaustively by test_realtime_voice_step006_evidence_import).
    # Keep its compact synthetic payload behind the injected validator port so
    # stronger production causality checks cannot be bypassed by the real CLI.
    monkeypatch.setattr(
        cli_module,
        "validate_phase0_evidence_bundle",
        lambda candidate: candidate,
    )
    bundle = _bundle()
    path = _write_bundle(tmp_path, bundle)
    factory = _SessionFactory()
    captured = {}

    async def import_bundle(db, *, bundle, operator_id):
        captured.update(db=db, bundle=bundle, operator_id=operator_id)
        return {
            "evidence_run_id": RUN_ID,
            "record_count": 6,
            "bundle_sha256": bundle["bundle_sha256"],
            "draft_revision": 4,
            "idempotent": False,
            "unsafe_extra": SECRET_SENTINEL,
        }

    monkeypatch.setattr(
        realtime_voice_capability_service,
        "import_phase0_evidence_bundle",
        import_bundle,
    )
    exit_code, stdout, stderr = _invoke(
        [
            "--bundle",
            str(path),
            "--operator-id",
            "7",
            "--confirm",
            "CONFIRM",
        ],
        session_factory=factory,
    )

    assert exit_code == cli_module.EXIT_SUCCESS
    assert stderr == ""
    assert json.loads(stdout) == {
        "status": "success",
        "evidence_run_id": RUN_ID,
        "record_count": 6,
        "bundle_sha256": bundle["bundle_sha256"],
        "idempotent": False,
        "draft_revision": 4,
    }
    assert SECRET_SENTINEL not in stdout + stderr
    assert "event_evidence" not in stdout + stderr
    assert captured == {
        "db": factory.session,
        "bundle": bundle,
        "operator_id": 7,
    }
    assert factory.open_count == 1
    assert factory.session.begin_entered == 1
    assert factory.session.begin_exited == 1
    assert factory.session.rollback_count == 0
    assert factory.session.closed is True


@pytest.mark.parametrize("failure_kind", ["service", "commit"])
def test_cli_service_or_commit_failure_rolls_back_and_never_echoes_exception(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
):
    monkeypatch.setattr(
        cli_module,
        "validate_phase0_evidence_bundle",
        lambda candidate: candidate,
    )
    path = _write_bundle(tmp_path)
    factory = _SessionFactory(commit_error=failure_kind == "commit")

    async def import_bundle(db, *, bundle, operator_id):
        if failure_kind == "service":
            raise RuntimeError(SECRET_SENTINEL)
        return {
            "evidence_run_id": RUN_ID,
            "record_count": 6,
            "bundle_sha256": bundle["bundle_sha256"],
            "draft_revision": 4,
            "idempotent": False,
        }

    monkeypatch.setattr(
        realtime_voice_capability_service,
        "import_phase0_evidence_bundle",
        import_bundle,
    )
    exit_code, stdout, stderr = _invoke(
        [
            "--bundle",
            str(path),
            "--operator-id",
            "7",
            "--confirm",
            "CONFIRM",
        ],
        session_factory=factory,
    )

    assert exit_code == cli_module.EXIT_IMPORT_FAILED
    assert stdout == ""
    assert json.loads(stderr) == {
        "status": "import_failed",
        "code": "VOICE_EVIDENCE_IMPORT_FAILED",
    }
    assert SECRET_SENTINEL not in stdout + stderr
    assert factory.session.rollback_count == 1
    assert factory.session.closed is True

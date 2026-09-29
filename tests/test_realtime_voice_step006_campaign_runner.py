# -*- coding: utf-8 -*-
"""M1 campaign-only real runner harness tests (never call Provider)."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import importlib
from importlib import metadata
import inspect
import json
import os
import platform
import subprocess
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.constants.realtime_voice_config import (
    VOICE_CALL_CONFIG_KEY,
    build_canonical_voice_seed_manifest,
)
from backend.services.realtime_voice_capability_service import (
    _validate_evidence_record,
    compute_evidence_fingerprint,
)
from tests.test_realtime_voice_step006_evidence_import import (
    SECOND_RUN_ID,
    _record,
)


ACK_KEY = "supports_sentence_playback_ack"
SECRET = "campaign-provider-secret-SENTINEL"


def _subject():
    try:
        return importlib.import_module("scripts.realtime_voice_m1_campaign_runner")
    except ModuleNotFoundError:
        pytest.fail("缺少 M1 campaign-only runner harness")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    ["reserve-attempt", "advance-to-final-batch", "serve-direct", "connection", "ack"],
)
async def test_campaign_rejects_unbound_worktree_before_reading_frozen_inputs(
    mode: str, tmp_path: Path,
):
    subject = _subject()
    alternate_root = tmp_path / "unhashed-phase0"
    alternate_root.mkdir()
    args = subject._build_argument_parser().parse_args(
        [mode, "--phase0-root", str(alternate_root)]
    )

    with pytest.raises(ValueError, match="Phase0 worktree 必须与 runtime closure 一致"):
        await subject._run_cli(args)


def _draft() -> dict:
    subject = _subject()
    config = build_canonical_voice_seed_manifest(
        {
            "config_key": "persona",
            "version": 1,
            "content_sha256": "sha256:" + "a" * 64,
        }
    )[VOICE_CALL_CONFIG_KEY]
    config["s2s"]["protocol_profile"] = subject.PHASE0_PROTOCOL_PROFILE
    config["s2s"]["adapter_version"] = subject.PHASE0_ADAPTER_VERSION
    return config


def _phase0_ack_record() -> dict:
    record = deepcopy(_record(SECOND_RUN_ID, ACK_KEY))
    record["adapter_version"] = _subject().PHASE0_ADAPTER_VERSION
    record["evidence_suite_version"] = _subject().PHASE0_EVIDENCE_SUITE_VERSION
    record["sdk_version"] = f"websockets-{metadata.version('websockets')}"
    record["evidence_fingerprint"] = compute_evidence_fingerprint(record)
    without_hash = {
        key: value for key, value in record.items() if key != "report_sha256"
    }
    record["report_sha256"] = hashlib.sha256(
        json.dumps(
            without_hash,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return record


def _bundle(record: dict) -> dict:
    return {
        "schema_version": "phase0-evidence-bundle/v1",
        "evidence_run_id": record["evidence_run_id"],
        "record_count": 6,
        "production_source_of_truth": False,
        "records": [deepcopy(record)],
        "bundle_sha256": "not-consumed-by-campaign-runner",
    }


def _write_phase0_public_defaults(root: Path) -> None:
    target = root / "backend" / "phase0_realtime_voice" / "s2s_client.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                'DEFAULT_S2S_ENDPOINT = "wss://phase0.example/realtime"',
                'DEFAULT_RESOURCE_ID = "phase0.resource"',
                'DEFAULT_S2S_MODEL = "phase0-default-model"',
                'DEFAULT_S2S_SPEAKER = "phase0-default-speaker"',
            ]
        ),
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_files(tmp_path: Path) -> tuple[Path, Path, tuple[str, ...]]:
    project_root = tmp_path / "project"
    project_root.mkdir()
    required_paths = ("runtime/a.py", "runtime/b.py")
    for index, relative in enumerate(required_paths):
        target = project_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"runtime-{index}\n", encoding="utf-8")
    manifest = {
        "schema_version": "m1-campaign-runtime-manifest/v2",
        "files": [
            {"path": relative, "sha256": _sha256_file(project_root / relative)}
            for relative in required_paths
        ],
        **_runtime_identity_fixture(),
    }
    manifest_path = project_root / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    matrix_path = project_root / "matrix.json"
    matrix_path.write_text('{"scenario_ids":["S01","S02"]}', encoding="utf-8")
    return matrix_path, manifest_path, required_paths


def _campaign_baseline(*, marker: str = "a") -> dict:
    dimensions = {
        "provider_profile": "doubao-s2s-strong-character",
        "model_version": "2.2.0.0",
        "protocol_profile": "dialogue-v3-binary-gzip-json-pcm16",
        "adapter_version": "b937a78-step004-evidence-v3",
        "sdk_version": "websockets-15.0.1",
        "evidence_suite_version": "step004-o01-v3",
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            dimensions,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "m1-campaign-baseline/v1",
        "public_provider_settings_sha256": marker * 64,
        "voice_draft_sha256": marker * 64,
        "evidence_dimensions": dimensions,
        "evidence_fingerprint": fingerprint,
    }


_RUNTIME_PACKAGE_NAMES = (
    "asyncmy",
    "bcrypt",
    "fastapi",
    "httpx",
    "PyJWT",
    "pydantic",
    "pydantic-settings",
    "python-dotenv",
    "redis",
    "SQLAlchemy",
    "starlette",
    "uvicorn",
    "websockets",
)


def _runtime_identity_fixture() -> dict:
    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "packages": [
            {"distribution": name, "version": metadata.version(name)}
            for name in _RUNTIME_PACKAGE_NAMES
        ],
    }


def _write_complete_runtime_fixture(project_root: Path) -> tuple[Path, ...]:
    paths = (
        Path("admin/pages/voice-config.html"),
        Path("admin/static/js/voice-config-admin.js"),
        Path("backend/a.py"),
        Path("scripts/realtime_voice_m1_campaign_runner.py"),
        Path(
            "tmp/phase0-step004-s01-fix-20260906/backend/phase0_realtime_voice/a.py"
        ),
        Path(
            "tmp/phase0-step004-s01-fix-20260906/frontend/pages/"
            "phase0_realtime_voice.html"
        ),
        Path("tmp/phase0-step004-s01-fix-20260906/requirements.txt"),
    )
    for index, relative in enumerate(paths):
        target = project_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"runtime-closure-{index}\n", encoding="utf-8")
    return paths


class FakeWorker:
    def __init__(self, record: dict, *, secret: str = SECRET) -> None:
        self.record = deepcopy(record)
        self.secret = secret
        self.order: list[str] = []
        self.started = False
        self.ended = False
        self.stopped = False
        self.session_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

    def __repr__(self) -> str:
        return "FakeWorker(redacted=True)"

    async def start(self) -> None:
        self.started = True
        self.order.append("start")

    async def create_connection_session(self, *, user_id: int) -> dict:
        assert user_id == 101
        self.order.append("create")
        return {"session_id": self.session_id}

    async def get_session(self, session_id: str) -> dict:
        assert session_id == self.session_id
        self.order.append("session")
        return {
            "session_id": session_id,
            "evidence_run_id": self.record["evidence_run_id"],
        }

    async def fetch_evidence(self, session_id: str) -> dict:
        assert session_id == self.session_id
        self.order.append("final_evidence" if self.ended else "live_evidence")
        return _bundle(self.record)

    async def end_session(self, session_id: str) -> None:
        assert session_id == self.session_id
        self.ended = True
        self.order.append("end")

    async def stop(self) -> None:
        self.stopped = True
        self.order.append("stop")


def _attempt_now(record: dict) -> datetime:
    tested_at = datetime.fromisoformat(record["tested_at"].replace("Z", "+00:00"))
    return tested_at - timedelta(seconds=1)


@pytest.mark.asyncio
async def test_connection_uses_one_fresh_worker_and_gracefully_ends_before_return():
    subject = _subject()
    record = _phase0_ack_record()
    workers: list[FakeWorker] = []

    def factory(**kwargs):
        worker = FakeWorker(record, secret=kwargs["secret"])
        workers.append(worker)
        return worker

    runner = subject.CampaignVoiceTestRunner(
        worker_factory=factory,
        validator=lambda value: value,
        read_session_id=lambda: None,
        registry=subject.ConsumedEvidenceRegistry(),
        user_id=101,
        now=lambda: _attempt_now(record),
    )

    result = await runner.run_connection(draft_snapshot=_draft(), secret=SECRET)
    await runner.aclose()

    assert result["status"] == "passed"
    assert result["failure_category"] == "none"
    assert len(workers) == 1
    assert workers[0].order == ["start", "create", "end", "stop"]
    assert SECRET not in json.dumps(result, ensure_ascii=False)
    assert SECRET not in repr(runner)
    assert SECRET not in repr(workers[0])


@pytest.mark.asyncio
async def test_ack_finalizes_session_before_final_evidence_and_validates_admin_record():
    subject = _subject()
    record = _phase0_ack_record()
    worker = FakeWorker(record)
    validation_order: list[str] = []

    def validator(candidate):
        validation_order.extend(worker.order)
        return _validate_evidence_record(
            candidate,
            expected_source="admin_capability_test",
            allow_error=True,
            path="record",
        )

    async def read_session_id():
        return worker.session_id

    runner = subject.CampaignVoiceTestRunner(
        worker_factory=lambda **_kwargs: worker,
        validator=validator,
        read_session_id=read_session_id,
        registry=subject.ConsumedEvidenceRegistry(),
        user_id=101,
        now=lambda: _attempt_now(record),
        poll_interval_seconds=0,
    )

    result = await runner.run_capability(
        capability_key=ACK_KEY,
        draft_snapshot=_draft(),
        secret=SECRET,
    )
    await runner.aclose()

    assert result["status"] == record["verification_result"]
    assert result["failure_category"] == "protocol_error"
    converted = result["evidence_record"]
    assert converted["source_type"] == "admin_capability_test"
    assert converted["evidence_payload"]["runtime_conditions"] == {
        "real_provider": True,
        "network_profile": "admin_test",
    }
    without_hash = {
        key: value for key, value in converted.items() if key != "report_sha256"
    }
    assert converted["report_sha256"] == hashlib.sha256(
        json.dumps(
            without_hash,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert worker.order.index("end") < worker.order.index("final_evidence")
    assert "final_evidence" in validation_order
    assert worker.order[-1] == "stop"


def test_phase0_ack_conversion_is_accepted_by_production_admin_validator():
    subject = _subject()
    converted = subject.convert_phase0_ack_record(
        _phase0_ack_record(),
        draft_snapshot=_draft(),
    )

    normalized = _validate_evidence_record(
        converted,
        expected_source="admin_capability_test",
        allow_error=True,
        path="record",
    )

    assert normalized == converted


def test_phase0_ack_conversion_rejects_any_draft_evidence_dimension_mismatch():
    subject = _subject()
    record = _phase0_ack_record()
    record["model_version"] = "unexpected-model"

    with pytest.raises(ValueError, match="六维"):
        subject.convert_phase0_ack_record(record, draft_snapshot=_draft())


def test_isolated_phase0_producer_bundle_crosses_into_main_validators_without_provider():
    """Permanent producer/consumer drift guard; subprocess only builds local facts."""

    subject = _subject()
    phase0_root = (
        Path(__file__).resolve().parents[1]
        / "tmp"
        / "phase0-step004-s01-fix-20260906"
    )
    code = """
import json
import runpy
import uuid
from datetime import datetime, timezone

namespace = runpy.run_path("tests/test_phase0_step004_evidence.py")
events, actions, observations = namespace["_complete_events"]()
capability_keys = namespace["CAPABILITY_KEYS"]
bundle = namespace["build_evidence_bundle"](
    events=events,
    actions=actions,
    observations=observations,
    model_version="2.2.0.0",
    evidence_run_id=str(uuid.uuid4()),
    evidence_report_ids={key: str(uuid.uuid4()) for key in capability_keys},
    tested_at=datetime.now(timezone.utc),
    runtime_conditions={
        "real_provider": True,
        "chrome_desktop": True,
        "microphone_permission": True,
        "speaker_output": True,
        "aec_enabled": True,
        "bluetooth_tested": False,
        "background_resume_tested": False,
        "network_profile": "baseline",
    },
)
print(json.dumps(bundle, ensure_ascii=False, sort_keys=True))
"""
    child_env = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR")
        if os.environ.get(key)
    }
    child_env["PYTHONPATH"] = str(phase0_root)
    child_env["PYTHONUNBUFFERED"] = "1"
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    assert set(child_env) <= {
        "PATH",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
    }
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=phase0_root,
        env=child_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.stderr == ""
    assert SECRET not in completed.stdout

    from backend.services.realtime_voice_capability_service import (
        validate_phase0_evidence_bundle,
    )

    validated_bundle = validate_phase0_evidence_bundle(json.loads(completed.stdout))
    assert len(validated_bundle["records"]) == 6
    ack_record = next(
        record
        for record in validated_bundle["records"]
        if record["capability_key"] == ACK_KEY
    )
    converted = subject.convert_phase0_ack_record(
        ack_record,
        draft_snapshot=_draft(),
    )
    assert (
        _validate_evidence_record(
            converted,
            expected_source="admin_capability_test",
            allow_error=True,
            path="record",
        )
        == converted
    )


@pytest.mark.asyncio
async def test_consumed_or_pre_attempt_evidence_is_rejected_and_never_returned():
    subject = _subject()
    record = _phase0_ack_record()
    worker = FakeWorker(record)
    registry = subject.ConsumedEvidenceRegistry()
    registry.consume(record["evidence_run_id"], record["evidence_report_id"])

    async def read_session_id():
        return worker.session_id

    runner = subject.CampaignVoiceTestRunner(
        worker_factory=lambda **_kwargs: worker,
        validator=lambda value: value,
        read_session_id=read_session_id,
        registry=registry,
        user_id=101,
        now=lambda: _attempt_now(record),
        poll_interval_seconds=0,
    )

    result = await runner.run_capability(
        capability_key=ACK_KEY,
        draft_snapshot=_draft(),
        secret=SECRET,
    )
    await runner.aclose()

    assert result["status"] == "error"
    assert result["failure_category"] == "evidence_invalid"
    assert "evidence_record" not in result
    assert worker.ended is True
    assert worker.stopped is True


@pytest.mark.asyncio
async def test_user_window_timeout_is_normalized_and_aclose_stops_worker_without_retry():
    subject = _subject()
    record = _phase0_ack_record()
    worker = FakeWorker(record)
    factory_calls = 0

    def factory(**_kwargs):
        nonlocal factory_calls
        factory_calls += 1
        return worker

    async def never_supplies_session():
        await asyncio.Event().wait()

    runner = subject.CampaignVoiceTestRunner(
        worker_factory=factory,
        validator=lambda value: value,
        read_session_id=never_supplies_session,
        registry=subject.ConsumedEvidenceRegistry(),
        user_id=101,
        now=lambda: _attempt_now(record),
        user_window_seconds=0.01,
    )

    result = await runner.run_capability(
        capability_key=ACK_KEY,
        draft_snapshot=_draft(),
        secret=SECRET,
    )
    await runner.aclose()

    assert result["status"] == "error"
    assert result["failure_category"] == "timeout"
    assert factory_calls == 1
    assert worker.stopped is True


@pytest.mark.asyncio
async def test_draft_must_match_phase0_protocol_before_worker_or_secret_use():
    subject = _subject()
    record = _phase0_ack_record()
    calls = 0

    def factory(**_kwargs):
        nonlocal calls
        calls += 1
        return FakeWorker(record)

    draft = _draft()
    draft["s2s"]["adapter_version"] = "voice_adapter_v1"
    runner = subject.CampaignVoiceTestRunner(
        worker_factory=factory,
        validator=lambda value: value,
        read_session_id=lambda: None,
        registry=subject.ConsumedEvidenceRegistry(),
        user_id=101,
        now=lambda: _attempt_now(record),
    )

    result = await runner.run_connection(draft_snapshot=draft, secret=SECRET)
    await runner.aclose()

    assert result["failure_category"] == "invalid_config"
    assert calls == 0


def test_override_scope_preserves_real_auth_and_database_dependencies():
    subject = _subject()
    runner_dependency = object()
    auth_dependency = object()
    db_dependency = object()
    app = SimpleNamespace(
        dependency_overrides={
            auth_dependency: "real-auth",
            db_dependency: "real-db",
        }
    )

    with subject.campaign_runner_override(app, runner_dependency, lambda: object()):
        assert app.dependency_overrides[runner_dependency] is not None
        assert app.dependency_overrides[auth_dependency] == "real-auth"
        assert app.dependency_overrides[db_dependency] == "real-db"

    assert runner_dependency not in app.dependency_overrides
    assert app.dependency_overrides[auth_dependency] == "real-auth"
    assert app.dependency_overrides[db_dependency] == "real-db"


@pytest.mark.parametrize(
    ("database_name", "token", "expected"),
    [
        ("lxm", "jwt", "MYSQL_DATABASE"),
        ("lxm_step006_m1_campaign_20260902", "", "REALTIME_VOICE_M1_ADMIN_JWT"),
    ],
)
def test_campaign_environment_requires_isolated_database_and_real_jwt(
    database_name: str,
    token: str,
    expected: str,
):
    subject = _subject()
    with pytest.raises(ValueError, match=expected):
        subject.validate_campaign_environment(
            {
                "MYSQL_DATABASE": database_name,
                "REDIS_DB": "15",
                "REALTIME_VOICE_M1_ADMIN_JWT": token,
            }
        )


def test_phase0_child_env_uses_root_business_db_not_campaign_db_and_only_passed_provider_secret(
    tmp_path: Path,
):
    subject = _subject()
    project_env = tmp_path / ".env"
    project_env.write_text(
        "\n".join(
            [
                "MYSQL_HOST=mysql-container",
                "MYSQL_PORT=3306",
                "MYSQL_USER=business-user",
                "MYSQL_PASSWORD=business-password",
                "MYSQL_DATABASE=business-db",
                "REDIS_HOST=redis-container",
                "REDIS_PORT=6379",
                "REDIS_PASSWORD=business-redis-password",
                "REDIS_DB=3",
                "PHASE0_DOUBAO_S2S_APP_ID=phase0-app-id",
                "PHASE0_DOUBAO_S2S_ACCESS_KEY=stale-provider-secret",
                "UNRELATED_SECRET=must-not-enter-child",
            ]
        ),
        encoding="utf-8",
    )

    child = subject.build_phase0_child_environment(
        project_env_path=project_env,
        phase0_root=tmp_path / "phase0",
        draft_snapshot=_draft(),
        secret=SECRET,
        parent_environ={
            "PATH": "/safe/bin",
            "MYSQL_DATABASE": "lxm_step006_m1_campaign_20260902",
            "REDIS_DB": "15",
        },
    )

    assert child["MYSQL_DATABASE"] == "business-db"
    assert child["REDIS_DB"] == "3"
    assert child["MYSQL_HOST"] == "127.0.0.1"
    assert child["REDIS_HOST"] == "127.0.0.1"
    assert child["PHASE0_DOUBAO_S2S_ACCESS_KEY"] == SECRET
    assert child["PHASE0_DOUBAO_S2S_APP_ID"] == "phase0-app-id"
    assert child["PHASE0_DOUBAO_S2S_MODEL"] == _draft()["s2s"]["model_version"]
    assert child["PHASE0_DOUBAO_S2S_SPEAKER"] == _draft()["voice"]["voice_id"]
    assert "UNRELATED_SECRET" not in child
    assert "DOUBAO_S2S_ACCESS_KEY" not in child
    assert set(child) == {
        "PATH",
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "REDIS_DB",
        "PHASE0_DOUBAO_S2S_APP_ID",
        "PHASE0_DOUBAO_S2S_ACCESS_KEY",
        "PHASE0_DOUBAO_S2S_RESOURCE_ID",
        "PHASE0_DOUBAO_S2S_ENDPOINT",
        "PHASE0_DOUBAO_S2S_MODEL",
        "PHASE0_DOUBAO_S2S_SPEAKER",
        "PHASE0_SETTINGS_PATH",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
    }
    assert child["MYSQL_PASSWORD"] == "business-password"
    assert child["REDIS_PASSWORD"] == "business-redis-password"


def test_phase0_child_env_rejects_campaign_database_or_redis(tmp_path: Path):
    subject = _subject()
    project_env = tmp_path / ".env"
    project_env.write_text(
        "MYSQL_PORT=3306\nMYSQL_USER=u\nMYSQL_PASSWORD=p\n"
        "MYSQL_DATABASE=lxm_step006_m1_campaign_20260902\n"
        "REDIS_PORT=6379\nREDIS_PASSWORD=\nREDIS_DB=15\n"
        "PHASE0_DOUBAO_S2S_APP_ID=app-id\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="campaign"):
        subject.build_phase0_child_environment(
            project_env_path=project_env,
            phase0_root=tmp_path / "phase0",
            draft_snapshot=_draft(),
            secret=SECRET,
            parent_environ={"PATH": "/safe/bin"},
        )


def test_public_provider_settings_merge_project_env_with_current_phase0_v3_defaults(
    tmp_path: Path,
):
    subject = _subject()
    phase0_root = tmp_path / "phase0"
    _write_phase0_public_defaults(phase0_root)
    project_env = tmp_path / ".env"
    project_env.write_text(
        "\n".join(
            [
                "# PHASE0_DOUBAO_S2S_ENDPOINT=wss://commented.invalid",
                "PHASE0_DOUBAO_S2S_MODEL=project-model",
                "PHASE0_DOUBAO_S2S_SPEAKER=project-speaker",
                "PHASE0_DOUBAO_S2S_ACCESS_KEY=must-not-be-returned",
            ]
        ),
        encoding="utf-8",
    )

    settings = subject.load_phase0_public_provider_settings(
        project_env_path=project_env,
        phase0_root=phase0_root,
    )

    assert settings == {
        "endpoint": "wss://phase0.example/realtime",
        "resource_id": "phase0.resource",
        "model_version": "project-model",
        "voice_id": "project-speaker",
    }
    assert "must-not-be-returned" not in repr(settings)


@pytest.mark.asyncio
async def test_bootstrap_directly_seeds_exact_project_phase0_draft_without_secret(
    tmp_path: Path,
):
    subject = _subject()
    phase0_root = tmp_path / "phase0"
    _write_phase0_public_defaults(phase0_root)
    project_env = tmp_path / ".env"
    project_env.write_text(
        "PHASE0_DOUBAO_S2S_ENDPOINT=wss://project.example/realtime\n"
        "PHASE0_DOUBAO_S2S_RESOURCE_ID=project.resource\n"
        "PHASE0_DOUBAO_S2S_MODEL=project-model\n"
        "PHASE0_DOUBAO_S2S_SPEAKER=project-speaker\n"
        "PHASE0_DOUBAO_S2S_ACCESS_KEY=bootstrap-secret-must-not-cross\n",
        encoding="utf-8",
    )
    seeded: dict = {}

    async def seed_database(**kwargs):
        seeded.update(deepcopy(kwargs))

    username, password = await subject.bootstrap_campaign_prerequisites(
        project_env_path=project_env,
        phase0_root=phase0_root,
        seed_database=seed_database,
        password_factory=lambda: "Generated1!CampaignPassword",
        password_hasher=lambda _value: "bcrypt-hash",
    )

    assert username == "m1_campaign_admin"
    assert password == "Generated1!CampaignPassword"
    draft = seeded["voice_draft"]
    expected = {
        "endpoint": "wss://project.example/realtime",
        "resource_id": "project.resource",
        "model_version": "project-model",
        "protocol_profile": subject.PHASE0_PROTOCOL_PROFILE,
        "adapter_version": subject.PHASE0_ADAPTER_VERSION,
        "credential_ref": "PHASE0_DOUBAO_S2S_ACCESS_KEY",
        "voice_id": "project-speaker",
    }
    actual = dict(draft["s2s"])
    actual["voice_id"] = draft["voice"]["voice_id"]
    assert {key: actual[key] for key in expected} == expected
    assert seeded["password_hash"] == "bcrypt-hash"
    assert "bootstrap-secret-must-not-cross" not in repr(seeded)


def test_bootstrap_accepts_only_production_valid_capability_evolution():
    subject = _subject()
    from backend.services.realtime_voice_capability_service import (
        _project_record_to_capability,
    )

    base = _draft()
    evolved = deepcopy(base)
    converted = subject.convert_phase0_ack_record(
        _phase0_ack_record(),
        draft_snapshot=base,
    )
    evolved["capabilities"][ACK_KEY] = _project_record_to_capability(
        evolved["capabilities"][ACK_KEY],
        converted,
    )
    subject.validate_existing_campaign_draft(evolved, expected_base=base)

    non_capability_drift = deepcopy(evolved)
    non_capability_drift["s2s"]["endpoint"] = "wss://drift.invalid/realtime"
    with pytest.raises(ValueError, match="非 capability"):
        subject.validate_existing_campaign_draft(
            non_capability_drift,
            expected_base=base,
        )

    forged_capability = deepcopy(base)
    forged_capability["capabilities"][ACK_KEY]["enabled"] = True
    with pytest.raises(ValueError, match="capabilities"):
        subject.validate_existing_campaign_draft(
            forged_capability,
            expected_base=base,
        )


def test_frozen_runtime_manifest_is_exact_and_detects_dependency_drift(tmp_path: Path):
    subject = _subject()
    matrix_path, manifest_path, required_paths = _frozen_files(tmp_path)
    project_root = tmp_path / "project"
    ledger_path = subject.campaign_ledger_path(
        "m1-campaign-20260902", project_root=project_root
    )

    frozen = subject.resolve_frozen_campaign(
        campaign_id="m1-campaign-20260902",
        matrix_path=matrix_path,
        runtime_manifest_path=manifest_path,
        ledger_path=ledger_path,
        project_root=project_root,
        required_runtime_paths=required_paths,
    )

    assert frozen.matrix_sha256 == _sha256_file(matrix_path)
    assert len(frozen.runtime_manifest_sha256) == 64
    (tmp_path / "project" / required_paths[0]).write_text(
        "runtime-drift\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="runtime manifest"):
        subject.resolve_frozen_campaign(
            campaign_id="m1-campaign-20260902",
            matrix_path=matrix_path,
            runtime_manifest_path=manifest_path,
            ledger_path=ledger_path,
            project_root=project_root,
            required_runtime_paths=required_paths,
        )


def test_provider_attempt_ledger_binds_campaign_matrix_runtime_and_blocks_16th(
    tmp_path: Path,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    ledger_path = subject.campaign_ledger_path(
        "m1-campaign-20260902", project_root=project_root
    )
    kwargs = {
        "project_root": project_root,
        "ledger_path": ledger_path,
        "campaign_id": "m1-campaign-20260902",
        "matrix_sha256": "a" * 64,
        "runtime_manifest_sha256": "b" * 64,
        "baseline": _campaign_baseline(),
    }
    receipts = [
        subject.reserve_provider_attempt(
            **kwargs,
            attempt_kind="s01_start_session" if index == 0 else "s02_start_session",
        )
        for index in range(15)
    ]

    assert [receipt["attempt_ordinal"] for receipt in receipts] == list(range(1, 16))
    assert receipts[-1]["remaining_attempts"] == 0
    before = ledger_path.read_bytes()
    with pytest.raises(RuntimeError, match="15"):
        subject.reserve_provider_attempt(**kwargs, attempt_kind="s06_start_session")
    assert ledger_path.read_bytes() == before
    with pytest.raises(ValueError, match="绑定"):
        subject.reserve_provider_attempt(
            **{**kwargs, "matrix_sha256": "c" * 64},
            attempt_kind="s06_start_session",
        )
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert set(ledger) == {
        "schema_version",
        "campaign_id",
        "max_provider_attempts",
        "active_baseline_epoch",
        "baseline_epochs",
        "attempts",
    }
    assert ledger["active_baseline_epoch"] == 1
    assert len(ledger["baseline_epochs"]) == 1
    assert ledger["baseline_epochs"][0]["matrix_sha256"] == "a" * 64
    assert ledger["baseline_epochs"][0]["runtime_manifest_sha256"] == "b" * 64
    assert all(
        set(attempt)
        == {
            "attempt_id",
            "attempt_ordinal",
            "baseline_epoch",
            "attempt_kind",
            "reserved_at",
        }
        for attempt in ledger["attempts"]
    )
    assert not list(ledger_path.parent.rglob("*.tmp"))


def test_provider_attempt_ledger_concurrent_reservations_never_exceed_15(tmp_path: Path):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-campaign-concurrent"
    kwargs = {
        "project_root": project_root,
        "ledger_path": subject.campaign_ledger_path(
            campaign_id, project_root=project_root
        ),
        "campaign_id": campaign_id,
        "matrix_sha256": "d" * 64,
        "runtime_manifest_sha256": "e" * 64,
        "baseline": _campaign_baseline(),
        "attempt_kind": "s03_start_session",
    }

    def reserve_once(_index: int):
        try:
            return subject.reserve_provider_attempt(**kwargs)
        except RuntimeError:
            return None

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(reserve_once, range(20)))

    successes = [result for result in results if result is not None]
    assert len(successes) == 15
    assert sorted(item["attempt_ordinal"] for item in successes) == list(range(1, 16))
    ledger = json.loads(kwargs["ledger_path"].read_text(encoding="utf-8"))
    assert len(ledger["attempts"]) == 15


def test_provider_attempt_ledger_rejects_unknown_fields_without_repair(tmp_path: Path):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-campaign-tampered"
    ledger_path = subject.campaign_ledger_path(
        campaign_id, project_root=project_root
    )
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": "m1-campaign-provider-attempt-ledger/v1",
                    "campaign_id": campaign_id,
                "matrix_sha256": "a" * 64,
                "runtime_manifest_sha256": "b" * 64,
                "max_provider_attempts": 15,
                "attempts": [],
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )
    before = ledger_path.read_bytes()

    with pytest.raises(ValueError, match="schema"):
        subject.reserve_provider_attempt(
            project_root=project_root,
            ledger_path=ledger_path,
            campaign_id=campaign_id,
            matrix_sha256="a" * 64,
            runtime_manifest_sha256="b" * 64,
            baseline=_campaign_baseline(),
            attempt_kind="s04_start_session",
        )
    assert ledger_path.read_bytes() == before


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = deepcopy(payload)
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http failed with raw secret " + SECRET)

    def json(self) -> dict:
        return deepcopy(self._payload)


class _FakeHttpClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, dict | None, dict | None]] = []
        self.closed = False

    async def request(self, method: str, path: str, *, json=None, headers=None):
        self.requests.append((method, path, deepcopy(json), deepcopy(headers)))
        return self.responses.pop(0)

    async def aclose(self) -> None:
        self.closed = True


class _FakeProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        return int(self.returncode or 0)


@pytest.mark.asyncio
async def test_phase0_subprocess_worker_is_fresh_silent_and_uses_http_lifecycle(
    tmp_path: Path,
):
    subject = _subject()
    phase0_root = tmp_path / "phase0"
    _write_phase0_public_defaults(phase0_root)
    project_env = tmp_path / ".env"
    project_env.write_text(
        "MYSQL_PORT=3306\nMYSQL_USER=u\nMYSQL_PASSWORD=p\nMYSQL_DATABASE=business\n"
        "REDIS_PORT=6379\nREDIS_PASSWORD=\nREDIS_DB=0\n"
        "PHASE0_DOUBAO_S2S_APP_ID=app-id\n"
        f"PHASE0_DOUBAO_S2S_ENDPOINT={_draft()['s2s']['endpoint']}\n"
        f"PHASE0_DOUBAO_S2S_RESOURCE_ID={_draft()['s2s']['resource_id']}\n"
        f"PHASE0_DOUBAO_S2S_MODEL={_draft()['s2s']['model_version']}\n"
        f"PHASE0_DOUBAO_S2S_SPEAKER={_draft()['voice']['voice_id']}\n",
        encoding="utf-8",
    )
    session_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    run_id = _phase0_ack_record()["evidence_run_id"]
    bundle = _bundle(_phase0_ack_record())
    http = _FakeHttpClient(
        [
            _FakeResponse({"code": 0, "data": {"status": "ok"}}),
            _FakeResponse(
                {
                    "code": 0,
                    "data": {"session_id": session_id, "evidence_run_id": run_id},
                }
            ),
            _FakeResponse({"code": 0, "data": {"ended": True}}),
            _FakeResponse(bundle),
        ]
    )
    process = _FakeProcess()
    launches: list[tuple[tuple, dict]] = []

    async def launch(*args, **kwargs):
        launches.append((args, deepcopy(kwargs)))
        return process

    attempt_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    attempt_dir = tmp_path / "attempt-reservations"
    worker = subject.Phase0SubprocessWorker(
        phase0_root=phase0_root,
        project_env_path=project_env,
        draft_snapshot=_draft(),
        secret=SECRET,
        port=18765,
        process_factory=launch,
        http_client=http,
        parent_environ={"PATH": "/safe/bin"},
        startup_timeout_seconds=0.1,
        campaign_attempt={
            "attempt_directory": attempt_dir,
            "campaign_id": "m1-admin-worker",
            "matrix_sha256": "a" * 64,
            "runtime_manifest_sha256": "b" * 64,
            "baseline_epoch": 1,
            "attempt_id": attempt_id,
            "attempt_ordinal": 3,
            "attempt_kind": "admin_connection",
            "fresh_admin_worker": True,
        },
    )

    await worker.start()
    created = await worker.create_connection_session(user_id=101)
    await worker.end_session(session_id)
    exported = await worker.fetch_evidence(session_id)
    await worker.stop()

    assert created["session_id"] == session_id
    assert exported == bundle
    assert len(launches) == 1
    args, kwargs = launches[0]
    assert SECRET not in repr(args)
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["env"]["PHASE0_DOUBAO_S2S_ACCESS_KEY"] == SECRET
    assert kwargs["env"]["MYSQL_DATABASE"] == "business"
    assert kwargs["env"]["REDIS_DB"] == "0"
    assert {
        key: kwargs["env"][key]
        for key in (
            "PHASE0_M1_ATTEMPT_DIR",
            "PHASE0_M1_CAMPAIGN_ID",
            "PHASE0_M1_MATRIX_SHA256",
            "PHASE0_M1_RUNTIME_MANIFEST_SHA256",
            "PHASE0_M1_BASELINE_EPOCH",
            "PHASE0_M1_EXPECTED_START_ATTEMPT_KIND",
            "PHASE0_M1_EXPECTED_START_ATTEMPT_ORDINAL",
            "PHASE0_M1_FRESH_ADMIN_WORKER",
        )
    } == {
        "PHASE0_M1_ATTEMPT_DIR": str(attempt_dir),
        "PHASE0_M1_CAMPAIGN_ID": "m1-admin-worker",
        "PHASE0_M1_MATRIX_SHA256": "a" * 64,
        "PHASE0_M1_RUNTIME_MANIFEST_SHA256": "b" * 64,
        "PHASE0_M1_BASELINE_EPOCH": "1",
        "PHASE0_M1_EXPECTED_START_ATTEMPT_KIND": "admin_connection",
        "PHASE0_M1_EXPECTED_START_ATTEMPT_ORDINAL": "3",
        "PHASE0_M1_FRESH_ADMIN_WORKER": "1",
    }
    assert http.requests[1] == (
        "POST",
        "/api/phase0/realtime-voice/sessions",
        {
            "user_id": 101,
            "voice": _draft()["voice"]["voice_id"],
            "persona_label": "active",
            "net_profile": "baseline",
            "mock_s2s": False,
        },
        {"X-LXM-M1-Attempt-Id": attempt_id},
    )
    assert http.requests[2][:2] == (
        "DELETE",
        f"/api/phase0/realtime-voice/sessions/{session_id}",
    )
    assert http.requests[3][:2] == (
        "GET",
        f"/api/phase0/realtime-voice/sessions/{session_id}/evidence.json",
    )
    assert process.terminated is True
    assert http.closed is True
    assert SECRET not in repr(worker)


@pytest.mark.asyncio
async def test_worker_stop_is_bounded_and_terminates_process_even_when_cancelled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    subject = _subject()
    monkeypatch.setattr(subject, "WORKER_CLIENT_CLOSE_SECONDS", 0.01)
    monkeypatch.setattr(subject, "WORKER_TERMINATE_WAIT_SECONDS", 0.01)
    monkeypatch.setattr(subject, "WORKER_KILL_WAIT_SECONDS", 0.05)

    class BlockingClient:
        def __init__(self):
            self.close_started = asyncio.Event()

        async def aclose(self):
            self.close_started.set()
            await asyncio.Event().wait()

    class StubbornProcess:
        def __init__(self):
            self.returncode = None
            self.terminated = False
            self.killed = False
            self._killed = asyncio.Event()

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True
            self.returncode = -9
            self._killed.set()

        async def wait(self):
            await self._killed.wait()
            return -9

    client = BlockingClient()
    process = StubbornProcess()
    worker = subject.Phase0SubprocessWorker(
        phase0_root=tmp_path,
        project_env_path=tmp_path / ".env",
        draft_snapshot=_draft(),
        secret=SECRET,
    )
    worker._client = client
    worker._process = process

    stop_task = asyncio.create_task(worker.stop())
    await client.close_started.wait()
    stop_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(stop_task, timeout=0.25)

    assert process.terminated is True
    assert process.killed is True
    assert worker._client is None
    assert worker._process is None


@pytest.mark.asyncio
async def test_cancellable_posix_session_input_removes_reader_and_restores_fd_mode():
    subject = _subject()
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, True)
    real_loop = asyncio.get_running_loop()

    class TrackingLoop:
        def __init__(self):
            self.added: list[int] = []
            self.removed: list[int] = []

        def create_future(self):
            return real_loop.create_future()

        def add_reader(self, fd, callback):
            self.added.append(fd)
            return real_loop.add_reader(fd, callback)

        def remove_reader(self, fd):
            self.removed.append(fd)
            return real_loop.remove_reader(fd)

    tracking_loop = TrackingLoop()
    try:
        task = asyncio.create_task(
            subject._read_human_session_id(
                18765,
                fd=read_fd,
                event_loop=tracking_loop,
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert tracking_loop.added == [read_fd]
        assert tracking_loop.removed == [read_fd]
        assert os.get_blocking(read_fd) is True
        assert "to_thread" not in inspect.getsource(subject._read_human_session_id)
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.asyncio
async def test_ack_prompt_sets_the_reserved_attempt_id_for_the_phase0_page(
    capsys: pytest.CaptureFixture,
):
    subject = _subject()
    read_fd, write_fd = os.pipe()
    attempt_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    try:
        os.write(write_fd, (attempt_id + "\n").encode("utf-8"))
        assert (
            await subject._read_human_session_id(
                18765,
                fd=read_fd,
                attempt_id=attempt_id,
            )
            == attempt_id
        )
        prompt = capsys.readouterr().out
        assert attempt_id in prompt
        assert "setM1CampaignAttemptId" in prompt
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_campaign_environment_pins_exact_db_and_redis_15():
    subject = _subject()
    subject.validate_campaign_environment(
        {
            "MYSQL_DATABASE": "lxm_step006_m1_campaign_20260902",
            "REDIS_DB": "15",
            "REALTIME_VOICE_M1_ADMIN_JWT": "real-jwt",
        }
    )

    with pytest.raises(ValueError, match="REDIS_DB"):
        subject.validate_campaign_environment(
            {
                "MYSQL_DATABASE": "lxm_step006_m1_campaign_20260902",
                "REDIS_DB": "0",
                "REALTIME_VOICE_M1_ADMIN_JWT": "real-jwt",
            }
        )


class _FakeAdminClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []

    async def post(self, path: str, *, json: dict, headers: dict):
        self.calls.append((path, deepcopy(json), deepcopy(headers)))
        return _FakeResponse(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "status": "error",
                    "failure_category": "internal_error",
                    "latency_ms": None,
                    "tested_at": "2026-09-02T00:00:00Z",
                },
            }
        )


class _FakeLoginAndProbeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    async def post(self, path: str, *, json: dict):
        self.calls.append(("POST", path, deepcopy(json)))
        return _FakeResponse(
            {
                "code": 0,
                "message": "success",
                "data": {"token": "fresh-real-admin-jwt"},
            }
        )

    async def get(self, path: str, *, headers: dict):
        self.calls.append(("GET", path, deepcopy(headers)))
        return _FakeResponse(
            {
                "code": 0,
                "message": "success",
                "data": {"draft": {"draft_revision": 1}},
            }
        )


@pytest.mark.asyncio
async def test_admin_route_call_uses_bearer_jwt_and_only_temporary_runner_override():
    subject = _subject()
    runner_dependency = object()
    auth_dependency = object()
    db_dependency = object()
    app = SimpleNamespace(
        dependency_overrides={
            auth_dependency: "real-auth",
            db_dependency: "real-db",
        }
    )
    client = _FakeAdminClient()

    payload = await subject.call_admin_test_route(
        app=app,
        runner_dependency=runner_dependency,
        runner_factory=lambda: object(),
        jwt="real-admin-jwt",
        mode="ack",
        http_client=client,
    )

    assert payload["data"]["failure_category"] == "internal_error"
    assert client.calls == [
        (
            "/api/admin/voice/config/test-capability",
            {"capability_key": ACK_KEY},
            {"Authorization": "Bearer real-admin-jwt"},
        )
    ]
    assert runner_dependency not in app.dependency_overrides
    assert app.dependency_overrides[auth_dependency] == "real-auth"
    assert app.dependency_overrides[db_dependency] == "real-db"


@pytest.mark.asyncio
async def test_login_and_read_only_auth_probe_use_real_routes_directly():
    subject = _subject()
    client = _FakeLoginAndProbeClient()

    token = await subject.login_campaign_admin(
        client,
        "m1_campaign_admin",
        "Generated1!CampaignPassword",
    )
    await subject.probe_campaign_admin_auth(client, token)

    assert token == "fresh-real-admin-jwt"
    assert client.calls == [
        (
            "POST",
            "/api/admin/auth/login",
            {
                "username": "m1_campaign_admin",
                "password": "Generated1!CampaignPassword",
            },
        ),
        (
            "GET",
            "/api/admin/voice/config/config",
            {"Authorization": "Bearer fresh-real-admin-jwt"},
        ),
    ]


@pytest.mark.asyncio
async def test_admin_route_timeout_exceeds_production_deadline_plus_cleanup_budget():
    subject = _subject()

    class SlowClient:
        calls = 0

        async def post(self, *_args, **_kwargs):
            self.calls += 1
            await asyncio.Event().wait()

    client = SlowClient()
    assert subject.CAMPAIGN_ROUTE_DEADLINE_SECONDS > 65.0
    with pytest.raises(RuntimeError, match="admin route"):
        await subject.call_admin_test_route(
            app=SimpleNamespace(dependency_overrides={}),
            runner_dependency=object(),
            runner_factory=lambda: object(),
            jwt="real-admin-jwt",
            mode="connection",
            http_client=client,
            request_timeout_seconds=0.01,
        )
    assert client.calls == 1


@pytest.mark.asyncio
async def test_read_only_preflight_checks_real_database_schema_and_redis_selection():
    subject = _subject()

    class ScalarResult:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return self

        def all(self):
            return list(self._values)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def scalar(self, statement):
            sql = str(statement)
            if "DATABASE()" in sql:
                return subject.CAMPAIGN_DATABASE_NAME
            if "alembic_version" in sql:
                return "v8c_voice_schema_001"
            raise AssertionError(sql)

        async def execute(self, statement):
            assert "information_schema.tables" in str(statement)
            return ScalarResult(subject.CAMPAIGN_REQUIRED_TABLES)

    class FakeRedis:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def ping(self):
            self.calls.append("ping")
            return True

        async def client_info(self):
            self.calls.append("client_info")
            return {"db": 15}

    redis = FakeRedis()
    result = await subject.preflight_campaign_dependencies(
        session_maker=lambda: FakeSession(),
        redis_getter=lambda: redis,
    )

    assert result == {
        "database": subject.CAMPAIGN_DATABASE_NAME,
        "alembic_revision": "v8c_voice_schema_001",
        "required_table_count": len(subject.CAMPAIGN_REQUIRED_TABLES),
        "redis_db": 15,
    }
    assert redis.calls == ["ping", "client_info"]


@pytest.mark.asyncio
async def test_verify_no_provider_uses_production_default_without_any_override():
    subject = _subject()
    from backend.services.realtime_voice_admin_test_service import (
        UnavailableVoiceTestRunner,
        get_voice_test_runner,
    )

    default_runner = get_voice_test_runner()
    assert type(default_runner) is UnavailableVoiceTestRunner
    default_result = await default_runner.run_capability(
        capability_key=ACK_KEY,
        draft_snapshot=_draft(),
        secret=SECRET,
    )
    await default_runner.aclose()
    assert default_result["failure_category"] == "internal_error"
    assert "evidence_record" not in default_result

    auth_dependency = object()
    db_dependency = object()
    app = SimpleNamespace(
        dependency_overrides={
            auth_dependency: "real-auth",
            db_dependency: "real-db",
        }
    )
    before_overrides = dict(app.dependency_overrides)
    client = _FakeAdminClient()
    payload = await subject.call_admin_test_route(
        app=app,
        runner_dependency=get_voice_test_runner,
        runner_factory=None,
        jwt="real-admin-jwt",
        mode="connection",
        http_client=client,
    )

    assert payload["data"]["failure_category"] == "internal_error"
    assert app.dependency_overrides == before_overrides
    assert "evidence_run_id" not in payload["data"]
    assert "evidence_report_id" not in payload["data"]


@pytest.mark.asyncio
async def test_run_cli_bootstrap_path_is_directly_exercised_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    subject = _subject()
    from backend.services.realtime_voice_admin_test_service import (
        UnavailableVoiceTestRunner,
    )
    phase0_root = tmp_path / "phase0"
    _write_phase0_public_defaults(phase0_root)
    project_env = tmp_path / ".env"
    project_env.write_text(
        "MYSQL_DATABASE=phase0-business\nREDIS_DB=0\n"
        "PHASE0_DOUBAO_S2S_ACCESS_KEY=offline-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MYSQL_DATABASE", subject.CAMPAIGN_DATABASE_NAME)
    monkeypatch.setenv("REDIS_DB", subject.CAMPAIGN_REDIS_DB)
    monkeypatch.delenv("REALTIME_VOICE_M1_ADMIN_JWT", raising=False)
    calls: list[str] = []

    async def preflight(**_kwargs):
        calls.append("preflight")
        return {
            "database": subject.CAMPAIGN_DATABASE_NAME,
            "alembic_revision": "v8c_voice_schema_001",
            "required_table_count": len(subject.CAMPAIGN_REQUIRED_TABLES),
            "redis_db": 15,
        }

    async def bootstrap(**kwargs):
        calls.append("bootstrap")
        assert kwargs["project_env_path"] == project_env.resolve()
        assert kwargs["phase0_root"] == phase0_root.resolve()
        return "m1_campaign_admin", "Generated1!CampaignPassword"

    async def state():
        calls.append("state")
        return {"database": subject.CAMPAIGN_DATABASE_NAME, "active_rows": [], "redis": {}}

    async def login(_client, username, password):
        calls.append("login")
        assert username == "m1_campaign_admin"
        assert password == "Generated1!CampaignPassword"
        return "fresh-real-admin-jwt"

    async def auth_probe(_client, jwt):
        calls.append("auth_probe")
        assert jwt == "fresh-real-admin-jwt"

    async def route_call(**kwargs):
        calls.append("route")
        assert kwargs["jwt"] == "fresh-real-admin-jwt"
        assert kwargs["runner_factory"] is None
        return {
            "code": 0,
            "data": {
                "status": "error",
                "latency_ms": None,
                "failure_category": "internal_error",
                "tested_at": "2026-09-02T00:00:00Z",
            },
        }

    class FakeEngine:
        async def dispose(self):
            calls.append("dispose")

    async def close_redis():
        calls.append("close_redis")

    runtime = SimpleNamespace(
        app=SimpleNamespace(dependency_overrides={}),
        runner_dependency=lambda: UnavailableVoiceTestRunner(),
        unavailable_runner_type=UnavailableVoiceTestRunner,
        validator=lambda value: value,
        close_redis=close_redis,
        engine=FakeEngine(),
    )

    class ClientContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(subject, "preflight_campaign_dependencies", preflight)
    monkeypatch.setattr(subject, "bootstrap_campaign_prerequisites", bootstrap)
    monkeypatch.setattr(subject, "capture_campaign_state", state)
    monkeypatch.setattr(subject, "login_campaign_admin", login)
    monkeypatch.setattr(subject, "probe_campaign_admin_auth", auth_probe)
    monkeypatch.setattr(subject, "call_admin_test_route", route_call)
    monkeypatch.setattr(subject, "load_campaign_runtime", lambda: runtime)
    monkeypatch.setattr(subject, "campaign_http_client", lambda _app: ClientContext())

    @contextmanager
    def canary_scope():
        calls.append("canary_scope")
        yield

    monkeypatch.setattr(subject, "no_provider_canary_secret_scope", canary_scope)

    @contextmanager
    def forbidden_real_secret(_path):
        raise AssertionError("verify-no-provider 禁止读取真实 Provider secret")
        yield

    monkeypatch.setattr(subject, "project_provider_secret_scope", forbidden_real_secret)
    monkeypatch.setattr(
        subject,
        "reserve_provider_attempt",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("verify-no-provider 禁止占 Provider 号")
        ),
    )

    args = SimpleNamespace(
        mode="verify-no-provider",
        phase0_root=phase0_root,
        project_env=project_env,
        port=18765,
        phase0_user_id=101,
        bootstrap=True,
        campaign_id=None,
        matrix_path=None,
        runtime_manifest=None,
        ledger_path=None,
        attempt_kind=None,
    )
    exit_code = await subject._run_cli(args)

    assert exit_code == 0
    assert calls == [
        "preflight",
        "bootstrap",
        "state",
        "login",
        "auth_probe",
        "canary_scope",
        "route",
        "state",
        "close_redis",
        "dispose",
    ]


@pytest.mark.asyncio
async def test_connection_reserves_frozen_attempt_immediately_before_route_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    subject = _subject()
    from backend.services.realtime_voice_admin_test_service import (
        UnavailableVoiceTestRunner,
    )
    monkeypatch.setattr(subject, "_PROJECT_ROOT", tmp_path)
    phase0_root = tmp_path / "tmp/phase0-step004-s01-fix-20260906"
    _write_phase0_public_defaults(phase0_root)
    project_env = tmp_path / ".env"
    project_env.write_text(
        "MYSQL_DATABASE=phase0-business\nREDIS_DB=0\n"
        "PHASE0_DOUBAO_S2S_ACCESS_KEY=offline-real-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MYSQL_DATABASE", subject.CAMPAIGN_DATABASE_NAME)
    monkeypatch.setenv("REDIS_DB", subject.CAMPAIGN_REDIS_DB)
    monkeypatch.setenv("REALTIME_VOICE_M1_ADMIN_JWT", "external-real-jwt")
    calls: list[str] = []
    frozen = subject.FrozenCampaign(
        campaign_id="m1-frozen",
        matrix_sha256="a" * 64,
        runtime_manifest_sha256="b" * 64,
        ledger_path=tmp_path / "ledger.json",
    )

    monkeypatch.setattr(
        subject,
        "resolve_frozen_campaign_from_args",
        lambda _args: calls.append("freeze") or frozen,
    )

    async def preflight(**_kwargs):
        calls.append("preflight")

    async def state():
        calls.append("state")
        return {"database": subject.CAMPAIGN_DATABASE_NAME, "active_rows": [], "redis": {}}

    async def auth_probe(_client, _jwt):
        calls.append("auth_probe")

    async def baseline(**_kwargs):
        calls.append("baseline")
        return _campaign_baseline()

    def reserve(**kwargs):
        calls.append("reserve")
        assert kwargs["attempt_kind"] == "admin_connection"
        assert kwargs["campaign_id"] == frozen.campaign_id
        return {
            "schema_version": "m1-campaign-provider-attempt-receipt/v1",
            "campaign_id": frozen.campaign_id,
            "attempt_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "attempt_ordinal": 1,
            "baseline_epoch": 1,
            "attempt_kind": "admin_connection",
            "remaining_attempts": 14,
        }

    async def route_call(**kwargs):
        calls.append("route")
        assert kwargs["runner_factory"] is not None
        return {
            "code": 0,
            "data": {
                "status": "passed",
                "latency_ms": 1,
                "failure_category": "none",
                "tested_at": "2026-09-02T00:00:00Z",
            },
        }

    class FakeEngine:
        async def dispose(self):
            calls.append("dispose")

    async def close_redis():
        calls.append("close_redis")

    runtime = SimpleNamespace(
        app=SimpleNamespace(dependency_overrides={}),
        runner_dependency=object(),
        unavailable_runner_type=UnavailableVoiceTestRunner,
        validator=lambda value: value,
        close_redis=close_redis,
        engine=FakeEngine(),
    )

    class ClientContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(subject, "preflight_campaign_dependencies", preflight)
    monkeypatch.setattr(subject, "capture_campaign_state", state)
    monkeypatch.setattr(subject, "probe_campaign_admin_auth", auth_probe)
    monkeypatch.setattr(subject, "capture_current_campaign_baseline", baseline)
    monkeypatch.setattr(subject, "reserve_provider_attempt", reserve)
    monkeypatch.setattr(subject, "call_admin_test_route", route_call)
    monkeypatch.setattr(subject, "load_campaign_runtime", lambda: runtime)
    monkeypatch.setattr(subject, "campaign_http_client", lambda _app: ClientContext())

    args = SimpleNamespace(
        mode="connection",
        phase0_root=phase0_root,
        project_env=project_env,
        port=18765,
        phase0_user_id=101,
        bootstrap=False,
        campaign_id="m1-frozen",
        matrix_path=tmp_path / "matrix.json",
        runtime_manifest=tmp_path / "runtime.json",
        ledger_path=tmp_path / "ledger.json",
        attempt_kind=None,
    )
    assert await subject._run_cli(args) == 0
    assert calls.index("reserve") + 1 == calls.index("route")
    assert calls.count("reserve") == 1


@pytest.mark.asyncio
async def test_direct_phase0_reserve_cli_only_emits_safe_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    subject = _subject()
    monkeypatch.setattr(subject, "_PROJECT_ROOT", tmp_path)
    phase0_root = tmp_path / "tmp/phase0-step004-s01-fix-20260906"
    _write_phase0_public_defaults(phase0_root)
    project_env = tmp_path / ".env"
    project_env.write_text(
        "MYSQL_DATABASE=phase0-business\nREDIS_DB=0\n",
        encoding="utf-8",
    )
    frozen = subject.FrozenCampaign(
        campaign_id="m1-direct",
        matrix_sha256="c" * 64,
        runtime_manifest_sha256="d" * 64,
        ledger_path=tmp_path / "ledger.json",
    )
    monkeypatch.setattr(
        subject, "resolve_frozen_campaign_from_args", lambda _args: frozen
    )
    receipt = {
        "schema_version": "m1-campaign-provider-attempt-receipt/v1",
        "campaign_id": "m1-direct",
        "attempt_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "attempt_ordinal": 1,
        "attempt_kind": "s01_start_session",
        "remaining_attempts": 14,
    }
    monkeypatch.setattr(subject, "reserve_provider_attempt", lambda **_kwargs: receipt)
    monkeypatch.setenv("MYSQL_DATABASE", subject.CAMPAIGN_DATABASE_NAME)
    monkeypatch.setenv("REDIS_DB", subject.CAMPAIGN_REDIS_DB)
    calls: list[str] = []

    async def preflight():
        calls.append("preflight")

    async def baseline(**_kwargs):
        calls.append("baseline")
        return _campaign_baseline()

    async def close_redis():
        calls.append("close_redis")

    class FakeEngine:
        async def dispose(self):
            calls.append("dispose")

    monkeypatch.setattr(subject, "preflight_campaign_dependencies", preflight)
    monkeypatch.setattr(subject, "capture_current_campaign_baseline", baseline)
    monkeypatch.setattr(
        subject,
        "load_campaign_runtime",
        lambda: SimpleNamespace(close_redis=close_redis, engine=FakeEngine()),
    )
    args = SimpleNamespace(
        mode="reserve-attempt",
        attempt_kind="s01_start_session",
        campaign_id="m1-direct",
        matrix_path=tmp_path / "matrix.json",
        runtime_manifest=tmp_path / "runtime.json",
        ledger_path=tmp_path / "ledger.json",
        phase0_root=phase0_root,
        project_env=project_env,
        port=18765,
        phase0_user_id=101,
        bootstrap=False,
    )

    assert await subject._run_cli(args) == 0
    output_lines = capsys.readouterr().out.splitlines()
    assert json.loads(output_lines[-1]) == receipt
    assert calls == ["preflight", "baseline", "close_redis", "dispose"]


@pytest.mark.asyncio
async def test_no_provider_runner_cannot_emit_or_append_capability_evidence():
    from backend.services.realtime_voice_admin_test_service import get_voice_test_runner

    runner = get_voice_test_runner()

    result = await runner.run_capability(
        capability_key=ACK_KEY,
        draft_snapshot=_draft(),
        secret=SECRET,
    )
    await runner.aclose()

    assert result["failure_category"] == "internal_error"
    assert "evidence_record" not in result
    assert SECRET not in json.dumps(result)


def test_campaign_state_guard_detects_active_or_redis_mutation():
    subject = _subject()
    stable = {
        "database": "lxm_step006_m1_campaign_20260902",
        "active_rows": [(1, "voice_call_config", 1, "sha")],
        "redis": {"active_config:voice_call_config": ("payload", 10)},
    }
    subject.assert_campaign_state_unchanged(stable, deepcopy(stable))

    changed = deepcopy(stable)
    changed["redis"]["active_config:voice_call_config"] = ("other", 10)
    with pytest.raises(RuntimeError, match="active/Redis"):
        subject.assert_campaign_state_unchanged(stable, changed)


def _state_config_row(content: dict, *, revision: int) -> dict:
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "id": 1,
        "config_key": VOICE_CALL_CONFIG_KEY,
        "version": 0,
        "draft_revision": revision,
        "is_draft": True,
        "is_active": False,
        "content_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "content": deepcopy(content),
    }


def _campaign_state(content: dict, *, revision: int, evidence_rows=None) -> dict:
    return {
        "database": "lxm_step006_m1_campaign_20260902",
        "active_rows": [],
        "config_rows": [_state_config_row(content, revision=revision)],
        "evidence_rows": list(evidence_rows or []),
        "redis": {"key-hash": ("hash", "dump-hash", "persistent")},
    }


def test_ack_state_guard_allows_exact_target_projection_and_one_matching_evidence():
    subject = _subject()
    from backend.services.realtime_voice_capability_service import (
        _project_record_to_capability,
    )

    before_config = _draft()
    converted = subject.convert_phase0_ack_record(
        _phase0_ack_record(), draft_snapshot=before_config
    )
    after_config = deepcopy(before_config)
    after_config["capabilities"][ACK_KEY] = _project_record_to_capability(
        after_config["capabilities"][ACK_KEY], converted
    )
    evidence_row = {"id": 9, **deepcopy(converted)}
    before = _campaign_state(before_config, revision=1)
    after = _campaign_state(after_config, revision=2, evidence_rows=[evidence_row])
    route_result = {
        "status": converted["verification_result"],
        "evidence_report_id": converted["evidence_report_id"],
        "evidence_run_id": converted["evidence_run_id"],
        "capability_key": ACK_KEY,
    }

    subject.assert_campaign_state_transition(
        before,
        after,
        mode="ack",
        route_result=route_result,
    )

    changed_other = deepcopy(after)
    changed_other["config_rows"][0]["content"]["capabilities"][
        "supports_reply_cancel"
    ]["last_test_result"] = "failed"
    with pytest.raises(RuntimeError, match="ACK"):
        subject.assert_campaign_state_transition(
            before,
            changed_other,
            mode="ack",
            route_result=route_result,
        )


def test_ack_error_state_guard_requires_zero_config_evidence_and_redis_change():
    subject = _subject()
    before = _campaign_state(_draft(), revision=1)
    route_result = {
        "status": "error",
        "evidence_report_id": None,
        "evidence_run_id": None,
        "capability_key": ACK_KEY,
    }
    subject.assert_campaign_state_transition(
        before,
        deepcopy(before),
        mode="ack",
        route_result=route_result,
    )

    changed = deepcopy(before)
    changed["evidence_rows"].append({"unexpected": True})
    with pytest.raises(RuntimeError, match="非预期"):
        subject.assert_campaign_state_transition(
            before,
            changed,
            mode="ack",
            route_result=route_result,
        )


@pytest.mark.asyncio
async def test_redis_snapshot_hashes_dump_for_arbitrary_value_types():
    subject = _subject()

    class FakeRedis:
        def __init__(self, dumps):
            self.dumps = dumps

        async def scan_iter(self, match="*"):
            assert match == "*"
            for key in (b"string-key", b"hash-key"):
                yield key

        async def type(self, key):
            return b"string" if key == b"string-key" else b"hash"

        async def dump(self, key):
            return self.dumps[key]

        async def ttl(self, _key):
            return -1

    first = await subject.capture_redis_dump_state(
        FakeRedis({b"string-key": b"serialized-a", b"hash-key": b"serialized-b"})
    )
    second = await subject.capture_redis_dump_state(
        FakeRedis({b"string-key": b"serialized-a", b"hash-key": b"serialized-c"})
    )

    assert first != second
    assert all(len(key_hash) == 64 for key_hash in first)
    assert {value[0] for value in first.values()} == {"string", "hash"}


def test_campaign_ledger_path_is_fixed_and_alternate_path_cannot_reset_budget(
    tmp_path: Path,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-fixed-ledger"
    expected = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / campaign_id
        / "attempt-ledger.json"
    )

    assert subject.campaign_ledger_path(
        campaign_id, project_root=project_root
    ) == expected
    with pytest.raises(ValueError, match="固定|ledger"):
        subject.reserve_provider_attempt(
            ledger_path=project_root / "alternate-ledger.json",
            project_root=project_root,
            campaign_id=campaign_id,
            matrix_sha256="a" * 64,
            runtime_manifest_sha256="b" * 64,
            baseline=_campaign_baseline(),
            attempt_kind="s01_start_session",
        )


def test_campaign_ledger_has_two_append_only_epochs_and_one_shared_15_attempt_cap(
    tmp_path: Path,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-two-epochs"
    ledger_path = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / campaign_id
        / "attempt-ledger.json"
    )
    baseline_one = _campaign_baseline(marker="a")
    baseline_two = _campaign_baseline(marker="b")
    epoch_one = {
        "project_root": project_root,
        "ledger_path": ledger_path,
        "campaign_id": campaign_id,
        "matrix_sha256": "1" * 64,
        "runtime_manifest_sha256": "2" * 64,
        "baseline": baseline_one,
    }
    for _index in range(8):
        subject.reserve_provider_attempt(
            **epoch_one,
            attempt_kind="s01_start_session",
        )

    regression = project_root / "evidence" / "automatic-regression.json"
    regression.parent.mkdir()
    regression.write_text('{"passed":true}\n', encoding="utf-8")
    advance_receipt = subject.advance_campaign_to_final_batch(
        project_root=project_root,
        ledger_path=ledger_path,
        campaign_id=campaign_id,
        matrix_sha256="3" * 64,
        runtime_manifest_sha256="4" * 64,
        baseline=baseline_two,
        regression_evidence_path=regression,
    )
    assert advance_receipt == {
        "schema_version": "m1-campaign-final-batch-receipt/v1",
        "campaign_id": campaign_id,
        "active_baseline_epoch": 2,
        "remaining_attempts": 7,
    }

    epoch_two = {
        "project_root": project_root,
        "ledger_path": ledger_path,
        "campaign_id": campaign_id,
        "matrix_sha256": "3" * 64,
        "runtime_manifest_sha256": "4" * 64,
        "baseline": baseline_two,
    }
    for _index in range(7):
        subject.reserve_provider_attempt(
            **epoch_two,
            attempt_kind="s02_start_session",
        )
    with pytest.raises(RuntimeError, match="15"):
        subject.reserve_provider_attempt(
            **epoch_two,
            attempt_kind="s03_start_session",
        )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["active_baseline_epoch"] == 2
    assert [epoch["baseline_epoch"] for epoch in ledger["baseline_epochs"]] == [1, 2]
    assert [attempt["attempt_ordinal"] for attempt in ledger["attempts"]] == list(
        range(1, 16)
    )
    assert [attempt["baseline_epoch"] for attempt in ledger["attempts"]] == [
        *([1] * 8),
        *([2] * 7),
    ]
    assert ledger["baseline_epochs"][1]["regression_evidence"] == {
        "path": "evidence/automatic-regression.json",
        "sha256": _sha256_file(regression),
    }

    with pytest.raises(RuntimeError, match="final|两"):
        subject.advance_campaign_to_final_batch(
            project_root=project_root,
            ledger_path=ledger_path,
            campaign_id=campaign_id,
            matrix_sha256="5" * 64,
            runtime_manifest_sha256="6" * 64,
            baseline=_campaign_baseline(marker="c"),
            regression_evidence_path=regression,
        )
    with pytest.raises(ValueError, match="绑定|回退|baseline"):
        subject.reserve_provider_attempt(
            **epoch_one,
            attempt_kind="s04_start_session",
        )


def test_reserve_binds_exact_public_draft_dimensions_fingerprint_sdk_and_suite(
    tmp_path: Path,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-baseline-drift"
    ledger_path = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / campaign_id
        / "attempt-ledger.json"
    )
    baseline = _campaign_baseline()
    kwargs = {
        "project_root": project_root,
        "ledger_path": ledger_path,
        "campaign_id": campaign_id,
        "matrix_sha256": "1" * 64,
        "runtime_manifest_sha256": "2" * 64,
        "attempt_kind": "s01_start_session",
    }
    subject.reserve_provider_attempt(**kwargs, baseline=baseline)

    mutations = []
    for path, changed in (
        (("public_provider_settings_sha256",), "f" * 64),
        (("voice_draft_sha256",), "e" * 64),
        (("evidence_dimensions", "sdk_version"), "websockets-99.0"),
        (("evidence_dimensions", "evidence_suite_version"), "unexpected-suite"),
    ):
        mutated = deepcopy(baseline)
        if len(path) == 1:
            mutated[path[0]] = changed
        else:
            mutated[path[0]][path[1]] = changed
            mutated["evidence_fingerprint"] = hashlib.sha256(
                json.dumps(
                    mutated["evidence_dimensions"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        mutations.append(mutated)
    for mutated in mutations:
        with pytest.raises(ValueError, match="baseline|冻结"):
            subject.reserve_provider_attempt(**kwargs, baseline=mutated)

    malformed = deepcopy(baseline)
    malformed["evidence_dimensions"]["sdk_version"] = "websockets-99.0"
    with pytest.raises(ValueError, match="fingerprint"):
        subject.reserve_provider_attempt(**kwargs, baseline=malformed)


def test_runtime_manifest_covers_complete_closure_and_rejects_file_set_drift(
    tmp_path: Path,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    closure_paths = _write_complete_runtime_fixture(project_root)
    manifest = {
        "schema_version": "m1-campaign-runtime-manifest/v2",
        "files": [
            {
                "path": relative.as_posix(),
                "sha256": _sha256_file(project_root / relative),
            }
            for relative in sorted(closure_paths)
        ],
        **_runtime_identity_fixture(),
    }
    manifest_path = project_root / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    matrix_path = project_root / "matrix.json"
    matrix_path.write_text('{"scenario_ids":["S01"]}\n', encoding="utf-8")
    ledger_path = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / "m1-runtime-closure"
        / "attempt-ledger.json"
    )

    frozen = subject.resolve_frozen_campaign(
        campaign_id="m1-runtime-closure",
        matrix_path=matrix_path,
        runtime_manifest_path=manifest_path,
        ledger_path=ledger_path,
        project_root=project_root,
    )
    assert len(frozen.runtime_manifest_sha256) == 64

    added = project_root / "backend" / "new_runtime_dependency.py"
    added.write_text("ADDED = True\n", encoding="utf-8")
    with pytest.raises(ValueError, match="集合|closure|allowlist"):
        subject.resolve_frozen_campaign(
            campaign_id="m1-runtime-closure",
            matrix_path=matrix_path,
            runtime_manifest_path=manifest_path,
            ledger_path=ledger_path,
            project_root=project_root,
        )
    added.unlink()

    target = project_root / "backend" / "a.py"
    target.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        subject.resolve_frozen_campaign(
            campaign_id="m1-runtime-closure",
            matrix_path=matrix_path,
            runtime_manifest_path=manifest_path,
            ledger_path=ledger_path,
            project_root=project_root,
        )


def test_runtime_manifest_rejects_python_or_key_package_version_drift(tmp_path: Path):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    closure_paths = _write_complete_runtime_fixture(project_root)
    manifest = {
        "schema_version": "m1-campaign-runtime-manifest/v2",
        "files": [
            {
                "path": relative.as_posix(),
                "sha256": _sha256_file(project_root / relative),
            }
            for relative in sorted(closure_paths)
        ],
        **_runtime_identity_fixture(),
    }
    manifest_path = project_root / "runtime-manifest.json"
    matrix_path = project_root / "matrix.json"
    matrix_path.write_text("{}\n", encoding="utf-8")
    ledger_path = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / "m1-runtime-versions"
        / "attempt-ledger.json"
    )

    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    subject.resolve_frozen_campaign(
        campaign_id="m1-runtime-versions",
        matrix_path=matrix_path,
        runtime_manifest_path=manifest_path,
        ledger_path=ledger_path,
        project_root=project_root,
    )

    for mutate in ("python", "package"):
        changed = deepcopy(manifest)
        if mutate == "python":
            changed["python"]["version"] = "0.0.0"
        else:
            changed["packages"][0]["version"] = "0.0.0"
        manifest_path.write_text(
            json.dumps(changed, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Python|package|版本|runtime"):
            subject.resolve_frozen_campaign(
                campaign_id="m1-runtime-versions",
                matrix_path=matrix_path,
                runtime_manifest_path=manifest_path,
                ledger_path=ledger_path,
                project_root=project_root,
            )


@pytest.mark.parametrize(
    ("field", "changed"),
    (
        ("enabled", True),
        ("sdk_version", "websockets-forged"),
        ("evidence_ttl_days", 7),
        ("verified_at", "2099-01-01T00:00:00Z"),
        ("fallback_mode", "forged"),
    ),
)
def test_ack_guard_requires_full_production_projection_equality(field, changed):
    subject = _subject()
    from backend.services.realtime_voice_capability_service import (
        _project_record_to_capability,
    )

    before_config = _draft()
    converted = subject.convert_phase0_ack_record(
        _phase0_ack_record(), draft_snapshot=before_config
    )
    after_config = deepcopy(before_config)
    after_config["capabilities"][ACK_KEY] = _project_record_to_capability(
        after_config["capabilities"][ACK_KEY], converted
    )
    after_config["capabilities"][ACK_KEY][field] = changed
    evidence_row = {"id": 9, **deepcopy(converted)}
    before = _campaign_state(before_config, revision=1)
    after = _campaign_state(after_config, revision=2, evidence_rows=[evidence_row])
    route_result = {
        "status": converted["verification_result"],
        "evidence_report_id": converted["evidence_report_id"],
        "evidence_run_id": converted["evidence_run_id"],
        "capability_key": ACK_KEY,
    }

    with pytest.raises(RuntimeError, match="projection|投影|ACK"):
        subject.assert_campaign_state_transition(
            before,
            after,
            mode="ack",
            route_result=route_result,
        )


def test_admin_config_snapshot_covers_every_key_without_non_voice_plaintext():
    subject = _subject()
    rows = [
        SimpleNamespace(
            id=1,
            config_key=VOICE_CALL_CONFIG_KEY,
            version=0,
            draft_revision=1,
            is_draft=True,
            is_active=False,
            config_value=json.dumps(_draft()),
            updated_by="m1",
            updated_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            id=2,
            config_key="provider_secret_config",
            version=1,
            draft_revision=None,
            is_draft=False,
            is_active=True,
            config_value='{"secret":"must-not-appear"}',
            updated_by="m1",
            updated_at=None,
        ),
        SimpleNamespace(
            id=3,
            config_key="nullable_config",
            version=1,
            draft_revision=None,
            is_draft=False,
            is_active=False,
            config_value=None,
            updated_by=None,
            updated_at=None,
        ),
    ]

    snapshots = subject.snapshot_admin_config_rows(rows)
    assert [row["config_key"] for row in snapshots] == [
        VOICE_CALL_CONFIG_KEY,
        "provider_secret_config",
        "nullable_config",
    ]
    assert snapshots[0]["content"] == _draft()
    assert snapshots[1]["content"] is None
    assert snapshots[1]["value_kind"] == "text"
    assert snapshots[2]["value_kind"] == "null"
    assert "must-not-appear" not in repr(snapshots)


def test_every_reserve_writes_exact_phase0_gate_receipt_next_to_fixed_ledger(
    tmp_path: Path,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-gate-receipt"
    ledger_path = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / campaign_id
        / "attempt-ledger.json"
    )
    receipt = subject.reserve_provider_attempt(
        project_root=project_root,
        ledger_path=ledger_path,
        campaign_id=campaign_id,
        matrix_sha256="a" * 64,
        runtime_manifest_sha256="b" * 64,
        baseline=_campaign_baseline(),
        attempt_kind="admin_connection",
        now=lambda: datetime(2026, 9, 2, tzinfo=timezone.utc),
        attempt_id_factory=lambda: uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    )

    reserved_path = (
        ledger_path.parent
        / "attempt-reservations"
        / "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.reserved.json"
    )
    reserved = json.loads(reserved_path.read_text(encoding="utf-8"))
    assert reserved == {
        "schema_version": "m1-campaign-provider-attempt-receipt/v1",
        "campaign_id": campaign_id,
        "matrix_sha256": "a" * 64,
        "runtime_manifest_sha256": "b" * 64,
        "baseline_epoch": 1,
        "attempt_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "attempt_ordinal": 1,
        "attempt_kind": "admin_connection",
        "reserved_at": "2026-09-02T00:00:00Z",
    }
    assert set(reserved) == {
        "schema_version",
        "campaign_id",
        "matrix_sha256",
        "runtime_manifest_sha256",
        "baseline_epoch",
        "attempt_id",
        "attempt_ordinal",
        "attempt_kind",
        "reserved_at",
    }
    assert receipt["attempt_id"] == reserved["attempt_id"]
    assert receipt["baseline_epoch"] == 1
    assert reserved_path.stat().st_mode & 0o777 == 0o600


def test_gate_receipt_write_failure_still_conservatively_consumes_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    subject = _subject()
    project_root = tmp_path / "project"
    project_root.mkdir()
    campaign_id = "m1-gate-write-failure"
    ledger_path = (
        project_root
        / "docs/design/realtime_voice/P1/execution/evidence/step004/campaigns"
        / campaign_id
        / "attempt-ledger.json"
    )

    def fail_write(*_args, **_kwargs):
        raise OSError("simulated reservation write failure")

    monkeypatch.setattr(subject, "_write_attempt_reservation", fail_write)
    with pytest.raises(OSError, match="simulated"):
        subject.reserve_provider_attempt(
            project_root=project_root,
            ledger_path=ledger_path,
            campaign_id=campaign_id,
            matrix_sha256="a" * 64,
            runtime_manifest_sha256="b" * 64,
            baseline=_campaign_baseline(),
            attempt_kind="admin_ack",
        )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert len(ledger["attempts"]) == 1
    assert ledger["attempts"][0]["attempt_kind"] == "admin_ack"


@pytest.mark.asyncio
async def test_serve_direct_only_hosts_one_gate_worker_and_never_creates_a_session(
    capsys: pytest.CaptureFixture,
):
    subject = _subject()

    class Worker:
        def __init__(self):
            self.calls = []

        async def start(self):
            self.calls.append("start")

        async def stop(self):
            self.calls.append("stop")

        async def create_connection_session(self, **_kwargs):
            raise AssertionError("serve-direct 禁止自行创建 session")

    worker = Worker()
    waited = False

    async def wait_for_shutdown():
        nonlocal waited
        waited = True

    await subject.serve_direct_worker(
        worker,
        port=18765,
        attempt_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        reconnect_attempt_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        wait_for_shutdown=wait_for_shutdown,
    )

    assert waited is True
    assert worker.calls == ["start", "stop"]
    output = capsys.readouterr().out
    assert "setM1CampaignAttemptId" in output
    assert "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" in output
    assert "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" in output
    parsed = subject._build_argument_parser().parse_args(
        [
            "serve-direct",
            "--campaign-id",
            "m1-direct",
            "--matrix-path",
            "matrix.json",
            "--runtime-manifest",
            "runtime.json",
            "--expected-start-kind",
            "s01_start_session",
            "--expected-start-ordinal",
            "1",
            "--expected-reconnect-ordinal",
            "2",
        ]
    )
    assert parsed.mode == "serve-direct"

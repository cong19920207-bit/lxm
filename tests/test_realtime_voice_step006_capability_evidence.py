# -*- coding: utf-8 -*-
"""STEP-006A capability state and read-only evidence acceptance tests."""

from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import get_db
from backend.models.realtime_voice import VoiceCapabilityEvidence
from backend.routers.admin.voice_config import router as voice_router
from backend.services.realtime_voice_capability_service import (
    CAPABILITY_EVIDENCE_NOT_FOUND,
    EVIDENCE_FINGERPRINT_FIELDS,
    CapabilityStateError,
    compute_evidence_fingerprint,
    evidence_expires_at,
    realtime_voice_capability_service,
    resolve_runtime_capability,
    run_fixture_evidence_transaction,
    validate_evidence_ttl_days,
)
from backend.services.realtime_voice_config_service import (
    realtime_voice_config_service,
)
from backend.utils.admin_auth import get_current_admin


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def override_current_admin(request: Request):
    role = request.headers.get("x-admin-role", "observer")
    return SimpleNamespace(
        id=1,
        username=f"step006-{role}",
        role=role,
    )


app = FastAPI()
app.include_router(voice_router, prefix="/api/admin/voice")
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_admin] = override_current_admin


REPORT_ID = "11111111-1111-4111-8111-111111111111"
RUN_ID = "22222222-2222-4222-8222-222222222222"


def _dimensions() -> dict[str, str]:
    return {
        "provider_profile": "doubao-prod@sha256:safe-profile",
        "model_version": "model-v1",
        "protocol_profile": "dialog-v3-pcm",
        "adapter_version": "adapter-v1",
        "sdk_version": "sdk-v1",
        "evidence_suite_version": "suite-v1",
    }


def _fixture_evidence() -> VoiceCapabilityEvidence:
    dimensions = _dimensions()
    return VoiceCapabilityEvidence(
        evidence_report_id=REPORT_ID,
        evidence_run_id=RUN_ID,
        capability_key="supports_reply_cancel",
        verification_result="failed",
        source_type="admin_capability_test",
        **dimensions,
        evidence_fingerprint=compute_evidence_fingerprint(dimensions),
        evidence_payload={
            "events": [
                {"name": "fixture.cancel.observed", "result": "not_supported"}
            ]
        },
        report_sha256="b" * 64,
        tested_at=datetime(2026, 8, 31, 1, 0, 0),
        verified_at=None,
        evidence_ttl_days_snapshot=30,
        expires_at=None,
        operator_id=42,
        created_at=datetime(2026, 8, 31, 1, 1, 0),
    )


@pytest_asyncio.fixture(autouse=True)
async def evidence_table():
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: VoiceCapabilityEvidence.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )
    async with session_factory() as session:
        session.add(_fixture_evidence())
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: VoiceCapabilityEvidence.__table__.drop(
                sync_connection,
                checkfirst=True,
            )
        )


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://step006",
    ) as http_client:
        yield http_client


def _headers(role: str) -> dict[str, str]:
    return {"x-admin-role": role}


def test_six_dimension_fingerprint_is_exact_canonical_and_order_independent():
    dimensions = _dimensions()
    canonical = json.dumps(
        {field: dimensions[field] for field in EVIDENCE_FINGERPRINT_FIELDS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert compute_evidence_fingerprint(dimensions) == expected
    assert compute_evidence_fingerprint(dict(reversed(list(dimensions.items())))) == expected
    assert (
        compute_evidence_fingerprint(
            {**dimensions, "provider": "not-a-seventh-dimension"}
        )
        == expected
    )
    assert len(expected) == 64

    for field in EVIDENCE_FINGERPRINT_FIELDS:
        changed = deepcopy(dimensions)
        changed[field] += "-changed"
        assert compute_evidence_fingerprint(changed) != expected

    for invalid in (
        {key: value for key, value in dimensions.items() if key != "sdk_version"},
        {**dimensions, "sdk_version": ""},
        {**dimensions, "sdk_version": 7},
        [],
    ):
        with pytest.raises(CapabilityStateError) as exc_info:
            compute_evidence_fingerprint(invalid)
        assert exc_info.value.code == "VOICE_CAPABILITY_EVIDENCE_DIMENSION_INVALID"


def test_ttl_is_integer_7_to_90_and_expiry_is_derived_from_verified_at():
    assert validate_evidence_ttl_days(7) == 7
    assert validate_evidence_ttl_days(90) == 90
    for invalid in (6, 91, True, 30.0, "30"):
        with pytest.raises(CapabilityStateError) as exc_info:
            validate_evidence_ttl_days(invalid)
        assert exc_info.value.code == "VOICE_CAPABILITY_EVIDENCE_TTL_INVALID"
        assert exc_info.value.field == "evidence_ttl_days"

    verified_at = datetime(2026, 8, 31, 1, 2, 3, tzinfo=timezone.utc)
    assert evidence_expires_at(verified_at, 30) == verified_at + timedelta(days=30)


def _verified_fixture_projection() -> dict:
    verified_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    dimensions = _dimensions()
    return {
        "verification_status": "verified",
        "enabled": True,
        "forced_enabled": False,
        "effective_scope": "test",
        "fallback_mode": "next_turn",
        **dimensions,
        "evidence_fingerprint": compute_evidence_fingerprint(dimensions),
        "evidence_ttl_days": 30,
        "verified_at": verified_at.isoformat(),
        "expires_at": (verified_at + timedelta(days=30)).isoformat(),
        "evidence_report_id": REPORT_ID,
        "last_test_result": "not_run",
    }


def _assert_stale_disabled(resolved: dict) -> None:
    assert resolved["verification_status"] == "stale"
    assert resolved["enabled"] is False
    assert resolved["forced_enabled"] is False
    assert resolved["effective_scope"] == "off"


def test_each_dimension_change_and_expiry_force_stale_false_off_without_mutation():
    original = _verified_fixture_projection()
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)

    for field in EVIDENCE_FINGERPRINT_FIELDS:
        current = _dimensions()
        current[field] += "-changed"
        resolved = resolve_runtime_capability(
            original,
            current_dimensions=current,
            now=now,
        )
        _assert_stale_disabled(resolved)

        changed_projection = deepcopy(original)
        changed_projection[field] += "-changed"
        resolved_projection = resolve_runtime_capability(
            changed_projection,
            current_dimensions=_dimensions(),
            now=now,
        )
        _assert_stale_disabled(resolved_projection)

    at_expiry = resolve_runtime_capability(
        original,
        current_dimensions=_dimensions(),
        now=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    _assert_stale_disabled(at_expiry)

    invalid_ttl = deepcopy(original)
    invalid_ttl["evidence_ttl_days"] = 6
    _assert_stale_disabled(
        resolve_runtime_capability(
            invalid_ttl,
            current_dimensions=_dimensions(),
            now=now,
        )
    )

    inconsistent_expiry = deepcopy(original)
    inconsistent_expiry["expires_at"] = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    ).isoformat()
    _assert_stale_disabled(
        resolve_runtime_capability(
            inconsistent_expiry,
            current_dimensions=_dimensions(),
            now=now,
        )
    )

    missing_report = deepcopy(original)
    missing_report["evidence_report_id"] = None
    _assert_stale_disabled(
        resolve_runtime_capability(
            missing_report,
            current_dimensions=_dimensions(),
            now=now,
        )
    )
    assert original == _verified_fixture_projection()


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("enabled", "true"),
        ("enabled", 1),
        ("forced_enabled", "false"),
        ("forced_enabled", 0),
        ("effective_scope", "gray"),
        ("effective_scope", "percentage"),
        ("effective_scope", {}),
    ],
)
def test_malformed_verified_projection_fails_closed(field: str, invalid):
    capability = _verified_fixture_projection()
    capability[field] = invalid
    resolved = resolve_runtime_capability(
        capability,
        current_dimensions=_dimensions(),
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    _assert_stale_disabled(resolved)


def test_malformed_current_dimensions_fail_closed():
    resolved = resolve_runtime_capability(
        _verified_fixture_projection(),
        current_dimensions=[],
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    _assert_stale_disabled(resolved)


@pytest.mark.parametrize("status", ["unverified", "failed", "stale"])
def test_non_verified_runtime_states_are_always_false_off(status: str):
    capability = {
        "verification_status": status,
        "enabled": True,
        "forced_enabled": True,
        "effective_scope": "test",
        "evidence_ttl_days": 30,
    }
    resolved = resolve_runtime_capability(
        capability,
        current_dimensions={},
        now=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    assert resolved["verification_status"] == status
    assert resolved["enabled"] is False
    assert resolved["forced_enabled"] is False
    assert resolved["effective_scope"] == "off"
    assert capability["enabled"] is True


async def _stored_projection() -> tuple:
    async with session_factory() as session:
        row = (
            await session.execute(
                select(VoiceCapabilityEvidence).where(
                    VoiceCapabilityEvidence.evidence_report_id == REPORT_ID
                )
            )
        ).scalars().one()
        return (
            row.id,
            row.evidence_report_id,
            row.evidence_run_id,
            row.capability_key,
            row.verification_result,
            row.source_type,
            row.evidence_fingerprint,
            json.dumps(row.evidence_payload, ensure_ascii=False, sort_keys=True),
            row.operator_id,
            row.created_at,
        )


@pytest.mark.asyncio
async def test_evidence_get_has_five_role_projection_and_is_read_only(client: AsyncClient):
    before = await _stored_projection()
    path = f"/api/admin/voice/capability-evidence/{REPORT_ID}"

    for role in ("super_admin", "tech_ops"):
        response = await client.get(path, headers=_headers(role))
        assert response.status_code == 200, (role, response.text)
        projected = response.json()["data"]
        assert projected["evidence_payload"] == {
            "events": [
                {"name": "fixture.cancel.observed", "result": "not_supported"}
            ]
        }
        assert projected["operator_id"] == 42

    for role in ("ai_trainer", "ops_admin", "observer"):
        response = await client.get(path, headers=_headers(role))
        assert response.status_code == 200, (role, response.text)
        projected = response.json()["data"]
        assert "evidence_payload" not in projected
        assert "operator_id" not in projected
        assert not [key for key in projected if "operator" in key]

    forbidden = await client.get(path, headers=_headers("unknown_role"))
    assert forbidden.status_code == 403

    missing = await client.get(
        "/api/admin/voice/capability-evidence/missing-report",
        headers=_headers("observer"),
    )
    assert missing.status_code == 404
    assert missing.json()["data"]["error_code"] == CAPABILITY_EVIDENCE_NOT_FOUND
    assert await _stored_projection() == before


@pytest.mark.asyncio
async def test_evidence_route_exposes_get_only_and_service_has_only_frozen_internal_writers(
    client: AsyncClient,
):
    route_path = "/capability-evidence/{evidence_report_id}"
    matching_routes = [
        route
        for route in voice_router.routes
        if getattr(route, "path", None) == route_path
    ]
    assert len(matching_routes) == 1
    assert matching_routes[0].methods == {"GET"}

    actual_path = f"/api/admin/voice/capability-evidence/{REPORT_ID}"
    for method in ("post", "put", "patch", "delete"):
        response = await getattr(client, method)(
            actual_path,
            headers=_headers("super_admin"),
        )
        assert response.status_code == 405, (method, response.text)

    internal_write_methods = {
        name
        for name in dir(realtime_voice_capability_service)
        if name.startswith(("append", "create", "delete", "force", "import", "test", "update"))
    }
    assert internal_write_methods == {
        "append_admin_capability_evidence",
        "import_phase0_evidence_bundle",
        "import_phase0_evidence_selection",  # User-approved M1 report selection, internal only.
    }


class _FailingFixtureTransactionPort:
    def __init__(self) -> None:
        self.evidence = [{"evidence_report_id": "existing"}]
        self.projection = {"verification_status": "unverified", "effective_scope": "off"}
        self.events: list[str] = []
        self._snapshot = None

    async def begin(self) -> None:
        self.events.append("begin")
        self._snapshot = (deepcopy(self.evidence), deepcopy(self.projection))

    async def stage_fixture_evidence(self, rows) -> None:
        self.events.append("stage_evidence")
        self.evidence.extend(deepcopy(list(rows)))

    async def stage_fixture_projection(self, projection) -> None:
        self.events.append("stage_projection")
        self.projection = deepcopy(dict(projection))
        raise RuntimeError("controlled fixture projection failure")

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")
        self.evidence, self.projection = deepcopy(self._snapshot)


@pytest.mark.asyncio
async def test_fixture_transaction_port_failure_rolls_back_evidence_and_projection():
    port = _FailingFixtureTransactionPort()
    before = (deepcopy(port.evidence), deepcopy(port.projection))

    with pytest.raises(RuntimeError, match="controlled fixture projection failure"):
        await run_fixture_evidence_transaction(
            port,
            rows=[
                {
                    "evidence_report_id": "fixture-only",
                    "verification_result": "failed",
                }
            ],
            projection={
                "verification_status": "unverified",
                "enabled": False,
                "effective_scope": "off",
            },
        )

    assert (port.evidence, port.projection) == before
    assert port.events == [
        "begin",
        "stage_evidence",
        "stage_projection",
        "rollback",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "service_method", "body"),
    [
        (
            "/api/admin/voice/config/config/publish",
            "publish",
            {"confirm_text": "CONFIRM", "change_note": "STEP-006 log boundary"},
        ),
        (
            "/api/admin/voice/config/config/rollback",
            "rollback",
            {
                "version": 1,
                "confirm_text": "CONFIRM",
                "change_note": "STEP-006 log boundary",
            },
        ),
    ],
)
async def test_publish_and_rollback_unexpected_errors_do_not_log_exception_secrets(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    path: str,
    service_method: str,
    body: dict,
):
    sentinel = "STEP006_PROVIDER_SECRET_SENTINEL"

    async def fail_without_side_effects(*args, **kwargs):
        raise RuntimeError(f"upstream raw response contained {sentinel}")

    monkeypatch.setattr(
        realtime_voice_config_service,
        service_method,
        fail_without_side_effects,
    )
    caplog.set_level(logging.ERROR, logger="backend.routers.admin.voice_config")

    response = await client.post(path, headers=_headers("super_admin"), json=body)

    assert response.status_code == 503
    assert sentinel not in response.text
    assert sentinel not in caplog.text
    assert "Traceback" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)

"""Isolated MySQL/Redis record API and export acceptance."""
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from backend.database import Base
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.realtime_voice import VoiceMemoryJob,VoiceMemoryTrace,VoicePostprocessJob,VoiceFollowupJob
from backend.models.relationship_growth_log import RelationshipGrowthLog
from tests.test_realtime_voice_m4_runtime import containers,runtime
from tests.test_realtime_voice_step028_jobs import add_turn
from tests.test_realtime_voice_step033_records import (
    test_record_role_matrix_and_audit,test_debug_role_expiry_and_each_read_audit,
    test_jobs_metadata_has_no_extraction_body,test_summary_retry_http_uses_existing_service_and_role_boundary,
    test_list_filters_and_deleted_audit_boundary,test_record_metadata_tabs_role_and_projection,
    test_list_statistics_count_records_without_exposing_job_bodies,test_export_exact_authorized_projection_multiset,
    test_config_snapshot_credential_role_projection,test_config_snapshot_legacy_empty_compatibility,
    test_config_snapshot_audit_failure_returns_no_data,
    test_r04_list_records_one_safe_request_summary,test_r04_export_keeps_all_call_links_and_audit_lookup,
    test_r04_failed_requests_persist_safe_audit,test_r04_real_auth_role_denials_are_audited,
    test_r04_invalid_identity_never_creates_operator_audit,test_r04_failed_transaction_uses_independent_audit,
    test_r04_untrusted_filters_are_hashed_or_omitted,test_r04_bulk_rejection_keeps_bounded_targets,
    test_r04_job_metadata_audit_uses_its_own_permission,
)

pytestmark=pytest.mark.skipif(os.getenv('RUN_VOICE_M6_RUNTIME')!='1',reason='isolated runtime opt-in')


@pytest_asyncio.fixture
async def card_env(runtime):
    factory,call_id,_=runtime
    tables=[m.__table__ for m in (VoiceMemoryJob,VoiceMemoryTrace,VoicePostprocessJob,VoiceFollowupJob,RelationshipGrowthLog)]
    async with factory.kw['bind'].begin() as conn:
        await conn.run_sync(Base.metadata.create_all,tables=tables)
    try: yield factory,call_id
    finally:
        async with factory.kw['bind'].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all,tables=tables)


@pytest.mark.asyncio
async def test_audit_tab_reads_legacy_jobs_with_existing_log_collation(card_env, monkeypatch):
    """The legacy operation log uses a different collation from MySQL 8 expressions."""
    from tests.test_realtime_voice_step033_records import r04_application

    factory, call_id = card_env
    async with factory.kw['bind'].begin() as conn:
        await conn.execute(text(
            'ALTER TABLE admin_operation_logs MODIFY target_description '
            'VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL'
        ))

    turn_id = await add_turn(factory, call_id)
    async with factory() as db:
        memory = VoiceMemoryJob(call_id=call_id, turn_id=turn_id, turn_index=1,
                                pipeline_version='voice_memory_v1', status='pending')
        summary = VoicePostprocessJob(call_id=call_id, job_type='call_summary', status='pending')
        db.add_all([memory, summary])
        await db.flush()
        logs = [AdminOperationLog(admin_user_id=1, admin_username='test', module='voice_job',
                                  action='retry', target_description=target)
                for target in (f'memory:{memory.id}', f'call_summary:{summary.id}')]
        db.add_all(logs)
        await db.commit()
        expected_ids = {log.id for log in logs}

    app, headers, _ = await r04_application(factory, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False),
                           base_url='http://test', headers=headers) as client:
        response = await client.get(f'/api/admin/voice/calls/{call_id}/audit')

    assert response.status_code == 200
    assert {item['id'] for item in response.json()['data']['items']} == expected_ids

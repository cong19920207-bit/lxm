"""AC55: force-test audit retains explicit non-content capability facts."""
import json
import pytest
from tests import test_realtime_voice_step006_capability_control as support
from tests.test_realtime_voice_step006_capability_control import database
from backend.services.realtime_voice_config_service import realtime_voice_config_service


@pytest.mark.asyncio
@pytest.mark.parametrize('status',['unverified','stale'])
async def test_force_audit_keeps_evidence_version_scope_and_fallback(database,status):
    config=support._default_config()
    if status=='stale':config=support._trusted_projection(config,'stale',forced=False)
    await support._insert_voice_config(config,draft=config)
    async with support.session_factory() as db:
        await realtime_voice_config_service.force_capability_test(db,
            capability_key=support.CAPABILITY_KEY,effective_scope='test',confirm_text='CONFIRM',
            reason=support.SECRET_SENTINEL,admin_user=await support._admin(db,'super_admin'))
        await db.commit()
    logs=await support._operation_logs()
    assert len(logs)==1 and logs[0].admin_user_id==support.role_ids['super_admin']
    payload=json.loads(logs[0].after_value)
    original=config['capabilities'][support.CAPABILITY_KEY]
    assert payload['capability_audit']=={
        'capability_key':support.CAPABILITY_KEY,'effective_scope':'test',
        'fallback_mode':original['fallback_mode'],
        'evidence_report_id':original.get('evidence_report_id'),
        'evidence_suite_version':original.get('evidence_suite_version'),
        'evidence_fingerprint':original.get('evidence_fingerprint')}
    assert support.SECRET_SENTINEL not in logs[0].after_value
    assert 'credential_ref' not in logs[0].after_value

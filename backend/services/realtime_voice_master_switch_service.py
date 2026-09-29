"""Independent, database-authoritative voice master switch; never writes config drafts."""
from dataclasses import dataclass
from datetime import datetime
import json

from sqlalchemy import select

from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY, VOICE_CALL_MASTER_SWITCH_KEY
from backend.models.admin_config import AdminConfig
from backend.services.realtime_voice_config_service import VoiceConfigError
from backend.utils.admin_auth import log_operation


@dataclass(frozen=True)
class VoiceMasterSwitchState:
    enabled: bool
    version: int
    updated_at: datetime
    updated_by: str | None

    def as_dict(self):
        return dict(enabled=self.enabled, version=self.version,
                    updated_at=self.updated_at.isoformat(), updated_by=self.updated_by)


def parse_master_switch_rows(rows):
    if len(rows) != 1:
        return None
    row = rows[0]
    try:
        value = json.loads(row.config_value)
    except (ValueError, TypeError):
        return None
    if (row.config_key != VOICE_CALL_MASTER_SWITCH_KEY or row.is_active is not True
            or row.is_draft is not False or type(row.version) is not int or row.version < 1
            or not isinstance(row.updated_at, datetime) or type(value) is not dict
            or set(value) != {'enabled'} or type(value['enabled']) is not bool):
        return None
    return VoiceMasterSwitchState(value['enabled'], row.version, row.updated_at, row.updated_by)


class RealtimeVoiceMasterSwitchService:
    async def _rows(self, db, *, lock=False):
        query = select(AdminConfig).where(
            AdminConfig.config_key == VOICE_CALL_MASTER_SWITCH_KEY,
            AdminConfig.is_active.is_(True), AdminConfig.is_draft.is_(False),
        ).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalars().all()

    @staticmethod
    def _state(rows):
        state = parse_master_switch_rows(rows)
        if state is None:
            raise VoiceConfigError('VOICE_MASTER_SWITCH_UNAVAILABLE', '总开关状态不可用，请刷新后重试', status_code=503)
        return state

    async def get_state(self, db):
        return self._state(await self._rows(db)).as_dict()

    async def _validate_enable(self, db):
        from backend.services.realtime_voice_config_service import (
            realtime_voice_config_service, validate_trusted_voice_bundle,
            _validate_published_persona_ref, _parse_config_value,
        )
        # Lock only the published bundle while checking readiness, never its draft.
        rows = (await db.execute(select(AdminConfig).where(
            AdminConfig.config_key == VOICE_CALL_CONFIG_KEY,
            AdminConfig.is_active.is_(True), AdminConfig.is_draft.is_(False),
        ).with_for_update())).scalars().all()
        config = _parse_config_value(rows[0]) if len(rows) == 1 else None
        if config is None:
            raise VoiceConfigError('VOICE_MASTER_SWITCH_NOT_READY', '请先发布有效的语音设置')
        issues = validate_trusted_voice_bundle(VOICE_CALL_CONFIG_KEY, config)
        if issues:
            raise VoiceConfigError('VOICE_MASTER_SWITCH_NOT_READY', '已发布的语音设置未通过校验', errors=issues)
        persona_issue = await _validate_published_persona_ref(db, config)
        if persona_issue is not None:
            raise VoiceConfigError('VOICE_MASTER_SWITCH_NOT_READY', '已发布的语音设置缺少有效的人格引用', errors=[persona_issue])
        realtime_voice_config_service._ensure_credential_configured(config)
        await realtime_voice_config_service._ensure_all_scope_evidence(db, config)

    async def publish(self, db, *, enabled, expected_version, admin_user, request=None):
        try:
            rows = await self._rows(db, lock=True)
            before = self._state(rows)
            if expected_version != before.version:
                raise VoiceConfigError('VOICE_MASTER_SWITCH_CONFLICT', '总开关已被其他管理员更新，请刷新后重试', status_code=409)
            if enabled == before.enabled:
                return before.as_dict()
            if enabled:
                await self._validate_enable(db)
            after = VoiceMasterSwitchState(enabled, before.version + 1, datetime.utcnow(), admin_user.username)
            rows[0].is_active = False
            db.add(AdminConfig(config_key=VOICE_CALL_MASTER_SWITCH_KEY,
                config_value=json.dumps({'enabled': enabled}), version=after.version,
                is_active=True, is_draft=False, updated_by=after.updated_by, updated_at=after.updated_at))
            await db.flush()
            await log_operation(db=db, admin_user=admin_user, module='voice_master_switch', action='publish',
                target_description='开启语音通话总开关' if enabled else '关闭语音通话总开关',
                before_value=json.dumps(before.as_dict(), ensure_ascii=False),
                after_value=json.dumps(after.as_dict(), ensure_ascii=False), request=request)
            await db.commit()
            return after.as_dict()
        except Exception:
            await db.rollback()
            raise


realtime_voice_master_switch_service = RealtimeVoiceMasterSwitchService()

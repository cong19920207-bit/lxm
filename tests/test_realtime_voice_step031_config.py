from copy import deepcopy
import json
import pytest
from sqlalchemy import select
from backend.constants.realtime_voice_config import VOICE_CALL_CONFIG_KEY,VOICE_CALL_SCRIPT_KEY
from backend.constants.realtime_voice_summary import DEFAULT_VOICE_SUMMARY_MODEL,DEFAULT_VOICE_SUMMARY_PROMPT
from backend.services.realtime_voice_config_service import validate_voice_bundle,content_sha256
from backend.services.realtime_voice_summary_runtime import summary_model
from tests.test_realtime_voice_step006_runtime_loader import database,manifest,replace_active_rows,service,session_factory,AdminConfig


@pytest.mark.parametrize('key',[VOICE_CALL_CONFIG_KEY,VOICE_CALL_SCRIPT_KEY])
def test_new_defaults_and_legacy_optional_sections_validate(key):
    data=manifest()[key];assert validate_voice_bundle(key,data)==[]
    data.pop('summary');assert validate_voice_bundle(key,data)==[]
    data['summary']={};assert validate_voice_bundle(key,data)


@pytest.mark.parametrize('model',['https://example.test','sk-secret','','not-a-deepseek-model'])
def test_model_field_does_not_accept_credentials_or_endpoint(model):
    data=manifest()[VOICE_CALL_CONFIG_KEY];data['summary']={'model':model}
    assert validate_voice_bundle(VOICE_CALL_CONFIG_KEY,data)


@pytest.mark.asyncio
async def test_legacy_hash_unchanged_and_new_call_freezes_prompt_model():
    values=manifest()
    for value in values.values():value.pop('summary')
    hashes={key:content_sha256(value) for key,value in values.items()}
    await replace_active_rows({key:(value,4) for key,value in values.items()})
    old=(await service().load_bundle()).build_snapshot()
    assert old.config_snapshot['resolved_config']['summary']['model']==DEFAULT_VOICE_SUMMARY_MODEL
    assert old.config_snapshot['resolved_script']['summary']['prompt_template']==DEFAULT_VOICE_SUMMARY_PROMPT
    assert old.config_snapshot['config_content_sha256']==hashes[VOICE_CALL_CONFIG_KEY]
    async with session_factory() as db:
        rows=(await db.scalars(select(AdminConfig).where(AdminConfig.config_key.in_(values)))).all()
        assert all('summary' not in json.loads(row.config_value) for row in rows)
    values[VOICE_CALL_CONFIG_KEY]['summary']={'model':'deepseek-chat'}
    values[VOICE_CALL_SCRIPT_KEY]['summary']={'prompt_template':'已发布新版提示词'}
    await replace_active_rows({key:(value,5) for key,value in values.items()})
    new=(await service().load_bundle()).build_snapshot()
    assert new.config_snapshot['resolved_script']['summary']['prompt_template']=='已发布新版提示词'
    assert new.config_snapshot['resolved_config']['summary']['model']=='deepseek-chat'
    assert old.config_snapshot['resolved_script']['summary']['prompt_template']==DEFAULT_VOICE_SUMMARY_PROMPT


@pytest.mark.asyncio
async def test_deepseek_adapter_uses_frozen_model_and_separates_input(monkeypatch):
    import backend.services.realtime_voice_summary_runtime as module
    seen=[]
    class Client:
        async def chat_sync(self,messages,**kw):seen.append((messages,kw));return '{}'
        async def close(self):seen.append('closed')
    monkeypatch.setattr(module,'DeepSeekClient',Client)
    fn=summary_model({'resolved_config':{'summary':{'model':'deepseek-chat'}},'resolved_script':{'summary':{'prompt_template':'my prompt'}}})
    assert await fn('system rules\nINPUT_JSON:\n{"turns":[]}')=='{}'
    assert seen[0][0]==[{'role':'system','content':'system rules\n'},{'role':'user','content':'{"turns":[]}'}]
    assert seen[0][1]['model']=='deepseek-chat' and seen[-1]=='closed'

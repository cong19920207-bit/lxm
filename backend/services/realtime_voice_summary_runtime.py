"""DeepSeek composition for the approved post-call summary pipeline."""
from backend.constants.realtime_voice_summary import DEFAULT_VOICE_SUMMARY_MODEL,DEFAULT_VOICE_SUMMARY_PROMPT
from backend.utils.deepseek_client import DeepSeekClient,DEEPSEEK_DEFAULT_TIMEOUT


def summary_settings(snapshot):
    config=snapshot.get('resolved_config',{}).get('summary',{'model':DEFAULT_VOICE_SUMMARY_MODEL})
    script=snapshot.get('resolved_script',{}).get('summary',{'prompt_template':DEFAULT_VOICE_SUMMARY_PROMPT})
    model=config.get('model');prompt=script.get('prompt_template')
    if not isinstance(model,str) or not model.startswith('deepseek-') or not isinstance(prompt,str) or not prompt.strip():
        raise ValueError('summary_configuration_invalid')
    return model,prompt


def summary_model(snapshot):
    model,_=summary_settings(snapshot)
    async def call(prompt):
        system,separator,inputs=prompt.rpartition('INPUT_JSON:\n')
        if not separator:raise ValueError('summary_input_missing')
        client=DeepSeekClient()
        try:
            return await client.chat_sync([{'role':'system','content':system},{'role':'user','content':inputs}],
                model=model,timeout=DEEPSEEK_DEFAULT_TIMEOUT)
        finally:
            await client.close()
    return call


async def build_voice_summary_service():
    from backend.services.realtime_voice_metric_service import VoiceMetrics
    from backend.services.realtime_voice_memory_service import build_voice_memory_service
    from backend.services.realtime_voice_summary_job_service import VoiceSummaryJobService
    from backend.services.realtime_voice_summary_followup_service import stage_summary_followup
    memory=await build_voice_memory_service()
    async def prepare(*,call_id):return await memory.compensate(call_id=call_id,audited=True)
    async def permits(*,call_id,text):
        result=await memory.gate.assess(call_id=call_id,direction='assistant',text=text)
        return result.safety=='passed' and result.crisis=='passed'
    return VoiceSummaryJobService(session_factory=memory.factory,model=None,model_factory=summary_model,
        permits=permits,prepare=prepare,timeout_seconds=DEEPSEEK_DEFAULT_TIMEOUT,stage_followup=stage_summary_followup,
        metrics=VoiceMetrics(memory.gate.cache),safety_gate=memory.gate)

"""Step8 consume exactly one frozen retrieval/config/counter/Prompt result."""
import os
import time
from datetime import datetime
from backend import config as environment
from backend.database import async_session_maker
from backend.services.memory_effective_config import resolve_active_memory_config, Secret
from backend.services.memory_retrieval_pipeline import execute_memory_retrieval, RewriteProvider
from backend.services.memory_prompt_builder import reserve_prompt
from backend.services.memory_model_handoff import GuardedModelClient
from backend.services.memory_use_guard import MemoryUseGuard
from backend.services.memory_token_budget import OfficialTextCounter
from backend.services.prompt_builder import PromptBuilder
from backend.services.llm_service import parse_step5_output

async def assemble_step8_prompt(handle,*,bundled,rewrite_input,persona_text,round_context,recent_conversations,relationship_info,emotion_context):
    environment_id=os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip()
    if not environment_id:raise RuntimeError('runtime_not_active')
    isolated=environment_id.startswith('isolated:')
    deadline=time.monotonic()+max(0,(handle.deadline_at-datetime.utcnow()).total_seconds())
    credential=Secret(environment.get_volc_api_key())
    async with async_session_maker() as db:
        config=await resolve_active_memory_config(db,environment_id,allow_isolated=isolated)
    counter=OfficialTextCounter.from_config(config,credential,deadline=deadline)
    retrieval=await execute_memory_retrieval(config=config,session_factory=async_session_maker,environment_id=environment_id,
        partition='default',user_id=handle.user_id,original_deadline=deadline,rewrite_input=rewrite_input,
        persona_text=persona_text,round_context=round_context,recent_conversations=recent_conversations,
        rewrite_provider=RewriteProvider(environment.get_volc_endpoint(),config.reply_model,credential),source='step8',allow_isolated=isolated)
    async with async_session_maker() as db:
        result=await PromptBuilder(db).build_memory_prompt(config=config,retrieval=retrieval,counter=counter,user_id=handle.user_id,
            user_input=bundled,recent_conversations=recent_conversations,relationship_info=relationship_info,
            emotion_context=emotion_context,round_context=round_context,source='step8')
    return result,retrieval,config,counter,credential,deadline

async def build_step8_prompt(handle,**context):
    result,retrieval,config,counter,credential,deadline=await assemble_step8_prompt(handle,**context)
    environment_id=os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip()
    isolated=environment_id.startswith('isolated:')
    guard=MemoryUseGuard(async_session_maker,environment_id,allow_isolated=isolated)
    prepared=await reserve_prompt(result,config=config,counter=counter,guard=guard,user_id=handle.user_id,
        consumer_kind='step8',execution_id=handle.consume_id,owner_id=handle.owner,deadline_at=handle.deadline_at)
    return prepared,guard,GuardedModelClient(environment.get_volc_endpoint(),config.reply_model,credential),min(
        deadline-config.profiles["timeouts_ms"]["commit_prepare_reserve"]/1000,
        time.monotonic()+config.profiles["timeouts_ms"]["reply_call"]/1000)

async def call_step8_model(prepared,owner):
    result,guard,client,deadline=prepared
    response=await client.send(result,guard=guard,owner_id=owner,deadline=deadline)
    return parse_step5_output(response['choices'][0]['message']['content'])

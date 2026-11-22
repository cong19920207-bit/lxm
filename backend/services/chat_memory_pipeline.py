"""Main/Open consume exactly one frozen retrieval/config/counter/Prompt result."""
import os
import time
from datetime import datetime
from backend import config as environment
from backend.database import async_session_maker
from backend.services.chat_execution_context import ExecutionIdentity, read_raw_chat_context, freeze_chat_context
from backend.services.memory_query_router import route_query, RouterProvider, RouterResult
from backend.services.chat_lifecycle import renew, LostOwnership
from backend.services.memory_router_trace import ChatTrace, active_observation
from backend.services.memory_retrieval_pipeline import empty_retrieval_result
from backend.services.memory_effective_config import resolve_active_memory_config, Secret
from backend.services.memory_retrieval_pipeline import execute_memory_retrieval, RewriteProvider
from backend.services.memory_prompt_builder import reserve_prompt
from backend.services.memory_model_handoff import GuardedModelClient
from backend.services.memory_use_guard import MemoryUseGuard
from backend.services.memory_token_budget import OfficialTextCounter
from backend.services.prompt_builder import PromptBuilder
from backend.services.llm_service import parse_step5_output

async def check_chat_owner(handle):
    if datetime.utcnow() >= handle.deadline_at:
        raise TimeoutError("deadline_exceeded")
    if not await renew(handle, sessions=async_session_maker):
        raise LostOwnership()


async def read_main_context(handle, *, current_messages, current_message_ids, current_refs=(), source_channels=()):
    environment_id = os.getenv("MEMORY_RUNTIME_ENVIRONMENT_ID", "").strip()
    if not environment_id:
        raise RuntimeError("runtime_not_active")
    return await read_raw_chat_context(sessions=async_session_maker, environment_id=environment_id,
        user_id=handle.user_id, identity=ExecutionIdentity("chat",handle.generation_id,handle.epoch),
        current_messages=current_messages, current_message_ids=current_message_ids,current_refs=current_refs,source_channels=source_channels)


async def assemble_routed_prompt(raw, *, user_id, environment_id, sessions, deadline, check_execution, trace=None, mode="runtime_path"):
    config = raw.config
    credential = Secret(environment.get_volc_api_key())
    endpoint = environment.get_volc_endpoint()
    counter = OfficialTextCounter.from_config(config, credential, deadline=deadline)
    shared = await freeze_chat_context(raw, counter, deadline=deadline)
    rewrite_deadline = min(deadline, time.monotonic()+config.profiles["timeouts_ms"]["rewrite_stage"]/1000)
    if mode == "retrieval_only":
        router = RouterResult(None, "retrieval", "retrieval_only", 0, 0)
    else:
        router = await route_query(shared, counter=counter, provider=RouterProvider.from_config(config.router, config.reply_model),
            check_execution=check_execution, original_deadline=deadline, rewrite_deadline=rewrite_deadline,
            test_disabled=mode=="router_only")
    if trace:
        await trace.record("routed", shared, router, deadline)
    await check_execution()
    if mode == "router_only":
        return None, None, config, counter, credential, deadline, shared, router
    if router.path == "skip":
        retrieval = empty_retrieval_result(config, rewrite_deadline=rewrite_deadline, original_deadline=deadline)
    else:
        retrieval = await execute_memory_retrieval(config=config,session_factory=sessions,environment_id=environment_id,
            partition="default",user_id=user_id,original_deadline=deadline,rewrite_deadline=rewrite_deadline,
            rewrite_input=shared.current_input,persona_text=raw.persona.text,round_context=raw.round_context,
            recent_conversations=(),shared_history=shared.history,counter=counter,check_execution=check_execution,
            rewrite_provider=RewriteProvider(endpoint,config.reply_model,credential),source="main",
            allow_isolated=environment_id.startswith("isolated:"))
    await check_execution()
    result = await PromptBuilder(None).build_memory_prompt(config=config,retrieval=retrieval,counter=counter,
        user_id=user_id,user_input=None,recent_conversations=(),relationship_info=None,emotion_context=None,
        round_context=raw.round_context,prepared_context=shared)
    return result, retrieval, config, counter, credential, deadline, shared, router


async def assemble_main_prompt(handle,*,raw_context=None,trace=None,bundled=None,rewrite_input=None,persona_text=None,
                               round_context=None,recent_conversations=(),relationship_info=None,emotion_context=None):
    environment_id=os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID','').strip()
    if not environment_id:raise RuntimeError('runtime_not_active')
    isolated=environment_id.startswith('isolated:')
    deadline=time.monotonic()+max(0,(handle.deadline_at-datetime.utcnow()).total_seconds())
    if raw_context is not None:
        assembled = await assemble_routed_prompt(raw_context, user_id=handle.user_id, environment_id=environment_id,
            sessions=async_session_maker, deadline=deadline, check_execution=lambda: check_chat_owner(handle), trace=trace)
        return assembled[:6]
    credential=Secret(environment.get_volc_api_key())
    async with async_session_maker() as db:
        config=await resolve_active_memory_config(db,environment_id,allow_isolated=isolated)
    counter=OfficialTextCounter.from_config(config,credential,deadline=deadline)
    retrieval=await execute_memory_retrieval(config=config,session_factory=async_session_maker,environment_id=environment_id,
        partition='default',user_id=handle.user_id,original_deadline=deadline,rewrite_input=rewrite_input,
        persona_text=persona_text,round_context=round_context,recent_conversations=recent_conversations,
        rewrite_provider=RewriteProvider(environment.get_volc_endpoint(),config.reply_model,credential),source='main',allow_isolated=isolated)
    async with async_session_maker() as db:
        result=await PromptBuilder(db).build_memory_prompt(config=config,retrieval=retrieval,counter=counter,user_id=handle.user_id,
            user_input=bundled,recent_conversations=recent_conversations,relationship_info=relationship_info,
            emotion_context=emotion_context,round_context=round_context)
    return result,retrieval,config,counter,credential,deadline

async def build_main_prompt(handle, **context):
    raw = context.get("raw_context")
    if raw is None:
        return await _prepare_main_prompt(handle, context, None)
    trace = ChatTrace(async_session_maker, handle, raw)
    token = active_observation.set(trace.observed)
    try:
        return await _prepare_main_prompt(handle, context, trace)
    except Exception as exc:
        await trace.record("interrupted", exc)
        raise
    finally:
        active_observation.reset(token)


async def _prepare_main_prompt(handle, context, trace):
    options = {**context, "trace": trace} if trace else context
    result, retrieval, config, counter, credential, deadline = await assemble_main_prompt(handle, **options)
    environment_id = os.getenv("MEMORY_RUNTIME_ENVIRONMENT_ID", "").strip()
    guard = MemoryUseGuard(async_session_maker, environment_id, allow_isolated=environment_id.startswith("isolated:"))
    if trace:
        await check_chat_owner(handle)
        if result.over_budget:
            await trace.record("assembled", result, retrieval)
    prepared = await reserve_prompt(result, config=config, counter=counter, guard=guard, user_id=handle.user_id,
        consumer_kind="main", execution_id=handle.generation_id, owner_id=handle.owner, deadline_at=handle.deadline_at)
    if trace:
        await trace.record("assembled", prepared, retrieval)
    client = GuardedModelClient(environment.get_volc_endpoint(), config.reply_model, credential)
    reply_deadline = min(deadline - config.profiles["timeouts_ms"]["commit_prepare_reserve"] / 1000,
                         time.monotonic() + config.profiles["timeouts_ms"]["reply_call"] / 1000)
    return prepared, guard, client, reply_deadline


async def call_main_model(prepared,owner):
    result,guard,client,deadline=prepared
    response=await client.send(result,guard=guard,owner_id=owner,deadline=deadline)
    return parse_step5_output(response['choices'][0]['message']['content'])

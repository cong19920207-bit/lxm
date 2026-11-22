"""Concrete read-only business loading, retrieval, selection and local handoff."""
from dataclasses import asdict, replace
from datetime import datetime
from types import SimpleNamespace, MappingProxyType
from sqlalchemy import select
from backend.models.memory_diagnostic import MemoryDiagnosticRun as Run
from backend.services.chat_execution_context import read_raw_chat_context, ExecutionIdentity
from backend.services.memory_config_schema import ROUTER_KEY, MemoryQueryRouterConfig
from backend.services.memory_router_trace import CallObservation, active_observation
import time
from backend.services.memory_prompt_builder import reserve_prompt, PromptBudgetExceeded
from backend.services.memory_use_guard import MemoryUseGuard

async def load_context(source,user_id,input_text,db):
    if source=='step8':
        from backend.services.step8_subchain import _load_memory_context
    else:
        from backend.routers.chat import _load_memory_context
    context=await _load_memory_context(user_id,db)
    return {**context,'bundled':input_text,'rewrite_input':input_text}


def candidate_snapshot(item,ordinal):
    result=asdict(item)
    result.update(id=f'{item.route}:{item.identity_id}:{item.generation}',ordinal=ordinal,
        identity_id=str(item.identity_id),generation=str(item.generation),body_hash=item.body_hash.hex())
    return result


def selection_snapshot(result):
    def entry(e):
        return {'id':f'{e.candidate.route}:{e.candidate.identity_id}:{e.candidate.generation}',
            'route':e.candidate.route,'doc_id':e.candidate.doc_id,'rendered_text':e.rendered_text,
            'identity_id':str(e.candidate.identity_id),'generation':str(e.candidate.generation)}
    return dict(selected=[entry(e) for e in result.selected],initial_selected=[entry(e) for e in result.initial_selected],
        removed=[{**asdict(r),'identity_id':str(r.identity_id) if r.identity_id is not None else None} for r in result.removed],
        route_counts=dict(result.route_counts),module_charges=dict(result.module_charges),counter=dict(result.counter),
        over_budget=result.over_budget)

def annotate_candidates(output):
    selection=output['selection_result']
    final={row['id']:(i,row) for i,row in enumerate(selection['selected'])}
    initial={row['id']:i for i,row in enumerate(selection['initial_selected'])}
    for row in output['candidate_snapshots']:
        key=row['id'];chosen=final.get(key)
        row.update(selected=chosen is not None,initial_selected=key in initial,
            selection_order=chosen[0] if chosen else None,initial_selection_order=initial.get(key),
            rendered_text=chosen[1]['rendered_text'] if chosen else None,
            removals=[r for r in selection['removed'] if r['route']==row['route'] and r['doc_id']==row['doc_id']])
    return output

async def execute_diagnostic(row,sessions,environment_id):
    observation = CallObservation()
    versions = {**(row.frozen_versions or {}), "schema_version": 1}
    sources = {**(row.context_sources or {}), "schema_version": 1, "source": row.source}
    token = active_observation.set(observation)
    try:
        return await _execute(row, sessions, environment_id, observation, versions, sources)
    except PromptBudgetExceeded as exc:
        return dict(execution_state="budget_blocked", frozen_versions=versions,
            context_sources={**sources, "failed_stage":"context_budget"},
            candidate_snapshots=[], selection_result={"over_budget":True,"counter":exc.measurement},
            metrics={"schema_version":1,"observed_calls":observation.counts,"reply_calls":0,"step6_calls":0,
                     "step3_status":"budget_blocked","mode":row.mode})
    finally:
        active_observation.reset(token)


async def check_owner(sessions, row):
    async with sessions() as db:
        now = datetime.utcnow()
        valid = await db.scalar(select(Run.run_id).where(Run.run_id==row.run_id,
            Run.environment_id==row.environment_id, Run.execution_state=="running",
            Run.lease_owner==row.lease_owner, Run.lease_version==row.lease_version,
            Run.lease_until>now, Run.deadline_at>now))
        if valid is None:
            raise TimeoutError("diagnostic_ownership_lost")


async def _execute(row, sessions, environment_id, observation, versions, context_meta):
    started=time.monotonic()
    selected=versions.get("selected_router")
    router_detail=None

    def capture_config(config):
        public = config.public()
        public["providers"] = {key: {k: v for k, v in provider.items() if k in {
            "service_key", "provider", "model", "collection_name", "dimension", "dtype", "metric",
            "normalization", "version", "revision", "source", "credential_configured",
            "profile_fingerprint", "field_sources"}}
            for key, provider in public["providers"].items()}
        versions.update(public)
        context_meta.update(effective_max_total=config.prompt["max_total"],
                            loaded_at=datetime.utcnow().isoformat()+'Z')

    await check_owner(sessions,row)
    if row.source=="step8":
        from backend.services.step8_memory_pipeline import assemble_step8_prompt
        async with sessions() as db:
            context=await load_context(row.source,row.user_id,row.input_text,db)
        loaded=time.monotonic()
        handle=SimpleNamespace(user_id=row.user_id,deadline_at=row.deadline_at)
        message_ids=[str(c.id) for c in context["recent_conversations"]]
        context_meta["recent_message_ids"] = message_ids
        result,retrieval,config,counter,_,_=await assemble_step8_prompt(handle, on_config=capture_config, **context)
    else:
        from backend.services.chat_memory_pipeline import assemble_routed_prompt
        raw=await read_raw_chat_context(sessions=sessions,environment_id=environment_id,user_id=row.user_id,
            identity=ExecutionIdentity("diagnostic",row.run_id,row.lease_version),current_messages=(row.input_text,))
        if selected:
            config=replace(raw.config,router=MemoryQueryRouterConfig.model_validate(selected["config"]),
                versions=MappingProxyType({**raw.config.versions,ROUTER_KEY:{k:selected.get(k) for k in ("source","version","revision")}}))
            raw=replace(raw,config=config)
        capture_config(raw.config)
        context_meta.update(persona_source=raw.persona.source, persona_version=raw.persona.version,
                            read_errors=list(raw.read_errors), history_rounds_loaded=len(raw.history_candidates.rounds))
        loaded=time.monotonic()
        deadline=loaded+(row.deadline_at-datetime.utcnow()).total_seconds()
        result,retrieval,config,counter,_,_,shared,router=await assemble_routed_prompt(raw,user_id=row.user_id,
            environment_id=environment_id,sessions=sessions,deadline=deadline,mode=row.mode,
            check_execution=lambda:check_owner(sessions,row))
        history=shared.history
        message_ids=list(map(str,history.message_ids))
        context_meta.update(history_rounds_used=len(history.rounds),
            history_rounds_trimmed=len(raw.history_candidates.rounds)-len(history.rounds),history_digest=history.digest,
            history_render_version="shanghai-json-v1",history_timezone="Asia/Shanghai",
            history_rendered_tokens=history.rendered_tokens, fixed_prompt_tokens=shared.fixed_prompt_tokens,
            retrieval_reserve=shared.retrieval_reserve,
            history_start=history.first_message_time.isoformat() if history.first_message_time else None,
            history_end=history.last_message_time.isoformat() if history.last_message_time else None,
            history_round_refs=[dict(key=r.key,source=r.source,message_ids=list(map(str,r.message_ids))) for r in history.rounds],
            rewrite_input_truncated=shared.reply_input_truncated,reply_input_truncated=shared.reply_input_truncated,
            relationship_source="relationship.level / fixed definitions",visible_background_modules=list(shared.visible_background))
        router_detail=dict(decision=router.decision,reason=router.reason,enabled=config.router.enabled,
            model=config.router.effective_model(config.reply_model), provider=config.router.provider_name,
            thinking_enabled=config.router.thinking_enabled, timeout_ms=config.router.timeout_ms,model_profile_id=config.router.model_profile_id,
            duration_ms=router.duration_ms if observation.counts["router"] else None,
            suggested_path=router.path if row.mode=="router_only" else None,
            execution_path=None if row.mode=="router_only" else router.path,
            test_only=row.mode=="router_only", config_source=selected.get("choice") if selected else "active")
    built=time.monotonic()
    snapshots=[]
    for route,route_result in (retrieval.routes.items() if retrieval else ()):
        snapshots.extend(candidate_snapshot(item,i) for i,item in enumerate(route_result.candidate_snapshots or route_result.candidates))
    queries={route:asdict(query) for route,query in retrieval.queries.routes.items()} if retrieval else {}
    output=dict(frozen_versions=versions,context_sources={**context_meta,'rewrite_source':'step8' if row.source=='step8' else 'main',
        'recent_message_ids':message_ids,
        'input_semantics':'future_action' if row.source=='step8' else 'single_input','future_consumed':False},
        candidate_snapshots=snapshots,selection_result=None,metrics={'schema_version':1,'queries':queries,
        'routes':{key:{name:getattr(value,name) for name in ('dense_status','bm25_status','rerank_status','reason')} for key,value in retrieval.routes.items()} if retrieval else {},
        'context_ms':round((loaded-started)*1000),'retrieval_and_selection_ms':round((built-loaded)*1000),
        'call_counts':dict(retrieval.call_counts) if retrieval else {},'tokenization_calls':counter.request_count,'reply_calls':0,'step6_calls':0,'cost':None,'cost_status':'not_provided'})
    metrics=output["metrics"]
    metrics.update(router=router_detail, observed_calls=observation.counts, provider_usage=observation.usage or None,
                   mode=row.mode, retrieval_status=retrieval.retrieval_status if retrieval else "not_run",
                   step3_status="not_run" if result is None else "assembled")
    router_degraded=router_detail and router_detail["reason"] in {"timeout","invalid_response","provider_error"}
    if result is None:
        output["execution_state"]="degraded" if router_degraded else "completed"
        return output
    if result.over_budget:
        output.update(execution_state='budget_blocked',selection_result=selection_snapshot(result))
        return annotate_candidates(output)
    await check_owner(sessions,row)
    guard=MemoryUseGuard(sessions,environment_id,allow_isolated=environment_id.startswith('isolated:'))
    prepared=await reserve_prompt(result,config=config,counter=counter,guard=guard,user_id=row.user_id,
        consumer_kind='diagnostic',execution_id=row.run_id,owner_id=row.lease_owner,deadline_at=row.deadline_at)
    async def construct():
        # This is the actual local consumer. There is no reply HTTP request.
        output['selection_result']=selection_snapshot(prepared)
        return 'handed_off'
    status=await guard.handoff(prepared.use_claim_id,row.lease_owner,construct)
    if status!='handed_off':raise RuntimeError('diagnostic_handoff_unverified')
    degraded=router_degraded or (retrieval.retrieval_status!="skipped_by_router" and (not retrieval.queries.parsed or any(r.reason not in (None,'explicit_skip') or
        r.rerank_status=='fallback' or 'error' in (r.dense_status,r.bm25_status) for r in retrieval.routes.values())))
    output['metrics']['tokenization_calls']=counter.request_count
    output['execution_state']='degraded' if degraded else 'completed'
    return annotate_candidates(output)

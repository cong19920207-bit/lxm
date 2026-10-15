"""Concrete read-only business loading, retrieval, selection and local handoff."""
from dataclasses import asdict
from datetime import datetime
from types import SimpleNamespace
import time
from backend.services.memory_prompt_builder import reserve_prompt
from backend.services.memory_use_guard import MemoryUseGuard

async def load_context(source,user_id,input_text,db):
    if source=='step8':
        from backend.services.step8_subchain import _load_memory_context
        rewrite=input_text
    else:
        from backend.routers.chat import _load_memory_context,_truncate_bundled
        rewrite=_truncate_bundled(input_text)
    context=await _load_memory_context(user_id,db)
    return {**context,'bundled':input_text,'rewrite_input':rewrite}


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
    started=time.monotonic()
    async with sessions() as db:context=await load_context(row.source,row.user_id,row.input_text,db)
    loaded=time.monotonic()
    if row.source=='step8':from backend.services.step8_memory_pipeline import assemble_step8_prompt as assemble
    else:from backend.services.chat_memory_pipeline import assemble_main_prompt as assemble
    handle=SimpleNamespace(user_id=row.user_id,deadline_at=row.deadline_at)
    result,retrieval,config,counter,credential,deadline=await assemble(handle,**context)
    built=time.monotonic()
    # Public config deliberately omits endpoints, credentials and any provider response.
    versions=dict(config.public())
    versions['providers']={key:{field:value for field,value in cfg.public().items() if field in {
        'service_key','provider','model','collection_name','dimension','dtype','metric','normalization',
        'version','revision','source','credential_configured','profile_fingerprint','field_sources'}}
        for key,cfg in config.providers.items()}
    snapshots=[]
    for route,route_result in retrieval.routes.items():
        snapshots.extend(candidate_snapshot(item,i) for i,item in enumerate(route_result.candidate_snapshots or route_result.candidates))
    queries={route:asdict(query) for route,query in retrieval.queries.routes.items()}
    output=dict(frozen_versions=versions,context_sources={'source':row.source,'rewrite_source':'step8' if row.source=='step8' else 'main',
        'loaded_at':datetime.utcnow().isoformat()+'Z','recent_message_ids':[str(c.id) for c in context['recent_conversations']],
        'input_semantics':'future_action' if row.source=='step8' else 'single_input','future_consumed':False},
        candidate_snapshots=snapshots,selection_result=None,metrics={'queries':queries,
        'routes':{key:{name:getattr(value,name) for name in ('dense_status','bm25_status','rerank_status','reason')} for key,value in retrieval.routes.items()},
        'context_ms':round((loaded-started)*1000),'retrieval_and_selection_ms':round((built-loaded)*1000),
        'call_counts':dict(retrieval.call_counts),'tokenization_calls':counter.request_count,'reply_calls':0,'step6_calls':0,'cost':None,'cost_status':'not_provided'})
    if result.over_budget:
        output.update(execution_state='budget_blocked',selection_result=selection_snapshot(result))
        return annotate_candidates(output)
    guard=MemoryUseGuard(sessions,environment_id,allow_isolated=environment_id.startswith('isolated:'))
    prepared=await reserve_prompt(result,config=config,counter=counter,guard=guard,user_id=row.user_id,
        consumer_kind='diagnostic',execution_id=row.run_id,owner_id=row.lease_owner,deadline_at=row.deadline_at)
    async def construct():
        # This is the actual local consumer. There is no reply HTTP request.
        output['selection_result']=selection_snapshot(prepared)
        return 'handed_off'
    status=await guard.handoff(prepared.use_claim_id,row.lease_owner,construct)
    if status!='handed_off':raise RuntimeError('diagnostic_handoff_unverified')
    degraded=(not retrieval.queries.parsed or any(r.reason not in (None,'explicit_skip') or
        r.rerank_status=='fallback' or 'error' in (r.dense_status,r.bm25_status) for r in retrieval.routes.values()))
    output['metrics']['tokenization_calls']=counter.request_count
    output['execution_state']='degraded' if degraded else 'completed'
    return annotate_candidates(output)

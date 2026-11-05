"""Draft revisions and content-bound release checks for pet configuration."""
from copy import deepcopy
from sqlalchemy import select, func
from backend.models.pet import new_id, utcnow
from backend.models.pet_config import PetConfigDraftRevision, PetConfigVersion
from backend.models.pet_admin import PetAdminOperation, PetAdminAudit
from backend.services.pet_admin_security import check_permission, allowed, prepare_operation, execute_operation

WORKFLOWS=('immediate','daily','period','return')

def changes(before, after, path=''):
    if isinstance(before,dict) and isinstance(after,dict):
        result={}
        for key in sorted(before.keys()|after.keys()):
            result.update(changes(before.get(key),after.get(key),path+'.'+key if path else key))
        return result
    return {path:{'before':before,'after':after}} if before!=after else {}

async def record_save(db,actor,head,source):
    from backend.services.pet_config_service import fingerprint
    db.add(PetConfigDraftRevision(domain=head.domain,revision=head.draft_revision,base_version=head.draft_base_version,
        content=deepcopy(head.draft),content_digest=fingerprint(head.draft),source=source or {'kind':'edit'},saved_by=actor['id'],saved_at=head.updated_at))
    identifier=new_id();payload={'revision':head.draft_revision,'base_version':head.draft_base_version,'source':source or {'kind':'edit'}}
    result={'draft_revision':head.draft_revision,'content_digest':fingerprint(head.draft)}
    db.add(PetAdminOperation(id=identifier,admin_id=actor['id'],actor_role=actor['role'],token_version=actor['token_version'],
        action='config.draft.save',domain=head.domain,target=head.domain,reason='保存配置草稿',payload=payload,request_digest=fingerprint(payload),state='done',result=result,finished_at=utcnow()))
    await db.flush()
    db.add(PetAdminAudit(operation_id=identifier,admin_id=actor['id'],actor_role=actor['role'],action='config.draft.save',domain=head.domain,target=head.domain,reason='保存配置草稿',result=result))

def model_identity():
    from backend.services.pet_llm import deployment_config,ModelConfigurationError
    try:return deployment_config().public()
    except ModelConfigurationError:return None

def changed_workflows(before,after):
    from backend.services.pet_llm import resolve_thinking
    return [k for k in WORKFLOWS if before['workflows'][k]!=after['workflows'][k] or
        resolve_thinking(before['thinking'],before['workflow_thinking'][k])['resolved']!=resolve_thinking(after['thinking'],after['workflow_thinking'][k])['resolved']]

async def ai_tests(db,head,current):
    from backend.services.pet_config_service import defaults,fingerprint
    if head is None or head.draft is None:return []
    try:required=changed_workflows(current or defaults('ai'),head.draft)
    except (KeyError,TypeError,ValueError):
        return [{'workflow':k,'required':True,'passed':False,'reason':'configuration_invalid','revision':head.draft_revision} for k in WORKFLOWS]
    digest=fingerprint(head.draft);identity=model_identity()
    rows=list(await db.scalars(select(PetAdminOperation).where(PetAdminOperation.action=='model.test',PetAdminOperation.state=='done').order_by(PetAdminOperation.recorded_at.desc())))
    result=[]
    for workflow in WORKFLOWS:
        matching=[r for r in rows if r.target==workflow and (r.payload or {}).get('revision')==head.draft_revision and (r.payload or {}).get('digest')==digest and identity is not None and (r.result or {}).get('configuration')==identity]
        passed=next((r for r in matching if (r.result or {}).get('valid') is True and ((r.result or {}).get('usage') or {}).get('complete') is True),None)
        latest=matching[0] if matching else None
        result.append({'workflow':workflow,'required':workflow in required,'passed':bool(passed),'operation_id':passed.id if passed else latest.id if latest else None,'reason':(latest.result or {}).get('fallback_reason') if latest else 'not_tested','revision':head.draft_revision})
    return result

async def require_tests(db,head,current):
    from backend.services.pet_config_service import ConfigInvalid
    missing=[x['workflow'] for x in await ai_tests(db,head,current) if x['required'] and not x['passed']]
    if missing:raise ConfigInvalid('model_test_required:'+','.join(missing))

async def history(db,actor,domain,*,page=1,page_size=10):
    from backend.services.pet_config_service import read_config
    await check_permission(db,actor,'audit.read',domain)
    c=await read_config(db,domain);offset=(page-1)*page_size
    q=select(PetConfigDraftRevision).where(PetConfigDraftRevision.domain==domain,PetConfigDraftRevision.deleted_at.is_(None))
    editable=allowed(actor['role'],'config.publish',domain)
    total=await db.scalar(select(func.count()).select_from(q.subquery())) if editable else 0
    drafts=list(await db.scalars(q.order_by(PetConfigDraftRevision.revision.desc()).offset(offset).limit(page_size))) if editable else []
    vq=select(PetConfigVersion).where(PetConfigVersion.domain==domain)
    vt=await db.scalar(select(func.count()).select_from(vq.subquery()))
    versions=list(await db.scalars(vq.order_by(PetConfigVersion.version.desc()).offset(offset).limit(page_size)))
    return {'drafts':[{'revision':x.revision,'base_version':x.base_version,'content':x.content,'source':x.source,'saved_by':x.saved_by,'saved_at':x.saved_at.isoformat(),'current':x.revision==c['draft_revision'] and c['draft'] is not None,'diff':changes(c['content'] or {},x.content)} for x in drafts],
        'versions':[{'version':x.version,'id':x.id,'content':x.content,'effective_at':x.effective_at.isoformat(),'current':x.version==c['version'],'action':x.action,'diff':changes(c['content'] or {},x.content)} for x in versions],
        'draft_total':total,'version_total':vt,'page':page,'page_size':page_size}

async def restore(sessions,actor,domain,*,source_type,expected_revision,base_version,operation_id,reason,source_revision=None,source_version=None,workflow=None):
    from backend.services.pet_config_service import ConfigInvalid,ConfigConflict,_head,read_config,save_draft,defaults
    if source_type not in {'draft','version'}:raise ConfigInvalid('restore_source_invalid')
    if workflow is not None and (domain!='ai' or workflow not in (*WORKFLOWS,'birthday')):raise ConfigInvalid('workflow_invalid')
    payload={'source_type':source_type,'source_revision':source_revision,'source_version':source_version,'workflow':workflow,'expected_revision':expected_revision,'base_version':base_version}
    op=await prepare_operation(sessions,actor,operation_id=operation_id,action='config.draft.restore',domain=domain,target=domain,reason=reason,payload=payload)
    async def work(db,operation):
        head=await _head(db,domain)
        if head.draft_revision!=expected_revision or head.active_version!=base_version:raise ConfigConflict('draft_or_base_changed')
        if source_type=='draft':
            row=await db.scalar(select(PetConfigDraftRevision).where(PetConfigDraftRevision.domain==domain,PetConfigDraftRevision.revision==source_revision,PetConfigDraftRevision.deleted_at.is_(None)))
            if row is None:raise ConfigInvalid('draft_missing')
        else:
            row=await db.scalar(select(PetConfigVersion).where(PetConfigVersion.domain==domain,PetConfigVersion.version==source_version))
            if row is None:raise ConfigInvalid('version_missing')
        source=deepcopy(row.content)
        if workflow:
            c=await read_config(db,domain);value=deepcopy(head.draft if head.draft is not None else c['content'] or defaults(domain))
            if workflow=='birthday':value['templates']['birthday']=source['templates']['birthday']
            else:
                value['workflows'][workflow]=source['workflows'][workflow]
                # Freeze the historical effective thinking mode without changing the shared global value.
                from backend.services.pet_llm import resolve_thinking
                resolved=resolve_thinking(source['thinking'],source['workflow_thinking'][workflow])['resolved']
                if resolved=='default' and value['thinking']!='default':raise ConfigInvalid('restore_thinking_default_conflict')
                value['workflow_thinking'][workflow]='inherit' if resolved==value['thinking'] else resolved
        else:value=source
        return await save_draft(db,actor,domain,value,expected_revision=expected_revision,base_version=base_version,source=payload,force=True)
    return await execute_operation(sessions,actor,op,work)

async def delete_draft(sessions,actor,domain,revision,*,expected_revision,base_version,operation_id,reason):
    from backend.services.pet_config_service import ConfigInvalid,ConfigConflict,_head,read_config
    op=await prepare_operation(sessions,actor,operation_id=operation_id,action='config.draft.delete',domain=domain,target=str(revision),reason=reason,payload={'revision':revision,'expected_revision':expected_revision,'base_version':base_version})
    async def work(db,operation):
        head=await _head(db,domain)
        if head.draft_revision!=expected_revision or head.active_version!=base_version:raise ConfigConflict('draft_or_base_changed')
        row=await db.scalar(select(PetConfigDraftRevision).where(PetConfigDraftRevision.domain==domain,PetConfigDraftRevision.revision==revision,PetConfigDraftRevision.deleted_at.is_(None)).with_for_update())
        if row is None:raise ConfigInvalid('draft_missing')
        row.deleted_at=utcnow();row.deleted_by=actor['id']
        if revision==head.draft_revision and head.draft is not None:
            head.draft=None;head.draft_revision+=1;head.draft_base_version=head.active_version
            head.validated_digest=None;head.validated_revision=None;head.validation_error=None
            head.updated_by=actor['id'];head.updated_at=utcnow()
        await db.flush()
        return await read_config(db,domain)
    return await execute_operation(sessions,actor,op,work)

"""Server-side pet action/scope whitelist and commit-time authorization fencing."""
import json
from hashlib import sha256
from fastapi import HTTPException
from sqlalchemy import select
from backend.models.admin_user import AdminUser
from backend.models.pet_admin import PetAdminOperation, PetAdminAudit
from backend.models.pet import utcnow
from backend.utils.credential_redaction import redact_credentials

ROLES=('super_admin','ops_admin','ai_trainer','tech_ops','observer')
DOMAINS=frozenset({'runtime','facts','rules','appearance','ai','debug','copy','fault','repair'})
SCOPES={
 'super_admin':DOMAINS,
 'ops_admin':frozenset({'runtime','facts','rules','appearance','copy','fault','repair'}),
 'ai_trainer':frozenset({'ai','debug','copy'}),
 'tech_ops':DOMAINS,
 'observer':DOMAINS,
}
WRITE_ROLES={
 ('resource.register','appearance'):('super_admin','ops_admin'),
 ('config.publish','rules'):('super_admin','ops_admin'),
 ('config.publish','appearance'):('super_admin','ops_admin'),
 ('config.publish','runtime'):('super_admin','ops_admin','tech_ops'),
 ('config.publish','ai'):('super_admin','ai_trainer'),
 ('model.test','debug'):('super_admin','ai_trainer'),
 ('task.retry','copy'):('super_admin','ops_admin','ai_trainer'),
 ('task.retry','fault'):('super_admin','ops_admin','tech_ops'),
 ('text.hide','copy'):('super_admin','ops_admin','ai_trainer'),
 ('text.hide','fault'):('super_admin','tech_ops'),
 ('state.repair','repair'):('super_admin','tech_ops'),
 ('repair.request','repair'):('super_admin','ops_admin','tech_ops'),
}
WRITE_ROLES.update({('config.rollback',domain):roles for (action,domain),roles in list(WRITE_ROLES.items()) if action=='config.publish'})
WRITE_ROLES.update({(action,domain):roles for (base,domain),roles in list(WRITE_ROLES.items()) if base=='config.publish' for action in ('config.draft.restore','config.draft.delete')})

class PetAdminDenied(HTTPException):
    def __init__(self,reason='pet_permission_denied'):
        self.reason=reason
        super().__init__(403,detail={'reason':reason})

def actor_from_admin(admin):
    return {'id':admin.id,'role':admin.role,'token_version':admin.token_version}

def allowed(role,action,domain):
    if role not in ROLES or domain not in DOMAINS:return False
    if action=='overview.read':return domain=='runtime'
    if action=='pet.read':return domain=='facts'
    if action=='audit.read':return domain in SCOPES[role]
    return role in WRITE_ROLES.get((action,domain),())

async def check_permission(db,actor,action,domain,*,commit=False):
    query=select(AdminUser).where(AdminUser.id==actor['id']).execution_options(populate_existing=True)
    if commit:query=query.with_for_update()
    admin=await db.scalar(query)
    if admin is None or not admin.is_active or admin.is_locked:raise PetAdminDenied('admin_inactive')
    if admin.token_version!=actor['token_version']:raise PetAdminDenied('admin_session_changed')
    if admin.role!=actor['role']:raise PetAdminDenied('admin_role_changed')
    if not allowed(admin.role,action,domain):raise PetAdminDenied()
    return admin

def project_pet(raw,role):
    # Do not redact an unrestricted account/chat object: select pet-domain fields first.
    fields={'id','name','user_id','birth_date','adopted_at','age_days','stage','values','closeness_label',
            'unlocked_behaviors','facts','result','rule_versions','record_version','data_version'}
    result={key:value for key,value in raw.items() if key in fields}
    if role not in {'super_admin','ops_admin'}:
        result.pop('user_id',None)
        if 'name' in result:result['name']='宠物·'+str(raw.get('id',''))[-6:]
    return redact_credentials(result)

def operation_view(op):
    return redact_credentials({key:getattr(op,key) for key in (
        'id','action','domain','target','reason','state','stop_reason','result')})

async def prepare_operation(sessions,actor,*,operation_id,action,domain,target,reason,payload):
    if not operation_id or len(operation_id)>64 or not reason.strip():raise ValueError('operation id and reason required')
    if (action,domain) not in WRITE_ROLES:raise PetAdminDenied()
    # Never store credentials in the durable operation/audit data.
    safe_payload=redact_credentials(payload)
    frozen=json.dumps({'action':action,'domain':domain,'target':target,'reason':reason,'payload':safe_payload},sort_keys=True,ensure_ascii=False,allow_nan=False)
    digest=sha256(frozen.encode()).hexdigest()
    async with sessions.begin() as db:
        await check_permission(db,actor,action,domain,commit=True)
        old=await db.scalar(select(PetAdminOperation).where(PetAdminOperation.id==operation_id).with_for_update())
        if old:
            if old.admin_id!=actor['id'] or old.request_digest!=digest:raise ValueError('operation content conflict')
            return old.id
        db.add(PetAdminOperation(id=operation_id,admin_id=actor['id'],actor_role=actor['role'],token_version=actor['token_version'],
            action=action,domain=domain,target=target,reason=redact_credentials(reason),payload=safe_payload,request_digest=digest))
    return operation_id

async def execute_operation(sessions,actor,operation_id,work):
    try:
        async with sessions.begin() as db:
            operation=await db.scalar(select(PetAdminOperation).where(PetAdminOperation.id==operation_id).with_for_update())
            if operation is None or operation.admin_id!=actor['id']:raise LookupError('operation not found')
            await check_permission(db,actor,operation.action,operation.domain)
            if operation.actor_role!=actor['role'] or operation.token_version!=actor['token_version']:raise PetAdminDenied('admin_session_changed')
            if operation.state=='done':return operation.result
            if operation.state!='prepared':raise PetAdminDenied(operation.stop_reason or 'operation_not_executable')
            result=await work(db,operation)
            await check_permission(db,actor,operation.action,operation.domain,commit=True)
            operation.state='done';operation.result=redact_credentials(result);operation.finished_at=utcnow()
            db.add(PetAdminAudit(operation_id=operation.id,admin_id=actor['id'],actor_role=actor['role'],
                action=operation.action,domain=operation.domain,target=operation.target,reason=operation.reason,result=operation.result))
            return operation.result
    except PetAdminDenied as error:
        async with sessions.begin() as db:
            operation=await db.scalar(select(PetAdminOperation).where(PetAdminOperation.id==operation_id).with_for_update())
            if operation is not None and operation.admin_id==actor['id'] and operation.state=='prepared':
                operation.state='blocked';operation.stop_reason=error.reason;operation.finished_at=utcnow()
                db.add(PetAdminAudit(operation_id=operation.id,admin_id=actor['id'],actor_role=operation.actor_role,
                    action=operation.action,domain=operation.domain,target=operation.target,reason=operation.reason,result={'stop_reason':error.reason}))
        raise

async def read_audit(db,actor,*,domain=None,operation_id=None,limit=100):
    domains=SCOPES.get(actor['role'],frozenset())
    if domain is not None:
        if domain not in domains:raise PetAdminDenied()
        domains={domain}
    await check_permission(db,actor,'overview.read','runtime')
    query=select(PetAdminAudit).where(PetAdminAudit.domain.in_(domains))
    if operation_id:query=query.where(PetAdminAudit.operation_id==operation_id)
    rows=await db.scalars(query.order_by(PetAdminAudit.recorded_at.desc(),PetAdminAudit.id.desc()).limit(limit))
    return [redact_credentials({'id':x.id,'operation_id':x.operation_id,'action':x.action,'domain':x.domain,
        'target':x.target,'reason':x.reason,'result':x.result,'recorded_at':x.recorded_at.isoformat()}) for x in rows]

async def task_actor_reason(db,task,*,commit=False):
    operation_id=(task.result or {}).get('admin_operation_id')
    if not operation_id:return None
    operation=await db.get(PetAdminOperation,operation_id)
    if not operation:return 'admin_operation_missing'
    actor={'id':operation.admin_id,'role':operation.actor_role,'token_version':operation.token_version}
    try:await check_permission(db,actor,operation.action,operation.domain,commit=commit)
    except PetAdminDenied as error:return error.reason
    return None

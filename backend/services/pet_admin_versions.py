from backend.services.pet_settlement import aware
"""Complete immutable publications and pet-scoped audit, independent of general logs."""
from sqlalchemy import select,func
from fastapi import HTTPException
from backend.models.pet_config import PetConfigVersion,PetConfigHead,PetResource
from backend.models.pet_admin import PetAdminOperation,PetAdminAudit
from backend.models.pet import PetProfile,PetState,PetFactEvent,PetSnapshot,PetFormalText,utcnow
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_budget import PetRequestAttempt
from backend.services.pet_admin_security import check_permission,SCOPES
from backend.services.pet_admin_read import serialize
from backend.services.pet_appearance import resource_references
from backend.services.pet_config_service import _validate,ConfigInvalid
from backend.services.pet_persistence import _utc

def contains(value,identifiers):
 if isinstance(value,dict):return any(contains(v,identifiers) for v in value.values())
 if isinstance(value,list):return any(contains(v,identifiers) for v in value)
 return isinstance(value,str) and value in identifiers

async def scope(db,actor,domain):
 await check_permission(db,actor,'overview.read','runtime')
 domains=SCOPES[actor['role']]
 if domain:await check_permission(db,actor,'audit.read',domain);domains={domain}
 return domains

async def versions(db,actor,*,domain=None,version=None,admin_id=None,action=None,start=None,end=None,at=None,page=1,page_size=20):
 domains=await scope(db,actor,domain);at=_utc(aware(at or utcnow()));q=select(PetConfigVersion,PetAdminOperation).join(PetAdminOperation,PetConfigVersion.operation_id==PetAdminOperation.id).where(PetConfigVersion.domain.in_(domains),PetConfigVersion.recorded_at<=at)
 for value,column in ((version,PetConfigVersion.version),(admin_id,PetAdminOperation.admin_id),(action,PetConfigVersion.action)):
  if value is not None:q=q.where(column==value)
 if start:q=q.where(PetConfigVersion.recorded_at>=_utc(aware(start)))
 if end:q=q.where(PetConfigVersion.recorded_at<=_utc(aware(end)))
 total=await db.scalar(select(func.count()).select_from(q.subquery()));rows=(await db.execute(q.order_by(PetConfigVersion.recorded_at.desc(),PetConfigVersion.id).offset((page-1)*page_size).limit(page_size))).all()
 heads={h.domain:h.active_version for h in await db.scalars(select(PetConfigHead).where(PetConfigHead.domain.in_(domains)))}
 return {'list':[{**serialize(v,actor['role']),'current':v.version==heads.get(v.domain),'source_draft_revision':(op.result or {}).get('source_draft_revision'),'restored_from_version':(op.result or {}).get('restored_from_version'),'admin_id':op.admin_id,'reason':op.reason,'scope':(op.result or {}).get('scope')} for v,op in rows],'page':page,'page_size':page_size,'total':total,'at':at.isoformat()}

async def version_detail(db,actor,version_id):
 v=await db.get(PetConfigVersion,version_id)
 if not v:raise HTTPException(404,detail='version_missing')
 await check_permission(db,actor,'audit.read',v.domain);op=await db.get(PetAdminOperation,v.operation_id);head=await db.get(PetConfigHead,v.domain)
 previous=await db.scalar(select(PetConfigVersion).where(PetConfigVersion.domain==v.domain,PetConfigVersion.version<v.version).order_by(PetConfigVersion.version.desc()).limit(1))
 before=previous.content if previous else {};after=v.content;diff={key:{'before':before.get(key),'after':after.get(key)} for key in before.keys()|after.keys() if before.get(key)!=after.get(key)}
 ids={x for x in (v.id,v.snapshot_id,v.growth_snapshot_id,v.state_snapshot_id) if x};references=[]
 for model in (PetProfile,PetState,PetFactEvent,PetSnapshot,PetFormalText,PetGenerationTask,PetRequestAttempt):
  for row in await db.scalars(select(model)):
   data={c.name:getattr(row,c.name) for c in model.__table__.columns}
   if contains(data,ids):references.append({'kind':model.__tablename__,'id':getattr(row,'id',None) or row.pet_id,'pet_id':getattr(row,'pet_id',None),'reason':'saved business/history references this immutable version or rule snapshot'})
 resources=[]
 if v.domain=='appearance':
  for rid in sorted(set([*v.content['stages'].values(),v.content['fallback'],*v.content['actions'].values(),v.content.get('template',{}).get('scene','approved-v4:room.webp')])):
   r=await db.get(PetResource,rid);resources.append({'id':rid,'available':bool(r and r.available),'references':await resource_references(db,rid)})
 try:await _validate(db,v.domain,v.content);validation={'valid_now':True,'reason':None}
 except (ConfigInvalid,ValueError) as e:validation={'valid_now':False,'reason':str(e)}
 return {'version':serialize(v,actor['role']),'before':before,'after':after,'full_diff':diff,'operation':serialize(op,actor['role']),'scope':(op.result or {}).get('scope'),'validation':validation,'current_version':head.active_version if head else 0,'references':references,'resources':resources,'protection':'Published versions and referenced evidence are retained; ordinary diagnostic cleanup never deletes them.'}

async def audit(db,actor,*,domain=None,action=None,admin_id=None,operation_id=None,object_id=None,start=None,end=None,at=None,page=1,page_size=20):
 domains=await scope(db,actor,domain);at=_utc(aware(at or utcnow()));q=select(PetAdminAudit,PetAdminOperation).join(PetAdminOperation,PetAdminAudit.operation_id==PetAdminOperation.id).where(PetAdminAudit.domain.in_(domains),PetAdminAudit.recorded_at<=at)
 for value,column in ((action,PetAdminAudit.action),(admin_id,PetAdminAudit.admin_id),(operation_id,PetAdminAudit.operation_id)):
  if value is not None:q=q.where(column==value)
 if start:q=q.where(PetAdminAudit.recorded_at>=_utc(aware(start)))
 if end:q=q.where(PetAdminAudit.recorded_at<=_utc(aware(end)))
 ids={object_id} if object_id else set()
 # Resolve associations using stable ids, never names or matching counts.
 if object_id:
  pet=await db.get(PetProfile,object_id)
  if pet:
   for model in (PetGenerationTask,PetRequestAttempt,PetFormalText):ids.update(await db.scalars(select(model.id).where(model.pet_id==pet.id)))
  attempt=await db.get(PetRequestAttempt,object_id)
  if attempt and attempt.origin!='debug' and len(attempt.request_key.split(':'))>=4:ids.add(attempt.request_key.split(':')[2])
  task=await db.get(PetGenerationTask,object_id)
  if task:
   ids.update(await db.scalars(select(PetRequestAttempt.id).where(PetRequestAttempt.request_key.startswith('user:'+str(task.user_id)+':'+task.id+':'))))
 rows=(await db.execute(q.order_by(PetAdminAudit.recorded_at.desc(),PetAdminAudit.id))).all()
 if object_id:rows=[(a,o) for a,o in rows if a.target in ids or a.operation_id in ids or contains(a.result,ids) or contains(o.payload,ids)]
 items=[{**serialize(a,actor['role']),'actor_role':a.actor_role,'operation_state':o.state} for a,o in rows[(page-1)*page_size:page*page_size]]
 return {'list':items,'total':len(rows),'page':page,'page_size':page_size,'at':at.isoformat(),'scope':'pet domain only; no general operation log access'}

async def impact(db,actor,domain,*,revision=None,target_version=None):
 from backend.services.pet_config_service import read_config
 from backend.services.pet_admin_security import allowed
 action='config.rollback' if target_version is not None else 'config.publish'
 await check_permission(db,actor,action,domain)
 head=await read_config(db,domain);current=head['content'] or {};target=None
 if target_version is not None:
  row=await db.scalar(select(PetConfigVersion).where(PetConfigVersion.domain==domain,PetConfigVersion.version==target_version))
  if not row:raise ConfigInvalid('target_version_missing')
  target=row.content
 else:
  if revision!=head['draft_revision'] or head['draft'] is None:raise ConfigInvalid('draft_revision_changed')
  target=head['draft']
 blocked=[]
 try:await _validate(db,domain,target)
 except (ConfigInvalid,ValueError) as error:blocked.append(str(error))
 if domain=='ai' and target_version is None:
  from backend.services.pet_config_history import require_tests
  try:await require_tests(db,await db.get(PetConfigHead,domain),current)
  except ConfigInvalid as error:blocked.append(str(error))
 refs=[]
 if domain=='appearance':
  for rid in sorted(set([*target['stages'].values(),target['fallback'],*target['actions'].values(),target.get('template',{}).get('scene','approved-v4:room.webp')])):
   refs.append({'resource_id':rid,'references':await resource_references(db,rid)})
 scope={'rules':'成长仅新领养绑定；其他规则用于后续执行，历史事实和已有收益不重算','appearance':'空闲时刷新当前展示；旧照片、历史资源和个体身份保留','ai':'后续表达使用新配置；已保存文字保留','runtime':'独立开关即时生效；账号停用和维护优先'}[domain]
 return {'current_version':head['version'],'target_version':target_version,'revision':revision,'full_diff':{k:{'before':current.get(k),'after':target.get(k)} for k in current.keys()|target.keys() if current.get(k)!=target.get(k)},'scope':scope,'references':refs,'blocked':blocked,'effective':'提交后由服务端再次核验当前基准与权限','preview_only':True}

"""Paid simulation has its own attempt and no pet identity or business writer."""
import json
from copy import deepcopy
from sqlalchemy import select
from backend.models.pet import utcnow
from backend.models.pet_admin import PetAdminOperation,PetAdminAudit
from backend.models.pet_config import PetConfigHead
from backend.services.pet_admin_security import check_permission,prepare_operation,operation_view,PetAdminDenied
from backend.services.pet_config_service import read_config,defaults,_validate,fingerprint,ConfigConflict,ConfigInvalid
from backend.services.pet_expression import render_template,workflow_config,validate_output,count_text,OutputInvalid
from backend.services.pet_llm import deployment_config,resolve_thinking,send_once,ProviderFailure,status
from backend.services.pet_settlement import aware
from backend.services import pet_budget as budget


def sample():
 return {'pet_name':'示例小狗','stage':'puppy','date':'2026-11-01','facts':[{'id':'sim-touch','event_type':'touch','source':'actual_execution','participants':['player'],'result':{'completed':True}}]}

def prompt_for(ai,workflow,inputs):
 if workflow not in {'immediate','daily','period','return'}:raise ConfigInvalid('workflow_invalid')
 if len(json.dumps(inputs,ensure_ascii=False))>30000:raise ConfigInvalid('simulation_input_too_large')
 facts=inputs.get('facts',[])
 if not isinstance(facts,list) or not 1<=len(facts)<=20:raise ConfigInvalid('simulation_facts_required')
 for f in facts:
  if not isinstance(f,dict) or not isinstance(f.get('id'),str) or not isinstance(f.get('participants'),list) or set(f['participants'])-{'player','xiaomeng'}:raise ConfigInvalid('simulation_fact_invalid')
 if len({f['id'] for f in facts})!=len(facts):raise ConfigInvalid('simulation_fact_duplicate')
 values={**inputs,'facts':json.dumps(facts,ensure_ascii=False),'participants':','.join(sorted({p for f in facts for p in f['participants']}))}
 config=workflow_config(ai,workflow);prompt=render_template(config['prompt'],values)
 return [{'role':'system','content':prompt+' 仅表达给定模拟事实，返回JSON: {"sentences":[{"text":"短句","source_ids":["事实ID"],"participants":["player"]}],"invitation":null}。不新增动作或参与者。仅描述已完成动作；reaction为空时不描写狗的回应，不推测情绪，不补写摇尾巴、靠近、叫声等未记录反应。目标'+str(config['target'])+'字，最多'+str(config['maximum'])+'字。'},{'role':'user','content':json.dumps({'simulation':True,'facts':facts,'profile':{'name':inputs.get('pet_name'),'stage':inputs.get('stage')}},ensure_ascii=False)}]

async def template_preview(db,actor,*,content=None,inputs=None,readonly=False):
 await check_permission(db,actor,'audit.read' if readonly else 'config.publish','ai');c=content or (await read_config(db,'ai'))['content'] or defaults('ai');await _validate(db,'ai',c)
 inputs=inputs or sample();values={**inputs,'facts':json.dumps(inputs.get('facts',[]),ensure_ascii=False),'participants':','.join(sorted({p for f in inputs.get('facts',[]) for p in f.get('participants',[])}))}
 rendered={k:{'body':render_template(v,values),'characters':count_text(render_template(v,values))} for k,v in c['templates'].items()}
 workflows={k:{'prompt':prompt_for(c,k,inputs)[0]['content'] if inputs.get('facts') else None,'blocked':None if inputs.get('facts') else 'no_new_facts','thinking':resolve_thinking(c['thinking'],c['workflow_thinking'][k]),'target':v['target'],'maximum':v['maximum']} for k,v in c['workflows'].items()}
 return {'kind':'template_preview','content_digest':fingerprint(c),'templates':rendered,'workflows':workflows,'model_requests':0,'simulation_only':True,'model_status':status(c)}

async def simulate(sessions,actor,*,operation_id,reason,revision,content_digest,workflow,inputs,config=None,transport=None,clock=None):
 clock=clock or (lambda:aware(utcnow()))
 async with sessions() as db:
  await check_permission(db,actor,'model.test','debug')
  old=await db.get(PetAdminOperation,operation_id)
  if old:
   expected={'revision':revision,'digest':content_digest,'workflow':workflow,'input':inputs}
   if old.admin_id!=actor['id'] or old.action!='model.test' or any(old.payload.get(k)!=v for k,v in expected.items()) or old.reason!=reason:raise ConfigConflict('operation_content_changed')
   if old.state!='prepared':return operation_view(old)
  c=await read_config(db,'ai');ai=c['draft']
  if ai is None or c['draft_revision']!=revision or fingerprint(ai)!=content_digest:raise ConfigConflict('simulation_draft_changed')
  await _validate(db,'ai',ai);messages=prompt_for(ai,workflow,inputs)
  thinking=resolve_thinking(ai['thinking'],ai['workflow_thinking'][workflow])
 config=config or deployment_config()
 await prepare_operation(sessions,actor,operation_id=operation_id,action='model.test',domain='debug',target=workflow,reason=reason,payload={'revision':revision,'digest':content_digest,'workflow':workflow,'input':inputs,'ai':ai})
 async with sessions.begin() as db:
  await check_permission(db,actor,'model.test','debug',commit=True)
  op=await db.scalar(select(PetAdminOperation).where(PetAdminOperation.id==operation_id).with_for_update())
  if op.state!='prepared':return operation_view(op)
  head=await db.get(PetConfigHead,'ai')
  if head.draft_revision!=revision or fingerprint(head.draft)!=content_digest:raise ConfigConflict('simulation_draft_changed')
  a=await budget.reserve(db,None,request_key=operation_id,origin='debug',kind=workflow,debug_owner=actor['id'],now=clock(),lease_seconds=int(config.timeout_seconds)+30)
  attempt_id=a.id
  if not await budget.authorize_send(db,a.id,now=clock()):raise budget.BudgetDenied('debug_send_not_authorized')
  op.state='running';op.result={'attempt_id':a.id,'content_digest':content_digest,'revision':revision,'configuration':config.public(),'thinking':thinking}
 try:
  async with sessions() as db:
   from backend.services.memory_business_guard import guard_business_write
   await guard_business_write(db);await check_permission(db,actor,'model.test','debug')
  raw=await send_once(config,messages,thinking,transport=transport,clock=clock)
  try:
   output=validate_output(json.loads(raw['content']),inputs['facts'],maximum=workflow_config(ai,workflow)['maximum'],allowed_invitations=[],title_max=workflow_config(ai,workflow)['title_max'])
   result={**{k:v for k,v in raw.items() if k!='content'},'output':output,'characters':count_text(output['body']),'valid':True,'fallback_reason':None}
  except (ValueError,OutputInvalid) as error:result={**{k:v for k,v in raw.items() if k!='content'},'valid':False,'fallback_reason':str(error) if isinstance(error,OutputInvalid) else 'output_json_invalid'}
  attempt_state='success'
 except ProviderFailure as error:
  result={**error.result,'valid':False,'fallback_reason':error.reason};attempt_state='unknown' if error.reason=='send_unknown' else 'failure'
 except PetAdminDenied as error:
  result={'valid':False,'fallback_reason':error.reason,'usage':None};attempt_state='unknown'
 async with sessions.begin() as db:
  # Cost belongs to the sent attempt even when permission/draft changed afterwards.
  await budget.finish(db,attempt_id,attempt_state,now=clock(),result=result)
  op=await db.scalar(select(PetAdminOperation).where(PetAdminOperation.id==operation_id).with_for_update())
  try:await check_permission(db,actor,'model.test','debug',commit=True)
  except PetAdminDenied as error:result={k:v for k,v in result.items() if k not in {'output'}};result.update(valid=False,fallback_reason=error.reason)
  head=await db.get(PetConfigHead,'ai');result['current_draft_matches']=bool(head and head.draft_revision==revision and fingerprint(head.draft)==content_digest)
  op.state='done';op.result={**op.result,**result};op.finished_at=utcnow()
  db.add(PetAdminAudit(operation_id=op.id,admin_id=actor['id'],actor_role=actor['role'],action=op.action,domain=op.domain,target=op.target,reason=op.reason,result=op.result))
  return operation_view(op)

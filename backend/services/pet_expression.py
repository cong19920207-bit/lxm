# coding: utf-8
"""Fact-scoped expression only. No generated field can execute a business action."""
import html,json,re
from datetime import timedelta
from string import Formatter
from sqlalchemy import select
from backend.models.pet import PetFactEvent,PetState,PetProfile,PetFormalText,PetTextSource
from backend.models.pet_generation import PetGenerationTask
from backend.services.pet_activity import owned
from backend.services.pet_user_service import runtime_flags,current_config,now_utc
from backend.services.pet_settlement import aware,iso
from backend.services.pet_persistence import _utc
from backend.services.pet_config_service import defaults

class OutputInvalid(ValueError):pass

def plain_text(value):
 if not isinstance(value,str):raise OutputInvalid('text_required')
 value=re.sub(r'!?\[([^\]]*)\]\([^)]*\)',r'\1',value)
 value=re.sub(r'<[^>]*>','',value);value=html.unescape(value)
 return re.sub(r'[\s*_`#~]','',value)

def count_text(value):return len(plain_text(value))

def render_template(template,values):
 try:
  parts=list(Formatter().parse(template))
  if any(field and (field not in values or spec or conversion) for _,field,spec,conversion in parts):raise ValueError()
  return template.format(**values)
 except (KeyError,ValueError,AttributeError):raise OutputInvalid('template_variables_missing_or_invalid')

def validate_output(output,facts,*,maximum,allowed_invitations,title_max=24):
 if not isinstance(output,dict) or set(output)-{'sentences','invitation','title'}:raise OutputInvalid('output_fields_invalid')
 sentences=output.get('sentences');known={f['id']:f for f in facts}
 if not isinstance(sentences,list) or not 1<=len(sentences)<=20:raise OutputInvalid('sentences_required')
 body=[];sources=[]
 for sentence in sentences:
  if not isinstance(sentence,dict) or set(sentence)!={'text','source_ids','participants'}:raise OutputInvalid('sentence_fields_invalid')
  ids=sentence['source_ids'];participants=sentence['participants']
  if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or x not in known for x in ids):raise OutputInvalid('unknown_fact')
  people=set().union(*(set(known[x]['participants']) for x in ids))
  if not isinstance(participants,list) or any(not isinstance(x,str) for x in participants) or set(participants)!=people:raise OutputInvalid('participants_mismatch')
  text=plain_text(sentence['text'])
  # Do not turn an attributed touch/feed into an unobserved reaction or emotion.
  if re.search(r'(摇|甩|晃).{0,3}尾',text) and not any((known[x].get('reaction') or {}).get('type')=='wag_tail' for x in ids):raise OutputInvalid('unsupported_reaction')
  if any(word in text for word in ('开心','高兴','兴奋','伤心','难过')):raise OutputInvalid('unsupported_emotion')
  if not text or any(word in text for word in ('每天一直','一直等你','你怎么才','不理它','奖励','亲近值')):raise OutputInvalid('unsupported_claim')
  if ('你' in text and 'player' not in people) or (any(word in text for word in ('我','小梦')) and 'xiaomeng' not in people):raise OutputInvalid('text_participant_mismatch')
  body.append(text);sources.extend(ids)
 text=''.join(body)
 # Never cut a negation, participant, or key result to satisfy a display limit.
 if count_text(text)>maximum:raise OutputInvalid('text_too_long')
 invitation=output.get('invitation')
 if invitation is not None and invitation not in allowed_invitations:raise OutputInvalid('invitation_not_allowed')
 title=plain_text(output.get('title',''))
 if count_text(title)>title_max:raise OutputInvalid('title_too_long')
 return {'body':text,'title':title,'source_ids':list(dict.fromkeys(sources)),'invitation':invitation}

def fact_view(f):
 return {'id':f.id,'event_type':f.event_type,'source':f.source,'participants':f.participants,'occurred_at':iso(f.occurred_at),'business_date':f.business_date.isoformat(),
  'result':{k:v for k,v in f.result.items() if k in {'completed','outcome','from_stage','to_stage','home_event','name','before_name','after_name','preparation','template'}},'reaction':f.reaction}

def workflow_config(ai,kind):return {**defaults('ai')['workflows'][kind],**ai.get('workflows',{}).get(kind,{})}

def template_for(fact,ai=None,pet_name='小狗'):
 from backend.services.pet_templates import render,TEMPLATES
 return render(ai,fact.event_type if fact.event_type in TEMPLATES else 'fallback',pet_name=pet_name,facts='',stage='',date=fact.business_date.isoformat(),participants=','.join(fact.participants))

def safe_fallback(body,maximum):
 return next((text for text in (body,'记下啦。','嗯。','') if count_text(text)<=maximum),'')

async def queue_feedback(db,pet,fact,now):
 from backend.services.pet_return import activation_uses_return
 if await activation_uses_return(db,pet,fact):return None
 if not fact.result.get('active_eligible') or not (await runtime_flags(db,now))['ai_enabled']:return None
 from backend.services.pet_generation import enqueue
 return await enqueue(db,pet.user_id,business_key='immediate:'+fact.id,kind='immediate',origin='interactive',source_ids=[fact.id],coverage_start=aware(fact.occurred_at),coverage_end=aware(fact.occurred_at),expires_at=now+timedelta(minutes=2),now=now)

async def expression_for_event(db,user_id,event_id,*,now=None):
 now=now or now_utc();pet=await owned(db,user_id)
 # The owner lock may have waited for another request to finish. Under MySQL
 # REPEATABLE READ, the earlier authentication snapshot cannot see that commit.
 # Keep the fact, generation receipt and state on the same current-read basis.
 fact=await db.scalar(select(PetFactEvent).where(PetFactEvent.id==event_id,PetFactEvent.pet_id==pet.id).with_for_update().execution_options(populate_existing=True))
 if fact is None or fact.pet_id!=pet.id:raise LookupError('event_not_found')
 t=await db.scalar(select(PetGenerationTask).where(PetGenerationTask.pet_id==pet.id,PetGenerationTask.business_key=='immediate:'+event_id).with_for_update().execution_options(populate_existing=True))
 state=await db.scalar(select(PetState).where(PetState.pet_id==pet.id).with_for_update().execution_options(populate_existing=True))
 stale=state.record_version!=fact.version_after or (t is not None and t.expires_at<=_utc(now))
 ai=t.configuration.get('ai',{}) if t and t.configuration else (await current_config(db,'ai',now)).content if await current_config(db,'ai',now) else defaults('ai')
 response={'event_id':event_id,'body':safe_fallback(template_for(fact,ai,pet.name),workflow_config(ai,'immediate')['maximum']),'source':'template','pending':bool(t and t.state in {'queued','claimed','requesting'}),'stale':stale,'fallback_reason':t.reason if t else 'template_only'}
 if t and t.state=='succeeded' and not stale:response.update({k:v for k,v in t.result.items() if k in {'body','source','fallback_reason','invitation','source_ids'}})
 return response

async def messages_for(db,t):
 pet=await db.get(PetProfile,t.pet_id);facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==t.pet_id,PetFactEvent.id.in_(t.source_ids)).order_by(PetFactEvent.occurred_at,PetFactEvent.id)))
 ai=t.configuration.get('ai',{});workflow=workflow_config(ai,t.kind);views=[fact_view(f) for f in facts]
 stats={}
 for f in facts:stats[f.event_type]=stats.get(f.event_type,0)+1
 selected=sorted(views,key=lambda f:(0 if f['event_type'] in {'natural_growth','birthday'} else 1 if f['participants']==['xiaomeng'] else 2,f['occurred_at']))[:t.configuration.get('rules',{}).get('narrative',{}).get('selected_facts',8)]
 current=[]
 if t.kind=='return':
  from backend.models.pet_return import PetReturn
  ret=await db.get(PetReturn,t.return_id)
  selected=[f for f in selected if f['id'] in ret.source_ids]
  current=[f for f in views if f['id']==ret.current_event_id]
  stats={}
  for f in views:
   if f['id'] in ret.source_ids:stats[f['event_type']]=stats.get(f['event_type'],0)+1
 context={'pet_name':pet.name,'facts':json.dumps(selected,ensure_ascii=False),'stage':(await db.get(PetState,t.pet_id)).stage,'date':aware(t.coverage_end).date().isoformat(),'participants':','.join(sorted({p for f in facts for p in f.participants}))}
 prompt=render_template(workflow['prompt'],context)
 extra=' 回访JSON顶层必须为past与current两个字段，分别使用相同sentences格式；past仅引用facts，current仅引用current_facts；没有current_facts时current为null。' if t.kind=='return' else ''
 return [{'role':'system','content':prompt+extra+' 你是小梦，只表达已确认事实，不责备缺席。返回JSON，格式示例：{"sentences":[{"text":"短句","source_ids":["事实ID"],"participants":["player"]}],"invitation":null}。每句必须引用所给事实及准确参与者；不新增动作、状态或奖励。仅描述已完成动作，reaction为空时不描写狗的回应；不推测开心、兴奋等情绪，不补写摇尾巴、靠近、叫声等未记录反应。目标'+str(workflow['target'])+'字以内，最大'+str(workflow['maximum'])+'字。'},
  {'role':'user','content':json.dumps({'profile':{'name':pet.name,'stage':context['stage']},'facts':selected,'current_facts':current,'statistics':stats,'coverage':{'start':iso(t.coverage_start),'end':iso(t.coverage_end)},'allowed_invitations':[]},ensure_ascii=False)}],views

async def write_expression(db,t,result,now):
 facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==t.pet_id,PetFactEvent.id.in_(t.source_ids))))
 workflow=workflow_config(t.configuration.get('ai',{}),t.kind)
 historical_ids=t.source_ids
 ret=None
 if t.kind=='return':
  from backend.models.pet_return import PetReturn
  ret=await db.get(PetReturn,t.return_id);historical_ids=ret.source_ids
 try:
  parsed=json.loads(result.get('content',''))
  if ret:
   if not isinstance(parsed,dict) or set(parsed)!={'past','current'}:raise OutputInvalid('return_regions_required')
   past=[fact_view(f) for f in facts if f.id in ret.source_ids]
   value=validate_output(parsed['past'],past,maximum=workflow['maximum'],title_max=workflow['title_max'],allowed_invitations=[])
   if ret.current_event_id:
    current=validate_output(parsed['current'],[fact_view(f) for f in facts if f.id==ret.current_event_id],maximum=workflow_config(t.configuration.get('ai',{}),'immediate')['maximum'],allowed_invitations=[])
   else:
    if parsed['current'] is not None:raise OutputInvalid('unexpected_current_action')
    current={'body':None,'source_ids':[]}
   value.update(past_body=value['body'],past_source_ids=value['source_ids'],current_body=current['body'],current_source_ids=current['source_ids'])
  else:value=validate_output(parsed,[fact_view(f) for f in facts],maximum=workflow['maximum'],title_max=workflow['title_max'],allowed_invitations=[])
  value.update(source='model',fallback_reason=None)
 except (ValueError,TypeError):
  value={'body':template_for(facts[-1],t.configuration.get('ai',{})) if t.kind=='immediate' else '这段时间的真实经历，已经留在记录里。','source':'template','source_ids':historical_ids,'fallback_reason':'output_invalid','invitation':None}
  if ret:value.update(past_body=value['body'],past_source_ids=ret.source_ids,current_body=template_for(next(f for f in facts if f.id==ret.current_event_id)) if ret.current_event_id else None,current_source_ids=[ret.current_event_id] if ret.current_event_id else [])
 value['body']=safe_fallback(value['body'],workflow['maximum'])
 if ret:
  value['past_body']=value['body']
  if value['current_body'] is not None:
   value['current_body']=safe_fallback(value['current_body'],workflow_config(t.configuration.get('ai',{}),'immediate')['maximum'])
 value['usage']=result.get('usage');value['returned_model']=result.get('returned_model');value['elapsed_ms']=result.get('elapsed_ms')
 if t.kind!='immediate':
  old=await db.scalar(select(PetFormalText).where(PetFormalText.pet_id==t.pet_id,PetFormalText.business_key==t.business_key).order_by(PetFormalText.version.desc()).limit(1))
  if old is None or (t.result or {}).get('regenerate'):
   text=PetFormalText(pet_id=t.pet_id,business_key=t.business_key,kind=t.kind,version=old.version+1 if old else 1,body=value['body'],coverage_start=t.coverage_start,coverage_end=t.coverage_end,config_snapshot={**t.configuration,'generation_task_id':t.id,'attempt_id':t.attempt_id,'expression':value})
   db.add(text);await db.flush()
   for source in historical_ids:db.add(PetTextSource(pet_id=t.pet_id,text_id=text.id,event_id=source))
   await db.flush();value['text_id']=text.id
  else:value['text_id']=old.id
 return value

async def run_task(sessions,task_id,*,owner,clock=now_utc,config=None,transport=None):
 from backend.services.pet_generation import claim,permit
 from backend.services.pet_llm import execute_claim,deployment_config,ModelConfigurationError
 try:config=config or deployment_config()
 except ModelConfigurationError:config=None
 c=await claim(sessions,task_id,owner=owner,now=clock(),lease_seconds=(config.timeout_seconds+30) if config else 120)
 if not c:return {'ok':False,'reason':'not_claimed'}
 async with sessions() as db:
  t=await db.get(PetGenerationTask,task_id)
  try:messages,_=await messages_for(db,t)
  except OutputInvalid:
   messages=None
 if messages is None:
  await permit(sessions,c,now=clock(),configuration_error='template_variables_missing_or_invalid');return {'ok':False,'reason':'template_invalid'}
 return await execute_claim(sessions,c,messages,config=config,transport=transport,clock=clock,writer=write_expression)

async def run_queued(sessions,*,owner,now=None,limit=5):
 async with sessions() as db:ids=list(await db.scalars(select(PetGenerationTask.id).where(PetGenerationTask.state=='queued').order_by(PetGenerationTask.expires_at).limit(limit)))
 import asyncio
 results=await asyncio.gather(*(run_task(sessions,i,owner=owner) for i in ids),return_exceptions=True)
 for task_id,result in zip(ids,results):
  if isinstance(result,BaseException):raise RuntimeError('pet_generation_task_failed:'+task_id+':'+type(result).__name__) from result
 return {'selected':len(ids),'completed':sum(isinstance(r,dict) and r.get('ok',False) for r in results)}

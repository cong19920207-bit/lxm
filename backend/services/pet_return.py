# coding: utf-8
"""Welcome is immediate; only actual participation freezes the previous interval."""
from datetime import timedelta
from sqlalchemy import select
from backend.models.pet import PetProfile,PetState,PetFactEvent,PetSnapshot,PetFormalText,PetTextSource
from backend.models.pet_return import PetReturn
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_budget import PetRequestAttempt
from backend.services.pet_activity import owned,activity_for,ensure_absence
from backend.services.pet_user_service import now_utc,current_config,runtime_flags,profile_view
from backend.services.pet_settlement import settle_pet,aware,iso
from backend.services.pet_persistence import _utc

LABELS={'natural_growth':'它又长大了一点','feed':'一次实际进食','touch':'一次轻柔的陪伴','play':'追过一次小球','joint_ball':'一起玩过球','joint_photo':'一起留下的照片','birthday':'游戏内生日纪念'}
def priority(f):
 return 0 if f.event_type=='natural_growth' else 1 if f.participants==['xiaomeng'] else 2 if f.event_type in {'joint_photo','joint_ball'} else 3

def is_highlight(f):return f.event_type=='natural_growth' or (f.source=='actual_execution' and (f.participants==['xiaomeng'] or f.event_type in {'joint_ball','joint_photo'}))

async def candidate(db,pet,absence,now,*,refresh=False,exclude_id=None):
 r=await db.scalar(select(PetReturn).where(PetReturn.absence_id==absence.id).with_for_update())
 if r and (r.confirmed_at or not refresh):return r
 if r is None:
  r=PetReturn(pet_id=pet.id,absence_id=absence.id,coverage_start=absence.started_at,coverage_end=_utc(now),version=1,source_ids=[],growth_ids=[],highlights=[]);db.add(r)
 else:r.version+=1;r.coverage_end=_utc(now)
 old_snapshot=await db.scalar(select(PetSnapshot).where(PetSnapshot.pet_id==pet.id,PetSnapshot.captured_at<=absence.started_at).order_by(PetSnapshot.captured_at.desc()).limit(1))
 r.last_snapshot_id=old_snapshot.id if old_snapshot else None
 # Settlement retains actual recording time and its explicit rule source.
 await settle_pet(db,pet.id,pet.user_id,until=now)
 facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.occurred_at>absence.started_at,PetFactEvent.occurred_at<=_utc(now),PetFactEvent.event_type!='system_settlement').order_by(PetFactEvent.occurred_at,PetFactEvent.id)))
 facts=[f for f in facts if f.id!=exclude_id and (f.occurred_at<_utc(now) or f.event_type=='natural_growth')]
 r.source_ids=[f.id for f in facts];r.growth_ids=[f.id for f in facts if f.event_type=='natural_growth']
 rules=await current_config(db,'rules',now);maximum=rules.content.get('return',{}).get('highlights',3)
 selected=sorted([f for f in facts if is_highlight(f)],key=lambda f:(priority(f),-f.occurred_at.timestamp(),f.id))[:maximum]
 r.highlights=[{'event_id':f.id,'event_type':f.event_type,'title':LABELS.get(f.event_type,'已经发生的日常'),'source':f.source,'participants':f.participants,'occurred_at':iso(f.occurred_at),'recorded_at':iso(f.recorded_at)} for f in selected]
 await db.flush();return r

async def present(db,r,*,show_intro=False,now=None):
 t=await db.get(PetGenerationTask,r.task_id) if r.task_id else None
 text=await db.get(PetFormalText,r.reused_text_id) if r.reused_text_id else None
 from backend.services.pet_admin_text import visible
 text=await visible(db,text)
 value={'id':r.id,'absence_id':r.absence_id,'version':r.version,'coverage_start':iso(r.coverage_start),'coverage_end':iso(r.coverage_end),'confirmed':r.confirmed_at is not None,
  'show_intro':show_intro,'welcome':'回来啦，来看看它。','highlights':r.highlights,'past_source_ids':r.source_ids,'growth_source_ids':r.growth_ids,'current_source_ids':[r.current_event_id] if r.current_event_id else [],
  'past_body':text.body if text else '这段时间的真实经历，已经留在记录里。' if r.source_ids else '回来陪陪它就好。','current_body':None,'pending':bool(t and t.state in {'queued','claimed','requesting'}),'reason':r.reason or (t.reason if t else None),'source':'existing' if text else 'template'}
 if not text:
  from backend.services.pet_expression import workflow_config,safe_fallback
  ai=(t.configuration or {}).get('ai') if t else None
  if ai is None:
   published=await current_config(db,'ai',now or now_utc());ai=published.content if published else {}
  from backend.services.pet_templates import render
  pet=await db.get(PetProfile,r.pet_id)
  values={'pet_name':pet.name,'date':aware(now or now_utc()).date().isoformat(),'stage':'','facts':'','participants':''}
  value['welcome']=render(ai,'return_welcome',**values)
  value['past_body']=safe_fallback(render(ai,'return_facts' if r.source_ids else 'return_empty',**values),workflow_config(ai,'return')['maximum'])
 if t and t.state=='succeeded':
  value.update({k:v for k,v in t.result.items() if k in {'past_body','current_body','past_source_ids','current_source_ids','source','fallback_reason'}})
 if t and t.state=='succeeded' and t.result.get('text_id'):
  saved=await visible(db,await db.get(PetFormalText,t.result['text_id']))
  if saved:value['past_body']=saved.body;value['text_id']=saved.id
  else:value['past_body']='这段时间的真实经历，已经留在记录里。';value['source']='template';value['fallback_reason']='text_hidden'
 return value

async def enter(db,user_id,*,now=None):
 now=now or now_utc();pet=await owned(db,user_id);a=await activity_for(db,pet);absence=await ensure_absence(db,pet,now)
 if absence is None:
  r=await db.scalar(select(PetReturn).where(PetReturn.absence_id==a.previous_absence_id)) if a.previous_absence_id else None
  return await present(db,r,now=now) if r else None
 r=await candidate(db,pet,absence,now,refresh=True)
 show=r.presented_at is None
 if show:r.presented_at=_utc(now)
 result=await present(db,r,show_intro=show,now=now);result['pet']=await profile_view(db,pet,now);return result

async def confirm_before_activity(db,pet,absence,now,source_event=None):
 r=await candidate(db,pet,absence,now,exclude_id=source_event.id if source_event else None)
 if r.confirmed_at:return r
 r.confirmed_at=_utc(now);r.current_event_id=source_event.id if source_event else None
 # Revoke unsent summaries. Sent/unknown usage stays; their content cannot replace this return.
 from backend.services.pet_generation import stop_attempt,enqueue
 old=list(await db.scalars(select(PetGenerationTask).where(PetGenerationTask.pet_id==pet.id,PetGenerationTask.absence_id==absence.id,PetGenerationTask.origin=='offline',PetGenerationTask.state.in_(['queued','claimed','requesting','retryable_failed'])).with_for_update()))
 for t in old:
  await stop_attempt(db,t,now);t.state='superseded';t.reason='return_superseded';t.generation+=1
 # An already persisted narrative covering the same source set is reusable without a request.
 texts=list(await db.scalars(select(PetFormalText).where(PetFormalText.pet_id==pet.id).order_by(PetFormalText.recorded_at.desc())))
 from backend.services.pet_admin_text import visible
 seen_texts=set()
 for text in texts:
  text=await visible(db,text)
  if text is None or text.id in seen_texts:continue
  seen_texts.add(text.id)
  sources=set(await db.scalars(select(PetTextSource.event_id).where(PetTextSource.text_id==text.id)))
  if r.source_ids and set(r.source_ids)<=sources:r.reused_text_id=text.id;r.reason='existing_coverage';return r
 rules=await current_config(db,'rules',now);cost=rules.content['costs']
 if not r.source_ids:r.reason='no_new_facts';return r
 if (r.coverage_end-r.coverage_start).total_seconds()<cost['return_min_hours']*3600:r.reason='absence_too_short';return r
 if not (await runtime_flags(db,now))['ai_enabled']:r.reason='ai_disabled';return r
 recent=await db.scalar(select(PetRequestAttempt).where(PetRequestAttempt.user_id==pet.user_id,PetRequestAttempt.origin=='return',PetRequestAttempt.sent_at.is_not(None)).order_by(PetRequestAttempt.sent_at.desc()).limit(1).with_for_update())
 if recent and (_utc(now)-recent.sent_at).total_seconds()<cost['return_cooldown_hours']*3600:r.reason='return_cooldown';return r
 ids=r.source_ids+([source_event.id] if source_event else [])
 t=await enqueue(db,pet.user_id,business_key='return:'+r.id,kind='return',origin='return',source_ids=ids,coverage_start=aware(r.coverage_start),coverage_end=aware(r.coverage_end),expires_at=now+timedelta(minutes=10),absence_id=absence.id,return_id=r.id,now=now)
 r.task_id=t.id;r.reason=None;await db.flush();return r

async def activation_uses_return(db,pet,fact):
 r=await db.scalar(select(PetReturn).where(PetReturn.pet_id==pet.id,PetReturn.current_event_id==fact.id))
 if r is None:return False
 rules=await current_config(db,'rules',aware(fact.occurred_at))
 return (r.coverage_end-r.coverage_start).total_seconds()>=rules.content['costs']['return_min_hours']*3600

async def read_return(db,user_id,return_id):
 pet=await owned(db,user_id);r=await db.get(PetReturn,return_id)
 if r is None or r.pet_id!=pet.id:raise LookupError('return_not_found')
 return await present(db,r)

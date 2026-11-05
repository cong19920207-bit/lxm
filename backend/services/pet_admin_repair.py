"""Rebuild only from retained initial evidence, ordered facts and original rule snapshots."""
from copy import deepcopy
from datetime import date,datetime
from sqlalchemy import select
from fastapi import HTTPException
from backend.models.pet import PetProfile,PetState,PetFactEvent,PetSnapshot,PetRuleSnapshot,utcnow
from backend.services.pet_admin_security import check_permission,prepare_operation,execute_operation
from backend.services.pet_admin_read import serialize
from backend.services.pet_config_service import fingerprint,ConfigConflict,ConfigInvalid
from backend.services.pet_settlement import aware,age_days,stage_for_age,STAGES,iso
from backend.services.pet_preferences import SUPPORTED

async def preview(db,actor,pet_id,*,birth_date=None,now=None):
 await check_permission(db,actor,'audit.read','repair');now=aware(now or utcnow())
 pet=await db.get(PetProfile,pet_id);state=await db.get(PetState,pet_id)
 if not pet or not state:raise HTTPException(404,detail='pet_or_state_missing')
 facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet_id).order_by(PetFactEvent.version_after)))
 initial=await db.scalar(select(PetSnapshot).where(PetSnapshot.pet_id==pet_id,PetSnapshot.kind=='adoption'))
 rules={x.id:x for x in await db.scalars(select(PetRuleSnapshot).where(PetRuleSnapshot.id.in_({pet.growth_rule_id,*[f.rule_snapshot_id for f in facts],*[s.get('snapshot_id') for f in facts for s in f.result.get('segments',[])]})))}
 blocked=[]
 if initial is None:blocked.append('initial_snapshot_missing')
 if not facts or facts[0].event_type!='adopted':blocked.append('adoption_fact_missing')
 if pet.growth_rule_id not in rules:blocked.append('growth_snapshot_missing')
 expected=1;values=deepcopy(initial.state.get('values')) if initial else None;total=0;stage='puppy';unlocked=[];discoveries={};evidence={};settled=pet.adopted_at
 for f in facts:
  if f.version_before!=expected:blocked.append('fact_sequence_missing:'+str(expected))
  expected=f.version_after;basis=rules.get(f.rule_snapshot_id)
  if not basis:blocked.append('rule_snapshot_missing:'+f.rule_snapshot_id);continue
  c=basis.content
  if f.event_type=='adopted':
   if initial and initial.source_event_id!=f.id:blocked.append('initial_fact_mismatch')
   if 'rewards' not in c:blocked.append('adoption_rule_incomplete');continue
   total=c['rewards']['initial_closeness'];values=deepcopy(f.state_after)
  elif f.event_type=='system_settlement':
   for segment in f.result.get('segments',[]):
    original=rules.get(segment.get('snapshot_id'))
    if not original:blocked.append('state_segment_missing:'+str(segment.get('snapshot_id')))
   settled=f.occurred_at;stage=f.result['stage_after']
  elif f.event_type=='natural_growth':stage=f.result['stage']
  if f.source=='admin_correction' and f.event_type=='state_repair':
   total=f.result['rebuilt']['closeness'];unlocked=list(f.result['rebuilt']['unlocked_behaviors']);discoveries=deepcopy(f.result['rebuilt']['preference_discoveries']);stage=f.result['rebuilt']['stage']
  else:
   total+=f.closeness_delta
   if f.source=='actual_execution' and 'player' in f.participants and f.result.get('completed'):
    for unlock in c.get('rewards',{}).get('unlocks',[]):
     if total>=unlock['closeness'] and (not(unlock['adult_required'] or unlock['adult_participation_required']) or stage=='adult') and unlock['key'] not in unlocked:unlocked.append(unlock['key'])
    pref=c.get('preferences',{});reaction=f.reaction or {};rule=SUPPORTED.get(pref.get('reaction_type'))
    if rule and pref.get('discovery_enabled'):
     key,value,actions=rule
     if f.event_type in actions and reaction.get('type')==pref['reaction_type'] and reaction.get('outcome')=='responded' and reaction.get('scene') in STAGES:
      evidence.setdefault(key,[]).append(f.id)
      if key not in discoveries and len(evidence[key])>=pref['evidence_required'] and pet.stable_preferences.get(key)==value:discoveries[key]={'value':value,'event_ids':list(evidence[key]),'rule_snapshot_id':f.rule_snapshot_id,'required':pref['evidence_required'],'confirmed_at':iso(f.occurred_at)}
  values=deepcopy(f.state_after)
 if expected!=state.record_version:blocked.append('projection_fact_cutoff_mismatch')
 proposed_birth=date.fromisoformat(birth_date) if birth_date else pet.birth_date
 if proposed_birth>=now.date() or proposed_birth>aware(pet.adopted_at).date():blocked.append('birth_date_invalid')
 if total<0:blocked.append('negative_rebuilt_closeness')
 desired=stage_for_age(age_days(proposed_birth,now),rules[pet.growth_rule_id].content) if pet.growth_rule_id in rules else stage
 proposed_stage=STAGES[max(STAGES.index(stage),STAGES.index(desired))]
 # Never silently regress an already displayed form. History and earned nodes remain intact.
 retained_stage=STAGES[max(STAGES.index(proposed_stage),STAGES.index(state.stage))]
 rebuilt={'values':values,'closeness':total,'stage':retained_stage,'unlocked_behaviors':unlocked,'preference_discoveries':discoveries,'birth_date':proposed_birth.isoformat(),'settled_at':settled.isoformat()}
 current={'values':state.values,'closeness':state.closeness,'stage':state.stage,'unlocked_behaviors':state.unlocked_behaviors,'preference_discoveries':pet.preference_discoveries,'birth_date':pet.birth_date.isoformat(),'settled_at':state.settled_at.isoformat()}
 basis={'state':serialize(state,'super_admin'),'proposed':rebuilt,'pet_data_version':pet.data_version,'record_version':state.record_version,'current':current,'stable_preferences':pet.stable_preferences,'fact_ids':[f.id for f in facts],'facts':[{**serialize(f,'super_admin')} for f in facts],'initial':serialize(initial,'super_admin') if initial else None,'rules':{k:fingerprint(v.content) for k,v in rules.items()}}
 return {'pet_id':pet_id,'data_version':pet.data_version,'record_version':state.record_version,'basis_digest':fingerprint(basis),'initial_snapshot_id':initial.id if initial else None,'fact_ids':[f.id for f in facts],'rule_ids':list(rules),'fact_cutoff':facts[-1].recorded_at.isoformat() if facts else None,'current':current,'rebuilt':rebuilt,'birth_date':birth_date,'blocked':sorted(set(blocked)),'stage_warning':'retains_previously_displayed_stage' if retained_stage!=desired else None,'birthday_event_ids':[f.id for f in facts if f.event_type=='birthday'],'growth_event_ids':[f.id for f in facts if f.event_type=='natural_growth'],'effect':'no reward, no model, no activity, no budget reset, no historical rewrite'}

async def repair(sessions,actor,*,pet_id,operation_id,reason,basis_digest,birth_date=None,now=None):
 now=aware(now or utcnow())
 await prepare_operation(sessions,actor,operation_id=operation_id,action='state.repair',domain='repair',target=pet_id,reason=reason,payload={'basis_digest':basis_digest,'birth_date':birth_date})
 async def work(db,op):
  from backend.services.pet_user_service import lock_owner
  pet=await db.get(PetProfile,pet_id)
  if not pet:raise LookupError('pet_not_found')
  await lock_owner(db,pet.user_id)
  pet=await db.scalar(select(PetProfile).where(PetProfile.id==pet_id).with_for_update().execution_options(populate_existing=True))
  state=await db.scalar(select(PetState).where(PetState.pet_id==pet_id).with_for_update().execution_options(populate_existing=True))
  p=await preview(db,actor,pet_id,birth_date=birth_date,now=now)
  if p['basis_digest']!=basis_digest:raise ConfigConflict('repair_preview_changed')
  if p['blocked']:raise ConfigInvalid('repair_basis_missing:'+','.join(p['blocked']))
  from backend.services.pet_lifecycle import invalidate_account
  await invalidate_account(db,pet.user_id,reason='admin_repair',now=now)
  pet.birth_date=date.fromisoformat(p['rebuilt']['birth_date']);pet.preference_discoveries=p['rebuilt']['preference_discoveries']
  from backend.services.pet_persistence import append_fact,FactCommand
  state.closeness=p['rebuilt']['closeness'];await db.flush()
  fact=await append_fact(db,FactCommand(pet_id=pet_id,user_id=pet.user_id,request_key='repair:'+operation_id,business_key='repair:'+operation_id,expected_version=state.record_version,event_type='state_repair',source='admin_correction',participants=(),occurred_at=now,result={'operation_id':operation_id,'before':p['current'],'rebuilt':p['rebuilt'],'basis_digest':basis_digest,'source_ids':p['fact_ids'],'birth_date_before':p['current']['birth_date'],'birth_date_after':p['rebuilt']['birth_date']},state_after=p['rebuilt']['values'],closeness_delta=0,settled_until=aware(datetime.fromisoformat(p['rebuilt']['settled_at'])),rule_snapshot_id=pet.growth_rule_id,stage_after=p['rebuilt']['stage'],unlocked_after=tuple(p['rebuilt']['unlocked_behaviors'])))
  await db.refresh(state)
  return {'pet_id':pet_id,'event_id':fact.id,'data_version':pet.data_version,'record_version':state.record_version,'before':p['current'],'after':p['rebuilt'],'stage_warning':p['stage_warning']}
 return await execute_operation(sessions,actor,operation_id,work)

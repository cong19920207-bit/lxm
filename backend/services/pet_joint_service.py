"""Finite shared-event instances. Invitations and animation are never completion."""
from datetime import timedelta,datetime
from sqlalchemy import select,func,cast,String
from backend.models.pet import PetRuleSnapshot
from backend.models.pet_config import PetConfigVersion,PetResource
from backend.models.pet_interaction import PetInteraction
from backend.services.pet_interactions import context,get_attempt,response
from backend.services.pet_user_service import now_utc,stable_key,current_config,runtime_flags,PetInputError,PetConflict,PetDisabled,PetUnavailable,BUSINESS_ZONE
from backend.services.pet_persistence import FactCommand,append_fact,_utc
from backend.services.pet_rewards import complete_participation
from backend.services.pet_settlement import settle_pet,iso
from backend.services.pet_scene_resources import verify_resource
from backend.services.pet_action_capabilities import joint_reason

IMPLEMENTED_STEPS=('player_pass','xiaomeng_receive','dog_response')

async def require_scene(db,state,resources_ready=True):
    if resources_ready is not True:raise PetUnavailable('scene_not_ready')
    appearance=await db.get(PetRuleSnapshot,state.appearance_rule_id)
    if appearance is None:raise PetUnavailable('appearance_missing')
    for key in [appearance.content['stages'][state.stage],appearance.content['fallback']]:
        resource=await db.get(PetResource,key)
        if not resource or not resource.available:raise PetUnavailable('resource_unavailable')
        try:verify_resource(resource)
        except ValueError:raise PetUnavailable('resource_integrity_error')
    return appearance

async def clear_expired(db,state,now):
    if not state.active_activity:return
    active=await db.get(PetInteraction,state.active_activity['id'])
    if active and active.state=='pending' and active.expires_at>_utc(now):raise PetConflict('pet_busy')
    if active and active.state=='pending':active.state='expired';active.result={'completed':False,'reason':'timeout'}
    state.active_activity=None

def end(attempt,state,status,reason):
    attempt.state=status;attempt.result={'completed':False,'reason':reason,'active_eligible':False}
    if state.active_activity and state.active_activity.get('id')==attempt.id:state.active_activity=None

async def valid_running(db,pet,state,attempt,now):
    if attempt.state!='pending':return False
    if attempt.expires_at<=_utc(now):end(attempt,state,'expired','timeout');return False
    if attempt.pet_data_version!=pet.data_version:end(attempt,state,'obsolete','pet_version_changed');return False
    if not (await runtime_flags(db,now))['interactions_enabled']:end(attempt,state,'blocked','interactions_disabled');return False
    await require_scene(db,state)
    return True

async def invitation_elapsed(db,pet_id,now):
    original_time=func.coalesce(PetInteraction.payload['invited_at'].as_string(),func.replace(cast(PetInteraction.started_at,String),' ','T').concat('+00:00'))
    recent=await db.scalar(select(PetInteraction).where(PetInteraction.pet_id==pet_id,PetInteraction.kind=='joint_ball',func.coalesce(PetInteraction.payload['initiator'].as_string(),PetInteraction.payload['entry'].as_string(),'invitation')=='invitation').order_by(original_time.desc()).limit(1))
    if not recent:return float('inf')
    stamp=datetime.fromisoformat(recent.payload['invited_at']) if recent.payload.get('invited_at') else recent.started_at
    return (_utc(now)-_utc(stamp)).total_seconds()

async def invite(db,user_id,*,request_key,direct=False,initiator='user',now=None):
    now=now or now_utc();stable_key(request_key);pet,state=await context(db,user_id)
    previous=await db.scalar(select(PetInteraction).where(PetInteraction.pet_id==pet.id,PetInteraction.request_key==request_key))
    if previous:
        if previous.kind!='joint_ball' or previous.payload.get('requested_direct',False)!=direct or previous.payload.get('initiator','user')!=initiator:raise PetConflict('request_content_changed')
        return await response(db,previous,pet,state)
    rules=await current_config(db,'rules',now)
    if not rules.content['joint']['enabled'] or not (await runtime_flags(db,now))['interactions_enabled']:raise PetDisabled('joint_disabled')
    await clear_expired(db,state,now)
    if initiator not in {'user','invitation'}:raise PetInputError('event_entry_not_implemented')
    entry='user' if direct or rules.content['joint'].get('entry')=='user' else 'invitation'
    elapsed=await invitation_elapsed(db,pet.id,now)
    why=joint_reason(rules.content,state.values,stage=state.stage,origin=initiator,invite_elapsed=elapsed)
    if why:raise PetInputError(why)
    attempt=PetInteraction(pet_id=pet.id,request_key=request_key,kind='joint_ball',state='invited',config_id=rules.id,pet_data_version=pet.data_version,
        started_at=_utc(now),expires_at=_utc(now)+timedelta(seconds=rules.content['joint']['timeout_seconds']),payload={'steps':list(rules.content['joint']['steps']),'progress':0,'entry':entry,'requested_direct':direct,'initiator':initiator,'invited_at':iso(now)})
    db.add(attempt);await db.flush();return await response(db,attempt,pet,state)

async def accept(db,user_id,attempt_id,*,resources_ready,now=None):
    now=now or now_utc();pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    if attempt.kind!='joint_ball':raise PetInputError('not_joint_ball')
    if attempt.state!='invited':return await response(db,attempt,pet,state)
    if attempt.expires_at<=_utc(now):end(attempt,state,'expired','invite_expired');return await response(db,attempt,pet,state)
    if not (await runtime_flags(db,now))['interactions_enabled']:raise PetDisabled('interactions_disabled')
    current=await current_config(db,'rules',now)
    if not current.content['joint']['enabled']:raise PetDisabled('joint_disabled')
    await clear_expired(db,state,now);await settle_pet(db,pet.id,user_id,until=now);await require_scene(db,state,resources_ready)
    # Acceptance starts a new running instance against the then-current full rules.
    why=joint_reason(current.content,state.values,stage=state.stage)
    if why:raise PetInputError(why)
    attempt.config_id=current.id;attempt.pet_data_version=pet.data_version
    from backend.services.pet_templates import render
    ai=await current_config(db,'ai',now)
    body=render(ai.content if ai else {},'joint_ball',pet_name=pet.name,date=now.astimezone(BUSINESS_ZONE).date().isoformat(),stage=state.stage,facts='',participants='player,xiaomeng')
    attempt.payload={**{k:attempt.payload[k] for k in ('entry','requested_direct','initiator','invited_at') if k in attempt.payload},'steps':list(current.content['joint']['steps']),'progress':0,'event_definition_id':current.content['joint'].get('event_id','shared-ball-01'),'display_template':'joint_ball','display_body':body,'copy_config_id':ai.id if ai else None};attempt.state='pending'
    attempt.started_at=_utc(now);attempt.expires_at=_utc(now)+timedelta(seconds=current.content['joint']['timeout_seconds'])
    state.active_activity={'id':attempt.id,'kind':attempt.kind};await db.flush();return await response(db,attempt,pet,state)

async def player_pass(db,user_id,attempt_id,*,now=None):
    now=now or now_utc();pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    if attempt.kind!='joint_ball':raise PetInputError('not_joint_ball')
    if not await valid_running(db,pet,state,attempt,now):return await response(db,attempt,pet,state)
    if attempt.payload.get('player_event_id'):return await response(db,attempt,pet,state)
    rules=await db.get(PetConfigVersion,attempt.config_id)
    fact=await append_fact(db,FactCommand(pet_id=pet.id,user_id=user_id,request_key='joint-player:'+attempt.id,business_key='joint-player:'+attempt.id,
        expected_version=state.record_version,event_type='joint_player_pass',source='actual_execution',participants=('player',),occurred_at=now,
        result={'completed':True,'active_eligible':True,'parent_id':attempt.id,'reward_family':'joint:'+attempt.id,'name':pet.name},state_after=state.values,
        closeness_delta=0,rule_snapshot_id=rules.snapshot_id,display_surfaces=('daily',)))
    attempt.payload={**attempt.payload,'progress':1,'player_event_id':fact.id};await db.flush();return await response(db,attempt,pet,state)

async def resolve(db,user_id,attempt_id,*,now=None):
    now=now or now_utc();pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    if attempt.kind!='joint_ball':raise PetInputError('not_joint_ball')
    if not await valid_running(db,pet,state,attempt,now):return await response(db,attempt,pet,state)
    if not attempt.payload.get('player_event_id'):raise PetInputError('player_step_required')
    rules=await db.get(PetConfigVersion,attempt.config_id)
    await settle_pet(db,pet.id,user_id,until=now)
    if state.values['energy']<rules.content['joint']['min_energy']:
        end(attempt,state,'refused','low_energy');return await response(db,attempt,pet,state)
    relay=await append_fact(db,FactCommand(pet_id=pet.id,user_id=user_id,request_key='joint-relay:'+attempt.id,business_key='joint-relay:'+attempt.id,
        expected_version=state.record_version,event_type='joint_xiaomeng_receive',source='actual_execution',participants=('xiaomeng',),occurred_at=now,
        result={'completed':True,'active_eligible':False,'parent_id':attempt.id,'player_event_id':attempt.payload['player_event_id']},state_after=state.values,
        closeness_delta=0,rule_snapshot_id=rules.snapshot_id,display_surfaces=('daily',)))
    values=dict(state.values);values['energy']=max(rules.content['state']['minimum']['energy'],values['energy']-rules.content['interaction']['play_cost']);values['mood']=min(rules.content['state']['maximum']['mood'],values['mood']+rules.content['interaction']['play_mood_gain'])
    fact=await complete_participation(db,pet,state,rules,action='joint_ball',request_key='joint:'+attempt.id,business_key='joint:'+attempt.id,
        parent_key='joint:'+attempt.id,now=now,state_after=values,participants=('player','xiaomeng'),
        result={'name':pet.name,'display_body':attempt.payload.get('display_body'),'copy_config_id':attempt.payload.get('copy_config_id'),'player_event_id':attempt.payload['player_event_id'],'xiaomeng_event_id':relay.id,'steps':attempt.payload['steps']},
        reaction={'type':'chased_ball','scene':state.stage,'outcome':'responded'},display_surfaces=('daily','album'))
    attempt.payload={**attempt.payload,'progress':3,'xiaomeng_event_id':relay.id};attempt.state='done';attempt.event_id=fact.id;attempt.result={**fact.result,'reaction':fact.reaction};state.active_activity=None
    await db.flush();return await response(db,attempt,pet,state)

async def cancel(db,user_id,attempt_id,*,now=None):
    pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    if attempt.kind!='joint_ball':raise PetInputError('not_joint_ball')
    if attempt.state in {'invited','pending'}:end(attempt,state,'cancelled','user_cancelled')
    await db.flush();return await response(db,attempt,pet,state)

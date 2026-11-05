"""Durable, idempotent action execution with server time and owner locking."""
from datetime import timedelta
from sqlalchemy import select
from backend.models.pet import PetState, PetFactEvent
from backend.models.pet_interaction import PetInteraction
from backend.models.pet_config import PetConfigVersion
from backend.services.pet_user_service import (now_utc,lock_owner,owner_pet,current_config,runtime_flags,stable_key,PetInputError,PetConflict,PetDisabled,profile_view)
from backend.services.pet_settlement import settle_pet,iso
from backend.services.pet_persistence import _utc, FactCommand, append_fact
from backend.services.pet_rewards import complete_participation

KINDS={'touch','play'}

async def context(db,user_id):
    await lock_owner(db,user_id);pet=await owner_pet(db,user_id,lock=True)
    if pet is None:raise LookupError('pet_not_found')
    state=await db.scalar(select(PetState).where(PetState.pet_id==pet.id).with_for_update().execution_options(populate_existing=True))
    return pet,state

async def response(db,attempt,pet,state):
    from backend.services.pet_expression import expression_for_event
    expression=await expression_for_event(db,pet.user_id,attempt.event_id) if attempt.event_id and attempt.state=='done' else None
    return {'id':attempt.id,'kind':attempt.kind,'state':attempt.state,'event_id':attempt.event_id,'result':attempt.result,'expression':expression,
        'started_at':iso(attempt.started_at),'expires_at':iso(attempt.expires_at),'payload':attempt.payload,
        'pet':await profile_view(db,pet,now_utc())}

async def start(db,user_id,*,kind,request_key,now=None):
    now=now or now_utc();stable_key(request_key)
    if kind not in KINDS:raise PetInputError('unsupported_interaction')
    pet,state=await context(db,user_id)
    old=await db.scalar(select(PetInteraction).where(PetInteraction.pet_id==pet.id,PetInteraction.request_key==request_key).with_for_update())
    if old:
        if old.kind!=kind:raise PetConflict('request_content_changed')
        return await response(db,old,pet,state)
    if not (await runtime_flags(db,now))['interactions_enabled']:raise PetDisabled('interactions_disabled')
    if state.active_activity:
        active=await db.get(PetInteraction,state.active_activity['id'])
        if active and active.state=='pending' and active.expires_at>_utc(now):raise PetConflict('pet_busy')
        if active and active.state=='pending':active.state='expired';active.result={'reason':'timeout'}
        state.active_activity=None
    await settle_pet(db,pet.id,user_id,until=now)
    rules=await current_config(db,'rules',now)
    attempt=PetInteraction(pet_id=pet.id,request_key=request_key,kind=kind,config_id=rules.id,pet_data_version=pet.data_version,
        started_at=_utc(now),expires_at=_utc(now)+timedelta(seconds=60),payload={'minimum_seconds':rules.content['interaction']['play_round_seconds' if kind=='play' else 'touch_min_seconds'],'merge_seconds':rules.content['interaction']['touch_merge_seconds']})
    db.add(attempt);await db.flush()
    from backend.services.pet_rule_decisions import action_reason
    if kind=='play' and action_reason(rules.content,state.values,kind)=='low_energy':
        attempt.state='refused';attempt.result={'completed':False,'reason':'low_energy','alternative':'touch','active_eligible':False}
    else:state.active_activity={'id':attempt.id,'kind':kind}
    await db.flush()
    return await response(db,attempt,pet,state)

async def get_attempt(db,pet,attempt_id):
    attempt=await db.scalar(select(PetInteraction).where(PetInteraction.id==attempt_id,PetInteraction.pet_id==pet.id).with_for_update())
    if attempt is None:raise LookupError('interaction_not_found')
    return attempt

async def query(db,user_id,attempt_id):
    pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    return await response(db,attempt,pet,state)

async def query_request(db,user_id,request_key):
    pet,state=await context(db,user_id)
    attempt=await db.scalar(select(PetInteraction).where(PetInteraction.pet_id==pet.id,PetInteraction.request_key==request_key))
    return await response(db,attempt,pet,state) if attempt else None

async def finish(db,user_id,attempt_id,*,evidence=None,cancel=False,now=None):
    now=now or now_utc();pet,state=await context(db,user_id);attempt=await get_attempt(db,pet,attempt_id)
    if attempt.kind not in KINDS:raise PetInputError('wrong_completion_endpoint')
    if attempt.state!='pending':return await response(db,attempt,pet,state)
    def end(status,reason):
        attempt.state=status;attempt.result={'completed':False,'reason':reason,'active_eligible':False}
        if state.active_activity and state.active_activity.get('id')==attempt.id:state.active_activity=None
    if cancel:end('cancelled','user_cancelled')
    elif attempt.expires_at<=_utc(now):end('expired','timeout')
    elif attempt.pet_data_version!=pet.data_version:end('obsolete','pet_version_changed')
    elif not (await runtime_flags(db,now))['interactions_enabled']:end('blocked','interactions_disabled')
    else:
        rules=await db.get(PetConfigVersion,attempt.config_id);evidence=evidence or {}
        duration=evidence.get('duration_ms',0)
        minimum=rules.content['interaction']['play_round_seconds' if attempt.kind=='play' else 'touch_min_seconds']
        valid=isinstance(duration,(int,float)) and not isinstance(duration,bool) and duration>=minimum*1000
        valid=valid and (_utc(now)-attempt.started_at).total_seconds()>=minimum
        valid=valid and evidence.get('region')==('toy' if attempt.kind=='play' else 'body') and (evidence.get('moved') is True or evidence.get('auxiliary') is True)
        if not valid:end('incomplete',attempt.kind+'_incomplete')
        else:
            await settle_pet(db,pet.id,user_id,until=now)
            values=dict(state.values)
            if attempt.kind=='play' and values['energy']<rules.content['interaction']['play_energy_min']:
                end('refused','low_energy');attempt.result={**attempt.result,'alternative':'touch'}
            else:
                if attempt.kind=='play':
                    values['energy']=max(rules.content['state']['minimum']['energy'],values['energy']-rules.content['interaction']['play_cost'])
                    values['mood']=min(rules.content['state']['maximum']['mood'],values['mood']+rules.content['interaction']['play_mood_gain'])
                fact=await complete_participation(db,pet,state,rules,action=attempt.kind,request_key='interaction:'+attempt.id,business_key='interaction:'+attempt.id,
                    now=now,state_after=values,result={'interaction_id':attempt.id},reaction={'type':'chased_ball' if attempt.kind=='play' else 'lean_towards_hand','scene':state.stage,'outcome':'responded'})
                attempt.state='done';attempt.event_id=fact.id;attempt.result={**fact.result,'reaction':fact.reaction};state.active_activity=None
    await db.flush();return await response(db,attempt,pet,state)


async def feed(db,user_id,*,request_key,actor='player',now=None,target=None):
    """One shared food rule for the player and internal limited-care executor."""
    now=now or now_utc();stable_key(request_key)
    if actor not in {'player','xiaomeng'}:raise PetInputError('invalid_actor')
    pet,state=await context(db,user_id)
    old=await db.scalar(select(PetInteraction).where(PetInteraction.pet_id==pet.id,PetInteraction.request_key==request_key).with_for_update())
    if old:
        if old.kind!='feed' or old.payload.get('actor')!=actor:raise PetConflict('request_content_changed')
        return await response(db,old,pet,state)
    flags=await runtime_flags(db,now)
    if not flags['interactions_enabled' if actor=='player' else 'care_enabled']:raise PetDisabled('feeding_disabled')
    if state.active_activity:
        active=await db.get(PetInteraction,state.active_activity['id'])
        if active and active.state=='pending' and active.expires_at>_utc(now):raise PetConflict('pet_busy')
        state.active_activity=None
    await settle_pet(db,pet.id,user_id,until=now);rules=await current_config(db,'rules',now)
    attempt=PetInteraction(pet_id=pet.id,request_key=request_key,kind='feed',config_id=rules.id,pet_data_version=pet.data_version,
        started_at=_utc(now),expires_at=_utc(now),payload={'actor':actor})
    db.add(attempt);await db.flush()
    from backend.services.pet_rule_decisions import action_reason
    if action_reason(rules.content,state.values,'feed')=='already_full':
        fact=await append_fact(db,FactCommand(pet_id=pet.id,user_id=user_id,request_key='interaction:'+attempt.id,business_key='interaction:'+attempt.id,
            expected_version=state.record_version,event_type='feed_refused',source='actual_execution',participants=(actor,),occurred_at=now,
            result={'completed':False,'reason':'already_full','active_eligible':False},state_after=state.values,closeness_delta=0,rule_snapshot_id=rules.snapshot_id))
        attempt.state='refused';attempt.result=fact.result
    else:
        values=dict(state.values)
        gain=rules.content['interaction']['feed_gain'];maximum=rules.content['state']['maximum']['satiety']
        values['satiety']=min(maximum,values['satiety']+gain)
        if actor=='xiaomeng' and target is not None:values['satiety']=max(state.values['satiety'],min(values['satiety'],target))
        fact=await complete_participation(db,pet,state,rules,action='feed',request_key='interaction:'+attempt.id,business_key='interaction:'+attempt.id,
            now=now,state_after=values,participants=(actor,),result={'interaction_id':attempt.id,'name':pet.name},reaction={'type':'ate','scene':state.stage,'outcome':'responded'})
        attempt.state='done';attempt.result={**fact.result,'reaction':fact.reaction}
    attempt.event_id=fact.id;await db.flush();return await response(db,attempt,pet,state)

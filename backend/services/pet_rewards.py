"""Internal completion boundary; transport adapters must prove action completion first."""
from sqlalchemy import select
from backend.models.pet import PetFactEvent, PetFactRequest, PetState
from backend.services.pet_persistence import FactCommand, append_fact, _utc
from backend.services.pet_user_service import BUSINESS_ZONE, PetConflict


async def complete_participation(db,pet,state,rules,*,action,request_key,business_key,now,state_after,
        participants=('player',),source='actual_execution',parent_key=None,result=None,reaction=None,display_surfaces=('daily',)):
    # The caller holds the pet lock. Replays are resolved before recomputing rewards.
    old=await db.scalar(select(PetFactEvent).join(PetFactRequest,PetFactRequest.event_id==PetFactEvent.id).where(PetFactRequest.pet_id==pet.id,PetFactRequest.request_key==request_key))
    if old:
        if old.event_type!=action or old.business_key!=business_key:raise PetConflict('request_content_changed')
        return old
    family=parent_key or business_key
    eligible=source=='actual_execution' and 'player' in participants
    if eligible:
        from backend.services.pet_activity import activity_for
        await activity_for(db,pet)
    config=rules.content['rewards'];delta=0;reason='not_player_participation'
    if eligible:
        day=now.astimezone(BUSINESS_ZONE).date()
        history=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.closeness_delta>0).order_by(PetFactEvent.occurred_at.desc())))
        same_family=any(e.result.get('reward_family')==family for e in history)
        spent=sum(e.closeness_delta for e in history if e.business_date==day)
        same_action=[e for e in history if e.event_type==action]
        cooling=bool(same_action and (_utc(now)-same_action[0].occurred_at).total_seconds()<config['cooldown_seconds'])
        from backend.services.pet_rule_decisions import reward
        delta,reason=reward(rules.content,action,spent=spent,closeness=state.closeness,same_family=same_family,cooling=cooling)
    unlocked=list(state.unlocked_behaviors)
    if eligible:
        for unlock in config['unlocks']:
            if state.closeness+delta<unlock['closeness']:continue
            if (unlock['adult_required'] or unlock['adult_participation_required']) and state.stage!='adult':continue
            if unlock['key'] not in unlocked:unlocked.append(unlock['key'])
    response=dict(reaction or {})
    if eligible and 'adult_cooperation' in unlocked:response['behavior']='adult_cooperation'
    elif eligible and 'approach' in unlocked:response['behavior']='approach'
    outcome={**(result or {}),'completed':True,'active_eligible':eligible,'reward_family':family,'reward_reason':reason,
        'outcome':'completed_closeness' if delta else 'completed_state' if state_after!=state.values else 'accepted_no_gain'}
    surfaces=list(display_surfaces)
    if set(unlocked)-set(state.unlocked_behaviors):surfaces.append('album')
    if source=='actual_execution' and participants==('xiaomeng',) and action in {'feed','touch'}:
        previous_care=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.event_type.in_(['feed','touch']))))
        if not any(f.participants==['xiaomeng'] and f.result.get('completed') for f in previous_care):surfaces.append('album')
    fact=await append_fact(db,FactCommand(pet_id=pet.id,user_id=pet.user_id,request_key=request_key,business_key=business_key,
        expected_version=state.record_version,event_type=action,source=source,participants=participants,occurred_at=now,
        result=outcome,state_after=state_after,closeness_delta=delta,rule_snapshot_id=rules.snapshot_id,reaction=response or None,
        display_surfaces=tuple(surfaces),unlocked_after=tuple(unlocked)))
    if eligible:
        from backend.services.pet_activity import mark_active
        await mark_active(db,pet,now,source_event=fact)
    from backend.services.pet_preferences import discover_from_reactions
    await discover_from_reactions(db,pet,rules,fact)
    from backend.models.pet import PetSnapshot, PetRuleSnapshot
    if source=='actual_execution':
        appearance=await db.get(PetRuleSnapshot,state.appearance_rule_id) if state.appearance_rule_id else None
        db.add(PetSnapshot(pet_id=pet.id,business_key='observation:'+fact.id,kind='observation',source_event_id=fact.id,captured_at=fact.occurred_at,
            profile={'name':pet.name,'stage':state.stage},state={'values':dict(state.values),'record_version':state.record_version,'basis':'actual_execution'},
            resources={'appearance_rule_id':state.appearance_rule_id,'appearance':appearance.content if appearance else None},rule_snapshot_id=rules.snapshot_id))
        await db.flush()
    if eligible:
        from backend.services.pet_expression import queue_feedback
        await queue_feedback(db,pet,fact,now)
    return fact

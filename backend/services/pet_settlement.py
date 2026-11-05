"""One rule-settlement entry for reads, player actions and background care."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from backend.models.pet import PetProfile,PetState,PetRuleSnapshot,PetFactEvent,PetSnapshot
from backend.models.pet_config import PetConfigVersion
from backend.models.user import User
from backend.services.pet_persistence import FactCommand,append_fact,_utc

STAGES=('puppy','growing','adult')
def aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def iso(value):return aware(value).isoformat()
def age_days(birth_date,now):return max(0,(aware(now).astimezone(ZoneInfo('Asia/Shanghai')).date()-birth_date).days)
def stage_for_age(age,curve):return 'puppy' if age<curve['puppy_until_days'] else ('growing' if age<curve['adult_from_days'] else 'adult')

async def settle_pet(db,pet_id,user_id,*,until):
    until=_utc(until)
    pet=await db.scalar(select(PetProfile).where(PetProfile.id==pet_id,PetProfile.user_id==user_id).with_for_update().execution_options(populate_existing=True))
    if pet is None:raise LookupError('pet_not_found')
    user=await db.get(User,user_id)
    if user is None or user.is_banned:raise PermissionError('user_inactive')
    state=await db.scalar(select(PetState).where(PetState.pet_id==pet_id).with_for_update().execution_options(populate_existing=True))
    if state is None:raise ValueError('pet_state_missing')
    curve=await db.get(PetRuleSnapshot,pet.growth_rule_id)
    if curve is None:raise ValueError('growth_basis_missing')
    age=age_days(pet.birth_date,until);target=stage_for_age(age,curve.content)
    # A normal settlement cannot silently reverse an already shown growth stage.
    target=STAGES[max(STAGES.index(target),STAGES.index(state.stage))]
    if until<=state.settled_at:return {'pet_id':pet_id,'age_days':age,'stage':state.stage,'values':dict(state.values),'record_version':state.record_version,'segments':[]}
    versions=list(await db.scalars(select(PetConfigVersion).where(PetConfigVersion.domain=='rules',PetConfigVersion.effective_at<=until).order_by(PetConfigVersion.effective_at,PetConfigVersion.version)))
    previous=[v for v in versions if v.effective_at<=state.settled_at]
    if not previous:raise ValueError('state_basis_missing')
    active=previous[-1];cursor=state.settled_at;values=dict(state.values);segments=[]
    boundaries=[(v.effective_at,v) for v in versions if state.settled_at<v.effective_at<=until]+[(until,None)]
    for end,next_version in boundaries:
        if end>cursor:
            rules=await db.get(PetRuleSnapshot,active.state_snapshot_id)
            if rules is None:raise ValueError('state_basis_missing')
            hours=(end-cursor).total_seconds()/3600
            values={key:max(rules.content['minimum'][key],min(rules.content['maximum'][key],values[key]+rules.content['hourly'][key]*hours)) for key in ('satiety','energy','mood')}
            segments.append({'from':iso(cursor),'to':iso(end),'version':active.version,'snapshot_id':rules.id})
            cursor=end
        if next_version is not None:active=next_version
    old_stage=state.stage
    fact=await append_fact(db,FactCommand(pet_id=pet_id,user_id=user_id,request_key='settle:'+iso(until),business_key='settle:'+iso(until),
        expected_version=state.record_version,event_type='system_settlement',source='rule_settlement',participants=(),occurred_at=aware(until),
        result={'coverage_start':iso(state.settled_at),'coverage_end':iso(until),'segments':segments,'stage_before':old_stage,'stage_after':target},
        state_after=values,closeness_delta=0,rule_snapshot_id=active.state_snapshot_id,stage_after=target,settled_until=aware(until)))
    await db.refresh(state)
    for index in range(STAGES.index(old_stage)+1,STAGES.index(target)+1):
        stage=STAGES[index];key='growth:'+stage
        existing=await db.scalar(select(PetFactEvent).where(PetFactEvent.pet_id==pet_id,PetFactEvent.business_key==key))
        if existing:continue
        threshold=curve.content['puppy_until_days'] if stage=='growing' else curve.content['adult_from_days']
        transition=datetime.combine(pet.birth_date+timedelta(days=threshold),datetime.min.time(),tzinfo=ZoneInfo('Asia/Shanghai'))
        growth=await append_fact(db,FactCommand(pet_id=pet_id,user_id=user_id,request_key=key,business_key=key,expected_version=state.record_version,
            event_type='natural_growth',source='rule_settlement',participants=(),occurred_at=aware(until),
            result={'stage':stage,'estimated_transition_at':transition.isoformat(),'computed_at':iso(until),'coverage_start':iso(pet.adopted_at),'coverage_end':iso(until)},
            state_after=values,closeness_delta=0,rule_snapshot_id=pet.growth_rule_id,display_surfaces=('daily','album')))
        db.add(PetSnapshot(pet_id=pet_id,business_key=key,kind='growth',source_event_id=growth.id,captured_at=until,
            profile={'name':pet.name,'birth_date':pet.birth_date.isoformat(),'stage':stage,'estimated_transition_at':transition.isoformat()},
            state={'values':values,'basis':'rule_settlement'},resources={'appearance_rule_id':state.appearance_rule_id},rule_snapshot_id=pet.growth_rule_id))
        await db.flush();await db.refresh(state)
    db.add(PetSnapshot(pet_id=pet_id,business_key='settle:'+iso(until),kind='rule_settlement',source_event_id=fact.id,captured_at=until,
        profile={'name':pet.name,'stage':target},state={'values':values,'basis':'rule_settlement','covered_until':iso(until)},
        resources={'appearance_rule_id':state.appearance_rule_id},rule_snapshot_id=active.state_snapshot_id))
    await db.flush()
    return {'pet_id':pet_id,'age_days':age,'stage':target,'values':values,'record_version':state.record_version,'segments':segments}

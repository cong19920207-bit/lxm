"""Owner-scoped pet entry points. The caller owns the transaction; never calls AI."""
from datetime import datetime, timedelta, timezone
import unicodedata
from zoneinfo import ZoneInfo
from sqlalchemy import select
from backend.models.user import User
from backend.models.pet import PetProfile, PetState, PetFactEvent, PetFactRequest, PetSnapshot, new_id
from backend.models.pet_config import PetConfigVersion
from backend.services.pet_config_service import defaults
from backend.services.pet_persistence import FactCommand, append_fact, _utc
from backend.services.pet_settlement import aware, age_days, iso, settle_pet

BUSINESS_ZONE=ZoneInfo('Asia/Shanghai')
def now_utc():return datetime.now(timezone.utc)

class PetInputError(ValueError):pass
class PetDisabled(PetInputError):pass
class PetUnavailable(PetInputError):pass
class PetConflict(PetInputError):pass

def stable_key(key):
    if not isinstance(key,str) or not key.strip() or len(key)>96:raise PetInputError('invalid_request_key')
    return key

def validate_name(name,maximum=12):
    name=unicodedata.normalize('NFC',name.strip())
    if not 1<=len(name)<=maximum or any(unicodedata.category(c).startswith('C') or c in '<>\n\r' for c in name):raise PetInputError('invalid_name')
    return name

async def current_config(db,domain,now,*,lock=False):
    query=select(PetConfigVersion).where(PetConfigVersion.domain==domain,PetConfigVersion.effective_at<=_utc(aware(now))).order_by(PetConfigVersion.effective_at.desc(),PetConfigVersion.version.desc()).limit(1)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    return await db.scalar(query)

async def runtime_flags(db,now,*,lock=False):
    config=await current_config(db,'runtime',now,lock=lock)
    return dict(config.content) if config else defaults('runtime')

async def lock_owner(db,user_id):
    user=await db.scalar(select(User).where(User.id==user_id).with_for_update().execution_options(populate_existing=True))
    if user is None or user.is_banned:raise PermissionError('user_inactive')
    from backend.services.pet_lifecycle import account_available
    if not await account_available(db,user_id):raise PermissionError('account_deletion')
    return user

async def owner_pet(db,user_id,*,lock=False):
    query=select(PetProfile).where(PetProfile.user_id==user_id)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    return await db.scalar(query)

async def profile_view(db,pet,now):
    state=await db.get(PetState,pet.id)
    from backend.services.pet_appearance import current_mapping
    appearance=await current_mapping(db,pet,state,now)
    from backend.services.pet_templates import render,TEMPLATES
    ai=await current_config(db,'ai',now)
    rules=await current_config(db,'rules',now)
    flags=await runtime_flags(db,now)
    from backend.models.pet_interaction import PetInteraction
    active=await db.get(PetInteraction,state.active_activity['id']) if state.active_activity else None
    occupied=bool(active and active.state=='pending' and active.expires_at>_utc(now))
    from backend.services.pet_rule_decisions import action_reason
    from backend.services.pet_action_capabilities import joint_reason
    availability={}
    for action in ('touch','feed','play','joint_ball','photo'):
        reason='interactions_disabled' if not flags['interactions_enabled'] else 'pet_busy' if occupied else None
        if reason is None and rules:
            if action=='joint_ball':reason=joint_reason(rules.content,state.values,stage=state.stage)
            elif action=='play':reason=action_reason(rules.content,state.values,action)
        availability[action]={'allowed':reason is None,'reason':reason}
        if action=='play' and reason=='low_energy':availability[action]['alternative']='touch'
    if rules:
        from backend.services.pet_joint_service import invitation_elapsed
        invitation_reason=joint_reason(rules.content,state.values,stage=state.stage,origin='invitation',occupied=occupied,invite_elapsed=await invitation_elapsed(db,pet.id,now))
        availability['joint_invitation']={'allowed':flags['interactions_enabled'] and invitation_reason is None,'reason':'interactions_disabled' if not flags['interactions_enabled'] else invitation_reason}
    labels={'satiety':'吃饱了' if rules and state.values.get('satiety',0)>=rules.content['interaction']['feed_max_satiety'] else '肚子舒服',
            'energy':'有点困了' if state.values.get('energy',100)<20 else '精力充足',
            'mood':'心情轻松' if state.values.get('mood',0)>=60 else '平稳地待着'}
    messages={k:render(ai.content if ai else {},k,pet_name=pet.name,date=aware(now).date().isoformat(),stage=state.stage,facts='',participants='') for k in TEMPLATES}
    return {'messages':messages,'appearance':appearance,'pet_id':pet.id,'name':pet.name,'birth_date':pet.birth_date.isoformat(),
        'adopted_at':iso(pet.adopted_at),'adoption_date':aware(pet.adopted_at).astimezone(BUSINESS_ZONE).date().isoformat(),
        'age_days':age_days(pet.birth_date,now),'life_days':max(1,(aware(now).astimezone(BUSINESS_ZONE).date()-aware(pet.adopted_at).astimezone(BUSINESS_ZONE).date()).days+1),
        'identity':pet.template,'stage':state.stage,'values':dict(state.values),'tired':state.values.get('energy',100)<20,'record_version':state.record_version,
        'appearance_rule_id':state.appearance_rule_id,'care_eligible':True,
        'interactions_enabled':flags['interactions_enabled'],'joint_entry':rules.content['joint'].get('entry','user_and_invite') if rules else 'user_and_invite','availability':availability,'state_labels':labels,
        'preferences':pet.preference_discoveries or {},'unlocked_behaviors':list(state.unlocked_behaviors),
        'relationship':'愿意主动靠近' if 'approach' in state.unlocked_behaviors else '慢慢变熟悉'}

async def read_pet(db,user_id,*,now=None,settle=True):
    now=now or now_utc();await lock_owner(db,user_id)
    pet=await owner_pet(db,user_id,lock=True)
    if pet is None:return None
    if settle:await settle_pet(db,pet.id,user_id,until=now)
    return await profile_view(db,pet,now)

async def adopt(db,user_id,*,name,acknowledged,request_key,clock=now_utc):
    stable_key(request_key)
    if acknowledged is not True:raise PetInputError('acknowledgement_required')
    name=validate_name(name)
    await lock_owner(db,user_id)
    # The clock is sampled after the serialization lock, not when a form was opened.
    now=clock();stamp=_utc(now)
    existing=await owner_pet(db,user_id,lock=True)
    if existing is not None:
        original=await db.scalar(select(PetFactEvent).where(PetFactEvent.pet_id==existing.id,PetFactEvent.event_type=='adopted'))
        if original and original.request_key==request_key and original.result['name']!=name:raise PetConflict('request_content_changed')
        return await profile_view(db,existing,now)
    if not (await runtime_flags(db,now))['adoption_enabled']:raise PetDisabled('adoption_disabled')
    rules=await current_config(db,'rules',now);appearance=await current_config(db,'appearance',now)
    if rules is None or appearance is None:raise PetUnavailable('pet_configuration_unpublished')
    if not appearance.content.get('template',{}).get('available',True):raise PetDisabled('adoption_disabled')
    name=validate_name(name,rules.content['name_max_length'])
    try:birth=now.astimezone(BUSINESS_ZONE).date()-timedelta(days=rules.content['initial_age_days'])
    except (ValueError,OverflowError):raise PetInputError('invalid_internal_birth_date')
    if birth>=now.astimezone(BUSINESS_ZONE).date():raise PetInputError('invalid_internal_birth_date')
    async with db.begin_nested():
        pet=PetProfile(id=new_id(),user_id=user_id,name=name,birth_date=birth,adopted_at=stamp,
            template={'identity_key':appearance.content['identity_key'],'species':'dog','traits':['亲人','好奇']},
            stable_preferences=dict(rules.content['preferences']['preset']),preference_discoveries={},growth_rule_id=rules.growth_snapshot_id)
        db.add(pet);await db.flush()
        state=PetState(pet_id=pet.id,stage='puppy',values=dict(rules.content['state']['initial']),closeness=rules.content['rewards']['initial_closeness'],
            unlocked_behaviors=[],appearance_rule_id=appearance.snapshot_id,settled_at=stamp)
        db.add(state);await db.flush()
        fact=await append_fact(db,FactCommand(pet_id=pet.id,user_id=user_id,request_key=request_key,business_key='adopted',expected_version=1,
            event_type='adopted',source='actual_execution',participants=('player',),occurred_at=now,
            result={'name':name,'birth_date':birth.isoformat(),'acknowledged':True,'care_eligible':True},
            state_after=state.values,closeness_delta=0,rule_snapshot_id=rules.snapshot_id,display_surfaces=('daily','album')))
        db.add(PetSnapshot(pet_id=pet.id,business_key='adopted',kind='adoption',source_event_id=fact.id,captured_at=stamp,
            profile={'name':name,'birth_date':birth.isoformat(),'adopted_at':iso(stamp),'stage':'puppy','identity':pet.template},
            state={'values':dict(state.values),'record_version':state.record_version},resources={'appearance_rule_id':appearance.snapshot_id,'appearance':appearance.content},rule_snapshot_id=rules.snapshot_id))
        await db.flush()
    return await profile_view(db,pet,now)

async def rename(db,user_id,*,name,request_key,now=None):
    now=now or now_utc();stable_key(request_key);await lock_owner(db,user_id)
    pet=await owner_pet(db,user_id,lock=True)
    if pet is None:raise LookupError('pet_not_found')
    rules=await current_config(db,'rules',now);name=validate_name(name,rules.content['name_max_length'])
    previous=await db.scalar(select(PetFactEvent).join(PetFactRequest,PetFactRequest.event_id==PetFactEvent.id).where(PetFactRequest.pet_id==pet.id,PetFactRequest.request_key==request_key))
    if previous:
        if previous.event_type!='renamed' or previous.result['after_name']!=name:raise PetConflict('request_content_changed')
        return await profile_view(db,pet,now)
    state=await db.get(PetState,pet.id)
    await append_fact(db,FactCommand(pet_id=pet.id,user_id=user_id,request_key=request_key,business_key='rename:'+request_key,
        expected_version=state.record_version,event_type='renamed',source='actual_execution',participants=('player',),occurred_at=now,
        result={'before_name':pet.name,'after_name':name},state_after=state.values,closeness_delta=0,rule_snapshot_id=rules.snapshot_id,display_surfaces=('daily',)))
    pet.name=name;await db.flush()
    return await profile_view(db,pet,now)

async def introduction(db,*,now=None):
    now=now or now_utc();flags=await runtime_flags(db,now);appearance=await current_config(db,'appearance',now)
    return {'identity_key':'fixed-dog-v4','age_description':'约30日龄','personal':False,'adoption_enabled':bool(flags['adoption_enabled'] and appearance and appearance.content.get('template',{}).get('available',True))}

async def rename_result(db,user_id,request_key,*,now=None):
    stable_key(request_key);await lock_owner(db,user_id);pet=await owner_pet(db,user_id,lock=True)
    if pet is None:raise LookupError('pet_not_found')
    fact=await db.scalar(select(PetFactEvent).join(PetFactRequest,PetFactRequest.event_id==PetFactEvent.id).where(PetFactRequest.pet_id==pet.id,PetFactRequest.request_key==request_key))
    if not fact:return None
    if fact.event_type!='renamed':raise PetConflict('request_content_changed')
    return {'event_id':fact.id,'name':fact.result['after_name'],'pet':await profile_view(db,pet,now or now_utc())}

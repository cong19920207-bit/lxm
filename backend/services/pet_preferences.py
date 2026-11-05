"""Discovery references actual response facts without changing preset preferences."""
from sqlalchemy import select
from backend.models.pet import PetFactEvent,PetRuleSnapshot
from backend.services.pet_settlement import iso
from backend.services.pet_user_service import lock_owner,owner_pet,PetInputError

SUPPORTED={'lean_towards_hand':('touch','gentle',{'touch'}),'chased_ball':('play','ball',{'play','joint_ball'})}

async def qualified(db,pet,config):
    reaction_type=config['reaction_type'];key,value,actions=SUPPORTED[reaction_type]
    facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.event_type.in_(actions)).order_by(PetFactEvent.occurred_at,PetFactEvent.id)))
    accepted=[];excluded=[];cache={}
    for fact in facts:
        reaction=fact.reaction or {}
        reason=None
        if fact.source!='actual_execution' or 'player' not in fact.participants or fact.result.get('completed') is not True:reason='not_completed_participation'
        elif reaction.get('type')!=reaction_type or reaction.get('outcome')!='responded' or reaction.get('scene') not in {'puppy','growing','adult'}:reason='no_matching_actual_reaction'
        else:
            if fact.rule_snapshot_id not in cache:cache[fact.rule_snapshot_id]=await db.get(PetRuleSnapshot,fact.rule_snapshot_id)
            basis=cache[fact.rule_snapshot_id];then=basis.content.get('preferences',{}) if basis else {}
            if not then.get('discovery_enabled') or then.get('reaction_type')!=reaction_type:reason='not_eligible_under_original_rule'
        if reason:excluded.append({'event_id':fact.id,'reason':reason})
        else:accepted.append(fact)
    return key,value,accepted,excluded

async def discover_from_reactions(db,pet,rules,trigger):
    config=rules.content['preferences']
    if not config['discovery_enabled'] or not trigger.reaction:return
    key,value,accepted,_=await qualified(db,pet,config)
    if key in pet.preference_discoveries or pet.stable_preferences.get(key)!=value:return
    if len(accepted)<config['evidence_required']:return
    pet.preference_discoveries={**pet.preference_discoveries,key:{'value':value,'event_ids':[f.id for f in accepted],
        'rule_snapshot_id':rules.snapshot_id,'required':config['evidence_required'],'confirmed_at':iso(trigger.occurred_at)}}
    await db.flush()

async def preference_evidence(db,user_id,key):
    await lock_owner(db,user_id);pet=await owner_pet(db,user_id)
    if not pet or key not in pet.stable_preferences:raise LookupError('preference_not_found')
    discovery=pet.preference_discoveries.get(key)
    if not discovery:
        from backend.services.pet_user_service import current_config,now_utc
        from backend.services.pet_templates import render
        ai=await current_config(db,'ai',now_utc())
        return {'status':'learning','explanation':render(ai.content if ai else {},'preference_learning',pet_name=pet.name,date='',stage='',facts='',participants=''),'evidence':[]}
    facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.pet_id==pet.id,PetFactEvent.id.in_(discovery['event_ids'])).order_by(PetFactEvent.occurred_at)))
    return {'status':'confirmed','value':discovery['value'],'rule_snapshot_id':discovery['rule_snapshot_id'],'confirmed_at':discovery['confirmed_at'],
        'evidence':[{'event_id':f.id,'event_type':f.event_type,'occurred_at':iso(f.occurred_at),'reaction':f.reaction,'rule_snapshot_id':f.rule_snapshot_id} for f in facts]}

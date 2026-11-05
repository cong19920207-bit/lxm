"""One-time, idempotent removal of the retired SQL photo payloads; no OSS migration."""
from sqlalchemy import select,delete
from datetime import date,datetime
from backend.models.pet import PetSnapshot,PetFactEvent,PetDisplayEntry,PetTextSource,PetFormalText,PetTaskCandidate
from backend.models.pet_interaction import PetInteraction
from backend.models.pet_photo import PetPhotoAsset
from backend.models.pet_text_visibility import PetTextVisibility

_DROP=object()
def scrub(value,ids):
    if isinstance(value,dict):
        if any(value.get(k) in ids for k in ('event_id','source_event_id') if isinstance(value.get(k),str)):return _DROP
        return {k:new for k,v in value.items() if k!='photo_data_url' and (new:=scrub(v,ids)) is not _DROP}
    if isinstance(value,list):return [new for v in value if (new:=scrub(v,ids)) is not _DROP]
    return _DROP if isinstance(value,str) and value in ids else value

async def clear_legacy_photos(db):
    snapshots=list(await db.scalars(select(PetSnapshot).where(PetSnapshot.kind=='photo')))
    old=[s for s in snapshots if not s.resources.get('photo_asset_id')]
    oss_ids={s.source_event_id for s in snapshots if s.resources.get('photo_asset_id')}
    facts=list(await db.scalars(select(PetFactEvent).where(PetFactEvent.event_type=='joint_photo')))
    ids={f.id for f in facts if f.id not in oss_ids and not f.result.get('photo_cleared')}
    attempts=list(await db.scalars(select(PetInteraction).where(PetInteraction.kind=='photo')))
    cleared=0
    for a in attempts:
        if a.payload.get('storage')!='oss-v1' and not await db.get(PetPhotoAsset,a.id) and not a.payload.get('photo_cleared'):
            a.payload={'photo_cleared':True};a.result={'completed':a.state=='done','photo_cleared':True}
            if a.state=='pending':a.state='cancelled'
            cleared+=1
    text_ids=list(await db.scalars(select(PetTextSource.text_id).where(PetTextSource.event_id.in_(ids)).distinct())) if ids else []
    if text_ids:
        # Facts retain their minimum tombstone, so original text/source bindings stay valid.
        for text in await db.scalars(select(PetFormalText).where(PetFormalText.id.in_(text_ids))):
            text.config_snapshot={**text.config_snapshot,'source_photo_cleared':True}
    if ids:
        await db.execute(delete(PetDisplayEntry).where(PetDisplayEntry.source_event_id.in_(ids)))
        await db.execute(delete(PetTaskCandidate).where(PetTaskCandidate.source_event_id.in_(ids)))
        for f in facts:
            if f.id in ids:f.result={'completed':True,'photo_cleared':True};f.reaction=None
    old_snapshot_ids={s.id for s in old}
    from backend.models.pet_return import PetReturn
    from backend.models.pet_generation import PetGenerationTask
    for ret in await db.scalars(select(PetReturn)):
        if ret.last_snapshot_id in old_snapshot_ids:ret.last_snapshot_id=None
        ret.source_ids=[x for x in ret.source_ids if x not in ids]
        shaped=scrub(ret.highlights,ids);ret.highlights=[] if shaped is _DROP else shaped
    for task in await db.scalars(select(PetGenerationTask)):
        if set(task.source_ids)&ids:
            task.source_ids=[x for x in task.source_ids if x not in ids];task.state='superseded';task.reason='legacy_photo_cleared';task.generation+=1;task.result={}
    await db.flush()
    for s in old:await db.delete(s)
    await db.flush()
    affected_days={(f.pet_id,f.business_date.isoformat()) for f in facts if f.id in ids}
    overviews=0
    for s in await db.scalars(select(PetSnapshot).where(PetSnapshot.kind=='daily_overview')):
        shaped=scrub(s.state,ids|old_snapshot_ids)
        day=s.profile.get('business_date') or s.state.get('date')
        if (s.pet_id,day) in affected_days and isinstance(shaped,dict):
            from backend.models.pet import PetProfile
            from backend.services.pet_records import daily_for_pet
            from backend.services.pet_settlement import aware
            from backend.models.pet_rule_job import PetRuleJob
            basis=await db.scalar(select(PetRuleJob).where(PetRuleJob.pet_id==s.pet_id,PetRuleJob.kind=='daily_overview',PetRuleJob.business_key==s.business_key))
            cutoff=aware(basis.covered_until) if basis else None
            if cutoff is None:
                try:cutoff=aware(datetime.fromisoformat(s.business_key.split(':',2)[2]))
                except (IndexError,ValueError):pass
            if cutoff is not None:
                record=await daily_for_pet(db,await db.get(PetProfile,s.pet_id),date.fromisoformat(day),cutoff)
                for key in ('interaction_counts','participants','mood_observation','coverage_until'):
                    if key in shaped:shaped[key]=record[key]
            elif shaped!=s.state:
                # Unknown legacy cutoff: remove only photo-specific claims; never add later facts.
                if isinstance(shaped.get('interaction_counts'),dict):shaped['interaction_counts'].pop('joint_photo',None)
                if 'mood_observation' in shaped:shaped['mood_observation']=None
                shaped['photo_storage_cleared']=True
        if shaped!=s.state:s.state={} if shaped is _DROP else shaped;overviews+=1
    from backend.models.pet import PetState
    for state in await db.scalars(select(PetState).where(PetState.active_activity.is_not(None))):
        if isinstance(state.active_activity,dict) and state.active_activity.get('kind')=='photo':
            a=await db.get(PetInteraction,state.active_activity.get('id'))
            if a and a.payload.get('photo_cleared'):state.active_activity=None
    await db.flush()
    return {'snapshots':len(old),'facts_cleared':len(ids),'attempts_cleared':cleared,'texts_cleared':len(text_ids),'overviews_cleared':overviews}

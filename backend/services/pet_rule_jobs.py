"""Persistent rule-task claims and bounded, idempotent background production."""
from datetime import timedelta,timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.models.pet import PetProfile,utcnow
from backend.models.pet_rule_job import PetRuleJob
from backend.models.user import User
from backend.services.pet_persistence import _utc
from backend.services.pet_settlement import settle_pet,aware,iso

class StaleClaim(ValueError):pass

async def enqueue_job(db,pet_id,kind,business_key,covered_until):
    pet=await db.get(PetProfile,pet_id)
    if pet is None:raise LookupError('pet_not_found')
    await db.scalar(select(User).where(User.id==pet.user_id).with_for_update())
    pet=await db.scalar(select(PetProfile).where(PetProfile.id==pet_id).with_for_update().execution_options(populate_existing=True))
    if pet is None:raise LookupError('pet_not_found')
    job=await db.scalar(select(PetRuleJob).where(PetRuleJob.pet_id==pet_id,PetRuleJob.business_key==business_key).with_for_update())
    if job is None:
        job=PetRuleJob(pet_id=pet_id,kind=kind,business_key=business_key,covered_until=_utc(covered_until),pet_data_version=pet.data_version)
        db.add(job);await db.flush()
    elif job.kind!=kind or job.covered_until!=_utc(covered_until):raise ValueError('rule_job_key_conflict')
    return job

async def _eligible(db,job,*,commit=False):
    pet_query=select(PetProfile).where(PetProfile.id==job.pet_id).execution_options(populate_existing=True)
    pet=await db.scalar(pet_query)
    if pet is None or pet.data_version!=job.pet_data_version:raise StaleClaim('pet_version_changed')
    query=select(User).where(User.id==pet.user_id).execution_options(populate_existing=True)
    if commit:query=query.with_for_update()
    user=await db.scalar(query)
    if user is None or user.is_banned:raise StaleClaim('user_inactive')
    from backend.services.pet_lifecycle import account_available
    if not await account_available(db,pet.user_id):raise StaleClaim('account_deletion')
    if commit:
        # Match foreground user -> pet lock order; do not deadlock a player action.
        pet=await db.scalar(pet_query.with_for_update())
        if pet is None or pet.data_version!=job.pet_data_version:raise StaleClaim('pet_version_changed')
    return pet

async def claim_job(sessions,job_id,*,owner,now,lease_seconds=30):
    now=_utc(now)
    async with sessions.begin() as db:
        job=await db.get(PetRuleJob,job_id)
        if job is None or job.state in {'done','obsolete'}:return None
        await _eligible(db,job,commit=True)
        job=await db.scalar(select(PetRuleJob).where(PetRuleJob.id==job_id).with_for_update().execution_options(populate_existing=True))
        if job is None or job.state in {'done','obsolete'}:return None
        if job.state=='running' and job.lease_until and job.lease_until>now:return None
        job.generation+=1;job.owner=owner;job.lease_until=now+timedelta(seconds=lease_seconds);job.state='running';job.attempts+=1
        return {'id':job.id,'owner':owner,'generation':job.generation}

def _valid(job,claim,now):
    return job is not None and job.state=='running' and job.owner==claim['owner'] and job.generation==claim['generation'] and job.lease_until>now

async def execute_job(sessions,claim,work,*,clock=utcnow):
    if claim is None:return None
    try:
        async with sessions.begin() as db:
            job=await db.get(PetRuleJob,claim['id'])
            if job is None:raise StaleClaim('claim_expired_or_replaced')
            await _eligible(db,job,commit=True)
            job=await db.scalar(select(PetRuleJob).where(PetRuleJob.id==claim['id']).with_for_update().execution_options(populate_existing=True))
            if not _valid(job,claim,_utc(aware(clock()))):raise StaleClaim('claim_expired_or_replaced')
            result=await work(db,job)
            if not _valid(job,claim,_utc(aware(clock()))):raise StaleClaim('claim_expired_or_replaced')
            await _eligible(db,job,commit=True)
            if job.kind=='care' and result.get('executed'):
                from backend.services.pet_user_service import runtime_flags
                if not (await runtime_flags(db,aware(clock()),lock=True))['care_enabled']:raise StaleClaim('care_disabled_before_commit')
            job.state='done';job.result=result;job.last_success_at=_utc(aware(clock()));job.last_error=None
            return result
    except Exception as error:
        async with sessions.begin() as db:
            job=await db.scalar(select(PetRuleJob).where(PetRuleJob.id==claim['id']).with_for_update())
            if job is not None and job.generation==claim['generation'] and job.owner==claim['owner'] and job.state=='running':
                job.state='error';job.last_error=str(error) if isinstance(error,StaleClaim) else type(error).__name__
        raise

async def scan_settlements(sessions,*,now,owner,limit=100,after=None,clock=None):
    cutoff=_utc(now).replace(minute=0,second=0,microsecond=0)
    async with sessions() as db:
        query=select(PetProfile.id).join(User,User.id==PetProfile.user_id).where(User.is_banned.is_(False)).order_by(PetProfile.id).limit(limit)
        if after:query=query.where(PetProfile.id>after)
        ids=list(await db.scalars(query))
    completed=errors=0
    for pet_id in ids:
        async with sessions.begin() as db:
            job=await enqueue_job(db,pet_id,'settlement','settlement:'+iso(cutoff),aware(cutoff));job_id=job.id
        try:
            claim=await claim_job(sessions,job_id,owner=owner,now=aware(clock()) if clock else now)
            if claim is None:continue
            async def work(db,job):
                pet=await db.get(PetProfile,job.pet_id)
                return await settle_pet(db,pet.id,pet.user_id,until=aware(job.covered_until))
            await execute_job(sessions,claim,work,clock=clock or (lambda:now))
            completed+=1
        except (StaleClaim,ValueError,PermissionError):errors+=1
    return {'completed':completed,'errors':errors,'next_cursor':ids[-1] if len(ids)==limit else None,'covered_until':iso(cutoff)}

"""Same-cutoff accounting: source attempts and facts, never presentation rows."""
from datetime import timedelta
from collections import Counter
from hashlib import sha256
from sqlalchemy import select
from backend.models.pet import PetProfile,PetFactEvent,utcnow
from backend.models.pet_activity import PetActivity
from backend.models.pet_budget import PetRequestAttempt,PetBudgetEntry
from backend.models.pet_generation import PetGenerationTask
from backend.models.pet_rule_job import PetRuleJob
from backend.models.pet_health import PetJobHealth
from backend.services.pet_admin_security import check_permission
from backend.services.pet_admin_read import rules_at,serialize,list_pets
from backend.services.pet_job_health import PRODUCERS
from backend.services.pet_user_service import current_config,BUSINESS_ZONE
from backend.services.pet_settlement import aware

async def section(db,actor,name,*,at=None,start=None):
 await check_permission(db,actor,'overview.read','runtime');at=at or utcnow();at=aware(at).replace(tzinfo=None)
 start=aware(start).replace(tzinfo=None) if start else aware(at).astimezone(BUSINESS_ZONE).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(aware(at).tzinfo).replace(tzinfo=None)
 base={'at':at.isoformat(),'start':start.isoformat(),'timezone':'Asia/Shanghai','completeness':'available','role':actor['role']}
 if name=='population':
  profiles=list(await db.scalars(select(PetProfile).where(PetProfile.adopted_at<=at)));active=list(await db.scalars(select(PetActivity.pet_id).where(PetActivity.last_active_at>=at-timedelta(hours=24),PetActivity.last_active_at<=at)))
  bands={}
  for band in ('daily','short','long','extended'):bands[band]=(await list_pets(db,actor,at=at,band=band,page_size=1))['total']
  flags=await current_config(db,'runtime',aware(at));base.update(adopted_ids=[p.id for p in profiles],active_ids=active,tiers=bands,denominator=len(profiles),runtime=flags.content if flags else None,runtime_version=flags.id if flags else None)
 elif name=='requests':
  rows=list(await db.scalars(select(PetRequestAttempt).where(PetRequestAttempt.reserved_at<=at,((PetRequestAttempt.sent_at>=start)|(PetRequestAttempt.sent_at.is_(None)&(PetRequestAttempt.reserved_at>=start))))))
  sent=[a for a in rows if (a.sent_at is not None and a.sent_at<=at) or (a.state=='unknown' and a.sent_at is None)];events=list(await db.scalars(select(PetFactEvent.id).where(PetFactEvent.occurred_at>=start,PetFactEvent.occurred_at<=at,PetFactEvent.recorded_at<=at)))
  base.update(attempt_ids=[a.id for a in sent],formal_ids=[a.id for a in sent if a.origin!='debug'],debug_ids=[a.id for a in sent if a.origin=='debug'],unknown_ids=[a.id for a in sent if a.state=='unknown'],event_ids=events,attempts=[{'id':a.id,'origin':a.origin,'kind':a.kind,'state':a.state,'reason':a.reason,'sent_at':a.sent_at.isoformat() if a.sent_at else None,'usage':a.result.get('usage'),'elapsed_ms':a.result.get('elapsed_ms'),'config_id':a.config_id} for a in rows],usage_missing_ids=[a.id for a in sent if not a.result.get('usage',{}).get('complete')])
  completed=[a for a in sent if a.result.get('usage',{}).get('complete')]
  elapsed=[a.result['elapsed_ms'] for a in sent if isinstance(a.result.get('elapsed_ms'),(int,float))]
  fallbacks=list(await db.scalars(select(PetGenerationTask).where(PetGenerationTask.updated_at>=start,PetGenerationTask.updated_at<=at)))
  fallbacks=[t for t in fallbacks if t.result.get('source')=='template']
  base.update(usage={'input_tokens':sum(a.result['usage'].get('input_tokens') or 0 for a in completed),'output_tokens':sum(a.result['usage'].get('output_tokens') or 0 for a in completed),'complete_count':len(completed),'missing_count':len(sent)-len(completed),'basis':'only complete provider receipts; missing is unknown'},elapsed={'known_count':len(elapsed),'mean_ms':sum(elapsed)/len(elapsed) if elapsed else None,'maximum_ms':max(elapsed) if elapsed else None},template_fallback={'count':len(fallbacks),'task_ids':[t.id for t in fallbacks],'reasons':dict(Counter(t.result.get('fallback_reason') or t.reason or 'unspecified' for t in fallbacks)),'basis':'saved task results; excludes unsaved template displays'})
 elif name=='budgets':
  rules=await current_config(db,'rules',aware(at));cost=rules.content['costs'] if rules else None
  attempts=list(await db.scalars(select(PetRequestAttempt).where(PetRequestAttempt.reserved_at<=at)));byid={a.id:a for a in attempts};entries=list(await db.scalars(select(PetBudgetEntry).where(PetBudgetEntry.attempt_id.in_(byid)))) if byid else []
  day=aware(at).astimezone(BUSINESS_ZONE).date().isoformat();limits={'global':'global_daily','debug':'debug_daily','user':'user_daily','narrative':'narrative_daily','offline':'offline_total','return':'return_total'};groups={}
  for row in entries:
   a=byid[row.attempt_id];bucket=row.bucket
   if row.layer not in {'offline','return'} and not bucket.endswith(day):continue
   if row.layer in {'user','narrative','debug'} and actor['role'] not in {'super_admin','ops_admin'}:bucket=sha256(bucket.encode()).hexdigest()[:16]
   key=row.layer+':'+bucket;item=groups.setdefault(key,{'layer':row.layer,'bucket':bucket,'limit':cost[limits[row.layer]] if cost else None,'consumed_ids':[],'reserved_ids':[],'unknown_ids':[]})
   if row.state=='consumed':item['consumed_ids'].append(a.id)
   if row.state=='reserved' and a.concurrent_until>at:item['reserved_ids'].append(a.id)
   if row.state=='consumed' and a.state=='unknown':item['unknown_ids'].append(a.id)
  groups.setdefault('global:'+day,{'layer':'global','bucket':day,'limit':cost['global_daily'] if cost else None,'consumed_ids':[],'reserved_ids':[],'unknown_ids':[]})
  for item in groups.values():item['remaining']=max(0,item['limit']-len(item['consumed_ids'])-len(item['reserved_ids'])) if item['limit'] is not None else None
  concurrent=[a for a in attempts if a.concurrent_active and a.concurrent_until>at]
  base.update(configured=bool(cost and cost['global_daily']>0 and cost['global_concurrency']>0),config_id=rules.id if rules else None,layers=list(groups.values()),concurrency={'global_ids':[a.id for a in concurrent],'debug_ids':[a.id for a in concurrent if a.origin=='debug'],'global_limit':cost['global_concurrency'] if cost else None,'debug_limit':cost['debug_concurrency'] if cost else None})
 elif name=='health':
  runs={x.producer:x for x in await db.scalars(select(PetJobHealth).where(PetJobHealth.last_run_at<=at))};jobs=list(await db.scalars(select(PetRuleJob).where(PetRuleJob.recorded_at<=at)));tasks=list(await db.scalars(select(PetGenerationTask).where(PetGenerationTask.coverage_end<=at)))
  mapping={'care':['care'],'growth_snapshot':['settlement'],'birthday':['birthday'],'daily_overview':['daily_overview'],'generation':[],'cleanup':[]};health=[]
  for kind,producers in PRODUCERS.items():
   matching=[j for j in jobs if j.kind in mapping[kind]]
   waiting=[j for j in matching if j.state in {'pending','running'}]
   if kind=='generation':waiting=[t for t in tasks if t.state in {'queued','claimed','requesting'}]
   if kind=='cleanup':waiting=[t for t in tasks if t.expires_at<=at and t.state in {'queued','claimed','requesting'}]
   observed=[serialize(runs[p],actor['role']) for p in producers if p in runs]
   health.append({'kind':kind,'producers':producers,'coverage':'observed' if len(observed)==len(producers) else 'not_covered','runs':observed,'pending_ids':[x.id for x in waiting],'oldest_pending':min([getattr(x,'recorded_at',None) or x.coverage_end for x in waiting],default=None),'task_ids':[x.id for x in matching]})
  issues=[{'id':t.id,'type':'generation','kind':t.kind,'reason':t.reason,'state':t.state,'pet_id':t.pet_id,'at':at.isoformat(),'start':start.isoformat(),'role':actor['role']} for t in tasks if t.state in {'retryable_failed','final_failed','policy_skipped','superseded'}]
  issues.extend({'id':j.id,'type':'rule','kind':j.kind,'reason':j.last_error,'state':j.state,'pet_id':j.pet_id,'at':at.isoformat(),'start':start.isoformat(),'role':actor['role']} for j in jobs if j.state in {'error','obsolete'})
  base.update(health=health,issues=issues)
 else:
  from fastapi import HTTPException
  raise HTTPException(404,detail='overview_section_not_found')
 return base

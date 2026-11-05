"""Explicit legacy-photo removal and bounded OSS orphan cleanup. Run with python -m scripts.pet_photo_maintenance."""
import argparse,asyncio,json
from sqlalchemy import select,func
from backend.database import async_session_maker as sessions,engine
from backend.models.pet import PetSnapshot,PetFactEvent

async def maintain(args):
 async with sessions() as db:
  rows=list(await db.scalars(select(PetSnapshot).where(PetSnapshot.kind=='photo')))
  count=sum(not s.resources.get('photo_asset_id') for s in rows)
  before={'legacy_photo_snapshots':count,'oss_photo_snapshots':len(rows)-count,'other_snapshots':await db.scalar(select(func.count()).select_from(PetSnapshot).where(PetSnapshot.kind!='photo')),'other_facts':await db.scalar(select(func.count()).select_from(PetFactEvent).where(PetFactEvent.event_type!='joint_photo'))}
 if args.apply:
  if args.expected_legacy_photos is None or count!=args.expected_legacy_photos:raise SystemExit('Legacy photo count changed; inspect before applying')
  from backend.services.pet_photo_legacy_cleanup import clear_legacy_photos
  async with sessions.begin() as db:before['cleared']=await clear_legacy_photos(db)
 if args.cleanup_oss:
  from backend.services.pet_photos import cleanup_objects
  before['oss_cleanup']=await cleanup_objects(sessions,limit=50)
 print(json.dumps(before,ensure_ascii=False,indent=2))

async def main(args):
 from backend.services.memory_business_guard import enter_business_epoch,business_epoch
 token=None
 try:
  token=business_epoch.set(await enter_business_epoch(sessions))
  await maintain(args)
 finally:
  if token is not None:business_epoch.reset(token)
  await engine.dispose()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');p.add_argument('--expected-legacy-photos',type=int);p.add_argument('--cleanup-oss',action='store_true');asyncio.run(main(p.parse_args()))

"""Compatible current rendering is separate from immutable historical snapshots."""
from sqlalchemy import select
from backend.models.pet import PetRuleSnapshot,PetState,PetProfile,PetSnapshot
from backend.models.pet_config import PetResource,PetConfigVersion
from backend.services.pet_scene_resources import verify_resource,resource_capabilities
from backend.services.pet_config_service import ConfigInvalid

SLOTS={'room':'room.webp','rest':'rest.webp','puppy':'puppy.webp','blink':'blink.webp','ball':'ball.webp','juvenile':'juvenile.webp','adult':'adult.webp','feeding':'feeding.webp','puppy-low-energy':'puppy-low-energy-v4.png','juvenile-low-energy':'juvenile-low-energy-v4.png','adult-low-energy':'adult-low-energy-v4.png'}
ACTIONS={'idle','pet','feed','play','delivery','hand','dog','welcome'}
async def validate_compatibility(db,content):
 if content['identity_key']!='fixed-dog-v4':raise ConfigInvalid('appearance_identity_incompatible')
 if set(content['actions'])-ACTIONS:raise ConfigInvalid('appearance_action_unsupported')
 for action,identifier in content['actions'].items():
  resource=await db.get(PetResource,identifier)
  if not resource or action not in resource.actions:raise ConfigInvalid('appearance_action_incompatible:'+action)
  if resource_capabilities(resource)['actor']!='dog':raise ConfigInvalid('appearance_actor_not_adapted:'+action)
 for identifier in [*content['stages'].values(),content['fallback']]:
  resource=await db.get(PetResource,identifier)
  if resource and resource_capabilities(resource)['actor']!='dog':raise ConfigInvalid('appearance_portrait_actor_incompatible')
 # The renderer's approved rig requires every auxiliary asset, not just three portraits.
 for name in SLOTS.values():
  resource=await db.get(PetResource,'approved-v4:'+name)
  if not resource or not resource.available:raise ConfigInvalid('renderer_resource_missing:'+name)
  verify_resource(resource)

async def current_mapping(db,pet,state,now):
 from backend.services.pet_user_service import current_config
 published=await current_config(db,'appearance',now)
 if published and not state.active_activity:state.appearance_rule_id=published.snapshot_id
 basis=await db.get(PetRuleSnapshot,state.appearance_rule_id)
 if not basis:return None
 content=basis.content;ids={slot:'approved-v4:'+name for slot,name in SLOTS.items()}
 for stage,slot in [('puppy','puppy'),('growing','juvenile'),('adult','adult')]:ids[slot]=content['stages'][stage]
 ids['rest']=content['fallback']
 ids['room']=content.get('template',{}).get('scene','approved-v4:room.webp')
 if 'feed' in content['actions']:ids['feeding']=content['actions']['feed']
 for action,identifier in content['actions'].items():
  asset=await db.get(PetResource,identifier)
  for stage in asset.stages:ids['action:'+action+':'+{'growing':'juvenile'}.get(stage,stage)]=identifier
 resources={};versions={}
 for slot,identifier in ids.items():
  resource=await db.get(PetResource,identifier)
  if not resource:raise ConfigInvalid('appearance_resource_missing:'+identifier)
  resources[slot]=resource.uri;versions[slot]=resource.version
 current={'puppy':'puppy','growing':'juvenile','adult':'adult'}[state.stage]
 from backend.services.pet_config_service import defaults
 return {'snapshot_id':basis.id,'mapping_version':basis.id,'resource_version':versions[current],'resources':resources,'resource_ids':ids,'template':content.get('template',defaults('appearance')['template'])}

async def resource_references(db,resource_id):
 result=[]
 for version in await db.scalars(select(PetConfigVersion).where(PetConfigVersion.domain=='appearance')):
  c=version.content
  if resource_id in [*c['stages'].values(),c['fallback'],*c['actions'].values(),c.get('template',{}).get('scene','approved-v4:room.webp')]:result.append({'kind':'published_appearance','version_id':version.id,'version':version.version})
 if resource_id.startswith('approved-v4:'):
  for row in await db.scalars(select(PetSnapshot.id)):
   result.append({'kind':'approved_renderer_history','snapshot_id':row})
 return result

async def retire_unreferenced_resource(db,resource_id):
 references=await resource_references(db,resource_id)
 if references:raise ConfigInvalid('resource_referenced')
 resource=await db.get(PetResource,resource_id)
 if resource:resource.available=False
 await db.flush()

"""Register the approved local assets after verifying bytes; never downloads media."""
import json
from hashlib import sha256
from pathlib import Path
from backend.models.pet_config import PetResource
from backend.services.pet_config_service import ConfigInvalid
from sqlalchemy import select

ROOT=Path(__file__).resolve().parents[2]
ASSET_DIRECTORY=ROOT/'frontend/static/pet-assets/v4'
IMPLEMENTED_ACTIONS=frozenset({'idle','pet','feed','play','delivery','hand','dog','welcome'})

def resource_capabilities(resource):
    if resource.uri in {'/static/pet-assets/v4/room.webp','/static/pet-assets/v4/ball.webp'}:actor='prop'
    else:actor=(resource.capabilities or {}).get('actor','dog')
    return {**(resource.capabilities or {}),'actor':actor,'touch_region':'body' if actor=='dog' else None,'callbacks':['start','end','cancel'],'fallback':(resource.capabilities or {}).get('fallback','static'),'source':(resource.capabilities or {}).get('source','approved local manifest / legacy reviewed resource')}

def resource_view(resource):
    return {**{k:getattr(resource,k) for k in ('id','version','uri','identity_key','stages','actions','available','sha256')},'capabilities':resource_capabilities(resource)}

def validate_registration(data):
    required={'id','version','uri','identity_key','stages','actions','sha256','source','actor','fallback'}
    if set(data)!=required:raise ConfigInvalid('resource_fields_invalid')
    if any(not isinstance(data[k],str) or not data[k].strip() or len(data[k])>512 for k in ('id','version','uri','sha256','source')):raise ConfigInvalid('resource_fields_invalid')
    if len(data['id'])>128 or len(data['version'])>64:raise ConfigInvalid('resource_identifier_invalid')
    if not data['uri'].startswith('/static/pet-assets/') or '..' in data['uri'].split('/') or '?' in data['uri'] or '#' in data['uri']:raise ConfigInvalid('resource_path_invalid')
    if data['identity_key']!='fixed-dog-v4':raise ConfigInvalid('appearance_identity_incompatible')
    if not isinstance(data['stages'],list) or not data['stages'] or set(data['stages'])-{'puppy','growing','adult'}:raise ConfigInvalid('resource_stage_invalid')
    if not isinstance(data['actions'],list) or not data['actions'] or set(data['actions'])-IMPLEMENTED_ACTIONS:raise ConfigInvalid('resource_action_not_implemented')
    if data['actor'] not in {'dog','prop'} or data['fallback'] not in {'static','none'}:raise ConfigInvalid('resource_capability_invalid')
    value={k:data[k] for k in required-{'source','actor','fallback'}}
    value.update(available=True,capabilities={'source':data['source'],'actor':data['actor'],
        'touch_region':'body' if data['actor']=='dog' else None,'callbacks':['start','end','cancel'],'fallback':data['fallback']})
    resource=PetResource(**value);verify_resource(resource)
    if resource_capabilities(resource)['actor']!=data['actor']:raise ConfigInvalid('resource_actor_not_adapted')
    return resource

async def register_resource(sessions,actor,*,operation_id,reason,resource):
    from backend.services.pet_admin_security import prepare_operation,execute_operation
    await prepare_operation(sessions,actor,operation_id=operation_id,action='resource.register',domain='appearance',
                            target=resource.get('id',''),reason=reason,payload=resource)
    async def work(db,operation):
        proposed=validate_registration(operation.payload)
        existing=await db.get(PetResource,proposed.id)
        if existing:
            if resource_view(existing)!=resource_view(proposed):raise ConfigInvalid('immutable_resource_version_changed:'+proposed.id)
            return {'resource':resource_view(existing)}
        db.add(proposed);await db.flush()
        return {'resource':resource_view(proposed)}
    return await execute_operation(sessions,actor,operation_id,work)

async def list_resources(db,actor):
    from backend.services.pet_admin_security import check_permission
    from backend.services.pet_appearance import resource_references
    await check_permission(db,actor,'audit.read','appearance')
    return {'items':[{**resource_view(r),'references':await resource_references(db,r.id)} for r in await db.scalars(select(PetResource).order_by(PetResource.id))],
            'actions':sorted(IMPLEMENTED_ACTIONS),'stages':['puppy','growing','adult']}

def verify_resource(resource):
    if not resource.uri.startswith('/static/') or not resource.sha256:raise ConfigInvalid('resource_unverified:'+resource.id)
    public=(ROOT/'frontend/static').resolve();path=(ROOT/'frontend'/resource.uri.lstrip('/')).resolve()
    if not path.is_relative_to(public) or not path.is_file() or sha256(path.read_bytes()).hexdigest()!=resource.sha256:raise ConfigInvalid('resource_integrity_error:'+resource.id)

async def register_approved_resources(db):
    manifest=json.loads((ASSET_DIRECTORY/'manifest.json').read_text())
    prepared=[]
    for name,entry in manifest['files'].items():
        path=ASSET_DIRECTORY/name
        if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ConfigInvalid('approved_resource_missing_or_changed:'+name)
        stage='growing' if name.startswith('juvenile') else ('adult' if name.startswith('adult') else ('puppy' if name.startswith(('puppy','blink','feeding')) else None))
        prepared.append(dict(id=manifest['version']+':'+name,version=manifest['version'],uri=entry['uri'],identity_key=manifest['identity_key'],
            stages=[stage] if stage else ['puppy','growing','adult'],actions=['idle','pet','feed','play','delivery','hand','dog'],available=True,sha256=entry['sha256']))
    for data in prepared:
        existing=await db.get(PetResource,data['id'])
        if existing is None:db.add(PetResource(**data))
        elif existing.sha256!=data['sha256'] or existing.uri!=data['uri']:raise ConfigInvalid('immutable_resource_version_changed:'+data['id'])
    await db.flush()
    return {'identity_key':manifest['identity_key'],'stages':{'puppy':'approved-v4:puppy.webp','growing':'approved-v4:juvenile.webp','adult':'approved-v4:adult.webp'},'fallback':'approved-v4:rest.webp','actions':{}}

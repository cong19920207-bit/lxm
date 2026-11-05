"""Versioned pet config: no generic 20-version pruning or model side effects."""
from copy import deepcopy
from backend.services.pet_templates import TEMPLATES
from hashlib import sha256
import json,math
from string import Formatter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.models.pet import PetRuleSnapshot,new_id,utcnow
from backend.models.pet_config import PetConfigHead,PetConfigVersion,PetResource
from backend.services.pet_admin_security import check_permission,prepare_operation,execute_operation

class ConfigConflict(ValueError):pass
class ConfigInvalid(ValueError):pass

DEFAULTS={
 'runtime':{'adoption_enabled':True,'interactions_enabled':True,'care_enabled':True,'ai_enabled':False},
 'rules':{
  'initial_age_days':30,'name_max_length':12,
  'growth':{'puppy_until_days':90,'adult_from_days':180},
  'state':{'minimum':{'satiety':20,'energy':10,'mood':20},'maximum':{'satiety':100,'energy':100,'mood':100},
           'initial':{'satiety':60,'energy':80,'mood':70},'hourly':{'satiety':-2,'energy':4,'mood':-1}},
  'rewards':{'initial_closeness':0,'maximum_closeness':100,'daily_cap':6,'cooldown_seconds':60,
    'amounts':{'touch':1,'feed':1,'play':2,'joint_ball':3},
    'unlocks':[{'key':'approach','closeness':3,'adult_required':False,'adult_participation_required':False},
               {'key':'adult_cooperation','closeness':12,'adult_required':True,'adult_participation_required':True}]},
  'interaction':{'touch_min_seconds':0.8,'touch_merge_seconds':1.2,'feed_max_satiety':80,'feed_gain':25,
                 'play_energy_min':25,'play_cost':15,'play_mood_gain':10,'play_round_seconds':3},
  'care':{'check_hours':6,'min_interval_hours':6,'daily_cap':2,'feed_threshold':35,'feed_target':60,
          'home_event_interval_hours':12},
  'joint':{'enabled':True,'steps':['player_pass','xiaomeng_receive','dog_response'],'timeout_seconds':30,'invite_cooldown_seconds':300,'min_energy':25,
           'event_id':'shared-ball-01','allowed_stages':['puppy','growing','adult'],'entry':'user_and_invite','display_template':'joint_ball'},
  'preferences':{'preset':{'touch':'gentle','play':'ball'},'discovery_enabled':True,'evidence_required':3,'reaction_type':'lean_towards_hand'},
  'return':{'highlights':3},
  'narrative':{'day_start_minute':10,'day_end_minute':360,'selected_facts':8},
  'birthday':{'enabled':True,'leap_day':'02-28','template':'今天是{pet_name}的生日纪念日。'},
  'costs':{'user_daily':8,'narrative_daily':1,'global_daily':0,'global_concurrency':0,'debug_daily':0,'debug_concurrency':0,
           'offline_total':3,'return_total':1,'daily_hours':48,'short_days':7,'long_days':30,
           'short_interval_hours':72,'return_min_hours':24,'return_cooldown_hours':24,'view_seconds':15}},
 'ai':{'prompt':'根据真实事实{facts}，简短描述{pet_name}的状态，不编造参与者。','text_target':100,'text_max':160,
       'workflows':{k:{'prompt':p,'target':n,'maximum':m,'title_max':24} for k,p,n,m in [('immediate','根据本次真实互动{facts}，对{pet_name}说一句简短回应。',40,60),('daily','依据当天事实{facts}，为{pet_name}写一段日记录。',150,180),('period','依据期间事实{facts}，为{pet_name}写一段期间摘要。',150,180),('return','依据冻结的离开期间事实{facts}，欢迎回来看看{pet_name}。',150,180)]},
       'thinking':'default','workflow_thinking':{'immediate':'inherit','daily':'inherit','period':'inherit','return':'inherit'},'templates':deepcopy(TEMPLATES)},
 'appearance':{'identity_key':'fixed-dog-v4','stages':{'puppy':'','growing':'','adult':''},'fallback':'','actions':{},
               'template':{'template_id':'fixed-dog-v4','breed':'','sex':'','coat':'奶油色','features':'亲人、好奇','scene':'approved-v4:room.webp','available':True,'preference_ref':'rules.preferences'}},
}

def defaults(domain):
    if domain not in DEFAULTS:raise ConfigInvalid('unknown_config_domain')
    return deepcopy(DEFAULTS[domain])

def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _keys(value,template,path=''):
    if isinstance(value,dict) and isinstance(template,dict) and template:
        unknown=set(value)-set(template)
        if unknown:raise ConfigInvalid(f'unknown_fields:{path}:{sorted(unknown)}')
        for key,item in value.items():_keys(item,template[key],path+'.'+key)

def _shape(value,template,path=''):
    if isinstance(template,bool):
        if type(value) is not bool:raise ConfigInvalid('boolean_required:'+path)
    elif isinstance(template,(int,float)):
        if type(value) not in (int,float) or not math.isfinite(value):raise ConfigInvalid('number_required:'+path)
        if isinstance(template,int) and type(value) is not int:raise ConfigInvalid('integer_required:'+path)
    elif isinstance(template,str):
        if not isinstance(value,str):raise ConfigInvalid('string_required:'+path)
    elif isinstance(template,dict):
        if not isinstance(value,dict) or (template and set(value)!=set(template)):raise ConfigInvalid('fields_incomplete:'+path)
        for key,exemplar in template.items():_shape(value[key],exemplar,path+'.'+key)
    elif isinstance(template,list):
        if not isinstance(value,list):raise ConfigInvalid('list_required:'+path)
        if template:
            for item in value:_shape(item,template[0],path)

async def _validate(db,domain,content):
    _keys(content,defaults(domain))
    shaped=deepcopy(content)
    if domain=='appearance':shaped.setdefault('template',defaults('appearance')['template'])
    if domain=='rules' and isinstance(shaped.get('joint'),dict):
        for k in ('event_id','allowed_stages','entry','display_template'):shaped['joint'].setdefault(k,deepcopy(DEFAULTS['rules']['joint'][k]))
    if domain=='ai' and isinstance(shaped.get('templates'),dict):shaped['templates']={**TEMPLATES,**shaped['templates']}
    _shape(shaped,defaults(domain))
    if domain=='rules':
        g=content['growth'];r=content['rewards'];st=content['state'];c=content['care'];cost=content['costs'];i=content['interaction']
        if content['initial_age_days']!=30 or not 1<=content['name_max_length']<=12:raise ConfigInvalid('adoption_fields_invalid')
        if not 30<g['puppy_until_days']<g['adult_from_days']:raise ConfigInvalid('growth_thresholds_invalid')
        for key in ('satiety','energy','mood'):
            if not st['minimum'][key]<=st['initial'][key]<=st['maximum'][key]:raise ConfigInvalid('state_bounds_invalid:'+key)
        if not 0<=r['initial_closeness']<=r['maximum_closeness'] or r['daily_cap']<0 or r['cooldown_seconds']<0 or any(x<0 for x in r['amounts'].values()):raise ConfigInvalid('reward_bounds_invalid')
        if not st['minimum']['satiety']<c['feed_threshold']<c['feed_target']<=st['maximum']['satiety']:raise ConfigInvalid('care_state_combination_invalid')
        if c['check_hours']<=0 or c['min_interval_hours']<=0 or c['daily_cap']<0:raise ConfigInvalid('care_frequency_invalid')
        if i['touch_min_seconds']<=0 or i['touch_merge_seconds']<0 or i['play_round_seconds']<=0:raise ConfigInvalid('interaction_timing_invalid')
        if not st['minimum']['satiety']<i['feed_max_satiety']<=st['maximum']['satiety'] or i['feed_gain']<=0 or i['play_cost']<0:raise ConfigInvalid('interaction_state_invalid')
        if any(x<0 for x in cost.values()) or not cost['daily_hours']/24<cost['short_days']<cost['long_days']:raise ConfigInvalid('budget_or_tiers_invalid')
        if cost['return_total']>1:raise ConfigInvalid('return_single_request_limit')
        if not 0<=content['return']['highlights']<=10:raise ConfigInvalid('return_highlights_invalid')
        narrative=content['narrative']
        if not 0<=narrative['day_start_minute']<narrative['day_end_minute']<=1440 or not 1<=narrative['selected_facts']<=100:raise ConfigInvalid('narrative_window_invalid')
        if content['birthday']['leap_day'] not in {'02-28','03-01'}:raise ConfigInvalid('birthday_mapping_invalid')
        template=content['birthday']['template']
        try:
            parts=list(Formatter().parse(template));fields={field for _,field,_,_ in parts if field}
            if any(spec or conversion for _,_,spec,conversion in parts):raise ValueError('template_format_not_supported')
            if any(spec or conversion for _,_,spec,conversion in parts):raise ValueError()
        except ValueError:raise ConfigInvalid('birthday_template_invalid')
        if fields-{'pet_name','business_date'} or not template.strip() or len(template)>500 or any(word in template for word in ('庆祝','喂食','拍照','吹蜡烛','送礼','真实生日')):raise ConfigInvalid('birthday_template_must_only_describe_date')
        joint=shaped['joint']
        if joint.get('display_template')=='一起陪它玩了一会儿。':joint={**joint,'display_template':'joint_ball'}
        if not isinstance(joint.get('event_id','shared-ball-01'),str) or not joint.get('event_id','shared-ball-01').strip() or len(joint.get('event_id','shared-ball-01'))>64:raise ConfigInvalid('event_id_invalid')
        if not joint.get('allowed_stages',['puppy','growing','adult']) or set(joint.get('allowed_stages',[]))-{'puppy','growing','adult'}:raise ConfigInvalid('event_stage_invalid')
        if joint.get('entry','user_and_invite') not in {'user_and_invite','user'}:raise ConfigInvalid('event_entry_not_implemented')
        if joint.get('display_template','joint_ball')!='joint_ball':raise ConfigInvalid('event_template_not_implemented')
        if joint['enabled']:
            try:
                from backend.services.pet_joint_service import IMPLEMENTED_STEPS
            except ImportError:IMPLEMENTED_STEPS=frozenset()
            if not joint['steps'] or len(set(joint['steps']))!=len(joint['steps']) or set(joint['steps'])-set(IMPLEMENTED_STEPS):raise ConfigInvalid('joint_steps_not_implemented')
            if tuple(joint['steps'])!=tuple(IMPLEMENTED_STEPS) or joint['timeout_seconds']<=0 or joint['invite_cooldown_seconds']<0:raise ConfigInvalid('joint_contributions_required')
        if content['preferences']['evidence_required']<1:raise ConfigInvalid('reaction_evidence_invalid')
        if content['preferences']['reaction_type'] not in {'lean_towards_hand','chased_ball'} or content['preferences']['preset']!={'touch':'gentle','play':'ball'}:raise ConfigInvalid('preference_reaction_not_implemented')
    elif domain=='runtime' and content['ai_enabled']:
        rules=(await read_config(db,'rules'))['content']
        if not rules or rules['costs']['global_daily']<=0 or rules['costs']['global_concurrency']<=0:raise ConfigInvalid('global_budget_required')
    elif domain=='ai':
        from backend.services.pet_llm import resolve_thinking,ModelConfigurationError
        try:
            for value in content['workflow_thinking'].values():resolve_thinking(content['thinking'],value)
        except ModelConfigurationError as error:raise ConfigInvalid(str(error))
        if not 0<content['text_target']<=content['text_max'] or content['thinking'] not in {'default','on','off'}:raise ConfigInvalid('text_or_thinking_invalid')
        for workflow in content['workflows'].values():
            if not 0<workflow['target']<=workflow['maximum'] or workflow['title_max']<=0:raise ConfigInvalid('workflow_length_invalid')
            try:
                parts=list(Formatter().parse(workflow['prompt']));fields={field for _,field,_,_ in parts if field}
                if not {'facts','pet_name'}<=fields or fields-{'facts','pet_name','stage','date','participants'} or any(spec or conversion for _,_,spec,conversion in parts):raise ValueError()
            except ValueError:raise ConfigInvalid('workflow_template_variables_invalid')
        try:
            parts=[part for text in [content['prompt'],*content['templates'].values()] for part in Formatter().parse(text)]
            if any(spec or conversion for _,_,spec,conversion in parts):raise ValueError('template_format_not_supported')
            variables={field for _,field,_,_ in parts if field}
        except ValueError as error:raise ConfigInvalid('template_invalid') from error
        if variables-{'pet_name','facts','stage','date','participants'}:raise ConfigInvalid('template_variables_unsupported')
        for key,template in content['templates'].items():
            if not template.strip() or len(template)>500:raise ConfigInvalid('template_empty_or_too_long:'+key)
            fields={field for _,field,_,_ in Formatter().parse(template) if field}
            if key in {'welcome','fallback','birthday'} and 'pet_name' not in fields:raise ConfigInvalid('template_pet_name_required:'+key)
            if key=='birthday' and any(word in template for word in ('庆祝','喂食','拍照','吹蜡烛','送礼','真实生日')):raise ConfigInvalid('birthday_template_must_only_describe_date')
    elif domain=='appearance':
        template=shaped['template']
        if template['template_id']!='fixed-dog-v4' or template['preference_ref']!='rules.preferences':raise ConfigInvalid('template_identity_incompatible')
        if any(len(template[k])>512 for k in ('breed','sex','coat','features','scene')):raise ConfigInvalid('template_field_too_long')
        from backend.services.pet_appearance import validate_compatibility
        await validate_compatibility(db,content)
        refs=[*content['stages'].values(),content['fallback'],*content['actions'].values(),template['scene']]
        for key in refs:
            resource=await db.get(PetResource,key)
            if resource is None or not resource.available or resource.identity_key!=content['identity_key']:raise ConfigInvalid('resource_unavailable:'+str(key))
            from backend.services.pet_scene_resources import verify_resource
            verify_resource(resource)
        from backend.services.pet_scene_resources import resource_capabilities
        if resource_capabilities(await db.get(PetResource,template['scene']))['actor']!='prop':raise ConfigInvalid('scene_resource_actor_incompatible')
        for stage,key in content['stages'].items():
            if stage not in (await db.get(PetResource,key)).stages:raise ConfigInvalid('resource_stage_incompatible:'+stage)

async def _head(db,domain):
    defaults(domain)
    head=await db.scalar(select(PetConfigHead).where(PetConfigHead.domain==domain).with_for_update().execution_options(populate_existing=True))
    if head is None:
        try:
            async with db.begin_nested():
                head=PetConfigHead(domain=domain);db.add(head);await db.flush()
        except IntegrityError:
            head=await db.scalar(select(PetConfigHead).where(PetConfigHead.domain==domain).with_for_update().execution_options(populate_existing=True))
    return head

async def read_config(db,domain):
    defaults(domain)
    head=await db.get(PetConfigHead,domain)
    version=await db.scalar(select(PetConfigVersion).where(PetConfigVersion.domain==domain,PetConfigVersion.version==head.active_version)) if head and head.active_version else None
    from backend.services.pet_config_history import changes,ai_tests
    draft=head.draft if head else None;content=version.content if version else None
    changed=changes(content or {},draft) if draft is not None else {}
    stale=bool(head and draft is not None and head.draft_base_version!=head.active_version)
    validated=bool(head and draft is not None and not stale and head.validated_revision==head.draft_revision and head.validated_digest==fingerprint({'domain':domain,'revision':head.draft_revision,'base':head.active_version,'content':draft}))
    return {'domain':domain,'version':head.active_version if head else 0,'version_id':version.id if version else None,
        'content':deepcopy(version.content) if version else None,'draft_revision':head.draft_revision if head else 0,
        'draft_base_version':head.draft_base_version if head else 0,'draft':deepcopy(head.draft) if head else None,
        'validated':validated,'effective_at':version.effective_at.isoformat() if version else None,
        'draft_state':'none' if draft is None else 'stale' if stale else 'same' if not changed else 'validated' if validated else 'invalid' if head.validation_error else 'saved',
        'changed_paths':list(changed),'draft_diff':changed,'validation_error':head.validation_error if head else None,
        'updated_by':head.updated_by if head else None,'updated_at':head.updated_at.isoformat() if head else None,
        'ai_tests':await ai_tests(db,head,content) if domain=='ai' else []}

async def save_draft(db,actor,domain,content,*,expected_revision,base_version,source=None,force=False):
    await check_permission(db,actor,'config.publish',domain,commit=True)
    _keys(content,defaults(domain));fingerprint(content)
    head=await _head(db,domain)
    if head.draft_revision!=expected_revision or head.active_version!=base_version:raise ConfigConflict('draft_or_base_changed')
    if not force and head.draft is not None and fingerprint(head.draft)==fingerprint(content) and head.draft_base_version==base_version:return await read_config(db,domain)
    head.draft=deepcopy(content);head.draft_revision+=1;head.draft_base_version=base_version
    head.validated_digest=None;head.validated_revision=None;head.validation_error=None;head.updated_by=actor['id'];head.updated_at=utcnow()
    from backend.services.pet_config_history import record_save
    await record_save(db,actor,head,source)
    await db.flush()
    return await read_config(db,domain)

async def validate_draft(db,actor,domain,*,revision):
    await check_permission(db,actor,'config.publish',domain,commit=True)
    head=await _head(db,domain)
    if head.draft_revision!=revision or head.draft_base_version!=head.active_version:raise ConfigConflict('draft_or_base_changed')
    if head.draft is None:raise ConfigInvalid('draft_missing')
    try:await _validate(db,domain,head.draft)
    except ConfigInvalid as error:
        head.validated_digest=None;head.validated_revision=None;head.validation_error=str(error)[:512]
        await db.flush()
        raise
    head.validated_digest=fingerprint({'domain':domain,'revision':revision,'base':head.active_version,'content':head.draft})
    head.validated_revision=revision
    head.validation_error=None
    await db.flush()
    return {'revision':revision,'content_digest':fingerprint(head.draft),'validation_digest':head.validated_digest,'valid':True}

async def _write_version(db,operation,head,content,action):
    old=await read_config(db,head.domain);now=utcnow();version=head.active_version+1;identifier=new_id()
    snapshot=PetRuleSnapshot(id=identifier,kind='config:'+head.domain,version=str(version),content=deepcopy(content),effective_at=now)
    db.add(snapshot);growth_id=state_id=None
    if head.domain=='rules':
        growth_id=new_id();state_id=new_id()
        db.add(PetRuleSnapshot(id=growth_id,kind='growth',version=identifier,content=deepcopy(content['growth']),effective_at=now))
        db.add(PetRuleSnapshot(id=state_id,kind='state',version=identifier,content=deepcopy(content['state']),effective_at=now))
    await db.flush()
    before=old['content'] or {}
    diff={key:{'before':before.get(key),'after':value} for key,value in content.items() if before.get(key)!=value}
    publication=PetConfigVersion(id=identifier,domain=head.domain,version=version,content=deepcopy(content),
        content_digest=fingerprint(content),diff=diff,effective_at=now,action=action,operation_id=operation.id,
        snapshot_id=identifier,growth_snapshot_id=growth_id,state_snapshot_id=state_id)
    db.add(publication);head.active_version=version;head.validated_digest=None;head.validated_revision=None;head.validation_error=None
    if action=='publish':head.draft_base_version=version
    await db.flush()
    return {'domain':head.domain,'version':version,'version_id':identifier,'effective_at':now.isoformat(),
        'action':action,'content':deepcopy(content),'diff':diff,'operation_id':operation.id,
        'source_draft_revision':head.draft_revision if action=='publish' else None,
        'restored_from_version':operation.payload.get('target_version') if action=='rollback' else None,
        'scope':'new_adoptions_and_future_actions; bound_growth_and_history_preserved' if head.domain=='rules' else ('existing_current_scene_when_idle; immutable_history_preserved' if head.domain=='appearance' else 'future_applicable_work')}

async def publish(sessions,actor,domain,*,revision,base_version,operation_id,reason):
    op=await prepare_operation(sessions,actor,operation_id=operation_id,action='config.publish',domain=domain,target=domain,reason=reason,payload={'revision':revision,'base_version':base_version})
    async def work(db,operation):
        head=await _head(db,domain)
        if head.draft_revision!=revision or head.active_version!=base_version or head.draft_base_version!=base_version:raise ConfigConflict('draft_or_base_changed')
        expected=fingerprint({'domain':domain,'revision':revision,'base':base_version,'content':head.draft})
        if head.draft is None or head.validated_digest!=expected or head.validated_revision!=revision:raise ConfigInvalid('validation_not_bound')
        await _validate(db,domain,head.draft)
        if domain=='ai':
            from backend.services.pet_config_history import require_tests
            await require_tests(db,head,(await read_config(db,domain))['content'])
        return await _write_version(db,operation,head,head.draft,'publish')
    return await execute_operation(sessions,actor,op,work)

async def rollback(sessions,actor,domain,*,target_version,base_version,operation_id,reason):
    op=await prepare_operation(sessions,actor,operation_id=operation_id,action='config.rollback',domain=domain,target=domain,reason=reason,payload={'target_version':target_version,'base_version':base_version})
    async def work(db,operation):
        head=await _head(db,domain)
        if head.active_version!=base_version:raise ConfigConflict('base_changed')
        old=await db.scalar(select(PetConfigVersion).where(PetConfigVersion.domain==domain,PetConfigVersion.version==target_version))
        if old is None:raise ConfigInvalid('version_missing')
        await _validate(db,domain,old.content)
        return await _write_version(db,operation,head,old.content,'rollback')
    return await execute_operation(sessions,actor,op,work)

async def disable(sessions,actor,flag,*,operation_id,reason):
    if flag not in defaults('runtime'):raise ConfigInvalid('unknown_runtime_switch')
    op=await prepare_operation(sessions,actor,operation_id=operation_id,action='config.publish',domain='runtime',target=flag,reason=reason,payload={'disable':flag})
    async def work(db,operation):
        head=await _head(db,'runtime');current=await read_config(db,'runtime');content=current['content'] or defaults('runtime')
        content[flag]=False
        return await _write_version(db,operation,head,content,'disable')
    return await execute_operation(sessions,actor,op,work)

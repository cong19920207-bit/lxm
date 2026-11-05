"""Business editor metadata and deterministic simulations; no real pet mutations."""
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from sqlalchemy import select
from backend.models.pet_config import PetResource,PetConfigVersion
from backend.services.pet_config_service import defaults,read_config,_validate,ConfigInvalid,fingerprint
from backend.services.pet_admin_security import check_permission,allowed
from backend.services.pet_settlement import age_days,stage_for_age,aware
from backend.services.pet_activity import tier
from backend.services.pet_birthday import birthday_date
from backend.services.pet_appearance import resource_references
from backend.services.pet_rule_decisions import action_reason,reward,care_reason
from backend.services.pet_expression import render_template

LABELS={'event_id':'共同事件标识','allowed_stages':'适用成长阶段','entry':'发起方式','display_template':'完成文案模板引用','template_id':'固定模板标识','breed':'品种（未定留空）','sex':'性别（未定留空）','coat':'毛色','features':'稳定辨识特征','scene':'场景资源','available':'可用于新领养（不隐藏已有宠物）','preference_ref':'偏好规则引用','rules':'成长、互动与成本','runtime':'独立运行开关','appearance':'固定模板与素材','initial_age_days':'初始估算年龄','name_max_length':'名字长度','growth':'成长曲线（仅新领养绑定）','puppy_until_days':'成长期起点','adult_from_days':'成年起点','state':'状态自然变化','minimum':'保底下限','maximum':'上限','initial':'领养初值','hourly':'每小时变化','satiety':'饱腹','energy':'精力','mood':'心情','rewards':'玩家亲近收益','initial_closeness':'初始亲近','maximum_closeness':'亲近上限','daily_cap':'每日上限','cooldown_seconds':'同类收益间隔','amounts':'单次收益','touch':'抚摸','feed':'喂食','play':'陪玩','joint_ball':'共同玩球','unlocks':'表现解锁','key':'已实现表现标识','closeness':'亲近门槛','adult_required':'需要成年','adult_participation_required':'需要成年后玩家参与','interaction':'日常互动','touch_min_seconds':'有效抚摸时长','touch_merge_seconds':'连续触摸合并窗口','feed_max_satiety':'接受喂食的饱腹上界','feed_gain':'喂食饱腹增加','play_energy_min':'陪玩最低精力','play_cost':'陪玩精力消耗','play_mood_gain':'陪玩心情增加','play_round_seconds':'短回合时长','care':'有限自动照顾','check_hours':'检查窗口','min_interval_hours':'同类照顾间隔','feed_threshold':'照顾触发饱腹','feed_target':'照顾目标饱腹','home_event_interval_hours':'居家事件间隔','joint':'共同事件','enabled':'启用','steps':'双方步骤顺序','timeout_seconds':'最长占用时长','invite_cooldown_seconds':'邀请间隔','min_energy':'最低精力','preferences':'稳定偏好发现','preset':'固定稳定偏好','discovery_enabled':'发现开关','evidence_required':'所需真实反应数','reaction_type':'已实现反应','return':'回访','highlights':'事实重点数量','narrative':'叙事窗口','day_start_minute':'每日窗口开始','day_end_minute':'每日窗口结束','selected_facts':'选取事实数','birthday':'生日纪念','leap_day':'闰日映射','template':'固定纪念模板','costs':'分层预算与四档','user_daily':'用户每日请求','narrative_daily':'用户每日叙事','global_daily':'全局每日请求','global_concurrency':'全局并发','debug_daily':'调试每日请求','debug_concurrency':'调试并发','offline_total':'连续离开总请求','return_total':'单次回访请求','daily_hours':'日常档时限','short_days':'短期档时限','long_days':'长期档时限','short_interval_hours':'短期双间隔','return_min_hours':'最短离开时长','return_cooldown_hours':'回访间隔','view_seconds':'有效查看时长','adoption_enabled':'新领养','interactions_enabled':'用户互动','care_enabled':'自动照顾','ai_enabled':'AI 表达','identity_key':'固定狗身份','stages':'三个阶段资源','puppy':'幼犬','growing':'成长期','adult':'成年','fallback':'简化表现引用','actions':'已实现动作映射'}

def schema(value,path=''):
 if isinstance(value,dict):return {'type':'group','label':LABELS.get(path.split('.')[-1],path),'children':{k:schema(v,path+'.'+k) for k,v in value.items()}}
 if isinstance(value,list):return {'type':'list','label':LABELS.get(path.split('.')[-1],path),'items':[schema(v,path) for v in value]}
 key=path.split('.')[-1];kind='boolean' if isinstance(value,bool) else 'number' if isinstance(value,(int,float)) else 'text'
 unit='秒' if key.endswith('seconds') else '小时' if key.endswith('hours') else '天' if key.endswith('days') else '分钟（北京时间零点起）' if key.endswith('minute') else '次' if key in {'daily_cap','evidence_required','user_daily','global_daily','debug_daily','narrative_daily','offline_total','return_total'} else '数值' if kind=='number' else ''
 range_text='有限数值；按所在组联合校验'
 if key=='initial_age_days':range_text='固定30天'
 elif key=='return_total':range_text='0或1'
 elif key=='name_max_length':range_text='1至12字'
 elif kind=='boolean':range_text='开启 / 关闭；相互独立'
 elif kind=='text':range_text='已实现标识或受限模板；服务端校验'
 if path.endswith('.birthday.template'):range_text='兼容回退；正式生日文案在 AI 与文案维护'
 return {'read_only':path.endswith('.birthday.template'),'type':kind,'choices':({'joint_ball':'共同陪玩固定文案（在 AI 与文案维护）'} if key=='display_template' else {'lean_towards_hand':'轻抚后靠向手边','chased_ball':'实际追球回应'} if key=='reaction_type' else {'gentle':'轻柔抚摸（固定定义）'} if path.endswith('.preset.touch') else {'ball':'小球（固定定义）'} if path.endswith('.preset.play') else {'user_and_invite':'用户发起与邀请','user':'仅用户发起'} if key=='entry' else {'default':'跟随供应商默认','on':'开启思考','off':'关闭思考'} if key=='thinking' else {'inherit':'跟随养宠全局','on':'开启思考','off':'关闭思考'} if '.workflow_thinking.' in path else None),'label':LABELS.get(key,key),'unit':unit,'range':range_text,'path':path.lstrip('.')}

async def editor(db,actor,domain):
 await check_permission(db,actor,'audit.read',domain)
 c=await read_config(db,domain);value=c['draft'] if allowed(actor['role'],'config.publish',domain) and c['draft'] is not None else c['content'] or defaults(domain)
 if domain=='appearance':
  value=deepcopy(value);value.setdefault('template',defaults('appearance')['template'])
 if domain=='rules':
  value=deepcopy(value)
  for k in ('event_id','allowed_stages','entry','display_template'):value['joint'].setdefault(k,deepcopy(defaults('rules')['joint'][k]))
  if value['joint'].get('display_template')=='一起陪它玩了一会儿。':value['joint']['display_template']='joint_ball'
 if domain=='ai':
  from backend.services.pet_templates import TEMPLATES
  value=deepcopy(value);value['templates']={**TEMPLATES,**value['templates']}
 if not allowed(actor['role'],'config.publish',domain):
  for key in ('draft','validated','draft_diff','validation_error','ai_tests'):c.pop(key,None)
  c.update(draft_state='none',changed_paths=[])
 from backend.services.pet_action_capabilities import STEPS
 return {**c,'editable':allowed(actor['role'],'config.publish',domain),'editor_value':value,'schema':schema(value),'action_capabilities':STEPS,'scope':{'rules':'新领养绑定成长；未来互动/后续状态分段；不重写历史或已保存发现','appearance':'已有宠物空闲时当前展示；历史资源与个体数据不变','runtime':'提交后独立开关；账号和全局维护优先','ai':'未来生成使用新配置；既有文字不改写'}[domain]}

def sample_input():
 return {'date':'2026-03-01T00:00:00+00:00','birth_date':'2024-02-29','pet_name':'示例小狗','hours':12,'values':{'satiety':40,'energy':15,'mood':60},'daily_reward_used':6,'closeness':10,'action':'feed','completed_steps':['player_pass','xiaomeng_receive','dog_response'],'last_active_at':'2026-02-25T00:00:00+00:00','origin':'return','absence_ended':True,'remaining':{'offline':0,'return':1,'narrative':1,'user':8,'global':10},'reactions':[]}

def simulate_rules(c,i):
 now=aware(datetime.fromisoformat(i['date']));birth=date.fromisoformat(i['birth_date']);hours=float(i.get('hours',0))
 if hours<0 or hours>24*3650:raise ConfigInvalid('preview_hours_invalid')
 values=dict(i.get('values',c['state']['initial']));segments=[]
 # Each supplied segment is an explicitly simulated version, not a historical claim.
 for seg in i.get('segments',[{'hours':hours,'state':c['state'],'version':'draft'}]):
  st=seg['state'];length=float(seg['hours'])
  if length<0:raise ConfigInvalid('preview_segment_invalid')
  values={k:max(st['minimum'][k],min(st['maximum'][k],values[k]+st['hourly'][k]*length)) for k in ('satiety','energy','mood')};segments.append({'version':seg.get('version'),'hours':length,'values':dict(values)})
 action=i.get('action','feed')
 why=action_reason(c,values,action,occupied=i.get('occupied',False),duration_ms=i.get('duration_ms'))
 if action=='joint_ball':
  from backend.services.pet_action_capabilities import joint_reason
  why=joint_reason(c,values,stage=i.get('stage','puppy'),occupied=i.get('occupied',False),origin=i.get('initiator','user'),invite_elapsed=i.get('invite_elapsed_seconds',float('inf')))
 accepted=why is None
 amount,gain_reason=reward(c,action,spent=i.get('daily_reward_used',0),closeness=i.get('closeness',0),same_family=i.get('already_rewarded',False),cooling=i.get('reward_elapsed_seconds',float('inf'))<c['rewards']['cooldown_seconds'])
 if not accepted:amount=0;gain_reason=why
 care_why=care_reason(c,values,used=i.get('care_used',0),elapsed_hours=i.get('care_elapsed_hours',float('inf')),occupied=i.get('occupied',False))
 from backend.services.pet_action_capabilities import joint_reason
 joint_why=joint_reason(c,values,stage=i.get('stage','puppy'),occupied=i.get('occupied',False),origin=i.get('initiator','user'),invite_elapsed=i.get('invite_elapsed_seconds',float('inf')))
 selected=i.get('completed_steps',[]);joint_complete=joint_why is None and selected==c['joint']['steps']
 if action=='joint_ball' and not joint_complete:amount=0
 pref=c['preferences'];seen=set();reactions=[];accepted_ids=[]
 for r in i.get('reactions',[]):
  rid=r.get('id');reason='included'
  if not rid:reason='missing_source_id'
  elif rid in seen:reason='duplicate_reaction'
  elif r.get('source')!='actual_execution' or not r.get('completed') or 'player' not in r.get('participants',[]):reason='not_actual_player_reaction'
  elif r.get('type')!=pref['reaction_type'] or r.get('outcome')!='responded' or r.get('scene') not in {'puppy','growing','adult'}:reason='reaction_mismatch'
  elif not r.get('original_rule_eligible',False):reason='original_rule_not_eligible'
  if rid:seen.add(rid)
  if reason=='included':accepted_ids.append(rid)
  reactions.append({'id':rid,'reason':reason})
 layers=['global','debug'] if i.get('origin')=='debug' else ['global','user','narrative','return'] if i.get('origin')=='return' else ['global','user','narrative','offline'] if i.get('origin')=='offline' else ['global','user']
 remaining=i.get('remaining',{});blocked=[x for x in layers if remaining.get(x,0)<=0]
 if i.get('concurrent',0)>=c['costs']['global_concurrency']:blocked.append('global_concurrency')
 if i.get('origin')=='debug' and i.get('debug_concurrent',0)>=c['costs']['debug_concurrency']:blocked.append('debug_concurrency')
 if i.get('important_facts') is False and i.get('origin') in {'offline','return'}:blocked.append('no_new_facts')
 if c['costs']['global_daily']<=0 or c['costs']['global_concurrency']<=0:blocked.append('global_configuration_incomplete')
 if i.get('origin')=='return' and not i.get('absence_ended'):blocked.append('return_not_confirmed')
 anniversary=birthday_date(birth,now.year,c['birthday']['leap_day']);curve=i.get('bound_growth',c['growth'])
 band=tier(datetime.fromisoformat(i.get('last_active_at',i['date'])),now,c['costs'])
 if i.get('origin')=='offline':
  if i.get('absence_ended'):blocked.append('absence_closed')
  if band in {'long','extended'}:blocked.append('offline_tier_forbidden')
  if band=='short':
   anchor=aware(datetime.fromisoformat(i['last_active_at']))
   if (now-anchor).total_seconds()<c['costs']['short_interval_hours']*3600:blocked.append('short_interval')
   if i.get('last_attempt_at') and (now-aware(datetime.fromisoformat(i['last_attempt_at']))).total_seconds()<c['costs']['short_interval_hours']*3600:blocked.append('short_interval')
 return {'simulation_only':True,'model_requests':0,'stage':stage_for_age(age_days(birth,now),curve),'growth_basis':'provided_bound_curve' if 'bound_growth'in i else 'draft_for_new_adoption','segments':segments,'values':values,'action':{'accepted':accepted,'reason':why,'closeness_delta':amount,'daily_cap':c['rewards']['daily_cap'],'gain_reason':gain_reason},'care':{'trigger':care_why is None,'reason':care_why,'target':c['care']['feed_target'],'daily_cap':c['care']['daily_cap'],'minimum_interval_hours':c['care']['min_interval_hours'],'check_hours':c['care']['check_hours']},'joint':{'steps':c['joint']['steps'],'completed':joint_complete,'timeout_seconds':c['joint']['timeout_seconds'],'reward_family':'one_parent_only','interrupted':'only already completed actual actions retained; no joint completion'},'preferences':{'reactions':reactions,'accepted_ids':accepted_ids,'discovered':pref['discovery_enabled'] and len(accepted_ids)>=pref['evidence_required']},'birthday':{'date':anniversary.isoformat(),'body':render_template(i.get('birthday_template',c['birthday']['template']),{'pet_name':i.get('pet_name','示例小狗'),'business_date':anniversary.isoformat(),'date':anniversary.isoformat(),'stage':stage_for_age(age_days(birth,now),curve),'facts':'','participants':''}),'participants':[],'source':'rule_settlement','model_requests':0,'copy_source':i.get('birthday_copy_source','rules_compatibility_fallback')},'budget':{'tier':band,'layers':layers,'blocked':blocked,'eligible':not blocked,'old_offline_ledger_retained':True}}

async def preview(db,actor,domain,*,content=None,inputs=None,readonly=False):
 await check_permission(db,actor,'audit.read' if readonly else 'config.publish',domain)
 c=content or (await read_config(db,domain))['content'] or defaults(domain)
 await _validate(db,domain,c)
 if domain=='rules':
  simulation=deepcopy(inputs or sample_input())
  from backend.services.pet_user_service import current_config,now_utc
  ai=await current_config(db,'ai',now_utc())
  if ai and 'birthday' in ai.content.get('templates',{}):simulation.update(birthday_template=ai.content['templates']['birthday'],birthday_copy_source='ai.templates.birthday')
  result=simulate_rules(c,simulation)
 elif domain=='runtime':result={'switches':c,'independent':True,'ai_off_retains':['rules','facts','templates'],'priority':['account','global_maintenance'],'model_requests':0}
 elif domain=='appearance':
  result={'stages':c['stages'],'actions':c['actions'],'identity':c['identity_key'],'unknown_traits':'not_displayed','scope':'current_scene_when_idle; history_and_individual_unchanged','resources':[{'id':r.id,'version':r.version,'uri':r.uri,'stages':r.stages,'actions':r.actions,'available':r.available,'references':await resource_references(db,r.id)} for r in await db.scalars(select(PetResource))],'model_requests':0}
 else:raise ConfigInvalid('unsupported_preview_domain')
 return {'content_digest':fingerprint(c),'result':result,'kind':'deterministic_preview','published':False}

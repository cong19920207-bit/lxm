/* Presentation helpers: existing routes, permissions and business actions remain authoritative. */
(()=>{'use strict';const A=window.PetAdmin;
const guides={
 overview:{tag:'日常巡检',description:'先了解养宠功能的运行情况，再从异常、宠物或预算进入具体处理。',steps:['查看领养、活跃、请求及待关注数量。','检查任务运行与预算情况；未覆盖表示尚无运行证据。','沿关联入口查看原始记录，再决定是否需要处理。']},
 pets:{tag:'个体查询',description:'查找一只宠物，了解它的当前状态，并追溯成长、互动和文案背后的真实记录。',steps:['通过名字、宠物标识、阶段或陪伴档位筛选。','打开宠物，先看档案与状态，再查看对应类型的记录。','需要排查时，从详情进入关联任务、修复预览或操作日志。']},
 rules:{tag:'体验与成本配置',description:'管理成长、互动、自动照顾、请求预算与回访规则；通过业务分类定位要调整的参数。',steps:['选择业务分类，查看当前生效版本与生效范围。','修改参数后可先预览；保存草稿，再执行服务端校验。','核对差异和影响范围，填写原因后发布；修改草稿会使旧校验失效。']},
 settings:{tag:'展示与运行配置',description:'维护固定模板、场景和动作素材，或管理养宠功能的独立运行开关。',steps:['选择固定模板与素材，查看阶段与动作表现；选择运行开关，管理各功能启停。','修改后核对预览与完整差异，保存草稿并完成服务端校验。','确认生效范围并填写原因后发布；素材与运行开关各自保留独立版本。']},
 ai:{tag:'表达与内容配置',description:'按触发场景维护宠物文案，先用固定模板预览，再按需要进行模型测试。',steps:['选择即时表达、日总结、期间摘要、回访或生日场景。','维护对应文案与模拟事实；模板预览不发起模型请求。','模型测试会消耗调试及全局额度；正式生效仍需保存、校验并发布。']},
 tasks:{tag:'异常排查与处理',description:'从任务查原因、从宠物修状态、从文字核对来源。选择与你遇到的问题对应的处理入口。',steps:['任务排查：查询任务，查看失败原因、源事实和处理资格。','单宠修复：填写宠物标识，核对修复差异及依据后再执行。','文字处理：读取原文与事实，按权限隐藏、更正或申请重新生成。']},
 versions:{tag:'变更追溯',description:'查询配置变更与后台操作，核对版本差异、引用依据及操作结果。',steps:['配置版本用于比较历史配置；操作日志用于追查谁在何时做了什么。','打开版本详情查看完整差异、当前有效性及关联记录。','需要恢复时，将选定历史内容校验并发布为新版本，保留历史记录。']}
};
const extraLabels={operation_id:'操作标识',configuration:'连接配置',base_url:'服务地址',timeout_seconds:'请求超时（秒）',credential_configured:'凭据是否已配置',configuration_id:'配置摘要',activation:'配置生效方式',resolved:'最终思考模式',parameter:'请求参数',workflow:'当前场景',global:'全局设置',age_days:'当前年龄（天）',life_days:'共同生活（天）',tier:'陪伴档位',account:'账号状态',profile:'宠物档案',current_version:'当前生效版本',draft_revision:'草稿修订',editable:'是否可编辑',valid:'校验通过',valid_now:'当前校验通过',blocked:'阻塞原因',protection:'历史记录保护',configuration_ids:'关联配置',task:'任务详情',attempt:'请求详情',facts:'源事实',texts:'正式文字',attempts:'请求尝试',rule_jobs:'规则任务',anomaly:'异常提示',usage:'模型用量',elapsed:'请求耗时',elapsed_ms:'耗时（毫秒）',template_fallback:'固定模板回退',input_tokens:'输入 Token',output_tokens:'输出 Token',complete_count:'完整回执数',missing_count:'缺失回执数',basis:'统计依据',known_count:'已知数量',mean_ms:'平均耗时（毫秒）',maximum_ms:'最长耗时（毫秒）',count:'数量',task_ids:'关联任务标识',reasons:'原因分布',global_ids:'全局并发请求',debug_ids:'调试并发请求',global_limit:'全局并发上限',debug_limit:'调试并发上限',layer:'额度层级',bucket:'统计分组',consumed_ids:'已消耗请求',reserved_ids:'有效预留请求',unknown_ids:'未知结果请求',coverage:'运行覆盖',runs:'运行记录',producers:'生产任务',pending_ids:'待处理标识',oldest_pending:'最早待处理时间',available:'是否可用',thinking:'全局思考模式',workflow_thinking:'场景思考模式',templates:'固定模板',workflows:'场景配置',prompt:'提示词',text_target:'目标字数',text_max:'字数上限',model:'模型',provider:'供应商',problems:'连接问题',configured:'是否已配置',current:'当前状态',rebuilt:'重建后状态',fact_ids:'事实依据',basis_digest:'依据摘要',recorded:'已记录',source_photo_cleared:'来源照片已清理'};
A.label=k=>extraLabels[k]||null;
const states={queued:'排队中',claimed:'已认领',requesting:'请求中',succeeded:'成功',retryable_failed:'可重试失败',final_failed:'最终失败',policy_skipped:'策略略过',superseded:'已失效',unknown:'结果未知',pending:'待处理',running:'运行中',done:'完成',blocked:'受阻',error:'异常',obsolete:'已过时',consumed:'已消耗',reserved:'已预留',released:'已释放',active:'正常',disabled:'停用',puppy:'幼犬',growing:'成长期',adult:'成年',daily:'日常陪伴',short:'短期离开',long:'较长离开',extended:'长期离开',immediate:'即时表达',period:'期间摘要',return:'回访回顾',debug:'调试',global:'全局',user:'用户',narrative:'叙事',offline:'离开期间',rules:'成长、互动与成本',appearance:'固定模板与素材',runtime:'运行开关',ai:'AI 表达',copy:'文字处理',fault:'故障处理',repair:'状态修复',publish:'发布',rollback:'回滚',disable:'停用',actual_execution:'实际执行',rule_settlement:'规则结算',observed:'已有运行证据',not_covered:'尚无运行证据'};
A.term=(v)=>states[v]||v;
A.formatTime=value=>{if(!value)return '暂无记录';const text=String(value),date=new Date(/T/.test(text)&&!/(Z|[+-]\d\d:\d\d)$/.test(text)?text+'Z':text);return Number.isNaN(date.getTime())?text:new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'short',timeStyle:'short',hour12:false}).format(date);};
A.kind=v=>({immediate:'即时表达',daily:'日总结',period:'期间摘要',return:'回访回顾',care:'自动照顾',birthday:'生日纪念',settlement:'状态结算',daily_overview:'每日聚合'}[v]||A.term(v));
A.value=(key,value)=>{if(typeof value==='boolean')return A.el('span',value?'是':'否',{class:'pet-badge '+(value?'is-success':'is-neutral')});
 if(['state','stage','tier','band','account','domain','origin','source','coverage','action','layer'].includes(key)&&states[value]){const box=A.el('span',undefined,{class:'pet-enum'});box.append(A.el('span',states[value],{class:'pet-badge '+(['error','final_failed','blocked','unknown'].includes(value)?'is-warning':['succeeded','done','active'].includes(value)?'is-success':'is-neutral')}),A.el('small',String(value),{class:'pet-raw'}));return box;}return null;};
const formNames={thinking:'全局思考模式',workflow_thinking:'各场景思考模式',workflows:'场景文案配置',templates:'固定模板文案',immediate:'即时表达与邀请',daily:'日总结',period:'期间摘要',return:'回访回顾',prompt:'场景提示词',target:'正文目标字数',max:'正文最多字数',maximum:'正文最多字数',title_max:'标题最多字数',text_target:'正文目标字数',text_max:'正文最多字数'};
const templateNames={welcome:'领养欢迎',fallback:'通用回退文案',touch:'抚摸完成',feed:'喂食完成',play:'陪玩完成',joint_ball:'共同玩球完成',joint_photo:'共同留影完成',refuse_feed:'吃饱后拒绝喂食',low_energy:'精力不足提示',touch_incomplete:'抚摸未完成',rest:'休息提示',invite:'共同玩球邀请',preference_learning:'偏好了解中',birthday:'生日纪念',return_title:'回访标题',return_body:'回访正文',return_empty:'回访无新增事实'};
A.formLabel=(meta,key,path)=>{if(path[0]==='templates')return templateNames[key]||meta.label||key;return (key==='maximum'&&path[0]!=='workflows'?undefined:formNames[key])||(!meta.label||meta.label.startsWith('.')?A.label(key)||key:meta.label);};
A.formHint=(meta,key,path)=>{
 const unit=meta.unit&&meta.unit!=='数值'?meta.unit:'';
 const fixed=meta.range&&!['有限数值；按所在组联合校验','已实现标识或受限模板；服务端校验'].includes(meta.range)?meta.range:'';
 let hint='';
 if(path[0]==='templates')hint='用于对应场景的固定表达，可使用受支持的变量。';
 else if(key==='prompt')hint='描述本场景的表达要求；内容应依据传入的事实。';
 else if(['target','text_target'].includes(key))hint='期望生成的正文长度。';
 else if((['max','text_max','title_max'].includes(key)||(key==='maximum'&&path[0]==='workflows')))hint='限制输出长度，发布前会检查相关配置。';
 else if(path.includes('hourly'))hint='每小时的状态变化；负数表示下降。';
 else if(path[0]==='state'&&path.includes('initial'))hint='宠物领养时的初始状态。';
 else if(path[0]==='state'&&path.includes('minimum'))hint='状态下降时保留的下限。';
 else if(path[0]==='state'&&path.includes('maximum'))hint='状态能够达到的上限。';
 else if(key==='thinking')hint='各场景未单独指定时，使用这里的思考模式。';
 else if(path[0]==='workflow_thinking')hint='跟随全局或为当前场景单独指定。';
 return [unit,hint,fixed].filter(Boolean).join(' · ');
};
A.sectionTabs=(label,items,current,params)=>{const nav=A.el('nav',undefined,{class:'pet-tabs pet-section-tabs','aria-label':label});for(const[key,title,extra]of items){const a=A.link(title,{...params,...extra});if(key===current)a.setAttribute('aria-current','page');nav.append(a);}return nav;};
A.taskMode=p=>p.id?'tasks':p.text?'text':p.repair||p.pet?'repair':['repair','text'].includes(p.mode)?p.mode:'tasks';
A.pageIntro=(section,box)=>{
 const guide=guides[section]||guides.overview;
 box.classList.add('pet-page');
 box.querySelector(':scope > h2')?.remove();
 const header=A.el('header',undefined,{class:'pet-page-intro'});
 const text=A.el('div');
 const titles={overview:'概览',pets:'宠物与记录',rules:'规则与成本',settings:'素材与运行配置',ai:'AI 与文案',tasks:'任务与修复',versions:'版本与操作日志'};
 text.append(A.el('p','养宠管理 / '+guide.tag,{class:'pet-eyebrow'}),
  A.el('h1',titles[section]||'养宠管理'),A.el('p',guide.description,{class:'pet-page-description'}));
 const tools=A.el('div',undefined,{class:'pet-page-tools'});
 if(A.permissions.role==='observer')tools.append(A.el('span','只读',{class:'pet-badge is-neutral'}));
 const help=A.el('details',undefined,{class:'pet-help'});
 const list=A.el('ol');
 for(const step of guide.steps)list.append(A.el('li',step));
 help.append(A.el('summary','使用指南'),list);
 tools.append(help);header.append(text,tools);
 const mobile=A.el('details',undefined,{class:'pet-mobile-nav'});
 const nav=A.el('nav',undefined,{'aria-label':'养宠管理导航'});
 for(const [key,title] of Object.entries(titles)){
  const a=A.link(title,{section:key});
  if(key===section)a.setAttribute('aria-current','page');
  nav.append(a);
 }
 mobile.append(A.el('summary','养宠导航 · '+(titles[section]||'概览')),nav);
 box.prepend(mobile,header);
};

A.context=(title,text)=>{const box=A.el('aside',undefined,{class:'pet-context'});box.append(A.el('strong',title),A.el('p',text));return box;};
A.diagnostic=(title,data)=>{
 const details=A.el('details',undefined,{class:'pet-inline-details'});
 details.append(A.el('summary',title),A.fields(data));
 return details;
};
A.reasonLabel=reason=>({
 send_unknown:'请求结果未知',invalid_output:'模型输出未通过校验',global_exhausted:'全局额度用尽',
 task_not_retryable:'当前状态不可重试',task_expired:'任务已过期',
 budget_exhausted:'请求额度用尽',no_new_facts:'没有新增事实',
 provider_unavailable:'模型服务暂不可用',source_facts_missing:'来源事实缺失',
 global_configuration_incomplete:'全局额度或并发未配置'
})[reason]||'查看原因详情';

A.decorate=box=>{
 for(const form of box.querySelectorAll('form.pet-toolbar')){
  form.classList.add('pet-filter');const advanced=A.el('details',undefined,{class:'pet-filter-advanced'}),grid=A.el('div',undefined,{class:'pet-filter-grid'});advanced.append(A.el('summary','更多筛选 · 时间与精确定位'),grid);
  for(const label of [...form.children].filter(n=>n.tagName==='LABEL')){const input=label.querySelector('[name]');if(input&&['start','end','reason','validity','unknown','admin_id','operation_id','object_id'].includes(input.name)){grid.append(label);if(input.value)advanced.open=true;}}
  const actions=A.el('div',undefined,{class:'pet-filter-actions'});for(const n of [...form.children])if(n.tagName==='BUTTON'||n.tagName==='A'){if(n.tagName==='BUTTON'){n.classList.add('btn','btn-primary');n.type='submit';}actions.append(n);}if(grid.children.length)form.append(advanced);form.append(actions);
 }
 for(const button of box.querySelectorAll('button:disabled[title]')){if(button.title)button.after(A.el('span',button.title,{class:'pet-disabled-reason'}));}
 for(const table of box.querySelectorAll('.pet-table')){
  if(table.parentElement.classList.contains('pet-table-scroll'))continue;
  const wrap=A.el('div',undefined,{class:'pet-table-scroll',tabindex:'0','aria-label':'记录表格'});
  table.before(wrap);wrap.append(table);
 }
 for(const p of box.querySelectorAll('p'))if(/^没有符合|^暂无该|^暂无记录/.test(p.textContent))p.classList.add('pet-empty');
};
})();

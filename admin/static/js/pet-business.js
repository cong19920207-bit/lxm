/* Structured business controls over the existing, single revisioned draft. */
(()=>{'use strict';const A=window.PetAdmin;
const stageNames={puppy:'幼犬',growing:'成长期',adult:'成年'};
function select(options,value,change,label){const n=A.el('select',undefined,{'aria-label':label});for(const[k,v]of Object.entries(options))n.append(A.el('option',v,{value:k}));n.value=value;n.onchange=()=>change(n.value);return n;}
function input(label,value,change,type='text'){const l=A.el('label',label),i=A.el('input',undefined,{type,value,'aria-label':label});if(type==='number')i.step='any';i.oninput=()=>change(type==='number'?Number(i.value):i.value);l.append(i);return l;}
function check(label,value,change){const l=A.el('label',label),i=A.el('input',undefined,{type:'checkbox','aria-label':label});i.checked=value;i.onchange=()=>change(i.checked);l.append(i);return l;}
function choose(label,options,value,change){const l=A.el('label',label);l.append(select(options,value,change,label));return l;}
A.confirmImpact=async(title,data,reason)=>new Promise(resolve=>{
 const focused=document.activeElement;
 const dialog=A.el('dialog',undefined,{class:'pet-confirm','aria-labelledby':'pet-confirm-title'});
 dialog.append(A.el('h2',title,{id:'pet-confirm-title'}));
 if(data.scope)dialog.append(A.el('p',data.scope,{class:'pet-confirm-scope'}));
 dialog.append(A.el('p','操作原因：'+reason,{class:'pet-meta'}));
 const {full_diff,scope,...details}=data;
 if(full_diff){
  const diff={};
  for(const [key,pair] of Object.entries(full_diff))Object.assign(diff,A.changeDiff(pair.before,pair.after,key));
  const target=data.target_version!=null?'所选版本值':'待发布值';
  dialog.append(A.el('h3','变更明细'),A.renderDiff(diff,{before:'当前生效值',after:target}));
 }
 const evidence=A.el('details',undefined,{class:'pet-inline-details'});
 evidence.append(A.el('summary','查看操作依据'),A.fields(details));
 dialog.append(evidence);
 const controls=A.el('div',undefined,{class:'pet-toolbar pet-confirm-actions'});
 const finish=accepted=>{dialog.close();dialog.remove();focused?.focus();resolve(accepted);};
 const cancel=A.button('返回修改',()=>finish(false));
 const submit=A.button('确认提交',()=>finish(true));submit.classList.add('btn-primary');
 controls.append(cancel,submit);dialog.append(controls);
 dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false);},{once:true});
 document.body.append(dialog);dialog.showModal();cancel.focus();
});

function simulator(s,box){const details=A.el('details'),summary=A.el('summary','自定义模拟条件（展开）');details.append(summary);box.append(details);const i=s.inputs,c=s.value,area=A.card('模拟条件 · 只读推演，不写真实宠物'),basic=A.el('div',undefined,{class:'pet-form-grid'});area.append(basic);
for(const[k,label,type]of [['date','模拟计算时间 UTC'],['birth_date','模拟出生日期','date'],['hours','距结算小时数','number'],['duration_ms','实际动作时长（毫秒）','number'],['daily_reward_used','当日已用亲近收益','number'],['closeness','当前亲近','number'],['reward_elapsed_seconds','距同类收益秒数','number'],['care_used','当日照顾次数','number'],['care_elapsed_hours','距同类照顾小时数','number'],['invite_elapsed_seconds','距上次邀请秒数','number'],['concurrent','当前全局并发','number'],['debug_concurrent','当前调试并发','number'],['last_active_at','最近有效活跃 UTC']])basic.append(input(label,i[k]??0,v=>i[k]=v,type));
basic.append(choose('模拟动作',{touch:'抚摸',feed:'喂食',play:'陪玩',joint_ball:'共同玩球'},i.action,v=>i.action=v),choose('模拟阶段',stageNames,i.stage,v=>i.stage=v),choose('请求来源',{interactive:'实际互动',offline:'离开期间',return:'回访',debug:'调试'},i.origin,v=>i.origin=v),choose('共同事件发起者',{user:'用户主动',invitation:'受邀'},'user',v=>i.initiator=v));
for(const[k,label,v]of [['occupied','已有活动占用',false],['already_rewarded','本收益族已经给过奖励',false],['absence_ended','离开区间已由有效参与结束',true],['important_facts','有新增重要事实',true]]){i[k]=v;basic.append(check(label,v,x=>i[k]=x));}
for(const group of ['values','remaining'])for(const k of Object.keys(i[group]))basic.append(input(`${group==='values'?'保存状态':'剩余额度'} · ${k}`,i[group][k],v=>i[group][k]=v,'number'));
const bound=A.el('fieldset');bound.append(A.el('legend','领养时绑定的成长曲线'),check('使用已绑定成长曲线',false,on=>{if(on)i.bound_growth={...c.growth};else delete i.bound_growth;}));for(const k of Object.keys(c.growth||{}))bound.append(input(k==='puppy_until_days'?'绑定成长期起点（天）':'绑定成年起点（天）',c.growth[k],v=>{i.bound_growth={...(i.bound_growth||c.growth),[k]:v};},'number'));area.append(bound);
const segmentBox=A.el('fieldset'),segments=[];segmentBox.append(A.el('legend','跨规则版本的状态分段'));const segmentRows=A.el('div');function drawSegments(){segmentRows.replaceChildren();segments.forEach((seg,index)=>{const row=A.el('div',undefined,{class:'pet-form-grid'});row.append(input('分段版本',seg.version,v=>seg.version=v),input('分段小时数',seg.hours,v=>seg.hours=v,'number'));for(const k of ['satiety','energy','mood'])row.append(input('每小时 · '+k,seg.state.hourly[k],v=>seg.state.hourly[k]=v,'number'));row.append(A.button('移除该分段',()=>{segments.splice(index,1);i.segments=segments.length?segments:undefined;drawSegments();}));segmentRows.append(row);});}segmentBox.append(segmentRows,A.button('添加状态分段',()=>{segments.push({version:'模拟版本 '+(segments.length+1),hours:6,state:structuredClone(c.state)});i.segments=segments;drawSegments();}));area.append(segmentBox);
const reactions=A.el('fieldset'),rows=A.el('div');reactions.append(A.el('legend','逐条反应证据'),A.el('p','可比较实际反应、浏览、AI 评论及重复来源；预览解释逐条纳入或排除。'));function draw(){rows.replaceChildren();i.reactions.forEach((r,index)=>{const row=A.el('div',undefined,{class:'pet-form-grid'});row.append(input('反应源标识',r.id,v=>r.id=v),choose('来源',{actual_execution:'实际执行',rule_settlement:'规则结算',ai_comment:'AI 评论',view:'浏览'},r.source,v=>r.source=v),input('反应类型',r.type,v=>r.type=v),choose('反应结果',{responded:'已回应',refused:'拒绝'},r.outcome,v=>r.outcome=v),choose('反应发生阶段',stageNames,r.scene,v=>r.scene=v),check('实际完成',r.completed,v=>r.completed=v),check('玩家实际参与',r.participants.includes('player'),v=>r.participants=v?['player']:[]),check('原规则下符合证据条件',r.original_rule_eligible,v=>r.original_rule_eligible=v),A.button('移除反应',()=>{i.reactions.splice(index,1);draw();}));rows.append(row);});}reactions.append(rows,A.button('添加反应证据',()=>{i.reactions.push({id:crypto.randomUUID(),source:'actual_execution',type:c.preferences?.reaction_type||'lean_towards_hand',outcome:'responded',scene:'puppy',completed:true,participants:['player'],original_rule_eligible:true});draw();}));area.append(reactions);const output=A.card('自定义推演结果');area.append(A.button('按这些条件运行纯规则预览',async()=>{try{const value=await A.api('/preview/rules',s.c.editable?'POST':'GET',s.c.editable?{content:c,inputs:i}:null);output.replaceChildren(A.fields(value));}catch(e){output.replaceChildren(A.el('p',e.message,{class:'pet-error'}));}}),output);if(!s.c.editable){for(const n of area.querySelectorAll('input,select,textarea'))n.disabled=true;area.prepend(A.el('p','当前角色仅查看已发布配置的默认模拟预览。',{class:'pet-meta'}));}details.append(area);
}
function finiteSteps(s,form){const joint=s.value.joint;if(!joint)return;const stages=form.querySelector('[data-config-group="joint.allowed_stages"]');if(stages){stages.replaceChildren(A.el('legend','适用成长阶段'));for(const[k,label]of Object.entries(stageNames)){const field=check(label,joint.allowed_stages.includes(k),on=>{joint.allowed_stages=on?[...joint.allowed_stages,k]:joint.allowed_stages.filter(x=>x!==k);s.changed();});field.querySelector('input').disabled=!s.c.editable;stages.append(field);}}const holder=form.querySelector('[data-config-group="joint.steps"]');if(!holder)return;const caps=s.c.action_capabilities||{},body=A.el('div');holder.replaceChildren(A.el('legend','共同事件步骤 · 仅已实现能力'),body);function draw(){body.replaceChildren();joint.steps.forEach((key,index)=>{const row=A.el('div',undefined,{class:'pet-step-row'}),cap=caps[key]||{};row.append(select(Object.fromEntries(Object.entries(caps).map(([k,v])=>[k,v.label])),key,v=>{joint.steps[index]=v;s.changed();draw();},'第'+(index+1)+'步动作'),A.el('span',`${cap.actor||'未知参与者'} · ${cap.completion||'未实现完成点'}`));for(const[txt,delta]of [['上移',-1],['下移',1]]){const b=A.button(txt,()=>{const j=index+delta;[joint.steps[index],joint.steps[j]]=[joint.steps[j],joint.steps[index]];s.changed();draw();});b.disabled=!s.c.editable||index+delta<0||index+delta>=joint.steps.length;row.append(b);}const remove=A.button('移除步骤',()=>{joint.steps.splice(index,1);s.changed();draw();});remove.disabled=!s.c.editable;row.append(remove);body.append(row);});const add=A.button('添加已实现步骤',()=>{const next=Object.keys(caps).find(k=>!joint.steps.includes(k));if(next){joint.steps.push(next);s.changed();draw();}});add.disabled=!s.c.editable||joint.steps.length>=Object.keys(caps).length;body.append(add,A.el('p','必须依次保留玩家有效递球→小梦接应→狗狗回应。非法删减或排序不能通过发布校验。',{class:'pet-meta'}));for(const n of body.querySelectorAll('select'))n.disabled=!s.c.editable;}draw();
}
async function resources(s,box){const area=A.card('已审核资源登记与引用'),list=A.el('div');area.append(list);box.append(area);try{const d=await A.api('/resources');const grid=A.el('div',undefined,{class:'pet-asset-grid'});for(const r of d.items){const item=A.el('article');const img=A.el('img',undefined,{src:r.uri,alt:r.id});item.append(img,A.el('strong',r.id),A.el('p',`${r.version} · ${r.available?'可用':'不可用'} · ${r.stages.map(x=>stageNames[x]).join(' / ')}`),A.el('details'));item.lastChild.append(A.el('summary','能力与保护引用'),A.fields({actions:r.actions,capabilities:r.capabilities,references:r.references}));grid.append(item);}list.append(grid);
const mapping=box.querySelector('[data-config-group="actions"]');if(mapping){const body=A.el('div');mapping.replaceChildren(A.el('legend','已实现动作资源映射'),body);for(const action of d.actions){const label=A.el('label',action),control=select({'':'默认已审核表现',...Object.fromEntries(d.items.filter(r=>r.actions.includes(action)&&(r.capabilities?.actor||'dog')==='dog').map(r=>[r.id,r.id]))},s.value.actions[action]||'',v=>{if(v)s.value.actions[action]=v;else delete s.value.actions[action];s.changed();},'动作映射 '+action);control.disabled=!s.c.editable;label.append(control);body.append(label);}}
if(!A.can('resource.register','appearance'))return;const form=A.el('fieldset');form.append(A.el('legend','登记已审核的项目静态资源'));const r={id:'',version:'',uri:'/static/pet-assets/',identity_key:'fixed-dog-v4',stages:['puppy','growing','adult'],actions:['idle'],sha256:'',source:'',actor:'dog',fallback:'static'};for(const[k,label]of [['id','不可变资源标识'],['version','资源版本'],['uri','项目静态资源路径'],['sha256','审核文件 SHA256'],['source','审核来源与依据']])form.append(input(label,r[k],v=>r[k]=v));form.append(choose('参与者',{dog:'狗狗',prop:'场景或道具'},r.actor,v=>r.actor=v),choose('降级能力',{static:'静态表现',none:'不可降级'},r.fallback,v=>r.fallback=v));for(const[k,label]of Object.entries(stageNames))form.append(check('适用阶段 · '+label,true,on=>r.stages=on?[...r.stages,k]:r.stages.filter(x=>x!==k)));for(const k of d.actions)form.append(check('支持动作 · '+k,r.actions.includes(k),on=>r.actions=on?[...r.actions,k]:r.actions.filter(x=>x!==k)));let reason='';const result=A.card('登记结果');form.append(input('资源登记原因','',v=>reason=v));const storage='pet-resource-operation';form.append(A.button('校验并登记资源版本',async()=>{try{if(!reason.trim())throw Error('请填写登记原因');if(sessionStorage.getItem(storage))throw Error('先查询原资源登记操作');const id=crypto.randomUUID();sessionStorage.setItem(storage,id);const saved=await A.api('/resources','POST',{operation_id:id,reason,resource:r});result.replaceChildren(A.fields(saved));const registered=saved.result?.resource||saved.resource;if(registered){for(const action of registered.actions||[]){const select=box.querySelector('select[aria-label="动作映射 '+action+'"]');if(select&&![...select.options].some(o=>o.value===registered.id))select.append(A.el('option',registered.id,{value:registered.id}));}const item=A.el('article');item.append(A.el('img',undefined,{src:registered.uri,alt:registered.id}),A.el('strong',registered.id),A.el('p','已登记，可以用于当前草稿'));grid.prepend(item);}sessionStorage.removeItem(storage);}catch(e){if(e.confirmed)sessionStorage.removeItem(storage);result.replaceChildren(A.el('p',e.message,{class:'pet-error'}));}}),A.button('查询原资源登记结果',async()=>{try{const id=sessionStorage.getItem(storage);if(!id)throw Error('没有待核对登记');const v=await A.api('/operations/'+id);result.replaceChildren(A.fields(v));if(['done','blocked'].includes(v.state))sessionStorage.removeItem(storage);}catch(e){result.replaceChildren(A.el('p',e.message));}}),result);area.append(form);
}catch(e){list.append(A.el('p','资源读取失败：'+e.message,{class:'pet-error'}));}}
const groups={
 growth:['成长与互动',['growth','state','rewards','interaction','initial_age_days','name_max_length'],'调整成长门槛、状态变化和互动收益。成长曲线在新领养时绑定。'],
 events:['共同与居家事件',['joint'],'配置共同玩球的适用阶段、发起方式与完成步骤。'],
 preference:['偏好发现',['preferences'],'设置稳定偏好及发现所需的真实反应。'],
 care:['自动照顾',['care'],'设置自动照顾的触发门槛和间隔。请求额度与陪伴档位在预算页签维护。'],
 budget:['预算、叙事与回访',['costs','narrative','return','birthday'],'设置请求额度、并发、陪伴档位、叙事窗口和回访规则。']
};
A.markConfigTabs=(box,paths)=>{
 for(const button of box.querySelectorAll('button[data-group],button[data-workflow]')){
  button.querySelector('.pet-change-count')?.remove();
  const group=groups[button.dataset.group];
  const count=group ? paths.filter(path=>group[1].includes(path.split('.')[0])).length
   : A.workflowChangeCount?.(button.dataset.workflow,paths);
  if(count)button.append(A.el('span',String(count),{class:'pet-change-count','aria-label':count+' 项待发布修改'}));
 }
};
const edit=A.editDomain;
A.editDomain=async(domain,box,current)=>{
 const s=await edit(domain,box,current);
 if(!s)return;
 if(domain==='rules'){
  const nav=A.el('nav',undefined,{class:'pet-tabs','aria-label':'规则业务分组'});
  const form=box.querySelector('.pet-config-form');
  const help=A.context('','');
  function show(key){
   const [,fields,description]=groups[key];
   help.replaceChildren(A.el('p',description));
   if(key==='care')help.append(A.button('查看额度与档位',()=>show('budget')));
   for(const field of form.children){
    const path=field.dataset.configGroup||field.querySelector('[data-field]')?.dataset.field;
    field.hidden=!fields.includes(path);
   }
   for(const button of nav.querySelectorAll('button'))button.setAttribute('aria-selected',String(button.dataset.group===key));
  }
  for(const [key,[name,fields]] of Object.entries(groups)){
   const button=A.button(name,()=>show(key));
   button.dataset.group=key;
   button.dataset.configKeys=fields.join(' ');
   nav.append(button);
  }
  box.insertBefore(nav,box.querySelector('.pet-workflow'));
  nav.after(help);
  const selected=new URLSearchParams(location.search).get('group');
  show(Object.hasOwn(groups,selected)?selected:'growth');
  finiteSteps(s,form);simulator(s,box);s.refresh();
 }else if(domain==='appearance')await resources(s,box);
 return s;
};
A.simInput={input,check,choose,select};
})();

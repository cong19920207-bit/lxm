(()=>{'use strict';const A=window.PetAdmin;
A.changeDiff=(before,after,path='')=>{if(before&&after&&typeof before==='object'&&typeof after==='object'){const r={};for(const k of new Set([...Object.keys(before),...Object.keys(after)]))Object.assign(r,A.changeDiff(before[k],after[k],path?path+'.'+k:k));return r;}return JSON.stringify(before)===JSON.stringify(after)?{}:{[path]:{before,after}};};
A.compactValue=v=>v===undefined||v===null?'未设置':typeof v==='boolean'?v?'开启':'关闭':typeof v==='object'?JSON.stringify(v):String(v);
A.configError=message=>{const m=String(message);if(m.startsWith('model_test_required:'))return '以下场景需通过当前草稿的真实模型测试：'+m.split(':')[1].split(',').map(k=>({immediate:'即时表达',daily:'日总结',period:'期间摘要',return:'回访回顾'})[k]||k).join('、');return ({draft_or_base_changed:'草稿或生效版本已变化，请保留本地修改并重新核对。',draft_missing:'该草稿已删除或不存在。',restore_thinking_default_conflict:'历史场景使用供应商默认思考模式，与当前全局模式不同；请先核对全局思考配置。',global_budget_required:'请先发布正数的全局每日额度和全局并发。',validation_not_bound:'校验与当前草稿不匹配，请重新校验。'})[m]||m;};
A.renderDiff=(diff,{before='生效值',after='草稿值',empty='两份配置内容一致。',schema}={})=>{
 const box=A.el('div',undefined,{class:'pet-diff-list'});
 if(!Object.keys(diff).length)box.append(A.el('p',empty,{class:'pet-meta'}));
 for(const [path,value] of Object.entries(diff)){
  const row=A.el('div',undefined,{class:'pet-diff-row'});
  let meta=schema;
  const keys=path.split('.');
  const title=keys.map((key,index)=>{
   meta=meta?.children?.[key]||meta?.items?.[key];
   return meta?A.formLabel(meta,key,keys.slice(0,index)):A.label(key)||key;
  }).join(' / ');
  row.append(A.el('strong',title),A.el('small',path,{class:'pet-raw'}),
   A.el('p',before+'：'+A.compactValue(value.before)),
   A.el('p',after+'：'+A.compactValue(value.after)));
  box.append(row);
 }
 return box;
};
A.attachDraftHistory=(s,box,controls)=>{const area=A.card('草稿与发布历史');area.classList.add('pet-config-history');area.hidden=true;box.append(area);let page=1,selectedWorkflow=null;
const filter=content=>{if(!selectedWorkflow)return content;if(selectedWorkflow==='birthday')return {templates:{birthday:content.templates?.birthday}};return {workflows:{[selectedWorkflow]:content.workflows?.[selectedWorkflow]},workflow_thinking:{[selectedWorkflow]:content.workflow_thinking?.[selectedWorkflow]},thinking:content.thinking};};
const pending='pet-history-operation:'+s.domain;
function pendingRequest(){const raw=sessionStorage.getItem(pending);if(!raw)return null;try{return JSON.parse(raw);}catch{return {operation_id:raw};}}
function showError(e){area.hidden=false;area.append(A.el('p',A.configError(e.message),{class:'pet-error'}));}
let sending=false;
async function sendRequest(request){
 if(sending)return;
 sending=true;
 const sequence=s.editSequence;
 try{
  await A.api(request.url,request.method,request.payload);
  sessionStorage.removeItem(pending);
  if(sequence===s.editSequence){s.resetDirty();await A.render();}
  else await s.sync();
 }catch(e){if(e.confirmed)sessionStorage.removeItem(pending);showError(e);}
 finally{sending=false;}
}
async function mutate(title,url,method,body){try{if(s.busy||sending)throw Error('请等待当前配置操作完成。');s.requireIdleDraft();if(pendingRequest())throw Error('有结果待核对的历史操作，请先查询或重试原操作。');const impact={current_version:s.base,draft_revision:s.revision,scope:s.dirty?'此操作会舍弃页面尚未保存的修改。':'生效配置与已发布历史版本保留。',...body};if(!await A.confirmImpact(title,impact,title))return;const operation_id=crypto.randomUUID(),request={operation_id,url,method,payload:{operation_id,reason:title,expected_revision:s.revision,base_version:s.base,...body}};sessionStorage.setItem(pending,JSON.stringify(request));await sendRequest(request);}catch(e){showError(e);}}

const deleteButton=revision=>A.button('删除草稿 D'+revision,()=>mutate('确认删除草稿 D'+revision,'/config/'+s.domain+'/drafts/'+revision,'DELETE',{}));
async function draw(){area.hidden=false;area.replaceChildren(A.el('h2',selectedWorkflow?'当前场景的草稿与发布历史':'草稿与发布历史'),A.el('p','每次有变动的保存都会留存草稿修订。历史恢复为新草稿，核对后再发布。',{class:'pet-meta'}));try{const d=await A.api('/config/'+s.domain+'/drafts?page='+page);for(const[type,rows]of [['draft',d.drafts],['version',d.versions]]){const section=A.el('div');section.append(A.el('h3',type==='draft'?'保存过的草稿':'已发布版本'));if(!rows.length)section.append(A.el('p','暂无记录。',{class:'pet-meta'}));for(const r of rows){const id=type==='draft'?r.revision:r.version,row=A.el('article',undefined,{class:'pet-history-row'});row.append(A.el('strong',(type==='draft'?'草稿 D':'版本 v')+id+(r.current?(type==='draft'?' · 当前草稿':' · 当前生效'):'')),A.el('p',type==='draft'?`基于 v${r.base_version} · ${A.formatTime(r.saved_at)} · 保存人 #${r.saved_by??'未知'}`:A.formatTime(r.effective_at),{class:'pet-meta'}));const more=A.el('details');more.append(A.el('summary','与当前编辑内容比较'),A.renderDiff(A.changeDiff(filter(s.value),filter(r.content)),{before:'当前编辑值',after:type==='draft'?'历史草稿值':'所选版本值',schema:s.c.schema}));row.append(more);if(s.c.editable){row.append(A.button(selectedWorkflow?'恢复此场景为新草稿':'恢复为新草稿',()=>mutate('确认恢复'+(type==='draft'?'草稿 D':'版本 v')+id+(selectedWorkflow?' 中的当前场景':''),'/config/'+s.domain+'/restore','POST',{source_type:type,...(type==='draft'?{source_revision:id}:{source_version:id}),...(selectedWorkflow?{workflow:selectedWorkflow}:{})})));if(type==='draft')row.append(deleteButton(id));}section.append(row);}area.append(section);}const pager=A.el('div',undefined,{class:'pet-toolbar'});const prev=A.button('上一页',()=>{page--;draw();});prev.disabled=page<=1;const next=A.button('下一页',()=>{page++;draw();});next.disabled=page*d.page_size>=Math.max(d.draft_total,d.version_total);pager.append(prev,A.el('span','第 '+page+' 页'),next,A.button('收起历史',()=>area.hidden=true));area.append(pager);A.decorate(area);}catch(e){area.append(A.el('p',A.configError(e.message),{class:'pet-error'}));}}
s.openHistory=workflow=>{selectedWorkflow=workflow||null;page=1;draw();};controls.append(A.button(s.domain==='ai'?'整套配置历史与恢复':'历史与恢复',()=>s.openHistory()));if(s.c.editable&&s.c.draft_state!=='none')controls.append(A.button('删除当前草稿',()=>mutate('确认删除当前草稿 D'+s.revision,'/config/'+s.domain+'/drafts/'+s.revision,'DELETE',{})));
controls.append(A.button('查询历史操作结果',async()=>{const request=pendingRequest();try{if(!request)throw Error('没有待核对的历史操作。');const r=await A.api('/operations/'+encodeURIComponent(request.operation_id));s.result.replaceChildren(A.fields(r));if(['done','blocked'].includes(r.state)){sessionStorage.removeItem(pending);if(r.state==='done'){if(s.dirty)await s.sync();else await A.render();}}}catch(e){if(request&&!request.payload&&(e.status===404||e.message==='operation_not_found'))sessionStorage.removeItem(pending);showError(e);}}),A.button('重试原历史操作',async()=>{const request=pendingRequest();if(!request?.payload){showError(Error('没有可重试的历史操作；如有旧操作，请先查询结果。'));return;}await sendRequest(request);}));
};})();

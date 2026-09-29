(function () {
  'use strict';
  if (!checkAdminLogin()) return;
  const role=getAdminRole(), readers=['super_admin','ops_admin','observer'];
  if (!readers.includes(role)) {location.replace('error.html?type=403');return;}
  const $=id=>document.getElementById(id);
  $('sidebar-mount').innerHTML=renderSidebar('voice-calls');
  $('header-mount').innerHTML=renderHeader('通话记录');
  const labels={user_id:'用户',call_id:'通话标识',created_at:'开始时间',connected_at:'接通时间',ended_at:'结束时间',
    status:'状态',end_reason:'结束原因',duration_seconds:'时长（秒）',free_seconds_used:'免费秒数',extra_seconds_used:'额外秒数',
    grace_seconds:'收尾秒数',growth_eligible_seconds:'成长有效秒数',growth_points:'成长值',provider:'Provider',
    model_version:'模型',voice_id:'音色',config_version:'配置版本',summary_status:'摘要状态',call_summary:'摘要',
    turn_count:'回合数',memory_success_count:'记忆成功任务',memory_failed_count:'记忆失败任务',memory_trace_count:'已写记忆条目',
    memory_dropped_count:'已知丢弃条目',memory_dropped_complete:'丢弃统计完整',safety_matched_count:'普通安全命中（方向数）',
    crisis_matched_count:'危机命中（方向数）',crisis_suspected_count:'危机疑似（方向数）',
    isolated_turn_count:'危机隔离回合',readable_turn_count:'可读文字回合',
    user_crisis_status:'用户危机检测',assistant_crisis_status:'林小梦危机检测',
    content_unavailable_reason:'内容说明',effective_text_evidence:'播放文字依据',
    interrupted_count:'打断次数',followup_statuses:'追加消息状态',user_emotion:'用户情绪',assistant_emotion:'林小梦情绪',
    remaining_days:'剩余天数',transcript_expires_at:'转写到期',cleared_turn_count:'已清理回合',deleted_at:'删除时间',
    turn_index:'回合',user_text_final:'用户最终文字',assistant_text_effective:'实际播放文字',assistant_text_generated:'完整生成文字',
    memory_status:'记忆状态',attempt_count:'累计尝试',fail_reason:'失败分类',next_retry_at:'下次重试',kind:'任务类型',
    action:'操作',admin_username:'操作人',module:'模块',points:'成长值',business_date:'业务日',eligible_seconds:'有效秒数',
    segment_seq:'分段',quota_date:'额度日期',usage_type:'用量类型',id:'编号',content_available:'内容读取条件满足',
    effective_text_expires_at:'有效文字到期',effective_text_cleared_at:'有效文字清理时间',
    content_clear_status:'清理状态',content_clear_reason:'清理原因'};
  const columns=['user_id','created_at','status','duration_seconds','end_reason','free_seconds_used','extra_seconds_used',
    'grace_seconds','provider','model_version','voice_id','config_version','summary_status','turn_count','memory_success_count',
    'memory_failed_count','memory_trace_count','memory_dropped_count','memory_dropped_complete','safety_matched_count',
    'crisis_matched_count','crisis_suspected_count','isolated_turn_count','readable_turn_count',
    'interrupted_count','followup_statuses','user_emotion','assistant_emotion','transcript_expires_at','remaining_days','cleared_turn_count'];
  function node(tag,text){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;}
  function value(v){return v==null?'—':typeof v==='object'?JSON.stringify(v):typeof v==='boolean'?(v?'是':'否'):String(v);}
  function statusTagClass(raw){
    const value=String(raw||'').toLowerCase();
    if(['ended','ready','success','connected','completed','passed'].includes(value))return 'tag-success';
    if(['failed','cancelled','error','deleted','matched','isolation_failed'].includes(value))return 'tag-error';
    if(['pending','processing','reconnecting','partial_success','suspected'].includes(value))return 'tag-warning';
    return 'tag-default';
  }
  function appendValueCell(row,key,raw){
    const cell=node('td');
    if(['status','summary_status','memory_status','postprocess_status','user_crisis_status','assistant_crisis_status'].includes(key)&&raw!=null){
      const crisisText={passed:'通过',matched:'命中',suspected:'疑似（检测未能可靠完成）',pending:'待检测',isolation_failed:'隔离写入异常'};
      const tag=node('span',key.endsWith('_crisis_status')?(crisisText[raw]||value(raw)):value(raw));tag.className='tag '+statusTagClass(raw);cell.append(tag);
    }else cell.textContent=value(raw);
    row.append(cell);
  }
  function turnRetention(item){
    const raw=item.effective_text_expires_at;
    const expiry=typeof raw==='string'?Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(raw)?raw:raw+'Z'):NaN;
    return {...item,remaining_days:item.effective_text_cleared_at?0:Number.isFinite(expiry)?Math.max(0,Math.floor((expiry-Date.now())/86400000)):null,
      content_unavailable_reason:({deleted:'通话已删除',cleared:'文字已清理',expired:'文字已到期',
        crisis_isolated:'危机隔离：正文不进入普通转写、摘要或记忆',assessment_incomplete:'检测未完成，正文不可读',
        retention_unavailable:'有效文字保留状态缺失',no_effective_text:'未保存有效文字'})[item.content_unavailable_reason]||item.content_unavailable_reason,
      content_clear_status:item.effective_text_cleared_at?'已清理':'未清理',
      content_clear_reason:({expired:'到期清理',admin_deleted:'管理员删除'})[item.content_clear_reason]||item.content_clear_reason};
  }
  function table(items,keys){const t=node('table');t.className='admin-table';const h=node('tr');keys.forEach(k=>h.append(node('th',labels[k]||k)));t.append(h);
    items.forEach(item=>{const row=node('tr');keys.forEach(k=>appendValueCell(row,k,item[k]));t.append(row);});return t;}
  const fields=[['started_from','开始于','datetime-local'],['started_before','早于','datetime-local'],['user_id','用户 ID','number'],
    ['status','状态',['ended','missed','failed','cancelled','connected','reconnecting']],['end_reason','结束原因',['user_hangup','exit_intent','silence_timeout','quota_exhausted','hard_limit','reconnect_timeout','provider_error','system_error','user_cancel']],
    ['provider','Provider','text'],['model','模型','text'],['config_version','配置版本','number'],
    ['summary_status','摘要状态',['pending','ready','failed','not_applicable']],['memory_status','记忆状态',['pending','processing','success','failed','skipped','cancelled']],
    ['postprocess_status','后处理状态',['pending','processing','success','partial_success','failed','cancelled']],
    ['interrupted','有无打断',['true','false']],['expired','是否到期',['true','false']],['cleared','是否清理',['true','false']],
    ['audit_view','审计视图',['true','false']],['deleted','是否删除（审计视图）',['true','false']]];
  fields.forEach(([name,title,type])=>{const label=node('label'),caption=node('span',title),input=node(Array.isArray(type)?'select':'input');label.className='voice-filter-field';input.className='form-control';input.name=name;
    if(Array.isArray(type)){input.append(new Option('全部',''));type.forEach(v=>input.append(new Option(v==='true'?'是':v==='false'?'否':v,v)));}
    else {input.type=type;if(type==='number')input.min='1';}label.append(caption,input);$('voice-filter-fields').append(label);});
  let page=1,total=0,listGeneration=0,detailGeneration=0,current=null,tab='',cursor=null,jobKind='memory';
  const dialog=$('voice-dialog'),panel=$('voice-panel');
  function clear(){detailGeneration++;current=null;panel.replaceChildren();$('voice-detail-status').textContent='';dialog.close();}
  $('voice-close').onclick=clear;dialog.addEventListener('cancel',clear);window.addEventListener('pagehide',clear);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clear();});
  async function request(method,path,body){const result=await adminRequest(method,'/api/admin/voice'+path,body);if(!result||result.code!==0)throw Error('请求失败，请重试');return result.data;}
  window.loadVoiceCallsPage=nextPage=>{page=nextPage;load();};
  async function load(){const generation=++listGeneration;clear();$('voice-rows').replaceChildren();$('voice-status').textContent='加载中…';
    const params=new URLSearchParams({page:String(page),page_size:'20'});
    new FormData($('voice-filters')).forEach((v,k)=>{if(v)params.set(k,k.startsWith('started_')?new Date(v).toISOString():v);});
    try{const data=await request('GET','/calls?'+params);if(generation!==listGeneration)return;total=data.total;
      const head=node('tr');columns.forEach(k=>head.append(node('th',labels[k])));head.append(node('th','操作'));$('voice-head').replaceChildren(head);
      data.items.forEach(item=>{const row=node('tr');columns.forEach(k=>appendValueCell(row,k,item[k]));const cell=node('td'),button=node('button','查看');button.className='btn btn-link';button.onclick=()=>open(item.call_id);cell.append(button);row.append(cell);$('voice-rows').append(row);});
      if(!data.items.length){const row=node('tr'),cell=node('td','暂无通话数据');cell.colSpan=columns.length+1;cell.className='voice-empty';row.append(cell);$('voice-rows').append(row);}
      $('voice-status').textContent=total?'共 '+total+' 条':'暂无匹配的通话';
      renderPagination('voice-pagination',page,total,20,function(nextPage){window.loadVoiceCallsPage(nextPage);});
    }catch(e){if(generation===listGeneration)$('voice-status').textContent=e.message;}}
  const tabs=[['overview','概览'],['turns','逐轮转写'],['jobs','任务'],['config','配置快照'],['usage','用量与成长'],['audit','审计']];
  tabs.forEach(([key,title])=>{const button=node('button',title);button.className='btn btn-default';button.onclick=()=>show(key);button.dataset.tab=key;$('voice-tabs').append(button);});
  function open(id){current=id;dialog.showModal();$('voice-title').textContent='通话详情 · '+id;show('overview');}
  async function show(key,more=false){if(!current)return;const generation=++detailGeneration,id=current;tab=key;
    if(!more){cursor=null;panel.replaceChildren();} $('voice-more').hidden=true;$('voice-detail-status').textContent='加载中…';
    document.querySelectorAll('[data-tab]').forEach(el=>el.setAttribute('aria-selected',String(el.dataset.tab===key)));
    let suffix=key==='overview'?'':'/'+key;const params=new URLSearchParams();if(cursor)params.set(key==='audit'?'before':'after',cursor);if(key==='jobs')params.set('kind',jobKind);
    try{const data=await request('GET','/calls/'+encodeURIComponent(id)+suffix+'?'+params);if(generation!==detailGeneration||id!==current)return;
      if(key==='overview'){
        panel.append(node('p','保留状态只表示内容未到期、未删除；可读文字回合数另行统计。命中次数按用户与林小梦两个方向分别计数。'));
        if(data.summary_status==='not_applicable')panel.append(node('p','未满足摘要生成条件。通话需已接通且至少 15 秒，并存在包含有效用户表达、实际播放文字且检测通过的回合。此状态不会通过等待自动生成摘要。'));
        if(data.isolated_turn_count>0)panel.append(node('p','有 '+data.isolated_turn_count+' 个回合被危机隔离；这些正文不参与普通摘要与记忆。疑似状态也可能由配置不可用引起，不等同于实际命中危机词。'));
        panel.append(table(Object.entries(data).map(([k,v])=>({field:k==='content_available'?'通话内容未到期且未删除':labels[k]||k,value:value(v)})),['field','value']));}
      else if(key==='config'){const pre=node('pre',JSON.stringify(data,null,2));panel.append(pre);}
      else if(key==='usage'){panel.append(node('h3','用量账本'),table(data.ledger,['segment_seq','quota_date','usage_type','duration_seconds','free_seconds_used','extra_seconds_used']),node('h3','成长记录'),table(data.growth,['id','points','eligible_seconds','business_date']));}
      else{if(key==='jobs'&&!more){const select=node('select');select.className='form-control';select.style.maxWidth='220px';select.setAttribute('aria-label','任务类型');['memory','postprocess','followup'].forEach(k=>select.append(new Option(k,k)));select.value=jobKind;select.onchange=()=>{jobKind=select.value;show('jobs');};panel.append(select);}
        if(key==='debug')panel.append(node('p','内部判断：'+value(data.reasoning)));
        if(key==='turns'&&!more)panel.append(node('p','危机隔离、检测未完成或保留期结束时，普通转写中不展示正文。疑似状态可能由检测配置不可用引起，不能据此判断对话实际命中了危机词。'));
        const keys=key==='turns'?['turn_index','user_text_final','assistant_text_effective','user_crisis_status','assistant_crisis_status','content_unavailable_reason','effective_text_evidence','memory_status','effective_text_expires_at','remaining_days','content_clear_status','effective_text_cleared_at','content_clear_reason','content_available']:
          key==='debug'?['turn_index','assistant_text_generated','generated_text_expires_at']:key==='jobs'?['id','kind','status','attempt_count','fail_reason','next_retry_at']:['id','admin_username','module','action','created_at'];
        panel.append(table(key==='turns'?data.items.map(turnRetention):data.items,keys));if(!data.items.length)panel.append(node('p','暂无记录'));
        if(key==='jobs'&&role==='super_admin')data.items.filter(j=>j.retry_path).forEach(j=>{
          const button=node('button','补跑任务 #'+j.id);button.className='btn btn-default';button.onclick=async()=>{button.disabled=true;try{await request('POST',j.retry_path);await show('jobs');}catch(e){$('voice-detail-status').textContent=e.message;button.disabled=false;}};panel.append(button);});
        cursor=data.next_after||data.next_before||null;$('voice-more').hidden=!cursor;
      }$('voice-detail-status').textContent='';
    }catch(e){if(generation===detailGeneration)$('voice-detail-status').textContent=e.message;}}
  $('voice-more').onclick=()=>show(tab,true);$('voice-debug').hidden=role!=='super_admin';$('voice-debug').onclick=()=>show('debug');
  $('voice-delete').hidden=role!=='super_admin';$('voice-delete').onclick=async()=>{
    if(!current)return;
    const id=current,button=$('voice-delete');
    if(!window.confirm('将删除通话卡片、摘要和逐轮文字，并取消未完成任务。\n已经成功写入的长期记忆、用量账本、成长值和无正文审计不会删除或回滚。'))return;
    button.disabled=true;
    try{await request('DELETE','/calls/'+encodeURIComponent(id));if(current===id){clear();await load();}}
    catch(e){if(current===id)$('voice-detail-status').textContent=e.message;}
    finally{button.disabled=false;}
  };
  $('voice-export').hidden=!['super_admin','ops_admin'].includes(role);$('voice-export').onclick=async()=>{if(!current)return;const id=current,button=$('voice-export');button.disabled=true;
    try{const data=await request('POST','/calls/export',{call_ids:[id]});if(current!==id)return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=node('a');a.href=url;a.download='voice-'+id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){$('voice-detail-status').textContent=e.message;}finally{button.disabled=false;}};
  $('voice-filters').onsubmit=e=>{e.preventDefault();page=1;load();};
  $('voice-filters').onreset=()=>setTimeout(()=>{page=1;load();},0);
  const initialUser=new URLSearchParams(location.search).get('user_id');
  if(initialUser&&/^\d+$/.test(initialUser))$('voice-filters').elements.user_id.value=initialUser;
  load();
})();

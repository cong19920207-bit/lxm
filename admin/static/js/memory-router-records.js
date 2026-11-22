(function () {
  'use strict';
  const M=MemoryAdmin, base='/api/admin/memory-diagnostics/router-runs',get=id=>document.getElementById(id);
  const form=get('online-filter'),params=new URLSearchParams(location.search);
  let page=1,sequence=0,detailSequence=0;
  M.setupTabs(id=>{
    if(id==='tab-online')load();
    else detailSequence++;
    const url=new URL(location.href);
    if(id==='tab-online')url.searchParams.set('tab','online');
    else url.searchParams.delete('tab');
    window.history.replaceState(null,'',url);
  });
  function dateValue(time) {return new Date(time-time.getTimezoneOffset()*60000).toISOString().slice(0,16);}
  const end=new Date(Date.now()+60000);
  form.elements.end.value=dateValue(end);form.elements.start.value=dateValue(new Date(end-86400000));
  form.elements.version.value=params.get('version')||'';
  if(params.has('generation_id'))form.elements.generation_id.value=params.get('generation_id');
  async function load() {
    const seq=++sequence;detailSequence++;
    const filters=M.formValues(form);
    for(const key of ['start','end'])if(filters[key])filters[key]=new Date(filters[key]).toISOString();
    get('online-detail').replaceChildren();get('online-state').textContent='正在读取…';
    const r=await M.request('GET',base+'?'+new URLSearchParams({...filters,page,page_size:20}));
    if(seq!==sequence)return;
    const list=get('online-list');list.replaceChildren();get('online-summary').replaceChildren();
    if(r?.code!==0){get('online-state').textContent=M.error(r);get('online-prev').disabled=true;get('online-next').disabled=true;return;}
    const d=r.data,s=d.summary;
    M.fields(get('online-summary'),{
      '时间和用户范围内的全部执行':s.total,'有记录 / 无记录':s.covered+' / '+s.missing,
      '筛选后有记录':s.matching_traces,'合法 false / true':s.false+' / '+s.true,
      '合法 false 比例':d.legal_decisions?(100*d.false_ratio).toFixed(1)+'%（分母 '+d.legal_decisions+'）':'无有效判定',
      '当前租约成功执行的合法 false / 分母':s.current_success_false+' / '+d.success_legal_decisions,
      '关闭 / 保守 / 错误回退':s.disabled+' / '+s.conservative+' / '+s.error_fallback,
      '路由超时':s.timeout,'判定耗时（毫秒，100ms 分组）':d.duration,'耗时未记录':s.duration_missing});
    for(const item of d.list) {
      const row=M.el('article',null,'ma-record'),info=M.el('div'),status=M.el('div',null,'ma-record-info');
      const label=(name,value,fallback)=>Array.from(form.elements[name].options).find(o=>o.value===value)?.textContent||value||fallback;
      info.append(M.el('div','用户 '+item.user_id+' · '+label('path',item.execution_path,'路径未记录'),'ma-record-title'),
        M.el('div',item.accepted_at+' · 渠道 '+(item.source_channels?.join('、')||'未记录'),'ma-record-meta'),
        M.el('div',['版本 '+(item.router_config_version??'未记录'),'判定 '+(item.decision??'未判定'),
          label('reason',item.controlled_reason,'原因未记录'),'完整性 '+(item.stats_completeness||'未记录'),
          item.lease_match==='earlier'?'较早执行尝试':''].filter(Boolean).join(' · '),'ma-record-meta'));
      status.append(M.badge(label('state',item.state,'未记录'),item.state),
        M.el('span',item.router_duration_ms==null?'耗时未记录':item.router_duration_ms+' ms','ma-record-meta'));
      info.append(M.el('div','执行 ID：'+item.generation_id,'ma-record-meta'));
      const open=M.button('查看记录',()=>detail(item.generation_id));
      row.append(info,status,open);
      list.append(row);
    }
    get('online-state').textContent='第 '+page+' 页，共 '+d.total+' 项。覆盖范围可能包含旧版本。';
    get('online-prev').disabled=page===1;get('online-next').disabled=page*20>=d.total;
  }
  function link(title,url) {const a=M.el('a',title);a.href=url;return a;}
  async function detail(id) {
    const seq=++detailSequence,r=await M.request('GET',base+'/'+encodeURIComponent(id));
    if(seq!==detailSequence)return;
    const box=get('online-detail');box.replaceChildren();
    if(r?.code!==0){box.textContent=M.error(r);return;}
    const d=r.data,t=d.trace||{},f=M.el('div');
    box.append(M.el('h3','线上执行 '+id),f);
    box.scrollIntoView({block:'start'});
    if(d.source_reference.current.scope==='fragment')box.append(M.el('p','当前输入仅展示本轮实际使用并通过摘要核验的片段。'));
    M.fields(f,{'执行终态':d.state,'执行阶段':d.phase,'终态原因':d.reason,'成功轮次':d.round_id,'受理至终态（毫秒）':d.elapsed_ms,'来源渠道':d.source_channels,
      '记录归属':d.lease_match==='earlier'?'较早执行尝试 · 无法归因当前终态':d.lease_match,'判定原因':d.reason_text,
      '路由模型':t.effective_model,'思考模式':t.thinking_enabled==null?'未记录':t.thinking_enabled?'开启':'关闭',
      '路径选择':d.execution_path,'实际阶段':t.stage_statuses,'采集完整性':d.stats_completeness,
      '实际调用':t.call_counts,'当轮输入 token / 预算':(t.official_prompt_tokens??'未采集')+' / '+(t.effective_max_total??'未采集'),
      '供应商 usage':t.provider_usage??'未提供','当时配置':d.config_reference,'历史与输入来源':d.source_reference,
      '有序引用':{current:t.current_input_refs,history:t.history_round_refs},'动态背景摘要':t.router_background_digest,'当时采集的完整 trace':d.trace,
      '原任务状态':d.effects,'当轮业务结果证据':d.business_evidence});
    if(d.config_reference.status==='verified'&&String(t.router_config_version)!=='0')box.append(link('查看当时配置版本','/admin/pages/prompt.html?tab=router&version='+encodeURIComponent(t.router_config_version)));
    if([d.source_reference.current,d.source_reference.history].some(ref=>ref.status==='verified'))
      box.append(link('查看用户对话来源','/admin/pages/user-detail.html?id='+encodeURIComponent(d.user_id)+'#tab-conversation'));
    if(M.write())box.append(link('使用当前数据创建新诊断','/admin/pages/memory-diagnostics.html?'+new URLSearchParams({
      mode:'runtime_path',user_id:d.user_id,source_generation_id:id})));
  }

  form.onsubmit=e=>{e.preventDefault();page=1;load();};
  get('online-prev').onclick=()=>{page--;load();};get('online-next').onclick=()=>{page++;load();};
  if(params.get('tab')==='online')get('tab-online').click();
})();

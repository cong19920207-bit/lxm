(function () {
  'use strict';var M=MemoryAdmin;if(!M.start('memory-diagnostics','记忆检索诊断'))return;
  document.getElementById('diag-create').hidden=!M.write();
  var base='/api/admin/memory-diagnostics',form=document.getElementById('diag-input'),feedback=document.getElementById('submission-state'),storage='memory_diagnostic_pending',active=null,submitting=false,detailId=null,detailSequence=0,detailData=null,candidates=null, timer=null, observationSequence=0, interval=2000, pageActive=true, lifecycle=0;
  var executionLabels={accepted:'已受理',running:'执行中',completed:'完成',degraded:'部分降级',failed:'执行失败',budget_blocked:'预算阻断',interrupted:'已中断',manual_required:'待人工核实'};
  var historyLabels={pending:'保存中',saved:'已保存',failed:'保存失败',unknown:'保存结果待核实',deleted:'历史已清理'};
  function states(d){return '执行：'+(executionLabels[d.execution_state]||d.execution_state)+'；历史：'+(historyLabels[d.history_state]||d.history_state);}
  function stopObservation(){observationSequence++;clearTimeout(timer);timer=null;}
  function canObserve(){return pageActive&&Boolean(getAdminToken());}
  function leavePage(){pageActive=false;lifecycle++;detailSequence++;submitting=false;stopObservation();freeze();}
  function scheduleObservation(){clearTimeout(timer);if(!active||!canObserve())return;var remaining=active.observe_until-performance.now();if(remaining<=0){feedback.textContent+=' · 自动核实已到150秒上界，请手动核实';return;}var wait=Math.min(interval,remaining);timer=setTimeout(function(){if(active&&canObserve())queryActive(true);},wait);interval=Math.min(5000,interval*1.5);}
  window.addEventListener('pagehide',leavePage);
  window.addEventListener('admin-session-cleared',function(){active=null;leavePage();});
  window.addEventListener('pageshow',function(){if(!pageActive){pageActive=true;lifecycle++;interval=2000;freeze();if(active&&getAdminToken())queryActive(false);}});
  function persist(){if(active)sessionStorage.setItem(storage,JSON.stringify({request_id:active.request_id,execution_id:active.execution_id||null,observation_end:performance.timeOrigin+active.observe_until}));else sessionStorage.removeItem(storage);}
  function freeze(){var frozen=Boolean(active||submitting);document.getElementById('query-active').disabled=!active;form.querySelectorAll('input,textarea,select,button').forEach(function(n){n.disabled=frozen||(form.elements.source.value==='step8'&&['mode','router_config_source'].includes(n.name));});}
  function observeData(d){if(active&&active.request_id===d.request_id){active.execution_id=d.execution_id;if(d.created_at&&d.server_time)active.observe_until=performance.now()+Math.max(0,Date.parse(d.created_at)+150000-Date.parse(d.server_time));feedback.textContent=states(d)+' · '+d.execution_id+' · '+M.text(d.reason);if(!['accepted','running','manual_required'].includes(d.execution_state)&&!['pending','unknown'].includes(d.history_state)){active=null;stopObservation();}persist();freeze();}}
  async function queryActive(automatic){if(!canObserve())return;var cycle=lifecycle;if(automatic&&(!active||!getAdminToken()||performance.now()>=active.observe_until)){if(active)feedback.textContent='自动核实已到150秒上界，请手动核实';return;}var querySequence=++observationSequence;if(!active){feedback.textContent='当前没有待核实的提交身份';return;}var context=active;feedback.textContent='正在只读核实本次执行…';var r=await M.request('GET',context.execution_id?base+'/'+encodeURIComponent(context.execution_id):base+'?request_id='+encodeURIComponent(context.request_id)+'&page_size=1');if(active!==context||querySequence!==observationSequence||cycle!==lifecycle||!canObserve())return;if(!r||r.code!==0){feedback.textContent='结果待核实：'+M.error(r)+'；请保留本次身份，不重复执行';scheduleObservation();return;}var d=context.execution_id?r.data:r.data.list[0];if(!d){feedback.textContent='暂未查到本次身份，不能确认请求未受理；请继续只读核实';scheduleObservation();return;}observeData(d);var filterUser=document.getElementById('diag-filter').elements.user_id.value;if(detailId===d.execution_id||(!detailId&&(!filterUser||filterUser===String(d.user_id))))showDetail(d.execution_id);history.load();scheduleObservation();}
  document.getElementById('query-active').onclick=function(){queryActive(false);};
  const params=new URLSearchParams(location.search);
  let sourceGeneration=params.get('source_generation_id'), draftDigest=params.get('draft_digest'), configSequence=0;
  const sourceLabel=document.getElementById('diag-router-source');
  async function selectedConfig() {
    const seq=++configSequence, useDraft=form.elements.router_config_source.value==='draft';
    const result=await M.request('GET','/api/admin/prompt/memory-router'+(useDraft?'/draft':''));
    if(seq!==configSequence)return;
    if(result?.code!==0){sourceLabel.textContent='配置读取失败';return;}
    let label, digest;
    if(useDraft){
      if(!draftDigest)draftDigest=result.data.draft_digest;
      label=draftDigest?'已保存草稿':'暂无草稿';
      if(draftDigest!==result.data.draft_digest)label+=' · 已发生变更，请重选配置';
      digest=draftDigest;
    }else {label='生效版本 '+result.data.version;digest=result.data.config_digest;}
    sourceLabel.replaceChildren(M.el('span',label));
    if(digest){
      const more=M.el('details');
      more.append(M.el('summary','配置摘要'),M.el('code',digest));
      sourceLabel.append(more);
    }
  }
  function inputLimit() {
    return form.elements.source.value === 'step8' ? 200 : 2000;
  }
  function updateInputLength() {
    const input = form.elements.input;
    const count = Array.from(input.value).length, limit = inputLimit();
    input.setCustomValidity(count > limit ? '本来源最多允许 '+limit+' 个字符' : '');
    document.getElementById('input-range').textContent = '已输入 '+count+' / '+limit+' 个字符'+
      (form.elements.source.value === 'step8' ? ' · 不消费 Future 槽' : '');
  }
  form.elements.input.addEventListener('input', updateInputLength);
  function setSource() {
    const step8=form.elements.source.value==='step8';
    updateInputLength();
    if(step8){form.elements.mode.value='retrieval_only';form.elements.router_config_source.value='active';}
    form.elements.mode.disabled=step8;form.elements.router_config_source.disabled=step8;
    selectedConfig();
  }
  form.elements.source.onchange=setSource;
  form.elements.router_config_source.onchange=()=>{draftDigest=null;selectedConfig();};
  if(params.has('mode'))form.elements.mode.value=params.get('mode');
  if(params.has('router_config_source'))form.elements.router_config_source.value=params.get('router_config_source');
  if(params.has('user_id'))form.elements.user_id.value=params.get('user_id');
  async function prepareOrigin(id) {
    feedback.textContent='使用当前数据的新测试 · 来源 '+id+' · 请确认输入后提交';
    const result=await M.request('GET',base+'/router-runs/'+encodeURIComponent(id));
    if(sourceGeneration!==id||!canObserve()||active||submitting||form.elements.input.value)return;
    const current=result?.data?.source_reference?.current;
    if(current?.status==='verified' && typeof current.verified_text==='string'){
      if(Array.from(current.verified_text).length<=inputLimit()){
        form.elements.input.value=current.verified_text;
        updateInputLength();
        if(current.scope==='fragment') feedback.textContent='已填入本轮实际使用的片段，请确认后提交新诊断。';
      }
    }
  }
  if(sourceGeneration)prepareOrigin(sourceGeneration);
  setSource();
  async function submit(parent){if(!canObserve())return;var cycle=lifecycle;if(active||submitting){queryActive();return;}var uid=form.elements.user_id.value,input=form.elements.input.value,source=form.elements.source.value,limit=inputLimit();if(!/^[1-9]\d*$/.test(uid)||!Number.isSafeInteger(Number(uid))||!input.trim()||Array.from(input).length>limit){feedback.textContent='请填写正整数用户ID与范围内非空输入（本来源最多'+limit+'字符）';return;}if(form.elements.router_config_source.value==='draft'&&!draftDigest){feedback.textContent='请先选择已保存的草稿';return;}submitting=true;freeze();feedback.textContent='正在校准服务器时间…';var clock=await M.calibrate();if(cycle!==lifecycle||!canObserve())return;if(!clock){submitting=false;freeze();feedback.textContent='服务器校时失败，未提交诊断；输入已保留';return;}interval=2000;active={request_id:M.uuid7(Math.floor(clock.server+performance.now()-clock.received)),observe_until:performance.now()+150000};persist();freeze();feedback.textContent='提交中；本次身份 '+active.request_id;var body={request_id:active.request_id,user_id:Number(uid),source:source,input:input};body.mode=form.elements.mode.value;body.router_config_source=form.elements.router_config_source.value;if(body.router_config_source==='draft')body.draft_digest=draftDigest;if(sourceGeneration)body.source_generation_id=sourceGeneration;if(parent)body.parent_execution_id=parent;var context=active;var r=await M.request('POST',base,body);if(active!==context)return;if(cycle!==lifecycle||!canObserve()){if(!getAdminToken()){active=null;return;}if(r&&r.code===0&&r.data)context.execution_id=r.data.execution_id;persist();return;}submitting=false;if(r&&r.code===0&&r.data){observeData(r.data);showDetail(r.data.execution_id);history.load();scheduleObservation();}else if(r&&![20122,20129].includes(r.code)){active=null;persist();feedback.textContent='执行请求未成功：'+M.error(r);}else{feedback.textContent='受理结果待核实：'+M.error(r)+'；只按原请求身份查询，不自动重发';scheduleObservation();}freeze();}
  form.onsubmit=function(e){e.preventDefault();submit();};
  const sourceNames={main:'主文字',openapi:'OpenAPI',step8:'Step8 主动对话'};
  function historyRow(d){
    const row=M.el('article',null,'ma-record'),info=M.el('div'),status=M.el('div',null,'ma-record-info');
    info.append(M.el('div',sourceNames[d.source]||d.source,'ma-record-title'),
      M.el('div','用户 '+d.user_id+' · '+M.text(d.created_at),'ma-record-meta'),M.el('div',d.execution_id,'ma-record-meta'));
    status.append(M.badge('执行：'+(executionLabels[d.execution_state]||d.execution_state),d.execution_state),
      M.badge('历史：'+(historyLabels[d.history_state]||d.history_state),d.history_state));
    row.append(info,status,M.button('查看详情',()=>{
      showDetail(d.execution_id);
      document.getElementById('diag-detail').scrollIntoView({block:'start'});
    }));
    return row;
  }
  var history=M.pager(document.getElementById('diag-history'),base,historyRow,
    ()=>M.formValues(document.getElementById('diag-filter')));
  document.getElementById('diag-filter').onsubmit=function(e){e.preventDefault();detailSequence++;detailId=null;detailData=null;if(candidates)candidates.invalidate();document.getElementById('diag-detail').hidden=true;['diag-context','diag-version','diag-queries','diag-selection','diag-status','diag-actions'].forEach(function(k){document.getElementById(k).replaceChildren();});history.load(true);};
  function candidate(c){var row=M.el('article'),expanded=M.el('details');expanded.append(M.el('summary',c.id+' · '+c.doc_id+' · '+(c.selected?'最终选入':c.initial_selected?'模块初选后淘汰':'未选入')+' · 排序 '+M.text(c.order_method)+' · 重排分 '+M.text(c.rerank_score)));row.append(expanded);var data={身份代次:c.identity_id+' / '+M.text(c.generation),原渠道名次与分数:c.channel_ranks||{dense_rank:c.dense_rank,bm25_rank:c.bm25_rank,dense_score:c.dense_score,bm25_score:c.bm25_score},原分:{dense:c.dense_score,bm25:c.bm25_score},渠道:c.source_channels,路内名次:c.route_rank,准入理由:c.admission_reason,重排分:c.rerank_score,排序方式:c.order_method,故障排序分:c.fusion_score,模块初选:c.initial_selected,最终选入:c.selected,最终选入顺序:c.selection_order,淘汰原因:c.removals||c.reason,阶段:c.stage};var box=M.el('div');M.fields(box,data);expanded.append(box);if(c.entry_kind==='removal')expanded.append(M.el('p','校验淘汰项，无可信正文快照'));else{expanded.append(M.el('pre',M.text(c.key)+'：'+M.text(c.value)),M.el('pre',c.rendered_text==null?'未最终选入':c.rendered_text));}return row;}
  document.getElementById('candidate-route').onchange=function(){if(candidates)candidates.load(true);};
  async function showDetail(id){if(!canObserve())return;var cycle=lifecycle;detailId=id;var seq=++detailSequence;detailData=null;document.getElementById('diag-detail').hidden=false;['diag-context','diag-version','diag-queries','diag-selection','diag-status','diag-actions'].forEach(function(k){document.getElementById(k).replaceChildren();});if(candidates)candidates.invalidate();document.getElementById('diag-context').textContent='加载中…';var r=await M.request('GET',base+'/'+encodeURIComponent(id));if(seq!==detailSequence||cycle!==lifecycle||!canObserve())return;if(!r||r.code!==0){document.getElementById('diag-context').textContent='详情加载失败：'+M.error(r);return;}var d=r.data;detailData=d;observeData(d);
    M.fields(document.getElementById('diag-context'),{执行ID:d.execution_id,用户ID:d.user_id,来源:d.source,原输入:d.input,创建时间:d.created_at,历史快照:d.snapshot_semantics});
    M.fields(document.getElementById('diag-version'),{本次冻结配置:d.frozen_versions,装载来源与时点:d.context_sources});
    M.fields(document.getElementById('diag-queries'),{四路Question与Keywords:d.metrics&&d.metrics.queries,渠道状态与降级:d.metrics&&d.metrics.routes});
    M.fields(document.getElementById('diag-selection'),{模块初选数量:d.selection_result&&d.selection_result.initial_selected_count,最终选入数量:d.selection_result&&d.selection_result.selected_count,路实际数量:d.selection_result&&d.selection_result.route_counts,模块Token:d.selection_result&&d.selection_result.module_charges,最终Token与预算:d.selection_result&&d.selection_result.counter,预算阻断:d.selection_result&&d.selection_result.over_budget,裁剪说明:'候选页逐项标注模块初选、最终选入及两次淘汰原因；选入正文为本次实际渲染文本'});
    M.fields(document.getElementById('diag-status'),{状态:states(d),模式:d.mode,配置来源:d.frozen_versions?.selected_router?.choice,测试摘要:d.frozen_versions?.selected_router?.config_digest,
      路由模型:d.metrics?.router?.model,思考模式:d.metrics?.router?.thinking_enabled==null?'未记录':d.metrics.router.thinking_enabled?'开启':'关闭',
      路由耗时:d.metrics?.router?.duration_ms==null?null:d.metrics.router.duration_ms+' 毫秒',
      判定:d.metrics?.router?.decision===null?'未判定':d.metrics?.router?.decision,建议路径:d.metrics?.router?.suggested_path,
      实际路径:d.metrics?.router?.execution_path,路由原因:d.metrics?.router?.reason,
      共享上下文:d.context_sources,各阶段实际调用:d.metrics?.observed_calls,检索状态:d.metrics?.retrieval_status,
      Step3状态:d.metrics?.step3_status,最终模块计数:d.selection_result?.module_charges,
      仅测试:d.metrics?.router?.test_only?'仅判定，线上开关保持原值':null,实际阶段:d.stage,原因:d.reason,核实时点:d.observed_at,执行截止:d.deadline_at,保存截止:d.persist_deadline_at,阶段与调用指标:d.metrics,费用:d.metrics&&d.metrics.cost_status==='not_provided'?'未提供':d.metrics&&d.metrics.cost});
    var actions=document.getElementById('diag-actions');actions.append(M.button('刷新详情',function(){showDetail(id);}));if(M.write()&&d.history_state!=='deleted'){var rerun=M.button('重新执行',function(){if(active||submitting){feedback.textContent='另一执行仍待核实，请先核实本次执行';return;}form.elements.user_id.value=d.user_id;form.elements.source.value=d.source;form.elements.input.value=d.input||'';form.elements.mode.value=d.mode||'retrieval_only';form.elements.router_config_source.value=d.frozen_versions?.selected_router?.choice||'active';draftDigest=d.frozen_versions?.selected_router?.config_digest;sourceGeneration=d.source_generation_id||null;setSource();submit(id);},true);rerun.disabled=Boolean(active||submitting)||!d.input;actions.append(rerun);var del=M.button('删除诊断历史',async function(){if(!confirm('仅删除本次诊断记录及文本快照，不删除当前记忆'))return;del.disabled=true;var res=await M.request('DELETE',base+'/'+encodeURIComponent(id));if(detailId!==id)return;if(res&&res.code===0){feedback.textContent='本次历史已清理';showDetail(id);history.load();}else{feedback.textContent='删除'+(res&&res.code===20122?'结果待核实':'失败')+'：'+M.error(res)+'；记录保留，刷新详情核实';del.disabled=!d.can_delete;}},true);del.classList.add('ma-destructive');del.disabled=!d.can_delete;actions.append(del,M.el('span',d.action_reason||''));}
    candidates=M.pager(document.getElementById('diag-candidates'),base+'/'+encodeURIComponent(id),candidate,function(){var route=document.getElementById('candidate-route').value;return Object.assign({section:'candidates'},route?{route:route}:{});});candidates.load();
    var url=new URL(location.href);url.searchParams.set('execution_id',id);window.history.replaceState(null,'',url);
  }
  try{var saved=JSON.parse(sessionStorage.getItem(storage)||'null');if(saved&&saved.request_id)active=Object.assign(saved,{observe_until:Math.max(performance.now(),(saved.observation_end||performance.timeOrigin)-performance.timeOrigin)});}catch(e){sessionStorage.removeItem(storage);}freeze();history.load();var initial=new URLSearchParams(location.search).get('execution_id');if(active)queryActive();else if(initial)showDetail(initial);
})();

(function () {
  'use strict';
  if (!checkAdminLogin()) return;
  if (!['super_admin','ai_trainer','tech_ops','ops_admin','observer'].includes(getAdminRole())) {
    location.replace('error.html?type=403'); return;
  }
  const $=id=>document.getElementById(id);
  $('sidebar-mount').innerHTML=renderSidebar('voice-metrics');
  $('header-mount').innerHTML=renderHeader('通话指标');
  const names={daily_call_count:'通话数',connect_rate:'接通率',missed_rate:'未接率',failure_rate:'技术失败率',
    avg_duration_seconds:'平均通话时长（秒）',billable_seconds:'有效计费秒数',estimated_cost:'估算成本',
    call01_fallback_rate:'CALL-01 兜底率',memory_success_rate:'记忆成功率',summary_success_rate:'摘要成功率',
    truncate_success_rate:'上下文截断成功率',effective_text_evidence_distribution:'有效文本证据等级占比',
    double_reply_count:'额外回复数（按回复去重）',provider_usage_business_cost_ratio:'Provider Usage 与业务时长成本比'};
  const reasons={unknown_call01_outcomes:'部分通话缺少兜底记录',not_materialized:'尚无可用落库值',invalid_materialized_value:'落库值校验未通过',price_unconfigured:'尚未配置单价',durable_source_unavailable:'缺少持久化来源',
    no_eligible_samples:'无合格样本',undated_legacy_usage:'旧账本缺少业务日期',settlement_pending:'等待结算',
    capability_evidence_unavailable_for_bucket:'该观测日缺少可核验能力证据，指标不可测'};
  const statusNames={missing:'无保留样本',invalid:'样本无效',unavailable:'暂不可用',not_measurable:'不可测'};
  function row(target,values) {
    const tr=document.createElement('tr');
    values.forEach(value=>{const td=document.createElement('td');td.textContent=String(value);tr.append(td);});
    $(target).append(tr);
  }
  function value(item) {
    if (item.value===null || item.value===undefined || item.status==='not_measurable') return '不可测';
    if(item.name==='effective_text_evidence_distribution') {
      const levels={exact_played:'精确已播',confirmed_sentences:'已确认句子',full:'完整播放',none:'无有效文本'};
      return Object.entries(levels).map(([key,label])=>label+' '+(item.value[key]*100).toFixed(2)+'%').join('；');
    }
    const number=item.name.endsWith('_rate') ? (item.value*100).toFixed(2)+'%' : String(item.value);
    return number+(item.status==='provisional'?'（暂定）':'');
  }
  let dailyGeneration=0,observationGeneration=0,historyGeneration=0,billingGeneration=0,historyData=null;
  async function billing() {
    const generation=++billingGeneration;
    $('billing-rows').replaceChildren();$('billing-status').textContent='计算中…';
    const query=new URLSearchParams({start:$('billing-start').value,end:$('billing-end').value,
      bill_start:$('billing-start').value,bill_end:$('billing-end').value,
      unit_price:$('billing-price').value,unit:$('billing-unit').value,
      currency:$('billing-currency').value,bill_currency:$('billing-currency').value,billed_cost:$('billing-amount').value});
    try {
      const result=await adminRequest('GET','/api/admin/voice/metrics/billing-preview?'+query);
      if(generation!==billingGeneration)return;
      if(!result||result.code!==0)throw new Error('unavailable');
      const data=result.data;
      const amount=n=>n===null?'不可测':n+' '+data.currency;
      row('billing-rows',['有效计费秒数',data.billable_seconds===null?'不可测':data.billable_seconds]);
      row('billing-rows',['估算值（模拟）',amount(data.estimated_cost)]);
      row('billing-rows',['账单值（模拟）',amount(data.provider_billed_cost)]);
      row('billing-rows',['差额（估算减账单）',amount(data.difference_amount)]);
      row('billing-rows',['差异率',data.difference_rate===null?'不可测':(Number(data.difference_rate)*100).toFixed(2)+'%']);
      $('billing-status').textContent='模拟核对：'+data.start+' 至 '+data.end+'；'+
        (reasons[data.reason]||(data.difference_rate===null?'账单为零，无法计算差异率':data.formula_version));
    } catch(e) {if(generation===billingGeneration){$('billing-rows').replaceChildren();$('billing-status').textContent='计算失败，请检查日期范围（最多31天）和金额后重试';}}
  }
  async function daily() {
    const generation=++dailyGeneration;
    $('daily-rows').replaceChildren();$('daily-status').textContent='加载中…';
    try {
      const result=await adminRequest('GET','/api/admin/voice/metrics/daily?day='+encodeURIComponent($('daily-date').value)+'&simulated_pricing='+$('daily-simulated').checked);
      if(generation!==dailyGeneration)return;
      if(!result || result.code!==0)throw new Error('unavailable');
      result.data.metrics.forEach(item=>row('daily-rows',[names[item.name]||item.name,value(item),
        reasons[item.reason]||(item.status==='provisional'?'尚有未完成通话或任务':'') ]));
      $('daily-status').textContent='统计日期：'+result.data.date+'（北京时间）；按当前持久化结果计算'+(result.data.pricing?'；模拟估算 CNY 0.06/分钟':'');
    } catch(e) {if(generation===dailyGeneration){$('daily-rows').replaceChildren();$('daily-status').textContent='加载失败，请重试';}}
  }
  async function observations() {
    const generation=++observationGeneration;
    $('observation-rows').replaceChildren();$('capability-rows').replaceChildren();$('observation-status').textContent='加载中…';
    try {
      const result=await adminRequest('GET','/api/admin/voice/metrics/observations?day='+encodeURIComponent($('observation-date').value));
      if(generation!==observationGeneration)return;
      if(!result || result.code!==0)throw new Error('unavailable');
      const data=result.data;
      data.capability_metrics.forEach(item=>row('capability-rows',[names[item.name]||item.name,value(item),reasons[item.reason]||(item.unit==='text_snapshot'?'文本状态采样 '+item.sample_count+' 次；不代表回复数':'')]));
      data.events.forEach(item=>{
        if(item.status!=='available'){row('observation-rows',[item.name,'—',statusNames[item.status]||'不可测']);return;}
        item.samples.forEach(sample=>row('observation-rows',[item.name,JSON.stringify(sample.dimensions),sample.value]));
      });
      data.durations.forEach(item=>{
        if(item.status!=='available'){row('observation-rows',[item.name+'（分位数）','—',statusNames[item.status]||'不可测']);return;}
        item.groups.forEach(group=>row('observation-rows',[item.name+'（分位数）',JSON.stringify(group.dimensions),
          group.status==='available'?[group.p50_ms,group.p90_ms,group.p95_ms].join(' / ')+' ms；样本 '+group.sample_count:'不可测']));
      });
      $('observation-status').textContent='观测日期：'+data.date+'（UTC）；不保证样本完整';
    } catch(e) {if(generation===observationGeneration){$('observation-rows').replaceChildren();$('capability-rows').replaceChildren();$('observation-status').textContent='加载失败，请重试';}}
  }
  function renderHistory() {
    $('history-rows').replaceChildren();
    if(!historyData)return;
    historyData.days.forEach(day=>{
      const item=day.metrics.find(metric=>metric.name===$('history-metric').value);
      if(item)row('history-rows',[day.date,value(item),reasons[item.reason]||'',item.computed_at_utc||'—']);
    });
  }
  async function history() {
    const generation=++historyGeneration;
    historyData=null;renderHistory();$('history-status').textContent='加载中…';
    try {
      const result=await adminRequest('GET','/api/admin/voice/metrics/history?start='+encodeURIComponent($('history-start').value)+'&end='+encodeURIComponent($('history-end').value)+'&simulated_pricing='+$('history-simulated').checked);
      if(generation!==historyGeneration)return;
      if(!result||result.code!==0)throw new Error('unavailable');
      historyData=result.data;renderHistory();
      $('history-status').textContent='已落库结果：'+historyData.start+' 至 '+historyData.end+'（北京时间）'+(historyData.pricing?'；模拟估算 CNY 0.06/分钟':'');
    } catch(e) {if(generation===historyGeneration){historyData=null;renderHistory();$('history-status').textContent='加载失败，请检查日期范围（最多31天）后重试';}}
  }
  Object.keys(names).slice(0,10).forEach(name=>{
    const option=document.createElement('option');option.value=name;option.textContent=names[name];$('history-metric').append(option);
  });
  $('history-metric').value='billable_seconds';
  $('history-metric').addEventListener('change',renderHistory);
  $('history-form').addEventListener('submit',event=>{event.preventDefault();history();});
  const now=new Date();
  $('daily-date').value=new Date(now.getTime()+8*3600000).toISOString().slice(0,10);
  $('observation-date').value=now.toISOString().slice(0,10);
  $('history-end').value=new Date(now.getTime()+8*3600000-86400000).toISOString().slice(0,10);
  $('history-start').value=new Date(now.getTime()+8*3600000-7*86400000).toISOString().slice(0,10);
  $('billing-start').value=$('history-end').value;$('billing-end').value=$('history-end').value;
  $('billing-form').addEventListener('submit',event=>{event.preventDefault();billing();});
  $('daily-form').addEventListener('submit',event=>{event.preventDefault();daily();});
  $('observation-form').addEventListener('submit',event=>{event.preventDefault();observations();});
  const tabKeys=['daily','history','billing','observation'];
  const tabLoaders={daily,history,billing,observation:observations};
  const tabItems=Array.from(document.querySelectorAll('#voice-metrics-tabs [data-metrics-tab]'));
  const tabPanels=Array.from(document.querySelectorAll('[data-metrics-panel]'));
  const loadedTabs=new Set();
  let activeTab=null;
  function tabFromLocation() {
    const key=new URLSearchParams(location.search).get('tab');
    return tabKeys.includes(key)?key:'daily';
  }
  function writeTabUrl(key,mode) {
    const url=new URL(location.href);
    url.searchParams.set('tab',key);
    window.history[mode+'State']({voiceMetricsTab:key},'',url.pathname+url.search+url.hash);
  }
  function activateTab(key,mode,focus) {
    const normalized=tabKeys.includes(key)?key:'daily';
    const changed=normalized!==activeTab;
    activeTab=normalized;
    tabItems.forEach(item=>{
      const selected=item.dataset.metricsTab===normalized;
      item.classList.toggle('active',selected);
      item.setAttribute('aria-selected',String(selected));
      item.tabIndex=selected?0:-1;
      if(selected&&focus)item.focus();
    });
    tabPanels.forEach(panel=>{
      const selected=panel.dataset.metricsPanel===normalized;
      panel.classList.toggle('active',selected);
      panel.hidden=!selected;
    });
    if(mode==='replace'||(mode==='push'&&changed))writeTabUrl(normalized,mode);
    if(!loadedTabs.has(normalized)) {
      loadedTabs.add(normalized);
      tabLoaders[normalized]();
    }
  }
  tabItems.forEach((item,index)=>{
    item.addEventListener('click',()=>activateTab(item.dataset.metricsTab,'push',false));
    item.addEventListener('keydown',event=>{
      let nextIndex=null;
      if(event.key==='ArrowRight'||event.key==='ArrowDown')nextIndex=(index+1)%tabItems.length;
      if(event.key==='ArrowLeft'||event.key==='ArrowUp')nextIndex=(index-1+tabItems.length)%tabItems.length;
      if(event.key==='Home')nextIndex=0;
      if(event.key==='End')nextIndex=tabItems.length-1;
      if(nextIndex===null)return;
      event.preventDefault();
      activateTab(tabItems[nextIndex].dataset.metricsTab,'push',true);
    });
  });
  window.addEventListener('popstate',()=>activateTab(tabFromLocation(),null,false));
  window.addEventListener('pagehide',()=>{
    dailyGeneration++;observationGeneration++;historyGeneration++;billingGeneration++;historyData=null;loadedTabs.clear();
    ['billing-rows','history-rows','daily-rows','capability-rows','observation-rows'].forEach(id=>$(id).replaceChildren());
    ['billing-status','history-status','daily-status','observation-status'].forEach(id=>$(id).textContent='');
  });
  window.addEventListener('pageshow',event=>{if(event.persisted)activateTab(tabFromLocation(),null,false);});
  activateTab(tabFromLocation(),'replace',false);
})();

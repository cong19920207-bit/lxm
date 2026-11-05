(()=>{const A=window.PetAdmin;
A.handlers.overview=async(params,box,current)=>{
 const at=params.at||new Date().toISOString(),q=new URLSearchParams({at,...(params.start?{start:params.start}:{})});
 const shortcuts=A.el('nav',undefined,{class:'pet-shortcuts','aria-label':'常用工作入口'});
 for(const[title,description,section,extra]of [['查找宠物','查看档案与真实记录','pets',{}],['排查任务','定位失败、略过和未知结果','tasks',{}],['调整配置','维护成长、互动与成本','rules',{}],['追溯变更','比较版本与操作结果','versions',{}]]){const a=A.link('',{section,...extra});a.append(A.el('strong',title),A.el('span',description),A.el('b','↗',{'aria-hidden':'true'}));shortcuts.append(a);}
 box.append(A.el('p',`统计截止 ${A.formatTime(at)}（北京时间）`,{class:'pet-meta'}));
 const stats=A.el('div',undefined,{class:'pet-stats'}),values={};
 for(const[k,title,help]of [['adopted','已领养宠物 · 累计','截至当前查询时点'],['active','近24小时有效活跃','按有效参与记录统计'],['requests','今日模型请求','正式与调试请求合计'],['issues','待关注任务','需逐项核对原因与资格']]){const c=A.card(title);c.dataset.metric=k;values[k]=A.el('p','读取中',{class:'pet-value'});c.append(values[k],A.el('p',help,{class:'pet-meta'}));stats.append(c);}box.append(stats,shortcuts);
 const grid=A.el('div',undefined,{class:'pet-overview-grid'}),areas={};
 for(const[k,title]of [['health','需要关注与任务运行'],['population','陪伴档位与运行状态'],['budgets','分层预算与并发'],['requests','内容与请求']]){areas[k]=A.card(title);grid.append(areas[k]);}box.append(grid);
 await Promise.all(Object.keys(areas).map(async name=>{const target=areas[name];try{
  const d=await A.api('/overview/'+name+'?'+q);if(current!==A.epoch)return;
  if(name==='population'){
   values.adopted.textContent=d.adopted_ids.length;values.active.textContent=d.active_ids.length;
   const bands=A.el('div',undefined,{class:'pet-band-grid'});for(const[band,count]of Object.entries(d.tiers)){const a=A.link('',{section:'pets',band,at:d.at});a.append(A.el('span',A.term(band)),A.el('strong',String(count)));bands.append(a);}target.append(bands,A.fields({runtime:d.runtime,denominator:d.denominator}),A.link('管理运行开关 →',{section:'settings',domain:'runtime'}));
  }
  if(name==='requests'){
   values.requests.textContent=d.attempt_ids.length;target.append(A.fields({formal:d.formal_ids.length,debug:d.debug_ids.length,unknown:d.unknown_ids.length,usage_missing:d.usage_missing_ids.length,event_count:d.event_ids.length,usage:d.usage,elapsed:d.elapsed,template_fallback:d.template_fallback,start:d.start,at:d.at}));
   const evidence=A.el('details',undefined,{class:'pet-diagnostics'});evidence.append(A.el('summary',`请求记录与统计依据（${d.attempts.length}）`));for(const row of d.attempts){const item=A.el('details');item.append(A.el('summary',`${row.id} · ${row.state}`),A.fields(row),A.link('请求详情',{section:'tasks',type:'attempt_id',id:row.id,at:d.at,from:location.search.slice(1)}));evidence.append(item);}target.append(evidence);
  }
  if(name==='health'){
   values.issues.textContent=d.issues.length;
   if(!d.issues.length)target.append(A.el('p','当前没有待关注任务；运行覆盖情况见下方。',{class:'pet-empty is-compact'}));
   for(const issue of d.issues){const row=A.el('div',undefined,{class:'pet-issue'});row.append(A.el('span',A.term(issue.state),{class:'pet-badge is-warning'}),A.link(`${A.kind(issue.kind)} · ${issue.reason?A.reasonLabel(issue.reason):A.term(issue.state)}`,{section:'tasks',...issue,from:location.search.slice(1)}));target.append(row);}
   const names={care:'自动照顾',growth_snapshot:'成长快照',birthday:'生日纪念',daily_overview:'每日聚合',generation:'文案生成',cleanup:'过期清理'};
   for(const h of d.health){const item=A.el('details',undefined,{class:'pet-health-row'}),summary=A.el('summary');summary.append(A.el('strong',names[h.kind]||h.kind),A.el('span',`${h.kind} · ${h.coverage==='observed'?'已有运行记录':'尚未覆盖'} · 待处理 ${h.pending_ids.length}`,{class:'pet-health-caption'}));item.append(summary,A.fields(h));target.append(item);}
   target.append(A.link('进入任务排查 →',{section:'tasks'}));
  }
  if(name==='budgets'){
   if(!d.configured)target.append(A.context('请求发送受限','全局配置未完成；当前不可发送。请在规则与成本中核对预算及并发上限。'));
   target.append(A.fields(d.concurrency));
   for(const row of d.layers){const item=A.el('details',undefined,{class:'pet-budget-row'});item.append(A.el('summary',`${A.term(row.layer)} · 剩余 ${row.remaining??'未知'} / ${row.limit??'未配置'}`),A.fields(row));for(const id of [...row.consumed_ids,...row.reserved_ids])item.append(A.link('请求 '+id,{section:'tasks',id,type:'attempt_id',at:d.at,from:location.search.slice(1)}));target.append(item);}
   target.append(A.link('调整预算与成本 →',{section:'rules',domain:'rules',group:'budget'}));
  }
 }catch(e){if(current===A.epoch){A.error(target,e);for(const k of ({population:['adopted','active'],requests:['requests'],health:['issues']}[name]||[]))values[k].textContent='读取失败';}}}));
};})();

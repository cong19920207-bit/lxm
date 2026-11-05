const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stamp=value=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}):'无记录';
const source=f=>f.source==='rule_settlement'?'规则来源':f.source==='admin_correction'?'后台更正':(f.participants||[]).map(x=>({player:'你',xiaomeng:'小梦'}[x]||x)).join('和')||'系统';
export function mountRecords(view,{root,api}){
 const scope=view.scope,panel=document.createElement('section');panel.className='pet-records';root.append(panel);scope.own(()=>panel.remove());
 let selectedDate=null,data=null,event=null,error=null,loading=false,epoch=0,albumData=null,albumCursor=null,albumStack=[],recordVersion=view.pet?.record_version;
 const button=(text,action,attrs='')=>`<button type="button" class="text-button" data-record="${action}" ${attrs}>${text}</button>`;
 const tabs=()=>'<div class="tabs" role="tablist"><button role="tab" data-record="tab-daily" aria-selected="'+(view.route==='records')+'">每日记录</button><button role="tab" data-record="tab-album" aria-selected="'+(view.route==='album')+'">共同事件册</button></div>';
 const toolbar=()=>'<div class="records-toolbar">'+tabs()+button('回房间','home')+'</div>';
 const kindLabels={adopted:'领养',joint_ball:'共同陪玩',joint_photo:'共同留影',natural_growth:'自然成长',birthday:'生日纪念'};
 function render(){
  if(!scope.active)return;
  if(view.pet?.record_version!==recordVersion){recordVersion=view.pet?.record_version;epoch++;data=null;albumData=null;albumCursor=null;albumStack=[];loading=false;}
  const host=root.querySelector('[data-records-slot]');if(host&&panel.parentElement!==host)host.append(panel);panel.hidden=!host;
  if(view.route==='event'&&event){const historical=event.historical;panel.innerHTML='<article data-source-event="'+escape(event.event_id)+'"><h2>'+escape(event.title)+'</h2>'+(event.result?.display_body?'<p>'+escape(event.result.display_body)+'</p>':'')+'<p>'+escape(source(event))+' · '+escape(event.business_date)+'</p><p>发生：'+escape(stamp(event.occurred_at))+'</p><p>记录：'+escape(stamp(event.recorded_at))+'</p>'+(historical?'<p>当时的'+escape(historical.name||'小狗')+' · '+escape({puppy:'幼犬',growing:'成长期',adult:'成年'}[historical.stage]||'阶段未记录')+'</p>'+(historical.available?'<img alt="当时的外观" src="'+escape(historical.image_url)+'" style="max-width:100%">':'<p>当时的外观资源暂不可用。</p>'):'')+'</article>'+button(event.return_context.surface==='album'?'返回事件册':'返回当天记录','back');return;}
  if(view.route==='album'){
   panel.innerHTML=toolbar()+'<p class="subtle">按时间倒序，留下值得记住的日常。</p>';
   if(loading){panel.innerHTML+='<p>正在读取…</p>';return;}if(error){panel.innerHTML+='<p>事件册暂时没能读取。</p>'+button('重新读取','album-retry');return;}
   if(!albumData){void loadAlbum();return;}
   panel.innerHTML+=albumData.items.map(f=>'<article class="paper memory-card" data-source-event="'+escape(f.event_id)+'"><div><span class="tag">'+escape(kindLabels[f.type]||'共同经历')+'</span></div>'+(f.historical?.available&&f.historical.kind==='photo'?'<img alt="这一刻的留影" style="max-width:100%" src="'+escape(f.historical.image_url)+'">':'')+'<button type="button" class="row-link" data-event="'+escape(f.event_id)+'">'+escape(f.title)+'</button><p>'+escape(f.business_date)+' · '+escape(source(f))+'</p><p class="small">'+escape(f.historical?.name||'')+(f.historical?.name?' · 当时的名字':'')+'</p></article>').join('')||( '<p>还没有收录的经历。</p>');
   if(albumStack.length)panel.innerHTML+=button('上一页','album-prev');if(albumData.next_cursor)panel.innerHTML+=button('下一页','album-next');return;
  }
  if(view.route!=='records'){panel.innerHTML='';return;}
  panel.innerHTML=toolbar()+'<div class="date-row">'+button('‹','previous-day','aria-label="上一日"')+'<label><span>记录日期</span><input type="date" aria-label="记录日期" value="'+escape(selectedDate||data?.date||'')+'" '+(data?'max="'+escape(data.today)+'"':'')+'></label>'+button('›','next-day','aria-label="下一日" '+(selectedDate&&data?.today&&selectedDate>=data.today?'disabled':''))+'</div>';
  if(loading){panel.innerHTML+='<p>正在读取这一天的记录…</p>';return;}
  if(error){panel.innerHTML+='<p role="alert">这一天的记录暂时没能读取。</p>'+button('重新读取','retry');return;}
  if(!data){void load();return;}
  const labels={touch:'抚摸',feed:'进食',play:'陪玩',joint_ball:'共同玩球',joint_photo:'共同留影'};
  panel.innerHTML+='<section class="paper"><h2>这一天的事实</h2><p>'+escape(Object.entries(data.interaction_counts).map(([key,n])=>(labels[key]||key)+' '+n+' 次').join(' · ')||'没有已记录的互动')+'</p><p>'+escape(Object.entries(data.participants).map(([key,n])=>({player:'你',xiaomeng:'小梦',joint:'你和小梦'}[key]||key)+'参与 '+n+' 次').join(' · ')||'没有实际参与记录')+'</p></section>';
  let observation='<section class="paper"><h3>状态观察</h3><p>'+(data.mood_observation?'已有 '+data.snapshots.length+' 次状态记录；仅说明记录时的情况。':'当天没有状态快照，无法判断全日心情。')+'</p><p class="subtle">事实覆盖到：'+escape(stamp(data.coverage_until))+'</p>';
  const valueLabels={satiety:'饱腹',energy:'精力',mood:'心情'};
  for(const change of data.state_changes||[])observation+='<p>'+escape(Object.keys(valueLabels).filter(k=>change.before[k]!==change.after[k]).map(k=>valueLabels[k]+' '+Math.round(change.before[k])+' → '+Math.round(change.after[k])).join('，'))+'</p>';
  panel.innerHTML+=observation+'</section>';
  panel.innerHTML+='<section class="record-timeline"><h3>时间线</h3><ol class="timeline">'+data.timeline.map(f=>'<li class="timeline-item" data-source-event="'+escape(f.event_id)+'"><button type="button" class="record-detail" data-event="'+escape(f.event_id)+'">'+escape(f.title)+'</button><p>'+escape(source(f))+' · '+escape(stamp(f.occurred_at))+'</p></li>').join('')+'</ol></section>';
  panel.innerHTML+='<section class="paper daily-summary"><h3>已保存的总结</h3>'+(data.summaries.length?data.summaries.map(t=>'<details><summary>展开阅读</summary><p>'+escape(t.body)+'</p>'+(t.source_photo_cleared?'<p class="subtle">来源照片已清理，原文保留。</p>':'')+'</details>').join(''):'<p>这一天没有已保存的总结，已有事实仍可查看。</p>')+'</section>';
 }
 async function load(){const ticket=++epoch;loading=true;error=null;render();try{const result=await api.call('/records'+(selectedDate?'?day='+encodeURIComponent(selectedDate):''));if(!scope.active||ticket!==epoch)return;data=result;selectedDate=result.date;}catch(e){if(ticket===epoch)error=e;}finally{if(scope.active&&ticket===epoch){loading=false;render();}}}
 async function loadAlbum(){const ticket=++epoch;loading=true;error=null;render();try{const result=await api.call('/album'+(albumCursor?'?cursor='+encodeURIComponent(albumCursor):''));if(!result||!Array.isArray(result.items))throw Error('album_unavailable');if(scope.active&&ticket===epoch)albumData=result;}catch(e){if(ticket===epoch)error=e;}finally{if(scope.active&&ticket===epoch){loading=false;render();}}}
 scope.listen(panel,'change',e=>{if(e.target.matches('input[type=date]')){selectedDate=e.target.value;data=null;void load();}});
 scope.listen(panel,'click',async e=>{
  const id=e.target.closest('[data-event]')?.dataset.event;
  if(id){const originRoute=view.route,origin=originRoute==='album'?'album':'daily',originDate=origin==='album'?albumData.items.find(f=>f.event_id===id).business_date:selectedDate,ticket=++epoch;try{const result=await api.call('/events/'+encodeURIComponent(id)+'?origin='+origin+'&origin_date='+encodeURIComponent(originDate));if(scope.active&&ticket===epoch&&view.route===originRoute){event=result;view.go('event');}}catch(_){view.notify('暂时没能读取这条记录。');}return;}
  const action=e.target.closest('[data-record]')?.dataset.record;if(action==='tab-daily'){view.go('records');return;}if(action==='tab-album'){view.go('album');return;}if(action==='previous-day'||action==='next-day'){const base=selectedDate||data?.date;if(base){const date=new Date(base+'T12:00:00+08:00');date.setUTCDate(date.getUTCDate()+(action==='previous-day'?-1:1));const next=date.toISOString().slice(0,10);if(next<=(data?.today||base)){selectedDate=next;data=null;void load();}}return;}if(action==='home')view.go('home');if(action==='retry')void load();
  if(action==='back'){if(event.return_context.surface==='album')view.go('album');else{selectedDate=event.return_context.date;view.go('records');}}
  if(action==='album-retry')void loadAlbum();
  if(action==='album-next'){albumStack.push(albumCursor);albumCursor=albumData.next_cursor;albumData=null;void loadAlbum();}
  if(action==='album-prev'){albumCursor=albumStack.pop()??null;albumData=null;void loadAlbum();}
 });
 scope.listen(root,'pet:completed',()=>{epoch++;data=null;albumData=null;albumCursor=null;albumStack=[];loading=false;render();});
 scope.listen(root,'pet:render',render);render();return {reload:load,inspect:()=>({selectedDate,event,data})};
}

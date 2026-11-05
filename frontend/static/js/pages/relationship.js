import { createPageTimers } from '../app/page-timers.js';
import { parseRelationshipTime, beijingDay, recentLogWindow, visibleRecentLogs } from './relationship-data.js';

export async function mount(context) {
  const {root,services}=context, byId=id=>root.querySelector('#'+id);
  if(!context.valid()||!services.auth.snapshot().authenticated)return {unmount(){}};
  const options=()=>({authPolicy:'protected-home-modal',routeEpoch:context.routeEpoch,
    routeCurrent:()=>context.router.current?.context.routeEpoch===context.routeEpoch,
    isCurrent:context.valid,signal:context.signal});
  const request=url=>services.auth.request('GET',url,undefined,options());
  const escapeHtml=value=>{const el=document.createElement('span');el.textContent=String(value??'');return el.innerHTML;};
  const icon=(name,cls='')=>'<svg aria-hidden="true" class="'+cls+'"><use href="#rel-icon-'+name+'"/></svg>';
  const {setTimeout,requestAnimationFrame}=createPageTimers(context);
  const number=value=>Math.max(0,Number(value)||0);
  const time=value=>{const date=parseRelationshipTime(value);return date?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(date):'';};
  const dateLabel=value=>{const day=beijingDay(value);if(!day)return '';const [,month,date]=day.split('-');return Number(month)+'月'+Number(date)+'日';};
  let pageData=null,levelLease=null,levelOverlay=null,pendingUpgrade=null,active=true;
  let logs=[],logPage=1,logTotal=0,logLoading=false,logNoMore=false,logError=false,logWindow=recentLogWindow();
  const logIds=new Set(),restoredPages=Math.max(1,Math.min(100,Number(context.state?.cursor)||1));
  let sheetMode='',sheetLease,logResetPending=false;
  await context.scope.adopt(services.resources.style('css/bgm.css'),release=>release());
  for(const name of ['bgm-page','bgm-record','bgm-bubble']) {
    await services.shared.script('js/'+name+'.js');if(!context.valid())return {unmount(){}};
  }
  const audioPage=services.audio.attachPage(context,'content'),bubble=BgmBubble.mount(audioPage);
  if(bubble)context.cleanup(()=>bubble.destroy());
  const sheet=byId('relationship-sheet');
  sheetLease=services.overlays.register({kind:'relationship-sheet',ownerId:context.scope.ownerId,element:sheet,background:byId('page-body'),
    open:()=>sheet.showModal(),close:()=>{
      sheet.close();sheetMode='';
      if(pendingUpgrade&&context.valid())setTimeout(()=>{const info=pendingUpgrade;pendingUpgrade=null;if(info)showLevelUpModal(info);},0);
    }});
  context.scope.listen(sheet,'cancel',event=>{event.preventDefault();sheetLease.close();});
  context.scope.listen(sheet,'close',()=>sheetLease.close());
  context.scope.listen(sheet,'click',event=>{
    if(event.target!==sheet)return;
    const box=sheet.getBoundingClientRect();
    if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)sheetLease.close();
  });
  function openSheet(mode,title,subtitle,html) {
    sheetMode=mode;sheet.classList.toggle('records-sheet',mode==='logs');
    byId('relationship-sheet-title').textContent=title;
    byId('relationship-sheet-subtitle').textContent=subtitle||'';
    byId('relationship-sheet-content').innerHTML=html;
    byId('relationship-sheet-content').scrollTop=0;
    sheetLease.open();
  }
  function animateNumber(id,value) {
    const el=byId(id),target=number(value),start=performance.now();
    if(matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=target;return;}
    function tick(now){if(!context.valid())return;const t=Math.min((now-start)/300,1);el.textContent=Math.round(target*(1-Math.pow(1-t,3)));if(t<1)requestAnimationFrame(tick);}
    requestAnimationFrame(tick);
  }
  function renderDetail(data) {
    const info=data.level_info,growth=data.growth_info,ms=data.milestones;
    byId('rel-level-badge').textContent=info.name;
    byId('rel-desc').textContent=info.description||'';
    byId('rel-perks-summary').textContent='已解锁 '+(info.perks||[]).length+' 项陪伴权益';
    byId('keepsake-number').textContent='NO. '+number(ms.known_days);
    animateNumber('m-known-days',ms.known_days);animateNumber('m-conv-rounds',ms.total_conversation_rounds);animateNumber('m-login-days',ms.consecutive_login_days);
    const percent=Math.min(100,number(growth.progress_percent));
    byId('progress-percent').textContent=Math.round(percent)+'%';
    if(growth.is_max_level)byId('progress-content').innerHTML='<div class="rel-max-badge"><strong>已达到最高等级「'+escapeHtml(info.name)+'」</strong><p class="sub">所有陪伴权益已解锁，我们的故事还在继续。</p></div>';
    else {
      byId('progress-content').innerHTML='<div class="progress-labels"><span class="current-stage">'+icon('heart')+escapeHtml(info.name)+'</span><span class="next-stage">'+escapeHtml(info.next_level_name||'下一阶段')+icon('lock')+'</span></div>'+
        '<div class="progress" id="detail-bar" role="progressbar" aria-label="亲密进度" aria-valuemin="0" aria-valuemax="'+number(growth.points_needed)+'" aria-valuenow="'+number(growth.points_in_level)+'"><div id="detail-fill"></div></div>'+
        '<div class="progress-meta"><span><strong>'+number(growth.points_in_level)+'</strong> / '+number(growth.points_needed)+' 亲密值</span><span>还差 <strong>'+number(growth.points_to_next)+'</strong></span></div>'+
        '<button class="next-unlock" data-action="perks"><span class="unlock-icon">'+icon('spark')+'</span><span><strong>下一站，'+escapeHtml(info.next_level_name||'更多陪伴')+'</strong><small>'+escapeHtml((info.next_perks||[])[0]||'一起走向下一段故事')+'</small></span>'+icon('arrow','chevron')+'</button>';
      byId('detail-fill').style.width=percent+'%';
    }
    renderToday(data.today_growth,ms.consecutive_login_days);
    renderTimeline(data.level_history,info,ms,data.ai_current_emotion);
  }
  function todayItems(tg,days) {
    return [
      {type:'dialog',icon:'chat',title:'日常对话',sub:tg.today_dialog_limit_reached?'今天的对话成长已满':'聊聊今天发生的事',points:number(tg.today_dialog_points),limit:number(tg.today_dialog_limit??(number(tg.today_dialog_points)+number(tg.today_remaining_dialog))),rule:'每完成一轮对话，获得 2 亲密值。\n今天还可获得 '+number(tg.today_remaining_dialog)+' 亲密值。'},
      {type:'voice',icon:'phone',title:'语音陪伴',sub:'听见彼此的声音',points:number(tg.today_voice_points),limit:tg.today_voice_limit==null?null:number(tg.today_voice_limit),rule:'通话结束后，按有效通话时长结算亲密值。\n今天已获得 '+number(tg.today_voice_points)+' 亲密值。'},
      {type:'deep',icon:'moon',title:'深度聊天',sub:'留一点时间，慢慢说',points:number(tg.today_session_points),limit:number(tg.today_session_limit??20),rule:'连续互动满 10 分钟，可获得 20 亲密值，每天一次。\n以成功收到回复的对话计时，两轮发言间隔超过 5 分钟或跨过午夜，就重新计时。\n今天已获得 '+number(tg.today_session_points)+' 亲密值。'},
      {type:'login',icon:'sun',title:'每日见面',sub:number(tg.today_login_points)>0?'今天你已经来过了':'新的一天，来见见她',points:number(tg.today_login_points),rule:'今天已获得 '+number(tg.today_login_points)+' 亲密值。\n已连续 '+number(days)+' 天来见她。'},
      {type:'reply',icon:'mail',title:'回应她的消息',sub:'让她知道，你也在想她',points:number(tg.today_reply_points),limit:number(tg.today_reply_limit??20),rule:'回应她新发来的主动消息并收到回复，可获得 10 亲密值，每天最多 20 亲密值。\n同一条消息只奖励一次，仅查看消息不计入。\n今天已获得 '+number(tg.today_reply_points)+' 亲密值。'}
    ];
  }
  function renderToday(tg,days) {
    byId('today-total').innerHTML='+'+number(tg.today_total_points)+' <small>亲密值</small>';
    byId('today-list').innerHTML=todayItems(tg,days).map(item=>{
      const completed=item.type==='login'?item.points>0:item.limit>0&&item.points>=item.limit;
      const status=completed?'今日已完成':item.limit===0?'今日暂无奖励':item.points>0?'进行中':'待完成';
      const subtitle=completed||item.limit===0?status:status+' · '+item.sub;
      return '<button class="today-row'+(completed?' completed':'')+'" data-rule="'+item.type+'"><span class="activity-icon">'+icon(item.icon)+'</span><span class="activity-copy"><strong class="tc-title">'+item.title+'</strong><small>'+subtitle+'</small></span><span class="activity-result">'+(item.points>0?'+':'')+item.points+(item.limit!=null?' <small>/ '+item.limit+'</small>':'')+(completed?icon('check'):'')+'</span>'+icon('info','row-info')+'</button>';
    }).join('');
  }
  function renderTimeline(history,info,ms,emotion) {
    const records=(history||[]).filter(item=>item.achieved_at);
    if(!records.length){byId('timeline-content').innerHTML='<div class="empty-state">'+(ms.first_conversation_at?'我们相识于 '+dateLabel(ms.first_conversation_at)+'，<br>':'')+'我们的故事，从这里开始。</div>';return;}
    byId('timeline-content').innerHTML=records.map((item,index)=>'<div class="milestone"><div class="milestone-marker">'+icon('heart')+'</div><div class="milestone-content"><span class="milestone-date">'+escapeHtml(beijingDay(item.achieved_at).replaceAll('-','.'))+'</span><h3>我们，成为'+escapeHtml(item.level_name)+'了。</h3><p>多了一份熟悉，<br>也多了一份信任。</p>'+((item.to_level===info.level||item.level_name===info.name)&&index===0?'<span class="milestone-tag">当前关系 · '+escapeHtml(info.name)+'</span>':'')+'</div>'+(index===0?'<figure class="memory-photo"><img id="linxiaomeng-avatar" src="/static/images/avatar/default.png" alt="林小梦"><figcaption>很高兴，遇见你。</figcaption><span aria-hidden="true">♡</span></figure>':'')+'</div>').join('');
    const avatar=byId('linxiaomeng-avatar'),fallback=avatar.src;
    context.scope.listen(avatar,'error',()=>{if(avatar.src!==fallback)avatar.src=fallback;});
    if(typeof AVATAR_MAP!=='undefined')avatar.src=AVATAR_MAP[emotion]||AVATAR_MAP.default||fallback;
  }
  function perks(next=false) {
    if(!pageData)return;
    const info=pageData.level_info,items=next?info.next_perks:info.perks;
    openSheet('perks',next?'关系里，多一点特别':'我们已经拥有的',next?'下一阶段 · '+info.next_level_name:'当前关系 · '+info.name,
      (next?'<p class="next-intro">再积累 <strong>'+number(pageData.growth_info.points_to_next)+' 亲密值</strong>，一起走向下一站。</p>':'')+
      '<div class="perks-list">'+(items||[]).map((value,index)=>'<div>'+icon(['chat','moon','heart'][index%3])+'<span><strong>'+escapeHtml(value)+'</strong></span>'+(!next?icon('check','check'):'')+'</div>').join('')+'</div><button class="primary-button" data-action="close-sheet">慢慢来，我们还有很多时间</button>');
  }
  function renderRecord(item,preview=false) {
    const icons={dialog:'chat',voice_call:'phone',long_session:'moon',daily_login:'sun',reply_agent:'mail'};
    return '<div class="record-row log-item" data-growth-id="'+escapeHtml(item.id??'')+'" data-date="'+beijingDay(item.created_at)+'"><span class="record-icon">'+icon(icons[item.action_type]||'spark')+'</span><div class="record-copy"><strong class="li-label">'+escapeHtml(item.action_label)+'</strong><time class="li-time">'+(preview?dateLabel(item.created_at)+' · ':'')+time(item.created_at)+'</time></div><span class="record-points li-points'+(number(item.points)===0?' zero':'')+'" aria-label="增加 '+number(item.points)+' 亲密值">+'+number(item.points)+'</span></div>';
  }
  function renderLogs() {
    const preview=logs.slice(0,5),empty=logError?'成长记录加载失败':logLoading?'正在加载成长记录…':'近 7 天暂无成长记录';
    byId('log-list').innerHTML=preview.length?preview.map(item=>renderRecord(item,true)).join(''):'<div class="empty-state">'+empty+(logError?'<button class="retry-button" data-action="retry-logs">重试</button>':'')+'</div>';
    byId('log-total').textContent='近 7 天'+(logs.length?' · 最近 '+preview.length+' 条':'');
    byId('log-count').textContent=logTotal+' 条';
    byId('open-logs').disabled=!logs.length;
    if(sheetMode==='logs')renderLogSheet();
  }
  function renderLogSheet() {
    const content=byId('relationship-sheet-content'),scroll=content.scrollTop,focused=document.activeElement?.dataset.action==='more-logs';
    let date='';
    const rows=logs.map(item=>{const key=beijingDay(item.created_at),heading=date!==key?'<h3 class="record-group-date log-date-sep">'+dateLabel(item.created_at)+'</h3>':'';date=key;return heading+renderRecord(item);}).join('');
    content.innerHTML='<div class="sheet-meta"><span>近 7 天，共 '+logTotal+' 条</span><span>北京时间 · 含今天</span></div>'+(rows||'<div class="empty-state">近 7 天暂无成长记录</div>')+
      (logNoMore?'<p class="demo-caption">近 7 天的记录已全部展示</p>':'<button class="load-more" data-action="more-logs" '+(logLoading?'disabled':'')+'>'+(logLoading?'正在加载…':logError?'加载失败，点击重试':'加载更早记录（近 7 天）')+'</button>');
    content.scrollTop=scroll;
    if(focused)content.querySelector('[data-action="more-logs"]')?.focus({preventScroll:true});
  }
  function resetLogs() {
    logs=[];logIds.clear();logPage=1;logTotal=0;logNoMore=false;logError=false;
    logWindow=recentLogWindow();logResetPending=false;
  }
  function refreshLogs() {
    if(logLoading){logResetPending=true;logs=visibleRecentLogs(logs,recentLogWindow());renderLogs();return;}
    resetLogs();void loadGrowthLog();
  }
  function scheduleDayChange() {
    setTimeout(()=>{refreshLogs();scheduleDayChange();},Math.max(1000,recentLogWindow().end-Date.now()+50));
  }
  scheduleDayChange();
  context.scope.listen(document,'visibilitychange',()=>{
    if(!document.hidden&&recentLogWindow().start!==logWindow.start)refreshLogs();
  });
  async function loadGrowthLog() {
    if(!active||logLoading||logNoMore)return false;
    logLoading=true;logError=false;renderLogs();
    try {
      const res=await request('/api/relationship/growth-log?page='+logPage+'&page_size=20');
      if(!context.valid())return false;
      if(logResetPending){resetLogs();logLoading=false;return await loadGrowthLog();}
      if(res.code!==0||!res.data)throw new Error('growth-log');
      const data=res.data,start=Date.parse(data.window_start),end=Date.parse(data.window_end);
      if(Number.isFinite(start)&&Number.isFinite(end)&&end-start===7*86400000){
        if(logPage>1&&(logWindow.start!==start||logWindow.end!==end)){
          resetLogs();logWindow={start,end};logLoading=false;return await loadGrowthLog();
        }
        logWindow={start,end};
      }
      logTotal=number(data.total);
      for(const item of visibleRecentLogs(data.list||[],logWindow)){
        const key=item.id??JSON.stringify([item.action_type,item.created_at,item.points]);
        if(!logIds.has(key)){logIds.add(key);logs.push(item);}
      }
      logNoMore=(data.list||[]).length<20||logPage*20>=logTotal;
      logPage++;return true;
    }catch(error){if(context.valid()&&!['AbortError','StaleRequestError'].includes(error.name))logError=true;return false;}
    finally{logLoading=false;if(context.valid())renderLogs();}
  }
  async function loadPage() {
    byId('page-body').classList.remove('content-failed');
    try {
      const res=await request('/api/relationship/detail');
      if(!context.valid())return;
      if(res.code!==0||!res.data)throw new Error('relationship-detail');
      pageData=res.data;renderDetail(pageData);byId('page-body').classList.add('content-loaded');
      if(context.router.consumeParam('just_leveled_up','true'))setTimeout(()=>showLevelUpModal(pageData.level_info),500);
      do {if(!await loadGrowthLog())break;}while(context.valid()&&!logNoMore&&logPage<=restoredPages);
    }catch(error){
      if(!context.valid())return;
      byId('page-body').classList.add('content-failed');
      if(!byId('relationship-error'))byId('page-body').insertAdjacentHTML('beforeend','<div id="relationship-error" class="empty-state">关系信息加载失败，请稍后重试。<button class="retry-button" data-action="retry-page">重新加载</button></div>');
    }
  }

  function showLevelUpModal(info) {
    if(!context.valid()||levelOverlay)return;
    if(sheetLease.isOpen()){pendingUpgrade=info;return;}
    const overlay=document.createElement('div');levelOverlay=overlay;
    overlay.className='levelup-overlay';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('aria-label','关系升级');
    overlay.innerHTML='<div class="levelup-box"><div class="particles" id="lu-particles"></div>'+
      '<div class="lu-title">🎉 恭喜升级！</div><div class="lu-subtitle">我们现在是「'+escapeHtml(info.name)+'」了</div>'+
      '<div class="lu-perks">'+(info.perks||[]).map(p=>'<div class="lu-perk">✨ '+escapeHtml(p)+'</div>').join('')+
      '</div><button type="button" class="lu-btn" id="lu-close-btn">继续聊天</button></div>';
    root.append(overlay);
    levelLease=services.overlays.register({kind:'relationship-upgrade',ownerId:context.scope.ownerId,
      element:overlay,background:byId('page-body'),close:()=>{
        overlay.classList.add('closing');overlay.querySelector('.particles')?.replaceChildren();
        // Match the original fade while keeping a deterministic cleanup if animationend is lost.
        setTimeout(()=>{overlay.remove();if(levelOverlay===overlay)levelOverlay=null;},300);
      }});
    levelLease.open();createParticles(byId('lu-particles'));byId('lu-close-btn').focus({preventScroll:true});
    context.scope.listen(overlay,'click',event=>{if(event.target===overlay||event.target.closest('#lu-close-btn'))levelLease.close();});
    context.scope.listen(overlay,'keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();levelLease.close();}
      if(event.key==='Tab'){event.preventDefault();byId('lu-close-btn')?.focus({preventScroll:true});}
    });
  }
    function createParticles(container) {
      if (!container) return
      const colors = ['#c084fc', '#e879f9', '#a855f7', '#f0abfc', '#ddd6fe', '#f9a8d4']
      for (let i = 0; i < 20; i++) {
        const p = document.createElement('div')
        p.className = 'particle'
        const size = 4 + Math.random() * 8
        p.style.width = size + 'px'
        p.style.height = size + 'px'
        p.style.background = colors[Math.floor(Math.random() * colors.length)]
        p.style.left = Math.random() * 100 + '%'
        p.style.top = 60 + Math.random() * 40 + '%'
        p.style.animationDelay = Math.random() * 1 + 's'
        p.style.animationDuration = (1.5 + Math.random() * 1) + 's'
        container.appendChild(p)
      }
    }




  context.scope.listen(root,'click',event=>{
    const action=event.target.closest('[data-action]')?.dataset.action;
    if(action==='back')context.router.back();
    if(action==='current-perks')perks();
    if(action==='perks')perks(true);
    if(action==='close-sheet')sheetLease.close();
    if(action==='logs'){
      if(recentLogWindow().start!==logWindow.start)refreshLogs();
      openSheet('logs','成长记录','每一次靠近，都有迹可循','');renderLogSheet();
    }
    if(action==='more-logs'||action==='retry-logs')void loadGrowthLog();
    if(action==='retry-page'){byId('relationship-error')?.remove();void loadPage();}
    const rule=event.target.closest('[data-rule]')?.dataset.rule;
    if(rule&&pageData){const item=todayItems(pageData.today_growth,pageData.milestones.consecutive_login_days).find(item=>item.type===rule);if(item)openSheet('rule',item.title,'成长说明','<p class="rule-copy">'+escapeHtml(item.rule)+'</p><button class="primary-button" data-action="close-sheet">知道了</button>');}
  });
  context.cleanup(()=>{
    active=false;pendingUpgrade=null;sheetLease.dispose();levelLease?.dispose();levelOverlay?.remove();levelOverlay=null;logs=[];logIds.clear();pageData=null;
  },{priority:90});
  void loadPage();
  return {captureState:()=>({rightsCollapsed:true,cursor:Math.max(1,logPage-1)}),unmount(){}};
}

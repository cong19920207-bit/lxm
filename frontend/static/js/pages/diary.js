export async function mount(context) {
  const {root,services}=context,byId=id=>root.querySelector('#'+id);
  const routeCurrent=()=>context.router.current?.context.routeEpoch===context.routeEpoch;
  const request=(method,path)=>services.auth.request(method,path,undefined,{
    authPolicy:'protected-home-modal',routeEpoch:context.routeEpoch,routeCurrent,isCurrent:context.valid,signal:context.signal
  });
  const run=promise=>Promise.resolve(promise).catch(error=>{
    if(context.valid()&&!['AbortError','StaleRequestError'].includes(error.name))services.ui.toast('日记加载失败，请稍后重试','error');
  });
  // The router guards before prepare/commit; the module also refuses private reads if invalidated.
  if(!context.valid()||!services.auth.snapshot().authenticated)return{unmount(){}};
  await context.scope.adopt(services.resources.style('css/bgm.css'),release=>release());
  for(const name of ['bgm-page','bgm-record','bgm-bubble']){
    await services.shared.script('js/'+name+'.js');if(!context.valid())return{unmount(){}};
  }
  const audioPage=services.audio.attachPage(context,'content'),bubble=BgmBubble.mount(audioPage);
  if(bubble)context.cleanup(()=>bubble.destroy());
  const MONTH_EN=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const WEEKDAY_ZH=['周日','周一','周二','周三','周四','周五','周六'];
  let currentPage=0,loading=false,noMore=false,observer=null,restoring=true,userInteracted=false,generation=0;
  let relationLevel=Number(services.auth.storage('getItem','relationship_level').value)||0;
  const items=new Map(),expanded=new Set((context.state?.expandedIds||[]).map(String)),readIds=new Set((context.state?.readIds||[]).map(String));
  const readPending=new Set(),readAttempts=new Set();
  const escapeHtml=value=>{const element=document.createElement('div');element.textContent=value==null?'':String(value);return element.innerHTML};

    /* 列表日期：优先北京覆盖日，旧数据无字段时回退 created_at */
    function parseDiaryDateParts(diary) {
      var y, m, d
      if (diary.covers_beijing_date) {
        var p = String(diary.covers_beijing_date).split('-')
        if (p.length === 3) {
          y = parseInt(p[0], 10)
          m = parseInt(p[1], 10)
          d = parseInt(p[2], 10)
        }
      }
      if ((!y || isNaN(m) || isNaN(d)) && diary.created_at) {
        var dt = new Date(diary.created_at)
        y = dt.getFullYear()
        m = dt.getMonth() + 1
        d = dt.getDate()
      }
      if (!y || isNaN(m) || isNaN(d)) {
        return { monthEn: '', day: '—', weekdayZh: '', iconIndex: 0 }
      }
      var dateObj = new Date(y, m - 1, d)
      return {
        monthEn: MONTH_EN[m - 1] || '',
        day: String(d),
        weekdayZh: WEEKDAY_ZH[dateObj.getDay()],
        iconIndex: dateObj.getDay() % 4
      }
    }

    function getDiaryDecorIcon(iconIndex) {
      var icons = [
        '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M19 14.5A7.5 7.5 0 0 1 5 12.8 5.5 5.5 0 1 1 12.2 5 6.5 6.5 0 0 1 19 14.5Z" stroke="currentColor" stroke-width="1.6"/></svg>',
        '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 18h10a4 4 0 0 0 .2-8 5.5 5.5 0 0 0-10.6-1.2A4 4 0 0 0 7 18Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
        '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.6"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
        '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3.5l1.4 4.3h4.5l-3.6 2.6 1.4 4.3L12 12.1 8.3 14.7l1.4-4.3-3.6-2.6h4.5L12 3.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>'
      ]
      return icons[iconIndex % 4] || icons[0]
    }

  function hideEmpty(){for(const id of ['empty-active','empty-new','empty-error'])byId(id).style.display='none'}
  function showEmpty(){hideEmpty();byId(relationLevel>=1?'empty-active':'empty-new').style.display='flex'}
  function renderItem(diary){
    const id=String(diary.id),parts=parseDiaryDateParts(diary),read=diary.is_read||readIds.has(id)||readAttempts.has(id);
    if(diary.is_read)readIds.add(id);
    const card=document.createElement('div');card.dataset.diaryId=id;card.dataset.id=id;
    card.className='diary-card'+(read?' read':' unread')+(expanded.has(id)?' expanded':'');
    card.innerHTML=(read?'':'<div class="unread-dot" aria-hidden="true"></div>')+
      '<div class="diary-card-date"><div class="diary-card-month">'+escapeHtml(parts.monthEn)+'</div>'+
      '<div class="diary-card-day">'+escapeHtml(parts.day)+'</div><div class="diary-card-weekday">'+escapeHtml(parts.weekdayZh)+'</div>'+
      '<div class="diary-card-icon">'+getDiaryDecorIcon(parts.iconIndex)+'</div></div>'+
      '<div class="diary-card-body"><div class="diary-card-content">'+escapeHtml(diary.content)+'</div>'+
      '<span class="diary-card-more">'+(expanded.has(id)?'收起':'继续看 &gt;')+'</span></div>';
    return card;
  }
  function renderList(){const fragment=document.createDocumentFragment();for(const diary of items.values())fragment.append(renderItem(diary));byId('diary-list').replaceChildren(fragment)}
  function remember(item){
    if(item.id==null)return;
    const diary={id:item.id,content:item.content,relationship_level_at_creation:item.relationship_level_at_creation,
      is_read:!!item.is_read,created_at:item.created_at,covers_beijing_date:item.covers_beijing_date};
    if(diary.is_read)readIds.add(String(diary.id));items.set(String(diary.id),diary);
  }
  async function loadDiaries(page){
    if(!context.valid()||loading||noMore)return false;
    loading=true;const owner=generation;
    try{
      const response=await request('GET','/api/diary/list?page='+page);
      if(!context.valid()||owner!==generation)return false;
      if(response?.code!==0||!response.data){
        if(page===1){hideEmpty();byId('empty-error-text').textContent=response?.message||'日记加载失败，请检查网络后重试';byId('empty-error').style.display='flex';services.ui.toast(response?.message||'日记列表加载失败，请稍后重试','error')}
        return false;
      }
      const data=response.data,batch=Array.isArray(data.items)?data.items:[],pageSize=typeof data.page_size==='number'&&data.page_size>0?data.page_size:20;
      if(page===1){hideEmpty();items.clear()}
      for(const item of batch)remember(item);
      currentPage=page;
      noMore=batch.length===0||(typeof data.total==='number'&&Number.isFinite(data.total)?items.size>=data.total:batch.length<pageSize);
      renderList();byId('no-more').style.display=noMore&&items.size?'block':'none';
      if(!items.size)showEmpty();return true;
    }finally{if(owner===generation)loading=false}
  }
  async function toggle(card){
    const id=card.dataset.diaryId,diary=items.get(id);if(!diary||!context.valid())return;
    const open=!expanded.has(id);if(open)expanded.add(id);else expanded.delete(id);
    card.classList.toggle('expanded',open);card.querySelector('.diary-card-more').textContent=open?'收起':'继续看 >';
    if(!open||readIds.has(id)||diary.is_read||readAttempts.has(id))return;
    readPending.add(id);readAttempts.add(id);card.classList.remove('unread');card.classList.add('read');
    try{
      const response=await request('POST','/api/diary/'+encodeURIComponent(diary.id)+'/read');
      if(context.valid()&&response?.code===0){readIds.add(id);diary.is_read=true}
    }finally{readPending.delete(id)}
  }
  async function updateRelationship(){
    const response=await request('GET','/api/relationship/status');if(!context.valid()||response?.code!==0||!response.data)return;
    relationLevel=response.data.level||0;services.auth.storage('setItem','relationship_level',String(relationLevel));
    if(!items.size&&['empty-active','empty-new'].some(id=>byId(id).style.display==='flex'))showEmpty();
  }
  function observe(){
    if(observer||!context.valid())return;
    observer=new IntersectionObserver(entries=>{if(context.valid()&&!restoring&&entries[0]?.isIntersecting&&!loading&&!noMore)run(loadDiaries(currentPage+1))});
    observer.observe(byId('bottom-sentinel'));context.cleanup(()=>observer.disconnect(),{kind:'observer'});
  }
  async function initialize(){
    // Relationship only selects empty-state wording; it never blocks the list.
    run(updateRelationship());
    const expected=Number.isSafeInteger(context.state?.cursor)?Math.max(1,context.state.cursor):1;
    if(!await loadDiaries(1))return;
    while(context.valid()&&!userInteracted&&!noMore&&currentPage<expected){if(!await loadDiaries(currentPage+1))break}
    if(!context.valid())return;restoring=false;observe();
    if(!userInteracted&&context.state?.scroll)await services.history.restore(context.router.current);
  }
  for(const event of ['wheel','touchstart','pointerdown','keydown'])context.scope.listen(root,event,()=>{userInteracted=true});
  context.scope.listen(root,'click',event=>{
    const action=event.target.closest('[data-diary-action]')?.dataset.diaryAction;
    if(action==='back')context.router.back();else if(action==='chat')context.router.navigate('/pages/chat.html');
    const card=event.target.closest('[data-diary-id]');if(card)run(toggle(card));
  });
  context.scope.listen(byId('btn-retry-diary'),'click',()=>{
    if(loading||!context.valid())return;generation++;noMore=false;currentPage=0;items.clear();byId('diary-list').replaceChildren();byId('no-more').style.display='none';hideEmpty();restoring=true;run(initialize());
  });
  if(Array.isArray(context.state?.items)){for(const item of context.state.items)remember(item);renderList()}
  context.cleanup(()=>{generation++;observer?.disconnect();readPending.clear()},{priority:100});
  run(initialize());
  return{unmount(){},captureState:()=>({items:[...items.values()],cursor:currentPage,hasMore:!noMore,expandedIds:[...expanded],readIds:[...readIds]})};
}

const PAPER_KEYS = ['calm', 'happy', 'curious', 'missing', 'worry', 'shy', 'sleepy'];
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
export function paperForDiaryId(id) {
  const value = String(id ?? '');
  return /^[1-9]\d*$/.test(value) ? PAPER_KEYS[Number((BigInt(value) - 1n) % 7n)] : PAPER_KEYS[0];
}
const pad = value => String(value).padStart(2, '0');
const localDate = date => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
function dateObject(value) { return new Date(`${value}T12:00:00`); }
export function diaryDate(diary) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(diary.covers_beijing_date || '') &&
      localDate(dateObject(diary.covers_beijing_date)) === diary.covers_beijing_date) return diary.covers_beijing_date;
  const fallback = new Date(diary.created_at);
  return Number.isNaN(fallback.getTime()) ? null : localDate(fallback);
}
const dateLabel = value => value ? `${value.slice(0,4)}年${Number(value.slice(5,7))}月${Number(value.slice(8))}日` : '日期未知';
const shortDateLabel = value => value ? `${Number(value.slice(5,7))}月${Number(value.slice(8))}日` : '日期未知';
const artURL = id => '/static/images/diary/paper/' + paperForDiaryId(id) + '.webp';

export async function mount(context) {
  const { root, services } = context, byId = id => root.querySelector('#' + id);
  const action = name => root.querySelector(`[data-diary-action="${name}"]`);
  const routeCurrent = () => context.router.current?.context.routeEpoch === context.routeEpoch;
  const request = (method, path) => services.auth.request(method, path, undefined, {
    authPolicy: 'protected-home-modal', routeEpoch: context.routeEpoch, routeCurrent,
    isCurrent: context.valid, signal: context.signal
  });
  const run = promise => Promise.resolve(promise).catch(error => {
    if (context.valid() && !['AbortError', 'StaleRequestError'].includes(error.name)) services.ui.toast('日记加载失败，请稍后重试', 'error');
  });
  if (!context.valid() || !services.auth.snapshot().authenticated) return { unmount() {} };
  await context.scope.adopt(services.resources.style('css/bgm.css'), release => release());
  for (const name of ['bgm-page', 'bgm-record', 'bgm-bubble']) {
    await services.shared.script('js/' + name + '.js');
    if (!context.valid()) return { unmount() {} };
  }
  const audioPage = services.audio.attachPage(context, 'content'), bubble = BgmBubble.mount(audioPage);
  if (bubble) context.cleanup(() => bubble.destroy());

  const items = new Map(), readIds = new Set((context.state?.readIds || []).map(String));
  const readAttempts = new Set(), animations = new Set();
  const paper = byId('diary-paper'), dialog = byId('diary-calendar');
  let selectedId = null, presentedId = null, selectedDate = null, calendarMonth = context.state?.calendarMonth || localDate(new Date()).slice(0,7);
  let currentPage = 0, noMore = false, pagePromise = null, allPromise = null;
  let loadFailed = false, busy = true, ready = false, userInteracted = false, retryDate = null;
  let relationLevel = Number(services.auth.storage('getItem', 'relationship_level').value) || 0;

  function adjacentId(direction) {
    const ids=[...items.keys()], index=ids.indexOf(selectedId);
    if (index>=0) return ids[index+direction];
    // An empty date (including today) can still return to its nearest diary.
    let nearest=null;
    for (const [id,diary] of items) {
      const date=diaryDate(diary);
      if (!date || !selectedDate || (direction>0 ? date>=selectedDate : date<=selectedDate)) continue;
      if (!nearest || (direction>0 ? date>nearest.date : date<nearest.date)) nearest={id,date};
    }
    return nearest?.id;
  }
  function status() {
    byId('diary-reader').setAttribute('aria-busy', String(busy));
    byId('diary-loading').hidden = loadFailed || (ready && (!!selectedId || !busy));
    byId('empty-error').hidden = ready || !loadFailed;
    byId('diary-load-error').hidden = !ready || !loadFailed || dialog.open;
    byId('diary-calendar-loading').hidden = noMore || loadFailed;
    byId('diary-calendar-error').hidden = !loadFailed;
    action('calendar').disabled = !ready || busy;
    action('today').disabled = !ready || busy;
    const previous=adjacentId(1), next=adjacentId(-1);
    action('previous').disabled = busy || (!previous && noMore) || !items.size;
    action('next').disabled = busy || !next;
    byId('diary-previous-date').textContent = previous ? shortDateLabel(diaryDate(items.get(previous))) : noMore ? '已经是第一篇' : '查看更早日记';
    byId('diary-next-date').textContent = next ? shortDateLabel(diaryDate(items.get(next))) : '已经是最新一篇';
  }
  function hideEmpty() {
    for (const id of ['empty-active', 'empty-new', 'empty-date']) byId(id).hidden = true;
  }
  function showEmpty() {
    hideEmpty(); byId(relationLevel >= 1 ? 'empty-active' : 'empty-new').hidden = false;
  }
  function firstOnDate(value) { return [...items.values()].find(item => diaryDate(item) === value); }
  function artNode(diary, calendar = false) {
    const node = document.createElement('span');
    node.className = 'diary-mood-art' + (calendar ? ' diary-calendar-art' : '');
    node.style.setProperty('--tile-art', `url("${artURL(diary.id)}")`);
    node.setAttribute('aria-hidden', 'true'); return node;
  }
  function dayButton(value, calendar) {
    const diary = firstOnDate(value), button = document.createElement('button'), number = document.createElement('span');
    const state = diary ? 'available' : noMore ? 'empty' : 'unknown';
    button.type = 'button'; button.className = calendar ? 'diary-calendar-day' : 'diary-week-day';
    button.dataset[calendar ? 'calendarDate' : 'weekDate'] = value;
    button.dataset.status = state; button.setAttribute('aria-pressed', String(value === selectedDate));
    if (value === localDate(new Date())) button.setAttribute('aria-current', 'date');
    button.setAttribute('aria-label', `${dateLabel(value)}，${diary ? '有日记' : noMore ? '无日记' : '尚在查找'}`);
    if (!calendar) { const week = document.createElement('span'); week.className = 'diary-weekday'; week.textContent = WEEKDAYS[dateObject(value).getDay()]; button.append(week); }
    number.className = calendar ? 'diary-calendar-number' : 'diary-day-number'; number.textContent = Number(value.slice(8)); button.append(number);
    if (diary) button.append(artNode(diary, calendar));
    else if (!noMore) { const pending = document.createElement('span'); pending.className = 'diary-day-status'; pending.textContent = '…'; pending.setAttribute('aria-hidden','true'); button.append(pending); }
    return button;
  }
  function renderDates() {
    root.querySelector('.diary-week').hidden = !ready || !items.size;
    const start = dateObject(selectedDate || localDate(new Date()));
    start.setDate(start.getDate() - (start.getDay() + 6) % 7);
    const days = Array.from({length:7}, (_, i) => { const d = new Date(start); d.setDate(d.getDate()+i); return localDate(d); });
    byId('diary-week-range').textContent = `${dateLabel(days[0])} — ${dateLabel(days[6])}`;
    byId('diary-week-grid').replaceChildren(...days.map(d => dayButton(d, false)));
    if (!dialog.open) return;
    const first = dateObject(calendarMonth + '-01'), cells = [];
    byId('diary-calendar-month').textContent = `${first.getFullYear()}年${first.getMonth()+1}月`;
    for (let i = 0; i < (first.getDay()+6)%7; i++) cells.push(document.createElement('span'));
    const count = new Date(first.getFullYear(), first.getMonth()+1, 0).getDate();
    for (let day = 1; day <= count; day++) cells.push(dayButton(`${calendarMonth}-${pad(day)}`, true));
    byId('diary-calendar-grid').replaceChildren(...cells);
  }
  function renderCurrentDiary(diary) {
    hideEmpty(); paper.hidden = false; byId('diary-pagination').hidden = false;
    paper.dataset.diaryId = String(diary.id); paper.dataset.paper = paperForDiaryId(diary.id);
    paper.style.setProperty('--art', `url("${artURL(diary.id)}")`);
    paper.setAttribute('aria-label', dateLabel(diaryDate(diary)) + '的日记');
    byId('diary-date').textContent = dateLabel(diaryDate(diary));
    byId('diary-date').dateTime = diaryDate(diary) || '';
    byId('diary-letter').textContent = diary.content ?? '';
    resizePaper();
  }
  function resizePaper() {
    const width = paper.getBoundingClientRect().width;
    if (width > 0) paper.style.setProperty('--paper-width', width + 'px');
  }
  if (typeof ResizeObserver === 'function') {
    const observer = new ResizeObserver(resizePaper); observer.observe(paper);
    context.cleanup(() => observer.disconnect(), { kind:'observer' });
  }
  async function markRead(diary) {
    const id = String(diary.id);
    if (services.entry?.pending) await services.entry.finished;
    if (!context.valid() || selectedId !== id || presentedId !== id || document.hidden || dialog.open) return;
    if (diary.is_read || readIds.has(id) || readAttempts.has(id) || !context.valid()) return;
    readAttempts.add(id);
    try {
      const response = await request('POST', '/api/diary/' + encodeURIComponent(id) + '/read');
      if (context.valid() && response?.code === 0) { readIds.add(id); diary.is_read = true; }
    } catch (_) { /* Existing policy: no automatic retry in this mounted instance. */ }
  }
  function loadNext() {
    if (pagePromise) return pagePromise;
    if (noMore || !context.valid()) return Promise.resolve(false);
    loadFailed = false;
    pagePromise = (async () => {
      try {
        const response = await request('GET', '/api/diary/list?page=' + (currentPage+1) + '&page_size=50');
        if (!context.valid()) return false;
        if (response?.code !== 0 || !response.data) throw new Error('DiaryListError');
        const data = response.data, batch = Array.isArray(data.items) ? data.items : [];
        for (const item of batch) {
          if (item.id == null) continue;
          const id = String(item.id);
          if (readIds.has(id)) item.is_read = true;
          items.set(id, item);
        }
        currentPage++;
        noMore = batch.length === 0 || (Number.isFinite(data.total) ? items.size >= data.total : batch.length < (data.page_size || 50));
        return true;
      } catch (error) {
        if (context.valid() && !['AbortError','StaleRequestError'].includes(error.name)) loadFailed = true;
        return false;
      } finally {
        pagePromise = null;
        if (context.valid()) { status(); renderDates(); }
      }
    })();
    status(); return pagePromise;
  }
  function ensureAll() {
    if (allPromise) return allPromise;
    allPromise = (async () => {
      while (context.valid() && !noMore) if (!await loadNext()) return false;
      return context.valid();
    })().finally(() => { allPromise = null; });
    return allPromise;
  }
  function prepareTurn(rect, direction) {
    const top = Math.max(0, rect.top), bottom = byId('diary-pagination').getBoundingClientRect().top;
    if (rect.bottom <= top || bottom <= top) return null;
    const layer = document.createElement('div'), front = document.createElement('div');
    const back = document.createElement('div'), shadow = document.createElement('div');
    layer.className = 'diary-turn'; layer.dataset.direction = direction > 0 ? 'right' : 'left';
    layer.setAttribute('aria-hidden', 'true'); layer.inert = true;
    Object.assign(layer.style, {left:rect.left+'px', top:top+'px', width:rect.width+'px', height:(bottom-top)+'px'});
    front.className = 'diary-turn-front'; back.className = 'diary-turn-back'; shadow.className = 'diary-turn-shadow';
    const copy = paper.cloneNode(true);
    copy.removeAttribute('id'); copy.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
    Object.assign(copy.style, {width:rect.width+'px', top:(rect.top-top)+'px', left:'0'});
    front.append(copy); back.hidden = true;
    layer.append(shadow, front, back); byId('lxm-painted-diary').append(layer);
    return {layer, front, back, shadow, width:rect.width, height:bottom-top, direction};
  }
  function turnPage(view) {
    if (!view) return Promise.resolve();
    const {layer, front, back, shadow, width:w, height:h, direction} = view;
    // Fold a polygon over a moving diagonal crease. The reflected polygon is the
    // paper's back; the untouched portion stays opaque above the incoming page.
    const tilt = Math.min(.18, w * .24 / h), rectangle = [[0,0],[w,0],[w,h],[0,h]];
    const polygon = points => 'polygon(' + points.map(([x,y]) => `${direction > 0 ? x : w-x}px ${y}px`).join(',') + ')';
    function halfPlane(c, folded) {
      const result = [], distance = ([x,y]) => x - tilt*y - c;
      for (let i=0; i<rectangle.length; i++) {
        const a=rectangle[i], b=rectangle[(i+1)%rectangle.length], da=distance(a), db=distance(b);
        const insideA=folded ? da<=0 : da>=0, insideB=folded ? db<=0 : db>=0;
        if (insideA) result.push(a);
        if (insideA!==insideB) { const t=da/(da-db); result.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]); }
      }
      return result;
    }
    return new Promise(resolve => {
      let frame, started;
      const animation = {cancel(){cancelAnimationFrame(frame);layer.remove();animations.delete(animation);resolve();}};
      animations.add(animation);
      function draw(now) {
        if (!context.valid()) { animation.cancel(); return; }
        started ??= now;
        const elapsed=Math.min(1,(now-started)/620), progress=elapsed*elapsed*(3-2*elapsed);
        const c=-tilt*h + (w+tilt*h)*progress;
        const flat=halfPlane(c,false), folded=halfPlane(c,true);
        front.style.clipPath = flat.length>=3 ? polygon(flat) : 'inset(0 100% 0 0)';
        const reflection=folded.map(([x,y])=>{const d=(x-tilt*y-c)/(1+tilt*tilt);return [x-2*d,y+2*tilt*d];});
        back.hidden=reflection.length<3;
        if (!back.hidden) back.style.clipPath=polygon(reflection);
        const angle=direction>0 ? 90-Math.atan(tilt)*180/Math.PI : 270+Math.atan(tilt)*180/Math.PI;
        const stop=(c+tilt*h)/Math.sqrt(1+tilt*tilt);
        back.style.background=`linear-gradient(${angle}deg, #d3c4af ${stop-6}px, #fffaf0 ${stop+22}px, #eee2ce ${stop+65}px, #faf3e5 ${stop+100}px)`;
        shadow.style.background=`linear-gradient(${angle}deg, transparent ${stop-32}px, #40304e ${stop}px, transparent ${stop+45}px)`;
        layer.dataset.progress=progress.toFixed(3);
        if (elapsed<1) frame=requestAnimationFrame(draw); else animation.cancel();
      }
      frame=requestAnimationFrame(draw);
    });
  }
  async function selectDiary(id, { animate = false, direction = 1, scroll = true } = {}) {
    const diary = items.get(String(id)); if (!diary || !context.valid()) return;
    if (selectedId === String(id) && !paper.hidden) return;
    const rect=paper.getBoundingClientRect(), reader=byId('diary-reader');
    const motion = animate && !paper.hidden && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    const view=motion ? prepareTurn(rect,direction) : null;
    // Keep long-to-short changes from clamping the document before the overlay
    // covers it. Reposition under the fold, never via a visible vertical tween.
    reader.style.minHeight=reader.getBoundingClientRect().height+'px';
    selectedId = String(id); selectedDate = diaryDate(diary);
    renderCurrentDiary(diary); renderDates(); status();
    if (scroll && (rect.top<0 || rect.top>=innerHeight)) window.scrollTo({top:window.scrollY+paper.getBoundingClientRect().top-16,behavior:'instant'});
    try { await turnPage(view); } finally { reader.style.minHeight=''; }
    if (!context.valid()) return;
    presentedId = selectedId;
    byId('diary-announcement').textContent = '正在阅读' + dateLabel(selectedDate) + '的日记';
    run(markRead(diary));
  }
  async function navigate(direction) {
    if (busy || !ready) return;
    busy = true; status();
    try {
      if (!selectedId) {
        const target=adjacentId(direction);
        if (target) await selectDiary(target,{animate:true,direction});
        return;
      }
      let ids = [...items.keys()], index = ids.indexOf(selectedId), target = index + direction;
      while (target >= ids.length && !noMore) { if (!await loadNext()) return; ids = [...items.keys()]; }
      if (target >= 0 && target < ids.length) await selectDiary(ids[target], {animate:true,direction});
    } finally { if (context.valid()) { busy = false; status(); } }
  }
  function closeCalendar(markVisible = true) {
    if (dialog.open) dialog.close();
    action('calendar').setAttribute('aria-expanded','false');
    action('calendar').focus({preventScroll:true}); status();
    if (markVisible && items.has(selectedId)) run(markRead(items.get(selectedId)));
  }
  async function selectDate(value) {
    if (busy || !ready) return;
    busy = true; retryDate = value; status();
    try {
      let diary = firstOnDate(value);
      if (!diary && !noMore) { if (!await ensureAll()) return; diary = firstOnDate(value); }
      if (!context.valid()) return;
      const direction = !selectedDate || value < selectedDate ? 1 : -1;
      closeCalendar(false); retryDate = null;
      if (diary) await selectDiary(diary.id, {animate:true,direction});
      else {
        selectedDate = value; selectedId = null; paper.hidden = true; byId('diary-pagination').hidden = !items.size; hideEmpty();
        byId('empty-date').textContent = `${dateLabel(value)}，还没有留下日记。`; byId('empty-date').hidden = false;
        renderDates(); byId('empty-date').scrollIntoView({block:'center',behavior:'instant'});
      }
    } finally { if (context.valid()) { busy = false; status(); } }
  }
  async function updateRelationship() {
    const response = await request('GET','/api/relationship/status');
    if (!context.valid() || response?.code !== 0 || !response.data) return;
    relationLevel = response.data.level || 0; services.auth.storage('setItem','relationship_level',String(relationLevel));
    if (ready && !items.size) showEmpty();
  }
  async function initialize() {
    busy = true; loadFailed = false; status();
    if (!await loadNext() || !context.valid()) { busy = false; status(); return; }
    const saved = context.state?.selectedId;
    // Re-fetch only as far as required; never serialize the diary corpus into history.
    if (saved) while (context.valid() && !items.has(String(saved)) && !noMore) { if (!await loadNext()) { busy = false; status(); return; } }
    if (!context.valid()) return;
    ready = true;
    if (items.size && !saved && context.state?.selectedDate) {
      selectedDate = context.state.selectedDate; busy = false;
      await selectDate(selectedDate);
    } else if (items.size) {
      if (saved && !items.has(String(saved))) services.ui.toast('原日记已不在列表，已打开最新一篇');
      await selectDiary(saved && items.has(String(saved)) ? saved : items.keys().next().value, {scroll:false});
    } else { paper.hidden = true; byId('diary-pagination').hidden = true; showEmpty(); }
    busy = false; renderDates(); status();
    if (!userInteracted && context.state?.scroll) await services.history.restore(context.router.current);
  }
  for (const name of ['wheel','touchstart','pointerdown','keydown']) context.scope.listen(root,name,()=>{userInteracted=true;},{passive:true});
  context.scope.listen(document,'visibilitychange',()=>{if(!document.hidden && items.has(selectedId))run(markRead(items.get(selectedId)));});
  context.scope.listen(dialog,'cancel',event=>{event.preventDefault();closeCalendar();});
  context.scope.listen(dialog,'click',event=>{if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)closeCalendar();}});
  context.scope.listen(root,'click',event=>{
    const button = event.target.closest('button'); if (!button || button.disabled) return;
    const value = button.dataset.calendarDate || button.dataset.weekDate;
    if (value) { run(selectDate(value)); return; }
    switch (button.dataset.diaryAction) {
      case 'back': context.router.back(); break;
      case 'chat': context.router.navigate('/pages/chat.html'); break;
      case 'previous': run(navigate(1)); break;
      case 'next': run(navigate(-1)); break;
      case 'today': run(selectDate(localDate(new Date()))); break;
      case 'calendar':
        calendarMonth = (selectedDate || localDate(new Date())).slice(0,7);
        dialog.showModal(); action('calendar').setAttribute('aria-expanded','true'); renderDates(); status(); run(ensureAll()); break;
      case 'close-calendar': closeCalendar(); break;
      case 'month-previous': case 'month-next': {
        const date = dateObject(calendarMonth+'-01'); date.setMonth(date.getMonth()+(button.dataset.diaryAction==='month-next'?1:-1));
        calendarMonth = localDate(date).slice(0,7); renderDates(); break;
      }
      case 'retry-calendar': run(ensureAll()); break;
      case 'retry-more': run(retryDate ? selectDate(retryDate) : navigate(1)); break;
      case 'retry': if (!pagePromise) { items.clear(); currentPage=0; noMore=false; run(initialize()); } break;
    }
  });
  context.cleanup(()=>{for(const animation of animations)animation.cancel();animations.clear();if(dialog.open)dialog.close();},{priority:100});
  run(updateRelationship()); run(initialize());
  return { unmount() {}, captureState: () => ({ selectedId, selectedDate, calendarMonth, cursor:currentPage, readIds:[...readIds].slice(-500) }) };
}

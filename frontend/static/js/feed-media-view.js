/* Shared by the standalone feed and an AppShell feed mount. One instance per visit. */
(() => {
  'use strict';
  function node(tag, className, text) {
    const element=document.createElement(tag);
    if(className) element.className=className;
    if(text!=null) element.textContent=text;
    return element;
  }
  function button(label, click, className) {
    const b=node('button',className,label);b.type='button';b.onclick=click;return b;
  }
  function image(src,alt) {
    const img=node('img');img.alt=alt;img.loading='lazy';img.src=src;return img;
  }
  function clock(ms) {
    const sec=Math.floor((Number(ms)||0)/1000);
    return Math.floor(sec/60)+':'+String(sec%60).padStart(2,'0');
  }
  function protectVideoMenu(video) {
    video.setAttribute('controlslist', 'nodownload nofullscreen');
    video.oncontextmenu = event => event.preventDefault();
  }
  function playerControls(layer, video, hasAudio) {
    const controls = node('div', 'feed-player-controls');
    const timeline = node('div', 'feed-player-timeline');
    const elapsed = node('span', '', '0:00');
    const total = node('span', '', '–:––');
    const seek = node('input');
    seek.type = 'range';
    seek.min = '0';
    seek.step = '0.1';
    seek.value = '0';
    seek.disabled = true;
    seek.setAttribute('aria-label', '播放进度');
    let scrubbing = false;
    function updateTime() {
      const duration = video.duration;
      seek.disabled = !Number.isFinite(duration) || duration <= 0;
      if (!seek.disabled) seek.max = String(duration);
      if (!scrubbing) seek.value = String(video.currentTime);
      elapsed.textContent = clock(Number(seek.value) * 1000);
      total.textContent = seek.disabled ? '–:––' : clock(duration * 1000);
      seek.setAttribute('aria-valuetext', elapsed.textContent + ' / ' + total.textContent);
    }
    seek.oninput = () => { scrubbing = true; updateTime(); };
    seek.onchange = () => {
      video.currentTime = Number(seek.value);
      scrubbing = false;
      play();
    };
    seek.onpointercancel = seek.onblur = () => { scrubbing = false; updateTime(); };
    video.addEventListener('timeupdate', updateTime);
    video.addEventListener('durationchange', updateTime);
    timeline.append(elapsed, seek, total);

    function play() { video.play().catch(() => {}); }
    const toggle = button('播放', () => video.paused ? play() : video.pause(), 'feed-player-toggle');
    video.onclick = () => toggle.click();
    function updatePlay() { toggle.textContent = video.paused ? '播放' : '暂停'; }
    video.addEventListener('play', updatePlay);
    video.addEventListener('pause', updatePlay);
    const actions = node('div', 'feed-player-actions');
    actions.append(toggle);
    if (hasAudio) {
      const mute = button('静音', () => { video.muted = !video.muted; });
      video.addEventListener('volumechange', () => { mute.textContent = video.muted ? '取消静音' : '静音'; });
      actions.append(mute);
    }
    if (document.fullscreenEnabled && layer.requestFullscreen) {
      const full = button('全屏', async () => {
        try {
          if (document.fullscreenElement === layer) await document.exitFullscreen();
          else await layer.requestFullscreen();
        } catch { /* The viewport player stays available if native fullscreen is restricted. */ }
      });
      layer.addEventListener('fullscreenchange', () => {
        full.textContent = document.fullscreenElement === layer ? '退出全屏' : '全屏';
      });
      actions.append(full);
    }
    controls.append(timeline, actions);
    return controls;
  }
  function enablePinPaging(track, counter, initialIndex, onPage) {
    const rows = Array.from(track.children);
    const offset = i => rows[i].offsetLeft - rows[0].offsetLeft;
    const indexAt = left => Math.max(0, Math.min(rows.length - 1, Math.round(left / offset(1))));
    let current = -1;
    function showPage(index) {
      if (current === index) return;
      current = index;
      counter.textContent = (index + 1) + ' / ' + rows.length;
      onPage(rows[index].dataset.pinId);
    }
    function go(index) {
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      track.scrollTo({left: offset(index), behavior: reduced ? 'instant' : 'smooth'});
    }
    track.tabIndex = 0;
    track.setAttribute('role', 'group');
    track.setAttribute('aria-label', '置顶动态，可横滑或用左右方向键翻页');
    showPage(initialIndex);
    track.scrollLeft = offset(initialIndex);
    track.onscroll = () => {
      if (track.clientWidth) showPage(indexAt(track.scrollLeft));
    };
    track.onkeydown = event => {
      const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
      if (!delta) return;
      event.preventDefault();
      const index = Math.max(0, Math.min(rows.length - 1, indexAt(track.scrollLeft) + delta));
      rows[index].querySelector('button').focus({preventScroll: true});
      go(index);
    };

    // Touch and trackpads use native scrolling. Give a mouse drag the same snap points.
    let drag = null, suppressClick = false;
    track.onpointerdown = event => {
      suppressClick = false;
      if (event.pointerType === 'mouse' && event.button === 0) {
        drag = {x: event.clientX, left: track.scrollLeft};
      }
    };
    track.ondragstart = event => event.preventDefault();
    track.onpointermove = event => {
      if (!drag || !event.buttons) return;
      const distance = event.clientX - drag.x;
      if (!suppressClick) {
        if (Math.abs(distance) < 6) return;
        suppressClick = true;
        track.setPointerCapture(event.pointerId);
        track.classList.add('is-dragging');
      }
      track.scrollLeft = drag.left - distance;
    };
    function finishDrag(event) {
      if (!drag) return;
      const start = indexAt(drag.left);
      const distance = drag.x - event.clientX;
      drag = null;
      if (!suppressClick) return;
      const step = event.type !== 'pointercancel' && Math.abs(distance) >= 32 ? Math.sign(distance) : 0;
      track.classList.remove('is-dragging');
      go(Math.max(0, Math.min(rows.length - 1, start + step)));
    }
    track.onpointerup = track.onpointercancel = finishDrag;
    track.onpointerleave = () => { if (!suppressClick) drag = null; };
    track.addEventListener('click', event => {
      if (suppressClick && event.detail) {
        event.preventDefault();
        event.stopPropagation();
      }
      suppressClick = false;
    }, true);
  }
  function publicationMeta(post) {
    const date = (post.scheduled_publish_time || '').slice(0, 10);
    const meta = node('span', 'feed-pin-meta');
    const parts = /^\d{4}-(\d{2})-(\d{2})$/.exec(date);
    if (parts) {
      const stamp = node('time', '', Number(parts[1]) + '月' + Number(parts[2]) + '日发布');
      stamp.dateTime = date;
      meta.append(stamp);
    }
    const city = (post.city || '').trim();
    if (city) meta.append(meta.hasChildNodes() ? ' · ' + city : city);
    return meta;
  }
  function mount({root,read,article,images,audio,readTargets,resetReads,resumeState,registerDetail}) {
    const shelf=root.querySelector('#feed-pins');
    const cards=new Map(),completed=new Set(resumeState?.completed||[]),failed=new Set();
    let pins=[],selectedPin=resumeState?.selectedPin,live=true,detail=null,detailPost=null,overlay=null;
    let generation=0,detailGeneration=0,schedule=null,active=null,waitForScroll=!!resumeState?.player;
    let imagePreviewOpen=false;
    function renderPins() {
      shelf.replaceChildren();shelf.hidden=!pins.length;
      if(!pins.length){selectedPin=null;return;}
      const header = node('div', 'feed-pin-header');
      header.append(node('h2', 'feed-pin-title', '置顶'));
      const track = node('div', 'feed-pin-track');
      shelf.append(header, track);
      for(const post of pins) {
        const row=node('article','feed-pin-row');row.dataset.pinId=post.id;
        const vid=post.video,urls=post.image_urls||[];
        const summary = button('', () => openDetail(post.id), 'feed-pin-summary');
        const content = (post.content_text || '').trim();
        if (content) summary.append(node('span', 'feed-pin-text', content));
        const meta = publicationMeta(post);
        if (meta.hasChildNodes()) summary.append(meta);
        summary.setAttribute('aria-label', ['查看完整动态', content, meta.textContent].filter(Boolean).join(' '));
        row.append(summary);
        if(vid?.cover_small_url || urls.length) {
          const open=event=>vid?openVideo(post,null,event.currentTarget):images(urls,0);
          const thumb=button('',open,'feed-pin-thumb');
          thumb.setAttribute('aria-label',vid?'播放正片':urls.length>1?'打开相册':'查看原图');
          thumb.append(image(vid?.cover_small_url || urls[0], ''));
          if (vid || urls.length > 1) {
            const badge = node('span', 'feed-pin-badge', vid ? '▶ ' + clock(vid.duration_ms) : urls.length + ' 张');
            thumb.append(badge);
          }
          row.append(thumb);
        }
        track.append(row);
      }
      if (pins.length > 1) {
        const counter = node('span', 'feed-pin-position');
        counter.setAttribute('role', 'status');
        header.append(counter);
        const index = Math.max(0, pins.findIndex(post => String(post.id) === selectedPin));
        enablePinPaging(track, counter, index, id => { selectedPin = id; });
      } else {
        selectedPin = String(pins[0].id);
      }
    }
    async function refreshPins() {
      const epoch=++generation;
      try {const result=await read('/api/feed/pins');if(live&&epoch===generation){pins=result?.posts||[];renderPins();}}
      catch{if(live&&epoch===generation){pins=[];renderPins();}}
    }
    function stopPreview() {
      if(!active)return;
      const record=active;active=null;
      record.video.onended=record.video.onerror=null;record.video.pause();
      record.video.removeAttribute('src');record.video.load();record.video.remove();
      record.card.classList.remove('is-playing');
    }
    function showFailure(record) {
      if(active!==record)return;
      failed.add(record.id);stopPreview();record.card.querySelector('.feed-short-retry').hidden=false;
      choose();
    }
    function play(record) {
      if(active?.card===record.card || completed.has(record.id) || failed.has(record.id))return;
      stopPreview();
      const video=node('video','feed-short');video.muted=true;video.defaultMuted=true;video.playsInline=true;
      protectVideoMenu(video);
      const current=active={...record,video};
      video.onended=()=>{if(active!==current)return;completed.add(record.id);stopPreview();choose();};
      video.onerror=()=>showFailure(current);
      video.onplaying=()=>{if(active===current)record.card.classList.add('is-playing');};
      record.card.prepend(video);video.src=record.post.video.preview_url;
      video.play().catch(()=>showFailure(current));
    }
    function canPreview() {
      return live && !document.hidden && !root.closest('[inert]') && !detail && !overlay && !imagePreviewOpen &&
        !waitForScroll && !document.querySelector('#feed-boot-loading.is-visible');
    }
    function choose() {
      clearTimeout(schedule);schedule=null;
      if(!canPreview()){stopPreview();return;}
      if(active && cards.get(active.card)?.ratio>=.5 && active.card.isConnected)return;
      stopPreview();
      const eligible=[...cards.values()].filter(r=>r.card.isConnected&&r.ratio>=.5&&!completed.has(r.id)&&!failed.has(r.id));
      const distance=r=>Math.abs(r.card.getBoundingClientRect().top+r.card.offsetHeight/2-innerHeight/2);
      eligible.sort((a,b)=>distance(a)-distance(b));
      const next=eligible[0];
      if(next)schedule=setTimeout(()=>{if(canPreview()&&next.card.isConnected&&next.ratio>=.5)play(next);},65);
    }
    function setImagePreviewOpen(open) {
      imagePreviewOpen=open;
      choose();
    }
    const observer=new IntersectionObserver(entries=>{
      for(const entry of entries){const r=cards.get(entry.target);if(r)r.ratio=entry.intersectionRatio;}
      choose();
    },{threshold:[0,.4999,.5,1]});
    function clearCards() {
      stopPreview();clearTimeout(schedule);observer.disconnect();cards.clear();
    }
    function decorate(item,post,inDetail=false) {
      if(post.is_pinned && !inDetail){
        const meta=item.querySelector('.feed-meta-row,.feed-author-name');
        meta?.append(node('span','feed-pin-mark','置顶'));
      }
      const single=item.querySelector('.feed-images.count-1 img');
      if(single) {
        const dimension=()=>single.closest('.count-1')?.classList.toggle('is-portrait',single.naturalHeight>single.naturalWidth);
        single.addEventListener('load',dimension,{once:true});if(single.complete)dimension();
      }
      if(!post.video)return item;
      const vid=post.video,id=String(post.id),card=node('div','feed-movie-card');
      card.dataset.mediaPost=id;card.style.aspectRatio=vid.height>vid.width?'4 / 5':vid.width+' / '+vid.height;
      card.style.setProperty('--feed-fit',vid.frame_mode==='contain'?'contain':'cover');
      card.style.setProperty('--feed-position',String(vid.frame_position??50)+'%');
      card.append(image(vid.cover_large_url,'视频封面'));
      const full=button('',event=>openVideo(post,null,event.currentTarget),'feed-watch');full.setAttribute('aria-label','播放完整视频');
      full.append(node('span','feed-play-glyph','▶'),node('span','feed-duration',clock(vid.duration_ms)));
      card.append(full);
      const retry=button('重试短预览',()=>{failed.delete(id);retry.hidden=true;waitForScroll=false;choose();},'feed-short-retry');
      retry.hidden=!failed.has(id);card.append(retry);
      item.classList.remove('feed-item--text');
      item.querySelector('.feed-actions')?.before(card);
      if(!inDetail){cards.set(card,{id,post,card,ratio:0});observer.observe(card);}
      return item;
    }
    function closeFull() {
      if(!overlay)return;
      const current=overlay;overlay=null;
      current.video.pause();current.video.removeAttribute('src');current.video.load();
      current.background.inert=current.wasInert;
      current.lease?.end({resumeAllowed:true});current.layer.remove();document.body.style.overflow=current.overflow;current.trigger?.focus({preventScroll:true});
      waitForScroll=true;resetReads?.();
    }
    function openVideo(post, resumeAt=null, trigger=document.activeElement) {
      closeFull();stopPreview();clearTimeout(schedule);
      const layer=node('section','feed-fullscreen');
      layer.setAttribute('role','dialog');layer.setAttribute('aria-label','视频播放器');
      layer.setAttribute('aria-modal','true');
      const video=node('video');video.playsInline=true;video.preload='none';video.muted=false;
      protectVideoMenu(video);
      const close=button('返回',closeFull,'feed-view-close');
      close.setAttribute('aria-label','返回，关闭视频播放');
      const message=node('p','feed-play-error','视频加载失败');message.setAttribute('role','alert');message.hidden=true;
      const retry=button('重试正片',start,'feed-player-retry');retry.hidden=true;
      const replay=button('重新播放',start,'feed-player-replay');replay.hidden=true;
      const stage=node('div','feed-player-stage');
      const status=node('div','feed-player-status');
      status.append(message,retry,replay);stage.append(video,status);
      layer.append(close,stage,playerControls(layer,video,post.video.has_audio!==false));root.append(layer);
      const overflow=document.body.style.overflow;document.body.style.overflow="hidden";
      const background=detail?.layer||root.querySelector('.feed-wrap'),wasInert=background.inert;
      background.inert=true;
      const current=overlay={layer,video,post,trigger,overflow,background,wasInert,lease:null};resetReads?.();
      if(post.video.has_audio!==false){
        current.lease=audio()?.mediaActivities?.begin('feed-video-'+post.id,{
          kind:'media',audible:true,stop:()=>{video.pause();return true;},isStopped:()=>video.paused,resumeAllowed:true
        });
      }
      function failure(){if(overlay===current){message.hidden=retry.hidden=false;}}
      function start(){
        if(overlay!==current)return;
        message.hidden=retry.hidden=replay.hidden=true;
        video.src=post.video.video_url;video.load();
        video.play().catch(e=>{if(e.name!=='NotAllowedError'&&e.name!=='AbortError')failure();});
      }
      video.onerror=failure;video.onended=()=>{replay.hidden=false;};
      let restorePaused=resumeAt!==null;
      video.onplay=()=>{restorePaused=false;};
      video.onseeked=()=>{if(!restorePaused&&overlay===current&&!document.hidden&&!video.ended)video.play().catch(()=>{});};
      close.focus({preventScroll:true});
      if(restorePaused){
        video.preload='metadata';
        video.onloadedmetadata=()=>{video.onloadedmetadata=null;if(resumeAt>0)video.currentTime=Math.min(resumeAt,video.duration);};
        video.src=post.video.video_url;
      }else start();
    }
    function closeDetail() {
      detailGeneration++;
      if(!detail)return;
      const current=detail;detail=null;detailPost=null;current.layer.remove();waitForScroll=true;
      if (current.lease) current.lease.dispose();
      else {
        current.background.inert = current.wasInert;
        document.body.style.overflow = current.overflow;
      }
      resetReads?.();window.scrollTo(0,current.scroll);current.trigger?.focus({preventScroll:true});
    }
    async function openDetail(id,commentId) {
      closeDetail();const epoch=detailGeneration,trigger=document.activeElement,scroll=window.scrollY;
      stopPreview();clearTimeout(schedule);
      const layer = node('div', 'feed-detail');
      const sheet = node('section', 'feed-detail-sheet');
      sheet.setAttribute('role', 'dialog');
      sheet.setAttribute('aria-modal', 'true');
      sheet.setAttribute('aria-label', '原帖详情');
      const grip = node('div', 'feed-detail-grip');
      grip.setAttribute('aria-hidden', 'true');
      let startY;
      grip.onpointerdown = e => { startY = e.clientY; grip.setPointerCapture(e.pointerId); };
      grip.onpointerup = e => { if (e.clientY - startY > 40) closeDetail(); };
      const header = node('header', 'feed-detail-header');
      const author = node('div', 'feed-detail-byline');
      const name = node('strong', 'feed-detail-name', root.querySelector('#feed-nickname').textContent);
      author.append(name);
      const avatar = image(root.querySelector('#feed-avatar').src, '');
      avatar.className = 'feed-author-avatar';
      const close = button('×', closeDetail, 'feed-view-close');
      close.setAttribute('aria-label', '关闭原帖详情');
      header.append(avatar, author, close);
      const body = node('div', 'feed-detail-body');
      const status = node('p', 'feed-detail-status', '正在加载动态…');
      status.setAttribute('role', 'status');
      body.append(status);
      sheet.append(grip, header, body);
      layer.append(sheet);
      layer.onclick = e => { if (e.target === layer) closeDetail(); };
      sheet.onkeydown = e => {
        if (e.key !== 'Tab') return;
        const controls = [...sheet.querySelectorAll('button:not([disabled]), [tabindex="0"]')].filter(el => el.getClientRects().length);
        const edge = e.shiftKey ? controls[0] : controls.at(-1);
        if (document.activeElement === edge) {
          e.preventDefault();
          (e.shiftKey ? controls.at(-1) : controls[0]).focus();
        }
      };
      const background = root.querySelector('.feed-wrap');
      const lease = registerDetail?.(sheet, background);
      const overflow = document.body.style.overflow, wasInert = background.inert;
      root.append(layer);
      detail = {layer, trigger, scroll, overflow, background, wasInert, lease};
      if (lease) lease.open();
      else { background.inert = true; document.body.style.overflow = 'hidden'; }
      resetReads?.();
      close.focus({preventScroll:true});
      try {
        const post=await read('/api/feed/posts/'+encodeURIComponent(id));
        if(!live||epoch!==detailGeneration)return;
        if(!post?.id){status.textContent='动态暂不可见';return;}
        detailPost=post;
        if (post.is_pinned) name.append(node('span','feed-pin-mark','置顶'));
        author.append(publicationMeta(post));
        const item=article(post,true);body.replaceChildren(item);readTargets?.(item);
        if(commentId){const anchor=[...item.querySelectorAll('[data-comment-id]')].find(x=>x.dataset.commentId===String(commentId));
          if(anchor){anchor.scrollIntoView({block:'center'});anchor.classList.add('comment-highlighted');}}
      } catch{if(detail?.layer===layer)status.textContent='详情加载失败';}
    }
    const onScroll=()=>{waitForScroll=false;choose();};
    const visibility=()=>{if(document.hidden)overlay?.video.pause();choose();};
    const onKey=e=>{
      if(e.defaultPrevented || e.key!=='Escape' || root.closest('[inert]') || root.querySelector('.preview-overlay,.comment-panel.show') || document.querySelector('#auth-login-modal.is-open'))return;
      if(overlay){e.preventDefault();closeFull();}else if(detail){e.preventDefault();closeDetail();}
    };
    window.addEventListener('home-startup-change',choose);
    const boot=root.querySelector('#feed-boot-loading');
    const bootObserver=new MutationObserver(choose);
    if(boot)bootObserver.observe(boot,{attributes:true,attributeFilter:['class']});
    window.addEventListener('scroll',onScroll,{passive:true});
    document.addEventListener('visibilitychange',visibility);window.addEventListener('keydown',onKey);
    function resetIdentity(){generation++;closeFull();closeDetail();clearCards();pins=[];renderPins();}
    function destroy(){live=false;bootObserver.disconnect();window.removeEventListener('home-startup-change',choose);resetIdentity();completed.clear();failed.clear();window.removeEventListener('scroll',onScroll);
      window.removeEventListener('keydown',onKey);document.removeEventListener('visibilitychange',visibility);}
    function capture(){
      const player=overlay?{id:overlay.post.id,version:overlay.post.video.media_version,time:overlay.video.currentTime||0}:null;
      return {completed:[...completed],selectedPin,detailId:detailPost?.id||null,player};
    }
    async function restore(){
      if(resumeState?.detailId)await openDetail(resumeState.detailId);
      const player=resumeState?.player;
      if(player){
        const post=detailPost?.id===player.id?detailPost:await read('/api/feed/posts/'+encodeURIComponent(player.id));
        if(live&&post?.video?.media_version===player.version)openVideo(post,player.time);
      }
    }
    return {capture,restore,setImagePreviewOpen,readingRoot:()=>live&&!document.hidden&&!overlay&&!root.closest('[inert]')?(detail?.layer||root.querySelector('#feed-list')):null,refreshPins,decorate,clearCards,openDetail,resetIdentity,destroy,
      detailPost:id=>String(detailPost?.id)===String(id)?detailPost:null,
      repaintDetail:()=>{if(detail&&detailPost){const old=detail.layer.querySelector('.feed-item');if(old){const item=article(detailPost,true);old.replaceWith(item);readTargets?.(item);}}}};
  }
  window.FeedMediaView={mount};
})();

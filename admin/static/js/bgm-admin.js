/* Management media is independent of H5 playback and preferences. */
(function () {
  'use strict';
  const ALLOWED_ROLES=['super_admin','ops_admin','observer'], pageSize=20;
  const states={receiving:'接收中',processing:'处理中',ready:'已就绪',failed:'处理失败',deleting:'删除中',delete_failed:'删除失败',deleted:'已删除',accepted:'已接纳',succeeded:'已完成',unknown:'结果待核对'};
  const failures={size_limit:'文件超过大小限制',duration_limit:'音频时长不符合要求',unsupported_format:'音频格式不支持',mime_mismatch:'文件类型与内容不符',format_mismatch:'音频格式与内容不符',invalid_audio:'音频无法读取',decode_failed:'音频解码失败',invalid_output:'转码结果不符合要求',processing_timeout:'音频处理超时',receive_timeout:'文件接收超时',dependency_unavailable:'处理服务暂不可用',probe_limit:'音频探测超过限制',worker_stopped:'处理任务中断',worker_interrupted:'处理任务中断',termination_unconfirmed:'处理任务状态待核对',stale_attempt:'处理版本已失效',invalid_asset:'音频资源校验失败',storage_unavailable:'存储服务暂不可用',storage_configuration:'存储配置需检查',storage_unknown:'存储结果待核对',remote_cors:'音频跨域访问校验失败',remote_mismatch:'远端音频校验不一致',remote_unreadable:'远端音频无法读取',remote_mime:'远端音频类型不符',remote_range:'远端音频分段读取失败',source_mismatch:'源文件校验不一致',authorization_changed:'操作权限已变化',interrupted:'文件接收已中断',deadline_expired:'操作接收期限已过',processing_failed:'音频处理失败，请核对后重试'};
  const $=id=>document.getElementById(id);
  let page=1,total=0,generation=0,detailGeneration=0,operationGeneration=0,catalogVersion=0,filter='all',enabledCount=0,searchTimer;
  let previewGeneration=0,previewTrack=null,previewState='idle',menuTrigger=null;
  function textNode(tag,value,cls){const n=document.createElement(tag);n.textContent=value==null?'—':String(value);if(cls)n.className=cls;return n;}
  function icon(name){const n=document.createElementNS('http://www.w3.org/2000/svg','svg'),u=document.createElementNS(n.namespaceURI,'use');n.classList.add('bgm-icon');n.setAttribute('aria-hidden','true');u.setAttribute('href','#bgm-i-'+name);n.append(u);return n;}
  function button(label,name,fn,cls='bgm-icon-button'){const b=document.createElement('button');b.type='button';b.className=cls;b.title=label;b.setAttribute('aria-label',label);if(name)b.append(icon(name));b.addEventListener('click',fn);return b;}
  function date(value){if(!value)return '—';const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'—';}
  function time(value){if(!Number.isFinite(value)||value<0)return '—';const s=Math.floor(value);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');}
  function showError(message){$('bgm-error').textContent=message||'';$('bgm-error').hidden=!message;}
  function cover(url){const fallback=textNode('span','','bgm-cover');fallback.setAttribute('aria-hidden','true');if(!url?.startsWith('https://'))return fallback;const img=document.createElement('img');img.className='bgm-cover';img.alt='';img.loading='lazy';img.src=url;img.addEventListener('error',()=>img.replaceWith(fallback),{once:true});return img;}
  function syncPreview(){
    const audio=$('bgm-preview'),playing=!!previewTrack&&!audio.paused&&!audio.ended&&previewState!=='error';
    $('bgm-preview-toggle').replaceChildren(icon(playing?'pause':'play'));
    $('bgm-preview-toggle').setAttribute('aria-label',playing?'暂停试听':'继续试听');
    $('bgm-preview-status').textContent=previewState==='loading'?'正在加载音频…':previewState==='error'?'加载失败，可再次点击播放':audio.ended?'试听结束':playing?'正在试听':'已暂停';
    $('bgm-preview-time').textContent=time(audio.currentTime||0)+' / '+time(audio.duration);
    document.querySelectorAll('[data-preview-id]').forEach(b=>{const active=previewTrack?.id===b.dataset.previewId,live=active&&playing;b.replaceChildren(icon(live?'pause':'play'));b.classList.toggle('is-playing',live);b.setAttribute('aria-label',(live?'暂停试听：':'试听：')+b.dataset.trackName);b.title=b.getAttribute('aria-label');b.setAttribute('aria-pressed',String(live));});
  }
  function stopPreview(){previewGeneration++;previewTrack=null;previewState='idle';const audio=$('bgm-preview');audio.pause();audio.removeAttribute('src');audio.load();$('bgm-preview-player').hidden=true;syncPreview();}
  async function preview(track){
    if(!track.audio_url?.startsWith('https://'))return showError('该音频尚不可试听。');
    const audio=$('bgm-preview');
    if(previewTrack?.id===track.id&&previewState!=='error'&&!audio.paused&&!audio.ended){previewGeneration++;previewState='paused';audio.pause();syncPreview();return;}
    if(previewTrack?.id!==track.id){stopPreview();previewTrack=track;audio.src=track.audio_url;$('bgm-preview-title').textContent=track.name;$('bgm-preview-player').hidden=false;}
    const run=++previewGeneration;if(previewState==='error')audio.load();previewState='loading';showError('');syncPreview();
    try{await audio.play();if(run===previewGeneration){previewState='playing';syncPreview();}}
    catch(_){if(run===previewGeneration){previewState='error';syncPreview();showError('试听未能播放，请检查音频或再次点击播放。');}}
  }
  function closeMenu(restore=false){$('bgm-row-menu').hidden=true;if(menuTrigger){menuTrigger.setAttribute('aria-expanded','false');if(restore&&menuTrigger.isConnected)menuTrigger.focus();}menuTrigger=null;}
  function openMenu(track,trigger){
    if(menuTrigger===trigger){closeMenu(true);return;}closeMenu();menuTrigger=trigger;const menu=$('bgm-row-menu');menu.replaceChildren();
    function entry(label,fn){const b=textNode('button',label);b.type='button';b.setAttribute('role','menuitem');b.addEventListener('click',()=>{closeMenu();fn();});menu.append(b);}
    entry('查看详情',()=>showDetail(track.id));entry(isObserver()?'预览封面':'管理封面',()=>BgmCoverUI.open(track.id));
    if(!isObserver()){
      if(!['deleting','delete_failed'].includes(track.audio_state))entry('修改名称',()=>BgmDirectoryUI.open(track,'rename',catalogVersion));
      if(track.audio_state==='failed')entry('重选文件重试',()=>BgmUploadUI.open(track));
    }
    entry('资产与清理',()=>BgmCleanupUI.open(track.id));menu.hidden=false;trigger.setAttribute('aria-expanded','true');
    const rect=trigger.getBoundingClientRect(),bounds=menu.getBoundingClientRect();menu.style.left=Math.max(8,Math.min(rect.right-bounds.width,window.innerWidth-bounds.width-8))+'px';menu.style.top=Math.max(8,Math.min(rect.bottom+6,window.innerHeight-bounds.height-8))+'px';menu.firstElementChild?.focus();
  }
  function cleanupNote(track){const s=track.cleanup_summary;if(!s)return '';return [['音频',s.audio],['封面',s.cover]].flatMap(([name,x])=>{const parts=[];if(x?.pending)parts.push(name+'待清理 '+x.pending);if(x?.failed)parts.push(name+'清理失败 '+x.failed);return parts;}).join(' · ');}
  function deletion(track){
    if(track.enabled)return ['启用中','先隐藏后才能删除'];
    if(track.audio_state==='deleting')return ['清理中','正在删除专属资源'];
    if(track.audio_state==='delete_failed')return ['待重试','到“资产与清理”核对剩余资源'];
    if(!['ready','failed'].includes(track.audio_state))return ['处理中','完成处理后再核对'];
    if(!track.ever_published)return ['无需等待','从未发布，可核对删除资格'];
    if(!track.deletable_at)return ['待核对','打开“资产与清理”核对'];
    return new Date(track.deletable_at).getTime()>Date.now()?['等待期内',date(track.deletable_at)+' 后可申请']:['可申请删除',date(track.deletable_at)];
  }
  function render(items){
    closeMenu();const body=$('bgm-tracks');body.replaceChildren();
    items.forEach(track=>{
      const row=document.createElement('tr');row.dataset.trackId=track.id;
      const name=document.createElement('td'),identity=textNode('div','','bgm-track-name'),thumb=button('预览封面：'+track.name,null,()=>BgmCoverUI.open(track.id),'bgm-cover-button');thumb.append(cover(track.cover_url));
      const copy=textNode('div','','bgm-track-copy');copy.append(textNode('strong',track.name),textNode('span',track.is_default?'默认播放 · '+track.id.slice(0,8):'ID '+track.id.slice(0,8)));identity.append(thumb,copy);name.append(identity);row.append(name);
      const state=document.createElement('td');state.append(textNode('span',states[track.audio_state]||'状态待核对','bgm-state bgm-state-'+track.audio_state));
      if(track.failure_category)state.append(textNode('small',failures[track.failure_category]||'音频处理失败，请重选文件','bgm-row-note is-error'));
      const cleanup=cleanupNote(track);if(cleanup)state.append(textNode('small',cleanup,'bgm-row-note'));row.append(state);
      const enabled=document.createElement('td'),toggle=button((track.enabled?'隐藏':'启用')+'：'+track.name,null,()=>BgmDirectoryUI.open(track,track.enabled?'hide':'enable',catalogVersion),'bgm-switch');toggle.setAttribute('role','switch');toggle.setAttribute('aria-checked',String(track.enabled));toggle.dataset.action=track.enabled?'hide':'enable';if(!isObserver())toggle.dataset.writeAction='';toggle.append(textNode('span',''));toggle.disabled=isObserver()||track.audio_state!=='ready'||!track.audio_url;enabled.append(toggle);row.append(enabled);
      const def=document.createElement('td'),star=button(track.is_default?'当前默认：'+track.name:'设为默认：'+track.name,'star',()=>BgmDirectoryUI.open(track,'set_default',catalogVersion),'bgm-icon-button bgm-default-star');star.classList.toggle('is-default',track.is_default);star.dataset.action='set_default';if(!isObserver())star.dataset.writeAction='';star.setAttribute('aria-pressed',String(track.is_default));star.disabled=isObserver()||!track.enabled||track.is_default;def.append(star);row.append(def);
      const order=document.createElement('td');if(track.enabled){const controls=textNode('div','','bgm-order-controls');controls.append(textNode('span',String(track.sort_position+1).padStart(2,'0')));for(const [label,delta,name] of [['上移',-1,'up'],['下移',1,'down']]){const b=button(label+'：'+track.name,name,()=>BgmDirectoryUI.move(track,delta,catalogVersion));if(!isObserver())b.dataset.writeAction='';b.disabled=isObserver()||(delta<0?track.sort_position<=0:track.sort_position>=enabledCount-1);controls.append(b);}order.append(controls);}else order.append(textNode('span','—','bgm-muted'));row.append(order);
      const audio=document.createElement('td');audio.append(textNode('span',time(track.duration_seconds)),textNode('small',track.size_bytes==null?'—':(track.size_bytes/1048576).toFixed(2)+' MiB','bgm-row-note'));row.append(audio);
      const removal=document.createElement('td'),[status,hint]=deletion(track);removal.append(textNode('span',status),textNode('small',hint,'bgm-row-note'));row.append(removal);
      const actions=document.createElement('td'),group=textNode('div','','bgm-row-actions');const listen=button('试听：'+track.name,'play',()=>preview(track));listen.dataset.previewId=track.id;listen.dataset.trackName=track.name;listen.disabled=track.audio_state!=='ready'||!track.audio_url;group.append(listen);
      const more=button('更多操作：'+track.name,'more',()=>openMenu(track,more));more.setAttribute('aria-haspopup','menu');more.setAttribute('aria-expanded','false');group.append(more);actions.append(group);row.append(actions);body.append(row);
    });
    $('bgm-count').textContent=total+' 首音乐';$('bgm-status').textContent=total?'共 '+total+' 首音乐':'暂无符合条件的音乐';$('bgm-empty').hidden=items.length>0;
    $('bgm-page').textContent='第 '+page+' 页';$('bgm-prev').disabled=page<=1;$('bgm-next').disabled=page*pageSize>=total;syncPreview();
  }
  async function load(){
    const run=++generation;showError('');$('bgm-status').textContent='正在读取音乐库…';
    const params=new URLSearchParams({page,page_size:pageSize,search:$('bgm-search').value.trim(),filter,sort:'playlist'});if($('bgm-state').value)params.set('state',$('bgm-state').value);
    const result=await adminRequest('GET','/api/admin/bgm/tracks?'+params,null,false,{silentErrorToast:true});if(run!==generation)return;
    if(!result||result.code!==0){$('bgm-status').textContent='音乐库暂时无法读取';showError(result?.message||'读取失败，请重试。');return;}
    const data=result.data;total=data.total;catalogVersion=data.catalog_version;enabledCount=data.summary?.enabled??0;
    if(page>1&&(page-1)*pageSize>=total){page=Math.max(1,Math.ceil(total/pageSize));return load();}
    for(const key of ['all','enabled','hidden','failed'])$('bgm-filter-count-'+key).textContent=data.summary?.[key==='all'?'total':key]??'—';
    $('bgm-summary-total').textContent=data.summary?.total??'—';$('bgm-summary-enabled').textContent=data.summary?.enabled??'—';$('bgm-catalog-version').textContent='v'+catalogVersion;
    $('bgm-default-name').textContent=data.default_track?.name||'暂无默认曲目';$('bgm-enabled-note').textContent=(data.summary?.enabled??'—')+' 首正在启用';$('bgm-summary-pending').textContent=(data.summary?.hidden??'—')+' 首待启用';render(data.list);
  }
  async function showDetail(id){const run=++detailGeneration,result=await adminRequest('GET','/api/admin/bgm/tracks/'+encodeURIComponent(id),null,false,{silentErrorToast:true});if(run!==detailGeneration)return;if(!result||result.code!==0)return showError(result?.message||'详情读取失败，请重试。');const t=result.data.track,grid=textNode('dl','','bgm-detail-grid');[['名称',t.name],['状态',states[t.audio_state]],['曲目标识',t.id],['记录版本',t.record_version],['音频版本',t.media_version],['封面版本',t.cover_version],['创建时间',date(t.created_at)],['最近隐藏',date(t.hidden_at)],['可删除时间',date(t.deletable_at)]].forEach(([n,v])=>grid.append(textNode('dt',n),textNode('dd',v)));$('bgm-detail-body').replaceChildren(grid);$('bgm-detail').showModal();}
  function chooseFilter(value){filter=value;document.querySelectorAll('[data-filter]').forEach(b=>{const active=b.dataset.filter===filter;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;});page=1;load();}
  function init(){
    if(!checkAdminLogin())return;if(!ALLOWED_ROLES.includes(getAdminRole())){window.location.href='/admin/pages/error.html?type=403';return;}
    $('sidebar-mount').innerHTML=renderSidebar('bgm');$('header-mount').innerHTML=renderHeader('BGM 管理');$('bgm-content').hidden=false;$('bgm-read-only').hidden=!isObserver();applyObserverReadOnly();
    BgmUploadUI.init({reload:load});BgmDirectoryUI.init({reload:load});BgmCoverUI.init({reload:load});BgmCleanupUI.init({reload:load});
    window.addEventListener('pagehide',stopPreview);document.addEventListener('visibilitychange',()=>{if(document.hidden){stopPreview();closeMenu();}});
    const audio=$('bgm-preview');for(const name of ['play','pause','timeupdate','durationchange','ended'])audio.addEventListener(name,()=>{if(name==='play')previewState='playing';syncPreview();});
    audio.addEventListener('error',()=>{if(previewTrack){previewState='error';syncPreview();showError('试听音频加载失败，请刷新后重试。');}});
    $('bgm-preview-toggle').addEventListener('click',()=>{if(previewTrack)preview(previewTrack);});$('bgm-preview-close').addEventListener('click',stopPreview);
    function setNavigation(open){document.body.classList.toggle('bgm-nav-open',open);$('bgm-nav-toggle').setAttribute('aria-expanded',String(open));$('bgm-nav-toggle').textContent=open?'关闭导航':'导航';}
    $('bgm-nav-toggle').addEventListener('click',()=>setNavigation(!document.body.classList.contains('bgm-nav-open')));
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){setNavigation(false);closeMenu(true);}});document.addEventListener('pointerdown',e=>{if(!e.target.closest('#bgm-row-menu')&&!menuTrigger?.contains(e.target))closeMenu();});window.addEventListener('resize',()=>closeMenu());document.addEventListener('scroll',()=>closeMenu(),true);
    $('bgm-row-menu').addEventListener('keydown',e=>{const items=[...$('bgm-row-menu').querySelectorAll('button')],index=items.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();items[e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus();}if(e.key==='Tab')closeMenu();});
    document.querySelectorAll('[data-filter]').forEach((b,index,buttons)=>{b.addEventListener('click',()=>chooseFilter(b.dataset.filter));b.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;buttons[next].focus();chooseFilter(buttons[next].dataset.filter);});});
    $('bgm-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=1;load();},220);});$('bgm-state').addEventListener('change',()=>{page=1;load();});
    $('bgm-filters').addEventListener('submit',e=>{e.preventDefault();clearTimeout(searchTimer);page=1;load();});$('bgm-refresh').addEventListener('click',()=>load());$('bgm-prev').addEventListener('click',()=>{if(page>1){page--;load();}});$('bgm-next').addEventListener('click',()=>{if(page*pageSize<total){page++;load();}});
    $('bgm-detail-close').addEventListener('click',()=>{detailGeneration++;$('bgm-detail').close();});
    $('bgm-operation-form').addEventListener('submit',async e=>{e.preventDefault();const run=++operationGeneration,id=$('bgm-operation-id').value.trim(),result=await adminRequest('GET','/api/admin/bgm/operations/'+encodeURIComponent(id),null,false,{silentErrorToast:true});if(run!==operationGeneration)return;$('bgm-operation-result').textContent=result?.code===0?(states[result.data.state]||'结果待核对')+' · '+result.data.id:result?.message||'暂时无法核对，请保留原操作标识后重试。';});load();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();

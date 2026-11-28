(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const api = '/api/admin/feed/video';
  const statuses = {queued:'排队中',processing:'处理中',ready:'媒体已就绪',failed:'处理失败',cancelled:'已取消'};
  const transfers = new Map();
  let edit = null, timer = null, dirty = false, busy = false, session = 0;
  let listRequest = 0, opener = null;
  const readOnly = () => isLifeFeedReadOnly('feed-posts');
  const error = message => { $('video-error').textContent = message || ''; };
  const expiry = e => e.media_expired ? '草稿媒体已到期' : e.expires_at ? '媒体到期 ' + new Date(e.expires_at+'Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '';
  function status(e) {
    if (e.pending_upload) return '正在接收或校验';
    if (e.last_receive_error) return e.last_receive_error;
    if (e.media_expired) return '草稿视频已清理，请重新上传';
    return e.failure_reason || statuses[e.task_state] || '等待选择视频';
  }
  async function request(method,path,data,blob=false) {
    const result = await adminRequest(method,api+path,data,blob,{returnErrorResponse:true,silentErrorToast:true});
    if (!result || result.code!==0) throw Error(typeof result?.detail==='string' ? result.detail : result?.message || '请求中断，请刷新查询原操作');
    return result.data;
  }
  function clearPlayer(el) {
    el.pause(); el.removeAttribute('src'); el.removeAttribute('poster'); el.load();
  }
  function close() {
    session++; clearInterval(timer); edit=null; dirty=false; busy=false;
    clearPlayer($('video-list-preview')); clearPlayer($('video-full-preview'));
    $('video-editor').classList.remove('show'); $('video-editor').setAttribute('aria-hidden','true');
    if (opener?.isConnected) opener.focus();
    list();
  }
  function showDrafts(active) {
    $('feed-post-list').hidden=active;
    $('video-drafts').hidden=!active;
    $('posts-view').setAttribute('aria-pressed', String(!active));
    $('drafts-view').setAttribute('aria-pressed', String(active));
    if (active) list();
  }
  function element(tag, className, value) {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = value;
    return node;
  }
  function draftRow(row) {
    const item = element('article', 'draft-row', '');
    const summary = element('div', 'draft-summary', '');
    const caption = row.content_text || row.upload?.filename || '未填写文案';
    const title = element('strong', 'draft-caption', caption);
    title.title = caption;
    summary.append(title, element('small', 'draft-ref',
      (row.is_replacement ? '更换视频' : '新帖草稿')+' #'+row.id+' · 帖子 #'+row.post_id));
    const tone = row.pending_upload ? 'blue' : row.media_expired || row.task_state === 'failed' || row.last_receive_error ? 'error' :
      ({ready:'success',queued:'blue',processing:'blue'})[row.task_state] || 'default';
    const statusTag = element('span', 'draft-state tag tag-'+tone, status(row));
    const button = element('button', 'btn btn-default btn-sm', readOnly() ? '查看' : '继续编辑');
    button.type = 'button';
    button.dataset.editId = row.id;
    button.onclick = () => open(row.id);
    item.append(summary, statusTag, element('small','video-note draft-date',expiry(row)), button);
    return item;
  }
  async function list() {
    const target=$('video-draft-list'), requestId=++listRequest;
    try {
      const rows=await request('GET','/edits');
      if (requestId!==listRequest) return;
      $('draft-count').textContent=String(rows.length);
      target.replaceChildren(...(rows.length ? rows.map(draftRow) : [element('p','empty-tip','暂无视频草稿')]));
    } catch(e) {
      if (requestId!==listRequest) return;
      $('draft-count').textContent='';
      target.replaceChildren(element('p','empty-tip',e.message));
    }
  }
  function scheduledTime() {
    const input=$('video-time').value, original=edit?.scheduled_publish_time || null;
    return input===(original || '').slice(0,16) ? original : input || null;
  }
  function timeValid() {
    const time=scheduledTime();
    return edit?.is_replacement || !time || Date.parse(time+'+08:00')>Date.now();
  }
  function framing() {
    const v=edit?.assets?.video;
    $('video-list-frame').style.aspectRatio=v && v.height>v.width?'4/5':(v?v.width+'/'+v.height:'4/5');
    for (const id of ['video-list-cover','video-list-preview']) {
      $(id).style.objectFit=$('video-mode').value==='contain'?'contain':'cover';
      $(id).style.objectPosition='50% '+$('video-position').value+'%';
    }
  }
  function update() {
    if (!edit) return;
    const assets=edit.assets||{}, src=edit.source_info, track=src?.streams?.find(s=>s.codec_type==='video');
    const final=assets.video, progress=transfers.get(edit.id);
    $('video-title').textContent=edit.is_replacement?'更换视频':'视频发帖';
    $('video-reference').textContent='帖子 #'+edit.post_id+' · 编辑 #'+edit.id;
    const attempt=edit.pending_upload || edit.failed_upload || edit.upload;
    $('video-status').textContent=(attempt?.filename ? attempt.filename+' · ':'')+status(edit)+(attempt?.task_id?' · 任务 #'+attempt.task_id:'');
    $('video-expires').textContent=expiry(edit);
    $('video-file-action').textContent=edit.upload?'更换视频文件':'选择视频';
    $('video-time-hint').textContent=edit.is_replacement?'沿用原帖发布时间（北京时间）':'北京时间，留空立即发布';
    $('video-progress').hidden=!progress;
    $('video-progress').value=progress?.pct||0;
    $('video-percent').textContent=progress ? progress.name+' '+progress.pct+'%'+(progress.pct===100?' · 等待校验':'') : '';
    $('video-spec').textContent=[edit.failed_upload && edit.upload && '当前保留「'+edit.upload.filename+'」',
      track && '原片 '+(src.format.tags?.major_brand||'MP4/MOV')+' '+track.width+'×'+track.height+' · '+(edit.upload.size_bytes/1048576).toFixed(2)+' MiB · '+Number(src.format.duration)+' 秒',
      final && '正片 MP4/H.264 '+final.width+'×'+final.height+' · '+(final.size_bytes/1048576).toFixed(2)+' MiB · '+final.duration_ms/1000+' 秒'].filter(Boolean).join('\n');
    $('video-submit').textContent=edit.is_replacement?'保存更改':$('video-time').value?'定时发布':'立即发布';
    $('video-submit').disabled=readOnly()||busy||!!progress||!!edit.pending_upload||!!edit.last_receive_error||edit.task_state!=='ready'||!$('video-text').value.trim()||!timeValid();
    $('video-save').disabled=readOnly()||busy;
    $('video-retry').hidden=readOnly()||edit.task_state!=='failed'||/导出 SDR|重新选择|损坏/.test(edit.failure_reason||'');
    const keep=$('video-keep-selected');
    keep.hidden=readOnly() || !edit.failed_upload || !edit.upload || edit.task_state!=='ready';
    keep.disabled=busy || !!progress;
    if (!keep.hidden) keep.textContent='沿用原视频「'+edit.upload.filename+'」';
    $('video-file').disabled=readOnly()||!!progress;
    $('video-time').disabled=readOnly()||edit.is_replacement;
    $('video-framing').hidden=!edit.upload?.task_id;
    for (const [id,kind] of [['video-pin-cover','cover_small'],['video-list-cover','cover_large']]) {
      const el=$(id),url=assets[kind]?.url;
      if(url && el.getAttribute('src')!==url) el.src=url;
      if(!url) el.removeAttribute('src');
      el.hidden=!url || (id==='video-list-cover' && !$('video-list-preview').hidden);
    }
    $('video-test-preview').disabled=!assets.preview; $('video-test-full').disabled=!final;
    framing();
  }
  function fields() {
    return {content_text:$('video-text').value,hashtags:parseHashtags($('video-hashtags').value),
      emotion:$('video-emotion').value.trim() || '平静',scheduled_publish_time:scheduledTime(),
      frame_mode:$('video-mode').value,frame_position:Number($('video-position').value)};
  }
  async function refresh(id, epoch, setFields=false) {
    const data=await request('GET','/edits/'+id);
    if(epoch!==session) return;
    if (edit && data.version < edit.version) return;
    if (data.state!=='draft') { close(); showToast(data.state==='submitted'?'提交已确认':'编辑已结束','success'); return; }
    // Automatic status polling cannot advance the revision of unsaved form input.
    const transfer=transfers.get(id);
    const ownReservation=transfer && data.version===transfer.version+1 &&
      [data.pending_upload,data.failed_upload,data.upload].some(row=>row?.operation_id===transfer.key);
    if (edit && dirty && data.version!==edit.version && !setFields && !ownReservation) {
      error('编辑已更新，请刷新后重新编辑'); return;
    }
    edit=data;
    if(setFields || !dirty) {
      $('video-text').value=data.content_text||'';
      $('video-hashtags').value=(data.hashtags||[]).join(', ');
      $('video-emotion').value=data.emotion||'平静';
      $('video-time').value=(data.scheduled_publish_time||'').slice(0,16);
      $('video-mode').value=data.frame_mode; $('video-position').value=data.frame_position;
    }
    update();
    if(!timeValid())error('预设时间已过，请修改或清空后提交');
  }
  async function open(id) {
    const epoch=++session; clearInterval(timer); dirty=false; busy=false; edit=null; error('');
    opener=document.activeElement;
    $('video-file').value=''; $('video-cover-file').value='';
    clearPlayer($('video-full-preview')); clearPlayer($('video-list-preview')); $('video-list-preview').hidden=true;
    try {
      await refresh(id,epoch,true); if(epoch!==session || !edit) return;
      $('video-editor').classList.add('show'); $('video-editor').setAttribute('aria-hidden','false');
      for (const el of $('video-editor').querySelectorAll('[data-write-action]')) el.hidden=readOnly();
      update();
      for(const id of ['video-text','video-hashtags','video-emotion','video-mode','video-position']) $(id).disabled=readOnly();
      $('video-close').focus();
      timer=setInterval(()=>{if(!busy) refresh(id,epoch).catch(e=>error(e.message));},1500);
    } catch(e) {showToast(e.message,'error');}
  }
  async function save() {
    if(!dirty)return edit;
    const id=edit.id, values=fields();
    const result=await request('PATCH','/edits/'+id,{version:edit.version,...values});
    if(edit?.id===id) {
      dirty=JSON.stringify(fields())!==JSON.stringify(values);
      edit=result;
      update();
    }
    return result;
  }
  async function action(fn) {
    if(busy||readOnly()||!edit)return;
    const epoch=session; busy=true; error(''); update();
    try {await fn();}
    catch(e){if(epoch===session) error(e.message);}
    finally {if(epoch===session){busy=false;update();}list();}
  }
  function transfer(id, key, file) {
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open('PUT',api+'/uploads/'+key+'/content');
      xhr.setRequestHeader('Authorization','Bearer '+getAdminToken());
      xhr.upload.onprogress=e=>{const progress=transfers.get(id);if(progress) progress.pct=Math.round(100*e.loaded/file.size);if(edit?.id===id)update();};
      xhr.onload=()=>{let body;try{body=JSON.parse(xhr.responseText);}catch{}
        if(xhr.status===200 && body?.code===0)resolve(body.data);else reject(Error(body?.detail||'上传失败，请重选文件'));};
      xhr.onerror=()=>reject(Error('上传中断，请重新进入原编辑核对接收结果'));xhr.send(file);
    });
  }
  async function upload(file) {
    if(!file||!edit||busy||readOnly()||transfers.has(edit.id))return;
    const id=edit.id, epoch=session, key=crypto.randomUUID();
    const progress={key,name:file.name,pct:0,version:edit.version};
    transfers.set(id,progress);error('');update();
    try {
      const saved=await save();
      progress.version=saved.version;
      await request('POST','/edits/'+id+'/uploads',{operation_id:key,filename:file.name,size_bytes:file.size,version:progress.version});
      if(edit?.id===id && edit.version===progress.version)edit.version=progress.version+1;
      await transfer(id,key,file);
    } catch(e){if(epoch===session)error(e.message);}
    finally {
      try {if(epoch===session)await refresh(id,epoch);}
      catch(e){if(epoch===session)error(e.message);}
      transfers.delete(id);if(edit?.id===id)update();list();
    }
  }
  async function create(path, version) {
    if(readOnly()) return;
    const storage='feed-video-request:'+path+':'+(version||0);
    const uuid=sessionStorage.getItem(storage)||crypto.randomUUID();
    sessionStorage.setItem(storage,uuid);
    try {
      const result=await request('POST',path,{request_id:uuid,...(version?{version}:{})});
      sessionStorage.removeItem(storage);await open(result.id);list();
    }catch(e){showToast(e.message,'error');}
  }
  window.feedVideoReplace=(pid,version)=>create('/posts/'+pid+'/edits',version);
  document.addEventListener('DOMContentLoaded',()=>{
    $('add-video').onclick=()=>create('/edits');
    $('posts-view').onclick=()=>showDrafts(false);
    $('drafts-view').onclick=()=>showDrafts(true);
    $('video-close').onclick=()=>{if(dirty) showConfirm('关闭并放弃尚未保存的修改？',close); else close();};
    $('video-editor').addEventListener('keydown',e=>{
      if(e.key==='Escape' && !busy) {e.preventDefault();$('video-close').click();}
    });
    $('edit-video-media').onclick=()=>{const el=$('edit-id');$('edit-modal').classList.remove('show');window.feedVideoReplace(el.value,Number(el.dataset.version));};
    for(const id of ['video-text','video-hashtags','video-emotion','video-time','video-mode','video-position']) $(id).oninput=()=>{dirty=true;error(timeValid()?'':'预设时间已过，请修改或清空后提交');update();};
    $('video-file').onchange=e=>{const file=e.target.files[0];e.target.value='';upload(file);};
    $('video-save').onclick=()=>action(async()=>{await save();showToast('草稿已保存','success');});
    $('video-submit').onclick=()=>action(async()=>{
      await save();const key='feed-video-submit:'+edit.id+':'+edit.version;
      const uuid=sessionStorage.getItem(key)||crypto.randomUUID();sessionStorage.setItem(key,uuid);
      const res=await request('POST','/edits/'+edit.id+'/submit',{request_id:uuid,version:edit.version});
      sessionStorage.removeItem(key);close();showDrafts(false);showToast(({scheduled:'定时待发布',published:'已立即发布',replaced:'更改已保存'})[res.action],'success');
      document.getElementById('btn-search').click();
    });
    $('video-abandon').onclick=()=>showConfirm('放弃本次编辑？',()=>action(async()=>{await request('DELETE','/edits/'+edit.id);close();}));
    $('video-retry').onclick=()=>action(async()=>{await request('POST','/edits/'+edit.id+'/uploads/'+edit.upload.operation_id+'/retry');await refresh(edit.id,session);});
    $('video-keep-selected').onclick=()=>action(async()=>{
      const id=edit.id, failedId=edit.failed_upload.operation_id, mediaVersion=edit.upload.operation_id;
      const saved=await save();
      const kept=await request('POST','/edits/'+id+'/uploads/'+failedId+'/keep-selected',
                               {version:saved.version,media_version:mediaVersion});
      if(edit?.id===id){edit=kept;update();}
    });
    async function cover(file) {
      await save();const url='/edits/'+edit.id+'/uploads/'+edit.upload.operation_id+'/cover';
      edit=await request(file?'PUT':'POST',url+(file?'':'/default')+'?version='+edit.version,file,!!file);update();
    }
    $('video-cover-file').onchange=e=>{const f=e.target.files[0];e.target.value='';if(f)action(()=>cover(f));};
    $('video-default').onclick=()=>action(()=>cover(null));
    $('video-test-preview').onclick=()=>{const v=$('video-list-preview');v.src=edit.assets.preview.url;v.hidden=false;$('video-list-cover').hidden=true;v.play().catch(e=>error(e.message));};
    $('video-list-preview').onended=()=>{$('video-list-preview').hidden=true;$('video-list-cover').hidden=false;};
    $('video-test-full').onclick=()=>{const v=$('video-full-preview');v.src=edit.assets.video.url;v.play().catch(e=>error(e.message));};
    list();
  });
})();

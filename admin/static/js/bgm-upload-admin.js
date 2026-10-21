/* Recoverable admin upload. This module never accesses H5 preference/session keys. */
window.BgmUploadUI = (function () {
  'use strict';
  const prefix = 'lxm_admin_bgm_operation:';
  const $ = id => document.getElementById(id);
  let pending = null, target = null, busy = false, completed = false, audioFile = null, coverCandidate = null, coverSequence = 0, coverPreparing = false, reload = () => {};
  const terminal = new Set(['succeeded', 'failed']);
  const failures = {source_mismatch:'文件与原提交不一致',size_limit:'文件大小不符合要求',duration_limit:'时长须大于0且不超过300秒',
    unsupported_format:'不支持此音频格式',mime_mismatch:'文件类型不匹配',format_mismatch:'真实格式与文件类型不一致',decode_failed:'文件损坏或无法解码',
    invalid_audio:'未发现合法音频',processing_timeout:'处理超时',receive_timeout:'接收超时',deadline_expired:'操作已超时',worker_interrupted:'处理已中断',
    authorization_changed:'提交权限已变化',storage_unknown:'文件存储结果待清理核对',remote_unreadable:'音频访问验证失败',storage_unavailable:'存储服务不可用',
    storage_configuration:'音乐存储或播放站点配置不完整',remote_cors:'音频跨域播放验证失败，请联系管理员检查存储配置',
    remote_range:'音频进度读取验证失败，请联系管理员检查存储配置',remote_mime:'音频响应类型验证失败',
    dependency_unavailable:'音频处理服务暂不可用，请联系管理员检查处理环境',processing_failed:'音频处理失败，请核对处理环境与源文件后重试'};

  function status(text) { $('bgm-upload-status').textContent = text; }
  function stage(text) { const el=$('bgm-upload-progress');if(el){el.textContent=text;el.hidden=!text;} }
  function sync(){
    $('bgm-upload-submit').disabled=busy||completed||coverPreparing;
    $('bgm-upload-name').disabled=busy||completed||!!pending;
    $('bgm-upload-file').disabled=busy||completed;
    $('bgm-upload-check').disabled=busy;
    $('bgm-pending').disabled=busy;
    for(const id of ['bgm-upload-file-remove','bgm-upload-cover-file','bgm-upload-cover-remove'])if($(id))$(id).disabled=busy||completed||coverPreparing;
    if($('bgm-upload-name-count'))$('bgm-upload-name-count').textContent=[...$('bgm-upload-name').value.trim()].length+' / 60';
    if($('bgm-upload-drop'))$('bgm-upload-drop').setAttribute('aria-disabled',String(busy||completed));
  }
  function chooseAudio(file){
    if(busy||completed)return;
    audioFile=file||null;
    if(!audioFile)$('bgm-upload-file').value='';
    // A dropped File is kept in memory; no synthetic FileList or binary persistence is needed.
    $('bgm-upload-file').required=!audioFile;
    if($('bgm-upload-file-card'))$('bgm-upload-file-card').hidden=!audioFile;
    if($('bgm-upload-file-name'))$('bgm-upload-file-name').textContent=audioFile?.name||'';
    if($('bgm-upload-file-size'))$('bgm-upload-file-size').textContent=audioFile?(audioFile.size/1048576).toFixed(2)+' MiB':'';
    sync();
  }
  function clearCover(){
    coverSequence++;coverPreparing=false;
    if(coverCandidate?.url)URL.revokeObjectURL(coverCandidate.url);coverCandidate=null;
    if($('bgm-upload-cover-file'))$('bgm-upload-cover-file').value='';
    if($('bgm-upload-cover-preview'))$('bgm-upload-cover-preview').replaceChildren();
    if($('bgm-upload-cover-remove'))$('bgm-upload-cover-remove').hidden=true;
    if($('bgm-upload-cover-note'))$('bgm-upload-cover-note').textContent='封面可选。音频成功后独立保存；无封面可继续。';
  }
  async function chooseCover(){
    if(busy||completed)return;
    const file=$('bgm-upload-cover-file').files[0];clearCover();
    if(!file){sync();return;}
    const run=coverSequence;coverPreparing=true;sync();
    $('bgm-upload-cover-note').textContent='正在读取封面预览…';
    try{
      const prepared=await BgmCoverUI.prepareFile(file);
      if(run!==coverSequence){URL.revokeObjectURL(prepared.url);return;}
      coverCandidate=prepared;
      const image=document.createElement('img');image.alt='本次选填封面预览';image.src=prepared.url;$('bgm-upload-cover-preview').append(image);
      $('bgm-upload-cover-remove').hidden=false;
      $('bgm-upload-cover-note').textContent=file.name+' · 本次预览，音频成功后独立保存。';
    }catch(error){if(run===coverSequence)$('bgm-upload-cover-note').textContent=error.message||'封面无法读取，可重新选择或无图继续。';}
    finally{if(run===coverSequence){coverPreparing=false;sync();}}
  }
  function name(value) {
    if (/[\u0000-\u001F\u007F-\u009F\uD800-\uDFFF]/u.test(value)) throw new Error('音乐名称不能含控制字符。');
    value = value.trim();
    if (![...value].length || [...value].length > 60) throw new Error('音乐名称须为 1～60 个 Unicode 码点。');
    return value;
  }
  function stored() {
    const items = [];
    for (let i=0; i<localStorage.length; i++) {
      const key=localStorage.key(i);
      if (!key?.startsWith(prefix)) continue;
      try {
        const item=JSON.parse(localStorage.getItem(key));
        if (item?.body?.operation_id && key===prefix+item.body.operation_id) items.push(item);
      } catch (_) { /* A malformed unrelated receipt is not a new submission. */ }
    }
    return items.sort((a,b) => a.saved_at-b.saved_at);
  }
  function save(item) {
    if (stored().length>=50) throw new Error('待核对提交过多，请先核对已有操作。');
    const key=prefix+item.body.operation_id, encoded=JSON.stringify(item);
    localStorage.setItem(key,encoded);
    if (localStorage.getItem(key)!==encoded) throw new Error('浏览器无法保存操作标识，请允许本地存储后再提交。');
  }
  function selectPending(item) {
    pending=item; completed=false;clearCover();
    $('bgm-upload-name').value=item.body.name;
    $('bgm-upload-name').disabled=true;
    $('bgm-upload-operation').textContent='操作标识：'+item.body.operation_id;
    $('bgm-upload-check').hidden=false;
    $('bgm-upload-submit').textContent='继续原提交';
    chooseAudio(null);stage('等待核对原音频操作');status('先核对原操作；如尚未接收文件，重选同一文件后可继续。');sync();
  }
  function open(track) {
    if (busy) { if (!$('bgm-upload').open) $('bgm-upload').showModal(); return; }
    target=track||null; pending=null; completed=false;clearCover();chooseAudio(null);
    $('bgm-upload-submit').disabled=false;
    $('bgm-upload-cover').hidden=true;
    $('bgm-upload-title').textContent=track?'重新处理原曲目':'上传音乐';
    $('bgm-upload-name').disabled=false; $('bgm-upload-name').value=track?.name||'';
    $('bgm-upload-file').value=''; $('bgm-upload-operation').textContent=''; $('bgm-upload-check').hidden=true;
    $('bgm-upload-submit').textContent=track?'重选文件并重试':'上传并处理';
    status('');stage('');
    try {
      const items=stored(); $('bgm-pending-label').hidden=!items.length; $('bgm-pending').replaceChildren();
      items.forEach((item,i) => { const option=document.createElement('option');option.value=String(i);option.textContent=item.body.name+' · '+item.body.operation_id;$('bgm-pending').append(option); });
      $('bgm-pending').onchange=()=>selectPending(items[Number($('bgm-pending').value)]);
      if (items.length) selectPending(items[0]);
    } catch (_) { status('浏览器无法读取本地操作记录，暂不能安全上传。'); }
    sync();if (!$('bgm-upload').open) $('bgm-upload').showModal();
  }
  async function showOperation(operation) {
    $('bgm-operation-id').value=operation.id;
    if (terminal.has(operation.state)) {
      completed=true;stage(operation.state==='succeeded'?'音频处理完成':'音频处理失败');
      try { localStorage.removeItem(prefix+operation.id); } catch (_) { /* A retained receipt can safely be queried again. */ }
      status(operation.state==='succeeded'?'音乐已就绪，尚未启用。请试听后再手动启用。':
        '音乐处理失败：'+(failures[operation.failure_category]||'请在音乐列表重新选择文件重试。'));
      pending=null; $('bgm-upload-submit').disabled=true;
      $('bgm-upload-check').hidden=true; $('bgm-pending-label').hidden=true;
      $('bgm-upload-cover').hidden=operation.state!=='succeeded';
      $('bgm-upload-cover').textContent=coverCandidate?'继续保存选填封面':'选填封面';
      $('bgm-upload-cover').onclick=async()=>{
        if(coverCandidate){
          const started=await BgmCoverUI.openWithFile(operation.track_id,coverCandidate.file,{submit:true});
          if(started){$('bgm-upload').close();clearCover();}
          else status('音乐已就绪。封面尚未提交，请先核对已有封面操作或刷新封面信息；无需重传音频。');
        }else{$('bgm-upload').close();BgmCoverUI.open(operation.track_id);}
      };
      await reload();
      if(operation.state==='succeeded'&&coverCandidate){
        stage('音频已完成 · 正在独立保存封面');
        const started=await BgmCoverUI.openWithFile(operation.track_id,coverCandidate.file,{submit:true});
        if(started){stage('音频已完成 · 封面结果见封面窗口');$('bgm-upload').close();clearCover();}
        else{stage('音频已完成 · 封面尚未提交');status('音乐已就绪，尚未启用。封面候选已保留，请先核对已有封面操作或刷新封面信息后再保存；无需重传音频。');}
      }
      sync();
    } else {
      stage(operation.state==='accepted'?'音频已接纳，等待接收':'音频接收或处理中');status(operation.state==='accepted'?'原操作已接纳，可重选同一文件继续。':'原操作正在接收或处理中，请保留标识并稍后核对。');
    }
  }
  async function check() {
    if (!pending||busy) return;
    const id=pending.body.operation_id;busy=true;sync();stage('正在核对原音频操作');
    try{
      const result=await adminRequest('GET','/api/admin/bgm/operations/'+encodeURIComponent(id),null,false,{silentErrorToast:true,returnErrorResponse:true,returnAuthError:true,timeoutMs:15000});
      if (!pending || pending.body.operation_id!==id) return;
      if (result?.code===0) await showOperation(result.data);
      else {stage('音频结果待核对');status('暂未确认原操作结果。请保留标识后重试；重新提交仍使用原标识，不会另建曲目。');}
    }finally{busy=false;sync();}
  }
  async function submit(event) {
    event.preventDefault(); if (busy || completed || coverPreparing || isObserver()) return;
    busy=true;sync();
    try {
      const file=audioFile||$('bgm-upload-file').files[0], title=name($('bgm-upload-name').value);
      if (!file || !file.size || file.size>100*1048576) throw new Error('请选择大于 0 且不超过 100 MiB 的音频文件。');
      const extension='.'+file.name.split('.').pop().toLowerCase();
      const mimes={'.mp3':['audio/mpeg','audio/mp3'],'.m4a':['audio/mp4','audio/x-m4a','audio/m4a'],'.aac':['audio/aac','audio/x-aac','audio/aacp'],'.wav':['audio/wav','audio/x-wav','audio/wave']};
      if (!mimes[extension] || (file.type && file.type!=='application/octet-stream' && !mimes[extension].includes(file.type))) throw new Error('仅接受格式匹配的 MP3、M4A、AAC、WAV。');
      if (!crypto?.subtle || !crypto?.randomUUID) throw new Error('请在安全连接中打开后台后上传。');
      stage('正在校验音频文件');status('正在核对文件内容…');
      const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
      const sha=Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
      const body={operation_id:pending?.body.operation_id||crypto.randomUUID(),action:target?'retry_audio':'upload_audio',name:title,extension,
        mime_type:file.type||'application/octet-stream',source_size:file.size,source_sha256:sha};
      if (target) { body.track_id=target.id;body.expected_revision=target.record_version; }
      if (pending) {
        const old=pending.body;
        if (old.source_sha256!==sha || old.source_size!==file.size || old.extension!==extension || old.name!==title) throw new Error('请选择原提交的同一文件；结果未核对前不能更换内容。');
      } else {
        const item={body,saved_at:Date.now()};
        try { save(item); } catch (_) { throw new Error('无法可靠保存操作标识，未提交。请允许本地存储后重试。'); }
        pending=item;
      }
      const current=pending.body;
      $('bgm-upload-operation').textContent='操作标识：'+current.operation_id; $('bgm-upload-check').hidden=false;
      stage('正在提交音频操作');status('正在接纳原操作…');
      const accepted=await adminRequest('POST','/api/admin/bgm/operations',current,false,{silentErrorToast:true,returnErrorResponse:true,returnAuthError:true,timeoutMs:15000});
      if (!accepted || accepted.code!==0) {
        stage('音频结果待核对');status(accepted?.message||'接纳结果待核对，请使用原操作标识查询。'); return;
      }
      if (accepted.data.state!=='accepted') { await showOperation(accepted.data); return; }
      stage('正在接收并处理音频');status('正在接收并处理音频，请保留此操作标识。离页或断网后仍需核对原结果。');
      const result=await adminRequest('PUT','/api/admin/bgm/operations/'+encodeURIComponent(current.operation_id)+'/content',file,true,
        {silentErrorToast:true,returnErrorResponse:true,returnAuthError:true,timeoutMs:Math.max(1000,Math.min(330000,new Date(accepted.data.deadline_at).getTime()-Date.now()+30000))});
      if (result?.code===0) await showOperation(result.data);
      else {stage('音频结果待核对');status(result?.message||'上传结果待核对。不要重建音乐，请查询原操作。');}
    } catch (error) { stage(completed?'音频已完成':pending?'音频结果待核对':'尚未提交音频');status(completed?'音频操作已结束。'+(error.message||'请刷新列表核对；无需再次上传音频。'):error.message||'上传未完成，请核对原操作。'); }
    finally { busy=false;sync(); }
  }
  function init(options) {
    reload=options.reload;
    $('bgm-upload-open').addEventListener('click',()=>{ $('bgm-upload-submit').disabled=false;open(); });
    $('bgm-upload-close').addEventListener('click',()=>$('bgm-upload').close());
    $('bgm-upload-form').addEventListener('submit',submit);
    $('bgm-upload-check').addEventListener('click',check);
    $('bgm-upload-name').addEventListener('input',sync);
    $('bgm-upload-file').addEventListener('change',()=>chooseAudio($('bgm-upload-file').files[0]));
    $('bgm-upload-file-remove')?.addEventListener('click',()=>chooseAudio(null));
    $('bgm-upload-cover-file')?.addEventListener('change',chooseCover);
    $('bgm-upload-cover-remove')?.addEventListener('click',()=>{if(!busy&&!completed){clearCover();sync();}});
    $('bgm-upload').addEventListener('close',()=>{if(!busy)clearCover();});
    const drop=$('bgm-upload-drop');
    if(drop){
      drop.addEventListener('dragover',event=>{event.preventDefault();if(!busy&&!completed)drop.classList.add('is-dragover');});
      drop.addEventListener('dragleave',()=>drop.classList.remove('is-dragover'));
      drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('is-dragover');if(busy||completed)return;const files=event.dataTransfer?.files;if(files?.length!==1){status('请一次选择一个音频文件。');return;}chooseAudio(files[0]);});
      drop.addEventListener('keydown',event=>{if(event.target!==drop||!['Enter',' '].includes(event.key))return;event.preventDefault();if(!busy&&!completed)$('bgm-upload-file').click();});
    }
    sync();
  }
  return {init,open};
})();

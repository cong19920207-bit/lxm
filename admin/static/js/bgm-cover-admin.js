/* Optional independent cover: saved image and unsaved choice always remain separate. */
window.BgmCoverUI=(function(){
  'use strict';
  const key='lxm_admin_bgm_cover_operation',$=id=>document.getElementById(id);
  let track=null,version=0,candidate=null,intent=null,pending=null,busy=false,loading=false,needsReview=false,sequence=0,reload=()=>{};
  const opts={silentErrorToast:true,returnErrorResponse:true,returnAuthError:true,timeoutMs:15000};
  function status(text){$('bgm-cover-status').textContent=text;}
  function read(){try{const x=JSON.parse(localStorage.getItem(key)||'null');return x?.body?.operation_id&&x?.track_id?x:null;}catch(_){return null;}}
  function preview(id,url){
    const box=$(id);box.replaceChildren();
    if(!url)return;
    const image=document.createElement('img');image.alt='圆形封面预览';image.src=url;image.addEventListener('error',()=>image.remove(),{once:true});box.append(image);
  }
  function clearCandidate(resetInput=true){if(candidate?.url)URL.revokeObjectURL(candidate.url);candidate=null;intent=null;if(resetInput)$('bgm-cover-file').value='';preview('bgm-cover-candidate',null);}
  function sync(){
    const write=!isObserver()&&Number.isInteger(track?.record_version)&&!['deleting','delete_failed','deleted'].includes(track.audio_state);
    $('bgm-cover-write').hidden=!write;$('bgm-cover-save').disabled=busy||loading||needsReview||!write||(!intent&&!pending)||(!candidate&&pending?.kind==='upload');
    $('bgm-cover-remove').disabled=busy||loading||!!pending||!track?.cover_url;
    $('bgm-cover-file').disabled=busy||loading||pending?.kind==='remove';
    $('bgm-cover-check').hidden=!pending;$('bgm-cover-check').disabled=busy;
    $('bgm-cover-pending').hidden=!read();$('bgm-cover-operation').textContent=pending?'操作标识：'+pending.body.operation_id:'';
    $('bgm-cover-candidate-group').hidden=!intent&&!candidate;
    $('bgm-cover-refresh').disabled=busy||loading||!!pending;
    $('bgm-cover-save').textContent=pending?'继续原提交':intent==='remove'?'确认移除封面':'保存封面';
  }
  async function refresh(){
    if(!track||busy||pending)return false;
    const current=++sequence,id=track.id;loading=true;sync();status('正在读取已保存信息…');
    try{
      const result=await adminRequest('GET','/api/admin/bgm/tracks/'+encodeURIComponent(id),null,false,opts);
      if(current!==sequence)return false;
      if(result?.code!==0){needsReview=true;status('已保存信息读取失败，请刷新后重试。');return false;}
      track=result.data.track;version=result.data.catalog_version;needsReview=false;preview('bgm-cover-saved',track.cover_url);
      $('bgm-cover-title').textContent=track.name+' · 封面';$('bgm-cover-versions').textContent='封面版本：'+(track.cover_version||'无')+' · 音频版本：'+(track.media_version||'无');
      status(candidate?'已读取最新保存信息。本次候选仍未保存，可核对后保存。':'');return true;
    }catch(_){if(current===sequence){needsReview=true;status('已保存信息读取失败，请刷新后重试。');}return false;}
    finally{if(current===sequence){loading=false;sync();}}
  }
  async function open(id){
    if(busy||loading){if(!$('bgm-cover').open)$('bgm-cover').showModal();return;}
    sequence++;clearCandidate();pending=read();track={id:pending?.track_id||id};intent=null;needsReview=false;preview('bgm-cover-saved',null);sync();
    if(!$('bgm-cover').open)$('bgm-cover').showModal();
    const receipt=pending;pending=null;await refresh();pending=receipt;
    if(pending)status('有待核对的封面操作。请先查询；尚未接收文件时，可重选原文件继续。');sync();
  }
  async function prepareFile(file){
    const extension='.'+file.name.split('.').pop().toLowerCase(),types={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'};
    if(!file.size||file.size>5*1048576||!types[extension]||(file.type&&file.type!=='application/octet-stream'&&file.type!==types[extension]))throw new Error('请选择不超过5 MiB的静态JPG、PNG或WebP。');
    const url=URL.createObjectURL(file),image=new Image();
    try{
      await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('图像读取超时。')),10000);image.onload=()=>{clearTimeout(timer);resolve();};image.onerror=()=>{clearTimeout(timer);reject(new Error('图片损坏或无法预览。'));};image.src=url;});
      if(Math.max(image.naturalWidth,image.naturalHeight)>4096)throw new Error('图片长边不能超过4096像素。');
      const hash=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
      return {file,url,extension,sha:Array.from(new Uint8Array(hash),n=>n.toString(16).padStart(2,'0')).join('')};
    }catch(e){URL.revokeObjectURL(url);throw e;}
  }
  async function chooseFile(file){
    if(busy||loading||isObserver())return false;
    const run=++sequence;
    if(!file){clearCandidate(false);sync();return false;}
    let next;loading=true;sync();
    try{
      next=await prepareFile(file);
      if(run!==sequence){URL.revokeObjectURL(next.url);return false;}
      if(pending&&(pending.kind!=='upload'||pending.body.source_sha256!==next.sha||pending.body.source_size!==file.size||pending.body.extension!==next.extension))throw new Error('请重选原提交的同一文件；结果未知时不能替换内容。');
      clearCandidate(false);candidate=next;intent='upload';preview('bgm-cover-candidate',candidate.url);
      status(needsReview?'候选已保留。请先刷新已保存信息，核对冲突后再保存。':'本次仅为预览，尚未保存。服务端会验证静态格式和完整解码。');sync();return true;
    }catch(e){if(next)URL.revokeObjectURL(next.url);if(run===sequence)status(e.message||'图片校验失败，已保存封面保持不变。');sync();return false;}
    finally{if(run===sequence){loading=false;sync();}}
  }
  async function choose(){return chooseFile($('bgm-cover-file').files[0]);}
  async function openWithFile(id,file,options={}){
    // A different unresolved cover operation must be reconciled before starting another.
    if(busy||loading||isObserver())return false;
    const existing=read();
    if(existing){await open(existing.track_id);return false;}
    await open(id);
    if(track?.id!==id||!Number.isInteger(track.record_version)||needsReview)return false;
    if(!await chooseFile(file))return false;
    if(options.submit)await save({preventDefault(){}});
    return true;
  }
  async function consume(result){
    if(result?.code===0&&['succeeded','failed'].includes(result.data.state)){
      const op=result.data;
      try{localStorage.removeItem(key);}catch(_){}
      pending=null;if(op.state==='succeeded')clearCandidate();
      const wasBusy=busy;busy=false;const refreshed=await refresh();busy=wasBusy;
      needsReview=!refreshed||op.failure_category==='version_conflict';
      status(op.state==='succeeded'?(op.result?.association_removed?'封面关联已移除。':'新封面已保存。')+(op.result?.cleanup_state==='pending'?'旧文件待清理。':'')+'音频及启用状态保持不变。':
        op.failure_category==='version_conflict'?'目录或曲目已更新，本次封面未保存；候选已保留，请刷新核对后再次保存。':'本次封面处理失败；已保存封面和成功音频保持不变，无需重传音频。候选已保留，'+(refreshed?'可再次保存重试。':'请刷新已保存信息后再次保存。'));
      await reload();
    }else if([20201,20202].includes(result?.code)||Array.isArray(result?.detail)){
      try{localStorage.removeItem(key);}catch(_){}pending=null;needsReview=true;
      status('本次封面修改未保存，候选已保留。请刷新已保存信息，核对后再次保存。');
    }else status(result?.code===401||result?.code===403?'权限已中断，原操作已保留，请恢复权限后核对。':result?.code===0?'原操作仍在处理中，请稍后核对。':'结果待核对，请保留原标识，不要重新上传另一份素材。');
    sync();
  }
  async function save(event){
    event.preventDefault();if(busy||loading||needsReview||isObserver()||!Number.isInteger(track?.record_version)||(!intent&&!pending))return;
    busy=true;sync();
    try{
      if(!pending){
        const body={operation_id:crypto.randomUUID(),expected_revision:track.record_version,expected_catalog_version:version};
        if(intent==='upload')Object.assign(body,{action:'upload_cover',track_id:track.id,extension:candidate.extension,mime_type:candidate.file.type||'application/octet-stream',source_size:candidate.file.size,source_sha256:candidate.sha});
        const receipt={kind:intent,track_id:track.id,body},encoded=JSON.stringify(receipt);
        try{localStorage.setItem(key,encoded);if(localStorage.getItem(key)!==encoded)throw new Error();}catch(_){throw new Error('无法可靠保存操作标识，本次未提交。');}
        pending=receipt;
      }
      sync();status('正在保存独立封面操作…');
      if(pending.kind==='remove'){
        await consume(await adminRequest('DELETE','/api/admin/bgm/tracks/'+encodeURIComponent(pending.track_id)+'/cover',pending.body,false,opts));return;
      }
      if(!candidate)throw new Error('请重选原文件，或先核对原操作。');
      const accepted=await adminRequest('POST','/api/admin/bgm/operations',pending.body,false,opts);
      if(accepted?.code!==0||accepted.data.state!=='accepted'){await consume(accepted);return;}
      const result=await adminRequest('PUT','/api/admin/bgm/operations/'+encodeURIComponent(pending.body.operation_id)+'/content',candidate.file,true,
        {...opts,timeoutMs:Math.max(1000,Math.min(330000,new Date(accepted.data.deadline_at).getTime()-Date.now()+30000))});
      await consume(result);
    }catch(e){status(e.message||'结果待核对，请保留原操作标识。');}
    finally{busy=false;sync();}
  }
  async function check(){
    if(busy||!pending)return;busy=true;sync();
    try{
      const result=await adminRequest('GET','/api/admin/bgm/operations/'+encodeURIComponent(pending.body.operation_id),null,false,opts);
      if(result?.code===20200)status('尚未查到原操作。继续原提交会沿用同一标识和内容，不会另建素材。');else await consume(result);
    }finally{busy=false;sync();}
  }
  function init(options){
    reload=options.reload;sync();
    $('bgm-cover-close').addEventListener('click',()=>$('bgm-cover').close());
    $('bgm-cover').addEventListener('close',()=>{if(!busy){sequence++;loading=false;clearCandidate();}});
    $('bgm-cover-file').addEventListener('change',choose);$('bgm-cover-form').addEventListener('submit',save);
    $('bgm-cover-remove').addEventListener('click',()=>{if(busy||pending)return;clearCandidate();intent='remove';status('当前封面尚未移除，确认保存后使用通用黑胶。');sync();});
    $('bgm-cover-check').addEventListener('click',check);$('bgm-cover-refresh').addEventListener('click',refresh);
    $('bgm-cover-pending').addEventListener('click',()=>{const p=read();if(p)open(p.track_id);});
  }
  return {init,open,prepareFile,openWithFile};
})();

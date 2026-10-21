/* Explicit manual cleanup, with a durable original-operation receipt. */
(function () {
  'use strict';
  const key='lxm_admin_bgm_cleanup_operation',$=id=>document.getElementById(id);
  let reload,pending=null,current=null,busy=false,sequence=0,page=1,trackId=null,loading=false;
  const states={not_requested:'保留',pending:'待清理',deleting:'清理中',failed:'清理失败',deleted:'已删除'};
  const failures={cleanup_not_confirmed:'删除尚未确认',storage_unknown:'存储结果待核对',asset_ownership:'资源归属核对失败',processing_timeout:'清理超时',authorization_changed:'权限已变化'};
  function node(tag,text){const n=document.createElement(tag);n.textContent=text;return n;}
  function date(value){return value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'—';}
  function message(text){$('bgm-cleanup-status').textContent=text;}
  function receipt(){try {const r=JSON.parse(localStorage.getItem(key)||'null');return r?.body?.operation_id&&['DELETE','POST'].includes(r.method)&&/^\/api\/admin\/bgm\/tracks\/[a-f0-9-]{36}(\/cleanup-retry)?$/.test(r.path)?r:null;}catch(_){return null;}}
  function clear(){try{localStorage.removeItem(key);}catch(_){}pending=null;}
  function sync(){
    $('bgm-cleanup-pending').hidden=!pending;
    $('bgm-cleanup-check').hidden=!pending;$('bgm-cleanup-check').disabled=busy||loading;
    $('bgm-cleanup-delete').hidden=!!pending||isObserver()||!current?.can_delete;
    $('bgm-cleanup-retry').hidden=!!pending||isObserver()||!current?.can_cleanup;
    $('bgm-cleanup-delete').disabled=$('bgm-cleanup-retry').disabled=busy||loading;
    if($('bgm-cleanup-refresh'))$('bgm-cleanup-refresh').disabled=busy||loading||!!pending||!trackId;
    $('bgm-cleanup-operation').textContent=pending?'操作标识：'+pending.body.operation_id:'';
    $('bgm-assets-prev').disabled=busy||loading||!!pending||!current||page<=1;
    $('bgm-assets-next').disabled=busy||loading||!!pending||!current||page*20>=current.total;
  }
  function renderAssets(assets){
    const list=$('bgm-cleanup-assets');list.replaceChildren();
    assets.forEach(a=>list.append(node('li',(a.kind==='audio'?'音频':'封面')+' · '+a.id+' · '+(states[a.cleanup_state]||'待核对')+(a.failure_category?'（'+(failures[a.failure_category]||'清理未完成')+'）':'')+(a.not_before?' · 可清理：'+date(a.not_before):''))));
    if(!assets.length)list.append(node('li','没有已登记的专属文件。'));
  }
  async function load(id){
    trackId=id;const run=++sequence;current=null;loading=true;sync();message('正在核对服务器删除资格与资源…');
    let r;
    try{r=await adminRequest('GET','/api/admin/bgm/tracks/'+encodeURIComponent(id)+'/assets?page='+page,null,false,{silentErrorToast:true,returnAuthError:true,returnErrorResponse:true,timeoutMs:10000});}catch(_){r=null;}
    if(run!==sequence)return;loading=false;
    if(!r||r.code!==0){message('资源信息读取失败，请点击刷新资格与资源重试。');sync();return;}
    current=r.data;$('bgm-cleanup-title').textContent='资产与清理 · '+current.name;
    $('bgm-cleanup-times').textContent='北京时间（UTC+8）｜服务器当前：'+date(current.server_time)+'；最近隐藏：'+date(current.hidden_at)+'；可删除：'+date(current.deletable_at);
    $('bgm-assets-page').textContent='第 '+page+' 页，共 '+current.total+' 个专属资源';renderAssets(current.list);
    message(current.audio_state==='deleted'?'曲目已删除，保留操作与资源核对记录。':current.can_delete?'确认后删除曲目及其全部专属音频、当前与旧封面。此操作不可恢复。':current.can_cleanup?'可手动清理剩余资源；正在使用的音频与封面会保留。':'当前不可删除或清理。已启用、等待期未满或有活动处理时服务端会拒绝。');sync();
  }
  async function open(id){
    if(busy)return;pending=receipt();trackId=pending?pending.path.split('/')[5]:id;page=1;
    if(!$('bgm-cleanup').open)$('bgm-cleanup').showModal();
    $('bgm-cleanup-replay').hidden=true;
    if(pending){current=null;$('bgm-cleanup-times').textContent='';$('bgm-assets-page').textContent='';$('bgm-cleanup-assets').replaceChildren(node('li','分项结果尚待核对。'));message('有待核对的原操作，请先查询结果。');sync();return;}
    await load(trackId);
  }
  async function consume(r){
    if(r?.code===0&&r.data){
      const op=r.data;
      if(Array.isArray(op.result?.assets))renderAssets(op.result.assets);
      if(['succeeded','failed'].includes(op.state)){
        trackId=op.track_id||trackId;clear();current=null;$('bgm-cleanup-replay').hidden=true;
        message(op.state==='succeeded'?(op.result?.track_deleted?'曲目及全部专属资源已删除。':'本次可清理资源已清理，当前音乐及封面保持不变。'):'清理未全部完成，已成功的对象不会重复删除。请刷新资格与资源，核对剩余对象后手动重试。');
        await reload();
      }else message('操作仍在处理中，请保留原标识并稍后核对；不会新建重复删除。');
    }else if([20200,20201,20202,20205,422].includes(r?.code)||Array.isArray(r?.detail)){
      clear();current=null;$('bgm-cleanup-replay').hidden=true;message('本次未接纳：'+(r.message||'曲目状态、版本或处理容量已变化')+'。请刷新资格与资源后重新决定。');await reload();
    }else message(r?.code===401||r?.code===403?'权限已中断，原操作标识已保留，恢复权限后先核对。':'结果待核对，原操作标识已保留。请先查询，不要重复删除。');
    sync();
  }
  async function submit(action){
    if(busy||loading||pending||!current||isObserver()||(action==='delete'?!current.can_delete:!current.can_cleanup))return;
    const r={method:action==='delete'?'DELETE':'POST',path:'/api/admin/bgm/tracks/'+current.track_id+(action==='delete'?'':'/cleanup-retry'),
      body:{operation_id:crypto.randomUUID(),expected_revision:current.record_version,expected_catalog_version:current.catalog_version}};
    try{const encoded=JSON.stringify(r);localStorage.setItem(key,encoded);if(localStorage.getItem(key)!==encoded)throw Error();}
    catch(_){message('无法可靠保存操作标识，本次尚未提交。请恢复浏览器存储后重试。');return;}
    pending=r;await send();
  }
  async function send(){
    if(busy||!pending||isObserver())return;busy=true;sync();message('正在逐项清理，请保留原操作标识…');$('bgm-cleanup-replay').hidden=true;
    try{await consume(await adminRequest(pending.method,pending.path,pending.body,false,{silentErrorToast:true,returnAuthError:true,returnErrorResponse:true,timeoutMs:200000}));}
    finally{busy=false;sync();}
  }
  async function check(){
    if(busy||!pending)return;busy=true;sync();
    try{
      const r=await adminRequest('GET','/api/admin/bgm/operations/'+encodeURIComponent(pending.body.operation_id),null,false,{silentErrorToast:true,returnAuthError:true,returnErrorResponse:true,timeoutMs:10000});
      if(r?.code===20200){message('尚未查到原操作；可继续核对，或原标识原内容重发。');$('bgm-cleanup-replay').hidden=isObserver();}
      else await consume(r);
    }finally{busy=false;sync();}
  }
  function actions(track,container){const b=node('button','资产与清理');b.className='btn';b.type='button';b.addEventListener('click',()=>open(track.id));container.append(b);}
  function init(options){
    reload=options.reload;pending=receipt();sync();
    $('bgm-cleanup-pending').addEventListener('click',()=>open(''));
    $('bgm-cleanup-close').addEventListener('click',()=>$('bgm-cleanup').close());
    $('bgm-cleanup').addEventListener('close',()=>{sequence++;loading=false;});
    $('bgm-cleanup-refresh')?.addEventListener('click',()=>{if(!busy&&!loading&&!pending&&trackId){page=1;return load(trackId);}});
    $('bgm-cleanup-delete').addEventListener('click',()=>submit('delete'));
    $('bgm-cleanup-retry').addEventListener('click',()=>submit('retry'));
    $('bgm-cleanup-check').addEventListener('click',check);$('bgm-cleanup-replay').addEventListener('click',send);
    for(const [id,delta] of [['bgm-assets-prev',-1],['bgm-assets-next',1]])$(id).addEventListener('click',()=>{if(!busy&&!loading&&!pending&&current){const tid=current.track_id;page+=delta;load(tid);}});
  }
  window.BgmCleanupUI={init,actions,open};
})();

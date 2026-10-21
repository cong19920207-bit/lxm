/* Atomic catalog edits. The saved receipt survives response loss and refresh. */
(function () {
  'use strict';
  const key='lxm_admin_bgm_directory_operation', $=id=>document.getElementById(id);
  let reload, busy=false, context=null, pending=null, sequence=0;
  const names={rename:'修改名称',enable:'启用音乐',hide:'隐藏音乐',set_default:'设为默认',reorder:'调整歌单顺序'};
  function node(tag,text,cls) { const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n; }
  function message(text) { $('bgm-edit-status').textContent=text; }
  function readReceipt() { try { const value=JSON.parse(localStorage.getItem(key)||'null');return value?.body?.operation_id&&['PATCH','PUT'].includes(value.method)?value:null; } catch (_) { return null; } }
  function sync() {
    $('bgm-directory-pending').hidden=!pending;
    $('bgm-edit-submit').hidden=!!pending||!context;
    $('bgm-edit-submit').disabled=busy;
    $('bgm-edit-check').hidden=!pending;
    $('bgm-edit-check').disabled=busy;
    $('bgm-edit-operation').textContent=pending?'操作标识：'+pending.body.operation_id:'';
  }
  function clearReceipt() { try { localStorage.removeItem(key); } catch (_) { /* A surviving receipt only queries/replays the original ID. */ } pending=null; }
  function openShell(title) {
    $('bgm-edit-title').textContent=title;$('bgm-edit-fields').replaceChildren();message('');
    if(!$('bgm-edit').open)$('bgm-edit').showModal();sync();
  }
  function openPending() { sequence++;context=null;pending=readReceipt()||pending;openShell('核对歌单操作');message('请核对原操作结果。确认前不会重新提交其他修改。');sync(); }
  async function order() {
    const r=await adminRequest('GET','/api/admin/bgm/order',null,false,{silentErrorToast:true,timeoutMs:8000});
    if(!r||r.code!==0)throw new Error('歌单读取失败，请关闭后刷新重试。');return r.data;
  }
  async function open(track, action, version) {
    if(busy||isObserver())return;
    pending=readReceipt();if(pending)return openPending();
    const run=++sequence;context=null;openShell(names[action]);
    const fields=$('bgm-edit-fields');fields.append(node('p',track.name));
    const next={method:'PATCH',path:'/api/admin/bgm/tracks/'+encodeURIComponent(track.id),body:{action,expected_catalog_version:version,expected_revision:track.record_version}};
    if(action==='rename'){
      const label=node('label','音乐名称'),input=node('input');input.id='bgm-edit-name';input.value=track.name;input.required=true;label.append(input);fields.append(label);
    }else if(action==='hide'){
      message('正在核对完整歌单…');
      try {
        const current=await order();if(run!==sequence||!$('bgm-edit').open)return;
        if(current.catalog_version!==version)throw new Error('目录已更新，请关闭并刷新列表后重新选择。');
        const alternatives=current.tracks.filter(t=>t.id!==track.id);
        if(current.default_track_id===track.id&&alternatives.length){
          const label=node('label','请选择替代默认音乐'),select=node('select');select.id='bgm-edit-replacement';select.required=true;
          const empty=node('option','请选择');empty.value='';select.append(empty);
          alternatives.forEach(t=>{const o=node('option',t.name+' · '+t.id.slice(0,8));o.value=t.id;select.append(o);});
          label.append(select);fields.append(label,node('p','隐藏与默认替换将同时保存。'));
        }else fields.append(node('p',alternatives.length?'隐藏后保留素材，可重新启用。':'这是最后一首音乐，隐藏后歌单和默认音乐将清空。'));
        message('');
      }catch(e){if(run===sequence){message(e.message);sync();}return;}
    }else fields.append(node('p',action==='enable'?'试听后确认启用，音乐将进入公共歌单。':'确认将此音乐设为歌单默认曲。'));
    if(run!==sequence)return;
    context=next;$('bgm-edit-submit').textContent=action==='enable'?'已试听，确认启用':action==='hide'?'确认隐藏':'保存';sync();
  }
  function renderOrder() {
    const list=$('bgm-edit-order');list.replaceChildren();
    context.tracks.forEach((track,index)=>{
      const li=node('li'),title=node('span',(index+1)+'. '+track.name+(track.id===context.defaultId?' · 默认':''));li.append(title);
      for(const [label,delta] of [['上移',-1],['下移',1]]){
        const b=node('button',label,'btn');b.type='button';b.disabled=index+delta<0||index+delta>=context.tracks.length;
        b.addEventListener('click',()=>{if(busy||pending)return;[context.tracks[index],context.tracks[index+delta]]=[context.tracks[index+delta],context.tracks[index]];renderOrder();});li.append(b);
      }
      list.append(li);
    });
  }
  async function openOrder() {
    if(busy||isObserver())return;
    pending=readReceipt();if(pending)return openPending();
    const run=++sequence;context=null;openShell(names.reorder);message('正在读取完整歌单…');
    try {
      const current=await order();if(run!==sequence||!$('bgm-edit').open)return;
      context={method:'PUT',path:'/api/admin/bgm/order',body:{expected_catalog_version:current.catalog_version},tracks:current.tracks,defaultId:current.default_track_id};
      const list=node('ol');list.id='bgm-edit-order';$('bgm-edit-fields').append(node('p','调整全部已启用音乐的顺序，点击保存后统一生效。'),list);
      renderOrder();message(current.tracks.length?'':'歌单暂无已启用音乐。');$('bgm-edit-submit').textContent='保存完整顺序';sync();
    }catch(e){if(run===sequence)message(e.message);}
  }
  // A row arrow always edits the complete server playlist, never the visible page.
  async function move(track, delta, version) {
    if(busy||isObserver())return;
    pending=readReceipt();if(pending)return openPending();
    const run=++sequence;context=null;openShell('调整歌单顺序');message('正在读取完整歌单…');
    busy=true;sync();
    try {
      const current=await order();if(run!==sequence||!$('bgm-edit').open)return;
      if(current.catalog_version!==version)throw new Error('目录已更新，本次未保存。请关闭并刷新列表后重新选择。');
      const index=current.tracks.findIndex(t=>t.id===track.id),next=index+delta;
      if(index<0||next<0||next>=current.tracks.length)throw new Error('曲目位置已变化，请关闭并刷新列表。');
      [current.tracks[index],current.tracks[next]]=[current.tracks[next],current.tracks[index]];
      context={method:'PUT',path:'/api/admin/bgm/order',body:{expected_catalog_version:version},tracks:current.tracks,defaultId:current.default_track_id};
      busy=false;
      await submit({preventDefault(){}});
      if(!pending&&!context&&$('bgm-edit-status').textContent.startsWith('已保存'))$('bgm-edit').close();
    }catch(e){message(e.message||'顺序未保存，请刷新后重试。');}
    finally{busy=false;sync();}
  }
  async function consume(result) {
    if(result?.code===0&&result.data?.state==='succeeded'){
      const version=result.data.result?.catalog_version;clearReceipt();context=null;
      message('已保存'+(version!=null?' · 目录版本 '+version:'')+'。');await reload();
    }else if(result?.code===0&&result.data?.state==='failed'){
      clearReceipt();context=null;message('原操作已明确失败。请关闭并刷新后重新选择。');await reload();
    }else if([20201,20202].includes(result?.code)||result?.code===422||Array.isArray(result?.detail)){
      clearReceipt();context=null;message(result.code===20202?'目录或曲目已更新，本次未保存。请关闭并刷新后重新选择。':'本次修改被拒绝，请关闭并核对最新曲目状态。');await reload();
    }else message(result?.code===401||result?.code===403?'权限已中断，原操作标识已保留。恢复权限后请核对。':'结果待核对。原操作标识已保留，请先核对，勿重复修改。');
    sync();
  }
  async function submit(event) {
    event.preventDefault();if(busy||pending||!context||isObserver())return;
    const snapshot=structuredClone(context.body);
    if(snapshot.action==='rename'){
      const raw=$('bgm-edit-name').value,name=raw.trim();
      if(!name||[...name].length>60||/[\p{Cc}\p{Cs}]/u.test(raw)){message('名称须为1～60个Unicode码点，不能含控制字符。');return;}snapshot.name=name;
    }
    if($('bgm-edit-replacement'))snapshot.replacement_default_id=$('bgm-edit-replacement').value;
    if(context.tracks)snapshot.track_ids=context.tracks.map(t=>t.id);
    snapshot.operation_id=crypto.randomUUID();
    const receipt={method:context.method,path:context.path,body:snapshot};
    try {const value=JSON.stringify(receipt);localStorage.setItem(key,value);if(localStorage.getItem(key)!==value)throw new Error();}
    catch(_){message('无法可靠保存操作标识，本次尚未提交。请检查浏览器存储后重试。');return;}
    pending=receipt;busy=true;sync();message('正在保存…');
    try {await consume(await adminRequest(receipt.method,receipt.path,receipt.body,false,{silentErrorToast:true,returnAuthError:true,returnErrorResponse:true,timeoutMs:30000}));}
    finally {busy=false;sync();}
  }
  async function check() {
    if(busy||!pending)return;busy=true;sync();
    try {
      const result=await adminRequest('GET','/api/admin/bgm/operations/'+encodeURIComponent(pending.body.operation_id),null,false,{silentErrorToast:true,returnAuthError:true,returnErrorResponse:true,timeoutMs:30000});
      if(result?.code===20200){
        message('尚未查询到原操作；可继续核对，或用原标识和原内容重发。');$('bgm-edit-replay').hidden=false;
      }else await consume(result);
    }finally{busy=false;sync();}
  }
  async function replay() {
    if(busy||!pending||isObserver())return;busy=true;sync();$('bgm-edit-replay').hidden=true;
    try{await consume(await adminRequest(pending.method,pending.path,pending.body,false,{silentErrorToast:true,returnAuthError:true,returnErrorResponse:true,timeoutMs:30000}));}
    finally{busy=false;sync();}
  }
  function actions(track,container,version) {
    if(isObserver())return;
    for(const action of ['rename',track.enabled?'hide':'enable',...(track.enabled&&!track.is_default?['set_default']:[])]){
      const b=node('button',names[action],'btn');b.type='button';b.dataset.action=action;b.dataset.writeAction='';
      b.disabled=['deleting','delete_failed'].includes(track.audio_state)||(action==='enable'&&(track.audio_state!=='ready'||!track.audio_url));
      if(b.disabled)b.title='当前素材不可执行此操作，请核对处理或资源状态。';
      b.addEventListener('click',()=>open(track,action,version));container.append(b);
    }
  }
  function init(options) {
    reload=options.reload;pending=readReceipt();sync();
    $('bgm-order-open').addEventListener('click',openOrder);$('bgm-directory-pending').addEventListener('click',openPending);
    $('bgm-edit-close').addEventListener('click',()=>{sequence++;$('bgm-edit').close();});
    $('bgm-edit').addEventListener('close',()=>{sequence++;$('bgm-edit-replay').hidden=true;});
    $('bgm-edit-form').addEventListener('submit',submit);$('bgm-edit-check').addEventListener('click',check);$('bgm-edit-replay').addEventListener('click',replay);
  }
  window.BgmDirectoryUI={init,actions,open,move};
})();

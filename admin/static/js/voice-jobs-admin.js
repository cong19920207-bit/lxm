(function(){
  'use strict';
  if(!checkAdminLogin())return;
  if(!['super_admin','tech_ops'].includes(getAdminRole())){location.replace('error.html?type=403');return;}
  const $=id=>document.getElementById(id);
  $('sidebar-mount').innerHTML=renderSidebar('voice-jobs');$('header-mount').innerHTML=renderHeader('语音任务');
  let generation=0,cursor=null,selection=null;
  const statusClass=value=>['success','completed'].includes(String(value))?'tag-success':
    ['failed','cancelled'].includes(String(value))?'tag-error':
    ['pending','processing'].includes(String(value))?'tag-warning':'tag-default';
  async function load(more=false){const token=++generation;
    if(!more){selection={call:$('job-call').value.trim(),kind:$('job-kind').value};cursor=null;$('job-rows').replaceChildren();}
    if(!selection.call)return;$('job-status').textContent='加载中…';$('job-more').disabled=true;
    try{const result=await adminRequest('GET','/api/admin/voice/calls/'+encodeURIComponent(selection.call)+'/jobs?kind='+selection.kind+(cursor?'&after='+cursor:''));
      if(token!==generation)return;if(!result||result.code!==0)throw Error('查询失败，请核对通话标识和权限');
      result.data.items.forEach(item=>{const row=document.createElement('tr');['id','job_type','status','attempt_count','fail_reason','next_retry_at'].forEach(k=>{const cell=document.createElement('td');
        if(k==='status'){const tag=document.createElement('span');tag.className='tag '+statusClass(item[k]);tag.textContent=item[k]??'—';cell.append(tag);}else cell.textContent=item[k]??'—';row.append(cell);});
        const actions=document.createElement('td');if(item.retry_path){const button=document.createElement('button');button.className='btn btn-link';button.textContent='补跑一次';button.onclick=async()=>{button.disabled=true;
          try{const r=await adminRequest('POST','/api/admin/voice'+item.retry_path);if(!r||r.code!==0)throw Error('该任务当前不能补跑，请刷新状态');await load();}
          catch(e){$('job-status').textContent=e.message;button.disabled=false;}};actions.append(button);}row.append(actions);$('job-rows').append(row);});
      if(!more&&!result.data.items.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=7;cell.className='voice-empty';cell.textContent='暂无任务';row.append(cell);$('job-rows').append(row);}
      cursor=result.data.next_after;$('job-more').disabled=!cursor;$('job-status').textContent=result.data.items.length?'已更新任务状态':'暂无任务';
    }catch(e){if(token===generation)$('job-status').textContent=e.message;}}
  $('job-query').onsubmit=e=>{e.preventDefault();load();};$('job-more').onclick=()=>load(true);
  window.addEventListener('pagehide',()=>{generation++;$('job-rows').replaceChildren();});
})();

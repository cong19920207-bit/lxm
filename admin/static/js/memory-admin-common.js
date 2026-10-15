/* Shared read-only pagers: every refresh owns a sequence and a bounded GET. */
(function () {
  'use strict';
  function el(tag, text, cls) { var n=document.createElement(tag); if(text!=null)n.textContent=String(text); if(cls)n.className=cls; return n; }
  function button(text, fn, write) { var b=el('button',text,'btn btn-default'); b.type='button';b.onclick=fn;if(write)b.setAttribute('data-write-action','');return b; }
  function text(v) { return v == null ? '未提供' : typeof v==='object' ? JSON.stringify(v,null,2) : String(v); }
  function fields(box, values) { box.replaceChildren();Object.keys(values).forEach(function(k){var row=el('div',null,'ma-field');row.append(el('strong',k+'：'));if(values[k]!==null&&typeof values[k]==='object'){var detail=el('details'),summary=el('summary','展开查看');detail.append(summary,el('pre',text(values[k]),'ma-text'));row.append(detail);}else row.append(el('span',text(values[k])));box.append(row);}); }
  async function request(method,path,body) { return adminRequest(method,path,body||null,false,{silentErrorToast:true,returnErrorResponse:true,timeoutMs:5000}); }
  async function calibrate() {var r=await request('GET','/api/admin/memory-diagnostics?page=1&page_size=1');var now=r&&r.code===0&&r.data&&Date.parse(r.data.server_time);return typeof now==='number'&&Number.isFinite(now)?{server:now,received:performance.now()}:null;}
  function error(r) { return r ? text(r.message||r.detail||('错误 '+r.code)) : '网络或权限不可用'; }
  function uuid7(now) {var bytes=crypto.getRandomValues(new Uint8Array(16));for(var i=5;i>=0;i--){bytes[i]=now%256;now=Math.floor(now/256);}bytes[6]=(bytes[6]&15)|112;bytes[8]=(bytes[8]&63)|128;var h=Array.from(bytes).map(function(b){return b.toString(16).padStart(2,'0');}).join('');return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);}
  function pager(root, path, render, filters) {
    var page=1,size=20,sequence=0,previous=false,key='',busy=false;
    var state=el('p','加载中…','ma-status'),list=el('div',null,'ma-list'),controls=el('div',null,'ma-controls');
    var label=el('span'),prev=button('上一页',function(){page--;load();}),next=button('下一页',function(){page++;load();});
    var select=el('select');select.setAttribute('aria-label','每页条数');[1,20,100].forEach(function(n){var o=el('option',n+'条/页');o.value=n;o.selected=n===20;select.append(o);});select.onchange=function(){size=Number(select.value);page=1;load();};
    controls.append(prev,label,next,select,button('只读刷新',function(){load();}));root.replaceChildren(state,list,controls);
    var total=0;
    async function load(reset) {
      if(reset)page=1;var seq=++sequence,params=Object.assign({},filters?filters():{}, {page:page,page_size:size});
      var url=typeof path==='function'?path():path,filterKey=url+'?'+JSON.stringify(filters?filters():{});
      if(filterKey!==key){previous=false;list.replaceChildren();key=filterKey;}busy=true;state.textContent='加载中…';prev.disabled=true;next.disabled=true;
      var r=await request('GET',url+'?'+new URLSearchParams(params));if(seq!==sequence)return;
      busy=false;
      if(!r||r.code!==0||!r.data){state.textContent=(previous?'更新失败，以下为上次结果：':'加载失败：')+error(r);prev.disabled=page<=1;next.disabled=true;return;}
      total=r.data.total;list.replaceChildren();r.data.list.forEach(function(item){var row=render(item);row.dataset.itemId=item.id;list.append(row);});
      previous=true;state.textContent=r.data.list.length?'共 '+total+' 项':'本页无记录（总数 '+total+'）';label.textContent='第 '+page+' 页 / '+Math.max(1,Math.ceil(total/size))+' 页';prev.disabled=page<=1;next.disabled=page*size>=total;
      root.dataset.total=total;root.dataset.page=page;root.dataset.size=size;root.dataset.loadedSequence=seq;
    }
    return {load:load,invalidate:function(){sequence++;previous=false;list.replaceChildren();state.textContent='';},get busy(){return busy;}};
  }
  function formValues(form) {var out={};new FormData(form).forEach(function(v,k){if(v)out[k]=v;});return out;}
  function start(key,title) {if(!checkAdminLogin())return false;if(!['super_admin','ai_trainer','observer'].includes(getAdminRole())){location.href='/admin/pages/error.html?type=403';return false;}document.getElementById('sidebar-mount').innerHTML=renderSidebar(key);document.getElementById('header-mount').innerHTML=renderHeader(title);return true;}
  window.MemoryAdmin={el:el,button:button,text:text,fields:fields,request:request,calibrate:calibrate,error:error,uuid7:uuid7,pager:pager,formValues:formValues,start:start,write:function(){return ['super_admin','ai_trainer'].includes(getAdminRole());}};
})();

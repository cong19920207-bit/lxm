(function () {
  'use strict';
  const M=MemoryAdmin, base='/api/admin/prompt/memory-router';
  const el=id=>document.getElementById('router-'+id);
  const status=message=>{el('status').textContent=message;};
  const key=()=> 'router_publication:'+getAdminUsername();
  let active,draft,clock,loaded=false,busy=false,page=1,sequence=0;
  const modelLabel=id=>id==='deepseek-flash'?'DeepSeek Flash':'豆包 Lite';
  const thinkingLabel=enabled=>enabled?'思考开启':'思考关闭';
  const sameConfig=(a,b)=>Boolean(a&&b)&&Object.keys({...a,...b}).every(k=>
    k==='thinking_enabled'?Boolean(a[k])===Boolean(b[k]):a[k]===b[k]);
  function editor(config) {
    el('model-profile').value=config.model_profile_id;
    el('thinking').checked=Boolean(config.thinking_enabled);
    el('enabled').checked=config.enabled;
    el('timeout').value=config.timeout_ms;
    el('prompt').value=config.prompt;
  }
  function formValue() {
    const base=draft?.config||active.config;
    const config={...base,model_profile_id:el('model-profile').value,enabled:el('enabled').checked,
      timeout_ms:Number(el('timeout').value),prompt:el('prompt').value};
    if(el('thinking').checked||'thinking_enabled' in base)config.thinking_enabled=el('thinking').checked;
    return config;
  }
  function controls() {
    const write=M.write();
    el('writes').hidden=!write;
    el('testing').hidden=!write;
    el('disable-panel').hidden=!write;
    el('editor').disabled=!write||busy||!loaded;
    el('model-editor').disabled=el('editor').disabled;
    for(const group of ['writes','testing','disable-panel'])
      Array.from(el(group).querySelectorAll('button,select')).forEach(n=>{n.disabled=!write||busy||!loaded;});
    const value=formValueSafe(),same=config=>sameConfig(value,config);
    const dirty=loaded&&!same(draft?.config||active?.config);
    el('publish').disabled=!write||busy||!loaded||!draft?.config||!same(draft.config);
    el('discard').disabled=!write||busy||!loaded||(!draft?.config&&same(active?.config));
    el('disable').disabled=!write||busy||!loaded||!active?.config.enabled;
    el('refresh').disabled=busy;
    el('test-source').querySelector('[value="draft"]').disabled=!draft?.config;
    if(!draft?.config)el('test-source').value='active';
    el('receipt').hidden=!write||!sessionStorage.getItem(key());
    const count=Array.from(el('prompt').value).length;
    el('count').textContent=count.toLocaleString('en-US')+' / 20,000 字符';
    el('count').dataset.invalid=count>20000?'true':'false';
    el('edit-state').textContent=!loaded?'未读取配置':!write?'只读查看':dirty?'有未保存修改':draft?.config?'已保存草稿':'与生效配置一致';
    el('edit-state').dataset.state=dirty?'dirty':draft?.config?'saved':'default';
    if(loaded)el('model-state').textContent=(dirty?'未保存':draft?.config?'已保存草稿':'当前配置')+' · '+
      modelLabel(value.model_profile_id)+' · '+thinkingLabel(value.thinking_enabled)+(dirty||draft?.config?'，发布后生效。':'');
  }
  function formValueSafe(){return active?formValue():null;}
  function describe(r) {
    if(Array.isArray(r?.detail))return r.detail.map(x=>x.msg).join('；');
    if(typeof r?.detail==='string')return r.detail;
    return r?.message||'请求结果待核实';
  }
  async function load(preserve=false) {
    const seq=++sequence;
    const [a,d]=await Promise.all([M.request('GET',base),M.request('GET',base+'/draft')]);
    if(seq!==sequence)return;
    if(a?.code!==0||d?.code!==0||a.data.revision!==d.data.revision) {
      loaded=false;controls();status('配置读取失败或版本正在变更，请重新读取');return;
    }
    active=a.data;draft=d.data;loaded=true;
    clock={server:Date.parse(active.server_time),received:performance.now()};
    el('active').textContent='生效版本 '+active.version+' · '+(active.source==='default'?'系统默认配置':'已发布配置');
    el('state').textContent=active.config.enabled?'已启用':'已关闭';
    el('state').dataset.state=active.config.enabled?'enabled':'disabled';
    el('model').textContent=modelLabel(active.config.model_profile_id);
    el('thinking-summary').textContent=active.thinking_enabled?'已开启':'已关闭';
    el('window').textContent='最近 '+active.history_round_limit+' 轮对话';
    el('timeout-summary').textContent=(active.config.timeout_ms/1000)+' 秒 · 不重试';
    el('draft').replaceChildren();
    if(draft.config){
      const labels={enabled:'启用状态',timeout_ms:'判定超时',prompt:'任务说明与案例',model_profile_id:'判定模型',thinking_enabled:'思考模式'};
      const changes=Object.keys(labels).filter(k=>!sameConfig({[k]:draft.config[k]},{[k]:active.config[k]})).map(k=>labels[k]);
      el('draft').append(M.el('span','已保存草稿 · '+(changes.length?'变更：'+changes.join('、'):'与生效配置一致')),
        M.el('small','保存于 '+date(draft.updated_at)));
    }else el('draft').textContent='暂无草稿 · 可编辑下方配置，保存后再发布。';
    el('fixed').replaceChildren();
    for(const [name,value] of Object.entries({'配置来源':active.source,'修订号':active.revision,'配置摘要':active.config_digest,'草稿摘要':draft.draft_digest||'暂无草稿','调用模型':active.effective_model,'行为策略':active.config.behavior_profile_id,'重试次数':active.config.max_retries,'历史时区':active.history_timezone}))
      el('fixed').append(M.el('dt',name),M.el('dd',value));
    el('rules').textContent=active.fixed_rules+'\n'+JSON.stringify(active.output_schema);
    if(!preserve)editor(draft.config||active.config);
    controls(); await history();
  }
  function date(value) {
    if(!value)return '时间未提供';
    const parsed=new Date(value);
    return Number.isNaN(parsed.getTime())?value:parsed.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（上海）';
  }
  function link(label,target) {const a=M.el('a',label);a.href=target;return a;}
  async function history() {
    const current=page,r=await M.request('GET',base+'/history?page_size=10&page='+page);
    if(page!==current)return;
    const box=el('history');box.replaceChildren();
    if(r?.code!==0){box.textContent=describe(r);el('prev').disabled=true;el('next').disabled=true;return;}
    for(const v of r.data.list ?? r.data.items){
      const row=M.el('div',null,'router-history-row'),info=M.el('div');
      const view=M.button('版本 '+v.version,()=>version(v.version));view.classList.add('router-version-link');
      info.append(view);
      if(v.is_active){const badge=M.el('span','当前生效','router-badge');badge.dataset.state='enabled';info.append(badge);}
      info.append(M.el('time',date(v.updated_at)));
      const open=M.button('查看配置',()=>version(v.version));
      row.append(info,open);box.append(row);
    }
    if(!r.data.total){const empty=M.el('div','尚无已发布版本','router-history-empty');empty.append(M.el('small','发布第一份草稿后，可在这里查看与回滚。'));box.append(empty);}
    el('history-count').textContent='共 '+r.data.total+' 个版本';
    el('page-label').textContent='第 '+page+' / '+Math.max(1,Math.ceil(r.data.total/10))+' 页';
    el('prev').disabled=page<=1;el('next').disabled=10*page>=r.data.total;
  }
  let versionSequence=0;
  async function version(id) {
    const seq=++versionSequence,r=await M.request('GET',base+'/history/'+encodeURIComponent(id));
    if(seq!==versionSequence)return;
    const box=el('version');box.replaceChildren();
    if(r?.code!==0){box.textContent=describe(r);return;}
    const v=r.data;box.append(M.el('h4','历史版本 '+id),M.el('p',(v.config.enabled?'已启用':'已关闭')+' · '+modelLabel(v.config.model_profile_id)+' · '+thinkingLabel(v.config.thinking_enabled)+' · 判定超时 '+v.config.timeout_ms+' 毫秒 · '+date(v.updated_at)),M.el('p','配置摘要：'+v.config_digest),M.el('pre',v.config.prompt),
      link('查看此版本线上记录','/admin/pages/memory-diagnostics.html?tab=online&version='+encodeURIComponent(id)));
    if(M.write())box.append(M.button('回滚为新版本',()=>publication('rollback',{version:id,version_digest:v.config_digest}),true));
  }
  async function edit(discard) {
    if(busy||!loaded)return;
    if(discard&&!draft.config){editor(active.config); controls(); status('已恢复当前版本'); return;}
    const body={expected_revision:active.revision,draft_digest:draft.draft_digest};
    if(!discard) {
      const value=formValue();
      if(Array.from(value.prompt).length>20000||new TextEncoder().encode(JSON.stringify({...value,enabled:false})).length>65535)
        return status('请缩短提示词：最多 20000 字符，完整配置上限 65535 UTF-8 字节。');
      body.config=value;
    }
    busy=true;controls();
    try {
      const r=await M.request(discard?'DELETE':'PUT',base+'/draft',body);
      if(r?.code!==0){status(describe(r)+'；保留本页编辑，可重新读取。');return;}
      await load();status(discard?'已恢复当前版本':'草稿已保存，可选择已保存草稿进行诊断，或发布使其生效。');
    } finally {busy=false;controls();}
  }
  async function receipt(result,id,preserve) {
    const data=result?.data,state=data?.commit_state;
    if(data?.admission_state==='not_admitted' && data.publish_id===id){
      sessionStorage.removeItem(key());
      clock={server:Date.parse(data.server_time),received:performance.now()};
      status('发布标识已过期，本次未受理。已重新校时，可再次发布。');
    } else if(state==='committed'||state==='rejected'||state==='expired'){
      sessionStorage.removeItem(key());
      const reason=data.reason==='router_credential_missing'?'该模型未配置服务端密钥，请配置后再发布。':data.reason;
      status(state==='committed'?'已发布，生效版本 '+data.committed_version:'发布未完成 · '+(reason||state));
      if(state==='committed')await load(preserve);
    } else status('发布结果待核实 · '+id+' · '+describe(result));
    controls();
  }
  async function publication(action,extra={}) {
    if(!M.write()||busy||!loaded)return;
    if(sessionStorage.getItem(key()))return status('请先核实上一笔发布回执');
    const id=M.uuid7(Math.floor(clock.server+performance.now()-clock.received));
    sessionStorage.setItem(key(),id);busy=true;controls();
    try{await receipt(await M.request('POST',base+'/'+action,{publish_id:id,expected_revision:active.revision,...extra}),id,action==='disable');}
    finally{busy=false;controls();}
  }
  el('editor').oninput=controls;
  el('model-editor').oninput=controls;
  el('refresh').onclick=()=>load();el('save').onclick=()=>edit(false);el('discard').onclick=()=>edit(true);
  el('publish').onclick=()=>publication('publish',{draft_digest:draft.draft_digest});
  el('disable').onclick=()=>publication('disable');
  el('prev').onclick=()=>{page--;history();};el('next').onclick=()=>{page++;history();};
  el('receipt').onclick=async()=>{const id=sessionStorage.getItem(key());if(id)await receipt(await M.request('GET','/api/admin/configs/publications/'+id),id,true);};
  el('test').onclick=()=>{
    const source=el('test-source').value;
    if(source==='draft'&&!draft.config)return status('请先保存要测试的草稿');
    const params=new URLSearchParams({mode:'router_only',router_config_source:source});
    if(source==='draft')params.set('draft_digest',draft.draft_digest);
    location.href='/admin/pages/memory-diagnostics.html?'+params;
  };
  window.routerConfigPanel={open:async()=>{if(!loaded)await load();const id=new URLSearchParams(location.search).get('version');if(id)await version(id);}};
  controls();
})();

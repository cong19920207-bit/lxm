(() => {
  'use strict';
  const A = window.PetAdmin;
  let dirty = false;
  window.addEventListener('beforeunload', event => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  function formFields(value, meta, onChange, readonly = false, path = []) {
    const box = A.el('div');
    for (const key of Object.keys(value)) {
      const child = meta.type === 'group' ? meta.children[key] : meta.items[key];
      const fieldPath = [...path, key].join('.');
      const v = value[key];
      const name = A.formLabel(child, key, path);
      if (v && typeof v === 'object') {
        const group = A.el('fieldset', undefined, {'data-config-group': fieldPath});
        group.append(A.el('legend', name), formFields(v, child, onChange, readonly, [...path, key]));
        box.append(group);
        continue;
      }

      const label = A.el('label', name, {class:'pet-config-field'});
      const hint = A.el('span', A.formHint(child, key, path), {class:'hint'});
      let input;
      if (child.choices) {
        input = A.el('select');
        for (const [option, title] of Object.entries(child.choices)) {
          input.append(A.el('option', title, {value: option}));
        }
      } else if (child.type === 'boolean') {
        input = A.el('input', undefined, {type:'checkbox'});
        input.checked = v;
      } else if (key === 'prompt' || path[0] === 'templates' || (typeof v === 'string' && v.length > 90)) {
        input = A.el('textarea');
      } else {
        input = A.el('input', undefined, {type: child.type === 'number' ? 'number' : 'text'});
      }
      if (child.type !== 'boolean') input.value = v ?? '';
      if (child.type === 'number') {
        input.step = 'any';
        input.required = true;
        hint.id = 'pet-field-hint-' + fieldPath;
        input.setAttribute('aria-describedby', hint.id);
      }
      input.dataset.field = fieldPath;
      input.disabled = readonly || Boolean(child.read_only) || fieldPath === 'initial_age_days';
      input.oninput = () => {
        if (child.type === 'boolean') value[key] = input.checked;
        else if (child.type === 'number') {
          value[key] = Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : null;
          const missing = value[key] === null;
          input.setAttribute('aria-invalid', String(missing));
          hint.textContent = missing ? '请输入有效数字。需要设为零时，请填写 0。' : A.formHint(child, key, path);
        } else value[key] = input.value;
        onChange();
      };
      label.append(input, hint);
      box.append(label);
    }
    return box;
  }
  A.formFields = formFields;

  A.editDomain = async (domain, box, current) => {
    const c = await A.api('/editor/' + domain);
    if (current !== A.epoch) return;
    dirty = false;
    const value = structuredClone(c.editor_value);
    let revision = c.draft_revision;
    let base = c.version;
    let validated = Boolean(c.validated);
    let editSequence = 0;
    let busy = false;
    const storage = 'pet-operation:' + domain;
    const summary = A.el('div', undefined, {class:'pet-config-summary'});
    const live = A.el('strong');
    const draftBadge = A.el('span');
    const savedMeta = A.el('p', undefined, {class:'pet-meta'});
    const meta = A.el('p', c.scope, {class:'pet-meta pet-config-scope'});
    const status = A.el('p', undefined, {role:'status'});
    const controls = A.el('div', undefined, {class:'pet-toolbar pet-editor-actions','aria-label':'草稿与发布操作'});
    const result = A.card('预览 / 校验 / 操作结果');
    result.classList.add('pet-editor-result');
    result.setAttribute('aria-live','polite');
    const tests = A.el('div', undefined, {class:'pet-test-summary'});
    const feedback = A.el('p', undefined, {class:'pet-action-feedback',role:'status'});
    summary.append(live, draftBadge, savedMeta, meta);
    if (domain === 'ai') summary.append(tests);
    box.append(summary);

    const changed = () => {
      editSequence++;
      dirty = true;
      validated = false;
      feedback.textContent = '';
      refresh();
    };
    const workflow = A.el('ol', undefined, {class:'pet-workflow','aria-label':'配置生效步骤'});
    for (const label of ['修改与预览','保存草稿','服务端校验','确认影响并发布']) workflow.append(A.el('li',label));
    const form = formFields(value, c.schema, changed, !c.editable);
    form.classList.add('pet-config-form');
    box.classList.add('pet-editor');
    box.append(workflow, status, form);

    function refresh() {
      live.textContent = `当前生效 v${base}`;
      const states = {
        none:'当前无草稿，正在查看生效配置',
        same:`草稿 D${revision} · 与生效版一致`,
        saved:`草稿 D${revision} · 已保存，未发布`,
        validated:`草稿 D${revision} · 已校验，待发布`,
        invalid:`草稿 D${revision} · 校验失败`,
        stale:`草稿 D${revision} · 基准已变化，需重新核对`
      };
      draftBadge.textContent = !c.editable ? '正在查看生效配置' : c.remote_changed ? '编辑基准已变化，请重新核对' : dirty ? '有未保存修改' : states[c.draft_state] || `草稿 D${revision} · 与生效版一致`;
      draftBadge.className = 'pet-badge ' + (dirty || c.remote_changed || ['saved','invalid','stale'].includes(c.draft_state) ? 'is-warning' : c.draft_state === 'validated' ? 'is-success' : 'is-neutral');
      savedMeta.textContent = c.editable && c.draft_state !== 'none'
        ? `基于 v${c.draft_base_version ?? base} · 最近保存 ${A.formatTime(c.updated_at)}${c.updated_by ? ' · 保存人 #' + c.updated_by : ''}`
        : '';
      const diff = A.changeDiff(c.content || {}, value);
      for (const input of form.querySelectorAll('[data-field]')) {
        const label = input.closest('label');
        const change = diff[input.dataset.field];
        label.querySelector('.pet-field-change')?.remove();
        label.classList.toggle('is-changed', Boolean(change));
        if (change) label.append(A.el('span',`生效值：${A.compactValue(change.before)} · 编辑值：${A.compactValue(change.after)}`,{class:'pet-field-change'}));
      }
      A.markConfigTabs?.(box, Object.keys(diff));
      status.className = dirty || c.remote_changed ? 'pet-dirty' : 'pet-meta';
      if (c.remote_changed) status.textContent = '请保留当前修改并重新读取配置。';
      else if (dirty) status.textContent = '有未保存修改，请保存后重新校验。';
      else if (c.validation_error) status.textContent = '校验失败：' + A.configError(c.validation_error);
      else if (!c.editable) status.textContent = '当前角色只读';
      else if (c.draft_state === 'stale') status.textContent = '生效版本发生变化，请比较差异后重新保存。';
      else status.textContent = '同一配置的各页签共同发布。';
      renderTestStatus();
    }

    function renderTestStatus() {
      tests.replaceChildren();
      if (domain !== 'ai' || !c.editable || !(c.ai_tests || []).length) return;
      tests.append(A.el('strong','草稿模型测试'));
      for (const t of c.ai_tests) {
        const label = t.passed ? '通过' : t.required ? '待测试' : '无需测试';
        tests.append(A.el('span',`${A.kind(t.workflow)} · ${label}`,{class:'pet-badge '+(t.passed?'is-success':t.required?'is-warning':'is-neutral')}));
      }
    }

    const inputs = {
      facts:[{id:'sim-touch',event_type:'touch',source:'actual_execution',participants:['player'],result:{completed:true}}],
      stage:'puppy', date:'2026-03-01T00:00:00+00:00', birth_date:'2024-02-29', pet_name:'示例小狗',
      hours:12, values:{satiety:40,energy:15,mood:60}, daily_reward_used:6, closeness:10, action:'feed',
      completed_steps:['player_pass','xiaomeng_receive','dog_response'], last_active_at:'2026-02-25T00:00:00+00:00',
      origin:'return', absence_ended:true, remaining:{offline:0,return:1,narrative:1,user:8,global:10}, reactions:[]
    };

    function assertInputs() {
      const invalid = form.querySelector('input[aria-invalid="true"]');
      if (!invalid) return;
      const tab = [...box.querySelectorAll('button[data-config-keys]')].find(button =>
        button.dataset.configKeys.split(' ').includes(invalid.dataset.field.split('.')[0]));
      tab?.click();
      invalid.focus();
      throw new Error('请先填写表单中标记的数字字段。');
    }

    const run = async (fn, view = A.fields) => {
      result.replaceChildren(A.el('h2','操作结果'), A.el('p','处理中…'));
      try {
        const data = await fn();
        if (data === undefined) result.replaceChildren();
        else result.replaceChildren(A.el('h2','操作结果'), view(data));
        return data;
      } catch (e) {
        result.replaceChildren(A.el('p', A.configError(e.message), {class:'pet-error',role:'alert'}));
        throw e;
      }
    };
    const execute = fn => async () => {
      if (busy) return;
      busy = true;
      controls.setAttribute('aria-busy','true');
      feedback.textContent = '处理中…';
      try { await run(fn); feedback.textContent = dirty ? '后续修改待保存' : '操作已完成'; }
      catch(e) { feedback.textContent = A.configError(e.message); }
      finally {
        busy = false;
        controls.removeAttribute('aria-busy');
      }
    };

    function pendingPublication() {
      const raw = sessionStorage.getItem(storage);
      if (!raw) return null;
      try { return JSON.parse(raw); }
      catch { return {operation_id:raw}; }
    }

    function requireIdleDraft() {
      if (pendingPublication()) throw new Error('请先核对待确认的发布结果。');
      if (sessionStorage.getItem('pet-history-operation:' + domain)) throw new Error('请先核对待确认的历史操作。');
    }

    const state = {
      c, value, inputs, result, run, changed, refresh, domain, assertInputs, requireIdleDraft,
      get revision() { return revision; },
      get base() { return base; },
      get editSequence() { return editSequence; },
      get busy() { return busy; },
      get dirty() { return dirty; },
      resetDirty() { dirty = false; },
      async sync() {
        const next = await A.api('/editor/' + domain);
        if (next.draft_revision !== revision || next.version !== base ||
            (!dirty && Object.keys(A.changeDiff(next.editor_value,value)).length)) {
          c.remote_changed = true;
          validated = false;
          refresh();
          return false;
        }
        if (dirty) return false;
        Object.assign(c,next);
        validated = Boolean(next.validated);
        refresh();
        return true;
      }
    };

    const preview = A.button(c.editable ? '确定性规则 / 模板预览' : '查看已发布规则预览', () => {
      run(async () => {
        assertInputs();
        const sequence = editSequence;
        const path = domain === 'ai' ? '/ai/preview' : '/preview/' + domain;
        const data = await A.api(path, c.editable ? 'POST' : 'GET',
          c.editable ? {content:structuredClone(value), inputs:structuredClone(inputs)} : null);
        if (sequence !== editSequence) throw new Error('编辑内容已变化，请重新预览。');
        return data;
      }, data => state.renderPreview ? state.renderPreview(data) : A.fields(data)).catch(() => {});
    });
    state.previewButton = preview;
    const diffButton = A.button('查看当前完整差异', () => {
      result.replaceChildren(A.el('h2','当前编辑与生效配置的完整差异'),A.renderDiff(A.changeDiff(c.content || {},value),{after:'当前编辑值',schema:c.schema}));
    });

    if (c.editable) {
      const save = A.button('保存草稿', execute(async () => {
        requireIdleDraft();
        assertInputs();
        const sequence = editSequence;
        const r = await A.api('/config/' + domain + '/draft','PUT',{
          content:structuredClone(value), expected_revision:revision, base_version:base
        });
        revision = r.draft_revision;
        Object.assign(c,r);
        c.draft_state = r.draft_state || 'saved';
        dirty = sequence !== editSequence;
        validated = !dirty && Boolean(r.validated);
        refresh();
        status.textContent = dirty
          ? `草稿 ${revision} 已保存，后续修改尚未保存。`
          : `草稿 ${revision} 已保存，尚未发布`;
        return r;
      }));
      const validate = A.button('服务端校验', execute(async () => {
        requireIdleDraft();
        assertInputs();
        if (dirty) throw new Error('请先保存当前修改');
        const sequence = editSequence;
        const targetRevision = revision;
        try {
          const r = await A.api('/config/' + domain + '/validate','POST',{revision:targetRevision});
          validated = r.valid === true && sequence === editSequence && r.revision === targetRevision;
          c.draft_state = Object.keys(A.changeDiff(c.content || {},value)).length ? 'validated' : 'same';
          c.validation_error = null;
          refresh();
          status.textContent = validated ? `草稿 ${targetRevision} 已校验；仅匹配该内容` : '已校验保存的草稿，后续修改尚未保存。';
          return r;
        } catch (e) {
          validated = false;
          c.validation_error = e.message;
          c.draft_state = 'invalid';
          refresh();
          throw e;
        }
      }));

      function acceptPublished(r, sequence) {
        if (!r || typeof r.version !== 'number' || r.version <= base) return;
        base = r.version;
        validated = false;
        c.content = r.content || c.draft || structuredClone(value);
        c.draft_state = 'same';
        c.draft_base_version = base;
        c.validation_error = null;
        c.ai_tests = [];
        if (sequence !== undefined) dirty = sequence !== editSequence;
        refresh();
        status.textContent = `已生效 v${base} · ${r.scope || c.scope}${dirty ? ' · 另有未保存修改' : ''}`;
      }

      async function sendPublication(request, sequence) {
        try {
          const r = await A.api('/config/' + domain + '/publish','POST',request);
          sessionStorage.removeItem(storage);
          acceptPublished(r,sequence);
          return r;
        } catch (e) {
          if (e.confirmed) sessionStorage.removeItem(storage);
          else status.textContent = '发布结果待核对。请查询或重试原发布请求。';
          throw e;
        }
      }

      const reason = A.el('input',undefined,{placeholder:'修改原因（必填）','aria-label':'发布原因'});
      const publish = A.button('发布已校验草稿', execute(async () => {
        requireIdleDraft();
        assertInputs();
        if (!validated || dirty) throw new Error('请保存并重新校验当前草稿');
        if (!reason.value.trim()) throw new Error('请填写原因');
        const sequence = editSequence;
        const request = {operation_id:crypto.randomUUID(), reason:reason.value.trim(), revision, base_version:base};
        const impact = await A.api('/config/' + domain + '/impact?revision=' + request.revision);
        if (impact.current_version !== undefined && impact.current_version !== request.base_version) {
          throw new Error('draft_or_base_changed');
        }
        if (impact.blocked.length) throw new Error('发布被阻塞：' + impact.blocked.map(A.configError).join('；'));
        if (sequence !== editSequence) throw new Error('编辑内容已变化，请重新保存并校验。');
        if (!await A.confirmImpact('确认发布当前草稿',impact,request.reason)) return;
        if (sequence !== editSequence) throw new Error('编辑内容已变化，请重新保存并校验。');
        sessionStorage.setItem(storage,JSON.stringify(request));
        return sendPublication(request,sequence);
      }));
      const query = A.button('查询原操作结果', execute(async () => {
        const request = pendingPublication();
        if (!request) throw new Error('没有待核对操作');
        let r;
        try {
          r = await A.api('/operations/' + encodeURIComponent(request.operation_id));
        } catch (e) {
          if (e.status !== 404 && e.message !== 'operation_not_found') throw e;
          if (request.revision === undefined) {
            sessionStorage.removeItem(storage);
            throw new Error('服务端未收到旧版发布请求，请重新核对草稿后发布。');
          }
          throw new Error('服务端尚无此操作。可重试原发布，操作标识将保持一致。');
        }
        if (r.state === 'done' || r.state === 'blocked') sessionStorage.removeItem(storage);
        if (r.state === 'done') acceptPublished(r.result);
        return r;
      }));
      const retry = A.button('重试原发布', execute(async () => {
        const request = pendingPublication();
        if (!request || request.revision === undefined) throw new Error('暂无可重试的发布请求，请先查询原操作。');
        return sendPublication(request);
      }));
      save.classList.add('btn-primary');
      for(const button of [save,validate,publish])button.dataset.primary='true';
      controls.append(reason,save,validate,publish,query,retry);
    }
    controls.prepend(preview,diffButton);
    box.append(controls,result);
    if (A.attachDraftHistory) A.attachDraftHistory(state,box,controls);
    const more = A.el('details',undefined,{class:'pet-more-actions'});
    const menu = A.el('div',undefined,{class:'pet-more-panel'});
    more.append(A.el('summary','更多操作'),menu);
    for(const button of controls.querySelectorAll('button:not([data-primary])'))menu.append(button);
    controls.append(more,feedback);
    refresh();
    return state;
  };

  A.handlers.rules = async (params,box,current) => { await A.editDomain('rules',box,current); };
  A.handlers.settings = async (params,box,current) => {
    const domain = params.domain === 'runtime' ? 'runtime' : 'appearance';
    box.append(A.sectionTabs('素材与运行分区',[
      ['appearance','固定模板与素材',{domain:'appearance'}],
      ['runtime','运行开关',{domain:'runtime'}]
    ],domain,{section:'settings'}));
    if (domain === 'runtime') {
      const guide = A.context('运行开关','管理新领养、用户互动、自动照顾和 AI 表达。开启 AI 表达需要有效的全局每日额度和并发。');
      guide.append(A.link('查看全局额度与并发',{section:'rules',group:'budget'}));
      box.append(guide);
    }
    await A.editDomain(domain,box,current);
  };
})();
/* Preview the registered rig, without mounting the user scene or any business controller. */
(()=>{const A=window.PetAdmin,edit=A.editDomain;A.editDomain=async(domain,box,current)=>{const state=await edit(domain,box,current);if(domain!=='appearance'||!state)return state;
const holder=A.card('三个阶段与已实现动作预览'),canvas=A.el('canvas');canvas.classList.add('pet-appearance-preview');const controls=A.el('div',undefined,{class:'pet-toolbar'});holder.append(canvas,controls);box.append(holder);
try{const preview=await A.api('/preview/appearance',state.c.editable?'POST':'GET',state.c.editable?{content:state.value,inputs:{}}:null);const assets=Object.fromEntries(preview.result.resources.map(r=>[r.id,r.uri]));const{createPetScene,DEFAULT_RESOURCES}=await import('/static/js/pet/scene.js');const{PageScope}=await import('/static/js/app/page-context.js');const scope=new PageScope({ownerId:'admin-appearance-preview'});window.addEventListener('pagehide',()=>scope.dispose(),{once:true});const mapping=state.value,resources={...DEFAULT_RESOURCES,room:assets[mapping.template?.scene]||DEFAULT_RESOURCES.room,puppy:assets[mapping.stages.puppy],juvenile:assets[mapping.stages.growing],adult:assets[mapping.stages.adult],rest:assets[mapping.fallback],...(mapping.actions.feed?{feeding:assets[mapping.actions.feed]}:{})};for(const[action,id]of Object.entries(mapping.actions)){const r=preview.result.resources.find(x=>x.id===id);for(const stage of r?.stages||[])resources['action:'+action+':'+(stage==='growing'?'juvenile':stage)]=r.uri;}const adapter=await createPetScene({canvas,scope,resources});for(const[stage,label]of Object.entries({puppy:'幼犬',growing:'成长期',adult:'成年'}))controls.append(A.button(label,()=>adapter.applyState({stage})));for(const[action,label]of Object.entries({idle:'待机',pet:'抚摸',feed:'喂食',play:'陪玩',delivery:'玩家递球',hand:'小梦接应',dog:'狗狗回应',welcome:'迎接'}))controls.append(A.button(label,()=>adapter.play(action)));holder.append(A.el('p','固定狗；演出预览不产生参与、奖励或记录。编辑资源后请重新打开预览。',{class:'pet-meta'}));}catch(e){holder.append(A.el('p',e.message,{class:'pet-error'}));}return state;};})();

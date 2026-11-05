(() => {
  'use strict';
  const A = window.PetAdmin;
  const scenes = {
    immediate:['即时表达与邀请','互动或邀请后，依据已保存事实生成简短表达。'],
    daily:['日总结','按业务日汇总真实陪伴记录。'],
    period:['期间摘要','归纳一段时间的经历，先检查事实覆盖范围。'],
    return:['回访回顾','用户回来时回顾离开期间的已保存经历。'],
    birthday:['生日固定文案','用固定模板表达日期纪念。']
  };
  const templateInScene = (key,scene) => {
    if (scene === 'birthday') return key === 'birthday';
    if (scene === 'return') return key.startsWith('return_') || key === 'fallback';
    if (scene === 'immediate') return !key.startsWith('return_') && key !== 'birthday';
    return key === 'fallback';
  };

  A.handlers.ai = async (params,box,current) => {
    const connection = A.el('details',undefined,{class:'pet-connection'});
    const connectionTitle = A.el('summary','模型连接');
    connection.append(connectionTitle);
    const requestStatus = A.api('/model-status');
    try {
      const data = await requestStatus;
      connectionTitle.textContent = '模型连接 · ' + (data.available ? '可用' : '待检查');
      connection.append(A.fields(data));
    } catch(e) {
      connectionTitle.textContent = '模型连接 · 读取失败';
      A.error(connection,e);
    }
    if (current !== A.epoch) return;
    const editRoles = ['super_admin','ai_trainer','tech_ops','observer'];
    if (!editRoles.includes(A.permissions.role)) {
      connection.open = true;
      box.append(connection,A.el('p','当前角色仅可查看模型连接摘要。'));
      return;
    }

    const s = await A.editDomain('ai',box,current);
    if (!s) return;
    const {input,choose,check} = A.simInput;
    const nav = A.el('nav',undefined,{class:'pet-tabs','aria-label':'AI 工作流'});
    const scenario = A.context('','');
    const history = A.button('当前场景历史与恢复',() => s.openHistory(workflow));
    const birthdayLink = A.link('维护生日日期映射',{section:'rules',group:'budget'});
    const modelArea = A.card('真实模型测试');
    const simulation = A.card('预览与测试');
    const workflowSelect = A.el('select',undefined,{'aria-label':'模型测试工作流'});
    let workflow = Object.hasOwn(scenes,params.workflow) ? params.workflow : 'immediate';
    let preset = 'touch';
    let testing = false;
    const testAllowed = A.can('model.test','debug');
    const noModel = () => workflow === 'birthday' || preset === 'budget' || !s.inputs.facts.length;
    const presetNote = A.el('p',undefined,{class:'pet-meta',role:'status'});
    const reason = A.el('input',undefined,{placeholder:'模型测试原因','aria-label':'模型测试原因'});
    const output = A.el('div',undefined,{'aria-live':'polite'});
    const key = 'pet-model-test';
    const run = A.button('发起模型模拟测试',runTest);
    const facts = A.el('div');
    const startingBudget = s.inputs.remaining.global;
    s.inputs.date = s.inputs.date.slice(0,10);

    function updateTestAvailability() {
      run.disabled = testing || noModel();
      presetNote.textContent = workflow === 'birthday' ? '生日文案使用固定模板。'
        : preset === 'budget' ? '全局剩余额度为 0，可预览回退文案。'
        : !s.inputs.facts.length ? '没有新增事实，可预览固定文案。'
        : '模板预览不消耗额度。真实测试消耗调试额度与全局额度。';
    }

    function show(scene) {
      workflow = scene;
      scenario.replaceChildren(A.el('strong',scenes[scene][0]),A.el('p',scenes[scene][1]),history);
      if (scene === 'birthday') scenario.append(birthdayLink);
      for (const button of nav.querySelectorAll('button')) button.setAttribute('aria-selected',String(button.dataset.workflow===scene));
      for (const n of box.querySelectorAll('[data-config-group^="workflows."]')) n.hidden = n.dataset.configGroup !== 'workflows.' + scene;
      for (const n of box.querySelectorAll('[data-field^="workflow_thinking."]')) n.closest('label').hidden = !n.dataset.field.endsWith('.'+scene);
      for (const n of box.querySelectorAll('[data-field^="templates."]')) n.closest('label').hidden = !templateInScene(n.dataset.field.split('.').at(-1),scene);
      for (const n of box.querySelectorAll('[data-field="thinking"]')) n.closest('label').hidden = scene === 'birthday';
      for (const n of box.querySelectorAll('[data-field="prompt"],[data-field="text_target"],[data-field="text_max"]')) n.closest('label').hidden = true;
      const workflows=box.querySelector('[data-config-group="workflows"]');
      const thinking=box.querySelector('[data-config-group="workflow_thinking"]');
      if(workflows)workflows.hidden=scene==='birthday';
      if(thinking)thinking.hidden=scene==='birthday';
      modelArea.hidden = scene === 'birthday';
      workflowSelect.value = scene === 'birthday' ? 'immediate' : scene;
      updateTestAvailability();
      s.refresh();
    }
    for (const [k,[name]] of Object.entries(scenes)) {
      const button = A.button(name,() => show(k));
      button.dataset.workflow = k;
      nav.append(button);
      if (k !== 'birthday') workflowSelect.append(A.el('option',name,{value:k}));
    }
    workflowSelect.onchange = () => show(workflowSelect.value);
    box.insertBefore(nav,box.querySelector('.pet-workflow'));
    nav.after(scenario);

    function drawFacts() {
      facts.replaceChildren();
      s.inputs.facts.forEach(f => {
        const row = A.el('div',undefined,{class:'pet-sentence pet-form-grid'});
        row.append(input('模拟事实标识',f.id,v => f.id=v),
          choose('模拟事件类型',{touch:'抚摸',feed:'喂食',play:'陪玩',joint_ball:'共同玩球',natural_growth:'自然成长'},f.event_type,v=>f.event_type=v),
          choose('模拟事实来源',{actual_execution:'实际执行',rule_settlement:'规则结算'},f.source,v=>f.source=v),
          check('事实已经完成',f.result?.completed,v=>f.result={...f.result,completed:v}));
        for (const [k,name] of Object.entries({player:'玩家参与',xiaomeng:'小梦参与'})) {
          row.append(check(name,f.participants.includes(k),on=>f.participants=on?[...f.participants,k]:f.participants.filter(x=>x!==k)));
        }
        row.append(A.button('移除模拟事实',() => {s.inputs.facts.splice(s.inputs.facts.indexOf(f),1);drawFacts();}));
        facts.append(row);
      });
      updateTestAvailability();
    }

    const options = A.el('div',undefined,{class:'pet-form-grid'});
    options.append(input('模拟宠物名',s.inputs.pet_name,v=>s.inputs.pet_name=v),
      choose('模拟宠物阶段',{puppy:'幼犬',growing:'成长期',adult:'成年'},s.inputs.stage,v=>s.inputs.stage=v),
      input('模拟日期',s.inputs.date,v=>s.inputs.date=v,'date'),
      choose('快速模拟情景',{touch:'轻抚完成',full:'吃饱后拒绝',empty:'没有新增事实',budget:'预算不足回退'},preset,v=>{
        preset = v;
        s.inputs.remaining.global = v === 'budget' ? 0 : startingBudget;
        s.inputs.facts = v === 'empty' ? [] : [{
          id:'sim-'+v,event_type:v==='full'?'feed':'touch',source:'actual_execution',participants:['player'],
          result:{completed:v!=='full',outcome:v==='full'?'refused':'completed'}
        }];
        drawFacts();
      }));
    const details = A.el('details',undefined,{class:'pet-inline-details'});
    details.append(A.el('summary','查看与编辑模拟事实'),facts,A.button('添加模拟事实',() => {
      s.inputs.facts.push({id:crypto.randomUUID(),event_type:'touch',source:'actual_execution',participants:['player'],result:{completed:true}});
      drawFacts();
    }));
    drawFacts();
    simulation.append(presetNote);
    if (s.c.editable) simulation.append(options,details);
    else simulation.append(A.el('p','当前角色使用默认示例预览已发布配置。',{class:'pet-meta'}));
    simulation.append(s.previewButton);
    s.result.before(simulation);

    s.renderPreview = data => {
      const panel = A.el('div');
      const keys = preset === 'budget' ? ['fallback'] : Object.keys(data.templates || {}).filter(k=>templateInScene(k,workflow));
      for (const k of keys) {
        const item = data.templates?.[k];
        if (item) panel.append(A.el('p',A.formLabel({},k,['templates'])+'：'+item.body,{class:'pet-preview-copy'}));
      }
      const raw = A.el('details');
      raw.append(A.el('summary','查看完整预览'),A.fields(data));
      panel.append(raw);
      return panel;
    };

    function showReceipt(receipt, matches) {
      output.replaceChildren();
      const result = receipt.result || {};
      const passed = result.valid === true && result.usage?.complete === true && result.current_draft_matches === true && matches === true;
      const grid = A.el('div',undefined,{class:'pet-test-cards'});
      for (const [title,label,ok] of [
        ['文案校验',result.valid===true?'通过':result.valid===false?'未通过':'待回执',result.valid===true],
        ['用量回执',result.usage?.complete?'完整':'待核对',result.usage?.complete],
        ['本场景发布测试',passed?'已满足':'待满足',passed]
      ]) {
        const item = A.el('div');
        item.append(A.el('strong',title),A.el('span',label,{class:'pet-badge '+(ok?'is-success':'is-warning')}));
        grid.append(item);
      }
      const raw = A.el('details');
      raw.append(A.el('summary','查看测试详情'),A.fields(receipt));
      output.append(grid,raw);
    }

    async function runTest() {
      if (testing || noModel()) return;
      const target = {revision:s.revision,base:s.base,sequence:s.editSequence,workflow,reason:reason.value.trim()};
      testing = true;
      updateTestAvailability();
      try {
        if (sessionStorage.getItem(key)) throw new Error('先查询原测试结果');
        if (s.dirty) throw new Error('请先保存当前修改');
        if (!target.reason) throw new Error('请填写测试原因');
        const inputs = structuredClone(s.inputs);
        const preview = await A.api('/ai/preview','POST',{content:structuredClone(s.value),inputs});
        const head = await A.api('/editor/ai');
        if (head.draft_revision !== target.revision || head.version !== target.base || s.editSequence !== target.sequence) {
          throw new Error('simulation_draft_changed');
        }
        const id = crypto.randomUUID();
        sessionStorage.setItem(key,id);
        const receipt = await A.api('/ai/test','POST',{
          operation_id:id,reason:target.reason,revision:target.revision,content_digest:preview.content_digest,workflow:target.workflow,inputs
        });
        if (['done','blocked'].includes(receipt.state)) sessionStorage.removeItem(key);
        showReceipt(receipt,await s.sync().catch(()=>false));
      } catch (e) {
        if (e.confirmed) sessionStorage.removeItem(key);
        output.replaceChildren(A.el('p',A.configError(e.message),{class:'pet-error',role:'alert'}));
      } finally {
        testing = false;
        updateTestAvailability();
      }
    }
    if (testAllowed) {
      modelArea.append(A.el('p','保存草稿后发起测试。配置校验与模型测试分别记录。',{class:'pet-meta'}),
        workflowSelect,reason,run,A.button('查询原测试结果',async()=>{
          try {
            const id=sessionStorage.getItem(key);
            if(!id)throw new Error('暂无待核对测试');
            const receipt=await A.api('/operations/'+encodeURIComponent(id));
            if(['done','blocked'].includes(receipt.state))sessionStorage.removeItem(key);
            showReceipt(receipt,await s.sync().catch(()=>false));
          }catch(e){output.replaceChildren(A.el('p',A.configError(e.message),{class:'pet-error'}));}
        }),output);
      s.result.before(modelArea);
    }
    box.append(connection,A.link('正式任务重试（按原资格，不作为模拟）',{section:'tasks'}));
    show(workflow);
  };

  A.workflowChangeCount = (workflow,paths) => paths.filter(path => {
    if (path === 'thinking') return workflow !== 'birthday';
    if (path.startsWith('templates.')) return templateInScene(path.split('.')[1],workflow);
    return path.startsWith('workflows.'+workflow+'.') || path === 'workflow_thinking.'+workflow;
  }).length;
})();

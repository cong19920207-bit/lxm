(() => {
'use strict';
const A = window.PetAdmin;

async function showVersion(p, box, epoch) {
  box.append(A.el('a', '返回版本来源', {href:'?' + (p.from || 'section=versions')}));
  const detail = await A.api('/versions/' + encodeURIComponent(p.id));
  if (epoch !== A.epoch) return;
  const selected = detail.version.version;
  const domain = detail.version.domain;
  const summary = A.context('版本摘要', '');
  const basis = A.el('p');
  const evidence = A.diagnostic('查看完整差异与依据', detail);

  function showCurrentVersion(version) {
    detail.current_version = version;
    summary.querySelector('p').textContent = `所选版本 v${selected} · 当前生效 v${version} · ${A.term(domain)}。完整差异与引用依据在下方展开查看。`;
    basis.textContent = `将历史 v${selected} 作为新版本发布；基准 v${version}。历史事实、成长依据、文字和用量保留。`;
  }

  showCurrentVersion(detail.current_version);
  box.append(summary, evidence);
  for (const reference of detail.references) {
    if (reference.pet_id) box.append(A.link('引用宠物 ' + reference.pet_id, {
      section:'pets', pet:reference.pet_id, at:p.at || '', from:location.search.slice(1)
    }));
    if (reference.kind === 'pet_generation_task') box.append(A.link('引用任务 ' + reference.id, {
      section:'tasks', id:reference.id, from:location.search.slice(1)
    }));
  }
  box.append(A.link('此版本操作日志', {
    section:'versions', tab:'logs', operation_id:detail.version.operation_id, at:p.at || '', from:location.search.slice(1)
  }));

  if (!A.can('config.rollback', domain)) return;
  const reason = A.el('textarea', undefined, {'aria-label':'回滚原因'});
  const out = A.card('回滚结果');
  const receipt = A.el('div', undefined, {'aria-live':'polite'});
  const key = 'pet-rollback-operation';
  out.append(receipt);

  function acceptRollback(result, response = result) {
    if (result.version > detail.current_version) {
      showCurrentVersion(result.version);
      evidence.querySelector('.pet-fields').replaceWith(A.fields(detail));
    }
    receipt.replaceChildren(
      A.el('p', `回滚成功，已生成 v${result.version}。`, {role:'status'}),
      A.fields(response)
    );
  }

  function setBusy(busy) {
    submit.disabled = query.disabled = busy;
  }

  const submit = A.button('验证并回滚为新版本', async () => {
    const message = reason.value.trim();
    setBusy(true);
    try {
      if (!message) throw Error('填写回滚原因');
      if (sessionStorage.getItem(key)) throw Error('先查询原操作结果');
      const base = detail.current_version;
      const impact = await A.api('/config/' + domain + '/rollback-preview?target_version=' + selected);
      if (impact.blocked.length) throw Error('目标版本当前不可发布：' + impact.blocked.join('；'));
      if (!await A.confirmImpact('确认将历史内容发布为新版本', impact, message)) return;
      const operation_id = crypto.randomUUID();
      sessionStorage.setItem(key, operation_id);
      const result = await A.api('/config/' + domain + '/rollback', 'POST', {
        operation_id, reason:message, target_version:selected, base_version:base
      });
      sessionStorage.removeItem(key);
      acceptRollback(result);
    } catch (e) {
      if (e.confirmed) sessionStorage.removeItem(key);
      receipt.replaceChildren(A.el('p', e.message, {class:'pet-error'}));
    } finally {
      setBusy(false);
    }
  });

  const query = A.button('查询原回滚操作', async () => {
    setBusy(true);
    try {
      const id = sessionStorage.getItem(key);
      if (!id) throw Error('暂无待查询操作');
      const operation = await A.api('/operations/' + encodeURIComponent(id));
      if (['done','blocked'].includes(operation.state)) sessionStorage.removeItem(key);
      if (operation.state === 'done' && operation.action === 'config.rollback' && operation.domain === domain) {
        acceptRollback(operation.result, operation);
      } else {
        receipt.replaceChildren(A.fields(operation));
      }
    } catch (e) {
      receipt.replaceChildren(A.el('p', e.message, {class:'pet-error'}));
    } finally {
      setBusy(false);
    }
  });
  box.append(basis, reason, submit, query, out);
}

A.handlers.versions = async (p, box, epoch) => {
if (p.id) {
  await showVersion(p, box, epoch);
  return;
}
box.append(A.sectionTabs('版本与日志视图',[['versions','配置版本',{tab:'versions',page:1,action:''}],['logs','养宠操作日志',{tab:'logs',page:1,action:''}]],p.tab==='logs'?'logs':'versions',{...p,section:'versions'}),A.context(p.tab==='logs'?'追溯一次后台操作':'比较配置的历史版本',p.tab==='logs'?'按操作者、操作类型或操作标识查询，核对执行结果；结果待核对时优先查询原操作。':'按配置域筛选历史版本，打开完整差异后核对影响范围与保护引用。回滚会将历史内容发布为新版本。'));if(p.from)box.append(A.el('a','返回日志来源',{href:'?'+p.from}));const logs=p.tab==='logs',form=A.el('form',undefined,{class:'pet-toolbar'});for(const[name,label]of [['domain','配置 / 权限域'],['version','版本号'],['admin_id','操作者标识'],['action',logs?'操作类型（config.publish / config.rollback 等）':'版本动作（publish / rollback / disable）'],['start','起始 UTC'],['end','截止 UTC'],['operation_id','操作标识'],['object_id','宠物 / 任务 / 尝试标识']]){if(logs&&name==='version'||!logs&&['operation_id','object_id'].includes(name))continue;const l=A.el('label',label);l.append(A.filterInput(name,p[name]||''));form.append(l);}form.append(A.el('button','查询版本或日志'),A.link('重置筛选',{section:'versions',tab:logs?'logs':'versions'}));form.onsubmit=e=>{e.preventDefault();location.search=new URLSearchParams({...Object.fromEntries(new FormData(form)),section:'versions',tab:logs?'logs':'versions',at:p.at||new Date().toISOString()});};box.append(form);const d=await A.api((logs?'/logs?':'/versions?')+A.query(p,['domain','version','admin_id','action','start','end','operation_id','object_id','page','page_size','at']));if(epoch!==A.epoch)return;p.at=d.at;box.append(A.meta(d));if(!d.total)box.append(A.el('p','没有符合条件的记录。'));for(const row of d.list){const card=A.card(`${A.term(row.domain)} · ${A.term(row.action)}${row.version?' · v'+row.version:''}`);if(!logs)card.append(A.el('span',row.current?'当前生效':'历史版本',{class:'pet-badge '+(row.current?'is-success':'is-neutral')}));if(row.reason)card.append(A.el('p',row.reason,{class:'pet-record-reason'}));
const time=row.effective_at||row.recorded_at;
if(time)card.append(A.el('p',A.formatTime(time),{class:'pet-meta'}));
card.append(A.diagnostic('查看标识与操作依据',row));const vid=logs?row.result?.version_id:row.id;if(vid)card.append(A.link('完整版本差异',{...p,id:vid,from:new URLSearchParams(p).toString()}));if(logs&&row.result?.task_id)card.append(A.link('关联任务',{section:'tasks',id:row.result.task_id,at:d.at,from:location.search.slice(1)}));box.append(card);}box.append(A.pager(d,p));};})();

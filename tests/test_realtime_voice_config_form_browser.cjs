const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

const config = {
  schema_version: 1,
  global: {
    enabled: false,
    maintenance_mode: false,
    maintenance_message: '语音通话暂时不可用，请稍后再试',
    soft_stop: false,
    rollout: { mode: 'allowlist', user_ids: [] },
    test_user_ids: []
  },
  persona_ref: { config_key: 'persona', version: 3, content_sha256: 'a'.repeat(64) },
  s2s: {
    provider: 'doubao',
    endpoint: 'wss://openspeech.bytedance.com/api/v3/realtime/dialogue',
    resource_id: 'volc.speech.dialog',
    model_version: '2.2.0.0',
    adapter_version: 'voice_adapter_v1',
    protocol_profile: 'doubao_dialog_v3_pcm',
    credential_ref: 'DOUBAO_S2S_ACCESS_KEY',
    credential_revision_ref: null,
    credential_configured: true,
    connect_timeout_ms: 10000,
    start_session_timeout_ms: 10000,
    max_retries: 2,
    retry_backoff_ms: [500, 1000]
  },
  voice: {
    voice_id: 'saturn_zh_female_keainvsheng_tob',
    voice_version: 'phase0-v1',
    candidates: [{ voice_id: 'saturn_zh_female_keainvsheng_tob', voice_version: 'phase0-v1', enabled: true }],
    persona_mapping: {},
    speech_rate: 0,
    loudness_rate: 0,
    expressive: false,
    tone_instruction: ''
  },
  capabilities: {},
  quota: { daily_free_seconds: 300, grace_seconds: 30, hard_limit_seconds: 3600, timezone: 'Asia/Shanghai' },
  growth: { segment_seconds: 30, points_per_segment: 5, daily_limit_points: 100, timezone: 'Asia/Shanghai' },
  concurrency: { heartbeat_interval_ms: 5000, user_lock_ttl_ms: 15000, reconnect_timeout_ms: 15000, call_ticket_ttl_ms: 30000, global_limit: 1 },
  interaction: { vad_rms_threshold: 0.015, candidate_ms: 200, sustained_ms: 600, goodbye_timeout_ms: 10000, post_playback_buffer_ms: 800, time_low_seconds: 60 },
  summary: { model: 'deepseek-chat' },
  followup: {
    summary_min_effective_seconds: 15,
    schedule: {
      timezone: 'Asia/Shanghai', jitter_min_minutes: 0, jitter_max_minutes: 20, max_delay_hours: 24,
      stages: {
        stranger: { windows: [{ start: '10:00', end: '21:00' }] },
        friend: { windows: [{ start: '09:30', end: '22:00' }] },
        intimate: { windows: [{ start: '09:00', end: '22:30' }] },
        soulmate: { windows: [{ start: '09:00', end: '23:00' }] }
      }
    }
  },
  retention: { effective_transcript_days: 180, generated_debug_days: 30, reasoning_days: 30, crisis_raw_days: 30, job_log_days: 90 }
};
const activeConfig = JSON.parse(JSON.stringify(config));
activeConfig.global.soft_stop = true;

const script = {
  schema_version: 1,
  context_pack: { voice_instruction_template: '', fallback_template_sections: ['persona', 'relationship'], persona_max_chars: 5000, dynamic_max_chars: 2000, recent_dialog_max_chars: 800, memory_max_items: 5, memory_lookback_days: 30, build_budget_ms: 3000, ready_barrier_enabled: true },
  call_answer: { prompt_template: '', failure_fallback: 'answer', min_ring_seconds: 4, max_wait_seconds: 12, fallback_delay_min_seconds: 4, fallback_delay_max_seconds: 8 },
  recall: { prompt_template: '', trigger_rules: ['上次', '你还记得'], max_query_chars: 200, top_k: 3, score_threshold: 0.7, timeout_ms: 1000, embedding_timeout_ms: 800, vector_timeout_ms: 800 },
  memory: { prompt_template: '', max_items_per_turn: 5, max_retries: 2, retry_backoff_ms: [1000, 5000] },
  summary: { prompt_template: '总结提示词' },
  barge_in: { weak_acknowledgements: ['嗯'], strong_interruptions: ['等等'], upgrade_connectors: ['但是'] },
  silence_and_exit: { exit_intent_template: '先聊到这', silence_timeout_template: '暂时听不到你', silence_confirm_seconds: 6, silence_hangup_seconds: 12, user_resume_cancels_exit: true },
  followup: { missed_explanation_template: '刚刚没接到你的电话' },
  end_reason: {
    user_hangup: '就先聊到这', user_cancel: { show_end_page: false, action: 'return_to_chat' },
    exit_intent: '先聊到这', silence_timeout: '暂时听不到你', quota_exhausted: '今天先聊到这里',
    hard_limit: '我们先休息一下', reconnect_timeout: '网络没有恢复',
    provider_error: { before_connected: '暂时无法接通', after_connected: '通话暂时中断' },
    system_error: { before_connected: '暂时无法接通', after_connected: '通话暂时中断' }
  },
  reconnect_bridge: { success_template: '刚刚好像断了一下' },
  crisis: { region: 'CN-mainland', in_call_banner: '请联系可信任的人', post_call_resource_card: '请立即拨打 110/120' }
};

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.setDefaultTimeout(5000);
    const errors = [];
    const writes = [];
    let draftRevision = 0;
    let configReadMode = 'normal';
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      sessionStorage.setItem('admin_token', 'local-test');
      sessionStorage.setItem('admin_role', 'super_admin');
    });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== 'http://voice.test') return route.abort();
      if (url.pathname.startsWith('/api/')) {
        if (url.pathname === '/api/admin/voice/master-switch') {
          return route.fulfill({ json: { code: 0, data: { enabled: true, version: 2, updated_at: '2026-09-27T00:00:00', updated_by: 'test' } } });
        }
        if (route.request().method() === 'PATCH') {
          const body = route.request().postDataJSON();
          const section = decodeURIComponent(url.pathname.split('/').pop());
          const alias = url.pathname.includes('/config/script/') ? 'script' : 'config';
          writes.push({ alias, section, body });
          (alias === 'config' ? config : script)[section] = body.content;
          draftRevision += 1;
          return route.fulfill({ json: { code: 0, data: { draft_revision: draftRevision } } });
        }
        const match = url.pathname.match(/^\/api\/admin\/voice\/config\/(config|script)$/);
        if (match) {
          if (match[1] === 'config' && configReadMode === 'unavailable') {
            return route.fulfill({ status: 503, json: { code: 503, message: '读取失败' } });
          }
          if (match[1] === 'config' && configReadMode === 'unpublished') {
            return route.fulfill({ json: { code: 0, data: { config, _meta: {
              base_version: 0, draft_revision: 1, has_draft: true, changed_sections: [], content_sha256: 'sha256:test'
            } } } });
          }
          const value = match[1] === 'config' ? config : script;
          return route.fulfill({ json: { code: 0, data: { config: value, _meta: { base_version: 1, draft_revision: draftRevision, has_draft: draftRevision > 0, changed_sections: writes.filter(item => item.alias === match[1]).map(item => item.section), content_sha256: 'sha256:test' } } } });
        }
        const historyDetail = url.pathname.match(/^\/api\/admin\/voice\/config\/(config|script)\/history\/1$/);
        if (historyDetail) {
          return route.fulfill({ json: { code: 0, data: { config: historyDetail[1] === 'config' ? activeConfig : script, version: 1, updated_at: '2026-09-27T00:00:00', updated_by: 'test' } } });
        }
        if (url.pathname.includes('/history')) return route.fulfill({ json: { code: 0, data: { list: [] } } });
        return route.fulfill({ json: { code: 0, data: { list: [], calls: [], database_count: 0, lease_count: 0 } } });
      }
      const file = url.pathname.slice(1);
      return fs.existsSync(file) ? route.fulfill({ path: file }) : route.fulfill({ status: 404, body: '' });
    });

    await page.goto('http://voice.test/admin/pages/voice-config.html');
    await page.waitForFunction(() => document.querySelector('#voice-business-form'));

    assert.match(await page.locator('#voice-section-list').innerText(), /开放与维护/);
    const sectionGroupStyle = await page.locator('.voice-section-group').first().evaluate(element => ({
      fontWeight: getComputedStyle(element).fontWeight,
      backgroundColor: getComputedStyle(element).backgroundColor,
      borderLeftWidth: getComputedStyle(element).borderLeftWidth
    }));
    assert.ok(Number(sectionGroupStyle.fontWeight) >= 700, 'configuration group headings must be visibly bold');
    assert.notEqual(sectionGroupStyle.backgroundColor, 'rgb(250, 250, 250)');
    assert.notEqual(sectionGroupStyle.borderLeftWidth, '0px');
    assert.equal(await page.locator('#voice-master-summary').innerText(), '已开启');
    await page.waitForFunction(() => document.querySelector('#voice-rollout-summary').textContent.includes('仅指定用户'));
    assert.equal(await page.locator('#voice-maintenance-summary').innerText(), '正常');
    assert.equal(await page.locator('#voice-ops-summary').innerText(), '已停止新拨打');
    assert.equal(await page.getByRole('link', { name: '前往通话运维' }).getAttribute('href'), '/admin/pages/voice-ops.html');
    activeConfig.global.soft_stop = false;
    await page.locator('#btn-voice-reload').click();
    await page.waitForFunction(() => document.querySelector('#voice-ops-summary').textContent === '正常');
    configReadMode = 'unpublished';
    await page.locator('#btn-voice-reload').click();
    await page.waitForFunction(() => document.querySelector('#voice-version-summary').textContent.startsWith('V0'));
    assert.equal(await page.locator('#voice-ops-summary').innerText(), '未发布');
    configReadMode = 'unavailable';
    await page.locator('#btn-voice-reload').click();
    await page.waitForFunction(() => document.querySelector('#voice-version-summary').textContent === '配置不可用');
    assert.equal(await page.locator('#voice-ops-summary').innerText(), '状态不可用');
    configReadMode = 'normal';
    await page.locator('#btn-voice-reload').click();
    await page.waitForFunction(() => document.querySelector('#voice-ops-summary').textContent === '正常');
    assert.match(await page.locator('#voice-rollout-summary').innerText(), /仅指定用户 · 0 人/);
    assert.match(await page.locator('#voice-gate-warning').innerText(), /名单为空/);
    assert.equal(await page.locator('#voice-advanced-editor').getAttribute('open'), null);
    const maintenanceToggle = page.getByRole('checkbox', { name: /维护模式/ });
    assert.equal(await maintenanceToggle.count(), 1);
    const maintenanceLabel = page.locator('.voice-form-field > label[for="voice-field-config-global-maintenance_mode"]');
    await maintenanceLabel.click();
    assert.equal(await maintenanceToggle.isChecked(), true);
    await maintenanceLabel.click();
    assert.equal(await maintenanceToggle.isChecked(), false);
    const maintenanceTrack = page.locator('#voice-field-config-global-maintenance_mode + .voice-switch-track');
    const maintenanceTrackBox = await maintenanceTrack.boundingBox();
    assert.deepEqual(
      { width: maintenanceTrackBox.width, height: maintenanceTrackBox.height },
      { width: 44, height: 22 },
      'the visible switch track must keep its full 44x22 layout'
    );
    await maintenanceTrack.click();
    assert.equal(await maintenanceToggle.isChecked(), true, 'clicking the visible switch track must toggle the field');
    await maintenanceTrack.click();
    assert.equal(await maintenanceToggle.isChecked(), false);

    await page.setViewportSize({ width: 900, height: 1000 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
    await page.setViewportSize({ width: 1440, height: 1000 });

    const rollout = page.locator('[data-voice-field="rollout.mode"]');
    assert.equal(await rollout.inputValue(), 'allowlist');
    assert.deepEqual(await page.getByLabel('开放范围').locator('option').allTextContents(), ['暂停开放', '仅指定用户', '全部用户']);
    await rollout.selectOption('all');
    assert.equal(JSON.parse(await page.locator('#voice-section-json').inputValue()).rollout.mode, 'all');
    assert.equal(await page.locator('#voice-form-warning').isVisible(), false);
    assert.match(await page.locator('#voice-gate-warning').innerText(), /名单为空/);
    await page.locator('#btn-voice-save-section').click();
    await page.waitForFunction(() => document.querySelector('#voice-section-change').textContent.includes('草稿'));
    assert.equal(writes[0].section, 'global');
    assert.equal(writes[0].body.content.rollout.mode, 'all');
    assert.equal(writes[0].body.content.maintenance_message, '语音通话暂时不可用，请稍后再试');
    assert.equal(writes[0].body.content.enabled, false);

    await page.locator('#btn-voice-publish').click();
    const activeDiff = page.locator('[data-risk-active]');
    const draftDiff = page.locator('[data-risk-draft]');
    assert.equal(
      await activeDiff.locator('.voice-diff-line.is-removed [data-diff-code]').filter({ hasText: '"mode": "allowlist"' }).count(),
      1
    );
    assert.equal(
      await draftDiff.locator('.voice-diff-line.is-added [data-diff-code]').filter({ hasText: '"mode": "all"' }).count(),
      1
    );
    assert.equal(
      await activeDiff.locator('.voice-diff-line').count(),
      await draftDiff.locator('.voice-diff-line').count(),
      'side-by-side diff rows must stay aligned'
    );
    assert.ok(await activeDiff.locator('.voice-diff-line.is-unchanged').count() > 0);
    await page.locator('[data-cancel]').click();

    await page.locator('[data-voice-section="s2s"]').click();
    const model = page.locator('[data-voice-field="model_version"]');
    assert.equal(await model.inputValue(), '2.2.0.0');
    await model.fill('2.3.0.0');
    assert.equal(JSON.parse(await page.locator('#voice-section-json').inputValue()).model_version, '2.3.0.0');
    assert.match(await page.locator('#voice-business-form').innerText(), /连接超时/);

    for (const section of ['global','persona_ref','s2s','voice','capabilities','quota','growth','concurrency','interaction','summary','followup','retention']) {
      await page.locator('[data-voice-section="' + section + '"]').click();
      assert.ok((await page.locator('#voice-business-form .voice-form-field').count()) > 0, 'config section has fields: ' + section);
      assert.ok(!(await page.locator('#voice-business-form').innerText()).includes('尚未表单化'), 'config section is form based: ' + section);
    }

    await page.locator('#voice-key-script').click();
    for (const section of ['context_pack','call_answer','recall','memory','summary','barge_in','silence_and_exit','followup','end_reason','reconnect_bridge','crisis']) {
      await page.locator('[data-voice-section="' + section + '"]').click();
      assert.ok((await page.locator('#voice-business-form .voice-form-field').count()) > 0, 'script section has fields: ' + section);
      assert.ok(!(await page.locator('#voice-business-form').innerText()).includes('尚未表单化'), 'script section is form based: ' + section);
    }
    assert.match(await page.locator('#voice-editor-note').innerText(), /内容安全/);
    assert.equal(await page.locator('#voice-editor-note a').getAttribute('href'), '/admin/pages/safety-rules.html#crisis');
    await page.locator('[data-voice-section="summary"]').click();
    const prompt = page.locator('[data-voice-field="prompt_template"]');
    assert.equal(await prompt.inputValue(), '总结提示词');
    await prompt.fill('新的总结提示词');
    assert.equal(await page.locator('#voice-section-json').inputValue(), '新的总结提示词');

    assert.deepEqual(errors, []);
    console.log('PASS: business forms, Chinese labels, gate summary, advanced JSON fallback and bidirectional draft updates');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

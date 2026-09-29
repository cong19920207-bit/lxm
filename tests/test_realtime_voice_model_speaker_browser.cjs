const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    const writes = [];
    const config = {
      global: { enabled: false, maintenance_mode: false },
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
        retry_backoff_ms: [200, 500]
      },
      voice: {
        voice_id: 'saturn_zh_female_keainvsheng_tob',
        voice_version: 'voice-v1',
        candidates: [{
          voice_id: 'saturn_zh_female_keainvsheng_tob',
          voice_version: 'voice-v1',
          enabled: true
        }],
        persona_mapping: {},
        speech_rate: 0,
        loudness_rate: 0,
        expressive: false,
        tone_instruction: ''
      }
    };
    let draftRevision = 0;

    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      sessionStorage.setItem('admin_token', 'local-test');
      sessionStorage.setItem('admin_role', 'super_admin');
    });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== 'http://voice.test') return route.abort();
      if (url.pathname.startsWith('/api/')) {
        if (route.request().method() === 'PATCH') {
          const body = route.request().postDataJSON();
          const section = decodeURIComponent(url.pathname.split('/').pop());
          writes.push({ section, body });
          config[section] = body.content;
          draftRevision += 1;
          return route.fulfill({ json: { code: 0, data: { draft_revision: draftRevision } } });
        }
        if (url.pathname === '/api/admin/voice/config/config') {
          return route.fulfill({ json: { code: 0, data: {
            config,
            _meta: {
              base_version: 1,
              draft_revision: draftRevision,
              has_draft: draftRevision > 0,
              changed_sections: writes.map(item => item.section)
            }
          } } });
        }
        if (url.pathname === '/api/admin/voice/config/config/history/1') {
          return route.fulfill({ json: { code: 0, data: {
            config,
            version: 1,
            updated_at: '2026-09-27T00:00:00',
            updated_by: 'test'
          } } });
        }
        if (url.pathname === '/api/admin/voice/config/config/history') {
          return route.fulfill({ json: { code: 0, data: { list: [] } } });
        }
        return route.fulfill({ json: { code: 0, data: { list: [] } } });
      }
      const file = url.pathname.slice(1);
      return fs.existsSync(file)
        ? route.fulfill({ path: file })
        : route.fulfill({ status: 404, body: '' });
    });

    await page.goto('http://voice.test/admin/pages/voice-config.html');
    await page.waitForFunction(() => document.querySelector('#voice-section-json').value.includes('maintenance_mode'));

    const s2sButton = page.locator('[data-voice-section="s2s"]');
    await assert.doesNotReject(() => s2sButton.waitFor());
    assert.match(await s2sButton.innerText(), /MODEL/);
    await s2sButton.click();
    const primaryInput = page.locator('#voice-primary-field-input');
    assert.equal(await page.locator('#voice-primary-field-label').innerText(), 'MODEL（s2s.model_version）');
    assert.equal(await primaryInput.inputValue(), '2.2.0.0');
    await primaryInput.fill('2.3.0.0');
    assert.equal(JSON.parse(await page.locator('#voice-section-json').inputValue()).model_version, '2.3.0.0');
    await page.locator('#btn-voice-save-section').click();
    await page.waitForFunction(() => document.querySelector('#voice-primary-field-input').value === '2.3.0.0');
    assert.equal(writes[0].section, 's2s');
    assert.equal(writes[0].body.content.model_version, '2.3.0.0');
    assert.equal(writes[0].body.content.provider, 'doubao');

    const voiceButton = page.locator('[data-voice-section="voice"]');
    assert.match(await voiceButton.innerText(), /SPEAKER/);
    await voiceButton.click();
    assert.equal(await page.locator('#voice-primary-field-label').innerText(), 'SPEAKER（voice.voice_id）');
    assert.equal(await primaryInput.inputValue(), 'saturn_zh_female_keainvsheng_tob');
    await primaryInput.fill('saturn_zh_female_shuangkuaisisi_tob');
    assert.equal(JSON.parse(await page.locator('#voice-section-json').inputValue()).voice_id, 'saturn_zh_female_shuangkuaisisi_tob');
    await page.locator('#btn-voice-save-section').click();
    await page.waitForFunction(() => document.querySelector('#voice-primary-field-input').value === 'saturn_zh_female_shuangkuaisisi_tob');
    assert.equal(writes[1].section, 'voice');
    assert.equal(writes[1].body.content.voice_id, 'saturn_zh_female_shuangkuaisisi_tob');
    assert.equal(writes[1].body.content.voice_version, 'voice-v1');
    assert.deepEqual(errors, []);
    console.log('PASS: MODEL and SPEAKER are visible, editable and saved through their documented P1 fields');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

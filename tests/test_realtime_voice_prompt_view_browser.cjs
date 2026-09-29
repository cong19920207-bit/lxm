/* Real frontend with source-derived template fixtures; no live model or database. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {chromium} = require(process.env.VOICE_PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '..');
const python = process.env.VOICE_TEST_PYTHON || path.join(root, '.venv-step001/bin/python');
const fixture = JSON.parse(execFileSync(python, ['-c',
  'import json; from backend.services.realtime_voice_prompt_view_service import get_prompt_catalog,get_prompt_view; c=get_prompt_catalog(); print(json.dumps(dict(catalog=c, views={i["key"]:get_prompt_view(i["key"]) for g in c["groups"] for i in g["items"]}), ensure_ascii=False))'
], {cwd: root, encoding: 'utf8'}));
const prefix = '/api/admin/voice/prompt-view';

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    for (const role of ['super_admin', 'ai_trainer', 'observer', 'ops_admin', 'tech_ops']) {
      const page = await browser.newPage({viewport: {width: 1440, height: 1050}});
      const methods = [], errors = [];
      let failing = false, unsafe = false;
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(role => {
        sessionStorage.setItem('admin_token', 'test');
        sessionStorage.setItem('admin_role', role);
        sessionStorage.setItem('admin_username', '测试账号');
        document.execCommand = command => {
          if (command !== 'copy') return false;
          window.copiedText = window.getSelection().toString();
          return true;
        };
      }, role);
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'http://voice.test') return route.abort();
        if (url.pathname.startsWith(prefix)) {
          methods.push(route.request().method());
          if (failing) return route.fulfill({json: {code: 503, message: 'unavailable'}});
          const key = url.pathname.slice(prefix.length + 1);
          let data = key ? fixture.views[key] : fixture.catalog;
          if (unsafe && key) data = {...data, content: '<img src=x onerror=alert(1)>\n{{safe_variable}}', title: '<svg onload=alert(1)>'};
          return route.fulfill({json: {code: 0, data}});
        }
        const file = path.resolve(root, '.' + url.pathname);
        if (!file.startsWith(root + path.sep)) return route.fulfill({status: 404});
        return fs.existsSync(file) ? route.fulfill({path: file}) : route.fulfill({status: 404, body: ''});
      });
      await page.goto('http://voice.test/admin/pages/voice-prompts.html');
      if (['ops_admin', 'tech_ops'].includes(role)) {
        await page.waitForURL('**/error.html?type=403');
        assert.equal(methods.length, 0);
        await page.close();
        continue;
      }
      await page.locator('#vp-panel').waitFor({state: 'visible'});
      assert.equal(await page.locator('#vp-tabs [role=tab]').count(), 7);
      assert.equal(await page.locator('#vp-prompt-count').innerText(), '10');
      assert.equal(await page.locator('#sidebar-mount .menu-item.active').filter({hasText: '语音 Prompt'}).count(), 1);
      assert.equal(await page.locator('.menu-group.expanded .menu-group-label').filter({hasText: '语音通话'}).count(), 1);
      assert.equal(await page.locator('main input, main textarea, main select, main [contenteditable=true]').count(), 0);
      for (const group of fixture.catalog.groups) {
        await page.locator('#vp-tabs').getByRole('tab', {name: group.label, exact: true}).click();
        for (const item of group.items) {
          if (group.items.length > 1) await page.locator('#vp-variants').getByRole('tab', {name: item.label, exact: true}).click();
          await page.waitForFunction(key => document.getElementById('vp-key').textContent === key && !document.getElementById('vp-panel').hidden, item.key);
          assert.equal(await page.locator('#vp-content').textContent(), fixture.views[item.key].content);
        }
      }
      await page.getByRole('tab', {name: '记忆抽取', exact: true}).click();
      await page.locator('#vp-content').getByText('【系统指令】', {exact: false}).waitFor();
      await page.getByRole('button', {name: '复制全文', exact: true}).click();
      assert.equal(await page.evaluate(() => window.copiedText), fixture.views.memory.content);
      if (role === 'super_admin') {
        await page.screenshot({path: '/private/tmp/voice-prompts-desktop.png', fullPage: true});
        await page.getByRole('tab', {name: '收尾控制', exact: true}).click();
        await page.locator('#vp-variants').getByRole('tab', {name: '时长将尽', exact: true}).click();
        await page.locator('#vp-variants [aria-selected=true]').focus();
        await page.keyboard.press('ArrowRight');
        await page.waitForFunction(() => document.getElementById('vp-key').textContent === 'silence_confirm');
        assert.equal(await page.locator('#vp-variants [aria-selected=true]').innerText(), '静默确认');
        await page.reload();
        await page.locator('#vp-panel').waitFor({state: 'visible'});
        assert.equal(await page.locator('#vp-key').innerText(), 'silence_confirm');
        await page.screenshot({path: '/private/tmp/voice-prompts-control.png', fullPage: true});
        await page.setViewportSize({width: 390, height: 844});
        await page.getByRole('tab', {name: '记忆抽取', exact: true}).click();
        await page.waitForFunction(() => document.getElementById('vp-key').textContent === 'memory');
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
        await page.screenshot({path: '/private/tmp/voice-prompts-mobile.png', fullPage: true});
      }
      failing = true;
      await page.getByRole('button', {name: '刷新当前提示词'}).click();
      await page.locator('#vp-error').waitFor({state: 'visible'});
      assert.equal(await page.locator('#vp-panel').isVisible(), false);
      failing = false;
      await page.getByRole('button', {name: '重新加载', exact: true}).click();
      await page.locator('#vp-panel').waitFor({state: 'visible'});
      unsafe = true;
      await page.getByRole('button', {name: '刷新当前提示词'}).click();
      await page.waitForFunction(() => document.getElementById('vp-title').textContent === '<svg onload=alert(1)>');
      assert.equal(await page.locator('#vp-title svg, #vp-content img').count(), 0);
      assert.ok(methods.length > 0 && methods.every(method => method === 'GET'));
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('PASS: 7 tabs / 10 source-derived prompts; role access, read-only requests, copy, keyboard, deep links, retry, safe rendering, narrow layout.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

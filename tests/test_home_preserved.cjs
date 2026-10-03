// PRD §4 on the actual homepage. Business data, clock and destination pages
// are controlled fixtures; this is not phone, destination-page or audio acceptance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {setup, ready, root} = require('./home_browser_helpers.cjs');
const output = process.env.HOME_REGRESSION_EVIDENCE_DIR || path.join(root, 'docs/design/home-redesign/execution/evidence/home-m4');
const results = [];
const more = "button[onclick=\"handleHomeQuickAction('more')\"]";
const quick = action => `button[onclick="handleHomeQuickAction('${action}')"]`;
async function start(token) {
  const s = await setup({token});
  await s.page.addInitScript(() => sessionStorage.setItem('lxm_home_loader_done', '1'));
  await s.page.clock.setFixedTime(new Date('2026-10-02T04:00:00Z'));
  return s;
}
async function home(s) {
  await s.page.goto(s.origin + '/pages/index.html');
  await ready(s.page);
  await s.page.waitForFunction(() => window.HomeData && getHomeDataController().inspect().batches === 0);
}
async function activate(page, selector, method) {
  if (method === 'click') { await page.locator(selector).click(); return; }
  // Use real Tab traversal, not HTMLElement.focus(), to check keyboard reachability.
  for (let i = 0; i < 35; i++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(selector => document.activeElement.matches(selector), selector)) {
      await page.keyboard.press(method); return;
    }
  }
  throw Error('Control is not reachable with Tab: ' + selector);
}
(async () => {
  fs.mkdirSync(output, {recursive:true});
  let s = await start(true);
  try {
    let relationship = {level:0,current_growth:0,next_threshold:200};
    let diary = {items:[]};
    await s.page.route('**/api/relationship/status', route => route.fulfill({json:{code:0,data:relationship}}));
    await s.page.route('**/api/diary/list?**', route => route.fulfill({json:{code:0,data:diary}}));
    await s.page.route('**/api/relationship/detail', route => route.fulfill({json:{code:0,data:{milestones:{known_days:42}}}}));
    await s.page.route('**/api/feed/list?**', route => route.fulfill({json:{code:0,data:{posts:[{content_text:'窗边的日常',scheduled_publish_time:'2026-10-02T11:30:00',images:[]}]}}}));
    await s.page.route('**/api/feed/badge', route => route.fulfill({json:{code:0,data:{unread_reply_count:3,new_post_count:2,has_new:true}}}));
    await home(s);
    const levels = [
      {data:{level:0,current_growth:0,next_threshold:200},label:'陌生',value:'0 / 200',percent:'0%',lock:'locked'},
      {data:{level:1,growth_value:100,next_threshold:200},label:'朋友',value:'100 / 200',percent:'50%',lock:'unlocked'},
      {data:{level:2,current_growth:250,growth_value:999,next_threshold:400,progress_percent:62.5},label:'亲密',value:'250 / 400',percent:'62.5%',lock:'unlocked'},
      {data:{level:3,current_growth:850,next_threshold:null},label:'知己',value:'850 / 已满级',percent:'100%',lock:'unlocked'},
    ];
    for (const item of levels) {
      relationship = item.data;
      await s.page.evaluate(() => getHomeDataController().retry('relationship'));
      assert.equal(await s.page.locator('#relationship-level-name').textContent(), item.label);
      assert.equal(await s.page.locator('#progress-info').textContent(), item.value);
      assert.equal(await s.page.locator('#progress-fill').evaluate(el => el.style.width), item.percent);
      assert.equal(await s.page.locator('#diary-lock').getAttribute('data-lock-state'), item.lock);
    }
    assert.equal(await s.page.locator('#known-days').textContent(), '陪伴你的第 42 天');
    assert.equal(await s.page.locator('#feed-preview-text').textContent(), '窗边的日常');
    assert.equal(await s.page.locator('#feed-updated').textContent(), '更新 · 今天 11:30');
    assert.equal(await s.page.locator('#feed-reply-pill').textContent(), 'NEW · 3条新回复');
    assert.equal(await s.page.locator('#feed-footer-text').textContent(), '2 条新动态 · 快来看看她分享了什么吧');
    results.push({case:'four relationship levels, growth fallback/precedence, maximum level, known days and Feed',pass:true});
    for (const [fields, expected] of [
      [{status_text:'今天在窗边等你',ai_current_emotion:'想念'},'今天在窗边等你'],
      [{ai_current_emotion:'想念'},'有点想你了，来聊聊吧~'],
      [{ai_current_emotion:'不存在的情绪'},'今天状态不错，继续陪伴你吧~'],
    ]) {
      relationship = {...levels[2].data,...fields};
      await s.page.evaluate(() => getHomeDataController().retry('relationship'));
      assert.equal(await s.page.locator('#status-text').textContent(), expected);
    }
    results.push({case:'status text, emotion and default priority',pass:true});
    const now = Date.parse('2026-10-02T04:00:00Z');
    for (const [age, expected] of [[30000,'刚刚'],[5*60000,'5分钟前'],[3*3600000,'3小时前'],[2*86400000,'9月30日']]) {
      diary = {items:[{created_at:new Date(now-age).toISOString(),is_read:false,content:'不应泄漏的日记正文'}]};
      await s.page.evaluate(() => getHomeDataController().retry('diary'));
      assert.equal(await s.page.locator('#diary-preview').textContent(), '今天记录点什么好呢...');
      assert.equal(await s.page.locator('#diary-time').textContent(), '刚刚写下 · ' + expected);
      assert.equal(await s.page.locator('#diary-new').isVisible(), true);
    }
    diary.items[0].is_read = true;
    await s.page.evaluate(() => getHomeDataController().retry('diary'));
    assert.equal(await s.page.locator('#diary-new').isVisible(), false);
    diary = {items:[]};
    await s.page.evaluate(() => getHomeDataController().retry('diary'));
    assert.equal(await s.page.locator('#diary-time').textContent(), '');
    results.push({case:'fixed diary sentence, four relative time bands, strict NEW and empty list',pass:true});
    const periods = [
      ['00:00','深夜',true],['04:59','深夜',true],['05:00','清晨',false],['07:59','清晨',false],
      ['08:00','上午',false],['11:59','上午',false],['12:00','中午',false],['13:59','中午',false],
      ['14:00','下午',false],['17:59','下午',false],['18:00','傍晚',false],['19:59','傍晚',false],
      ['20:00','晚上',true],['23:59','晚上',true],
    ];
    for (const [time, period, night] of periods) {
      await s.page.clock.setFixedTime(new Date('2026-10-02T' + time + ':00+08:00'));
      await s.page.evaluate(() => updateHeroClock());
      assert.equal(await s.page.locator('#beijing-time').textContent(), time);
      assert.equal(await s.page.locator('#beijing-period').textContent(), period);
      assert.equal(await s.page.locator('#good-night').evaluate(el => el.classList.contains('is-visible')), night);
    }
    assert.match(await s.page.locator('.home-cta-btn').textContent(), /和她说说话吧\s*她在等你哦/);
    assert.deepEqual(s.errors, []);
    results.push({case:'Beijing 24h clock, fourteen seven-period boundaries and Good night',pass:true});
  } finally { await s.close(); }

  const destinations = [
    ['#linxiaomeng-avatar','/pages/settings.html',false],
    ['.home-intimacy-pill','/pages/relationship.html',true],
    [quick('memory'),'/pages/memory.html',true],
    ['.home-diary-card','/pages/diary.html',true],
    ['#feed-entry-card','/pages/feed.html',false],
    ['.home-cta-btn','/pages/chat.html',false],
  ];
  for (const token of [false,true]) {
    s = await start(token);
    try {
      // A destination shell only captures the homepage's navigation target.
      await s.page.route(/\/pages\/(settings|relationship|memory|diary|feed|chat)\.html(?:\?.*)?$/, route => route.fulfill({contentType:'text/html',body:'<!doctype html><title>Controlled destination</title>'}));
      await s.page.route('**/api/feed/badge', route => route.fulfill({json:{code:0,data:{unread_reply_count:3,new_post_count:0,has_new:false}}}));
      await s.page.addInitScript(() => Object.defineProperty(navigator,'userAgent',{get:()=>'Controlled MicroMessenger fixture'}));
      for (const method of ['click','Enter','Space']) {
        for (const [selector, target, gated] of destinations) {
          await home(s);
          await activate(s.page,selector,method);
          if (!token && gated) {
            await s.page.waitForSelector('#auth-login-modal.is-open');
            assert.equal(new URL(s.page.url()).pathname, '/pages/index.html');
            await s.page.keyboard.press('Escape');
          } else {
            const expected = target === '/pages/feed.html' && token ? target+'?focus=unread_reply' : target;
            await s.page.waitForURL(s.origin+expected);
          }
          results.push({identity:token?'authenticated':'visitor',method,target,gated:!token&&gated,pass:true});
        }
        await home(s);
        await activate(s.page,more,method);
        await s.page.waitForSelector(token?'.toast-item':'#auth-login-modal.is-open');
        if (token) assert.equal(await s.page.locator('.toast-item').last().textContent(), '敬请期待');
        assert.equal(await s.page.locator('#home-motion-panel').count(), 0);
        assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().intent), false);
        await s.page.keyboard.press('Escape');
        results.push({identity:token?'authenticated':'visitor',method,target:'more placeholder',pass:true});
      }
      for (const action of ['video','sleep','voice']) {
        await home(s);
        await s.page.locator(quick(action)).click();
        if (!token) await s.page.waitForSelector('#auth-login-modal.is-open');
        else if (action !== 'voice') {
          await s.page.waitForSelector('.toast-item');
          assert.equal(await s.page.locator('.toast-item').last().textContent(), '敬请期待');
        }
        else {
          await s.page.waitForSelector('.voice-entry:not([hidden])');
          assert.equal(await s.page.locator('#voice-entry-title').textContent(), '换个浏览器，再和她说话');
          assert.equal(await s.page.evaluate(() => HomeScene.current.running), false);
          await s.page.getByRole('button',{name:'关闭通话',exact:true}).click();
        }
        assert.equal(new URL(s.page.url()).pathname, '/pages/index.html');
        results.push({identity:token?'authenticated':'visitor',target:action,pass:true});
      }
      assert.deepEqual(s.errors, []);
    } finally { await s.close(); }
  }
  s = await start(false);
  try {
    const privateRequests = [];
    s.page.on('request', request => {
      const url = new URL(request.url());
      if (url.pathname.startsWith('/api/')) privateRequests.push({path:url.pathname,method:request.method()});
    });
    await s.page.addInitScript(() => {
      window.__permissionCalls = 0;
      window.DeviceOrientationEvent.requestPermission = () => { window.__permissionCalls++; return Promise.resolve('granted'); };
    });
    await s.page.route('**/api/auth/login', route => route.fulfill({json:{code:0,data:{token:'controlled-login-token'}}}));
    await home(s);
    await s.page.locator(more).click();
    await s.page.locator('#auth-modal-login-username').fill('fixtureuser');
    await s.page.locator('#auth-modal-login-password').fill('Fixture123');
    privateRequests.length = 0;
    await s.page.locator('[data-auth-modal-submit="login"]').click();
    await s.page.waitForFunction(() => homeAuthMode === 'authenticated' && getHomeDataController().inspect().batches === 0);
    assert.equal(await s.page.locator('#auth-login-modal').evaluate(el => el.classList.contains('is-open')), false);
    assert.equal(await s.page.locator('#home-motion-panel').count(), 0);
    assert.equal(await s.page.evaluate(() => window.__permissionCalls), 0);
    assert.equal(await s.page.evaluate(() => HomeScene.tilt.inspect().intent), false);
    for (const endpoint of ['/api/relationship/status','/api/relationship/detail','/api/diary/list','/api/agent/unread-count','/api/feed/list','/api/feed/badge']) {
      assert.equal(privateRequests.filter(request => request.path === endpoint).length, 1, 'Exactly one restoration request: '+endpoint);
    }
    assert.equal(privateRequests.filter(request => request.path === '/api/auth/login').length, 1);
    assert.deepEqual(s.errors, []);
    results.push({case:'actual login form with controlled POST; single private restoration, no action replay or tilt authorization',pass:true});
  } finally { await s.close(); }
  const files = ['frontend/pages/index.html','frontend/static/js/api.js','frontend/static/js/home-data.js','frontend/static/js/home-scene.js'];
  const sourceSha256 = Object.fromEntries(files.map(file => [file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
  fs.writeFileSync(path.join(output,'step-017-preserved-results.json'),JSON.stringify({scope:'Actual desktop Chrome homepage, controlled API/clock/MicroMessenger capability/destination fixtures. Existing failure/unknown/login restoration cases are in regression/; actual phone keyboard/gestures/tilt/audio and destination pages remain unverified.',results,sourceSha256},null,2)+'\n');
  console.log('PASS '+results.length+' preserved homepage data and input scenarios');
})().catch(error => { console.error(error); process.exitCode=1; });

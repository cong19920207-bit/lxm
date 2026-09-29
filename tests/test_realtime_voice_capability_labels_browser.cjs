const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
const keys=['supports_current_turn_rag_gate','supports_reply_cancel','supports_context_truncate','supports_playback_text_mapping','supports_sentence_playback_ack','supports_session_reconnect'];
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
    for(const role of ['super_admin','tech_ops','observer','ops_admin','ai_trainer']) {
      const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[], writes=[];
      let status='unverified';
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(role=>{sessionStorage.setItem('admin_token','local-test');sessionStorage.setItem('admin_role',role);sessionStorage.setItem('admin_username','test');},role);
      await page.route('**/*',async route=>{
        const url=new URL(route.request().url());
        if(url.origin!=='http://voice.test')return route.abort();
        if(url.pathname.startsWith('/api/')) {
          if(route.request().method()!=='GET')writes.push(url.pathname);
          let data={};
          if(url.pathname==='/api/admin/voice/config/config')data={config:{global:{enabled:false},s2s:{credential_configured:false},capabilities:Object.fromEntries(keys.map(k=>[k,{verification_status:status,effective_scope:'off',enabled:false,fallback_mode:'next_turn',evidence_ttl_days:30}]))},_meta:{has_draft:false,base_version:0}};
          else if(url.pathname.includes('/history'))data={list:[]};
          else if(url.pathname.includes('/active-calls'))data={calls:[],database_count:0,lease_count:0};
          return route.fulfill({json:{code:0,data}});
        }
        const file=url.pathname.slice(1);
        return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404,body:''});
      });
      await page.goto('http://voice.test/admin/pages/voice-config.html');
      for(const [state,label] of [['unverified','未验证'],['stale','证据已过期或失效'],['failed','验证失败'],['verified','已验证']]) {
        status=state;
        await page.locator('#btn-voice-reload').click();
        const labels=page.locator('.voice-capability-state span:first-child');
        await page.waitForFunction(label=>Array.from(document.querySelectorAll('.voice-capability-state span:first-child')).filter(x=>x.textContent===label).length===6,label);
        assert.deepEqual(await labels.allTextContents(),Array(6).fill(label));
        assert.equal(await page.locator('.voice-capability-card.is-unverified').count(),6);
        assert.ok((await page.locator('.voice-capability-warning').innerText()).includes('未验证 / 关闭'));
        assert.deepEqual(await page.locator('.voice-capability-state span:nth-child(2)').allTextContents(),Array(6).fill('off'));
        assert.equal(await labels.first().evaluate(el=>getComputedStyle(el).display==='none'),false);
      }
      assert.deepEqual(writes,[]); assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('PASS: five Chrome roles, six cards, four Chinese verification states, off scope unchanged, zero writes');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

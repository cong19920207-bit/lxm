const fs=require('node:fs');const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require(process.env.VOICE_PLAYWRIGHT_PATH||'playwright');
(async()=>{
 const values=JSON.parse(execFileSync(process.env.VOICE_PYTHON||'.venv-step001/bin/python',['-c',
  "import json; from backend.constants.realtime_voice_config import get_default_voice_call_config,get_default_voice_call_script; print(json.dumps({'config':get_default_voice_call_config({'config_key':'persona','version':1,'content_sha256':'sha256:'+'0'*64}),'script':get_default_voice_call_script()}))"],{encoding:'utf8'}));
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{sessionStorage.setItem('admin_token','test-local');sessionStorage.setItem('admin_role','super_admin');sessionStorage.setItem('admin_username','test');});
  const writes=[];let saved=null;
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());if(url.origin!=='http://voice.test')return route.abort();
   if(url.pathname.startsWith('/api/')){
    const m=url.pathname.match(/\/voice\/config\/(config|script)(.*)/);let data={calls:[],list:[],total:0};
    if(m){const alias=m[1],suffix=m[2];const original=values[alias];const config=JSON.parse(JSON.stringify(original));
     if(alias==='script'&&saved)config.summary=saved;
     if(route.request().method()==='PATCH'){writes.push(route.request().postDataJSON());saved=writes.at(-1).content;data={draft_revision:1};}
     else if(!suffix){delete config.summary; if(saved&&alias==='script')config.summary=saved;data={config,_meta:{base_version:1,draft_revision:saved?1:null,has_draft:!!saved,content_sha256:'sha256:test',changed_sections:saved?['summary']:[],section_defaults:{summary:original.summary}}};}
     else if(suffix==='/history/1')data={config:original,version:1};
    }
    return route.fulfill({json:{code:0,data}});
   }
   const file=url.pathname.replace(/^\//,'');if(!file.includes('..')&&fs.existsSync(file))return route.fulfill({path:file});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://voice.test/admin/pages/voice-config.html');
  await page.locator('#voice-key-script').click();
  await page.locator('[data-voice-section="summary"]').click();
  const editor=page.locator('[data-voice-field="prompt_template"]');
  await editor.waitFor();assert.equal(await editor.inputValue(),values.script.summary.prompt_template);
  const edited=(await editor.inputValue())+'\n测试修改：摘要避免空泛措辞。';await editor.fill(edited);
  const savedResponse=page.waitForResponse(r=>r.request().method()==='PATCH');
  await page.locator('#btn-voice-save-section').click();await savedResponse;
  await page.waitForFunction(()=>document.querySelector('#voice-section-json').value.includes('测试修改'));
  await page.waitForFunction(()=>document.querySelector('#voice-section-change').textContent.includes('草稿'));
  assert.equal(writes.length,1);assert.deepEqual(writes[0].content,{prompt_template:edited});
  assert.deepEqual(errors,[]);
  assert.ok((await editor.boundingBox()).height>=360);
  await editor.evaluate(el=>{el.scrollTop=0});await editor.scrollIntoViewIfNeeded();
  await page.screenshot({path:'docs/design/realtime_voice/P1/execution/evidence/m6-20260913/step031-prompt-admin.png'});
  console.log('PASS: legacy default prompt visible, plain multiline editing, correct draft payload, no page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

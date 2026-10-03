// Real frontend files over local HTTP; business responses are controlled fixtures.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.HOME_PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '..');
const evidence = process.env.HOME_EVIDENCE_DIR || path.join(root, 'docs/design/home-redesign/execution/evidence/home-m1');
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript', '.css':'text/css',
  '.png':'image/png', '.jpg':'image/jpeg', '.webp':'image/webp', '.svg':'image/svg+xml', '.json':'application/json' };

async function setup({ baseline=false, token=false, viewport={width:390,height:844}, dpr=3, nativeBfcache=false }={}) {
  const requests = [];
  const apiRequests = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname.startsWith('/api/')) {
      apiRequests.push({path:url.pathname+url.search,method:req.method});
      let data = {};
      if (url.pathname === '/api/feed/list') data = { posts:[] };
      if (url.pathname === '/api/feed/badge') data = { unread_reply_count:0, new_post_count:0, has_new:false };
      if (url.pathname === '/api/relationship/status') data = {level:2, level_name:'亲密', ai_current_emotion:'开心', current_growth:250, next_threshold:400, progress_percent:62.5};
      if (url.pathname === '/api/relationship/detail') data = {milestones:[]};
      if (url.pathname === '/api/diary/list') data = {items:[]};
      if (url.pathname === '/api/agent/unread-count') data = {count:0};
      if (url.pathname === '/api/agent/messages') data = [];
      if (url.pathname === '/api/chat/timeline') data = {items:[],next_cursor:null,has_more:false};
      const bytes = Buffer.from(JSON.stringify({code:0,data}));
      res.writeHead(200, {'Content-Type':'application/json', 'Content-Length':bytes.length});
      res.end(bytes); return;
    }
    const pathname = decodeURIComponent(url.pathname);
    if (!pathname.startsWith('/static/') && !pathname.startsWith('/pages/')) { res.writeHead(404).end(); return; }
    let file = path.resolve(root, 'frontend', '.' + pathname);
    if (!file.startsWith(path.join(root, 'frontend') + path.sep)) { res.writeHead(403).end(); return; }
    if (baseline && pathname === '/pages/index.html') file = path.join(evidence,'baseline/index.html');
    if (baseline && pathname === '/static/js/api.js') file = path.join(evidence,'baseline/api.js');
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
    const bytes = fs.readFileSync(file);
    requests.push({path:pathname,bytes:bytes.length});
    res.writeHead(200, {'Content-Type':mime[path.extname(file)]||'application/octet-stream',
      'Content-Length':bytes.length, 'Cache-Control':'public, max-age=3600'});
    res.end(bytes);
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless:true,
    ...(nativeBfcache?{ignoreDefaultArgs:['--disable-back-forward-cache']}:{}),
    executablePath:process.env.HOME_CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context = await browser.newContext({viewport,deviceScaleFactor:dpr});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror',err=>errors.push(err.message));
  // Browser request routing disables HTTP cache. Block external fonts through CDP
  // so warm-navigation and refresh measurements can use the native cache.
  const network = await context.newCDPSession(page);
  await network.send('Network.enable');
  await network.send('Network.setBlockedURLs',{urls:['https://fonts.googleapis.com/*','https://fonts.gstatic.com/*']});
  if(token) await page.addInitScript(value=>{
    if (!sessionStorage.getItem('__home_fixture_token_seeded')) {
      localStorage.setItem('token',value);
      sessionStorage.setItem('__home_fixture_token_seeded','1');
    }
  },typeof token==='string'?token:'controlled-home-fixture');
  return { page, context, browser, origin, requests, apiRequests, errors,
    async close(){await context.close();await browser.close();await new Promise(resolve=>server.close(resolve));} };
}

async function ready(page){
  await page.waitForFunction(()=>!document.getElementById('home-loading-screen'),{},{timeout:10000});
  await page.waitForFunction(()=>document.getElementById('main-content').classList.contains('content-loaded'));
}
function artifact(original) {
  const destination=process.env.HOME_REGRESSION_EVIDENCE_DIR ? path.join(process.env.HOME_REGRESSION_EVIDENCE_DIR,path.basename(original)) : original;
  fs.mkdirSync(path.dirname(destination),{recursive:true});return destination;
}
module.exports = {setup, ready, root, evidence, artifact};

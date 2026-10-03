// Temporary controlled homepage preview. No backend forwarding or real login.
// Run: node scripts/serve_home_preview.cjs --host 0.0.0.0 --port 54323
const http = require('node:http'),fs=require('node:fs'),path=require('node:path');
const frontend=path.resolve(__dirname,'../frontend');
const MOCK_TOKEN='home-preview-mock-token';
const pictures=['/static/images/Index/in_memery/sunset.png','/static/images/home-thumbnails/v2/diary_1.1ff65a5fb6c1.webp'];
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.json':'application/json'};
function beijingWallClock(date=new Date()) {
  return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(date).replace(' ','T');
}
function mockPost(authenticated) {
  return {id:1,content_text:'傍晚看了海，回来把今天的小事写进本子里。',hashtags:[],image_urls:pictures,
    scheduled_publish_time:beijingWallClock(),emotion:'平静',city:'',display_likes:12,display_comments:0,
    ...(authenticated?{user_liked:false,comments:[]}:{})};
}
function homepage(html,authenticated) {
  const script=`<script>
  (() => {
    try { ${authenticated?`localStorage.setItem('token',${JSON.stringify(MOCK_TOKEN)})`:`localStorage.removeItem('token'); localStorage.removeItem('relationship_level')`} } catch (_) {}
    // The preview has explicit state selection, and never submits credentials.
    document.addEventListener('submit',event => {
      if (event.target.matches('[data-auth-modal-panel]')) {
        event.preventDefault(); event.stopImmediatePropagation();
        window.showToast?.('本预览不登录真实账号，请从模拟预览入口切换状态');
      }
    },true);
  })();
  </script>`;
  const badge=`<a href="/__home_preview" style="position:fixed;top:4px;left:8px;z-index:4000;padding:2px 7px;border-radius:8px;background:#171124ee;color:#d8c6ff;font:10px/16px sans-serif;text-decoration:none" aria-label="模拟预览，${authenticated?'已登录':'访客'}，切换状态">模拟预览 · ${authenticated?'已登录':'访客'} · 切换</a>`;
  return html.replace('<head>','<head>'+script).replace('</body>',badge+'</body>');
}
const chooser=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>首页模拟预览</title>
<style>body{margin:0;padding:32px 24px;background:#100b21;color:#e7ddfa;font:16px/1.7 sans-serif}main{max-width:540px;margin:auto}a{display:block;margin:18px 0;padding:16px;border:1px solid #7e53ae;border-radius:14px;color:#fff;text-decoration:none;background:#392257}small{display:block;color:#bdacd8}</style>
<main><h1>首页模拟预览</h1><p>朋友圈包含两张示例图片。账号和私有数据均为模拟，未连接真实服务。</p>
<a href="/pages/index.html?__home_preview=visitor">访客首页</a><a href="/pages/index.html?__home_preview=authenticated">模拟登录首页</a>
<small>模拟登录用于检查更多互动和动态开关，不需要账号密码。倾斜仍需可信 HTTPS 和主动开启；此 HTTP 地址不支持真机传感器验收。真实语音、登录和子页业务尚未接入。</small></main></html>`;
function createPreviewServer() {
  return http.createServer((request,response) => {
    const send=(status,bytes,type='text/plain; charset=utf-8')=>{
      bytes=Buffer.isBuffer(bytes)?bytes:Buffer.from(bytes);
      response.writeHead(status,{'Content-Type':type,'Content-Length':bytes.length,'Cache-Control':'no-store'});
      response.end(request.method==='HEAD'?undefined:bytes);
    };
    const json=(status,data,message='模拟预览')=>send(status,JSON.stringify({code:status===200?0:1,data,message}),'application/json; charset=utf-8');
    let url;
    try { url=new URL(request.url,'http://preview.local'); } catch (_) { send(400,'Invalid request');return; }
    if(!['GET','HEAD'].includes(request.method)){json(405,null,'此预览不处理真实登录或写请求');return;}
    // Shared api.js uses localhost:8000 for cross-port development. Redirect
    // localhost browsing to loopback-IP so this preview always stays same-origin.
    if(/^localhost(?::\d+)?$/i.test(request.headers.host||'')){
      response.writeHead(302,{Location:'http://127.0.0.1:'+serverPort(response)+url.pathname+url.search,'Cache-Control':'no-store'}).end();return;
    }
    if(url.pathname==='/'){response.writeHead(302,{Location:'/pages/index.html','Cache-Control':'no-store'}).end();return;}
    if(url.pathname==='/__home_preview'){send(200,chooser,'text/html; charset=utf-8');return;}
    if(url.pathname.startsWith('/api/')){
      const authenticated=request.headers.authorization==='Bearer '+MOCK_TOKEN;
      if(request.headers.authorization!=null&&!authenticated){json(401,null,'该账号不是本预览的模拟登录');return;}
      if(url.pathname==='/api/feed/list'){json(200,{posts:[mockPost(authenticated)],next_cursor:null});return;}
      const data={
        '/api/relationship/status':{level:2,level_name:'亲密',ai_current_emotion:'平静',status_text:'今天也在呢，等你来聊天~',current_growth:250,next_threshold:400,progress_percent:62.5},
        '/api/relationship/detail':{milestones:{known_days:12}},
        '/api/diary/list':{items:[{id:1,created_at:new Date(Date.now()-25*60000).toISOString(),is_read:false}]},
        '/api/agent/unread-count':{count:0},
        '/api/feed/badge':{unread_reply_count:0,new_post_count:0,has_new:false},
      };
      if(Object.hasOwn(data,url.pathname)){json(authenticated?200:401,authenticated?data[url.pathname]:null,authenticated?'模拟预览':'未选择模拟登录');return;}
      json(404,null,'该接口不在首页模拟预览范围');return;
    }
    let pathname;
    try { pathname=decodeURIComponent(url.pathname); } catch (_) {send(400,'Invalid path');return;}
    if(!pathname.startsWith('/pages/')&&!pathname.startsWith('/static/')){send(404,'Not found');return;}
    const file=path.resolve(frontend,'.'+pathname);
    if(!file.startsWith(frontend+path.sep)||pathname.split('/').some(segment=>segment.startsWith('.'))){send(404,'Not found');return;}
    try {
      if(!fs.statSync(file).isFile()){send(404,'Not found');return;}
      let bytes=fs.readFileSync(file);
      if(pathname==='/pages/index.html')bytes=Buffer.from(homepage(bytes.toString('utf8'),url.searchParams.get('__home_preview')==='authenticated'));
      send(200,bytes,mime[path.extname(file)]||'application/octet-stream');
    } catch (_){send(404,'Not found');}
  });
}
function serverPort(response) { return response.socket.localPort; }
module.exports = {createPreviewServer};
if(require.main===module){
  const args=process.argv.slice(2),port=Number(args.includes('--port')?args[args.indexOf('--port')+1]:54323),host=args.includes('--host')?args[args.indexOf('--host')+1]:'0.0.0.0';
  if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid preview port');
  const server=createPreviewServer();server.listen(port,host,()=>console.log('Controlled homepage preview: http://'+host+':'+port+'/__home_preview (default visitor; two Feed pictures; no real backend)'));
  const close=()=>server.close(()=>process.exit(0));process.on('SIGINT',close);process.on('SIGTERM',close);
}

// Isolated repository Nginx and controlled API; never attach to existing app containers.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {chromium}=require(process.env.HOME_PLAYWRIGHT_PATH||'playwright');
const root=path.resolve(__dirname,'..'),dockerPath='/Applications/Docker.app/Contents/Resources/bin/docker';
const docker=(...args)=>execFileSync(dockerPath,args,{encoding:'utf8',timeout:60000}).trim();
const probe=`from http.server import BaseHTTPRequestHandler,HTTPServer
import json
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  route=self.path.split('?')[0]
  data={'posts':[]} if route=='/api/feed/list' else {'unread_reply_count':0,'new_post_count':0,'has_new':False} if route=='/api/feed/badge' else {'level':2,'level_name':'亲密','ai_current_emotion':'开心','current_growth':250,'next_threshold':400,'progress_percent':62.5} if route=='/api/relationship/status' else {'milestones':{'known_days':12}} if route=='/api/relationship/detail' else {'items':[]} if route=='/api/diary/list' else {'count':0} if route=='/api/agent/unread-count' else {'path':route,'connection':self.headers.get('Connection'),'upgrade':self.headers.get('Upgrade')}
  body=json.dumps({'code':0,'data':data}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
HTTPServer(('0.0.0.0',8000),Handler).serve_forever()
`;
async function setupNginx(){
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'lxm-home-nginx-')),frontend=path.join(folder,'frontend');
 fs.cpSync(path.join(root,'frontend'),frontend,{recursive:true});
 const suffix=path.basename(folder).toLowerCase(),network=suffix,backend=suffix+'-probe',proxy=suffix+'-proxy';
 const created=[];let browser;
 const close=async()=>{if(browser)await browser.close();for(const name of created.reverse())docker('rm','-f',name);try{docker('network','rm',network)}catch(_){}fs.rmSync(folder,{recursive:true,force:true})};
 try{
  docker('network','create',network);
  docker('run','-d','--pull=never','--name',backend,'--network',network,'--network-alias','backend','--entrypoint','python','lxm_for-backend:latest','-u','-c',probe);created.push(backend);
  // Docker Desktop bind mounts inherit macOS case behavior. Copy to Linux's own
  // filesystem so an incorrect lowercase URL is a genuine service-level failure.
  docker('run','-d','--pull=never','--name',proxy,'--network',network,'-p','127.0.0.1::80','-v',path.join(root,'nginx/nginx.conf')+':/etc/nginx/nginx.conf:ro','-v',frontend+':/fixture:ro','--entrypoint','sh','nginx:alpine','-c','cp -a /fixture/. /usr/share/nginx/html/ && chmod -R a+rX /usr/share/nginx/html && exec nginx -g "daemon off;"');created.push(proxy);
  const origin='http://'+docker('port',proxy,'80/tcp');
  for(let i=0;i<50;i++){try{if((await fetch(origin+'/pages/index.html')).ok)break}catch(_){}if(i===49)throw Error('Isolated Nginx did not start');await new Promise(r=>setTimeout(r,100));}
  docker('exec',proxy,'nginx','-t');
  browser=await chromium.launch({headless:true,executablePath:process.env.HOME_CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:3});const page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const cdp=await context.newCDPSession(page);await cdp.send('Network.enable');await cdp.send('Network.setBlockedURLs',{urls:['https://fonts.googleapis.com/*','https://fonts.gstatic.com/*']});
  const syncFile=file=>{docker('cp',path.join(frontend,file),proxy+':/usr/share/nginx/html/'+file);docker('exec',proxy,'chmod','a+r','/usr/share/nginx/html/'+file)};
  return{origin,page,context,cdp,frontend,errors,proxy,syncFile,close};
 }catch(error){if(created.includes(proxy))console.error(docker('logs','--tail','10',proxy));await close();throw error;}
}
module.exports={setupNginx,docker,root};

const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {setupNginx,docker,root}=require('./home_nginx_helpers.cjs');
const output=process.env.HOME_REGRESSION_EVIDENCE_DIR||path.join(root,'docs/design/home-redesign/execution/evidence/home-m4');
(async()=>{const s=await setupNginx(),results=[];try{
 const paths=['/pages/index.html','/static/js/home-data.js','/static/js/home-scene-core.js','/static/js/home-scene.js','/static/css/home-scene.css','/static/images/home-scene/v4/background.c094490a4d8e.webp','/static/images/home-thumbnails/v2/default.0d3cb97c2162.webp','/static/images/Index/Index.png','/static/images/home-scene/v4/manifest.json','/static/css/voice-entry.css'];
 const preferencePaths=['/pages/settings.html','/static/js/home-preferences.js'];
 for(const pathname of [...paths,...preferencePaths]){const response=await fetch(s.origin+pathname),cache=response.headers.get('cache-control');assert.equal(response.status,200,pathname);const bytes=Buffer.from(await response.arrayBuffer());
  if([...paths.slice(0,5),...preferencePaths].includes(pathname))assert.equal(cache,'no-cache','Homepage, settings and unversioned home modules must revalidate: '+pathname);
  else if(pathname.includes('.c094490a4d8e.')||pathname.includes('.0d3cb97c2162.'))assert.equal(cache,'public, max-age=31536000, immutable');
  else assert.ok(!cache?.includes('immutable'),'Unrelated or unversioned assets must not receive immutable cache');
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),crypto.createHash('sha256').update(fs.readFileSync(path.join(s.frontend,pathname))).digest('hex'));
  results.push({path:pathname,status:response.status,cacheControl:cache,bytes:bytes.length,etag:response.headers.get('etag')});
 }
 // Linux serves exact case; macOS existence checks are not the expectation.
 assert.equal((await fetch(s.origin+'/static/images/Index/index.png')).status,404);
 const missing=await fetch(s.origin+'/static/images/home-scene/v4/missing.0123456789ab.webp');assert.equal(missing.status,404);assert.ok(!missing.headers.get('cache-control')?.includes('immutable'));
 for(const route of ['/api/feed/list','/api/voice/probe','/admin/probe']){const response=await fetch(s.origin+route);assert.equal(response.status,200);assert.ok(!response.headers.get('cache-control')?.includes('immutable'));}
 // A returning client may still have the previous shared API script in a fresh
 // HTTP cache. Homepage-only versioning must acquire the current implementation.
 const indexPath=path.join(s.frontend,'pages/index.html'),currentHtml=fs.readFileSync(indexPath,'utf8'),apiFile=path.join(s.frontend,'static/js/api.js'),currentApi=fs.readFileSync(apiFile,'utf8'),apiTimes=fs.statSync(apiFile);
 const writeApi=text=>{fs.writeFileSync(apiFile,text);fs.utimesSync(apiFile,apiTimes.atime,apiTimes.mtime);s.syncFile('static/js/api.js');};
 fs.writeFileSync(indexPath,currentHtml.replace(/\/static\/js\/api\.js\?home_v=[a-f0-9]+/,'/static/js/api.js'));s.syncFile('pages/index.html');
 writeApi(fs.readFileSync(path.join(root,'docs/design/home-redesign/execution/evidence/home-m1/baseline/api.js'),'utf8')+'\nwindow.__apiCacheProbe="old";');
 await s.page.goto(s.origin+'/pages/index.html');assert.equal(await s.page.evaluate(()=>window.__apiCacheProbe),'old');
 await s.page.goto(s.origin+'/pages/login.html');
 writeApi(currentApi+'\nwindow.__apiCacheProbe="current";');fs.writeFileSync(indexPath,currentHtml);s.syncFile('pages/index.html');
 await s.page.goto(s.origin+'/pages/index.html');assert.equal(await s.page.evaluate(()=>window.__apiCacheProbe),'current','Current homepage must replace a warm cached previous API implementation');
 writeApi(currentApi);await s.cdp.send('Network.clearBrowserCache');
 // Two actual resource contents and a changed HTML URL; use native cache, not request routing.
 const first='/static/images/home-scene/v4/cache_probe.c094490a4d8e.webp',second='/static/images/home-scene/v4/cache_probe.2816096f87aa.webp';
 fs.copyFileSync(path.join(s.frontend,paths[5]),path.join(s.frontend,first));fs.copyFileSync(path.join(s.frontend,'/static/images/home-scene/v4/character.2816096f87aa.webp'),path.join(s.frontend,second));
 s.syncFile(first);s.syncFile(second);
 const htmlFile=path.join(s.frontend,'/pages/index.html'),original=fs.readFileSync(htmlFile,'utf8'),cacheEvents=[];
 s.cdp.on('Network.responseReceived',event=>{if(event.response.url.includes('/cache_probe.'))cacheEvents.push({url:event.response.url,status:event.response.status,fromDiskCache:!!event.response.fromDiskCache});});
 s.cdp.on('Network.requestServedFromCache',event=>cacheEvents.push({requestId:event.requestId,servedFromCache:true}));
 const originalTimes=fs.statSync(htmlFile);
 const writeVersion=url=>{fs.writeFileSync(htmlFile,original.replace('</body>',`<img id="cache-probe" src="${url}" alt=""></body>`));fs.utimesSync(htmlFile,originalTimes.atime,originalTimes.mtime);s.syncFile('pages/index.html');};
 writeVersion(first);await s.page.goto(s.origin+'/pages/index.html');await s.page.waitForFunction(()=>document.getElementById('cache-probe').naturalWidth>0);await s.page.reload();await s.page.waitForFunction(()=>document.getElementById('cache-probe').naturalWidth>0);
 writeVersion(second);await s.page.reload();assert.equal(await s.page.locator('#cache-probe').getAttribute('src'),second,'Same-size deployment with preserved timestamp must still acquire current HTML');await s.page.waitForFunction(()=>document.getElementById('cache-probe').naturalWidth>0);
 assert.ok(cacheEvents.some(event=>event.servedFromCache||event.fromDiskCache),'Warm visit must serve real cached resources');
 assert.ok(cacheEvents.some(event=>event.url?.endsWith(second)&&!event.fromDiskCache),'New HTML version must acquire new URL');
 assert.equal(s.errors.length,0);fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'step-014-cache-results.json'),JSON.stringify({scope:'Isolated local Linux Nginx 80 over HTTP and controlled API; not external HTTPS or phone verification',nginxImage:docker('image','inspect','nginx:alpine','--format','{{.Id}}'),results,caseSensitiveOldImage:true,missingHashNotImmutable:true,sharedApiWarmCacheUpdated:true,newVersionAcquired:true,cacheEvents,errors:s.errors},null,2)+'\n');console.log('PASS isolated Nginx cache, exact legacy filename, native warm cache and resource version update');
 }finally{await s.close()}})().catch(error=>{console.error(error);process.exitCode=1});

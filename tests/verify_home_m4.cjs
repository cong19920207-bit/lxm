// Local M4 code/integration verification. Phone/HTTPS/audio/Q201 remain separate.
const {spawnSync}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),output=path.join(root,'docs/design/home-redesign/execution/evidence/home-m4'),regression=path.join(output,'regression');
fs.mkdirSync(regression,{recursive:true});
const scripts=['test_home_cache','test_home_fallback','test_home_startup','test_home_startup_boundaries','test_home_request_context','test_home_data','test_home_lifecycle','test_home_motion','test_home_response','test_home_preferences','test_home_tilt','test_home_panels','test_home_quality','test_home_scene_boundaries','test_home_native_bfcache','test_home_final_layout','test_home_assets'];
const results=[],env={...process.env,HOME_REGRESSION_EVIDENCE_DIR:regression,HOME_EVIDENCE_DIR:regression};
for(const script of scripts){console.log('VERIFY '+script);const started=Date.now();const result=spawnSync(process.execPath,['tests/'+script+'.cjs'],{cwd:root,env,encoding:'utf8',timeout:150000});
 fs.writeFileSync(path.join(output,script+'.log'),(result.stdout||'')+(result.stderr||''));results.push({script,exitCode:result.status,durationMs:Date.now()-started});
 console.log((result.status===0?'PASS ':'FAIL ')+script);if(result.status!==0){process.stderr.write(result.stderr||result.stdout||String(result.error));break}}
const files=['frontend/pages/index.html','frontend/static/js/api.js','frontend/static/js/home-data.js','frontend/static/js/home-scene-core.js','frontend/static/js/home-scene.js','frontend/static/css/home-scene.css','nginx/nginx.conf','tests/test_h5_static_contract.py'];
const sourceSha256=Object.fromEntries(files.map(file=>[file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
fs.writeFileSync(path.join(output,'final-browser-verification.json'),JSON.stringify({scope:'Isolated Linux Nginx and actual frontend desktop Chrome. API/storage/sensor/low-FPS faults are controlled; no phone/HTTPS/real audio/Q201 acceptance claim.',results,sourceSha256},null,2)+'\n');
if(results.length!==scripts.length||results.some(item=>item.exitCode!==0))process.exitCode=1;else console.log('PASS '+scripts.length+' local final-source verification scripts');

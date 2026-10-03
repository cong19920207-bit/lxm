// Final-source verification, serial execution keeps timing/performance observations uncontended.
const {spawnSync}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const scripts=['test_home_startup','test_home_startup_boundaries','test_home_request_context','test_home_data','test_home_lifecycle','test_home_motion','test_home_response','test_home_preferences','test_home_tilt','test_home_panels','test_home_quality','test_home_scene_boundaries','test_home_native_bfcache','test_home_final_layout','test_home_assets'];
const evidence=path.join(root,'docs/design/home-redesign/execution/evidence/home-m3/compatibility');fs.mkdirSync(evidence,{recursive:true});
const env={...process.env,HOME_EVIDENCE_DIR:evidence};const results=[];
for(const script of scripts){console.log('VERIFY '+script);const start=Date.now();const result=spawnSync(process.execPath,['tests/'+script+'.cjs'],{cwd:root,env,encoding:'utf8',timeout:150000});process.stdout.write(result.stdout||'');if(result.stderr)process.stderr.write(result.stderr);results.push({script,exitCode:result.status,durationMs:Date.now()-start});if(result.status!==0)break}
const sourcePaths=['frontend/pages/index.html','frontend/static/js/api.js','frontend/static/js/home-data.js','frontend/static/js/home-scene-core.js','frontend/static/js/home-scene.js','frontend/static/css/home-scene.css','tests/test_h5_static_contract.py'];
const sourceSha256=Object.fromEntries(sourcePaths.map(file=>[file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
fs.writeFileSync(path.join(root,'docs/design/home-redesign/execution/evidence/home-m3/final-browser-verification.json'),JSON.stringify({scope:'Actual frontend on desktop Chrome, controlled API/storage/sensor faults separately labeled; no phone/real audio/Q201 claims',results,sourceSha256},null,2)+'\n');
if(results.length!==scripts.length||results.some(r=>r.exitCode!==0))process.exitCode=1;else console.log('PASS all '+scripts.length+' final-source browser verification scripts');

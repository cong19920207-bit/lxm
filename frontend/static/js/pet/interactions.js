import {petReason} from './api.js';
import {clientToPetScene,petSceneToClient} from './scene-viewport.js';
/** Pointer proof is collected only while an explicit interaction mode owns the canvas. */
export function mountInteractions(view,{root,api,principalId,storage=sessionStorage,sharedAvailable=true}){
 const scope=view.scope,scene=view.scene,canvas=root.querySelector('canvas'),panel=document.createElement('div');
 panel.className='pet-controls';root.append(panel);scope.own(()=>panel.remove());
 const grip=document.createElement('button');grip.type='button';grip.className='ball-grip';grip.dataset.petAction='toy';grip.setAttribute('aria-label','拖动小球陪它玩');grip.hidden=true;root.append(grip);scope.own(()=>grip.remove());
 const offer=document.createElement('aside');offer.className='pet-invitation-offer';offer.hidden=true;root.append(offer);scope.own(()=>offer.remove());
 const storageKey='pet-action:'+principalId;let attempt=null,mode=null,first=false,sending=false,pointer=null,accumulated=0,mergeCancel=null,auxCancel=null,unknown=false,skipShared=false;
 let generation=0;const receipts=new WeakMap();async function call(...args){const ticket=generation,value=await api.call(...args);if(ticket!==generation){if(value?.id&&['pending','invited'].includes(value.state)&&api.release)void api.release(value.kind,value.id);throw new DOMException('Released interaction','AbortError');}if(value&&typeof value==='object')receipts.set(value,ticket);return value;}
 const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const button=(text,action,style='primary')=>`<button type="button" class="${style}" data-pet-action="${action}">${escape(text)}</button>`;
 function save(){if(attempt)storage.setItem(storageKey,JSON.stringify({id:attempt.id,request_key:attempt.request_key,kind:attempt.kind,first}));else storage.removeItem(storageKey);}
 function positionGrip(point){const client=petSceneToClient(canvas,point),rect=root.getBoundingClientRect();grip.style.left=(client.x-rect.left)+'px';grip.style.top=(client.y-rect.top)+'px';}
 function resetGrip(){if(!pointer)positionGrip(mode==='joint'?{x:625,y:1415}:{x:400,y:1450});}
 function clear(){mergeCancel?.();auxCancel?.();mergeCancel=auxCancel=null;pointer=null;accumulated=0;mode=null;canvas.style.touchAction='';scene.setBall(null);scene.skipVisual();}
 async function playSharedResult(id){
  const current=()=>scope.active&&attempt?.id===id&&mode==='joint_done'&&view.route==='home';
  await scene.play('hand');if(!current())return;
  if(!skipShared)await scene.play('dog');if(!current())return;
  scene.skipVisual();render();
 }
 function render(){
  if(!scope.active)return;
  const canOffer=view.route==='home'&&view.companionMode==='together'&&!mode&&!unknown&&sharedAvailable&&view.pet?.availability?.joint_invitation?.allowed===true&&scene.inspect().available;offer.hidden=!canOffer;if(canOffer){const copy=view.pet?.messages?.invite;offer.innerHTML='<p>小梦：'+escape(copy&&copy!=='邀请小梦玩球'?copy:'你递球，我来接应它。要一起玩一会儿吗？')+'</p>'+button('接下小梦的邀请','joint-proposal');}
  const host=root.querySelector('[data-interaction-slot]');if(host&&panel.parentElement!==host)host.append(panel);root.dataset.interactionMode=mode||'idle';
  if(unknown)panel.innerHTML='<p>结果正在确认</p>'+button('查询互动结果','recover')+button('先歇一会儿','cancel','secondary');
  else if(mode==='touch')panel.innerHTML='<p>在它身体上轻轻滑动</p>'+button('轻抚一下','auxiliary')+button('先歇一会儿','cancel','secondary');
  else if(mode==='play')panel.innerHTML='<p>拖动小球，陪它玩一小会儿</p>'+button('轻轻滚球','play-auxiliary')+button('先歇一会儿','cancel','secondary');
  else if(mode==='invited')panel.innerHTML='<p>'+escape(view.pet?.messages?.invite||'邀请小梦玩球')+'</p><p>你把球递过来，我来接应它。</p>'+button('好，一起玩','joint-accept')+button('一会儿再玩','cancel','secondary');
  else if(mode==='joint')panel.innerHTML='<p>你递球，小梦接应，小狗追球。</p>'+button('把球递过去','joint-pass')+button('结束','cancel','secondary');
  else if(mode==='joint_done')panel.innerHTML='<p>'+escape(attempt?.result?.display_body||view.pet?.messages?.joint_ball||'你和小梦一起陪它玩了一次球。')+'</p>'+button('跳过演出','skip-shared','text-button')+button('再玩一次','joint-again')+button('结束','joint-end','secondary');
  else panel.innerHTML=view.route==='home'?(view.companionMode==='together'?button('邀请小梦玩球','joint-invite')+(sharedAvailable?'':'<p>小梦正在歇一会儿，现在先由你陪它。</p>'):'<div class="solo-action-row">'+button('抚摸','touch')+button('喂食','feed')+button((view.pet?.availability?.play?.alternative==='touch')?'轻柔陪伴':'陪玩','play')+'</div>'):'';
  panel.hidden=!host;grip.hidden=!['play','joint'].includes(mode);grip.dataset.drag=mode==='joint'?'joint':'play';grip.setAttribute('aria-label',mode==='joint'?'拖动小球到小梦手边':'拖动小球陪它玩');resetGrip();
  if(mode==='joint'||mode==='joint_done')panel.insertAdjacentHTML('beforeend','<div class="shared-steps"><span class="'+(mode==='joint_done'||attempt?.payload?.progress>=1?'done':'')+'">你来递球</span><span class="'+(mode==='joint_done'||attempt?.payload?.progress>=2?'done':'')+'">小梦接应</span><span class="'+(mode==='joint_done'?'done':'')+'">一起完成</span></div>');
  for(const control of panel.querySelectorAll('button')){
   const action=control.dataset.petAction;
   const availability=action==='joint-invite'?view.pet?.availability?.joint_ball:view.pet?.availability?.[action];
   const alternative=action==='play'&&availability?.alternative==='touch'&&view.pet?.availability?.touch?.allowed!==false;
   const denied=availability?.allowed===false&&!alternative;
   control.disabled=(view.pet?.interactions_enabled===false&&!['recover','cancel','joint-end','skip-shared'].includes(action))||denied||(!sharedAvailable&&action==='joint-invite')||(!scene.inspect().available&&scene.inspect().renderMode!=='simple'&&!['recover','cancel','joint-end','skip-shared'].includes(action));
   control.title=denied?petReason(availability.reason):'';
  }

 }
 async function accept(result){
  if(!scope.active||(result&&receipts.has(result)&&receipts.get(result)!==generation))return;
  unknown=false;
  if(result?.pet&&result.state!=='done')view.setPet(result.pet);
  if(result?.state==='done'){
   if(result.kind==='joint_ball'){
    clear();attempt={...attempt,...result};mode='joint_done';skipShared=false;save();view.setPet(result.pet);render();root.dispatchEvent(new CustomEvent('pet:completed',{detail:result}));
    // The saved result releases the request lock; its animation must not block replay.
    void playSharedResult(result.id);return;
   }
   clear();view.setPet(result.pet);view.notify((result.expression?.body??view.pet?.messages?.[result.kind]??(result.kind==='feed'?'它低下头，认真吃起了食物。':result.kind==='play'?'它追着小球，摇起了尾巴。':'它把头轻轻留在你的手边。'))+(result.result?.reward_reason==='cap'?' 今天的亲近已经足够，陪伴的回应仍然在。':''));
   if(result.kind==='feed')await scene.play('feed');else if(result.kind==='play')await scene.play('dog');else await scene.respondToParticipation(result.result?.reaction);
   if(!scope.active)return;scene.skipVisual();if(first)view.finishFirstTouch();first=false;attempt=null;save();render();root.dispatchEvent(new CustomEvent('pet:completed',{detail:result}));
  }else if(result?.state==='invited'){attempt={...attempt,...result};mode='invited';save();render();}
  else if(result?.state==='pending'){attempt={...attempt,...result};if(['touch','play','joint_ball'].includes(attempt.kind)){unknown=false;mode=attempt.kind==='joint_ball'?'joint':attempt.kind;canvas.style.touchAction=mode==='touch'?'none':'';if(mode==='joint')void scene.play('shared-waiting');else if(mode==='play')void scene.play('play');save();}else unknown=true;render();}
  else{clear();attempt=null;save();view.notify(result?.result?.reason==='low_energy'?(view.pet?.messages?.low_energy||'它有点累了，可以轻轻摸摸它。'):result?.state==='refused'?(view.pet?.messages?.refuse_feed||'它闻了闻，已经吃饱啦。'):result?.result?.reason==='touch_incomplete'?(view.pet?.messages?.touch_incomplete||'这次还没摸够，可以再试试。'):(view.pet?.messages?.rest||'这次先休息。'));if(result?.state==='refused'&&result?.kind==='feed'){await scene.play('refuse');}render();}
 }
 async function beginTouch(isFirst=false,kind='touch'){
  if(view.pet?.interactions_enabled===false)return;
  if(sending||mode||unknown)return;sending=true;first=isFirst;
  attempt={request_key:crypto.randomUUID(),kind};save();
  try{
   const result=await call('/interactions','POST',{kind,request_key:attempt.request_key});
   if(!scope.active)return;attempt={...attempt,...result};save();
   if(result.state!=='pending'){await accept(result);return;}
   mode=kind;accumulated=0;canvas.style.touchAction='none';if(kind==='play')void scene.play('play');render();
  }catch(error){if(error.name==='AbortError')return;if(!scope.active)return;if(error.code){attempt=null;save();view.notify(error.message);}else unknown=true;render();}finally{sending=false;}
 }
 async function finish(evidence){
  if(sending||!attempt?.id)return;sending=true;mergeCancel?.();mergeCancel=null;
  try{await accept(await call('/interactions/'+attempt.id+'/finish','POST',{evidence}));}
  catch(error){if(error.name==='AbortError')return;if(scope.active){unknown=true;clear();render();view.notify('稍后查询原互动结果。');}}finally{sending=false;}
 }
 async function recover(){
  if(sending||!attempt)return;sending=true;
  try{const result=await call(attempt.id?'/interactions/'+attempt.id:'/interaction-requests/'+encodeURIComponent(attempt.request_key));await accept(result);}
  catch(error){if(error.name==='AbortError')return;view.notify(error.message);}finally{sending=false;}
 }
 async function feed(){
  if(view.pet?.interactions_enabled===false)return;
  if(sending||mode||unknown)return;sending=true;first=false;attempt={request_key:crypto.randomUUID(),kind:'feed'};save();
  try{await accept(await call('/feed','POST',{request_key:attempt.request_key}));}
  catch(error){if(error.name==='AbortError')return;if(error.code){attempt=null;save();view.notify(error.message);}else{unknown=true;render();}}finally{sending=false;}
 }
 async function jointAction(action){
  if(view.pet?.interactions_enabled===false&&!['cancel','joint-end','skip-shared'].includes(action))return;
  if(sending)return;
  if(!sharedAvailable){view.notify('仅自己陪伴预览中，小梦暂不参与。');return;}
  if(!scene.inspect().available){view.notify('场景素材还未就绪，请稍后再试。');return;}
  sending=true;first=false;
  try{
   if(action==='invite'||action==='proposal'){
    const direct=mode==='joint_done'||action==='proposal';if(direct){clear();attempt=null;}if(mode||unknown)return;
    attempt={request_key:crypto.randomUUID(),kind:'joint_ball'};save();
    let result=await call('/joint/invitations','POST',{request_key:attempt.request_key,direct,initiator:action==='proposal'?'invitation':'user'});if(result?.payload?.entry==='user'){attempt={...attempt,...result};save();result=await call('/joint/'+attempt.id+'/accept','POST',{resources_ready:scene.inspect().available});}await accept(result);
   }else if(action==='accept'){
    const result=await call('/joint/'+attempt.id+'/accept','POST',{resources_ready:scene.inspect().available});attempt={...attempt,...result};save();
    if(result.state==='pending'){mode='joint';void scene.play('shared-waiting');render();}else await accept(result);
   }else if(action==='pass'){
    const delivery=scene.play('delivery');await call('/joint/'+attempt.id+'/pass','POST',{});
    const [result]=await Promise.all([call('/joint/'+attempt.id+'/resolve','POST',{}),delivery]);await accept(result);
   }
  }catch(error){if(error.name==='AbortError')return;if(!scope.active)return;if(error.code)view.notify(error.message);else{unknown=true;clear();render();}}finally{sending=false;}
 }
 async function cancel(){
  if(!attempt){clear();unknown=false;render();return;}
  if(sending)return;
  clear();sending=true;
  try{if(!attempt.id){const result=await call('/interaction-requests/'+encodeURIComponent(attempt.request_key));if(result)attempt={...attempt,...result};}
   if(attempt.id)await accept(await call(attempt.kind==='joint_ball'?'/joint/'+attempt.id+'/cancel':'/interactions/'+attempt.id+'/finish','POST',{cancel:true}));else{attempt=null;unknown=false;save();render();}
  }catch(error){if(error.name==='AbortError')return;unknown=true;render();view.notify(error.message);}finally{sending=false;}
 }
 function endPointer(cancelled=false){
  if(!pointer)return;
  if(pointer.valid&&pointer.moved&&!cancelled)accumulated+=Math.max(0,performance.now()-pointer.started);
  pointer=null;
  if(cancelled){accumulated=0;scene.skipVisual();return;}
  mergeCancel?.();mergeCancel=scope.timeout(()=>{if(accumulated>0)void finish({duration_ms:accumulated,moved:true,region:'body'});},(attempt?.payload?.merge_seconds??1.2)*1000);
 }
 scope.listen(canvas,'pointerdown',event=>{
  if(mode!=='touch'||sending||unknown||!scene.hitTest(event))return;
  event.preventDefault();mergeCancel?.();mergeCancel=null;canvas.setPointerCapture?.(event.pointerId);
  pointer={id:event.pointerId,started:performance.now(),x:event.clientX,y:event.clientY,moved:false,valid:true};
 });
 scope.listen(canvas,'pointermove',event=>{if(!pointer||pointer.id!==event.pointerId)return;if(!scene.hitTest(event)){pointer.valid=false;return;}if(Math.hypot(event.clientX-pointer.x,event.clientY-pointer.y)>4){pointer.moved=true;void scene.play('pet');}});
 scope.listen(canvas,'pointerup',()=>endPointer());scope.listen(canvas,'pointercancel',()=>endPointer(true));
 scope.listen(panel,'click',event=>{const action=event.target.closest('[data-pet-action]')?.dataset.petAction;
  if(action==='touch')void beginTouch();if(action==='recover')void recover();if(action==='cancel')void cancel();
  if(action==='feed')void feed();
  if(action==='joint-invite'||action==='joint-again')void jointAction('invite');
  if(action==='joint-accept')void jointAction('accept');if(action==='joint-pass')void jointAction('pass');
  if(action==='skip-shared'){skipShared=true;scene.skipVisual();}
  if(action==='joint-end'){clear();attempt=null;save();view.go('home');render();}
  if(action==='play')void beginTouch(false,(view.pet?.availability?.play?.alternative==='touch')?'touch':'play');
  if(action==='play-auxiliary'&&mode==='play'&&!sending&&!auxCancel){const ms=attempt.payload.minimum_seconds*1000;auxCancel=scope.timeout(()=>{auxCancel=null;void finish({duration_ms:ms,auxiliary:true,region:'toy'});},ms);}
  if(action==='auxiliary'&&mode==='touch'&&!sending&&!auxCancel){void scene.play('pet');const ms=(attempt.payload.minimum_seconds||.8)*1000;auxCancel=scope.timeout(()=>{auxCancel=null;void finish({duration_ms:ms,auxiliary:true,region:'body'});},ms);}
 });
 scope.listen(offer,'click',event=>{if(event.target.closest('[data-pet-action=joint-proposal]'))void jointAction('proposal');});
 scope.listen(grip,'pointerdown',event=>{if(!['play','joint'].includes(mode)||sending)return;event.preventDefault();grip.setPointerCapture(event.pointerId);pointer={id:event.pointerId,started:performance.now(),moved:false,x:event.clientX,y:event.clientY,distance:0};});
 scope.listen(grip,'pointermove',event=>{if(!pointer||pointer.id!==event.pointerId||sending)return;const point=clientToPetScene(canvas,event),previous=clientToPetScene(canvas,{clientX:pointer.x,clientY:pointer.y});pointer.distance+=Math.hypot(point.x-previous.x,point.y-previous.y);pointer.x=event.clientX;pointer.y=event.clientY;pointer.moved=pointer.distance>=20;pointer.point=point;const ball={x:Math.max(160,Math.min(700,point.x)),y:Math.max(1260,Math.min(1520,point.y))};scene.setBall(ball);positionGrip(ball);if(mode==='play'&&!auxCancel){const ms=attempt.payload.minimum_seconds*1000;auxCancel=scope.timeout(()=>{auxCancel=null;if(pointer?.moved)void finish({duration_ms:ms,moved:true,region:'toy'});},ms);}});
 scope.listen(grip,'pointerup',()=>{if(!pointer)return;const p=pointer;pointer=null;auxCancel?.();auxCancel=null;if(mode==='joint'){if(p.distance>=55&&p.point&&Math.hypot(p.point.x-490,p.point.y-1360)<=80)void jointAction('pass');else{scene.setBall(null);render();view.notify('再递近一点，小梦会接住。');}}else if(mode==='play')void finish({duration_ms:performance.now()-p.started,moved:p.moved,region:'toy'});});
 scope.listen(grip,'pointercancel',()=>{pointer=null;scene.setBall(null);void cancel();});
 scope.listen(root,'pet:first-touch',()=>void beginTouch(true));scope.listen(root,'pet:render',render);
 scope.observe(new ResizeObserver(resetGrip),canvas);
 scope.listen(document,'visibilitychange',()=>{if(document.hidden&&attempt){if(api.release)void release();else if(mode)void cancel();}});
 scope.own(()=>{clear();if(attempt&&!unknown&&attempt.state!=='done')void (api.release?api.release(attempt.kind,attempt.id,attempt.request_key):api.call(attempt.kind==='joint_ball'?'/joint/'+attempt.id+'/cancel':'/interactions/'+attempt.id+'/finish','POST',attempt.kind==='joint_ball'?{}:{cancel:true})).catch(()=>{});});
 try{attempt=JSON.parse(storage.getItem(storageKey)||'null');if(attempt){first=Boolean(attempt.first);unknown=true;void recover();}}catch(_){}
 async function release(){if(!attempt||unknown||attempt.kind==='feed'||attempt.state==='done')return;const a=attempt;generation++;if(api.release){const ok=await api.release(a.kind,a.id,a.request_key);if(ok&&attempt===a){clear();attempt=null;unknown=false;sending=false;save();render();}else if(attempt===a){clear();unknown=true;sending=false;save();render();}}else await cancel();}
 render();return {beginTouch,cancel,recover,release,inspect:()=>({mode,unknown,attempt,first})};
}

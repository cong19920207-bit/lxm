import {petReason} from './api.js';
/** Real Canvas capture, explicit archive, and read-only recovery for lost responses. */
export function mountPhotos(view,{root,api,principalId,storage=sessionStorage,sharedAvailable=true}){
 const scope=view.scope,scene=view.scene,panel=document.createElement('section'),key='pet-photo:'+principalId;
 panel.className='pet-photo-controls';root.append(panel);scope.own(()=>panel.remove());
 let generation=0;let attempt=null,busy=false,unknown=false,prompt=false,promptChecked=false;
 const button=(text,action)=>`<button type="button" class="primary" data-photo="${action}">${text}</button>`;
 function save(){if(attempt)storage.setItem(key,JSON.stringify({id:attempt.id,request_key:attempt.request_key}));else storage.removeItem(key);}
 function render(){
  if(!scope.active)return;
  const host=root.querySelector('[data-photo-controls-slot]');if(host&&panel.parentElement!==host)host.append(panel);panel.hidden=!host;
  if(unknown)panel.innerHTML='<p>正在确认留影结果</p>'+button('查询留影结果','recover');
  else if(attempt&&['photo','photo-review'].includes(view.route)){
   if(attempt.payload?.captured&&attempt.photo?.url){panel.innerHTML='<p>小梦替你们留好了镜头，看看这一张。</p><img alt="刚刚拍下的照片" style="max-width:100%">'+button('收进共同事件册','archive')+button('先不保存','cancel');panel.querySelector('img').src=attempt.photo.url;}
   else if(attempt.photo&&['uploading','unknown','ready'].includes(attempt.photo.state))panel.innerHTML='<p>正在确认照片存储结果。</p>'+button('查询留影结果','recover')+button('先不保存','cancel');
   else panel.innerHTML='<p>你来吸引它，小梦准备镜头。</p>'+button(attempt.payload?.prepared?'一起留一张':view.pet?.tired?'等它看向镜头':'吸引它站好',attempt.payload?.prepared?'capture':'prepare')+button('先不拍了','cancel');
  }else if((view.route==='home'&&view.companionMode==='together'&&!view.interactions?.inspect().mode)||view.route==='growth')panel.innerHTML=(prompt?'<p>它又长大了一点，要不要一起留张影？</p>'+button('一起留影','start')+button('稍后','later'):'')+button('共同留影','start');
  else panel.innerHTML='';
  for(const control of panel.querySelectorAll('button')){const start=control.dataset.photo==='start',reason=start?(view.pet?.availability?.photo?.reason||(!scene.inspect().available?'scene_not_ready':null)):null;control.disabled=busy||Boolean(reason)||(view.pet?.interactions_enabled===false&&!['cancel','recover','later'].includes(control.dataset.photo));control.title=reason?petReason(reason):'';}
 }
 async function receive(result){
  if(!scope.active)return;unknown=false;
  if(result?.state==='done'){attempt=null;save();view.setPet(result.pet);root.dispatchEvent(new CustomEvent('pet:completed',{detail:result}));view.go('album');view.notify('这一刻，已经收进共同事件册。');render();}
  else if(result?.state==='pending'){attempt={...attempt,...result};save();view.go(attempt.payload?.captured?'photo-review':'photo');scene.applyState(result.pet);render();}
  else{attempt=null;save();view.go('home');render();}
 }
 async function act(action){
  if(view.pet?.interactions_enabled===false&&!['cancel','recover','later'].includes(action))return;
  if(busy)return;
  if(action==='later'){prompt=false;render();return;}
  if(action==='start'&&!sharedAvailable){view.notify('仅自己陪伴预览中，小梦暂不参与。');return;}
  const ticket=generation,receiveCurrent=async value=>{if(ticket!==generation||!scope.active){if(value?.id&&value.state==='pending'&&api.release)void api.release('photo',value.id);return;}await receive(value);};
  busy=true;render();
  try{
   if(action==='start'){
    scene.endPreview();if(!scene.inspect().available)throw new Error('场景素材还未就绪，暂时不能留影。');
    prompt=false;attempt={request_key:crypto.randomUUID()};save();await receiveCurrent(await api.call('/photos','POST',{request_key:attempt.request_key,resources_ready:true}));
   }else if(action==='prepare'){
    const result=await api.call('/photos/'+attempt.id+'/prepare','POST',{});await receiveCurrent(result);
    // Low energy keeps the approved prone/open-eyed pose; no forced standing animation.
    if(!view.pet.tired)await scene.play('pet');
   }else if(action==='capture'){
    scene.skipVisual();const snapshot=scene.snapshot();if(!snapshot?.data_url){const error=new Error('场景尚未准备好，请稍后再拍。');error.code='scene_not_ready';throw error;}
    await receiveCurrent(await api.call('/photos/'+attempt.id+'/capture','POST',{snapshot,resources_ready:scene.inspect().available}));
   }else if(action==='archive')await receiveCurrent(await api.call('/photos/'+attempt.id+'/archive','POST',{resources_ready:scene.inspect().available}));
   else if(action==='cancel')await receiveCurrent(await api.call('/photos/'+attempt.id+'/cancel','POST',{}));
   else if(action==='recover')await receiveCurrent(await api.call(attempt.id?'/photos/'+attempt.id:'/interaction-requests/'+encodeURIComponent(attempt.request_key)));
  }catch(error){if(!scope.active||ticket!==generation)return;view.notify(error.message);if(!error.code&&attempt){unknown=true;render();}}finally{busy=false;render();}
 }
 async function checkPrompt(){
  if(promptChecked||view.route!=='home'||!view.pet||view.pet.stage==='puppy')return;promptChecked=true;
  try{const result=await api.call('/photos/growth-prompt','POST',{});if(scope.active){prompt=Boolean(result.show);render();}}catch(_){}
 }
 scope.listen(panel,'click',event=>{const action=event.target.closest('[data-photo]')?.dataset.photo;if(action)void act(action);});
 scope.listen(root,'pet:render',()=>{render();void checkPrompt();});
 scope.listen(document,'visibilitychange',()=>{if(document.hidden&&attempt){if(api.release)void release();else if(!busy&&!unknown)void act('cancel');}});
 scope.own(()=>{if(attempt&&!unknown)void (api.release?api.release('photo',attempt.id,attempt.request_key):api.call('/photos/'+attempt.id+'/cancel','POST',{})).catch(()=>{});});
 try{attempt=JSON.parse(storage.getItem(key)||'null');if(attempt){unknown=true;void act('recover');}}catch(_){}
 async function release(){if(!attempt||unknown)return;const a=attempt;generation++;if(api.release){const ok=await api.release('photo',a.id,a.request_key);if(ok&&attempt===a){attempt=null;unknown=false;save();if(scope.active)view.go('home');}else if(attempt===a){unknown=true;save();render();}}else if(!busy)await act('cancel');}
 render();void checkPrompt();return {release,inspect:()=>({attempt,unknown,prompt}),act};
}

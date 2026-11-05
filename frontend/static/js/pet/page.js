import {PageScope} from '../app/page-context.js';
import {createPetScene,mountStagePreview} from './scene.js';
import {mountInteractions} from './interactions.js';
import {mountPhotos} from './photos.js';
import {mountRecords} from './records.js';
import {mountReturn} from './return.js';
import {mountExpression} from './expression.js';
import {mountActivity} from './activity.js';
import {mountBirthday} from './birthday.js';
import {renderPetView,asset} from './views.js';
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const button=(text,action)=>`<button type="button" data-action="${action}">${text}</button>`;

/** Isolated formal component. The application entry/router is wired by STEP-026. */
export async function mountPet({root,api,principalId=null,scope=new PageScope(),login=()=>{},onFirstTouch=()=>{},storage=sessionStorage,sharedAvailable=true,onHome=()=>location.assign('/pages/index.html')}) {
  let pet=null,route='loading',draft='',requestKey=null,busy=false,scene=null,firstGuide=false,previewScope=null,preferenceDetail=null,intro={adoption_enabled:true},companionMode='solo',renameDraft=null;
  scope.own(()=>previewScope?.dispose());
  const storageKey='pet-adoption:'+principalId,renameKey='pet-rename:'+principalId;let renamePending=null;
  try{renamePending=JSON.parse(storage.getItem(renameKey)||'null');}catch(_){}
  try {const saved=JSON.parse(storage.getItem(storageKey)||'null');if(saved){draft=saved.name||'';requestKey=saved.request_key||null;}}catch(_){}
  root.classList.add('pet-feature');
  root.innerHTML='<div class="pet-scene-wrap"><canvas aria-label="房间里的小狗"></canvas></div><section class="pet-panel"></section><p class="pet-message" role="status" aria-live="polite" hidden></p>';
  const panel=root.querySelector('.pet-panel'),canvas=root.querySelector('canvas'),message=root.querySelector('[role=status]');
  let hideMessage=null;function notify(text){if(!scope.active)return;hideMessage?.();message.textContent=text;message.hidden=!text;if(text)hideMessage=scope.timeout(()=>message.hidden=true,4500);}
  function render(){
    if(!scope.active)return;previewScope?.dispose();previewScope=null;root.dataset.route=route;scene?.skipVisual();scene?.setVisible(['home','success','photo','return','return-review'].includes(route));
    panel.innerHTML=renderPetView({route,pet,draft,principalId,companionMode,preferenceDetail,intro,renameDraft,renamePending});
    if(route==='growth'){
      previewScope=new PageScope({current:()=>scope.active});
      mountStagePreview(panel.querySelector('[data-stage-preview]'),scene,previewScope,{resources:pet?.appearance?.resources,onSelect(stage){
        panel.querySelector('.pet-growth-portrait img').src=pet?.appearance?.resources?.[stage==='growing'?'juvenile':stage]||asset(stage);
        panel.querySelector('[data-stage-description]').textContent={puppy:'软软的垂耳，圆圆的额头和短腿。现在的每一天，都在慢慢长大。',growing:'腿和身体慢慢拉长，耳朵开始立起来，胸颈的毛还没有完全丰满。',adult:'耳朵自然立起，体态更结实，胸颈的毛也变得丰厚。'}[stage];
      }});
    }
    const retry=panel.querySelector('[data-scene-retry]');if(retry)retry.hidden=scene?.inspect().available!==false;
    root.dispatchEvent(new CustomEvent('pet:render',{detail:{route,pet,scene,firstGuide}}));
  }
  async function accept(value){pet=value;requestKey=null;storage.removeItem(storageKey);route='success';firstGuide=true;scene?.applyState(pet);render();if(pet.messages?.welcome)notify(pet.messages.welcome);}
  async function recover(){const value=await api.adoptionResult();if(value)await accept(value);else{requestKey=null;storage.removeItem(storageKey);route='review';render();notify('尚未领养，可重新确认。');}}
  async function recoverRename(){if(!renamePending)return;const value=await api.call('/rename-requests/'+encodeURIComponent(renamePending.request_key));if(!scope.active)return;if(value){pet=value.pet;renamePending=null;storage.removeItem(renameKey);route='profile';render();}else notify('还没查到这次改名结果，请稍后再查询。');}
  async function read(){try{pet=principalId?await api.read():null;if(!scope.active)return;route=pet?(renamePending?'rename-unknown':'home'):'intro';scene?.applyState(pet||{});render();}catch(_){route='error';render();}}
  async function submitRename(){try{pet=await api.rename(renamePending);renamePending=null;storage.removeItem(renameKey);route='profile';render();}catch(error){if(error.code){renamePending=null;storage.removeItem(renameKey);}else{route='rename-unknown';render();}throw error;}}
  async function action(action){
    if(busy)return;busy=true;notify('');
    try{
      if(['home','profile','growth','records','album','rename-form'].includes(action)){await Promise.all([view.interactions?.release(),view.photos?.release()]);if(!scope.active)return;}
      if(action==='exit'){await Promise.all([view.interactions?.release(),view.photos?.release()]);if(scope.active)onHome();}
      else if(action==='intro-touch'){const target=panel.querySelector('.intro-dog');target?.classList.add('responding');scope.timeout(()=>target?.classList.remove('responding'),1100);}
      else if(action.startsWith('mode:')){if(view?.interactions?.inspect().attempt||view?.photos?.inspect().attempt)return;companionMode=action.split(':')[1];render();}
      else if(action==='reload-assets'){await scene.retryResources(pet?.appearance?.resources);render();}
      else if(action==='rename-form'){renameDraft=pet?.name;route=renamePending?'rename-unknown':'rename';render();}
      else if(['intro','form','home','profile','growth','records','album'].includes(action)){if(action!=='growth')scene?.endPreview();route=action;render();}
      else if(action==='begin'){if(!principalId)login();else{route='form';render();}}
      else if(action==='review'){draft=panel.querySelector('input').value.trim();if(!draft||[...draft].length>12)throw new Error('请输入 1—12 个可见字符的名字');storage.setItem(storageKey,JSON.stringify({name:draft}));route='review';render();}
      else if(action==='confirm'){
        if(!panel.querySelector('[name=acknowledged]').checked)throw new Error('请先勾选“我已了解”');
        requestKey=requestKey||crypto.randomUUID();storage.setItem(storageKey,JSON.stringify({name:draft,request_key:requestKey}));
        try{const value=await api.adopt({name:draft,acknowledged:true,request_key:requestKey});if(scope.active)await accept(value);}
        catch(error){if(error.code){requestKey=null;storage.setItem(storageKey,JSON.stringify({name:draft}));throw error;}route='unknown';render();}
      }
      else if(action==='recover')await recover();
      else if(action==='skip'){firstGuide=false;route='home';render();}
      else if(action==='first-touch'){onFirstTouch({pet,scene,scope});root.dispatchEvent(new CustomEvent('pet:first-touch'));}
      else if(action==='rename'){renameDraft=panel.querySelector('[name=rename]').value.trim();if(!renameDraft||[...renameDraft].length>12)throw new Error('请输入 1—12 个可见字符的名字');renamePending={name:renameDraft,request_key:crypto.randomUUID()};storage.setItem(renameKey,JSON.stringify(renamePending));await submitRename();}
      else if(action==='recover-rename')await recoverRename();
      else if(action==='retry-rename'&&renamePending)await submitRename();
      else if(action==='read')await read();
      else if(action.startsWith('preference:')){preferenceDetail=await api.call('/preferences/'+action.split(':')[1]);route='preference';render();}
    }catch(error){notify(error.message);}finally{busy=false;}
  }
  scope.listen(panel,'click',event=>{const target=event.target.closest('[data-action]');if(target)void action(target.dataset.action);});
  scope.listen(canvas,'click',()=>{if(route==='intro')void scene?.play('pet');});
  render();
  if(api.call){try{intro=await api.call('/intro')||intro;}catch(_){} }
  scene=await createPetScene({canvas,scope});
  if(!scope.active)return;
  let resourceStatus=String(scene.inspect().available)+':'+String(scene.inspect().fallback);
  scope.own(scene.subscribe(state=>{const next=String(state.available)+':'+String(state.fallback);if(next!==resourceStatus){resourceStatus=next;render();}}));
  if(requestKey&&principalId){route='unknown';render();try{await recover();}catch(_){notify('暂时没能确认，请稍后再查询。');}}else await read();
  const view={scene,scope,read,notify,render,get pet(){return pet;},get route(){return route;},get companionMode(){return companionMode;},
    setPet(value){pet=value;scene?.applyState(value);render();},go(value){route=value;render();},
    finishFirstTouch(){firstGuide=false;route='home';render();},unmount:()=>scope.dispose()};
  view.return=await mountReturn(view,{root,api,principalId});
  view.interactions=mountInteractions(view,{root,api,principalId,storage,sharedAvailable});
  view.photos=mountPhotos(view,{root,api,principalId,storage,sharedAvailable});
  view.records=mountRecords(view,{root,api});void mountBirthday(view,{root,api});view.activity=mountActivity(view,{root,api,principalId});view.expression=mountExpression(view,{root,api});return view;
}

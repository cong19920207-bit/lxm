import {mountPet} from './page.js';
import {createPetApi,createPetRelease} from './api.js';
export async function mount(context){
 const {root,scope,services}=context;
 if(services.audio&&services.shared){
  await scope.adopt(services.resources.style('css/bgm.css'),release=>release());
  for(const name of ['bgm-page','bgm-record','bgm-bubble']){await services.shared.script('js/'+name+'.js');if(!context.valid())return {unmount(){}};}
  const audioPage=services.audio.attachPage(context,'content'),bubble=globalThis.BgmBubble.mount(audioPage);
  if(bubble)context.cleanup(()=>bubble.destroy());
 }

 const api=createPetApi({signal:context.signal,request:(path,options)=>services.auth.request(options.method,path,options.body?JSON.parse(options.body):undefined,{signal:context.signal,isCurrent:context.valid,routeEpoch:context.routeEpoch,routeCurrent:context.valid,authPolicy:'silent-visitor'})});
 const original=services.auth.requestContext({routeCurrent:()=>true});api.release=createPetRelease({token:original.token,request:services.auth.fetcher});
 const view=await mountPet({root:root.querySelector('[data-pet-root]'),scope,api,principalId:context.principalId,login:()=>context.router.navigate('/pages/login.html'),onHome:()=>context.router.navigate('/pages/index.html')});
 if(!view||!context.valid())return {unmount(){}};
 function show(){
  const p=view.pet;
  root.classList.toggle('pet-maintenance',p?.interactions_enabled===false);
  const notice=root.querySelector('[data-pet-maintenance]');notice.hidden=p?.interactions_enabled!==false;
 }
 scope.listen(root,'pet:render',show);show();
 scope.interval(async()=>{if(document.hidden||view.route!=='home'||!view.pet||view.scene.inspect().phase!=='idle'||view.interactions.inspect().attempt||view.photos.inspect().attempt)return;try{const p=await api.read();if(context.valid()&&p&&p.record_version>=view.pet.record_version)view.setPet(p);}catch(_){}},30000);
 return {unmount:()=>view.unmount(),inspect:()=>view};
}

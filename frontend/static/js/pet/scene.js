import {PageScope} from '../app/page-context.js';
import {createApprovedPetScene} from './scene-engine.js';
import {clientToPetScene} from './scene-viewport.js';

const base='/static/pet-assets/v4/';
export const DEFAULT_RESOURCES=Object.freeze(Object.fromEntries(['room','rest','puppy','blink','ball','juvenile','adult','feeding'].map(k=>[k,base+k+'.webp']).concat(['puppy','juvenile','adult'].map(k=>[k+'-low-energy',base+k+'-low-energy-v4.png']))));
const engineStage={puppy:'puppy',growing:'juvenile',adult:'adult'},labels={puppy:'幼犬',growing:'成长期',adult:'成年'};

export async function createPetScene({canvas,scope=new PageScope(),stage='puppy',tired=false,resourceVersion='approved-v4',resources=DEFAULT_RESOURCES,onVisualEnd=()=>{},renderMode=(navigator.hardwareConcurrency&&navigator.hardwareConcurrency<3?'simple':'full')}){
 let engine=null,actualStage=stage,preview=null,currentTired=tired,disposed=false,available=false,fallback=false,epoch=0,pending=null,version=resourceVersion,bindings={...DEFAULT_RESOURCES,...resources},recordVersion=null;
 let mappingVersion=null,deferredMapping=null;
 async function applyMapping(value){if(!value)return;if(pending){deferredMapping=value;return;}version=value.resource_version;if(value.mapping_version===mappingVersion)return;mappingVersion=value.mapping_version;await load(value.resources);}
 function flushMapping(){const value=deferredMapping;deferredMapping=null;if(value)void applyMapping(value);}
 const subscribers=new Set(),valid=()=>!disposed&&scope.active;
 function notify(){if(valid())for(const callback of subscribers)callback(adapter.inspect());}
 function fallbackDraw(){
  if(!valid())return;
  const rect=canvas.getBoundingClientRect();canvas.width=Math.max(1,Math.round(rect.width));canvas.height=Math.max(1,Math.round(rect.height));
  const context=canvas.getContext('2d');if(context){context.fillStyle='#eee6dc';context.fillRect(0,0,canvas.width,canvas.height);context.fillStyle='#655b52';context.font='18px sans-serif';context.textAlign='center';context.fillText('小狗在房间里',canvas.width/2,canvas.height*.58);context.font='13px sans-serif';context.fillText('轻触它，或使用下方互动',canvas.width/2,canvas.height*.62);}
  canvas.dataset.actualStage=actualStage;canvas.dataset.stage=engineStage[preview||actualStage];canvas.dataset.pose='simplified';canvas.dataset.resourceState='fallback';canvas.dataset.phase='idle';canvas.dataset.frames=String(Number(canvas.dataset.frames||0)+1);
 }
 function sync(){if(!valid())return;canvas.dataset.actualStage=actualStage;if(engine){engine.setStage(engineStage[preview||actualStage]);engine.setEnergy(currentTired?10:75);}else fallbackDraw();notify();}
 async function load(nextBindings=bindings){
  const generation=++epoch;engine?.dispose();engine=null;available=false;bindings={...DEFAULT_RESOURCES,...nextBindings};notify();
  if(renderMode==='simple'){fallback=true;fallbackDraw();notify();return;}
  try{
   const loaded=await createApprovedPetScene(canvas,bindings,{signal:scope.signal});
   if(!valid()||generation!==epoch){loaded.dispose();return;}
   engine=loaded;available=true;fallback=false;canvas.dataset.resourceState='ready';
   engine.onEnd(phase=>{if(!valid())return;const current=pending;pending=null;current?.resolve({phase,skipped:false});try{onVisualEnd(phase);}catch(error){scope.report(error);}flushMapping();});
   sync();engine.start();
  }catch(error){
   if(!valid()||generation!==epoch||error.name==='AbortError')return;
   available=false;fallback=true;fallbackDraw();notify();
  }
 }
 const adapter={
  applyState(state){if(!valid())return;if(state.stage in engineStage)actualStage=state.stage;currentTired=Boolean(state.tired);recordVersion=state.record_version??recordVersion;sync();if(state.appearance)void applyMapping(state.appearance);},
  previewStage(value){if(!valid()||!(value in engineStage))return;preview=value;sync();},
  endPreview(){if(!valid())return;preview=null;sync();},
  play(phase){
   if(!valid())return Promise.resolve({skipped:true});
   adapter.skipVisual();
   if(!engine)return Promise.resolve({phase,skipped:true});
   return new Promise(resolve=>{pending={phase,resolve};engine.setPhase(phase);});
  },
  skipVisual(){const current=pending;pending=null;engine?.setPhase('idle');current?.resolve({phase:current.phase,skipped:true});flushMapping();},
  setVisible(visible){if(!valid())return;if(visible)engine?.start();else engine?.stop();},
  respondToParticipation(reaction){return adapter.play(reaction?.behavior==='adult_cooperation'?'hand':'pet');},
  setBall(point){if(valid())engine?.setBall(point);},
  hitTest(point){
   if(!valid())return false;
   const p=point.space==='scene'?point:clientToPetScene(canvas,point);
   return engine?engine.hitTest(p):(p.x>=160&&p.x<=700&&p.y>=880&&p.y<=1510);
  },
  snapshot(){if(!valid()||!available||preview)return null;const data=engine.snapshot();return data?{data_url:data,stage:actualStage,resource_version:version,record_version:recordVersion}:null;},
  async retryResources(next=bindings,nextVersion=version){if(!valid())return;version=nextVersion;await load(next);},
  async setRenderMode(mode){if(!valid())return;if(!['full','simple'].includes(mode))throw new TypeError('Unknown render mode');adapter.skipVisual();renderMode=mode;await load();},
  subscribe(callback){subscribers.add(callback);return()=>subscribers.delete(callback);},
  inspect(){return{actualStage,previewStage:preview,available,fallback,renderMode,resourceVersion:version,recordVersion,phase:canvas.dataset.phase||'idle',pose:canvas.dataset.pose||null,frames:Number(canvas.dataset.frames||0),disposed};},
  dispose(){if(disposed)return;disposed=true;epoch++;const current=pending;pending=null;current?.resolve({phase:current.phase,skipped:true});engine?.dispose();engine=null;subscribers.clear();}
 };
 return scope.adopt(load().then(()=>adapter),value=>value.dispose(),{kind:'pet-scene'});
}

export function mountStagePreview(container,adapter,scope,{onSelect=()=>{},resources=DEFAULT_RESOURCES}={}){
 const buttons=[];container.replaceChildren();
 for(const stage of Object.keys(engineStage)){
  const button=document.createElement('button');button.type='button';button.dataset.stage=stage;container.append(button);buttons.push(button);
  scope.listen(button,'click',()=>{adapter.previewStage(stage);onSelect(stage);});
 }
 const render=()=>{const view=adapter.inspect();for(const button of buttons){const current=button.dataset.stage===view.actualStage;button.dataset.current=String(current);button.innerHTML='<img src="'+base+({growing:'juvenile'}[button.dataset.stage]||button.dataset.stage)+'.webp" alt=""><span>'+labels[button.dataset.stage]+(current?' · 现在':'')+'</span>';button.setAttribute('aria-pressed',String(button.dataset.stage===(view.previewStage||view.actualStage)));}};
 const unsubscribe=adapter.subscribe(render);scope.own(unsubscribe,{kind:'pet-stage-preview'});render();return unsubscribe;
}

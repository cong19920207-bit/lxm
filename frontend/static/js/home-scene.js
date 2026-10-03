/* One owner for scene layout, motion, subscriptions, and optional enhancements. */
(function () {
  'use strict'
  let instance, nextId = 0
  function mount() {
    if (instance) return instance
    const page = document.querySelector('.h5-home-page')
    const scene = page?.querySelector('.home-scene')
    const rig = scene?.querySelector('.home-scene-position')
    const hero = page?.querySelector('.home-hero'), bar = page?.querySelector('.home-top-bar')
    if (!page || !scene || !rig || !hero || !bar) return null
    const core = window.HomeSceneCore
    const reasons = new Set(), cleaners = [], effects = new Set(), timers = new Set()
    let disposed = false, raf = 0, last = null, time = 0, layoutDirty = true, frames = 0, running = false
    const preferenceKey = 'lxm_home_motion_enabled'
    function readMotionPreference(refreshSaved = false) {
      if (window.HomePreferences) return window.HomePreferences.readMotion(refreshSaved)
      const saved = window.HomeStartup?.storage('localStorage','getItem',preferenceKey) || {ok:false}
      return {enabled: saved.ok ? saved.value !== '0' : true, note: saved.ok ? '' : '无法读取已保存的选择，本次默认开启。'}
    }
    const savedPreference = readMotionPreference()
    let motionEnabled = savedPreference.enabled, storageNote = savedPreference.note
    let reducedQuery
    const id = ++nextId
    function listen(target,type,fn,options) {
      target?.addEventListener(type,fn,options)
      let active=true
      const remove=()=>{if(!active)return;active=false;target?.removeEventListener(type,fn,options);const i=cleaners.indexOf(remove);if(i>=0)cleaners.splice(i,1)};cleaners.push(remove);return remove
    }
    function later(fn,ms) {
      const timer=setTimeout(()=>{timers.delete(timer);if(!disposed)fn()},ms);timers.add(timer);return timer
    }
    function clearLater(timer) { clearTimeout(timer);timers.delete(timer) }
    function layout() {
      layoutDirty=false
      const p=page.getBoundingClientRect(),h=hero.getBoundingClientRect()
      // Transient data notes and entrance translation must not resize the character.
      const meta=bar.querySelector('.home-top-meta'),barStyle=getComputedStyle(bar)
      const gap=parseFloat(getComputedStyle(meta).rowGap)||0
      const noteHeight=[...meta.querySelectorAll('.home-module-note')]
        .filter(note=>note.offsetHeight>0).reduce((height,note)=>height+note.offsetHeight+gap,0)
      const contentHeight=Math.max(meta.offsetHeight-noteHeight,
        bar.querySelector('#linxiaomeng-avatar')?.offsetHeight||0,
        bar.querySelector('.home-intimacy-pill')?.offsetHeight||0)
      const paddingHeight=['paddingTop','paddingBottom','borderTopWidth','borderBottomWidth']
        .reduce((height,key)=>height+(parseFloat(barStyle[key])||0),0)
      const barBottom=h.top+bar.offsetTop+paddingHeight+contentHeight
      const available=Math.max(90,h.bottom-barBottom-24),width=Math.min(p.width*.64,available/.4)
      rig.style.width=width+'px';rig.style.left=p.width*.64+'px'
      rig.style.top=(barBottom-p.top+(h.bottom-barBottom)*.52)+'px'
      for(const effect of effects) invoke(effect,'resize',p)
    }
    function invoke(effect,method,...args) {
      if (!effect[method]) return
      try { effect[method](...args) }
      catch (error) { effects.delete(effect);try{effect.destroy?.()}catch(_){};console.warn('Home scene effect unavailable',error) }
    }
    function schedule() { if(!disposed&&!raf&&!reasons.has('hidden')&&!reasons.has('bfcache')&&(running||layoutDirty)) raf=requestAnimationFrame(frame) }
    function frame(now) {
      raf=0;if(disposed)return
      if(layoutDirty)try{layout()}catch(error){layoutDirty=false;console.warn('Home scene layout unavailable',error)}
      if(running) {
        const rawDt=last==null?0:Math.max(0,now-last)
        const dt=core ? core.frameDelta(now,last) : (last==null?0:Math.min(40,Math.max(0,now-last)))
        last=now;time+=dt;frames++
        for(const effect of effects)invoke(effect,'frame',{now,time,dt,rawDt})
      }
      schedule()
    }
    function reconcile() {
      const next=!disposed&&reasons.size===0
      if(next===running){schedule();return}
      running=next;last=null
      scene.dataset.running=String(running)
      for(const effect of effects)invoke(effect,running?'resume':'pause')
      if(!running&&raf){cancelAnimationFrame(raf);raf=0}
      schedule()
    }
    function pause(reason,on=true) {
      if(disposed || reasons.has(reason) === !!on)return
      if(on)reasons.add(reason);else reasons.delete(reason)
      reconcile()
      page.dispatchEvent(new CustomEvent('home-scene-state'))
    }
    function addEffect(effect) {
      if(disposed)return ()=>{}
      effects.add(effect);invoke(effect,'resize',page.getBoundingClientRect());invoke(effect,running?'resume':'pause')
      return ()=>{effects.delete(effect);invoke(effect,'destroy')}
    }
    function startup() {pause('loading',window.HomeStartup?.phase!=='ready')}
    function sceneMode() {pause('legacy',window.HomeStartup?.sceneMode==='legacy')}
    function refreshMotionPreference(refreshSaved = false) {
      const saved = readMotionPreference(refreshSaved)
      motionEnabled = saved.enabled;storageNote = saved.note
      pause('user-off',!motionEnabled)
      page.dispatchEvent(new CustomEvent('home-scene-state'))
    }
    function visible() {if(!document.hidden)refreshMotionPreference();pause('hidden',document.hidden)}
    function resized() {layoutDirty=true;schedule()}
    function destroy() {
      if(disposed)return
      disposed=true;running=false;scene.dataset.running='false'
      if(raf)cancelAnimationFrame(raf);raf=0
      for(const timer of timers)clearTimeout(timer);timers.clear()
      for(const effect of [...effects])invoke(effect,'destroy');effects.clear()
      for(const clean of cleaners.splice(0))try{clean()}catch(_){}
      reasons.clear();last=null
    }
    instance={id,pause,addEffect,listen,later,clearLater,destroy,
      own:clean=>{cleaners.push(clean);return clean},
      get motionEnabled(){return motionEnabled},get storageNote(){return storageNote},
      setMotionEnabled(value){
        if(disposed)return
        motionEnabled=!!value
        if(window.HomePreferences)storageNote=window.HomePreferences.writeMotion(motionEnabled).note
        else {
          const saved=window.HomeStartup.storage('localStorage','setItem',preferenceKey,motionEnabled?'1':'0')
          storageNote=saved.ok?'':'选择仅本次生效，暂时无法保存。'
        }
        pause('user-off',!motionEnabled);page.dispatchEvent(new CustomEvent('home-scene-state'))
      },
      get running(){return running},get disposed(){return disposed},get time(){return time},
      inspect:()=>({id,running,disposed,reasons:[...reasons],raf:!!raf,time,frames,effects:effects.size,timers:timers.size,subscriptions:cleaners.length})}
    pause('user-off',!motionEnabled);sceneMode();startup();visible()
    try {
      reducedQuery=window.matchMedia?.('(prefers-reduced-motion: reduce)')
      pause('reduced',!!reducedQuery?.matches)
      if(reducedQuery?.addEventListener)listen(reducedQuery,'change',event=>pause('reduced',event.matches))
      else if(reducedQuery?.addListener){const fn=event=>pause('reduced',event.matches);reducedQuery.addListener(fn);cleaners.push(()=>reducedQuery.removeListener(fn))}
      listen(window,'home-startup-change',startup)
      listen(window,'home-scene-mode-change',sceneMode)
      listen(document,'visibilitychange',visible)
      listen(window,'resize',resized,{passive:true});listen(window.visualViewport,'resize',resized,{passive:true})
      listen(window,'pagehide',event=>event.persisted?pause('bfcache'):destroy())
      listen(window,'pageshow',()=>{refreshMotionPreference();window.HomeStartup?.checkDeadline();startup();visible();pause('bfcache',false);resized()})
      listen(window,'storage',event=>{if(event.key===null||event.key===preferenceKey)refreshMotionPreference(true)})
      if(typeof ResizeObserver==='function'){
        const observer=new ResizeObserver(resized);[page,hero,bar].forEach(el=>observer.observe(el));cleaners.push(()=>observer.disconnect())
      }
    }catch(error){console.warn('Home scene optional lifecycle unavailable',error)}
    try{layout()}catch(error){layoutDirty=false;console.warn('Home scene layout unavailable',error)}
    reconcile()
    return instance
  }
  window.HomeScene={mount,get current(){return instance}}
  try{mount()}catch(error){console.warn('Home scene unavailable',error)}
})();

/* Progressive effects own no additional RAF, intervals, or untracked delayed actions. */
(function () {
  'use strict'
  const controller=window.HomeScene?.current, core=window.HomeSceneCore
  const scene=document.querySelector('.home-scene')
  if(!controller||!core||!scene||window.HomeStartup?.sceneMode==='legacy')return
  const breathe=scene.querySelector('.home-scene-breathe'),gesture=scene.querySelector('.home-scene-gesture')
  const parallax=scene.querySelector('.home-scene-parallax'),character=scene.querySelector('.home-scene-character')
  const blink=scene.querySelector('.home-scene-blink'),lamp=scene.querySelector('.home-scene-lamp')
  const hair=Object.entries(core.CONFIG.hair).map(([key,cfg])=>({key,cfg,el:scene.querySelector('.home-scene-hair-'+key),x:0,vx:0,y:0,vy:0,r:0,vr:0}))
  const CITY_STARS=[{"x":0.1137,"y":0.596,"strength":1.0},{"x":0.1254,"y":0.596,"strength":0.971},{"x":0.5416,"y":0.5206,"strength":0.969},{"x":0.354,"y":0.5244,"strength":0.969},{"x":0.0821,"y":0.6285,"strength":0.965},{"x":0.0996,"y":0.596,"strength":0.958},{"x":0.0246,"y":0.5944,"strength":0.956},{"x":0.5674,"y":0.5217,"strength":0.943},{"x":0.422,"y":0.5239,"strength":0.943},{"x":0.3376,"y":0.5239,"strength":0.93},{"x":0.5006,"y":0.5889,"strength":0.916},{"x":0.0633,"y":0.2907,"strength":0.91},{"x":0.4361,"y":0.5336,"strength":0.896},{"x":0.4338,"y":0.5244,"strength":0.892},{"x":0.245,"y":0.4978,"strength":0.888},{"x":0.1243,"y":0.2896,"strength":0.879},{"x":0.0539,"y":0.4892,"strength":0.875},{"x":0.1923,"y":0.596,"strength":0.87},{"x":0.136,"y":0.596,"strength":0.868},{"x":0.5311,"y":0.5884,"strength":0.86},{"x":0.6038,"y":0.5255,"strength":0.852},{"x":0.3458,"y":0.6193,"strength":0.849},{"x":0.1032,"y":0.5553,"strength":0.848},{"x":0.5006,"y":0.5125,"strength":0.84},{"x":0.2098,"y":0.4463,"strength":0.839},{"x":0.1606,"y":0.596,"strength":0.837},{"x":0.3118,"y":0.3134,"strength":0.837},{"x":0.1794,"y":0.596,"strength":0.833},{"x":0.3294,"y":0.6198,"strength":0.83},{"x":0.5264,"y":0.5195,"strength":0.828},{"x":0.2544,"y":0.6226,"strength":0.826},{"x":0.5744,"y":0.5857,"strength":0.826},{"x":0.6249,"y":0.3265,"strength":0.825},{"x":0.626,"y":0.2907,"strength":0.822},{"x":0.2907,"y":0.5542,"strength":0.82},{"x":0.3294,"y":0.2901,"strength":0.818},{"x":0.2696,"y":0.5949,"strength":0.818},{"x":0.1782,"y":0.3623,"strength":0.815},{"x":0.1407,"y":0.4642,"strength":0.811},{"x":0.5873,"y":0.4919,"strength":0.811},{"x":0.5147,"y":0.5889,"strength":0.81},{"x":0.3095,"y":0.6204,"strength":0.806},{"x":0.1712,"y":0.5797,"strength":0.804},{"x":0.0926,"y":0.4886,"strength":0.803},{"x":0.3165,"y":0.2993,"strength":0.802},{"x":0.5909,"y":0.551,"strength":0.8},{"x":0.4174,"y":0.507,"strength":0.8},{"x":0.2274,"y":0.4469,"strength":0.794},{"x":0.238,"y":0.5954,"strength":0.794},{"x":0.1254,"y":0.4615,"strength":0.792},{"x":0.6342,"y":0.6291,"strength":0.788},{"x":0.5334,"y":0.5049,"strength":0.786},{"x":0.1278,"y":0.4387,"strength":0.786},{"x":0.286,"y":0.5944,"strength":0.785},{"x":0.5416,"y":0.5884,"strength":0.784},{"x":0.3154,"y":0.4219,"strength":0.783},{"x":0.102,"y":0.5022,"strength":0.783},{"x":0.1032,"y":0.5347,"strength":0.781},{"x":0.612,"y":0.3812,"strength":0.78},{"x":0.5698,"y":0.551,"strength":0.777},{"x":0.2063,"y":0.4561,"strength":0.777},{"x":0.1782,"y":0.5705,"strength":0.776},{"x":0.2309,"y":0.6231,"strength":0.774},{"x":0.2649,"y":0.622,"strength":0.774},{"x":0.0715,"y":0.462,"strength":0.772},{"x":0.0246,"y":0.5542,"strength":0.771},{"x":0.238,"y":0.4181,"strength":0.767},{"x":0.2579,"y":0.5949,"strength":0.762},{"x":0.5862,"y":0.4544,"strength":0.762},{"x":0.0645,"y":0.4886,"strength":0.761},{"x":0.1208,"y":0.5022,"strength":0.757},{"x":0.1336,"y":0.3677,"strength":0.755},{"x":0.3001,"y":0.4978,"strength":0.755},{"x":0.4795,"y":0.4333,"strength":0.75},{"x":0.2603,"y":0.551,"strength":0.749},{"x":0.3189,"y":0.5239,"strength":0.749},{"x":0.5522,"y":0.4881,"strength":0.749},{"x":0.0633,"y":0.359,"strength":0.74},{"x":0.2802,"y":0.6215,"strength":0.74},{"x":0.0856,"y":0.596,"strength":0.739},{"x":0.5217,"y":0.5244,"strength":0.738},{"x":0.3283,"y":0.5933,"strength":0.733},{"x":0.3411,"y":0.5933,"strength":0.732},{"x":0.4924,"y":0.4696,"strength":0.732},{"x":0.4162,"y":0.3248,"strength":0.73},{"x":0.6202,"y":0.4892,"strength":0.729},{"x":0.0352,"y":0.5938,"strength":0.728},{"x":0.2122,"y":0.3623,"strength":0.727},{"x":0.4947,"y":0.5206,"strength":0.721},{"x":0.4373,"y":0.4203,"strength":0.719},{"x":0.5158,"y":0.5325,"strength":0.719},{"x":0.5873,"y":0.5255,"strength":0.711},{"x":0.408,"y":0.5889,"strength":0.71},{"x":0.4596,"y":0.6155,"strength":0.706},{"x":0.4889,"y":0.5049,"strength":0.7},{"x":0.027,"y":0.462,"strength":0.7}]
  const loaded=new Set(),failed=new Set()
  let disposed=false,startTime=0, nextBlink=0,nextIdle=0,blinkAction=null,secondBlink=null,action=null
  let hairImpulse=0,env=null,environmentFrames=0,lastEnvironment=0,idleCount=0,blinkCount=0,responseCount=0
  let target={x:0,y:0},current={x:0,y:0},quality=0,pixelBudget=null,responseLatencyMs=null
  function optionalImages() {
    if(!character.complete||!character.naturalWidth||character.hidden)return
    for(const img of scene.querySelectorAll('img[data-src]')){
      if(img.dataset.requested)continue
      img.dataset.requested='1'
      const key=img===lamp?'lamp':img===blink?'blink':hair.find(h=>h.el===img)?.key
      controller.listen(img,'load',()=>{if(disposed)return;loaded.add(key);img.hidden=false})
      controller.listen(img,'error',()=>{failed.add(key);img.hidden=true})
      img.src=img.dataset.src
    }
  }
  function startBlink(at=controller.time,allowDouble=true) {
    if(!loaded.has('blink')||!controller.running)return
    const plan=core.createBlinkPlan();blinkAction={at,plan};blinkCount++
    secondBlink=allowDouble&&plan.doubleBlink?at+plan.totalMs+plan.doubleGapMs:null
  }
  function startAction(response=false) {
    if(!controller.running||disposed||quality>=3||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return false
    if(response&&action?.response)return false
    const plan=response?core.createAcknowledgePlan():{durationMs:3600+Math.random()*1100,
      translateXPercent:Math.random()<.5?-.62:.62,translateYPercent:-.42,rotateDeg:.26,scale:1.006}
    action={at:controller.time,plan,response,requestedAt:performance.now(),firstFrame:true};hairImpulse=response?-.95:.55
    if(response)responseCount++;else idleCount++
    return true
  }
  function neutral() {
    breathe.style.transform='none';gesture.style.transform='none';parallax.style.transform='none'
    blink.style.opacity='0';blink.style.clipPath='inset(48% 0 48% 0)';blink.style.transform='none'
    lamp.style.opacity='0'
    for(const h of hair){h.x=h.y=h.r=h.vx=h.vy=h.vr=0;h.el.style.transform='none';h.el.style.opacity='0'}
    blinkAction=null;secondBlink=null;action=null;hairImpulse=0;current={x:0,y:0};target={x:0,y:0}
    if(env)env.ctx.clearRect(0,0,env.width,env.height)
  }
  function texture(kind) {
    const canvas=document.createElement('canvas');canvas.width=32;canvas.height=64
    const ctx=canvas.getContext('2d');if(!ctx)throw Error('Canvas unavailable')
    if(kind==='star'){
      const g=ctx.createRadialGradient(16,32,0,16,32,16);g.addColorStop(0,'rgba(240,232,255,1)');g.addColorStop(.2,'rgba(189,204,255,.8)');g.addColorStop(1,'rgba(189,204,255,0)');ctx.fillStyle=g;ctx.fillRect(0,16,32,32)
    }else{
      const g=ctx.createLinearGradient(0,0,0,64);g.addColorStop(0,'rgba(170,160,255,0)');g.addColorStop(.55,'rgba(155,145,255,.7)');g.addColorStop(1,'rgba(110,120,255,0)');ctx.fillStyle=g;ctx.fillRect(15,0,2,64)
    }
    return canvas
  }
  function ensureEnvironment() {
    if(env||failed.has('environment'))return
    try {
      const canvas=scene.querySelector('canvas'),ctx=canvas.getContext('2d');if(!ctx)throw Error('Canvas unavailable')
      env={canvas,ctx,starTexture:texture('star'),rainTexture:texture('rain'),width:0,height:0,dpr:1,drops:[],stars:[]}
      env.stars=CITY_STARS.map((p,i)=>({...p,seed:i*1.137,plan:core.createTwinklePlan(),phase:Math.random()*10000}))
      resizeEnvironment()
    }catch(error){env=null;failed.add('environment');console.warn('Home environment unavailable',error)}
  }
  function resizeEnvironment() {
    if(!env)return
    const rect=scene.getBoundingClientRect()
    env.cssWidth=rect.width;env.cssHeight=rect.height;env.dpr=Math.min(window.devicePixelRatio||1,1.5)
    if(pixelBudget!=null)env.dpr=Math.min(env.dpr,Math.sqrt(pixelBudget/Math.max(1,rect.width*rect.height)))
    env.width=Math.max(1,Math.floor(rect.width*env.dpr));env.height=Math.max(1,Math.floor(rect.height*env.dpr))
    env.canvas.width=env.width;env.canvas.height=env.height
    env.scale=Math.max(rect.width/853,rect.height/1844)*env.dpr
    env.offsetX=(env.width-853*env.scale)/2;env.offsetY=(env.height-1844*env.scale)/2
    env.drops=Array.from({length:24},()=>({x:Math.random()*env.width*.65,y:Math.random()*env.height*.65,len:(18+Math.random()*48)*env.dpr,speed:(20+Math.random()*42)*env.dpr,alpha:.02+Math.random()*.064}))
  }
  function drawEnvironment(time,dt) {
    if(!env||quality>=3)return
    const e=env;e.ctx.clearRect(0,0,e.width,e.height)
    e.ctx.save();e.ctx.globalCompositeOperation='lighter'
    const starCount=quality>=1?Math.ceil(e.stars.length/4):e.stars.length
    for(let i=0;i<starCount;i++){const s=e.stars[i]
      const local=(time+s.phase)%(s.plan.durationMs+s.plan.pauseMs),pulse=local<s.plan.durationMs?Math.sin(Math.PI*local/s.plan.durationMs):0
      const alpha=.1+.14*s.strength+s.plan.peakAlpha*pulse*(.56+.44*s.strength)
      const r=(s.plan.radius*(.74+.42*pulse))*e.dpr*3.5
      e.ctx.globalAlpha=Math.min(1,alpha);e.ctx.drawImage(e.starTexture,s.x*853*e.scale+e.offsetX-r,s.y*1844*e.scale+e.offsetY-r,r*2,r*2)
    }
    // Rain stays in the window; its progression uses elapsed time, not display refresh rate.
    e.ctx.beginPath();e.ctx.rect(e.offsetX,e.offsetY+1844*.08*e.scale,853*.65*e.scale,1844*.58*e.scale);e.ctx.clip()
    const rainCount=quality>=1?8:e.drops.length
    for(let i=0;i<rainCount;i++){const d=e.drops[i]
      e.ctx.globalAlpha=d.alpha*.75;e.ctx.drawImage(e.rainTexture,d.x-2*e.dpr,d.y,4*e.dpr,d.len)
      d.y+=d.speed*dt/1000;if(d.y>e.height*.68){d.y=0;d.x=Math.random()*e.width*.65}
    }
    e.ctx.restore();environmentFrames++
  }
  function frame({time,dt}) {
    const local=time-startTime,ramp=Math.min(1,local/450)
    const breath=(1-Math.cos(local*Math.PI*2/5600))*.5*ramp
    breathe.style.transform=`translate3d(0,${(-.28*breath).toFixed(4)}%,0)`
    const smoothing=1-Math.exp(-dt/190);current.x=core.lerp(current.x,target.x,smoothing);current.y=core.lerp(current.y,target.y,smoothing)
    parallax.style.transform=`translate3d(${(current.x*3.2).toFixed(2)}px,${(current.y*2.4).toFixed(2)}px,0)`
    if(time>=nextBlink&&!blinkAction&&!secondBlink){startBlink(time);nextBlink=time+core.createBlinkPlan().nextDelayMs}
    if(secondBlink!=null&&time>=secondBlink){startBlink(time,false);secondBlink=null}
    if(blinkAction){
      const p=blinkAction.plan,elapsed=time-blinkAction.at
      const amount=elapsed<p.closeMs?elapsed/p.closeMs:elapsed<p.closeMs+p.holdMs?1:1-(elapsed-p.closeMs-p.holdMs)/p.openMs
      blink.style.opacity=String(core.clamp(amount,0,1));blink.style.clipPath=`inset(${(48*(1-core.clamp(amount,0,1))).toFixed(2)}% 0)`
      if(elapsed>=p.totalMs){blinkAction=null;blink.style.opacity='0'}
    }
    if(time>=nextIdle&&!action){startAction();nextIdle=time+core.createIdleDelay()}
    if(action){
      if(action.response&&action.firstFrame){responseLatencyMs=performance.now()-action.requestedAt;action.firstFrame=false}
      const p=action.plan,u=(time-action.at)/p.durationMs,amount=u<.34?Math.sin(u/.34*Math.PI/2):u<.64?1:Math.max(0,(1+Math.cos((u-.64)/.36*Math.PI))/2)
      gesture.style.transform=`translate3d(${p.translateXPercent*amount}%,${p.translateYPercent*amount}%,0) rotate(${p.rotateDeg*amount}deg) scale(${1+(p.scale-1)*amount})`
      if(u>=1){action=null;gesture.style.transform='none'}
    }
    if(loaded.has('lamp'))lamp.style.opacity=String((.23+.08*Math.sin(local/5400*Math.PI))*ramp)
    if(quality<2){
      const breeze=Math.sin(local*.00072)*.52+Math.sin(local*.00131+1.2)*.22
      for(const h of hair){if(!loaded.has(h.key))continue;const c=h.cfg,d=dt/16.667
        ;[h.x,h.vx]=core.stepSpring(h.x,h.vx,-current.x*c.travelPx*.58+breeze*c.travelPx*.32+hairImpulse*c.travelPx,c.stiffness,c.damping,d)
        ;[h.r,h.vr]=core.stepSpring(h.r,h.vr,-current.x*c.rotateDeg*.42+breeze*c.rotateDeg*.66+hairImpulse*c.rotateDeg*.68,c.stiffness*.72,c.damping,d)
        h.el.style.transform=`translate3d(${h.x.toFixed(2)}px,0,0) rotate(${h.r.toFixed(3)}deg)`;h.el.style.opacity=String(({front:.78,side:.86,back:.84}[h.key])*ramp)
      }
      hairImpulse*=Math.pow(.925,dt/16.667)
    }
    if(time-lastEnvironment>=1000/30){drawEnvironment(time,time-lastEnvironment);lastEnvironment=time}
  }
  const effect={frame,
    resume(){startTime=controller.time;nextBlink=controller.time+core.createBlinkPlan().nextDelayMs;nextIdle=controller.time+core.createIdleDelay();lastEnvironment=controller.time;optionalImages();ensureEnvironment()},
    pause:neutral,resize:resizeEnvironment,destroy(){disposed=true;neutral();env=null}}
  controller.listen(character,'load',()=>{if(controller.running)optionalImages()})
  HomeScene.motion={capPixels(value){pixelBudget=value;resizeEnvironment()},respond:()=>startAction(true),setInput:(input)=>{target={x:core.clamp(input.x,-1,1),y:core.clamp(input.y,-1,1)}},
    setQuality(value){quality=Math.max(quality,core.clamp(value,0,3));if(quality>=1&&env)env.ctx.clearRect(0,0,env.width,env.height);if(quality>=2)for(const h of hair){h.el.style.opacity='0';h.el.style.transform='none'}if(quality>=3)controller.pause('quality')},
    inspect:()=>({loaded:[...loaded],failed:[...failed],environmentFrames,blinkCount,idleCount,responseCount,action:action?.response?'response':action?'idle':null,quality,responseLatencyMs,pixelBudget,canvas:env?{width:env.width,height:env.height,dpr:env.dpr,pixels:env.width*env.height}:null})}
  controller.addEffect(effect)
})();

/* Restrict local feedback to the visible character; cards and overlays retain priority. */
(function () {
  const c=window.HomeScene?.current,hit=document.querySelector('.home-scene-hit'),page=document.querySelector('.h5-home-page')
  if(!c||!hit)return
  const sync=()=>{hit.disabled=!c.running||c.disposed}
  c.listen(hit,'click',()=>{if(!hit.disabled)window.HomeScene.motion?.respond()})
  c.listen(page,'home-scene-state',sync)
  sync()
})();

/* Settings owns explicit permission; the homepage owns sensor input and RAF. */
(function () {
  const c=window.HomeScene?.current
  const page=document.querySelector('.h5-home-page'),preferences=window.HomePreferences
  if(!c)return
  let intent=false,permissionGranted=false,listening=false,baseline=null,input={x:0,y:0}
  let state='off',message='已关闭',epoch=0,removeOrientation=null,dataTimer=null
  let pendingNotice=''
  function setState(next,text) {
    state=next;message=text
    preferences?.reportTilt(state,message)
  }
  function stopListening() {
    removeOrientation?.();removeOrientation=null;listening=false;baseline=null;input={x:0,y:0}
    window.HomeScene.motion?.setInput(input)
    if(dataTimer!=null)c.clearLater(dataTimer);dataTimer=null
  }
  function disable(text='已关闭') {
    closeTilt('off',text)
  }
  function unavailable(text,next='unavailable') {
    closeTilt(next,text)
  }
  function flushNotice() {
    if(!pendingNotice||c.disposed)return
    if(!preferences?.readTilt().pageOnly){pendingNotice='';return}
    if(document.hidden||window.HomeStartup?.phase!=='ready'||typeof window.showToast!=='function')return
    const text=pendingNotice;pendingNotice=''
    window.showToast(text)
  }
  function closeTilt(next,text) {
    epoch++;intent=false;stopListening();preferences?.writeTilt(false);setState(next,text)
    const selected=preferences?.readTilt()
    // Startup may close tilt before the shared toast script has loaded.
    pendingNotice=selected?.pageOnly?text+'；'+selected.note:''
    flushNotice()
  }
  function validData(event) {
    if(!intent||!c.running||event.beta==null||event.gamma==null||!Number.isFinite(event.beta)||!Number.isFinite(event.gamma))return
    if(!baseline)baseline={gamma:event.gamma,beta:event.beta}
    const normalized=window.HomeSceneCore.normalizeOrientation(event.gamma,event.beta,baseline)
    const angle=Number(window.screen.orientation?.angle ?? window.orientation ?? 0)
    input=window.HomeSceneCore.rotateInput(normalized.x,normalized.y,angle)
    window.HomeScene.motion?.setInput(input)
    if(dataTimer!=null)c.clearLater(dataTimer);dataTimer=null
    if(state!=='enabled')setState('enabled','已开启，轻转手机试试')
  }
  function attach() {
    if(!intent||!permissionGranted||!c.running||listening)return
    baseline=null;listening=true;removeOrientation=c.listen(window,'deviceorientation',validData,{passive:true})
    setState('waiting-data','轻转手机，正在等待方向数据…')
    watchData()
  }
  function watchData() {
    if(dataTimer!=null)c.clearLater(dataTimer)
    const run=epoch
    dataTimer=c.later(()=>{dataTimer=null;if(run===epoch&&intent&&state==='waiting-data')unavailable('暂时收不到方向数据，可在设置中重试')},5000)
  }
  function reconcilePreference() {
    if(c.disposed)return
    const selected=preferences?.readTilt() || {enabled:false,permissionGranted:false}
    const legacy=c.inspect().reasons.includes('legacy')
    permissionGranted=selected.permissionGranted
    if(!selected.enabled) {
      epoch++;intent=false;stopListening()
      const staleLegacy=selected.state==='legacy'&&!legacy
      const detail=selected.state==='unavailable'&&selected.message?selected.message:selected.note||selected.message||'已关闭'
      setState(legacy?'legacy':selected.state==='unavailable'?'unavailable':'off',
        legacy?'旧背景模式不支持倾斜':staleLegacy?'已关闭':detail)
      return
    }
    if(legacy){unavailable('旧背景模式不支持倾斜','legacy');return}
    if(!window.HomeSceneCore||!window.HomeScene.motion){unavailable('倾斜暂不可用，可在设置中重试');return}
    if(!window.isSecureContext){unavailable('当前页面连接不支持倾斜');return}
    const Orientation=window.DeviceOrientationEvent
    if(typeof Orientation==='undefined'){unavailable('当前浏览器不支持倾斜');return}
    if(typeof Orientation.requestPermission==='function'&&!permissionGranted) {
      unavailable('请在设置中重新开启倾斜并授权');return
    }
    // The stored grant is only a handoff hint. Browser permissions still gate
    // actual events, and finite data is required before reporting enabled.
    permissionGranted=true;intent=true
    if(c.running)attach()
    else {stopListening();setState('paused','倾斜当前已暂停')}
  }
  function suspend() {
    epoch++;stopListening()
    if(intent)setState('paused','倾斜当前已暂停')
  }
  function rotated() {
    baseline=null;input={x:0,y:0};window.HomeScene.motion?.setInput(input)
    if(listening){setState('waiting-data','方向已变化，轻转手机重新校准');watchData()}
  }
  c.listen(window,'orientationchange',rotated,{passive:true})
  c.listen(window.screen.orientation,'change',rotated,{passive:true})
  c.listen(window,'pageshow',reconcilePreference)
  c.listen(window,'pageshow',flushNotice)
  c.listen(window,'home-startup-change',flushNotice)
  c.listen(document,'DOMContentLoaded',flushNotice,{once:true})
  c.listen(document,'visibilitychange',flushNotice)
  c.listen(page,'home-scene-state',reconcilePreference)
  c.listen(window,'storage',event=>{if(event.key===null||event.key===preferences?.tiltKey)reconcilePreference()})
  window.HomeScene.tilt={disable,inspect:()=>({state,listening,intent,permissionGranted,input:{...input}})}
  c.addEffect({pause:suspend,resume:reconcilePreference,destroy:()=>{
    epoch++;pendingNotice='';const selected=intent;intent=false;stopListening()
    if(selected)setState('paused','返回主页后，轻转手机试试')
  }})
  reconcilePreference()
})();

/* Observe only the real modal roots, never the scene's per-frame style changes. */
(function () {
  const c=window.HomeScene?.current
  if(!c)return
  if(typeof MutationObserver!=='function'){console.warn('Home panel observation unavailable');return}
  const observed=new WeakSet()
  function visible(element) {
    if(!element||element.hidden)return false
    const style=getComputedStyle(element)
    return style.display!=='none'&&style.visibility!=='hidden'&&element.getClientRects().length>0
  }
  function sync() {
    const login=document.getElementById('auth-login-modal'),voice=document.querySelector('.voice-entry')
    for(const root of [login,voice])if(root&&!observed.has(root)){
      observed.add(root);const observer=new MutationObserver(sync)
      observer.observe(root,{attributes:true,attributeFilter:['class','hidden','style']});c.own(()=>observer.disconnect())
    }
    c.pause('login',!!login?.classList.contains('is-open')&&visible(login))
    c.pause('voice',visible(voice))
  }
  const observer=new MutationObserver(sync)
  observer.observe(document.body,{childList:true,attributes:true,attributeFilter:['class']})
  c.own(()=>observer.disconnect());c.listen(window,'pageshow',sync)
  sync()
})();

/* Q201 measurement adapter. Production parameters remain unset until real devices are measured. */
(function () {
  const c=window.HomeScene?.current,motion=window.HomeScene?.motion
  if(!c||!motion)return
  let calibration=null,level=0,windowElapsed=0,windowFrames=0,lastWindow=null
  const metrics={frames:0,elapsedMs:0,maxFrameMs:0,longTasks:0,longTaskMs:0}
  function configure(value) {
    if(!value||!Number.isFinite(value.pixelBudget)||value.pixelBudget<1||!Number.isFinite(value.windowMs)||value.windowMs<=0||!Number.isFinite(value.minimumFps)||value.minimumFps<30||value.minimumFps>60||typeof value.source!=='string'||!value.source.trim())return false
    calibration={pixelBudget:Math.floor(value.pixelBudget),windowMs:value.windowMs,minimumFps:value.minimumFps,source:value.source}
    windowElapsed=windowFrames=0;motion.capPixels(calibration.pixelBudget);return true
  }
  const effect={
    frame({rawDt}) {
      if(rawDt<=0)return
      metrics.frames++;metrics.elapsedMs+=rawDt;metrics.maxFrameMs=Math.max(metrics.maxFrameMs,rawDt)
      if(!calibration||level>=3)return
      windowElapsed+=rawDt;windowFrames++
      if(windowElapsed<calibration.windowMs)return
      lastWindow={elapsedMs:windowElapsed,frames:windowFrames,fps:1000*windowFrames/windowElapsed}
      windowElapsed=windowFrames=0
      if(lastWindow.fps<calibration.minimumFps){level++;motion.setQuality(level)}
    },pause(){windowElapsed=windowFrames=0},resume(){windowElapsed=windowFrames=0}
  }
  c.addEffect(effect)
  if(typeof PerformanceObserver==='function')try{
    const observer=new PerformanceObserver(list=>{for(const entry of list.getEntries()){metrics.longTasks++;metrics.longTaskMs+=entry.duration}})
    observer.observe({type:'longtask',buffered:false});c.own(()=>observer.disconnect())
  }catch(_){/* Metrics capability is optional and independent from the scene. */}
  window.HomeScene.quality={configure,inspect:()=>({level,calibrated:!!calibration,calibration:calibration?{...calibration}:null,lastWindow:lastWindow?{...lastWindow}:null,
    metrics:{...metrics,meanFps:metrics.elapsedMs?metrics.frames*1000/metrics.elapsedMs:null,heapBytes:performance.memory?.usedJSHeapSize??null}})}
  if(window.HomeSceneCalibration)configure(window.HomeSceneCalibration)
})();

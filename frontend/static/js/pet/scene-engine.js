// Approved v4 renderer adapted for owned lifecycle. No business state or API calls.
import {petSceneViewport,clientToPetScene} from './scene-viewport.js';
export async function createApprovedPetScene(canvas,sources,{signal}={}){
 const view={width:851,height:1848,cropY:0};let puppy={x:64,y:863.438,width:600,height:600};
 const handoff={x:490,y:1360};
 const bowlOutline=[[-4,1347],[8,1339],[38,1334],[72,1336],[104,1343],[122,1352],[130,1362],[146,1440],[132,1451],[95,1457],[50,1458],[8,1454],[-4,1446]];
 const smooth=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t);};
 const pulse=(t,start,rise,end,fall)=>smooth(start,start+rise,t)*(1-smooth(end,end+fall,t));
 const mix=(a,b,t)=>a+(b-a)*t;
 if(signal?.aborted)throw new DOMException('Scene owner expired','AbortError');
 const loaded=await Promise.all(Object.entries(sources).map(async([k,src])=>{
  const image=new Image(),abort=()=>{image.src='';};
  signal?.addEventListener('abort',abort,{once:true});
  try{image.src=src;await image.decode();if(signal?.aborted)throw new DOMException('Scene owner expired','AbortError');return[k,image];}
  finally{signal?.removeEventListener('abort',abort);}
 }));
 if(signal?.aborted)throw new DOMException('Scene owner expired','AbortError');
 const images=Object.fromEntries(loaded);images.open=images.puppy;images.closed=images.blink;
 // Preserve the accepted full-body painting. Only the baked-in toy is replaced
 // with the already available clean carpet, before any arm deformation occurs.
 const plate=document.createElement('canvas');plate.width=851;plate.height=1848;
 const plateContext=plate.getContext('2d');
 plateContext.drawImage(images.rest||images.room,0,0,851,1848);
 if(images.rest){
   plateContext.save();plateContext.beginPath();plateContext.ellipse(609,1357,64,59,0,0,Math.PI*2);plateContext.clip();
   if(images.room.width===140&&images.room.height===130)plateContext.drawImage(images.room,540,1288,140,130);
   else plateContext.drawImage(images.room,0,0,851,1848);
   plateContext.restore();
 }
 images.scene=plate;
  // Feature anchors belong to the approved v4 prone sprites (1254px originals).
  // The face moves as one piece; a brief local eye warp supplies a blink without new art.
  const norm=(x,y)=>({u:x/1254,v:y/1254});
  const tiredRigs={
    puppy:{head:{...norm(890,450),rx:.32,ry:.27},neck:norm(905,770),ears:[{...norm(610,455),rx:.105,ry:.15,pivot:norm(700,330)},{...norm(1140,450),rx:.08,ry:.15,pivot:norm(1070,330)}],eyes:[{...norm(790,430),rx:34/1254,ry:25/1254},{...norm(986,416),rx:32/1254,ry:23/1254}],breathPeriod:4.8,delay:0},
    juvenile:{head:{...norm(965,425),rx:.25,ry:.26},neck:norm(990,785),ears:[{...norm(745,400),rx:.10,ry:.14,pivot:norm(835,300)},{...norm(1120,235),rx:.085,ry:.11,pivot:norm(1065,345)}],eyes:[{...norm(890,422),rx:29/1254,ry:22/1254},{...norm(1033,387),rx:27/1254,ry:21/1254}],breathPeriod:5.2,delay:.7},
    adult:{head:{...norm(997,390),rx:.25,ry:.255},neck:norm(1010,765),ears:[{...norm(835,250),rx:.085,ry:.14,pivot:norm(900,345)},{...norm(1130,245),rx:.08,ry:.13,pivot:norm(1085,340)}],eyes:[{...norm(931,390),rx:29/1254,ry:22/1254},{...norm(1072,395),rx:27/1254,ry:21/1254}],breathPeriod:5.6,delay:1.3}
  };
  function tiredMotion(time,rig,engaged){
    if(reduced)return{breath:0,blink:0,nod:0,sigh:0,ear:0,tail:0};
    const cycle=(time-rig.delay+28)%28;
    const breath=(1-Math.cos(time*Math.PI*2/rig.breathPeriod))*.5;
    const blink=engaged?0:Math.max(pulse(cycle,2.65,.11,2.82,.22),pulse(cycle,9.45,.14,9.65,.24),pulse(cycle,18.3,.12,18.47,.23),pulse(cycle,25.1,.10,25.27,.22));
    return{breath,blink,nod:engaged?0:pulse(cycle,5.35,1.1,6.9,1.5),sigh:engaged?0:pulse(cycle,10.8,.8,11.8,1.1),ear:engaged?0:pulse(cycle,13.5,.12,13.68,.32)*Math.sin((cycle-13.5)*17),tail:engaged?0:pulse(cycle,20.2,.65,21.2,1.0)*Math.sin((cycle-20.2)*4.5)};
  }
  function restDeform(u,v,state){
    const m=state.tired,rig=state.rig,planted=1-smooth(.62,.71,v);
    const head=(1-smooth(.82,1.16,Math.hypot((u-rig.head.u)/rig.head.rx,(v-rig.head.v)/rig.head.ry)))*(1-smooth(.67,.79,v));
    const torso=(1-smooth(.70,1.15,Math.hypot((u-.53)/.47,(v-.64)/.29)))*planted*(1-head);
    let x=u+(u-.51)*(.007*m.breath+.003*m.sigh)*torso;
    let y=v-(.0045*m.breath+.0025*m.sigh)*torso;
    // The lowest paws and belly never translate or scale with the breathing chest.
    const tail=(1-smooth(.18,.29,u))*smooth(.45,.60,v)*(1-smooth(.78,.84,v));
    const ta=m.tail*.018,tx=u-.34,ty=v-.72;
    x+=(Math.cos(ta)*tx-Math.sin(ta)*ty-tx)*tail;
    y+=(Math.sin(ta)*tx+Math.cos(ta)*ty-ty)*tail*(1-smooth(.70,.76,v));
    rig.ears.forEach((ear,i)=>{
      const weight=1-smooth(.62,1.12,Math.hypot((u-ear.u)/ear.rx,(v-ear.v)/ear.ry));
      const angle=m.ear*.018*(i?-.45:1),dx=x-ear.pivot.u,dy=y-ear.pivot.v;
      x+=(Math.cos(angle)*dx-Math.sin(angle)*dy-dx)*weight;
      y+=(Math.sin(angle)*dx+Math.cos(angle)*dy-dy)*weight;
    });
    const angle=.018*m.nod,drop=.010*m.nod+.003*m.sigh-.0008*m.breath;
    const dx=x-rig.neck.u,dy=y-rig.neck.v;
    x+=(Math.cos(angle)*dx-Math.sin(angle)*dy-dx)*head;
    y+=(Math.sin(angle)*dx+Math.cos(angle)*dy-dy+drop)*head;
    return[x,y];
  }
  function deform(u, v, state) {
    let x = u, y = v;
    if(state.resting)return restDeform(u,v,state);
    const planted = 1 - smooth(0.70, 0.88, v);
    const body = (1 - smooth(0.50, 0.92, Math.abs(u - 0.52))) * planted;
    x += (u - 0.53) * 0.010 * state.breath * body;
    y -= 0.0042 * state.breath * body;
    const distance = Math.hypot((u - 0.625) / 0.30, (v - 0.285) / 0.255);
    const head = (1 - smooth(0.72, 1.10, distance)) * (1 - smooth(0.43, 0.60, v));
    const hx = x - 0.61, hy = y - 0.50;
    const cos = Math.cos(state.headAngle), sin = Math.sin(state.headAngle);
    x += ((cos * hx - sin * hy + 0.61) - x) * head;
    y += ((sin * hx + cos * hy + 0.50 - state.headLift) - y) * head;
    const tail = (1 - smooth(0.27, 0.39, u)) * (1 - smooth(0.38, 0.53, v));
    const tx = u - 0.295, ty = v - 0.47;
    x += (Math.cos(state.tailAngle) * tx - Math.sin(state.tailAngle) * ty - tx) * tail;
    y += (Math.sin(state.tailAngle) * tx + Math.cos(state.tailAngle) * ty - ty) * tail;
    const leftEar = 1 - smooth(0.6, 1, Math.hypot((u - 0.40) / 0.085, (v - 0.31) / 0.16));
    const rightEar = 1 - smooth(0.6, 1, Math.hypot((u - 0.81) / 0.085, (v - 0.31) / 0.16));
    x += (leftEar - rightEar) * state.earAngle * (v - 0.17);
    y += (leftEar + rightEar) * state.earAngle * 0.06;
    return [x, y];
  }
  function makeMesh(columns, rows) {
    const vertices = [], indices = [];
    for (let y = 0; y <= rows; y++) for (let x = 0; x <= columns; x++) vertices.push(x / columns, y / rows);
    for (let y = 0; y < rows; y++) for (let x = 0; x < columns; x++) {
      const a = y * (columns + 1) + x, b = a + 1, c = a + columns + 1, d = c + 1;
      indices.push(a, b, c, b, d, c);
    }
    return { vertices: new Float32Array(vertices), indices: new Uint16Array(indices) };
  }
  const shoulder={x:786,y:786},elbow={x:790,y:1042},wrist={x:574,y:1275},fingers={x:502,y:1333};
  const upperLength=Math.hypot(elbow.x-shoulder.x,elbow.y-shoulder.y),lowerLength=Math.hypot(wrist.x-elbow.x,wrist.y-elbow.y);
  const upperRest=Math.atan2(elbow.y-shoulder.y,elbow.x-shoulder.x),lowerRest=Math.atan2(wrist.y-elbow.y,wrist.x-elbow.x);
  function armPose(t){
    const lift=pulse(t,.05,.28,.95,.65),press=pulse(t,.35,.32,.9,.7);
    if(lift+press<.00001)return null;
    const target={x:wrist.x-18*press,y:wrist.y-6*lift+10*press};
    const distance=Math.min(upperLength+lowerLength-.001,Math.hypot(target.x-shoulder.x,target.y-shoulder.y));
    const direction=Math.atan2(target.y-shoulder.y,target.x-shoulder.x);
    const bend=Math.acos(Math.max(-1,Math.min(1,(upperLength*upperLength+distance*distance-lowerLength*lowerLength)/(2*upperLength*distance))));
    const upperAngle=direction-bend;
    const joint={x:shoulder.x+upperLength*Math.cos(upperAngle),y:shoulder.y+upperLength*Math.sin(upperAngle)};
    return {elbow:joint,wrist:target,upper:upperAngle-upperRest,lower:Math.atan2(target.y-joint.y,target.x-joint.x)-lowerRest,hand:-.035*lift+.04*press};
  }
  function rotatePoint(point,pivot,angle){const x=point.x-pivot.x,y=point.y-pivot.y;return{x:pivot.x+x*Math.cos(angle)-y*Math.sin(angle),y:pivot.y+x*Math.sin(angle)+y*Math.cos(angle)};}
  function segmentDistance(p,a,b){const dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/(dx*dx+dy*dy)));return Math.hypot(p.x-a.x-t*dx,p.y-a.y-t*dy);}
  function armVertex(point,pose){
    const upperMask=1-smooth(55,118,segmentDistance(point,shoulder,elbow));
    const lowerMask=1-smooth(55,105,segmentDistance(point,elbow,wrist));
    const handMask=1-smooth(32,76,segmentDistance(point,wrist,fingers));
    const edge=smooth(400,440,point.x)*(1-smooth(825,851,point.x))*smooth(710,755,point.y)*(1-smooth(1370,1420,point.y));
    const mask=Math.max(upperMask,lowerMask,handMask)*edge;
    if(mask<.00001)return point;
    const upper=rotatePoint(point,shoulder,pose.upper);
    let lower=rotatePoint(point,elbow,pose.lower);lower={x:lower.x+pose.elbow.x-elbow.x,y:lower.y+pose.elbow.y-elbow.y};
    let hand=rotatePoint(point,wrist,pose.lower+pose.hand);hand={x:hand.x+pose.wrist.x-wrist.x,y:hand.y+pose.wrist.y-wrist.y};
    const forearmBlend=smooth(1000,1090,point.y),handBlend=smooth(1245,1305,point.y);
    const low={x:mix(lower.x,hand.x,handBlend),y:mix(lower.y,hand.y,handBlend)};
    return{x:mix(point.x,mix(upper.x,low.x,forearmBlend),mask),y:mix(point.y,mix(upper.y,low.y,forearmBlend),mask)};
  }
  function drawBall(context,image,visual){
    if(visual.showTarget){context.save();context.strokeStyle='rgba(255,239,205,.8)';context.lineWidth=3;context.beginPath();context.ellipse(handoff.x,handoff.y+10,76,30,0,0,Math.PI*2);context.stroke();context.restore();}
    context.save();context.translate(visual.ball.x,visual.ball.y+38);context.scale(1,.28);const gradient=context.createRadialGradient(0,0,3,0,0,60);gradient.addColorStop(0,'rgba(59,32,39,.3)');gradient.addColorStop(1,'rgba(59,32,39,0)');context.fillStyle=gradient;context.fillRect(-62,-62,124,124);context.restore();
    context.save();context.translate(visual.ball.x,visual.ball.y-visual.lift);context.rotate(visual.roll);context.drawImage(image,-60,-60,120,120);context.restore();
  }
  function canvasRenderer(images) {
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) throw new Error('当前浏览器无法创建动画画布。');
    let scenePixelScale=1;
    const mesh = makeMesh(14, 18),armMesh=makeMesh(12,20);
    const armSource=[];
    for(let i=0;i<armMesh.vertices.length;i+=2)armSource.push({x:400+armMesh.vertices[i]*451,y:710+armMesh.vertices[i+1]*710});
    function triangle(image, source, destination, paddingPixels=1.6) {
      const [s0, s1, s2] = source, [d0, d1, d2] = destination;
      const denominator = s0[0] * (s1[1] - s2[1]) + s1[0] * (s2[1] - s0[1]) + s2[0] * (s0[1] - s1[1]);
      if (Math.abs(denominator) < 0.001) return;
      const a = (d0[0] * (s1[1] - s2[1]) + d1[0] * (s2[1] - s0[1]) + d2[0] * (s0[1] - s1[1])) / denominator;
      const c = (d0[0] * (s2[0] - s1[0]) + d1[0] * (s0[0] - s2[0]) + d2[0] * (s1[0] - s0[0])) / denominator;
      const e = (d0[0] * (s1[0] * s2[1] - s2[0] * s1[1]) + d1[0] * (s2[0] * s0[1] - s0[0] * s2[1]) + d2[0] * (s0[0] * s1[1] - s1[0] * s0[1])) / denominator;
      const b = (d0[1] * (s1[1] - s2[1]) + d1[1] * (s2[1] - s0[1]) + d2[1] * (s0[1] - s1[1])) / denominator;
      const d = (d0[1] * (s2[0] - s1[0]) + d1[1] * (s0[0] - s2[0]) + d2[1] * (s1[0] - s0[0])) / denominator;
      const f = (d0[1] * (s1[0] * s2[1] - s2[0] * s1[1]) + d1[1] * (s2[0] * s0[1] - s0[0] * s2[1]) + d2[1] * (s0[0] * s1[1] - s1[0] * s0[1])) / denominator;
      const center = [(d0[0] + d1[0] + d2[0]) / 3, (d0[1] + d1[1] + d2[1]) / 3];
      const padding = paddingPixels / scenePixelScale;
      const clip = [d0, d1, d2].map(point => {
        const dx = point[0] - center[0], dy = point[1] - center[1], length = Math.max(0.001, Math.hypot(dx, dy));
        return [point[0] + dx / length * padding, point[1] + dy / length * padding];
      });
      context.save(); context.beginPath(); context.moveTo(...clip[0]); context.lineTo(...clip[1]); context.lineTo(...clip[2]); context.closePath(); context.clip();
      context.transform(a, b, c, d, e, f); context.drawImage(image, 0, 0); context.restore();
    }
    function drawTiredBlink(state,texture){
      if(!state.resting||state.tired.blink<.001)return;
      for(const eye of state.rig.eyes){
        const xs=[-2,-1.7,-1.1,-.55,0,.55,1.1,1.7,2];
        const ys=[-2.3,-1.6,-1,-.5,0,.5,1,1.6,2.3];
        const source=[],dest=[];
        for(const yy of ys)for(const xx of xs){
          const u=eye.u+xx*eye.rx,v=eye.v+yy*eye.ry;
          const amount=state.tired.blink*(1-smooth(1.1,1.7,Math.abs(xx)))*.84;
          const distance=Math.abs(yy),inner=1-amount;
          const warped=distance<=1?distance*inner:inner+(distance-1)*(2.3-inner)/1.3;
          const point=deform(u,eye.v+Math.sign(yy)*warped*eye.ry,state);
          source.push([u*texture.width,v*texture.height]);dest.push([puppy.x+point[0]*puppy.width,puppy.y+point[1]*puppy.height]);
        }
        for(let y=0;y<ys.length-1;y++)for(let x=0;x<xs.length-1;x++){
          const a=y*xs.length+x,b=a+1,c=a+xs.length,d=c+1;
          for(const ids of [[a,b,c],[b,d,c]])triangle(texture,ids.map(i=>source[i]),ids.map(i=>dest[i]),.12);
        }
      }
    }
    return {
      name: 'Canvas2D texture mesh',
      draw(state, visual) {
        const rect=canvas.getBoundingClientRect(),viewport=petSceneViewport(rect);
        const pixelX=canvas.width/rect.width,pixelY=canvas.height/rect.height;
        scenePixelScale=viewport.scale*pixelX;
        context.setTransform(scenePixelScale,0,0,viewport.scale*pixelY,viewport.x*pixelX,viewport.y*pixelY);
        context.drawImage(images.scene, 0, -view.cropY, view.width, 1848);
        if(visual.armPose){
          const destination=armSource.map(point=>armVertex(point,visual.armPose));
          for(let i=0;i<armMesh.indices.length;i+=3){
            const ids=[armMesh.indices[i],armMesh.indices[i+1],armMesh.indices[i+2]];
            if(ids.every(id=>Math.abs(destination[id].x-armSource[id].x)+Math.abs(destination[id].y-armSource[id].y)<.001))continue;
            triangle(images.scene,ids.map(id=>[armSource[id].x,armSource[id].y]),ids.map(id=>[destination[id].x,destination[id].y]));
          }
        }
        const points = [];
        for (let i = 0; i < mesh.vertices.length; i += 2) {
          const p = deform(mesh.vertices[i], mesh.vertices[i + 1], state);
          points.push([puppy.x + p[0] * puppy.width, puppy.y + p[1] * puppy.height]);
        }
        for (let i = 0; i < mesh.indices.length; i += 3) {
          const ids = [mesh.indices[i], mesh.indices[i + 1], mesh.indices[i + 2]];
          triangle(visual.texture||images.open, ids.map(id => [mesh.vertices[id * 2] * (visual.texture||images.open).width, mesh.vertices[id * 2 + 1] * (visual.texture||images.open).height]), ids.map(id => points[id]));
        }
        drawTiredBlink(state,visual.texture);
        if (!visual.texture && state.blink > 0.001) {
          context.save(); context.beginPath();
          for (const [u, v] of [[0.534, 0.257], [0.686, 0.252]]) {
            const center = deform(u, v, state);
            context.moveTo(puppy.x + center[0] * puppy.width + 0.065 * puppy.width * Math.cos(state.headAngle), puppy.y + center[1] * puppy.height + 0.065 * puppy.width * Math.sin(state.headAngle));
            context.ellipse(puppy.x + center[0] * puppy.width, puppy.y + center[1] * puppy.height, 0.065 * puppy.width, 0.046 * puppy.height, state.headAngle, 0, Math.PI * 2);
          }
          context.clip(); context.globalAlpha = state.blink;
          for (let i = 0; i < mesh.indices.length; i += 3) {
            const ids = [mesh.indices[i], mesh.indices[i + 1], mesh.indices[i + 2]];
            const us = ids.map(id => mesh.vertices[id * 2]), vs = ids.map(id => mesh.vertices[id * 2 + 1]);
            if (Math.max(...us) < 0.45 || Math.min(...us) > 0.78 || Math.max(...vs) < 0.19 || Math.min(...vs) > 0.32) continue;
            triangle(images.closed, ids.map(id => [mesh.vertices[id * 2] * images.closed.width, mesh.vertices[id * 2 + 1] * images.closed.height]), ids.map(id => points[id]));
          }
          context.restore();
        }
        context.save(); context.beginPath();
        bowlOutline.forEach(([x, y], i) => i ? context.lineTo(x, y - view.cropY) : context.moveTo(x, y - view.cropY));
        context.closePath(); context.clip(); context.drawImage(images.scene, 0, -view.cropY, view.width, 1848); context.restore();
        drawBall(context, images.ball, visual);
      }
    };
  }

 const renderer=canvasRenderer(images);let raf=0,last=0,clock=0,phase='idle',phaseAt=0,stage='puppy',energy=75,active=false,visible=true,dragPoint=null,onEnd=null,frames=0,tiredAt=0,lastDog=null,disposed=false;
 const reducedQuery=matchMedia('(prefers-reduced-motion: reduce)');let reduced=reducedQuery.matches;
 const reducedChanged=event=>{reduced=event.matches;tiredAt=clock;cancelAnimationFrame(raf);raf=0;last=0;draw();schedule();};reducedQuery.addEventListener?.('change',reducedChanged);
 function draw(){
  if(disposed||!active||document.hidden)return;
  const t=clock-phaseAt,r=phase==='refuse'?pulse(t,0,.3,.9,.5):phase==='pet'||phase==='welcome'?pulse(t,0,.35,1.5,.7):phase==='dog'?pulse(t,0,.35,1.8,.6):phase==='feed'?pulse(t,0,.4,1.9,.6):0;
  const resting=energy<20&&phase!=='feed'&&Boolean(images[stage+'-low-energy']);
  const standingRects={puppy:{x:64,y:863.438,width:600,height:600},juvenile:{x:24,y:812.344,width:650,height:650},adult:{x:49,y:747.656,width:700,height:700}};
  // Resting variants keep the original face, with prone bodies on the same carpet baseline.
  const restingRects={"puppy":{"x":151.658,"y":1000.405,"width":497.071,"height":497.071},"juvenile":{"x":146.291,"y":922.455,"width":587.332,"height":587.332},"adult":{"x":152.665,"y":844.04,"width":669.055,"height":669.055}};
  puppy=(resting?restingRects:standingRects)[stage];
  const actionTexture=images['action:'+phase+':'+stage];
  const target=resting?images[stage+'-low-energy']:actionTexture||(stage==='puppy'?null:images[stage]);
  let ball={x:625,y:1415},roll=0,lift=0;
  if(phase==='shared-waiting'&&dragPoint)ball=dragPoint;
  if(phase==='delivery'){const x=smooth(0,.6,t);ball={x:mix(625,490,x),y:mix(1415,1360,x)};}
  if(phase==='hand'){const x=smooth(.5,1.6,t);ball={x:mix(490,335,x),y:mix(1360,1465,x)};roll=-x*3.9;}
  if(phase==='dog'||phase==='shared-done')ball={x:335,y:1465};
  if(phase==='play'){ball=dragPoint||{x:400+Math.sin(t*3)*150,y:1430+Math.cos(t*3)*20};roll=t*2;}
  const rig=tiredRigs[stage],tired=resting?tiredMotion(Math.max(0,clock-tiredAt),rig,phase!=='idle'):null;
  const dog={rig,tired,resting,time:clock,breath:reduced?.4:Math.sin(clock*(resting?.85:1.65))*.5+.5,blink:target?0:Math.max(pulse((clock+1.2)%5.4,4.48,.09,4.59,.15),r*.8),headAngle:(reduced?0:Math.sin(clock*.7)*.007)+r*(phase==='feed'?-.045:phase==='refuse'?-.07:.038),headLift:phase==='feed'?.012*r:-.014*r,tailAngle:Math.sin(clock*(r?8:2.3))*(reduced?.01:.035+r*.1),earAngle:Math.sin(clock*1.8+.7)*.008};
  lastDog=dog;
  const feeding=phase==='feed'&&images.feeding&&stage==='puppy';
  renderer.draw(dog,{ball,roll,lift,armPose:phase==='hand'?armPose(t):null,showTarget:phase==='shared-waiting',texture:feeding?images.feeding:target});
  frames++;canvas.dataset.tiredMotion=resting?JSON.stringify(tired):'';canvas.dataset.stage=stage;canvas.dataset.pose=resting?'low-energy':'standing';canvas.dataset.dogRect=JSON.stringify(puppy);canvas.dataset.phase=phase;canvas.dataset.frames=String(frames);
 }
 const silhouettes=new Map();
 function hitTest(point){
  let inBowl=false;for(let i=0,j=bowlOutline.length-1;i<bowlOutline.length;j=i++){const [xi,yi]=bowlOutline[i],[xj,yj]=bowlOutline[j];if((yi>point.y)!==(yj>point.y)&&point.x<(xj-xi)*(point.y-yi)/(yj-yi)+xi)inBowl=!inBowl;}if(inBowl)return false;
  const resting=energy<20&&phase!=='feed'&&images[stage+'-low-energy'];
  const image=resting||images['action:'+phase+':'+stage]||((phase==='feed'&&stage==='puppy')?images.feeding:images[stage]);
  const baseU=(point.x-puppy.x)/puppy.width,baseV=(point.y-puppy.y)/puppy.height;let u=baseU,v=baseV;
  if(resting&&lastDog?.resting){for(let n=0;n<4;n++){const p=deform(u,v,lastDog);u+=baseU-p[0];v+=baseV-p[1];}}
  if(u<0||u>=1||v<0||v>=1)return false;
  if(!silhouettes.has(image)){const mask=document.createElement('canvas');mask.width=image.width;mask.height=image.height;const ctx=mask.getContext('2d');ctx.drawImage(image,0,0);silhouettes.set(image,ctx.getImageData(0,0,image.width,image.height).data);}
  return silhouettes.get(image)[(Math.floor(v*image.height)*image.width+Math.floor(u*image.width))*4+3]>=32;
 }
 function tick(now){raf=0;if(disposed||!active||!visible||document.hidden||(reduced&&phase==='idle'))return;if(!last||now-last>=32){clock+=last?Math.min((now-last)/1000,.1):0;last=now;draw();const duration={pet:2.3,feed:2.8,refuse:1.5,welcome:2.4,delivery:.6,hand:1.8,dog:2.5};if(duration[phase]&&clock-phaseAt>=duration[phase]){const ended=phase;phase='idle';phaseAt=clock;if(energy<20)tiredAt=clock;onEnd?.(ended);}}schedule();}
 function schedule(){if(!disposed&&!raf&&active&&visible&&!document.hidden&&!(reduced&&phase==='idle'))raf=requestAnimationFrame(tick);}
 function resize(){if(disposed||document.hidden)return;const b=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2);const w=Math.round(b.width*dpr),h=Math.round(b.height*dpr);if(w&&h&&(canvas.width!==w||canvas.height!==h)){canvas.width=w;canvas.height=h;}draw();}
 const observer=new ResizeObserver(resize);observer.observe(canvas);
 const visibilityChanged=()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;last=0;}else{last=0;resize();schedule();}};
 document.addEventListener('visibilitychange',visibilityChanged);
 return{start(){if(disposed)return;active=true;resize();schedule();},stop(){active=false;cancelAnimationFrame(raf);raf=0;last=0;},setStage(value){if(disposed)return;if(value!==stage)tiredAt=clock;stage=value;draw();},setEnergy(value){if(disposed)return;if((value<20)!==(energy<20))tiredAt=clock;energy=value;draw();},setPhase(value){if(disposed)return;if(value==='idle'&&phase!=='idle')tiredAt=clock;phase=value;phaseAt=clock;if(reduced&&phase==='idle'){cancelAnimationFrame(raf);raf=0;last=0;}draw();schedule();},setBall(point){dragPoint=point;draw();},onEnd(fn){onEnd=fn;},hitTest,
  clientPoint(point){return clientToPetScene(canvas,point);},
  snapshot(){return disposed?null:canvas.toDataURL('image/jpeg',.8);},draw,
  dispose(){if(disposed)return;disposed=true;active=false;cancelAnimationFrame(raf);raf=0;onEnd=null;observer.disconnect();document.removeEventListener('visibilitychange',visibilityChanged);reducedQuery.removeEventListener?.('change',reducedChanged);silhouettes.clear();for(const image of Object.values(images))if(image instanceof HTMLImageElement)image.src='';}};
}

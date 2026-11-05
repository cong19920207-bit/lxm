const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
/** The old interval is readable before qualification; opening prose never sends a model request. */
export async function mountReturn(view,{root,api,principalId}){
 const scope=view.scope,panel=document.createElement('section');panel.className='pet-return';root.append(panel);scope.own(()=>panel.remove());
 let data=null,expanded=false,dismissed=false,busy=false,epoch=0;
 function render(){
  if(!scope.active)return;
  const host=root.querySelector('[data-return-slot]');if(host&&panel.parentElement!==host)host.append(panel);panel.hidden=!host;
  if(!data||!['home','return','return-review'].includes(view.route)){panel.innerHTML='';return;}
  const intro=data.show_intro&&!dismissed;
  panel.innerHTML=(intro?'<h2>'+escape(data.welcome)+'</h2>':'')+(intro&&data.highlights?.length?'<article aria-label="这段时间的近况"><h3>这段时间的近况</h3><ul>'+data.highlights.map(f=>'<li data-source-event="'+escape(f.event_id)+'">'+escape(f.title)+(f.source==='rule_settlement'?' · 规则记录':'')+'</li>').join('')+'</ul></article>':'')+'<button type="button" class="text-button return-review-link" data-return="read">看看这段时间</button>'+(intro?'<button type="button" class="primary" data-return="home">回到日常</button>':'');
  if(expanded){
   panel.innerHTML+='<article aria-label="离开期间"><h3>离开期间</h3><p>'+escape(data.past_body)+'</p></article>';
   if(data.current_body)panel.innerHTML+='<article aria-label="本次回来后的互动"><h3>本次回来后的互动</h3><p>'+escape(data.current_body)+'</p></article>';
   panel.innerHTML+='<button type="button" class="text-button" data-return="close">收起回顾</button>';
  }
 }
 async function refresh(){
  if(!data||busy||!scope.active)return;busy=true;const ticket=epoch;
  try{const result=await api.call('/returns/'+data.id);if(scope.active&&ticket===epoch){data={...data,...result,show_intro:data.show_intro};render();}}
  catch(_){}finally{busy=false;}
 }
 scope.listen(panel,'click',event=>{const action=event.target.closest('[data-return]')?.dataset.return;
  if(action==='read'){expanded=true;view.go('return-review');render();void refresh();}
  if(action==='close'){expanded=false;view.go(data?.show_intro&&!dismissed?'return':'home');render();}
  if(action==='home'){dismissed=true;expanded=false;view.go('home');render();}
 });
 scope.listen(root,'pet:render',()=>{epoch++;render();});scope.listen(root,'pet:completed',()=>void refresh());scope.listen(root,'pet:active',()=>{if(!data?.confirmed)void refresh();});
 scope.interval(()=>{if(expanded&&data?.pending&&!document.hidden)void refresh();},2000);
 if(principalId&&view.pet&&api.call){
  try{
   const result=await api.call('/returns/entry','POST',{});
   if(scope.active&&result?.id&&result?.absence_id&&result.coverage_end){
    data=result;
    if(result.pet&&result.pet.record_version>=view.pet.record_version)view.setPet(result.pet);
    if(result.show_intro&&view.route==='home'){view.go('return');void view.scene.play('welcome');}
   }
  }catch(_){}
 }
 render();return {refresh,inspect:()=>({data,expanded,dismissed})};
}

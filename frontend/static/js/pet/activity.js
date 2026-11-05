/** Count only ready, visible pet surfaces; reloads start new server sessions. */
export function mountActivity(view,{root,api,principalId}){
 const scope=view.scope;let session=null,sequence=0,busy=false,disposed=false;
 const surface=()=>view.route==='home'?'scene':view.route;
 const valid=()=>principalId&&view.pet&&view.scene.inspect().available&&!document.hidden&&['scene','records','album','event','profile','growth','photo','birthday','preference'].includes(surface());
 async function beat(){
  if(busy||disposed||!scope.active||!api.call)return;busy=true;
  try{
   if(!session){if(!valid())return;const result=await api.call('/view-sessions','POST',{});if(result?.id)session=result;return;}
   const result=await api.call('/view-sessions/'+session.id+'/heartbeat','POST',{sequence:++sequence,foreground:Boolean(valid()),surface:surface()});
   if(scope.active&&result?.qualified)root.dispatchEvent(new CustomEvent('pet:active',{detail:result}));
  }catch(_){session=null;sequence=0;}finally{busy=false;}
 }
 scope.interval(()=>void beat(),5000);scope.listen(document,'visibilitychange',()=>void beat());
 scope.listen(root,'pet:render',()=>{if(!session)void beat();});scope.own(()=>{disposed=true;});void beat();
 return {inspect:()=>({session,sequence}),beat};
}

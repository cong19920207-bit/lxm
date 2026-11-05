export function plainPetText(value){
 const decoded=document.createElement('textarea');decoded.innerHTML=String(value).replace(/!?\[([^\]]*)\]\([^)]*\)/g,'$1').replace(/<[^>]*>/g,'');
 return decoded.value.replace(/[\s*_`#~]/gu,'');
}
export const countPetText=value=>Array.from(plainPetText(value)).length;
/** Read only: late wording is discarded once the user moves on. */
export function mountExpression(view,{root,api}){
 let epoch=0;const scope=view.scope;
 const invalidate=()=>{epoch++;};scope.listen(root,'pointerdown',invalidate);scope.listen(root,'click',invalidate);scope.listen(root,'pet:render',invalidate);
 scope.listen(document,'visibilitychange',()=>{if(document.hidden)invalidate();});
 async function read(eventId,ticket,remaining=15){
  if(!eventId||!scope.active||ticket!==epoch||document.hidden)return;
  try{
   const result=await api.call('/expressions/'+encodeURIComponent(eventId));
   if(!scope.active||ticket!==epoch||document.hidden||result?.stale)return;
   if(result?.source==='model'&&result.body)view.notify(plainPetText(result.body));
   else if(result?.pending&&remaining>0)scope.timeout(()=>void read(eventId,ticket,remaining-1),2000);
  }catch(_){} // The already-confirmed action and template remain available.
 }
 scope.listen(root,'pet:completed',event=>{const ticket=++epoch;void read(event.detail.event_id,ticket);});
 return {inspect:()=>({epoch})};
}

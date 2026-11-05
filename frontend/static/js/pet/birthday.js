export async function mountBirthday(view,{root,api}){
 const scope=view.scope;
 if(!view.pet||view.route!=='home'||typeof api.call!=='function')return;
 try{
  const card=await api.call('/birthday');
  if(!scope.active||!card?.event_id||view.route!=='home'||view.interactions.inspect().attempt||view.photos.inspect().attempt)return;
  const panel=document.createElement('section');panel.className='pet-birthday';
  const title=document.createElement('h2');title.textContent=card.body;
  const date=document.createElement('p');date.textContent=card.date+' · 游戏内生日纪念';
  const note=document.createElement('p');note.textContent=card.note;
  const button=document.createElement('button');button.type='button';button.textContent='回去陪陪它';
  panel.append(date,title,note,button);root.append(panel);scope.own(()=>panel.remove());
  scope.listen(button,'click',()=>{panel.remove();view.go('home');});
  scope.listen(root,'pet:render',()=>{panel.hidden=view.route!=='birthday';});
  view.go('birthday');root.querySelector('[data-birthday-slot]')?.append(panel);
 }catch(_){/* A failed optional birthday read does not block the room. */}
}

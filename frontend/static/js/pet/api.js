// Read-only recovery never resubmits a timed-out mutation.
const reasons={invalid_name:'名字不合法，请使用可见字符，并去掉尖括号或换行。',storage_unavailable:'照片存储暂时不可用，请稍后查询原结果。',photo_not_ready:'照片仍在确认中，请稍后查询原结果。',pet_busy:'它正在另一端互动，请稍后再来。',adoption_disabled:'领养暂未开放，可以稍后再来看看。',pet_configuration_unpublished:'它的房间还没有准备好，请稍后再来。',interactions_disabled:'房间正在维护，暂时不能互动。',joint_disabled:'共同陪玩暂时不可用，可以先自己陪它。',low_energy:'它有点困了，先轻抚或安静留影吧。',invite_cooldown:'刚刚邀请过小梦，等一会儿再试吧。',stage_not_allowed:'它现在的成长阶段还不能进行这项互动。',scene_not_ready:'画面还没准备好，先看看档案和回忆吧。',resource_unavailable:'画面素材暂不可用，请重新加载。',resource_version_changed:'画面已更新，请重新准备这一张留影。',scene_snapshot_stale:'它的状态有了变化，请重新拍摄。',invalid_or_empty_photo:'这张照片还没准备好，请重新拍摄。',preparation_required:'先吸引它看向镜头，再一起留一张。',capture_required:'先拍下一张照片，再收进事件册。',photo_expired:'这次拍摄已结束，可以重新留一张。',storage_unknown:'正在确认照片保存结果，请查询原结果。',pet_not_found:'还没有找到你的宠物，可以重新打开看看。'};
export function petReason(reason,fallback='暂时未能完成，请稍后重试。'){return reasons[reason]||fallback;}
export function createPetApi({request,signal}) {
  const call=async(path,method='GET',body)=>{
    const result=await request('/api/pet'+path,{method,signal,...(body?{body:JSON.stringify(body),headers:{'Content-Type':'application/json'}}:{})});
    if(Array.isArray(result?.detail)){const error=new Error('提交内容不合法，请检查后重试。');error.code=422;error.unknown=false;throw error;}
    if(!result||result.code!==0){const unknown=!result||result.code===-1;const error=new Error(unknown?'请求结果暂未确认，请查询原结果。':petReason(result.data?.reason,result.message||'暂时未能完成，请稍后重试。'));if(!unknown)error.code=result.code;error.unknown=unknown;error.reason=result?.data?.reason;throw error;}
    return result.data;
  };
  return {read:()=>call('/me'),adopt:body=>call('/adopt','POST',body),adoptionResult:()=>call('/adoption-result'),rename:body=>call('/rename','POST',body),call};
}

/** A bounded cancellation channel owns only the credential captured at mount.
 * It outlives route abort, cannot start/finish an action, and never updates UI/auth. */
export function createPetRelease({token,request=fetch,timeoutMs=5000}){
 return async(kind,id,requestKey)=>{
  if(!token||!['touch','play','joint_ball','photo'].includes(kind))return false;
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs),headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
  try{
   if(!id&&/^[-a-zA-Z0-9_:]{1,96}$/.test(requestKey||'')){for(let n=0;n<3&&!id;n++){const response=await request('/api/pet/interaction-requests/'+encodeURIComponent(requestKey),{headers,signal:controller.signal,keepalive:true});if(!response.ok)return false;const value=await response.json();if(value.code===0&&value.data?.kind===kind)id=value.data.id;if(!id)await new Promise(resolve=>setTimeout(resolve,150));}}
   if(!/^[-a-zA-Z0-9_]{1,64}$/.test(id||''))return false;
   const path=kind==='photo'?'/photos/'+id+'/cancel':kind==='joint_ball'?'/joint/'+id+'/cancel':'/interactions/'+id+'/finish';
   const r=await request('/api/pet'+path,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(kind==='touch'||kind==='play'?{cancel:true}:{}),signal:controller.signal,keepalive:true});return r.ok&&(await r.json()).code===0;}
  catch(_){return false;}finally{clearTimeout(timer);}
 };
}

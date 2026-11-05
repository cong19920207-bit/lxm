// One centered, aspect-preserving cover transform for artwork and pointer coordinates.
export const PET_SCENE_SIZE=Object.freeze({width:851,height:1848});
export function petSceneViewport(rect){
 const scale=Math.max(rect.width/PET_SCENE_SIZE.width,rect.height/PET_SCENE_SIZE.height)||1;
 return {scale,x:(rect.width-PET_SCENE_SIZE.width*scale)/2,y:(rect.height-PET_SCENE_SIZE.height*scale)/2};
}
export function clientToPetScene(canvas,point){
 const rect=canvas.getBoundingClientRect(),view=petSceneViewport(rect);
 return {x:(point.clientX-rect.left-view.x)/view.scale,y:(point.clientY-rect.top-view.y)/view.scale};
}
export function petSceneToClient(canvas,point){
 const rect=canvas.getBoundingClientRect(),view=petSceneViewport(rect);
 return {x:rect.left+view.x+point.x*view.scale,y:rect.top+view.y+point.y*view.scale};
}

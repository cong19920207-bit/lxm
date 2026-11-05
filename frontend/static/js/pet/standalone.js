import {AuthService} from '../app/auth-service.js';
import {createPageContext} from '../app/page-context.js';
import {mount} from './entry.js';
const root=document.querySelector('#pet-page'),markup=root.innerHTML;let page,context,generation=0;
const auth=new AuthService({beforeChange:()=>{context?.scope.dispose('identity-change');root.replaceChildren();},onChange:()=>void enter()});
const router={navigate:url=>location.assign(url)};
async function enter(){
 const ticket=++generation;await context?.scope.dispose('remount');if(ticket!==generation)return;
 root.innerHTML=markup;context=createPageContext({root,route:{name:'pet',search:''},routeEpoch:ticket,router,services:{auth},isCurrent:()=>ticket===generation});
 page=await mount(context);if(ticket!==generation)await page?.unmount();
}
window.addEventListener('pagehide',()=>{generation++;void context?.scope.dispose('pagehide');root.replaceChildren();});
window.addEventListener('pageshow',event=>{if(event.persisted){auth.refresh();void enter();}});
void enter();

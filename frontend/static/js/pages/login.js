import { AuthFormSession, formRules } from '../app/auth-interactions.js';

export function mount(context) {
  const {root, services} = context, byId = id => root.querySelector('#' + id);
  const fields = {login:'login', register:'reg', reset:'reset'}, labels = {login:'登录', register:'注册', reset:'重置密码'};
  let active = 'login';
  const values = panel => { const prefix = fields[panel]; return {username:byId(prefix+'-username').value.trim(),
    password:byId(prefix+'-password').value, password2:byId(prefix+'-password2')?.value}; };
  function clearSensitive() {
    for (const input of root.querySelectorAll('input[id*="password"]')) { input.value=''; input.type='password'; }
    for (const button of root.querySelectorAll('[data-login-eye]')) { button.textContent='👁'; button.setAttribute('aria-label','显示密码'); }
  }
  function update(panel) {
    const value=values(panel), button=byId('btn-'+panel);
    const enabled=formRules.username.test(value.username)&&formRules.password.test(value.password)&&(panel==='login'||value.password===value.password2);
    button.disabled=form.busy||!enabled; button.classList.toggle('disabled',button.disabled);
  }
  function updateAll(){for(const panel of Object.keys(fields))update(panel)}
  const form = new AuthFormSession({auth:services.auth, router:context.router, mode:'standalone', ownerId:context.scope.ownerId,
    current:context.valid, routeCurrent:()=>context.router.current?.context.routeEpoch===context.routeEpoch,
    clearSensitive, submitting:(panel,busy)=>{byId('btn-'+panel).textContent=busy?(panel==='reset'?'重置中...':labels[panel]+'中...'):labels[panel];updateAll();}
  });
  context.cleanup(()=>form.dispose(),{priority:80,kind:'auth-form'});
  function clearErrors(){for(const input of root.querySelectorAll('.input-field'))input.classList.remove('error');for(const error of root.querySelectorAll('.field-error')){error.textContent='';error.classList.remove('visible')}}
  function switchPanel(panel){
    if(!Object.hasOwn(fields,panel))return;
    if(active!==panel){form.cancel();byId('btn-'+active).textContent=labels[active];active=panel;}
    for(const element of root.querySelectorAll('.form-panel'))element.classList.toggle('active',element.id==='panel-'+panel);
    clearErrors();updateAll();
  }
  function validate(input){
    const id=input.id,error=byId(id+'-error');if(!error)return;
    const value=id.endsWith('username')?input.value.trim():input.value;
    let message='';
    if(value){
      if(id.endsWith('password2'))message=value!==byId(id.slice(0,-1)).value?'两次密码不一致':'';
      else if(id.endsWith('username'))message=formRules.username.test(value)?'':'账号需要6-20位字母或数字';
      else message=formRules.password.test(value)?'':'密码需要8-20位，同时包含字母和数字';
    }
    input.classList.toggle('error',!value||!!message);error.textContent=message;error.classList.toggle('visible',!!message);
  }
  async function submit(panel){
    if(panel!==active||byId('btn-'+panel).disabled||!context.valid())return;
    const outcome=await form.submit(panel,values(panel),{remember:byId('remember-me').checked});
    if(!context.valid())return;
    if(outcome.status==='success'){
      switchPanel('login');byId('login-username').value=outcome.username;updateAll();
      services.ui.toast(panel==='register'?'注册成功，请登录':'密码重置成功，请登录','success');
    }else if(outcome.status==='error'){
      const seconds=outcome.result.data?.remaining_seconds;
      services.ui.toast(seconds?'密码错误次数过多，请'+Math.ceil(seconds/60)+'分钟后重试':outcome.result.message||labels[panel]+'失败','error');
    }
  }
  context.scope.listen(root,'click',event=>{
    const eye=event.target.closest('[data-login-eye]');
    if(eye){const input=byId(eye.dataset.loginEye),hidden=input.type==='password';input.type=hidden?'text':'password';eye.textContent=hidden?'🙈':'👁';eye.setAttribute('aria-label',hidden?'隐藏密码':'显示密码');return;}
    const panel=event.target.closest('[data-login-panel]');if(panel)return switchPanel(panel.dataset.loginPanel);
    const button=event.target.closest('[data-login-submit]');if(button)void submit(button.dataset.loginSubmit);
  });
  context.scope.listen(root,'input',()=>update(active));
  context.scope.listen(root,'focusout',event=>{if(event.target.matches('.input-field'))validate(event.target)});
  context.scope.listen(root,'keydown',event=>{
    if(event.key==='Enter'&&!event.isComposing&&event.target.matches('.input-field')){event.preventDefault();void submit(active);}
  });
  const saved=context.state;
  if(typeof saved?.remember==='boolean'){
    byId('remember-me').checked=saved.remember;
    if(saved.remember&&typeof saved.username==='string')byId('login-username').value=saved.username;
  }else{
    const remembered=services.auth.storage('getItem','remember_username').value;
    if(remembered){byId('login-username').value=remembered;byId('remember-me').checked=true;}
  }
  updateAll();
  // The router owns the login blocker before mount; no content adapter may initiate playback here.
  return {
    captureState(){const remember=byId('remember-me').checked;return {remember,...(remember?{username:byId('login-username').value}:{})};},
    unmount(){clearSensitive()}
  };
}

/* Home-only, independently rendered modules sharing bounded request batches. */
(function () {
  'use strict'
  const paths = {
    relationship: '/api/relationship/status', days: '/api/relationship/detail',
    diary: '/api/diary/list?page=1&page_size=1', unread: '/api/agent/unread-count',
    feedList: '/api/feed/list?size=8', feedBadge: '/api/feed/badge',
  }
  const validData = {
    relationship: data => Number.isInteger(data.level) && data.level >= 0 && data.level <= 3,
    days: data => data.milestones != null,
    diary: data => Array.isArray(data.items),
    unread: data => Number.isFinite(data.count) && data.count >= 0,
    feedList: data => Array.isArray(data.posts),
    feedBadge: data => Number.isFinite(data.unread_reply_count) && Number.isFinite(data.new_post_count),
  }
  let instance
  function mount(render) {
    if (instance) return instance
    const states = Object.fromEntries(Object.keys(paths).map(key => [key, { status:'pending', data:null, version:0 }]))
    const batches = new Set()
    let snapshot, disposed = false, generation = 0
    const same = (a,b) => a && b && a.known === b.known && a.token === b.token
    const auth = () => window.HomeStartup.auth()
    function notify(key) { render.state(key, states[key]) }
    function valid(batch, key) {
      if (batch.active && Date.now() >= batch.deadline) deadline(batch)
      return !disposed && batch.active && same(batch.auth, auth()) && (!key || states[key].version === batch.versions[key])
    }
    function finish(batch) {
      if (!batch.active) return
      batch.active = false; clearTimeout(batch.timer); batches.delete(batch); batch.resolve()
    }
    function cancel(batch) { batch.controller.abort(); finish(batch) }
    function deadline(batch) {
      if (!batch.active || Date.now() < batch.deadline) return
      if (same(batch.auth, auth())) {
        for (const key of batch.pending) {
          if (states[key].version === batch.versions[key]) { states[key].status = 'error'; notify(key) }
        }
      }
      cancel(batch)
    }
    function changeAuth() {
      if (disposed) return
      const next = auth()
      if (same(snapshot,next)) return
      for (const batch of [...batches]) cancel(batch)
      snapshot = next; generation++
      render.auth(next)
      for (const [key,state] of Object.entries(states)) {
        state.version++; state.data = null
        state.status = next.token ? 'pending' : (key === 'feedList' ? 'pending' : (next.known ? 'visitor' : 'unknown'))
        notify(key)
      }
      start(next.token ? Object.keys(paths) : ['feedList'])
    }
    function start(keys) {
      if (disposed) return Promise.resolve()
      if (!same(snapshot,auth())) { changeAuth(); return Promise.resolve() }
      keys = keys.filter(key => key === 'feedList' || snapshot.token)
      const existing = [...batches].find(b => keys.every(key => b.pending.has(key)))
      if (existing) return existing.promise
      // A module cannot be refreshed twice while its current request is pending.
      const waiting = [...batches].filter(b => keys.some(key => b.pending.has(key))).map(b=>b.promise)
      keys = keys.filter(key => ![...batches].some(b => b.pending.has(key)))
      if (!keys.length) return Promise.all(waiting)
      const batch = { auth:{...snapshot}, generation, controller:new AbortController(), active:true,
        deadline:Date.now()+8000, pending:new Set(keys), versions:{}, promise:null, timer:null }
      batch.promise = new Promise(resolve => batch.resolve = resolve)
      batches.add(batch)
      for (const key of keys) {
        const state = states[key]; state.version++; state.status = 'pending'
        batch.versions[key] = state.version; notify(key)
      }
      batch.timer = setTimeout(()=>deadline(batch),8000)
      for (const key of keys) {
        const version = states[key].version
        const isViewCurrent = () => !disposed && same(batch.auth,auth()) && states[key].version === version
        request('GET',paths[key],null,{signal:batch.controller.signal,isCurrent:()=>valid(batch,key),
          authPolicy:AUTH_401_POLICIES.SILENT_VISITOR,onUnauthorized:changeAuth})
          .then(result=>{
            if (!valid(batch,key)) return
            if (result.code === 0 && result.data != null && validData[key](result.data)) {
              states[key].data = result.data; states[key].status = 'success'
              render.success(key,result.data,isViewCurrent)
            } else states[key].status = 'error'
            notify(key)
          }).catch(error=>{
            if (valid(batch,key) && error.name !== 'AbortError' && error.name !== 'StaleRequestError') {
              states[key].status='error'; notify(key)
            }
          }).finally(()=>{
            batch.pending.delete(key)
            if (!batch.pending.size) finish(batch)
            if (!same(snapshot,auth())) changeAuth()
          })
      }
      return Promise.all([...waiting,batch.promise])
    }
    const onStorage = event => { if (!event.key || event.key === 'token') changeAuth() }
    const onVisible = () => {
      if (document.hidden) return
      for (const batch of [...batches]) deadline(batch)
      if (!same(snapshot,auth())) changeAuth()
      else start(snapshot.token ? ['feedList','feedBadge'] : ['feedList'])
    }
    const onShow = () => { for (const batch of [...batches]) deadline(batch); if(!same(snapshot,auth())) changeAuth() }
    function destroy() {
      if(disposed) return
      disposed=true; for(const batch of [...batches]) cancel(batch)
      window.removeEventListener('home-auth-change',changeAuth); window.removeEventListener('storage',onStorage)
      window.removeEventListener('pageshow',onShow); window.removeEventListener('pagehide',onHide)
      document.removeEventListener('visibilitychange',onVisible)
    }
    const onHide = event => { if(!event.persisted) destroy() }
    window.addEventListener('home-auth-change',changeAuth); window.addEventListener('storage',onStorage)
    window.addEventListener('pageshow',onShow); window.addEventListener('pagehide',onHide)
    document.addEventListener('visibilitychange',onVisible)
    instance = {load:()=>{if(!same(snapshot,auth())){changeAuth();return Promise.all([...batches].map(b=>b.promise))}return start(snapshot.token?Object.keys(paths):['feedList'])},
      feed:()=>start(snapshot?.token?['feedList','feedBadge']:['feedList']),retry:key=>start([key]),destroy,
      inspect:()=>({generation,batches:batches.size,disposed,modules:Object.fromEntries(Object.entries(states).map(([k,v])=>[k,{status:v.status,hasData:v.data!=null}]))})}
    changeAuth()
    return instance
  }
  window.HomeData = {mount}
})()

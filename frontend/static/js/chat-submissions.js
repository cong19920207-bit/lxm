/* Fixed STEP-002 observation budgets. These timers never grant generation time. */
(function (global) {
  'use strict'
  const TIMING = Object.freeze({
    text_status_poll_interval_ms: 2000, text_status_poll_max_interval_ms: 10000,
    text_status_poll_backoff_factor: 2, text_status_probe_timeout_ms: 3000,
    text_status_reconcile_margin_ms: 60000, text_admission_reconcile_window_ms: 240000,
    text_status_max_inflight_per_target: 1, text_status_max_inflight_per_page: 2,
    text_local_submission_retention_seconds: 604800, text_client_transport_margin_ms: 20000,
    text_business_deadline_ms: 180000
  })
  function encodeRequestId(raw) {
    const bytes = new TextEncoder().encode(raw)
    let binary = ''
    bytes.forEach(byte => { binary += String.fromCharCode(byte) })
    return 'b64.' + btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  }
  function compareRevision(a, b) {
    if (!/^\d+$/.test(a || '') || !/^\d+$/.test(b || '')) return null
    a = a.replace(/^0+(?=\d)/, ''); b = b.replace(/^0+(?=\d)/, '')
    return a.length === b.length ? (a === b ? 0 : a > b ? 1 : -1) : a.length > b.length ? 1 : -1
  }
  // JWT claims choose only the local namespace. Every GET still authenticates on the server.
  function userFromToken(token) {
    try {
      const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
      const value = JSON.parse(atob(part)).user_id
      return Number.isInteger(value) && value > 0 ? String(value) : null
    } catch (_) { return null }
  }
  const keyOf = (operation, id) => operation + ':' + id
  class Reconciler {
    constructor(options) {
      this.options = options; this.records = new Map(); this.user = null
      this.timer = null; this.epoch = 0; this.inflight = 0; this.timing=TIMING
    }
    configure(config) { this.timing=Object.freeze({...config}) }
    active() { return this.user && this.user === this.options.user() && this.options.active() }
    save() {
      if (!this.user) return
      const records = [...this.records.values()].filter(r => !r.terminal).map(r => ({
        operation:r.operation, request_id:r.request_id, submitted_at:r.submitted_at,
        until:r.until, exhausted:Boolean(r.exhausted), effective_generation_id:r.effective_generation_id || null,
        effective_deadline_at:r.effective_deadline_at || null, state_revision:r.state_revision || null,
        source_messages:r.source_messages || []
      }))
      localStorage.setItem('chat_submissions:' + this.user, JSON.stringify(records))
    }
    restore(user) {
      this.pause(); this.records.clear(); this.user = user
      if (!user) return
      let saved = []
      try { saved = JSON.parse(localStorage.getItem('chat_submissions:' + user) || '[]') } catch (_) {}
      if (Array.isArray(saved)) saved.forEach(r => {
        if (!['send','resend'].includes(r.operation) || typeof r.request_id !== 'string' ||
          r.request_id.length > (r.operation === 'send' ? 64 : 128) || !Number.isFinite(r.submitted_at) || !Number.isFinite(r.until)) return
        if (Date.now() - r.submitted_at >= this.timing.text_local_submission_retention_seconds * 1000) {
          this.options.unknown(r); return
        }
        // Reconstruct a whitelist; never copy arbitrary storage into the live record.
        this.records.set(keyOf(r.operation,r.request_id), {
          operation:r.operation, request_id:r.request_id, submitted_at:r.submitted_at, until:r.until,
          exhausted:Boolean(r.exhausted), effective_generation_id:r.effective_generation_id || null,
          effective_deadline_at:r.effective_deadline_at || null, state_revision:r.state_revision || null,
          source_messages:Array.isArray(r.source_messages)?r.source_messages.map(s=>({source:'user',id:s.id,sort_seq:s.sort_seq})):[],
          next:Date.now(), interval:this.timing.text_status_poll_interval_ms
        })
      })
      this.save(); this.wake(true)
    }
    start(operation, id) {
      if (!this.user || this.user !== this.options.user()) throw new Error('chat_identity_unavailable')
      const now = Date.now()
      const r = {operation,request_id:id,submitted_at:now,until:now+this.timing.text_admission_reconcile_window_ms,
        next:now,interval:this.timing.text_status_poll_interval_ms,source_messages:[]}
      this.records.set(keyOf(operation,id),r)
      this.save() // Must complete before the first POST, including pre-meta network failure.
      return r
    }
    pause() {
      this.epoch++; clearTimeout(this.timer); this.timer = null
      this.records.forEach(r => { if (r.controller) r.controller.abort(); r.controller = null; r.querying = false })
      this.inflight = 0
    }
    detach() { this.pause(); this.user = null; this.records.clear() }
    wake(explicit = false) {
      if (!this.active()) return
      const now = Date.now()
      this.records.forEach(r => {
        if (r.terminal || r.querying) return
        if (r.exhausted || now >= r.until) {
          r.exhausted = true
          if (explicit) r.once = true
          else this.options.unknown(r)
        }
        r.next = now
      })
      this.save(); this.pump()
    }
    apply(r, status) {
      if (this.records.get(keyOf(r.operation,r.request_id)) !== r || !this.active() || status.operation !== r.operation || status.request_id !== r.request_id) return false
      const revision = status.state_revision
      const comparison = r.state_revision ? compareRevision(revision,r.state_revision) : null
      if (r.state_revision && (comparison === null || comparison < 0)) return false
      if (r.terminal && (comparison === null || comparison <= 0)) return false
      if (typeof revision === 'string' && /^\d+$/.test(revision)) {
        const changed = status.effective_generation_id && status.effective_generation_id !== r.effective_generation_id
        const deadline = Date.parse(status.effective_deadline_at)
        if (Number.isFinite(deadline) && (!r.effective_generation_id || (changed && comparison > 0))) {
          r.effective_generation_id = status.effective_generation_id
          r.effective_deadline_at = status.effective_deadline_at
          // Derive from the original server D. Never extend this same generation on a repeated GET.
          const serverUntil = Date.parse(status.reconcile_until)
          r.until = Number.isFinite(serverUntil) ? serverUntil : deadline + this.timing.text_status_reconcile_margin_ms
        }
        r.state_revision = revision
      }
      if (Array.isArray(status.source_messages) && status.source_messages.length) {
        r.source_messages = status.source_messages.map(s => ({source:'user',id:s.id,sort_seq:s.sort_seq}))
      }
      const terminal = status.admission_state === 'accepted' && ['success','failed','superseded'].includes(status.processing_state)
      // Success without durable reply identity cannot be declared locally complete.
      r.terminal = terminal && (status.processing_state !== 'success' || Boolean(status.result &&
        status.result.messages && status.result.messages.length && status.result.messages.every(m => m.id != null)))
      this.options.update(r,status)
      this.save(); return true
    }
    pump() {
      clearTimeout(this.timer); this.timer = null
      if (!this.active()) return
      const now = Date.now()
      for (const r of this.records.values()) {
        if (r.terminal || r.querying) continue
        if (now >= r.until && !r.exhausted) { r.exhausted=true; this.options.unknown(r); this.save() }
        if (r.exhausted && !r.once) continue
        if (r.next <= now && this.inflight < this.timing.text_status_max_inflight_per_page) this.probe(r)
      }
      const due = [...this.records.values()].filter(r => !r.terminal && !r.querying && (!r.exhausted || r.once))
      if (due.length && this.inflight < this.timing.text_status_max_inflight_per_page) {
        this.timer=setTimeout(()=>this.pump(),Math.max(1,Math.min(...due.map(r=>Math.min(r.next,r.exhausted?Infinity:r.until)))-Date.now()))
      }
    }
    async probe(r) {
      const epoch=this.epoch; r.querying=true; r.once=false; this.inflight++
      const controller=new AbortController(); r.controller=controller
      const remaining=r.exhausted ? this.timing.text_status_probe_timeout_ms : Math.max(1,r.until-Date.now())
      const timer=setTimeout(()=>controller.abort(),Math.min(this.timing.text_status_probe_timeout_ms,remaining))
      try {
        const response=await this.options.fetch(r,controller.signal)
        if (epoch !== this.epoch || !this.active()) return
        if (!response || response.code !== 0 || !response.data) throw new Error('status_unavailable')
        this.apply(r,response.data)
        r.interval=this.timing.text_status_poll_interval_ms
      } catch (_) {
        if (epoch !== this.epoch) return
        this.options.unknown(r)
        r.interval=Math.min(this.timing.text_status_poll_max_interval_ms,r.interval*this.timing.text_status_poll_backoff_factor)
      } finally {
        clearTimeout(timer)
        if (epoch === this.epoch) {
          r.controller=null; r.querying=false; this.inflight--
          r.next=Date.now()+r.interval
          this.pump()
        }
      }
    }
  }
  global.ChatSubmissions = {TIMING,encodeRequestId,compareRevision,userFromToken,Reconciler}
})(window)

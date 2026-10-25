import { createPageTimers } from '../app/page-timers.js';

export async function mount(context) {
  const {root,services} = context, byId = id => root.querySelector('#'+id)
  if (!context.valid() || !services.auth.snapshot().authenticated) return {unmount(){}}
  await context.scope.adopt(services.resources.style('css/bgm.css'), release => release())
  for (const name of ['vendor/three.min','vendor/three-line2','memory-connection-layer','bgm-page','bgm-record','bgm-bubble']) {
    await services.shared.script('js/'+name+'.js')
    if (!context.valid()) return {unmount(){}}
  }
  const {setTimeout,clearTimeout,requestAnimationFrame,cancelAnimationFrame} = createPageTimers(context)
  const request = (...args) => services.auth.request(...args)
  const audioPage = services.audio.attachPage(context,'content'), bubble = BgmBubble.mount(audioPage)
  if (bubble) context.cleanup(()=>bubble.destroy())
  const sheetLease = services.overlays.register({kind:'memory-sheet',ownerId:context.scope.ownerId,element:byId('nebula-sheet'),background:byId('nebula-stage')})
  context.cleanup(()=>sheetLease.dispose())
  context.scope.listen(root,'keydown',event=>{
    if (!sheetLease.isOpen()) return
    if (event.key==='Escape') { event.preventDefault(); event.stopPropagation(); closeSheet() }
    if (event.key==='Tab') { event.preventDefault(); byId('nebula-sheet').focus({preventScroll:true}) }
  })
  var MIN_RADIUS = 6
  var MAX_RADIUS = 28
  var DEFAULT_RADIUS = 14
  /** 点击判定：移动阈值（px）；与按压时长一起区分拖动 */
  var TAP_MOVE_PX = 8
  var TAP_MAX_MS = 250
  var AUTO_YAW_SPEED = 0.08
  /** 记忆核心固定 id（连接线系统约定） */
  var CENTER_ID = 'core-memory'
  var ASSET_BASE = '/static/images/memory-nebula/'
  var SHEET_LIFT = 1.35
  /** 选中态建立清晰的主次层级 */
  var DIM_OPACITY = 0.58
  var DIM_SCALE = 0.92
  var RELATED_OPACITY = 0.92
  var SELECTED_BRIGHTNESS = 1.24
  var STAR_BASE_SCALE = 1.95
  var CORE_SCALE = 4.2
  var CORE_HIT_RADIUS = 1.2
  var MEMORY_HIT_RADIUS = 0.55

  var canvas = byId('nebula-canvas')
  var stage = byId('nebula-stage')
  var loadingEl = byId('nebula-loading')
  var emptyEl = byId('nebula-empty')
  var sheetEl = byId('nebula-sheet')
  var sheetMask = byId('nebula-sheet-mask')
  var sheetCategoryText = byId('nebula-sheet-category-text')
  var sheetCategoryRow = byId('nebula-sheet-category')
  var sheetTitle = byId('nebula-sheet-title')
  var sheetValue = byId('nebula-sheet-value')
  var sheetBadge = byId('nebula-sheet-badge')
  var sheetSourceText = byId('nebula-sheet-source-text')
  var backBtn = byId('nebula-back')
  var tipBtn = byId('nebula-tip')
  var countNumEl = byId('nebula-count-num')
  var countSubtitleEl = byId('nebula-count-subtitle')
  var bottomBar = byId('nebula-bottom-bar')
  var recenterBtn = byId('nebula-recenter')
  var toastEl = byId('nebula-toast')
  var goChatBtn = byId('nebula-go-chat')

  var CATEGORY_DEFS = [
    { id: 'prefer', label: '用户偏好', color: '#6F9EB7', file: 'star-teal.png', keys: ['偏好', '习惯', '兴趣'] },
    { id: 'event', label: '经历与事件', color: '#7FA48F', file: 'star-green.png', keys: ['经历', '事件', '出行', '工作'] },
    { id: 'relation', label: '关系与边界', color: '#9872D8', file: 'star-purple.png', keys: ['关系', '社交', '边界', '认知'] },
    { id: 'emotion', label: '情绪与状态', color: '#B77F9C', file: 'star-pink.png', keys: ['情绪', '状态', '心情'] },
    { id: 'important', label: '其他', color: '#B69A6D', file: 'star-gold.png', keys: [] },
  ]

  var FALLBACK_PALETTE = [
    { color: '#6F9EB7', file: 'star-teal.png', label: '其他' },
    { color: '#7FA48F', file: 'star-green.png', label: '其他' },
    { color: '#9872D8', file: 'star-purple.png', label: '其他' },
    { color: '#B77F9C', file: 'star-pink.png', label: '其他' },
    { color: '#B69A6D', file: 'star-gold.png', label: '其他' },
    { color: '#7A8FB5', file: 'star-teal.png', label: '其他' },
    { color: '#9A86B5', file: 'star-purple.png', label: '其他' },
    { color: '#A89078', file: 'star-gold.png', label: '其他' },
  ]

  /** @type {Array} */
  var nodes = []
  /** @type {THREE.Group|null} */
  var orbitGroup = null
  /** @type {number|null} */
  var selectedIndex = null
  /** @type {Object.<string, THREE.Texture>} */
  var texCache = {}
  /** @type {Object.<string, {color:string,file:string,label:string}>} */
  var keyL1StyleCache = {}
  /** @type {object|null} MemoryConnectionLayer 实例 */
  var connectionLayer = null
  /** 选中回弹：0～180ms 缩放脉冲 */
  var selectPulse = { active: false, index: null, elapsed: 0 }

  var scene = null
  var camera = null
  var renderer = null
  var rootGroup = null
  var coreGroup = null
  var coreSprite = null
  var raycaster = new THREE.Raycaster()
  var pointerNdc = new THREE.Vector2()
  var textureLoader = new THREE.TextureLoader()

  var orbit = { yaw: 0.55, pitch: 0.42, radius: DEFAULT_RADIUS, autoRotate: true }
  var defaultOrbit = { yaw: 0.55, pitch: 0.42, radius: DEFAULT_RADIUS }
  var velocity = { yaw: 0, pitch: 0 }
  var liftY = 0
  var liftTarget = 0

  var reduceMotion = false
  try {
    reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch (e) {
    reduceMotion = false
  }
  if (reduceMotion) orbit.autoRotate = false

  var clock = new THREE.Clock()
  var viewW = 0
  var viewH = 0
  var toastTimer = null
  var memoryCount = 0
  var memoryPageActive = context.valid()
  var animationFrameId = null

  function stopMemoryPrivateResources() {
    if (!memoryPageActive) return
    memoryPageActive = false
    if (animationFrameId != null) cancelAnimationFrame(animationFrameId)
    if (toastTimer) clearTimeout(toastTimer)
    if (gesture?.idleTimer) clearTimeout(gesture.idleTimer)
    for (const id of Object.keys(pointers || {})) {
      try { if (canvas.hasPointerCapture(Number(id))) canvas.releasePointerCapture(Number(id)) } catch (_) {}
    }
    pointers = {}; gesture.mode = 'none'; selectPulse.active = false
    sheetLease.dispose()
    for (const pending of [...pendingTextures.values()]) pending.cancel()
    pendingTextures.clear()
    // Connection visuals have their own textures and must be released before removing their group.
    connectionLayer?.dispose(); connectionLayer = null
    if (scene) { scene.traverse(disposeObject3D); scene.clear() }
    for (const texture of Object.values(texCache)) disposeTexture(texture)
    texCache = {}; nodes = []; keyL1StyleCache = {}
    if (renderer) { renderer.renderLists.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer = null }
    scene = camera = rootGroup = coreGroup = coreSprite = orbitGroup = null
  }

  function memoryProtectedAuthOptions() {
    return {authPolicy:'protected-home-modal',routeEpoch:context.routeEpoch,routeCurrent:()=>context.router.current?.context.routeEpoch===context.routeEpoch,isCurrent:context.valid,signal:context.signal}
  }

  function hashStr(s) {
    var h = 2166136261
    var str = String(s || '')
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i)
      h = Math.imul(h, 16777619)
    }
    return h >>> 0
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v))
  }

  function setVisible(el, on) {
    if (!el) return
    if (on) el.classList.add('is-visible')
    else el.classList.remove('is-visible')
  }

  function keyL1Of(key) {
    var k = (key || '').trim()
    if (!k) return '其他'
    var parts = k.split('-')
    if (parts[0] && parts[0].trim()) return parts[0].trim()
    return k.slice(0, 2) || '其他'
  }

  function matchCategoryDef(keyL1) {
    for (var i = 0; i < CATEGORY_DEFS.length; i++) {
      var def = CATEGORY_DEFS[i]
      for (var j = 0; j < def.keys.length; j++) {
        if (keyL1 === def.keys[j] || keyL1.indexOf(def.keys[j]) === 0) return def
      }
    }
    return null
  }

  function styleForKeyL1(keyL1) {
    var k = keyL1 || '其他'
    if (keyL1StyleCache[k]) return keyL1StyleCache[k]
    var matched = matchCategoryDef(k)
    var style
    if (matched) {
      style = { color: matched.color, file: matched.file, label: matched.label }
    } else {
      var pick = FALLBACK_PALETTE[hashStr(k) % FALLBACK_PALETTE.length]
      style = { color: pick.color, file: pick.file, label: pick.label }
    }
    keyL1StyleCache[k] = style
    return style
  }

  /** 自然语言短标题：取 value 首句并截断 */
  function titleFromValue(value) {
    var v = String(value || '').trim()
    if (!v) return '一段关于你的记忆'
    var cut = v.split(/[。！？\n]/)[0] || v
    cut = cut.trim()
    if (cut.length > 22) cut = cut.slice(0, 22) + '…'
    return cut
  }

  const pendingTextures = new Map(), disposedTextures = new WeakSet(), disposedGeometries = new WeakSet(), disposedMaterials = new WeakSet()
  function disposeTexture(texture) {
    if (!texture || disposedTextures.has(texture)) return
    disposedTextures.add(texture); texture.dispose(); texture.image?.close?.()
  }
  function loadTexture(file) {
    if (!context.valid() || !memoryPageActive) return Promise.resolve(null)
    if (texCache[file]) return Promise.resolve(texCache[file])
    if (pendingTextures.has(file)) return pendingTextures.get(file).promise
    let resolve, texture, settled = false
    const promise = new Promise(done => { resolve = done })
    const finish = value => { if (settled) return; settled = true; pendingTextures.delete(file); resolve(value) }
    const pending = {promise, cancel: () => { disposeTexture(texture); finish(null) }}
    pendingTextures.set(file, pending)
    texture = textureLoader.load(ASSET_BASE + file, tex => {
      if (!context.valid() || !memoryPageActive || settled) {
        // The loader may finish after disposal and set needsUpdate again; explicitly dispose that late result too.
        tex.dispose(); tex.image?.close?.(); finish(null); return
      }
      if (THREE.sRGBEncoding != null) tex.encoding = THREE.sRGBEncoding
      else if (THREE.SRGBColorSpace != null) tex.colorSpace = THREE.SRGBColorSpace
      tex.premultiplyAlpha = true; tex.needsUpdate = true; texCache[file] = tex; finish(tex)
    }, undefined, () => { disposeTexture(texture); finish(null) })
    return promise
  }

  function makeSpriteMaterial(tex, fallbackHex, additive) {
    var useAdd = additive !== false
    return new THREE.SpriteMaterial({
      map: tex || undefined,
      color: tex ? 0xffffff : new THREE.Color(fallbackHex || '#ffffff'),
      transparent: true,
      opacity: 1,
      depthWrite: false,
      blending: useAdd ? THREE.AdditiveBlending : THREE.NormalBlending,
      premultipliedAlpha: true,
    })
  }

  function showToast(msg) {
    if (!toastEl) return
    toastEl.textContent = msg
    toastEl.classList.add('is-visible')
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(function () {
      toastEl.classList.remove('is-visible')
    }, 2600)
  }

  function updateMemoryCount(total) {
    memoryCount = Math.max(0, Number(total) || 0)
    if (countNumEl) countNumEl.textContent = String(memoryCount)
    if (countSubtitleEl) countSubtitleEl.textContent = memoryCount + ' 颗记忆星体'
  }

  async function fetchAllMemories() {
    var page = 1
    var pageSize = 50
    var all = []
    var total = null
    var seen = new Set(), received = 0
    var guard = 0
    while (memoryPageActive && guard < 20) {
      guard++
      var res = await request(
        'GET',
        '/api/memory/list?page=' + page + '&page_size=' + pageSize,
        undefined,
        memoryProtectedAuthOptions()
      )
      if (!context.valid() || !memoryPageActive || (res && res.code === 401)) break
      if (!res || res.code !== 0 || !res.data) break
      var d = res.data
      var list = Array.isArray(d.list) ? d.list : []
      if (typeof d.total === 'number') total = d.total
      if (typeof d.page_size === 'number') pageSize = d.page_size
      received += list.length
      for (var i = 0; i < list.length; i++) {
        var id = list[i].doc_id
        if (id != null && seen.has(String(id))) continue
        if (id != null) seen.add(String(id))
        all.push(list[i])
      }
      if (list.length === 0) break
      if (list.length < pageSize) break
      if (total != null && received >= total) break
      page++
    }
    return all
  }

  function initRenderer() {
    viewW = stage.clientWidth || window.innerWidth
    viewH = stage.clientHeight || window.innerHeight

    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
      premultipliedAlpha: true,
    })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(viewW, viewH, false)
    renderer.setClearColor(0x000000, 0)

    scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x05050f, 0.026)

    camera = new THREE.PerspectiveCamera(48, viewW / viewH, 0.1, 200)
    rootGroup = new THREE.Group()
    scene.add(rootGroup)

    scene.add(new THREE.AmbientLight(0x6b5b95, 0.4))
    var coreLight = new THREE.PointLight(0xffd9a8, 1.15, 36, 2)
    coreLight.position.set(0, 0, 0)
    scene.add(coreLight)

    addBackgroundStars()
    addOrbitRings()
    updateCameraFromOrbit()
  }

  function addBackgroundStars() {
    var count = 70
    var positions = new Float32Array(count * 3)
    for (var i = 0; i < count; i++) {
      var seed = hashStr('bg-' + i)
      var r = 36 + ((seed % 1000) / 1000) * 48
      var theta = ((seed >>> 5) % 10000) / 10000 * Math.PI * 2
      var phi = Math.acos(2 * (((seed >>> 15) % 10000) / 10000) - 1)
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(theta) * 0.35
    }
    var geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    scene.add(
      new THREE.Points(
        geo,
        new THREE.PointsMaterial({
          color: 0xffffff,
          size: 0.06,
          sizeAttenuation: true,
          transparent: true,
          opacity: 0.32,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        })
      )
    )
  }

  function addOrbitRings() {
    orbitGroup = new THREE.Group()
    rootGroup.add(orbitGroup)
    // 纯装饰轨道：压暗压细，与关系连接线彻底分层
    var orbitCfg =
      (typeof MemoryConnectionConfig !== 'undefined' && MemoryConnectionConfig.orbit) || {
        opacity: 0.05,
        color: '#68658C',
      }
    var orbitColor = new THREE.Color(orbitCfg.color || '#68658C')
    var baseOp = typeof orbitCfg.opacity === 'number' ? orbitCfg.opacity : 0.05
    var rings = [
      { rx: 3.4, ry: 2.2, rotZ: 0.18, rotX: 0.55, opacity: baseOp * 1.3 },
      { rx: 4.8, ry: 3.1, rotZ: -0.32, rotX: 0.72, opacity: baseOp },
      { rx: 6.2, ry: 3.8, rotZ: 0.5, rotX: 0.4, opacity: baseOp * 0.7 },
    ]
    for (var i = 0; i < rings.length; i++) {
      var cfg = rings[i]
      var curve = new THREE.EllipseCurve(0, 0, cfg.rx, cfg.ry, 0.15, Math.PI * 1.85, false, 0)
      var pts = curve.getPoints(96)
      var positions = []
      for (var p = 0; p < pts.length; p++) positions.push(pts[p].x, pts[p].y, 0)
      var geo = new THREE.BufferGeometry()
      geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
      var line = new THREE.Line(
        geo,
        new THREE.LineBasicMaterial({
          color: orbitColor,
          transparent: true,
          opacity: clamp(cfg.opacity, 0.035, 0.07),
          depthWrite: false,
        })
      )
      line.renderOrder = 0
      line.rotation.x = cfg.rotX
      line.rotation.z = cfg.rotZ
      orbitGroup.add(line)
    }
  }

  async function addCenterStar() {
    coreGroup = new THREE.Group()
    rootGroup.add(coreGroup)

    var tex = await loadTexture('core-star.png')
    if (!context.valid() || !memoryPageActive) return
    var mat = makeSpriteMaterial(tex, '#ffd9a8', false)
    coreSprite = new THREE.Sprite(mat)
    coreSprite.scale.set(CORE_SCALE, CORE_SCALE, 1)
    coreSprite.userData.nodeIndex = 0
    coreGroup.add(coreSprite)

    var hit = new THREE.Mesh(
      new THREE.SphereGeometry(1.25, 16, 16),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
    )
    hit.userData.nodeIndex = 0
    coreGroup.add(hit)

    nodes = [
      {
        id: CENTER_ID,
        key: '',
        value: '',
        keyL1: '核心',
        categoryLabel: '记忆核',
        colorHex: '#FFD9A8',
        isCore: true,
        sprite: coreSprite,
        hit: hit,
        pos: new THREE.Vector3(0, 0, 0),
        baseOpacity: 1,
        relatedIds: [],
      },
    ]
  }

  function disposeObject3D(obj) {
    if (!obj) return
    if (obj.geometry && !disposedGeometries.has(obj.geometry)) { disposedGeometries.add(obj.geometry); obj.geometry.dispose() }
    for (const material of [obj.material].flat().filter(Boolean)) {
      if (disposedMaterials.has(material)) continue
      disposedMaterials.add(material)
      for (const value of Object.values(material)) if (value?.isTexture) disposeTexture(value)
      for (const uniform of Object.values(material.uniforms || {})) if (uniform?.value?.isTexture) disposeTexture(uniform.value)
      material.dispose()
    }
  }

  /** 旧折线入口保留：改由连接线层接管（契约锚点 buildSelectLinks / clearSelectLines） */
  function clearSelectLines() {
    if (connectionLayer) connectionLayer.setActivePlanet(null)
  }

  /**
   * 按同 keyL1 最近邻填充 relatedIds；若无同分类则退化为距离最近邻，避免默认态无线
   */
  function assignRelatedIds() {
    for (var i = 1; i < nodes.length; i++) {
      nodes[i].relatedIds = []
    }
    for (var a = 1; a < nodes.length; a++) {
      var cur = nodes[a]
      var sameCat = []
      var anyNear = []
      for (var b = 1; b < nodes.length; b++) {
        if (a === b) continue
        var d2 = cur.pos.distanceToSquared(nodes[b].pos)
        anyNear.push({ id: nodes[b].id, d2: d2 })
        if (nodes[b].keyL1 === cur.keyL1) sameCat.push({ id: nodes[b].id, d2: d2 })
      }
      sameCat.sort(function (x, y) { return x.d2 - y.d2 })
      anyNear.sort(function (x, y) { return x.d2 - y.d2 })
      var pool = sameCat.length ? sameCat : anyNear
      var n = Math.min(2, pool.length)
      for (var t = 0; t < n; t++) {
        var oid = pool[t].id
        if (cur.relatedIds.indexOf(oid) < 0) cur.relatedIds.push(oid)
      }
    }
    // 双向补全
    for (var i = 1; i < nodes.length; i++) {
      var src = nodes[i]
      for (var r = 0; r < src.relatedIds.length; r++) {
        var other = null
        for (var j = 1; j < nodes.length; j++) {
          if (nodes[j].id === src.relatedIds[r]) {
            other = nodes[j]
            break
          }
        }
        if (other && other.relatedIds.indexOf(src.id) < 0) other.relatedIds.push(src.id)
      }
    }
  }

  function planetsForConnectionLayer() {
    var list = []
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i]
      list.push({
        id: n.id,
        type: n.isCore ? 'core' : 'memory',
        position: n.pos,
        radius: n.isCore ? CORE_HIT_RADIUS : MEMORY_HIT_RADIUS,
        color: n.isCore ? '#FFB129' : n.colorHex,
        relatedIds: n.relatedIds ? n.relatedIds.slice() : [],
      })
    }
    return list
  }

  function ensureConnectionLayer() {
    if (connectionLayer || typeof MemoryConnectionLayer !== 'function') return
    var lowPower = false
    try {
      if (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) lowPower = true
    } catch (e) { /* ignore */ }
    connectionLayer = new MemoryConnectionLayer({
      parentGroup: rootGroup,
      camera: camera,
      reduceMotion: reduceMotion,
      lowPower: lowPower,
    })
    connectionLayer.resize(viewW, viewH)
  }

  function syncConnectionLayer() {
    ensureConnectionLayer()
    if (!connectionLayer) return
    connectionLayer.setPlanets(planetsForConnectionLayer())
  }

  async function buildMemoryNodes(rawList) {
    for (var i = nodes.length - 1; i >= 1; i--) {
      var old = nodes[i]
      if (old.sprite) {
        rootGroup.remove(old.sprite)
        disposeObject3D(old.sprite)
      }
      if (old.hit) {
        rootGroup.remove(old.hit)
        disposeObject3D(old.hit)
      }
    }
    nodes.length = 1
    if (connectionLayer) connectionLayer.setActivePlanet(null)

    var files = {}
    for (var f = 0; f < CATEGORY_DEFS.length; f++) files[CATEGORY_DEFS[f].file] = true
    await Promise.all(
      Object.keys(files).map(function (file) {
        return loadTexture(file)
      })
    )

    if (!context.valid() || !memoryPageActive) return
    for (var i = 0; i < rawList.length; i++) {
      var m = rawList[i] || {}
      var key = (m.key || '').trim()
      var value = (m.value || m.content || '').trim()
      if (!key && !value) continue

      var id = m.doc_id || 'm-' + i
      var seed = hashStr(id + '|' + key)
      var u = (seed % 10000) / 10000
      var v = ((seed >>> 10) % 10000) / 10000
      var theta = u * Math.PI * 2
      var phi = Math.acos(2 * v - 1)
      var rx = 3.6 + (((seed >>> 3) % 100) / 100) * 2.8
      var ry = 2.6 + (((seed >>> 7) % 100) / 100) * 2.3
      var rz = 3.4 + (((seed >>> 12) % 100) / 100) * 2.5
      var x = rx * Math.sin(phi) * Math.cos(theta)
      var y = ry * Math.cos(phi)
      var z = rz * Math.sin(phi) * Math.sin(theta)

      var keyL1 = keyL1Of(key)
      var style = styleForKeyL1(keyL1)
      var tex = texCache[style.file] || null
      var mat = makeSpriteMaterial(tex, style.color)
      var sprite = new THREE.Sprite(mat)
      var jitter = 0.9 + ((seed >>> 20) % 100) / 100 * 0.22
      var baseScale = STAR_BASE_SCALE * jitter
      sprite.scale.set(baseScale, baseScale, 1)
      sprite.position.set(x, y, z)
      var idx = nodes.length
      sprite.userData.nodeIndex = idx
      sprite.userData.baseScale = baseScale
      rootGroup.add(sprite)

      var hit = new THREE.Mesh(
        new THREE.SphereGeometry(0.62, 10, 10),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
      )
      hit.position.set(x, y, z)
      hit.userData.nodeIndex = idx
      rootGroup.add(hit)

      nodes.push({
        id: String(id),
        key: key,
        value: value || '（无内容）',
        keyL1: keyL1,
        categoryLabel: style.label,
        colorHex: style.color,
        isCore: false,
        sprite: sprite,
        hit: hit,
        pos: new THREE.Vector3(x, y, z),
        baseOpacity: 1,
        relatedIds: [],
      })
    }

    assignRelatedIds()
    syncConnectionLayer()
  }

  /** 点选记忆后激活关系线（核心主线 + 最多 2 条次级） */
  function buildSelectLinks(index) {
    if (!connectionLayer) return
    if (index == null || index <= 0) {
      connectionLayer.setActivePlanet(null)
      return
    }
    var cur = nodes[index]
    if (!cur || cur.isCore) {
      connectionLayer.setActivePlanet(null)
      return
    }
    connectionLayer.setActivePlanet(cur.id)
  }

  function updateCameraFromOrbit() {
    var phi = clamp(orbit.pitch, 0.18, Math.PI - 0.18)
    var theta = orbit.yaw
    var r = orbit.radius
    var lookY = 0.55 + liftY * 0.15
    camera.position.x = r * Math.sin(phi) * Math.cos(theta)
    camera.position.y = r * Math.cos(phi) + 0.6
    camera.position.z = r * Math.sin(phi) * Math.sin(theta)
    camera.lookAt(0, lookY, 0)
  }

  function resize() {
    viewW = stage.clientWidth || window.innerWidth
    viewH = stage.clientHeight || window.innerHeight
    camera.aspect = viewW / viewH
    camera.updateProjectionMatrix()
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(viewW, viewH, false)
    if (connectionLayer) connectionLayer.resize(viewW, viewH)
  }

  function isOrbitOffCenter() {
    return (
      Math.abs(orbit.yaw - defaultOrbit.yaw) > 0.35 ||
      Math.abs(orbit.pitch - defaultOrbit.pitch) > 0.25 ||
      Math.abs(orbit.radius - defaultOrbit.radius) > 2.5
    )
  }

  function updateRecenterVisibility() {
    if (!recenterBtn) return
    if (sheetEl.classList.contains('is-open')) {
      recenterBtn.classList.remove('is-visible')
      return
    }
    if (isOrbitOffCenter()) recenterBtn.classList.add('is-visible')
    else recenterBtn.classList.remove('is-visible')
  }

  function setBottomBarHidden(hidden) {
    if (!bottomBar) return
    if (hidden) bottomBar.classList.add('is-hidden')
    else bottomBar.classList.remove('is-hidden')
  }

  function recenterOrbit() {
    orbit.yaw = defaultOrbit.yaw
    orbit.pitch = defaultOrbit.pitch
    orbit.radius = defaultOrbit.radius
    velocity.yaw = 0
    velocity.pitch = 0
    updateCameraFromOrbit()
    updateRecenterVisibility()
  }

  function applySelectionHighlight() {
    var relatedSet = {}
    if (selectedIndex != null && selectedIndex > 0 && connectionLayer) {
      var cur = nodes[selectedIndex]
      if (cur && !cur.isCore) {
        relatedSet[cur.id] = true
        var rel = connectionLayer.getRelatedIds(cur.id)
        for (var r = 0; r < rel.length; r++) relatedSet[rel[r]] = true
      }
    }
    var arrivalBoost = connectionLayer && typeof connectionLayer.getArrivalBoost === 'function'
      ? connectionLayer.getArrivalBoost()
      : 0

    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i]
      if (!n.sprite || !n.sprite.material) continue
      if (n.isCore) {
        n.sprite.material.opacity = selectedIndex != null && selectedIndex !== 0 ? 0.85 : 1
        continue
      }
      var baseScale = (n.sprite.userData && n.sprite.userData.baseScale) || STAR_BASE_SCALE
      if (selectedIndex == null) {
        n.sprite.material.opacity = n.baseOpacity
        n.sprite.material.color.set(0xffffff)
        if (!(selectPulse.active && selectPulse.index === i)) {
          n.sprite.scale.set(baseScale, baseScale, 1)
        }
      } else if (i === selectedIndex) {
        // 稳定选中约 +20%，能量抵达瞬间再短暂抬升
        var bright = SELECTED_BRIGHTNESS * (1 + arrivalBoost)
        n.sprite.material.opacity = Math.min(1, n.baseOpacity * bright)
        if (!(selectPulse.active && selectPulse.index === i)) {
          n.sprite.scale.set(baseScale * 1.2, baseScale * 1.2, 1)
        }
      } else if (relatedSet[n.id]) {
        n.sprite.material.opacity = RELATED_OPACITY
        n.sprite.scale.set(baseScale, baseScale, 1)
      } else {
        n.sprite.material.opacity = DIM_OPACITY
        n.sprite.scale.set(baseScale * DIM_SCALE, baseScale * DIM_SCALE, 1)
      }
    }
  }

  function startSelectPulse(index) {
    if (reduceMotion || index == null || index <= 0) {
      selectPulse.active = false
      return
    }
    selectPulse.active = true
    selectPulse.index = index
    selectPulse.elapsed = 0
  }

  function updateSelectPulse(dt) {
    if (!selectPulse.active) return
    selectPulse.elapsed += dt * 1000
    var n = nodes[selectPulse.index]
    if (!n || !n.sprite) {
      selectPulse.active = false
      return
    }
    var baseScale = (n.sprite.userData && n.sprite.userData.baseScale) || STAR_BASE_SCALE
    var t = selectPulse.elapsed
    var mul = 1
    // 0～180ms：0.96 → 1.04 → 稳定选中倍率
    if (t < 70) mul = lerp(0.96, 1.04, t / 70)
    else if (t < 180) mul = lerp(1.04, 1.2, (t - 70) / 110)
    else {
      mul = 1.2
      selectPulse.active = false
    }
    n.sprite.scale.set(baseScale * mul, baseScale * mul, 1)
  }

  function lerp(a, b, t) {
    return a + (b - a) * Math.max(0, Math.min(1, t))
  }

  function openSheet(index) {
    var n = nodes[index]
    if (!n) return
    if (!sheetLease.isOpen() && !sheetLease.open()) return
    var sameSelection = selectedIndex === index
    selectedIndex = index
    liftTarget = SHEET_LIFT
    setBottomBarHidden(true)

    if (sheetBadge) sheetBadge.style.display = ''

    if (n.isCore) {
      if (sheetCategoryRow) sheetCategoryRow.style.display = ''
      if (sheetCategoryText) sheetCategoryText.textContent = '她记得 · 记忆总览'
      if (sheetTitle) {
        sheetTitle.textContent =
          memoryCount <= 0 ? '这里还没有关于你的记忆' : '她已经记住了关于你的 ' + memoryCount + ' 件事'
      }
      if (sheetValue) {
        sheetValue.textContent =
          memoryCount <= 0
            ? '你们聊过的事情，会慢慢在这里亮起来。'
            : '这些星点，都是她从对话里慢慢整理出来的关于你的记忆。'
      }
      if (sheetSourceText) sheetSourceText.textContent = '来自你们的对话'
      clearSelectLines()
    } else {
      if (sheetCategoryRow) sheetCategoryRow.style.display = ''
      if (sheetCategoryText) sheetCategoryText.textContent = '她记得 · ' + (n.categoryLabel || '其他')
      if (sheetTitle) sheetTitle.textContent = titleFromValue(n.value)
      if (sheetValue) sheetValue.textContent = n.value || '（无内容）'
      if (sheetSourceText) sheetSourceText.textContent = '来自你们的对话'
      buildSelectLinks(index)
      if (!sameSelection) startSelectPulse(index)
    }

    sheetEl.focus({preventScroll:true})
    sheetEl.classList.add('is-open')
    sheetMask.classList.add('is-open')
    sheetEl.setAttribute('aria-hidden', 'false')
    sheetMask.setAttribute('aria-hidden', 'false')
    applySelectionHighlight()
    updateRecenterVisibility()
  }

  function closeSheet() {
    sheetLease.close()
    selectedIndex = null
    liftTarget = 0
    setBottomBarHidden(false)
    sheetEl.classList.remove('is-open')
    sheetMask.classList.remove('is-open')
    sheetEl.setAttribute('aria-hidden', 'true')
    sheetMask.setAttribute('aria-hidden', 'true')
    clearSelectLines()
    applySelectionHighlight()
    updateRecenterVisibility()
  }

  function hitTest(clientX, clientY) {
    var rect = canvas.getBoundingClientRect()
    pointerNdc.x = ((clientX - rect.left) / rect.width) * 2 - 1
    pointerNdc.y = -((clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(pointerNdc, camera)

    var hitsTargets = []
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].hit) hitsTargets.push(nodes[i].hit)
      if (nodes[i].sprite) hitsTargets.push(nodes[i].sprite)
    }
    var hits = raycaster.intersectObjects(hitsTargets, false)
    if (hits.length) {
      var obj = hits[0].object
      while (obj && obj.userData.nodeIndex == null && obj.parent) obj = obj.parent
      if (obj && obj.userData.nodeIndex != null) return obj.userData.nodeIndex
    }
    if (raycaster.ray.distanceToPoint(new THREE.Vector3(0, liftY, 0)) < 1.5) return 0
    return null
  }

  var pointers = {}
  var gesture = {
    mode: 'none',
    moved: false,
    startX: 0,
    startY: 0,
    startTime: 0,
    lastX: 0,
    lastY: 0,
    startDist: 1,
    startRadius: DEFAULT_RADIUS,
    userInteracting: false,
    idleTimer: null,
  }

  function pointerList() {
    var arr = []
    for (var id in pointers) {
      if (Object.prototype.hasOwnProperty.call(pointers, id)) arr.push(pointers[id])
    }
    return arr
  }

  function dist(a, b) {
    var dx = a.x - b.x
    var dy = a.y - b.y
    return Math.sqrt(dx * dx + dy * dy)
  }

  function markInteracting() {
    gesture.userInteracting = true
    orbit.autoRotate = false
    if (bottomBar) bottomBar.classList.add('is-interacting')
    if (gesture.idleTimer) clearTimeout(gesture.idleTimer)
    gesture.idleTimer = setTimeout(function () {
      gesture.userInteracting = false
      if (bottomBar) bottomBar.classList.remove('is-interacting')
      if (!reduceMotion) orbit.autoRotate = true
    }, 2200)
  }

  function onPointerDown(ev) {
    if (sheetEl.classList.contains('is-open') && ev.target !== canvas) return
    if (canvas.setPointerCapture) {
      try { canvas.setPointerCapture(ev.pointerId) } catch (e) { /* ignore */ }
    }
    pointers[ev.pointerId] = { x: ev.clientX, y: ev.clientY }
    var pts = pointerList()
    markInteracting()
    if (pts.length === 1) {
      gesture.mode = 'orbit'
      gesture.moved = false
      gesture.startX = pts[0].x
      gesture.startY = pts[0].y
      gesture.startTime = performance.now()
      gesture.lastX = pts[0].x
      gesture.lastY = pts[0].y
      velocity.yaw = 0
      velocity.pitch = 0
    } else if (pts.length >= 2) {
      gesture.mode = 'pinch'
      gesture.moved = true
      gesture.startDist = Math.max(dist(pts[0], pts[1]), 1)
      gesture.startRadius = orbit.radius
    }
  }

  function onPointerMove(ev) {
    if (!pointers[ev.pointerId]) return
    pointers[ev.pointerId] = { x: ev.clientX, y: ev.clientY }
    var pts = pointerList()
    markInteracting()
    if (gesture.mode === 'pinch' && pts.length >= 2) {
      var d = Math.max(dist(pts[0], pts[1]), 1)
      orbit.radius = clamp(gesture.startRadius * (gesture.startDist / d), MIN_RADIUS, MAX_RADIUS)
      updateCameraFromOrbit()
      updateRecenterVisibility()
      return
    }
    if (gesture.mode === 'orbit' && pts.length === 1) {
      var p = pts[0]
      var dx = p.x - gesture.lastX
      var dy = p.y - gesture.lastY
      if (!gesture.moved) {
        var total = Math.sqrt(Math.pow(p.x - gesture.startX, 2) + Math.pow(p.y - gesture.startY, 2))
        if (total > TAP_MOVE_PX) gesture.moved = true
      }
      if (gesture.moved) {
        var sens = 0.0045
        orbit.yaw -= dx * sens
        orbit.pitch -= dy * sens
        orbit.pitch = clamp(orbit.pitch, 0.18, Math.PI - 0.18)
        velocity.yaw = -dx * sens * 0.32
        velocity.pitch = -dy * sens * 0.32
        updateCameraFromOrbit()
        updateRecenterVisibility()
      }
      gesture.lastX = p.x
      gesture.lastY = p.y
    }
  }

  function onPointerUp(ev) {
    try { if (canvas.hasPointerCapture(ev.pointerId)) canvas.releasePointerCapture(ev.pointerId) } catch (_) {}
    var pressMs = gesture.startTime ? performance.now() - gesture.startTime : 0
    var wasTap =
      ev.type !== 'pointercancel' && gesture.mode === 'orbit' &&
      !gesture.moved &&
      Object.keys(pointers).length <= 1 &&
      pressMs <= TAP_MAX_MS
    var tapX = gesture.startX
    var tapY = gesture.startY
    delete pointers[ev.pointerId]
    var pts = pointerList()
    if (pts.length >= 2) {
      gesture.mode = 'pinch'
      gesture.startDist = Math.max(dist(pts[0], pts[1]), 1)
      gesture.startRadius = orbit.radius
      gesture.moved = true
      return
    }
    if (pts.length === 1) {
      gesture.mode = 'orbit'
      gesture.lastX = pts[0].x
      gesture.lastY = pts[0].y
      gesture.startX = pts[0].x
      gesture.startY = pts[0].y
      gesture.startTime = performance.now()
      gesture.moved = true
      return
    }
    gesture.mode = 'none'
    if (wasTap) {
      var hit = hitTest(tapX, tapY)
      if (hit != null) openSheet(hit)
      else if (sheetEl.classList.contains('is-open')) closeSheet()
    }
  }

  function onWheel(ev) {
    ev.preventDefault()
    markInteracting()
    orbit.radius = clamp(orbit.radius * (ev.deltaY > 0 ? 1.06 : 0.94), MIN_RADIUS, MAX_RADIUS)
    updateCameraFromOrbit()
    updateRecenterVisibility()
  }

  function bindGestures() {
    context.scope.listen(canvas, 'pointerdown', onPointerDown)
    context.scope.listen(canvas, 'pointermove', onPointerMove)
    context.scope.listen(canvas, 'pointerup', onPointerUp)
    context.scope.listen(canvas, 'pointercancel', onPointerUp)
    context.scope.listen(canvas, 'wheel', onWheel, { passive: false })
    context.scope.listen(sheetMask, 'click', closeSheet)

    var sheetTouchY = null
    context.scope.listen(sheetEl, 'touchstart', function (e) {
      if (e.touches.length === 1) sheetTouchY = e.touches[0].clientY
    }, { passive: true })
    context.scope.listen(sheetEl, 'touchend', function (e) {
      if (sheetTouchY == null) return
      var y = (e.changedTouches[0] && e.changedTouches[0].clientY) || sheetTouchY
      if (y - sheetTouchY > 56) closeSheet()
      sheetTouchY = null
    }, { passive: true })
  }

  function animate() {
    if (!context.valid() || !memoryPageActive || !renderer) return
    animationFrameId = requestAnimationFrame(animate)
    var dt = Math.min(clock.getDelta(), 0.05)
    liftY += (liftTarget - liftY) * Math.min(1, dt * 4.2)
    if (rootGroup) rootGroup.position.y = liftY

    if (!gesture.userInteracting && gesture.mode === 'none') {
      if (Math.abs(velocity.yaw) > 0.0001 || Math.abs(velocity.pitch) > 0.0001) {
        orbit.yaw += velocity.yaw
        orbit.pitch = clamp(orbit.pitch + velocity.pitch, 0.18, Math.PI - 0.18)
        velocity.yaw *= 0.92
        velocity.pitch *= 0.92
        updateCameraFromOrbit()
        updateRecenterVisibility()
      } else if (orbit.autoRotate && !reduceMotion && selectedIndex == null) {
        orbit.yaw += AUTO_YAW_SPEED * dt
        updateCameraFromOrbit()
      }
    }

    if (coreGroup && !reduceMotion) {
      var s = 1 + Math.sin(clock.elapsedTime * ((Math.PI * 2) / 4)) * 0.028
      coreGroup.scale.setScalar(s)
    }

    updateSelectPulse(dt)
    if (connectionLayer) connectionLayer.update(dt)
    if (selectedIndex != null) applySelectionHighlight()

    renderer.render(scene, camera)
  }

  function goBack() {
    context.router.back()
  }

  async function init() {
    if (!memoryPageActive) return
    setVisible(loadingEl, true)
    setVisible(emptyEl, false)
    context.cleanup(stopMemoryPrivateResources, {kind:"webgl",priority:90})
    initRenderer()
    bindGestures()
    if (backBtn) context.scope.listen(backBtn, 'click', goBack)
    if (recenterBtn) context.scope.listen(recenterBtn, 'click', recenterOrbit)
    if (goChatBtn) {
      context.scope.listen(goChatBtn, 'click', function () {
        void context.router.navigate('/pages/chat.html')
      })
    }
    if (tipBtn) {
      context.scope.listen(tipBtn, 'click', function () {
        showToast('记忆根据你们的对话自动整理，目前仅供查看。')
      })
    }
    context.scope.listen(window, 'resize', resize)

    await addCenterStar()
    if (!memoryPageActive) return

    var raw = []
    try {
      raw = await fetchAllMemories()
    } catch (err) {
      console.warn('[memory-nebula] 加载失败', err)
      raw = []
    }
    if (!memoryPageActive) return

    await buildMemoryNodes(raw)
    if (!memoryPageActive) return
    updateMemoryCount(raw.length)
    setVisible(loadingEl, false)
    if (!raw.length) setVisible(emptyEl, true)

    // 空态也挂连接层（仅核心时无环境线）
    ensureConnectionLayer()
    if (connectionLayer && !raw.length) syncConnectionLayer()

    const view = context.state?.view
    if (view && ['yaw','pitch','radius'].every(key => Number.isFinite(view[key]))) {
      orbit.yaw = view.yaw; orbit.pitch = clamp(view.pitch, 0.18, Math.PI - 0.18); orbit.radius = clamp(view.radius, MIN_RADIUS, MAX_RADIUS)
      updateCameraFromOrbit(); updateRecenterVisibility()
    }
    const restoredIndex = nodes.findIndex(node => node.id === context.state?.selectedId)
    if (restoredIndex >= 0) openSheet(restoredIndex)
    animate()
  }

  void init().catch(error => {
    if (!context.valid() || ['AbortError','StaleRequestError'].includes(error.name)) return
    setVisible(loadingEl,false); showToast('记忆星云加载失败，请稍后重试')
  })
  return {unmount:stopMemoryPrivateResources,captureState:()=>({view:{yaw:orbit.yaw,pitch:orbit.pitch,radius:orbit.radius},selectedId:nodes[selectedIndex]?.id||null})}
}

/**
 * 记忆星云 · 记忆关系连接线系统（独立模块）
 * 依赖：window.THREE + vendor/three-line2.js
 *
 * 视觉层级：装饰轨道 << 默认关系线 << 激活主线
 * 能量光带：滑动短 Line2（复用 Geometry，不 fork LineMaterial Shader）
 * 簇拓扑：同关系连通分量 ≥2 → 核心→虚拟枢纽→目标（簇内不各自直连核心）
 */
;(function (root) {
  'use strict'

  var THREE = root.THREE
  if (!THREE || !THREE.Line2 || !THREE.LineGeometry || !THREE.LineMaterial) {
    console.error('[memory-connection-layer] 需要 THREE + Line2 扩展')
    root.MemoryConnectionLayer = function () {
      return {
        setPlanets: function () {},
        refreshConnections: function () {},
        setActivePlanet: function () {},
        update: function () {},
        resize: function () {},
        dispose: function () {},
        getRelatedIds: function () { return [] },
        getArrivalBoost: function () { return 0 },
        getConfig: function () { return CONNECTION_CONFIG },
      }
    }
    return
  }

  /** 统一视觉配置（调参入口） */
  var CONNECTION_CONFIG = {
    CORE_ID: 'core-memory',
    CORE_COLOR: '#FFB129',

    orbit: {
      width: 0.6,
      opacity: 0.05,
      color: '#68658C',
    },

    idle: {
      mobileMaxVisible: 14,
      wideMaxVisible: 18,
      wideBreakpoint: 600,
      width: 1.35,
      opacity: 0.56,
      glowWidth: 6,
      glowOpacity: 0.12,
      color: '#E3DEFF',
      glowColor: '#A995FF',
      tubeRadius: 0.012,
      breathDuration: 5.2,
      breathMin: 0.92,
      breathMax: 1.08,
      activeDim: 0.15,
      flowIntervalMin: 4.8,
      flowIntervalMax: 7.5,
      flowLength: 0.09,
      flowDuration: 1.8,
      flowOpacity: 0.68,
      /** 默认额外画几条「核心引力」辐线，避免无同分类时完全无线 */
      coreSpokes: 4,
      depthMin: 0.52,
      typeOpacity: { related: 1, core: 0.9, near: 0.62 },
    },

    active: {
      width: 4.2,
      opacity: 1.0,
      glowWidth: 18,
      glowOpacity: 0.38,
      innerWidth: 1.35,
      innerOpacity: 1.0,
      tubeRadius: 0.036,
      drawDuration: 0.52,
      glowDelay: 0.05,
      fadeOut: 0.28,
    },

    related: {
      maxVisible: 2,
      width: 2,
      opacity: 0.72,
      glowWidth: 8,
      glowOpacity: 0.25,
      tubeRadius: 0.018,
      flashMs: 280,
    },

    flow: {
      length: 0.12,
      duration: 1.2,
      samples: 12,
      width: 3.2,
      glowWidth: 14,
      glowOpacity: 0.35,
      opacity: 0.95,
      brightness: 1.4,
      repeatDelayMin: 2.8,
      repeatDelayMax: 4.0,
    },

    endpoint: {
      pointSize: 0.24,
      glowSize: 0.52,
      breathSec: 2.8,
      ringDuration: 0.66,
      ringStartScale: 1.08,
      ringEndScale: 1.34,
      ringOpacity: 0.72,
      arrivalBoost: 0.28,
      arrivalBoostDecay: 0.58,
    },

    cluster: {
      hubRadius: 0.18,
      minSize: 2,
    },

    curve: {
      samples: 56,
      samplesLow: 40,
      bendMin: 0.08,
      bendMax: 0.15,
      startPad: 1.05,
      endPad: 1.08,
    },

    renderOrder: 2,
    /** 柔光层始终开启：看不见关系线时优先保可见性 */
    lowPowerNoGlow: false,
    lowPowerNoIdleFlow: true,
  }

  var _dir = new THREE.Vector3()
  var _start = new THREE.Vector3()
  var _end = new THREE.Vector3()
  var _side = new THREE.Vector3()
  var _up = new THREE.Vector3(0, 1, 0)
  var _c1 = new THREE.Vector3()
  var _c2 = new THREE.Vector3()
  var _tmpColor = new THREE.Color()
  var _tmpColor2 = new THREE.Color()
  var _tmpColor3 = new THREE.Color()
  var _flowPos = null
  var _flowCol = null
  var _softTex = null

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

  function easeOutCubic(t) {
    var u = 1 - t
    return 1 - u * u * u
  }

  function lerp(a, b, t) {
    return a + (b - a) * t
  }

  function getVisibleLimit(width) {
    var idle = CONNECTION_CONFIG.idle
    return width >= idle.wideBreakpoint ? idle.wideMaxVisible : idle.mobileMaxVisible
  }

  function selectAmbientConnections(connections, limit) {
    var buckets = { related: [], core: [], near: [] }
    for (var i = 0; i < connections.length; i++) {
      var conn = connections[i]
      if (buckets[conn.type]) buckets[conn.type].push(conn)
    }
    var out = []
    var coreN = Math.min(CONNECTION_CONFIG.idle.coreSpokes, buckets.core.length, limit)
    for (var c = 0; c < coreN; c++) out.push(buckets.core[c])
    var order = [buckets.related, buckets.near]
    for (var b = 0; b < order.length && out.length < limit; b++) {
      for (var j = 0; j < order[b].length && out.length < limit; j++) out.push(order[b][j])
    }
    return out
  }

  function getDepthFactor(a, b, camera) {
    if (!camera || !a || !b || !a.position || !b.position) return 1
    _c1.copy(a.position).project(camera)
    _c2.copy(b.position).project(camera)
    var midZ = (_c1.z + _c2.z) * 0.5
    var normalized = clamp((1 - midZ) * 0.5, 0, 1)
    return lerp(CONNECTION_CONFIG.idle.depthMin, 1, normalized)
  }

  function pairKey(a, b) {
    return a < b ? a + '|' + b : b + '|' + a
  }

  function getSoftTexture() {
    if (_softTex) return _softTex
    var size = 64
    var canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    var ctx = canvas.getContext('2d')
    var g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
    g.addColorStop(0, 'rgba(255,255,255,1)')
    g.addColorStop(0.35, 'rgba(255,255,255,0.55)')
    g.addColorStop(0.7, 'rgba(255,255,255,0.12)')
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
    _softTex = new THREE.CanvasTexture(canvas)
    _softTex.needsUpdate = true
    return _softTex
  }

  function buildCurve(id, startPos, endPos, startRadius, endRadius, samples) {
    _dir.copy(endPos).sub(startPos)
    var len = _dir.length()
    if (len < 0.001) return null
    _dir.multiplyScalar(1 / len)

    var cfg = CONNECTION_CONFIG.curve
    _start.copy(startPos).addScaledVector(_dir, startRadius * cfg.startPad)
    _end.copy(endPos).addScaledVector(_dir, -endRadius * cfg.endPad)

    var pathLen = _start.distanceTo(_end)
    if (pathLen < 0.001) return null

    _side.crossVectors(_dir, _up)
    if (_side.lengthSq() < 1e-6) _side.set(1, 0, 0).cross(_dir)
    _side.normalize()

    var h = hashStr(id)
    var sign = h & 1 ? 1 : -1
    var bendT = cfg.bendMin + ((h >>> 3) % 1000) / 1000 * (cfg.bendMax - cfg.bendMin)
    var offset = pathLen * bendT * sign

    _c1.lerpVectors(_start, _end, 0.32).addScaledVector(_side, offset)
    _c2.lerpVectors(_start, _end, 0.68).addScaledVector(_side, offset * 0.82)

    var curve = new THREE.CubicBezierCurve3(_start.clone(), _c1.clone(), _c2.clone(), _end.clone())
    return { curve: curve, points: curve.getPoints(samples), pathLen: pathLen, endPoint: _end.clone() }
  }

  function pointsToLineArrays(points, colorStartHex, colorEndHex, alphaFn) {
    var n = points.length
    var positions = new Float32Array(n * 3)
    var colors = new Float32Array(n * 3)
    _tmpColor.set(colorStartHex)
    _tmpColor2.set(colorEndHex)
    for (var i = 0; i < n; i++) {
      var p = points[i]
      var t = n <= 1 ? 0 : i / (n - 1)
      var a = alphaFn ? alphaFn(t) : 1
      positions[i * 3] = p.x
      positions[i * 3 + 1] = p.y
      positions[i * 3 + 2] = p.z
      colors[i * 3] = lerp(_tmpColor.r, _tmpColor2.r, t) * a
      colors[i * 3 + 1] = lerp(_tmpColor.g, _tmpColor2.g, t) * a
      colors[i * 3 + 2] = lerp(_tmpColor.b, _tmpColor2.b, t) * a
    }
    return { positions: positions, colors: colors, segmentCount: Math.max(0, n - 1) }
  }

  function makeLineMaterial(opts) {
    var mat = new THREE.LineMaterial({
      color: 0xffffff,
      linewidth: opts.linewidth,
      transparent: true,
      opacity: opts.opacity,
      depthWrite: false,
      depthTest: true,
      blending: THREE.AdditiveBlending,
      vertexColors: true,
      dashed: false,
      worldUnits: false,
      fog: false,
    })
    mat.resolution.set(opts.resW || 1, opts.resH || 1)
    // 再次关闭雾效（部分 three 版本 setValues 可能覆盖）
    mat.fog = false
    return mat
  }

  function createLine2FromCurve(curveData, colorA, colorB, matOpts, alphaFn) {
    var arrays = pointsToLineArrays(curveData.points, colorA, colorB, alphaFn)
    var geo = new THREE.LineGeometry()
    geo.setPositions(arrays.positions)
    geo.setColors(arrays.colors)
    var mat = makeLineMaterial(matOpts)
    var line = new THREE.Line2(geo, mat)
    line.computeLineDistances()
    line.renderOrder = CONNECTION_CONFIG.renderOrder
    line.frustumCulled = false
    line.userData.segmentCount = arrays.segmentCount
    line.userData.curve = curveData.curve
    line.userData.pathLen = curveData.pathLen
    line.userData.endPoint = curveData.endPoint
    line.userData.colorA = colorA
    line.userData.colorB = colorB
    return line
  }

  /**
   * Tube 管线：保证在手机上有真实体积可见（Line2 线宽失效时仍能看见）
   */
  function createTubeFromCurve(curveData, radius, colorHex, opacity, renderOrder) {
    if (!curveData || !curveData.curve) return null
    var tubular = Math.max(24, Math.min(64, (curveData.points && curveData.points.length) || 48))
    var geo = new THREE.TubeGeometry(curveData.curve, tubular, radius, 6, false)
    var mat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(colorHex),
      transparent: true,
      opacity: opacity,
      depthWrite: false,
      depthTest: true,
      blending: THREE.AdditiveBlending,
      fog: false,
    })
    var mesh = new THREE.Mesh(geo, mat)
    mesh.renderOrder = renderOrder != null ? renderOrder : CONNECTION_CONFIG.renderOrder
    mesh.frustumCulled = false
    var idxCount = geo.index ? geo.index.count : geo.attributes.position.count
    mesh.userData.fullDrawCount = idxCount
    mesh.userData.baseOpacity = opacity
    mesh.userData.curve = curveData.curve
    mesh.userData.pathLen = curveData.pathLen
    mesh.userData.endPoint = curveData.endPoint
    return mesh
  }

  function setLineProgress(line, progress) {
    if (!line || !line.geometry) return
    var seg = line.userData.segmentCount || 0
    var p = clamp(progress, 0, 1)
    if (seg <= 0) {
      line.visible = p > 0.001
      return
    }
    var count = p >= 0.999 ? seg : Math.max(0, Math.floor(p * seg + 1e-6))
    line.geometry.instanceCount = count
    line.visible = count > 0
  }

  function setTubeProgress(mesh, progress) {
    if (!mesh || !mesh.geometry) return
    var full = mesh.userData.fullDrawCount || 0
    var p = clamp(progress, 0, 1)
    if (full <= 0) {
      mesh.visible = p > 0.001
      return
    }
    var count = p >= 0.999 ? full : Math.max(0, Math.floor(p * full))
    // 按三角形整组裁切（Tube 每环 6 段 → 指数约 36）
    count = count - (count % 3)
    mesh.geometry.setDrawRange(0, count)
    mesh.visible = count > 0
  }

  function disposeLine(line, parent) {
    if (!line) return
    if (parent) parent.remove(line)
    if (line.geometry) line.geometry.dispose()
    if (line.material) line.material.dispose()
  }

  function disposeSprite(sprite, parent) {
    if (!sprite) return
    if (parent) parent.remove(sprite)
    if (sprite.material) sprite.material.dispose()
  }

  /** 组合路径（主干+分支）上取点 */
  function pathPointAt(segments, t, out) {
    if (!segments || !segments.length) return out.set(0, 0, 0)
    var total = 0
    for (var i = 0; i < segments.length; i++) total += segments[i].pathLen || 0
    if (total < 1e-6) {
      segments[0].curve.getPoint(0, out)
      return out
    }
    var d = clamp(t, 0, 1) * total
    for (var j = 0; j < segments.length; j++) {
      var len = segments[j].pathLen || 0
      if (d <= len || j === segments.length - 1) {
        var u = len < 1e-6 ? 1 : clamp(d / len, 0, 1)
        segments[j].curve.getPoint(u, out)
        return out
      }
      d -= len
    }
    segments[segments.length - 1].curve.getPoint(1, out)
    return out
  }

  function pathColorAt(segments, t, colorA, colorB, outColor) {
    outColor.set(colorA)
    _tmpColor2.set(colorB)
    outColor.r = lerp(outColor.r, _tmpColor2.r, t)
    outColor.g = lerp(outColor.g, _tmpColor2.g, t)
    outColor.b = lerp(outColor.b, _tmpColor2.b, t)
    return outColor
  }

  /**
   * 滑动能量光带：固定采样点数，每帧更新顶点，不 new Geometry 对象
   */
  function createFlowBand(resW, resH, isGlow) {
    var n = CONNECTION_CONFIG.flow.samples
    if (!_flowPos || _flowPos.length !== n * 3) {
      _flowPos = new Float32Array(n * 3)
      _flowCol = new Float32Array(n * 3)
    }
    for (var i = 0; i < n; i++) {
      _flowPos[i * 3] = 0
      _flowPos[i * 3 + 1] = 0
      _flowPos[i * 3 + 2] = 0
      _flowCol[i * 3] = 1
      _flowCol[i * 3 + 1] = 1
      _flowCol[i * 3 + 2] = 1
    }
    var geo = new THREE.LineGeometry()
    geo.setPositions(_flowPos)
    geo.setColors(_flowCol)
    var mat = makeLineMaterial({
      linewidth: isGlow ? CONNECTION_CONFIG.flow.glowWidth : CONNECTION_CONFIG.flow.width,
      opacity: isGlow ? CONNECTION_CONFIG.flow.glowOpacity : CONNECTION_CONFIG.flow.opacity,
      resW: resW,
      resH: resH,
    })
    var line = new THREE.Line2(geo, mat)
    line.renderOrder = CONNECTION_CONFIG.renderOrder + (isGlow ? 1 : 2)
    line.frustumCulled = false
    line.visible = false
    line.userData.sampleCount = n
    return line
  }

  function updateFlowBand(line, segments, headT, length, colorA, colorB, brightness) {
    if (!line || !segments || !segments.length) return
    var n = line.userData.sampleCount || CONNECTION_CONFIG.flow.samples
    if (!_flowPos || _flowPos.length !== n * 3) {
      _flowPos = new Float32Array(n * 3)
      _flowCol = new Float32Array(n * 3)
    }
    var startT = Math.max(0, headT - length)
    var endT = clamp(headT, 0, 1)
    if (endT <= startT + 0.001) {
      line.visible = false
      return
    }
    var tmp = _c1
    for (var i = 0; i < n; i++) {
      var u = i / (n - 1)
      var t = lerp(startT, endT, u)
      // 尾淡、头亮
      var fade = Math.pow(u, 0.65)
      pathPointAt(segments, t, tmp)
      _flowPos[i * 3] = tmp.x
      _flowPos[i * 3 + 1] = tmp.y
      _flowPos[i * 3 + 2] = tmp.z
      pathColorAt(segments, t, colorA, colorB, _tmpColor3)
      var b = brightness * fade
      _flowCol[i * 3] = Math.min(1, _tmpColor3.r * b)
      _flowCol[i * 3 + 1] = Math.min(1, _tmpColor3.g * b)
      _flowCol[i * 3 + 2] = Math.min(1, _tmpColor3.b * b)
    }
    line.geometry.setPositions(_flowPos)
    line.geometry.setColors(_flowCol)
    line.geometry.instanceCount = Math.max(1, n - 1)
    line.visible = true
  }

  function MemoryConnectionLayer(options) {
    options = options || {}
    this.parentGroup = options.parentGroup
    this.camera = options.camera
    this.reduceMotion = !!options.reduceMotion
    this.lowPower = !!options.lowPower || this.reduceMotion
    this.onArrivalFlash = typeof options.onArrivalFlash === 'function' ? options.onArrivalFlash : null

    this.group = new THREE.Group()
    this.group.name = 'memory-connection-layer'
    if (this.parentGroup) this.parentGroup.add(this.group)

    this.planetMap = {}
    this.planets = []
    this.connections = []
    this.clusters = []
    this.planetClusterId = {}

    this.resW = 1
    this.resH = 1
    this.time = 0
    this.animToken = 0
    this.activePlanetId = null

    this.ambientLines = []
    this.mainSegments = []
    this.mainLines = []
    this.mainGlows = []
    this.mainInners = []
    this.mainTubes = []
    this.secondaryLines = []

    this.activeFlow = null
    this.activeFlowGlow = null
    this.idleFlow = null
    this.idleFlowGlow = null
    this.endpointSprite = null
    this.endpointGlow = null
    this.ringSprite = null

    this._fadeAmbient = 1
    this._ambientTarget = 1
    this._mainOpacityMul = 1
    this._drawProgress = 0
    this._glowProgress = 0
    this._activating = false
    this._activateElapsed = 0
    this._fadeOutElapsed = -1
    this._pendingActiveId = null
    this._secondaryFlash = 0
    this._activeFlowState = null
    this._idleFlowState = null
    this._ringState = null
    this._arrivalBoost = 0
    this._arrivalPlanetId = null
    this._flowWait = 0
    this._idleFlowWait = 0
    this._ringPlayedForToken = null
    this._activeColorA = CONNECTION_CONFIG.CORE_COLOR
    this._activeColorB = '#ffffff'

    this.samples = this.lowPower ? CONNECTION_CONFIG.curve.samplesLow : CONNECTION_CONFIG.curve.samples
  }

  MemoryConnectionLayer.prototype.getConfig = function () {
    return CONNECTION_CONFIG
  }

  MemoryConnectionLayer.prototype.getRelatedIds = function (planetId) {
    var p = this.planetMap[planetId]
    if (!p || !p.relatedIds) return []
    return p.relatedIds.slice()
  }

  /** 供主场景读取到达瞬间亮度加成 0～1 */
  MemoryConnectionLayer.prototype.getArrivalBoost = function () {
    return this._arrivalBoost
  }

  MemoryConnectionLayer.prototype.setPlanets = function (planets) {
    this.planets = Array.isArray(planets) ? planets : []
    this.planetMap = {}
    for (var i = 0; i < this.planets.length; i++) {
      var p = this.planets[i]
      if (p && p.id) this.planetMap[p.id] = p
    }
    this.refreshConnections()
  }

  MemoryConnectionLayer.prototype.refreshConnections = function () {
    var edgeMap = {}
    var list = []

    function addEdge(sourceId, targetId, type) {
      if (!sourceId || !targetId || sourceId === targetId) return
      if (!this.planetMap[sourceId] || !this.planetMap[targetId]) return
      var key = pairKey(sourceId, targetId)
      if (edgeMap[key]) return
      edgeMap[key] = true
      list.push({
        id: type + '-' + key,
        sourceId: sourceId,
        targetId: targetId,
        type: type,
        weight: type === 'core' ? 0.8 : 1,
      })
    }

    // 1) 同分类 relatedIds
    for (var i = 0; i < this.planets.length; i++) {
      var src = this.planets[i]
      if (!src || src.type === 'core') continue
      var related = src.relatedIds || []
      for (var j = 0; j < related.length; j++) {
        addEdge.call(this, src.id, related[j], 'related')
      }
    }

    // 2) 最近邻保底：任意记忆两两按距离取最短边，避免无同分类时完全无线
    var memories = []
    for (var m = 0; m < this.planets.length; m++) {
      if (this.planets[m] && this.planets[m].type !== 'core') memories.push(this.planets[m])
    }
    var distEdges = []
    for (var a = 0; a < memories.length; a++) {
      for (var b = a + 1; b < memories.length; b++) {
        distEdges.push({
          sourceId: memories[a].id,
          targetId: memories[b].id,
          d2: memories[a].position.distanceToSquared(memories[b].position),
        })
      }
    }
    distEdges.sort(function (x, y) { return x.d2 - y.d2 })
    var nearBudget = Math.max(getVisibleLimit(this.resW), 4)
    for (var d = 0; d < distEdges.length && nearBudget > 0; d++) {
      var before = list.length
      addEdge.call(this, distEdges[d].sourceId, distEdges[d].targetId, 'near')
      if (list.length > before) nearBudget--
    }

    // 3) 核心引力辐线：稳定挑选若干记忆连向核心
    var core = this.planetMap[CONNECTION_CONFIG.CORE_ID]
    if (core && memories.length) {
      var ranked = memories.slice().sort(function (x, y) {
        return hashStr(x.id) - hashStr(y.id)
      })
      var spokes = Math.min(CONNECTION_CONFIG.idle.coreSpokes || 3, ranked.length)
      for (var s = 0; s < spokes; s++) {
        addEdge.call(this, CONNECTION_CONFIG.CORE_ID, ranked[s].id, 'core')
      }
    }

    this.connections = list
    this._buildClusters()
    this._rebuildAmbient()
    if (this.activePlanetId) {
      var keep = this.activePlanetId
      this.activePlanetId = null
      this.setActivePlanet(keep)
    }
  }

  /** 关系边连通分量 → 星球簇 */
  MemoryConnectionLayer.prototype._buildClusters = function () {
    this.clusters = []
    this.planetClusterId = {}
    var parent = {}
    function find(x) {
      if (parent[x] !== x) parent[x] = find(parent[x])
      return parent[x]
    }
    function unite(a, b) {
      var ra = find(a)
      var rb = find(b)
      if (ra !== rb) parent[rb] = ra
    }

    for (var i = 0; i < this.planets.length; i++) {
      var p = this.planets[i]
      if (!p || p.type === 'core') continue
      parent[p.id] = p.id
    }
    for (var e = 0; e < this.connections.length; e++) {
      var c = this.connections[e]
      if (c.type !== 'related') continue
      if (parent[c.sourceId] != null && parent[c.targetId] != null) unite(c.sourceId, c.targetId)
    }

    var groups = {}
    for (var id in parent) {
      if (!Object.prototype.hasOwnProperty.call(parent, id)) continue
      var rootId = find(id)
      if (!groups[rootId]) groups[rootId] = []
      groups[rootId].push(id)
    }

    var cid = 0
    for (var g in groups) {
      if (!Object.prototype.hasOwnProperty.call(groups, g)) continue
      var members = groups[g]
      if (members.length < CONNECTION_CONFIG.cluster.minSize) continue
      var hub = new THREE.Vector3()
      for (var m = 0; m < members.length; m++) {
        var pl = this.planetMap[members[m]]
        if (pl) hub.add(pl.position)
        this.planetClusterId[members[m]] = cid
      }
      hub.multiplyScalar(1 / members.length)
      // 枢纽略向核心收拢，主干更干净
      hub.multiplyScalar(0.82)
      this.clusters.push({ id: cid, memberIds: members, hub: hub })
      cid++
    }
  }

  MemoryConnectionLayer.prototype._clearAmbient = function () {
    for (var i = 0; i < this.ambientLines.length; i++) {
      var amb = this.ambientLines[i]
      disposeLine(amb.line, this.group)
      disposeLine(amb.glow, this.group)
      disposeLine(amb.tube, this.group)
    }
    this.ambientLines = []
    this._clearIdleFlow()
  }

  MemoryConnectionLayer.prototype._clearIdleFlow = function () {
    disposeLine(this.idleFlow, this.group)
    disposeLine(this.idleFlowGlow, this.group)
    this.idleFlow = null
    this.idleFlowGlow = null
    this._idleFlowState = null
  }

  MemoryConnectionLayer.prototype._rebuildAmbient = function () {
    this._clearAmbient()
    var total = this.connections.length
    if (total <= 0) return

    // 先稳定排序，再为核心辐线预留配额，其余按 related → near 填充
    var ranked = this.connections.slice().sort(function (a, b) {
      var wa = a.type === 'related' ? 0 : a.type === 'core' ? 1 : 2
      var wb = b.type === 'related' ? 0 : b.type === 'core' ? 1 : 2
      if (wa !== wb) return wa - wb
      return hashStr(a.id) - hashStr(b.id)
    })
    ranked = selectAmbientConnections(ranked, Math.min(getVisibleLimit(this.resW), total))
    var pickN = ranked.length

    var idle = CONNECTION_CONFIG.idle
    for (var i = 0; i < pickN; i++) {
      var conn = ranked[i]
      var a = this.planetMap[conn.sourceId]
      var b = this.planetMap[conn.targetId]
      if (!a || !b) continue
      var built = buildCurve(conn.id, a.position, b.position, a.radius, b.radius, this.samples)
      if (!built) continue

      var typeOpacity = idle.typeOpacity[conn.type] || 1
      var depthFactor = getDepthFactor(a, b, this.camera)
      var baseOpacity = idle.opacity * typeOpacity
      var visibleOpacity = baseOpacity * depthFactor

      // Tube 主体：真实体积，手机上必可见
      var tubeColor = conn.type === 'core' ? CONNECTION_CONFIG.CORE_COLOR : idle.color
      var tube = createTubeFromCurve(
        built,
        idle.tubeRadius,
        tubeColor,
        visibleOpacity,
        CONNECTION_CONFIG.renderOrder
      )
      if (tube) {
        setTubeProgress(tube, 1)
        this.group.add(tube)
      }

      var glow = null
      if (!(this.lowPower && CONNECTION_CONFIG.lowPowerNoGlow)) {
        glow = createLine2FromCurve(built, idle.glowColor, idle.glowColor, {
          linewidth: idle.glowWidth,
          opacity: idle.glowOpacity * typeOpacity * depthFactor,
          resW: this.resW,
          resH: this.resH,
        })
        glow.renderOrder = CONNECTION_CONFIG.renderOrder - 1
        setLineProgress(glow, 1)
        this.group.add(glow)
      }

      var line = createLine2FromCurve(built, idle.color, tubeColor, {
        linewidth: idle.width,
        opacity: Math.min(1, (baseOpacity + 0.12) * depthFactor),
        resW: this.resW,
        resH: this.resH,
      })
      setLineProgress(line, 1)
      this.group.add(line)

      var h = hashStr(conn.id)
      this.ambientLines.push({
        id: conn.id,
        type: conn.type,
        source: a,
        target: b,
        line: line,
        glow: glow,
        tube: tube,
        segments: [built],
        phase: ((h % 1000) / 1000) * Math.PI * 2,
        speed: (Math.PI * 2) / idle.breathDuration,
        flowSeed: ((h >>> 8) % 1000) / 1000,
        depthFactor: depthFactor,
        baseLineOpacity: Math.min(1, baseOpacity + 0.12),
        baseGlowOpacity: idle.glowOpacity * typeOpacity,
        baseTubeOpacity: baseOpacity,
      })
    }

    this._idleFlowWait = 1.2 + (hashStr('idle-boot') % 100) / 100 * 2.5
  }

  MemoryConnectionLayer.prototype._clearActiveVisuals = function () {
    for (var i = 0; i < this.mainLines.length; i++) disposeLine(this.mainLines[i], this.group)
    for (var g = 0; g < this.mainGlows.length; g++) disposeLine(this.mainGlows[g], this.group)
    for (var n = 0; n < this.mainInners.length; n++) disposeLine(this.mainInners[n], this.group)
    for (var t = 0; t < this.mainTubes.length; t++) disposeLine(this.mainTubes[t], this.group)
    this.mainLines = []
    this.mainGlows = []
    this.mainInners = []
    this.mainTubes = []
    this.mainSegments = []
    this._clearActiveFlow()
    this._clearEndpoint()
    this._clearRing()
  }

  MemoryConnectionLayer.prototype._clearSecondary = function () {
    for (var i = 0; i < this.secondaryLines.length; i++) {
      disposeLine(this.secondaryLines[i].line, this.group)
      disposeLine(this.secondaryLines[i].glow, this.group)
      disposeLine(this.secondaryLines[i].tube, this.group)
    }
    this.secondaryLines = []
  }

  MemoryConnectionLayer.prototype._clearActiveFlow = function () {
    disposeLine(this.activeFlow, this.group)
    disposeLine(this.activeFlowGlow, this.group)
    this.activeFlow = null
    this.activeFlowGlow = null
    this._activeFlowState = null
  }

  MemoryConnectionLayer.prototype._clearEndpoint = function () {
    disposeSprite(this.endpointSprite, this.group)
    disposeSprite(this.endpointGlow, this.group)
    this.endpointSprite = null
    this.endpointGlow = null
  }

  MemoryConnectionLayer.prototype._clearRing = function () {
    disposeSprite(this.ringSprite, this.group)
    this.ringSprite = null
    this._ringState = null
  }

  MemoryConnectionLayer.prototype._ensureActiveFlow = function () {
    if (!this.activeFlow) {
      this.activeFlow = createFlowBand(this.resW, this.resH, false)
      this.group.add(this.activeFlow)
    }
    if (!this.activeFlowGlow && !(this.lowPower && CONNECTION_CONFIG.lowPowerNoGlow)) {
      this.activeFlowGlow = createFlowBand(this.resW, this.resH, true)
      this.group.add(this.activeFlowGlow)
    }
  }

  MemoryConnectionLayer.prototype._startActiveFlow = function (immediate) {
    if (this.reduceMotion || !this.mainSegments.length) return
    this._ensureActiveFlow()
    this._activeFlowState = {
      progress: 0,
      duration: CONNECTION_CONFIG.flow.duration,
      token: this.animToken,
    }
    if (!immediate) {
      this._flowWait =
        CONNECTION_CONFIG.flow.repeatDelayMin +
        ((hashStr(this.activePlanetId + 'flow') % 100) / 100) *
          (CONNECTION_CONFIG.flow.repeatDelayMax - CONNECTION_CONFIG.flow.repeatDelayMin)
    }
  }

  MemoryConnectionLayer.prototype._buildActiveLines = function (planetId) {
    this._clearActiveVisuals()
    this._clearSecondary()

    var target = this.planetMap[planetId]
    var core = this.planetMap[CONNECTION_CONFIG.CORE_ID]
    if (!target || !core || target.type === 'core') return false

    var colorA = CONNECTION_CONFIG.CORE_COLOR
    var colorB = target.color || '#ffffff'
    this._activeColorA = colorA
    this._activeColorB = colorB

    var segments = []
    var clusterId = this.planetClusterId[planetId]
    var useHub = clusterId != null && this.clusters[clusterId]

    if (useHub) {
      var hub = this.clusters[clusterId].hub
      var trunk = buildCurve('trunk|' + planetId, core.position, hub, core.radius, CONNECTION_CONFIG.cluster.hubRadius, this.samples)
      var branch = buildCurve('branch|' + planetId, hub, target.position, CONNECTION_CONFIG.cluster.hubRadius, target.radius, this.samples)
      if (!trunk || !branch) return false
      segments.push(trunk, branch)
    } else {
      var direct = buildCurve('core|' + planetId, core.position, target.position, core.radius, target.radius, this.samples)
      if (!direct) return false
      segments.push(direct)
    }

    this.mainSegments = segments
    var active = CONNECTION_CONFIG.active
    var showGlow = !(this.lowPower && CONNECTION_CONFIG.lowPowerNoGlow)

    for (var s = 0; s < segments.length; s++) {
      var seg = segments[s]
      // Tube 打底：保证激活主线在任何设备上都有体积
      var tubeCol = s === 0 ? colorA : colorB
      var tube = createTubeFromCurve(
        seg,
        active.tubeRadius,
        tubeCol,
        Math.min(1, active.opacity * 0.75),
        CONNECTION_CONFIG.renderOrder
      )
      if (tube) {
        this.group.add(tube)
        this.mainTubes.push(tube)
      }

      var line = createLine2FromCurve(seg, colorA, colorB, {
        linewidth: active.width,
        opacity: active.opacity,
        resW: this.resW,
        resH: this.resH,
      })
      this.group.add(line)
      this.mainLines.push(line)

      if (showGlow) {
        var glow = createLine2FromCurve(seg, colorA, colorB, {
          linewidth: active.glowWidth,
          opacity: active.glowOpacity,
          resW: this.resW,
          resH: this.resH,
        })
        glow.renderOrder = CONNECTION_CONFIG.renderOrder - 1
        this.group.add(glow)
        this.mainGlows.push(glow)
      }

      // 内高亮：仅路径中段（顶点 alpha 窗）
      _tmpColor.set('#ffffff')
      _tmpColor2.set(colorB)
      function hex2(n) {
        var s2 = Math.round(clamp(n, 0, 1) * 255).toString(16)
        return s2.length < 2 ? '0' + s2 : s2
      }
      var innerHex =
        '#' +
        hex2(lerp(_tmpColor.r, _tmpColor2.r, 0.35)) +
        hex2(lerp(_tmpColor.g, _tmpColor2.g, 0.35)) +
        hex2(lerp(_tmpColor.b, _tmpColor2.b, 0.35))
      var inner = createLine2FromCurve(
        seg,
        innerHex,
        colorB,
        {
          linewidth: active.innerWidth,
          opacity: active.innerOpacity,
          resW: this.resW,
          resH: this.resH,
        },
        function (t) {
          if (t < 0.28 || t > 0.78) return 0.05
          var mid = 1 - Math.abs(t - 0.53) / 0.25
          return clamp(mid, 0.15, 1)
        }
      )
      inner.renderOrder = CONNECTION_CONFIG.renderOrder + 1
      this.group.add(inner)
      this.mainInners.push(inner)
    }

    // 相关分支（最多 2）
    var related = (target.relatedIds || []).slice(0, CONNECTION_CONFIG.related.maxVisible)
    var relCfg = CONNECTION_CONFIG.related
    for (var r = 0; r < related.length; r++) {
      var rid = related[r]
      var other = this.planetMap[rid]
      if (!other || other.id === CONNECTION_CONFIG.CORE_ID) continue
      var sid = pairKey(planetId, rid)
      var built = buildCurve('sec-' + sid, target.position, other.position, target.radius, other.radius, this.samples)
      if (!built) continue
      var secTube = createTubeFromCurve(
        built,
        relCfg.tubeRadius,
        target.color,
        relCfg.opacity,
        CONNECTION_CONFIG.renderOrder
      )
      if (secTube) this.group.add(secTube)
      var secGlow = null
      if (showGlow) {
        secGlow = createLine2FromCurve(built, target.color, other.color, {
          linewidth: relCfg.glowWidth,
          opacity: relCfg.glowOpacity,
          resW: this.resW,
          resH: this.resH,
        })
        secGlow.renderOrder = CONNECTION_CONFIG.renderOrder - 1
        this.group.add(secGlow)
      }
      var sec = createLine2FromCurve(built, target.color, other.color, {
        linewidth: relCfg.width,
        opacity: relCfg.opacity,
        resW: this.resW,
        resH: this.resH,
      })
      this.group.add(sec)
      this.secondaryLines.push({ line: sec, glow: secGlow, tube: secTube, id: sid })
    }

    // 端点接触亮点
    var endPt = segments[segments.length - 1].endPoint
    var tex = getSoftTexture()
    this.endpointGlow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: tex,
        color: new THREE.Color(colorB),
        transparent: true,
        opacity: 0.45,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        fog: false,
      })
    )
    this.endpointGlow.position.copy(endPt)
    this.endpointGlow.scale.setScalar(CONNECTION_CONFIG.endpoint.glowSize)
    this.endpointGlow.renderOrder = CONNECTION_CONFIG.renderOrder + 3
    this.group.add(this.endpointGlow)

    this.endpointSprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: tex,
        color: new THREE.Color(colorB),
        transparent: true,
        opacity: 0.9,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        fog: false,
      })
    )
    this.endpointSprite.position.copy(endPt)
    this.endpointSprite.scale.setScalar(CONNECTION_CONFIG.endpoint.pointSize)
    this.endpointSprite.renderOrder = CONNECTION_CONFIG.renderOrder + 4
    this.group.add(this.endpointSprite)

    var initP = this.reduceMotion ? 1 : 0
    this._setMainProgress(initP, initP)
    for (var k = 0; k < this.secondaryLines.length; k++) {
      setLineProgress(this.secondaryLines[k].line, initP)
      if (this.secondaryLines[k].glow) setLineProgress(this.secondaryLines[k].glow, initP)
      if (this.secondaryLines[k].tube) setTubeProgress(this.secondaryLines[k].tube, initP)
    }

    this._secondaryFlash = 1
    this._mainOpacityMul = 1
    this._arrivalBoost = 0
    return true
  }

  MemoryConnectionLayer.prototype._setMainProgress = function (bodyP, glowP) {
    for (var i = 0; i < this.mainLines.length; i++) {
      var local = this.mainLines.length === 1 ? bodyP : (i === 0 ? clamp(bodyP * 2, 0, 1) : clamp(bodyP * 2 - 1, 0, 1))
      setLineProgress(this.mainLines[i], local)
      if (this.mainInners[i]) setLineProgress(this.mainInners[i], local)
      if (this.mainTubes[i]) setTubeProgress(this.mainTubes[i], local)
    }
    for (var g = 0; g < this.mainGlows.length; g++) {
      var gLocal = this.mainGlows.length === 1 ? glowP : (g === 0 ? clamp(glowP * 2, 0, 1) : clamp(glowP * 2 - 1, 0, 1))
      setLineProgress(this.mainGlows[g], gLocal)
    }
    var showEnd = bodyP > 0.92
    if (this.endpointSprite) this.endpointSprite.visible = showEnd
    if (this.endpointGlow) this.endpointGlow.visible = showEnd
  }

  MemoryConnectionLayer.prototype._playArrivalRing = function () {
    if (!this.mainSegments.length) return
    var endPt = this.mainSegments[this.mainSegments.length - 1].endPoint
    var target = this.planetMap[this.activePlanetId]
    var colorB = (target && target.color) || this._activeColorB
    var radius = (target && target.radius) || 0.55
    var ep = CONNECTION_CONFIG.endpoint

    this._clearRing()
    this.ringSprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: getSoftTexture(),
        color: new THREE.Color(colorB),
        transparent: true,
        opacity: ep.ringOpacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    )
    this.ringSprite.position.copy(endPt)
    var base = radius * 2 * ep.ringStartScale
    this.ringSprite.scale.setScalar(base)
    this.ringSprite.renderOrder = CONNECTION_CONFIG.renderOrder + 2
    this.group.add(this.ringSprite)
    this._ringState = {
      elapsed: 0,
      duration: ep.ringDuration,
      startScale: base,
      endScale: radius * 2 * ep.ringEndScale,
      token: this.animToken,
    }
    this._arrivalBoost = ep.arrivalBoost
    this._arrivalPlanetId = this.activePlanetId
    if (this.onArrivalFlash) this.onArrivalFlash(this.activePlanetId, this._arrivalBoost)
  }

  MemoryConnectionLayer.prototype.setActivePlanet = function (planetId) {
    if (planetId === CONNECTION_CONFIG.CORE_ID) planetId = null

    if (planetId && planetId === this.activePlanetId && this._fadeOutElapsed < 0 && !this._pendingActiveId) {
      return
    }

    this.animToken += 1
    this._ringPlayedForToken = null

    if (!planetId) {
      this._pendingActiveId = null
      this.activePlanetId = null
      this._activating = false
      this._ambientTarget = 1
      this._clearActiveFlow()
      this._clearRing()
      if (this.mainLines.length || this.secondaryLines.length) this._fadeOutElapsed = 0
      else {
        this._fadeOutElapsed = -1
        this._clearActiveVisuals()
        this._clearSecondary()
      }
      return
    }

    if (!this.planetMap[planetId] || this.planetMap[planetId].type === 'core') {
      this.setActivePlanet(null)
      return
    }

    if (this.mainLines.length && this.activePlanetId && this.activePlanetId !== planetId) {
      this._pendingActiveId = planetId
      this._fadeOutElapsed = 0
      this._activating = false
      this._clearActiveFlow()
      this._clearRing()
      this._ambientTarget = CONNECTION_CONFIG.idle.activeDim
      return
    }

    this._pendingActiveId = null
    this.activePlanetId = planetId
    this._ambientTarget = CONNECTION_CONFIG.idle.activeDim
    this._fadeOutElapsed = -1
    this._clearIdleFlow()

    if (!this._buildActiveLines(planetId)) {
      this.activePlanetId = null
      this._ambientTarget = 1
      return
    }

    this._activating = true
    this._activateElapsed = 0
    this._drawProgress = 0
    this._glowProgress = 0
    this._flowWait = 0

    if (this.reduceMotion) {
      this._activating = false
      this._drawProgress = 1
      this._glowProgress = 1
      this._setMainProgress(1, 1)
      for (var s = 0; s < this.secondaryLines.length; s++) {
        setLineProgress(this.secondaryLines[s].line, 1)
        if (this.secondaryLines[s].glow) setLineProgress(this.secondaryLines[s].glow, 1)
        if (this.secondaryLines[s].tube) setTubeProgress(this.secondaryLines[s].tube, 1)
      }
      this._ringPlayedForToken = this.animToken
    }
  }

  MemoryConnectionLayer.prototype._startPending = function () {
    var id = this._pendingActiveId
    this._pendingActiveId = null
    this._clearActiveVisuals()
    this._clearSecondary()
    if (!id) {
      this.activePlanetId = null
      this._ambientTarget = 1
      return
    }
    this.activePlanetId = null
    this.setActivePlanet(id)
  }

  MemoryConnectionLayer.prototype.update = function (deltaTime) {
    var dt = Math.min(Math.max(deltaTime || 0, 0), 0.05)
    this.time += dt
    var idle = CONNECTION_CONFIG.idle
    var active = CONNECTION_CONFIG.active
    var flow = CONNECTION_CONFIG.flow
    var ep = CONNECTION_CONFIG.endpoint

    // 默认关系线呼吸（激活时压暗；默认光带在激活态关闭）
    this._fadeAmbient += (this._ambientTarget - this._fadeAmbient) * Math.min(1, dt * 3.2)
    var breathAmp = (idle.breathMax - idle.breathMin) * 0.5
    var breathMid = (idle.breathMax + idle.breathMin) * 0.5
    for (var i = 0; i < this.ambientLines.length; i++) {
      var amb = this.ambientLines[i]
      var targetDepth = getDepthFactor(amb.source, amb.target, this.camera)
      amb.depthFactor += (targetDepth - amb.depthFactor) * Math.min(1, dt * 4)
      var breath = this.reduceMotion ? 1 : breathMid + breathAmp * Math.sin(this.time * amb.speed + amb.phase)
      var layerOpacity = breath * this._fadeAmbient * amb.depthFactor
      if (amb.line && amb.line.material) {
        amb.line.material.opacity = amb.baseLineOpacity * layerOpacity
      }
      if (amb.glow && amb.glow.material) {
        amb.glow.material.opacity = amb.baseGlowOpacity * layerOpacity
      }
      if (amb.tube && amb.tube.material) {
        amb.tube.material.opacity = amb.baseTubeOpacity * layerOpacity
      }
    }

    // 默认偶发光带（仅非激活）
    if (!this.activePlanetId && !this.reduceMotion && !(this.lowPower && CONNECTION_CONFIG.lowPowerNoIdleFlow)) {
      if (!this._idleFlowState) {
        this._idleFlowWait -= dt
        if (this._idleFlowWait <= 0 && this.ambientLines.length) {
          var idx = Math.floor(((hashStr('idle' + Math.floor(this.time * 10)) % 1000) / 1000) * this.ambientLines.length)
          var pick = this.ambientLines[idx]
          if (!this.idleFlow) {
            this.idleFlow = createFlowBand(this.resW, this.resH, false)
            this.idleFlow.material.linewidth = 2.2
            this.idleFlow.material.opacity = idle.flowOpacity
            this.group.add(this.idleFlow)
          }
          if (!this.idleFlowGlow && !(this.lowPower && CONNECTION_CONFIG.lowPowerNoGlow)) {
            this.idleFlowGlow = createFlowBand(this.resW, this.resH, true)
            this.idleFlowGlow.material.linewidth = 8
            this.idleFlowGlow.material.opacity = 0.18
            this.group.add(this.idleFlowGlow)
          }
          this._idleFlowState = {
            segments: pick.segments,
            progress: 0,
            duration: idle.flowDuration,
            length: idle.flowLength,
          }
          this._idleFlowWait =
            idle.flowIntervalMin + ((pick.flowSeed || 0) * (idle.flowIntervalMax - idle.flowIntervalMin))
        }
      } else {
        this._idleFlowState.progress += dt / this._idleFlowState.duration
        var ht = easeOutCubic(clamp(this._idleFlowState.progress, 0, 1))
        updateFlowBand(
          this.idleFlow,
          this._idleFlowState.segments,
          ht,
          this._idleFlowState.length,
          idle.color,
          idle.glowColor,
          1.1
        )
        if (this.idleFlowGlow) {
          updateFlowBand(
            this.idleFlowGlow,
            this._idleFlowState.segments,
            ht,
            this._idleFlowState.length * 1.15,
            idle.glowColor,
            idle.color,
            0.7
          )
        }
        if (this._idleFlowState.progress >= 1) {
          if (this.idleFlow) this.idleFlow.visible = false
          if (this.idleFlowGlow) this.idleFlowGlow.visible = false
          this._idleFlowState = null
        }
      }
    } else if (this._idleFlowState || this.idleFlow) {
      this._clearIdleFlow()
    }

    // 旧主线淡出
    if (this._fadeOutElapsed >= 0) {
      this._fadeOutElapsed += dt
      var fadeT = clamp(this._fadeOutElapsed / active.fadeOut, 0, 1)
      this._mainOpacityMul = 1 - fadeT
      for (var ml = 0; ml < this.mainLines.length; ml++) {
        if (this.mainLines[ml].material) this.mainLines[ml].material.opacity = active.opacity * this._mainOpacityMul
        if (this.mainInners[ml] && this.mainInners[ml].material) {
          this.mainInners[ml].material.opacity = active.innerOpacity * this._mainOpacityMul
        }
        if (this.mainTubes[ml] && this.mainTubes[ml].material) {
          this.mainTubes[ml].material.opacity =
            (this.mainTubes[ml].userData.baseOpacity || active.opacity * 0.75) * this._mainOpacityMul
        }
      }
      for (var mg = 0; mg < this.mainGlows.length; mg++) {
        if (this.mainGlows[mg].material) this.mainGlows[mg].material.opacity = active.glowOpacity * this._mainOpacityMul
      }
      for (var sc = 0; sc < this.secondaryLines.length; sc++) {
        var sec = this.secondaryLines[sc]
        if (sec.line && sec.line.material) sec.line.material.opacity = CONNECTION_CONFIG.related.opacity * this._mainOpacityMul
        if (sec.glow && sec.glow.material) sec.glow.material.opacity = CONNECTION_CONFIG.related.glowOpacity * this._mainOpacityMul
        if (sec.tube && sec.tube.material) {
          sec.tube.material.opacity =
            (sec.tube.userData.baseOpacity || CONNECTION_CONFIG.related.opacity) * this._mainOpacityMul
        }
      }
      if (this.endpointSprite && this.endpointSprite.material) {
        this.endpointSprite.material.opacity = 0.9 * this._mainOpacityMul
      }
      if (fadeT >= 1) {
        this._fadeOutElapsed = -1
        this._clearActiveVisuals()
        this._clearSecondary()
        if (this._pendingActiveId) this._startPending()
        else {
          this.activePlanetId = null
          this._ambientTarget = 1
        }
      }
    }

    // 激活动画
    if (this._activating && this.mainLines.length) {
      this._activateElapsed += dt
      var e = this._activateElapsed
      this._drawProgress = easeOutCubic(clamp(e / active.drawDuration, 0, 1))
      this._glowProgress = easeOutCubic(clamp((e - active.glowDelay) / active.drawDuration, 0, 1))
      this._setMainProgress(this._drawProgress, this._glowProgress)

      var secP = clamp((this._drawProgress - 0.4) / 0.6, 0, 1)
      for (var k = 0; k < this.secondaryLines.length; k++) {
        setLineProgress(this.secondaryLines[k].line, secP)
        if (this.secondaryLines[k].glow) setLineProgress(this.secondaryLines[k].glow, secP)
        if (this.secondaryLines[k].tube) setTubeProgress(this.secondaryLines[k].tube, secP)
      }

      // 主体过半后启动能量光带
      if (this._drawProgress > 0.45 && !this._activeFlowState) {
        this._startActiveFlow(true)
      }

      if (this._drawProgress >= 1 && this._glowProgress >= 1) {
        this._activating = false
        this._setMainProgress(1, 1)
        for (var m = 0; m < this.secondaryLines.length; m++) {
          setLineProgress(this.secondaryLines[m].line, 1)
          if (this.secondaryLines[m].glow) setLineProgress(this.secondaryLines[m].glow, 1)
          if (this.secondaryLines[m].tube) setTubeProgress(this.secondaryLines[m].tube, 1)
        }
      }
    }

    // 次级闪过
    if (this._secondaryFlash > 0 && !this.reduceMotion) {
      this._secondaryFlash = Math.max(0, this._secondaryFlash - dt * (1000 / CONNECTION_CONFIG.related.flashMs))
      var flashBoost = this._secondaryFlash * 0.22
      for (var f = 0; f < this.secondaryLines.length; f++) {
        var sl = this.secondaryLines[f].line
        if (sl && sl.material) {
          sl.material.opacity = (CONNECTION_CONFIG.related.opacity + flashBoost) * this._mainOpacityMul
        }
      }
    }

    // 激活能量光带
    if (this._activeFlowState && this._activeFlowState.token === this.animToken) {
      this._activeFlowState.progress += dt / this._activeFlowState.duration
      var head = easeOutCubic(clamp(this._activeFlowState.progress, 0, 1))
      updateFlowBand(
        this.activeFlow,
        this.mainSegments,
        head,
        flow.length,
        this._activeColorA,
        this._activeColorB,
        flow.brightness
      )
      if (this.activeFlowGlow) {
        updateFlowBand(
          this.activeFlowGlow,
          this.mainSegments,
          head,
          flow.length * 1.2,
          this._activeColorA,
          this._activeColorB,
          flow.brightness * 0.55
        )
      }
      if (this._activeFlowState.progress >= 1) {
        if (this.activeFlow) this.activeFlow.visible = false
        if (this.activeFlowGlow) this.activeFlowGlow.visible = false
        this._activeFlowState = null
        // 首次光带抵达终点：播放一次扩散光环
        if (this._ringPlayedForToken !== this.animToken) {
          this._playArrivalRing()
          this._ringPlayedForToken = this.animToken
        }
        this._flowWait =
          flow.repeatDelayMin +
          ((hashStr(String(this.animToken) + 'gap') % 100) / 100) * (flow.repeatDelayMax - flow.repeatDelayMin)
      }
    } else if (
      this.activePlanetId &&
      !this._activating &&
      this._fadeOutElapsed < 0 &&
      this.mainSegments.length &&
      !this.reduceMotion
    ) {
      this._flowWait -= dt
      if (this._flowWait <= 0 && !this._activeFlowState) {
        this._startActiveFlow(true)
      }
    }

    // 端点呼吸
    if (this.endpointSprite && this.endpointSprite.visible) {
      var eb = this.reduceMotion ? 1 : 0.85 + 0.15 * Math.sin(this.time * ((Math.PI * 2) / ep.breathSec))
      this.endpointSprite.material.opacity = 0.9 * eb * this._mainOpacityMul
      if (this.endpointGlow) {
        this.endpointGlow.material.opacity = 0.4 * eb * this._mainOpacityMul
        this.endpointGlow.scale.setScalar(ep.glowSize * (0.92 + 0.08 * eb))
      }
    }

    // 扩散光环
    if (this._ringState && this._ringState.token === this.animToken && this.ringSprite) {
      this._ringState.elapsed += dt
      var rt = clamp(this._ringState.elapsed / this._ringState.duration, 0, 1)
      var sc = lerp(this._ringState.startScale, this._ringState.endScale, easeOutCubic(rt))
      this.ringSprite.scale.setScalar(sc)
      this.ringSprite.material.opacity = ep.ringOpacity * (1 - rt) * this._mainOpacityMul
      if (rt >= 1) this._clearRing()
    }

    // 到达亮度衰减
    if (this._arrivalBoost > 0) {
      this._arrivalBoost = Math.max(0, this._arrivalBoost - dt / ep.arrivalBoostDecay)
    }
  }

  MemoryConnectionLayer.prototype.resize = function (width, height) {
    this.resW = Math.max(1, width || 1)
    this.resH = Math.max(1, height || 1)
    function applyRes(line, w, h) {
      if (line && line.material && line.material.resolution) line.material.resolution.set(w, h)
    }
    for (var i = 0; i < this.ambientLines.length; i++) {
      applyRes(this.ambientLines[i].line, this.resW, this.resH)
      applyRes(this.ambientLines[i].glow, this.resW, this.resH)
    }
    for (var a = 0; a < this.mainLines.length; a++) applyRes(this.mainLines[a], this.resW, this.resH)
    for (var b = 0; b < this.mainGlows.length; b++) applyRes(this.mainGlows[b], this.resW, this.resH)
    for (var c = 0; c < this.mainInners.length; c++) applyRes(this.mainInners[c], this.resW, this.resH)
    for (var d = 0; d < this.secondaryLines.length; d++) {
      applyRes(this.secondaryLines[d].line, this.resW, this.resH)
      applyRes(this.secondaryLines[d].glow, this.resW, this.resH)
    }
    applyRes(this.activeFlow, this.resW, this.resH)
    applyRes(this.activeFlowGlow, this.resW, this.resH)
    applyRes(this.idleFlow, this.resW, this.resH)
    applyRes(this.idleFlowGlow, this.resW, this.resH)
  }

  MemoryConnectionLayer.prototype.dispose = function () {
    this.animToken += 1
    this._clearAmbient()
    this._clearActiveVisuals()
    this._clearSecondary()
    this._clearIdleFlow()
    if (this.parentGroup && this.group) this.parentGroup.remove(this.group)
    this.planetMap = {}
    this.planets = []
    this.connections = []
    this.activePlanetId = null
  }

  root.MemoryConnectionLayer = MemoryConnectionLayer
  root.MemoryConnectionConfig = CONNECTION_CONFIG
})(typeof window !== 'undefined' ? window : this)

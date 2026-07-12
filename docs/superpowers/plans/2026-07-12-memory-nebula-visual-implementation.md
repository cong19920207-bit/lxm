# Memory Nebula Visual Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the memory-nebula relationship network readable by default, unmistakably highlighted after selection, and visually unify the header and peripheral controls.

**Architecture:** Preserve the existing Three.js scene and the independent `MemoryConnectionLayer` boundary. The HTML file owns glass-surface presentation, `memory-nebula.js` owns DOM/scene interaction state, and `memory-connection-layer.js` owns relationship ranking and line rendering.

**Tech Stack:** HTML5, CSS, vanilla JavaScript, Three.js, Line2, pytest static-contract tests.

## Global Constraints

- Do not modify backend APIs, memory relationship semantics, planet image assets, or memory-card content structure.
- Do not add third-party dependencies.
- Mobile default connection cap is 14; wide-screen cap is 18.
- Header copy is `她记得的你` and `N 颗记忆星体`.
- Reduced-motion mode keeps static hierarchy while disabling breathing, flow, and expansion animations.
- Preserve all existing local user changes outside the files named below.

## File Map

- `frontend/pages/memory.html`: glass header/footer presentation, semantic header copy, count subtitle, and controls.
- `frontend/static/js/memory-nebula.js`: count subtitle update and selection/interaction state passed to the connection layer.
- `frontend/static/js/memory-connection-layer.js`: relationship caps, per-type visuals, camera-depth attenuation, active-path hierarchy, and reduced-motion behavior.
- `tests/test_h5_static_contract.py`: stable DOM, copy, and configuration anchors for the new presentation.

---

### Task 1: Lock the new surface contract and implement the glass chrome

**Files:**
- Modify: `tests/test_h5_static_contract.py:70-155`
- Modify: `frontend/pages/memory.html:30-134,473-533`

**Interfaces:**
- Consumes: existing element IDs `nebula-back`, `nebula-tip`, `nebula-count-num`, `nebula-bottom-bar`, `nebula-gesture-hint`, and `nebula-recenter`.
- Produces: `#nebula-count-subtitle` for `memory-nebula.js`; CSS classes `nebula-top-fade`, `bar-title`, and `bar-subtitle`.

- [ ] **Step 1: Write the failing static-contract assertions**

Add these fragments to `test_memory_html_nebula_surface_contract`:

```python
    for fragment in (
        'class="nebula-top-fade"',
        'class="bar-title">她记得的你</div>',
        'id="nebula-count-subtitle"',
        'aria-label="记忆说明"',
        '拖动探索 · 点击查看记忆',
        'backdrop-filter: blur(18px)',
        '.nebula-top-bar .back-btn:active .back-btn-inner',
    ):
        assert fragment in html, fragment
    assert '枚记忆' not in html
    assert '拖动可探索星云' not in html
```

- [ ] **Step 2: Run the contract test and verify failure**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
```

Expected: FAIL because `nebula-top-fade`, the new title/subtitle, and new hint copy are absent.

- [ ] **Step 3: Replace the top-bar markup and bottom hint**

Use this structure inside `<body>`:

```html
  <div class="nebula-top-fade" aria-hidden="true"></div>
  <div class="nebula-top-bar">
    <button type="button" class="back-btn" id="nebula-back" aria-label="返回">
      <span class="back-btn-inner" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
      </span>
    </button>
    <div class="bar-center">
      <div class="bar-title">她记得的你</div>
      <div class="bar-subtitle" id="nebula-count-subtitle">0 颗记忆星体</div>
    </div>
    <button type="button" class="nebula-count-chip" id="nebula-tip" aria-label="记忆说明">
      <svg class="chip-info" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
        <path d="M8 7.2v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <circle cx="8" cy="5.2" r="0.7" fill="currentColor"/>
      </svg>
    </button>
    <span id="nebula-count-num" hidden>0</span>
  </div>
```

Change the hint text to:

```html
<span>拖动探索 · 点击查看记忆</span>
```

- [ ] **Step 4: Implement the glass-surface CSS**

Set `.nebula-top-fade` to a fixed 116-pixel, pointer-transparent gradient; make `.bar-center` a centered column; style `.bar-title` at 17 pixels and `.bar-subtitle` at 11 pixels. Apply the shared glass treatment below to the back/info/recenter/hint surfaces:

```css
background: linear-gradient(145deg, rgba(33, 27, 58, 0.62), rgba(8, 8, 24, 0.42));
border: 1px solid rgba(255, 255, 255, 0.16);
box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 8px 24px rgba(0, 0, 0, 0.24);
backdrop-filter: blur(18px) saturate(130%);
-webkit-backdrop-filter: blur(18px) saturate(130%);
```

Use this pressed state and preserve a 44-pixel target:

```css
.nebula-top-bar .back-btn:active .back-btn-inner,
.nebula-count-chip:active {
  transform: scale(0.94);
  background: rgba(47, 38, 78, 0.68);
}
```

Add `.nebula-gesture-hint` padding, border radius, border, background, blur, and shadow so it is a glass pill. Include all new transitions in the reduced-motion media query.

- [ ] **Step 5: Run the contract test and verify it passes**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
```

Expected: `1 passed`.

---

### Task 2: Increase default network density with explicit visual hierarchy

**Files:**
- Modify: `tests/test_h5_static_contract.py:125-155`
- Modify: `frontend/static/js/memory-connection-layer.js:31-131,539-750,1076-1140,1240-1380`

**Interfaces:**
- Consumes: planet records `{id, type, position, radius, color, relatedIds}` and the existing `camera` option.
- Produces: `getVisibleLimit(width: number): number`, ambient records with `type` and `depthFactor`, and unchanged public methods `setPlanets`, `setActivePlanet`, `update`, `resize`, and `dispose`.

- [ ] **Step 1: Add failing connection-layer contract assertions**

Append to the connection-layer fragment tuple:

```python
        "mobileMaxVisible: 14",
        "wideMaxVisible: 18",
        "wideBreakpoint: 600",
        "depthMin: 0.52",
        "getVisibleLimit",
        "getDepthFactor",
        "typeOpacity",
```

- [ ] **Step 2: Run the contract test and verify failure**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
```

Expected: FAIL on `mobileMaxVisible: 14`.

- [ ] **Step 3: Replace the idle visual configuration**

Use this idle configuration:

```javascript
idle: {
  mobileMaxVisible: 14,
  wideMaxVisible: 18,
  wideBreakpoint: 600,
  width: 1.7,
  opacity: 0.72,
  glowWidth: 8,
  glowOpacity: 0.2,
  color: '#E3DEFF',
  glowColor: '#A995FF',
  tubeRadius: 0.018,
  breathDuration: 5.2,
  breathMin: 0.92,
  breathMax: 1.08,
  activeDim: 0.15,
  flowIntervalMin: 4.8,
  flowIntervalMax: 7.5,
  flowLength: 0.09,
  flowDuration: 1.8,
  flowOpacity: 0.68,
  coreSpokes: 4,
  depthMin: 0.52,
  typeOpacity: { related: 1, core: 0.9, near: 0.62 },
},
```

Set active width/opacity to `4.2/1`, glow width/opacity to `18/0.38`, inner width/opacity to `1.35/1`, and `activeDim` to `0.15` through the idle setting above. Set secondary width/opacity to `2/0.72` and glow width/opacity to `8/0.25`.

- [ ] **Step 4: Add responsive limit and camera-depth helpers**

Add these module helpers:

```javascript
function getVisibleLimit(width) {
  var idle = CONNECTION_CONFIG.idle
  return width >= idle.wideBreakpoint ? idle.wideMaxVisible : idle.mobileMaxVisible
}

function getDepthFactor(a, b, camera) {
  if (!camera || !a || !b) return 1
  var midZ = (a.position.clone().project(camera).z + b.position.clone().project(camera).z) * 0.5
  var normalized = clamp((1 - midZ) * 0.5, 0, 1)
  return lerp(CONNECTION_CONFIG.idle.depthMin, 1, normalized)
}
```

In `_rebuildAmbient`, replace the fixed `maxVisible` cap with:

```javascript
var pickN = Math.min(getVisibleLimit(this.resW), total)
```

For every ambient record, retain `type`, calculate `depthFactor`, and set base opacity as:

```javascript
var typeOpacity = idle.typeOpacity[conn.type] || 1
var depthFactor = getDepthFactor(a, b, this.camera)
var baseOpacity = idle.opacity * typeOpacity * depthFactor
```

Use `baseOpacity` for the tube and line, and `idle.glowOpacity * typeOpacity * depthFactor` for glow. Store `{ type, depthFactor, baseOpacity }` on the ambient record so `update` can breathe from stable values rather than compounding opacity.

- [ ] **Step 5: Make ambient animation selection-aware and reduced-motion safe**

In `update`, derive the ambient multiplier from `_fadeAmbient` and set each material opacity from its stored base value. Apply breathing only when `!this.reduceMotion`; do not start or update idle flow when reduced motion is enabled. Preserve the current active-flow draw animation only outside reduced-motion mode; when reduced motion is enabled, immediately show the full active path.

- [ ] **Step 6: Run the contract test and verify it passes**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
```

Expected: `1 passed`.

---

### Task 3: Wire the count subtitle and strengthen selected-scene hierarchy

**Files:**
- Modify: `tests/test_h5_static_contract.py:100-155`
- Modify: `frontend/static/js/memory-nebula.js:35-122,631-780,1013-1055`
- Modify: `frontend/static/js/memory-connection-layer.js:75-115,833-1010`

**Interfaces:**
- Consumes: `#nebula-count-subtitle`, `MemoryConnectionLayer.getRelatedIds`, and active endpoint/ring rendering.
- Produces: `updateMemoryCount(total: number): void`; selected planet scale `1.2`, unrelated opacity `0.58`, unrelated scale `0.92`, and an active endpoint ring.

- [ ] **Step 1: Add failing behavior-contract assertions**

Add these memory-nebula fragments:

```python
        "nebula-count-subtitle",
        "updateMemoryCount",
        "颗记忆星体",
        "DIM_OPACITY = 0.58",
        "DIM_SCALE = 0.92",
```

Add these connection fragments:

```python
        "ringOpacity: 0.72",
        "ringEndScale: 1.34",
```

- [ ] **Step 2: Run the contract test and verify failure**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
```

Expected: FAIL on the new subtitle/update fragments.

- [ ] **Step 3: Implement the dynamic count subtitle**

Cache the subtitle element:

```javascript
var countSubtitleEl = document.getElementById('nebula-count-subtitle')
```

Replace the count updater with:

```javascript
function updateMemoryCount(total) {
  memoryCount = Math.max(0, Number(total) || 0)
  if (countNumEl) countNumEl.textContent = String(memoryCount)
  if (countSubtitleEl) countSubtitleEl.textContent = memoryCount + ' 颗记忆星体'
}
```

Call `updateMemoryCount(raw.length)` after `buildMemoryNodes(raw)`.

- [ ] **Step 4: Strengthen planet selection hierarchy**

Define:

```javascript
var DIM_OPACITY = 0.58
var DIM_SCALE = 0.92
var RELATED_OPACITY = 0.92
var SELECTED_BRIGHTNESS = 1.24
```

In `applySelectionHighlight`, keep selected scale at `baseScale * 1.2`, related planets at full scale and `RELATED_OPACITY`, and unrelated planets at `baseScale * DIM_SCALE` and `DIM_OPACITY`. Reset all material colors and scales when selection closes.

- [ ] **Step 5: Strengthen the active endpoint/ring without adding a new scene subsystem**

Update endpoint configuration to:

```javascript
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
```

Reuse the existing endpoint and ring sprites so the selected planet receives a persistent glow plus a one-shot outer-ring arrival cue. In reduced-motion mode, skip the expanding ring and retain the static endpoint glow.

- [ ] **Step 6: Run the contract test and verify it passes**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
```

Expected: `1 passed`.

---

### Task 4: Full verification and visual QA

**Files:**
- Verify: `frontend/pages/memory.html`
- Verify: `frontend/static/js/memory-nebula.js`
- Verify: `frontend/static/js/memory-connection-layer.js`
- Verify: `tests/test_h5_static_contract.py`

**Interfaces:**
- Consumes: completed Tasks 1–3.
- Produces: a verified mobile visual implementation with no static-contract regression or browser-console error.

- [ ] **Step 1: Run focused and full static tests**

Run:

```bash
pytest tests/test_h5_static_contract.py::test_memory_html_nebula_surface_contract -q
pytest tests/test_h5_static_contract.py -q
```

Expected: focused test passes; full file passes with no failures.

- [ ] **Step 2: Check JavaScript syntax and diff hygiene**

Run:

```bash
node --check frontend/static/js/memory-connection-layer.js
node --check frontend/static/js/memory-nebula.js
git diff --check -- frontend/pages/memory.html frontend/static/js/memory-nebula.js frontend/static/js/memory-connection-layer.js tests/test_h5_static_contract.py
```

Expected: all commands exit with status 0 and print no errors.

- [ ] **Step 3: Perform browser visual QA at mobile sizes**

Use the local page at `http://localhost:8000/pages/memory.html` with authenticated test state. Check 390×844 and 430×932 viewports for:

```text
default: 14 or fewer readable lines, near lines clearer than distant lines
selected: gold-to-category main path, two or fewer secondary paths, unrelated lines at 15%
header: two-line centered title, circular glass controls, no planet obstruction
footer: glass hint, recenter only after orbit displacement
sheet: bottom controls hidden while open, restored on close
reduced motion: no breathing, flow, or expanding ring
```

Expected: every state matches the checklist and the browser console has no new errors.

- [ ] **Step 4: Review only scoped changes**

Run:

```bash
git diff -- frontend/pages/memory.html frontend/static/js/memory-nebula.js frontend/static/js/memory-connection-layer.js tests/test_h5_static_contract.py
```

Expected: diff contains only the approved memory-nebula presentation changes and their tests.


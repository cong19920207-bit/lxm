(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HomeSceneCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const CONFIG = {
    characterScale: 0.82,
    layout: {
      characterRightPercent: -1.2,
      characterBottomPercent: -1.5
    },
    parallax: {
      backgroundX: -6.2,
      backgroundY: -5.0,
      characterX: 3.2,
      characterY: 2.4
    },
    orientation: {
      xRange: 25,
      yRange: 35,
      defaultBeta: 45
    },
    motion: {
      idleTranslateX: 0.62,
      idleTranslateY: 0.42,
      idleRotateDeg: 0.26,
      idleScale: 1.006
    },
    twinkle: {
      targetCount: 96,
      minPeakAlpha: 0.44,
      maxPeakAlpha: 1.0,
      minRadius: 0.8,
      maxRadius: 2.45,
      flareChance: 0.54
    },
    hair: {
      front: { travelPx: 2.2, rotateDeg: 0.45, stiffness: 0.115, damping: 0.76, phase: 0.1 },
      side:  { travelPx: 4.2, rotateDeg: 0.82, stiffness: 0.078, damping: 0.82, phase: 1.7 },
      back:  { travelPx: 6.2, rotateDeg: 1.15, stiffness: 0.048, damping: 0.87, phase: 3.0 }
    }
  };

  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const rand = (rng, min, max) => min + rng() * (max - min);

  function normalizeOrientation(gamma, beta, baseline) {
    const base = baseline || { gamma: 0, beta: CONFIG.orientation.defaultBeta };
    const dx = (Number(gamma) - Number(base.gamma || 0)) / CONFIG.orientation.xRange;
    const dy = (Number(beta) - Number(base.beta ?? CONFIG.orientation.defaultBeta)) / CONFIG.orientation.yRange;
    return {
      x: Number(clamp(dx, -1, 1).toFixed(3)),
      y: Number(clamp(dy, -1, 1).toFixed(3))
    };
  }

  function createBlinkPlan(rng = Math.random) {
    const closeMs = Math.round(rand(rng, 58, 92));
    const holdMs = Math.round(rand(rng, 16, 42));
    const openMs = Math.round(rand(rng, 92, 162));
    const nextDelayMs = Math.round(rand(rng, 3100, 6700));
    const doubleBlink = rng() < 0.12;
    const doubleGapMs = Math.round(rand(rng, 170, 320));
    return {
      closeMs,
      holdMs,
      openMs,
      totalMs: closeMs + holdMs + openMs,
      nextDelayMs,
      doubleBlink,
      doubleGapMs
    };
  }

  function createIdleDelay(rng = Math.random) {
    return Math.round(rand(rng, 15000, 33000));
  }

  function createAcknowledgePlan(rng = Math.random) {
    // Character sits on the right side of the scene. Negative X leans slightly
    // toward the viewer / scene centre instead of randomly recoiling away.
    return {
      durationMs: Math.round(rand(rng, 1900, 2350)),
      translateXPercent: Number((-rand(rng, 0.34, 0.54)).toFixed(3)),
      translateYPercent: Number((-rand(rng, 0.58, 0.82)).toFixed(3)),
      rotateDeg: Number((-rand(rng, 0.12, 0.23)).toFixed(3)),
      scale: Number(rand(rng, 1.012, 1.018).toFixed(4)),
      holdRatio: Number(rand(rng, 0.20, 0.30).toFixed(3))
    };
  }

  function createTwinklePlan(rng = Math.random) {
    const t = CONFIG.twinkle;
    return {
      durationMs: Math.round(rand(rng, 650, 1900)),
      pauseMs: Math.round(rand(rng, 420, 3600)),
      peakAlpha: Number(rand(rng, t.minPeakAlpha, t.maxPeakAlpha).toFixed(3)),
      radius: Number(rand(rng, t.minRadius, t.maxRadius).toFixed(3)),
      flare: rng() < t.flareChance
    };
  }

  return {
    CONFIG,
    frameDelta: (now, last) => last == null ? 0 : clamp(now - last, 0, 40),
    stepSpring: (value, velocity, target, stiffness, damping, dt) => {
      velocity = (velocity + (target - value) * stiffness * dt) * Math.pow(damping, dt)
      return [value + velocity * dt, velocity]
    },
    rotateInput: (x,y,angle) => {
      const radians = angle * Math.PI / 180
      return {x: clamp(x*Math.cos(radians)+y*Math.sin(radians),-1,1), y: clamp(-x*Math.sin(radians)+y*Math.cos(radians),-1,1)}
    },
    clamp,
    lerp,
    normalizeOrientation,
    createBlinkPlan,
    createIdleDelay,
    createAcknowledgePlan,
    createTwinklePlan
  };
});

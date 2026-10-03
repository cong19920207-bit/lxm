/* Browser-local homepage motion preference shared by home and settings. */
(function () {
  'use strict'
  const motionKey = 'lxm_home_motion_enabled'
  const sessionKey = 'lxm_home_motion_session'
  let current = null, motionPageChoice = null

  function storage(kind, operation, key, value) {
    try { return { ok: true, value: window[kind][operation](key, value) } }
    catch (_) { return { ok: false, value: null } }
  }

  function readMotion(refreshSaved = false) {
    if (refreshSaved) motionPageChoice = null
    if (motionPageChoice) return { ...motionPageChoice }
    const temporary = storage('sessionStorage', 'getItem', sessionKey)
    const saved = storage('localStorage', 'getItem', motionKey)
    if (temporary.value === '0' || temporary.value === '1') {
      current = { enabled: temporary.value === '1', note: '选择仅本次生效，暂时无法保存。' }
    } else if (saved.ok) {
      current = { enabled: saved.value !== '0', note: '' }
    } else if (!current) {
      current = { enabled: true, note: '无法读取已保存的选择，本次默认开启。' }
    }
    return { ...current }
  }

  function writeMotion(enabled) {
    enabled = !!enabled
    const value = enabled ? '1' : '0'
    const saved = storage('localStorage', 'setItem', motionKey, value)
    const temporary = saved.ok ? storage('sessionStorage', 'removeItem', sessionKey)
      : storage('sessionStorage', 'setItem', sessionKey, value)
    current = { enabled, note: saved.ok ? '' : temporary.ok ? '选择仅本次生效，暂时无法保存。'
      : '选择仅在本页生效，暂时无法保存；离开页面后可能恢复原设置。' }
    motionPageChoice = !saved.ok && !temporary.ok ? { ...current } : null
    return { ...current }
  }

  const tiltKey = 'lxm_home_tilt_enabled'
  const tiltPermissionKey = 'lxm_home_tilt_permission'
  const tiltStatusKey = 'lxm_home_tilt_status'
  const tiltSessionNote = '倾斜已关闭，暂时无法保存选择。'
  const tiltPageNote = '倾斜已在本页关闭，暂时无法保存；离开页面后可能恢复原设置。'
  let tiltClosed = null

  function readTiltStatus() {
    try {
      const value = JSON.parse(storage('sessionStorage', 'getItem', tiltStatusKey).value || '{}')
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
    } catch (_) { return {} }
  }

  function saveTiltStatus(status) {
    return storage('sessionStorage', 'setItem', tiltStatusKey, JSON.stringify(status))
  }

  function readTilt() {
    const saved = storage('sessionStorage', 'getItem', tiltKey)
    const permission = storage('sessionStorage', 'getItem', tiltPermissionKey)
    const status = readTiltStatus()
    // A later explicit saved choice supersedes a page-only closure after back.
    if (tiltClosed && status.choiceId && status.choiceId !== tiltClosed.choiceId) tiltClosed = null
    const closed = tiltClosed || (status.enabledOverride === false && saved.value !== '0')
    const pageOnly = !!tiltClosed && !tiltClosed.sessionSaved
    return { enabled: !closed && saved.value === '1', permissionGranted: permission.value === 'granted',
      state: status.state || 'off', message: status.message || '',
      note: closed ? pageOnly ? tiltPageNote : status.storageNote || tiltSessionNote
        : saved.ok ? '' : '无法读取倾斜选择，本次暂不开启。', pageOnly }
  }

  function retainTiltClosed() {
    const status = readTiltStatus()
    tiltClosed = { choiceId: status.choiceId || '', sessionSaved: false }
    tiltClosed.sessionSaved = saveTiltStatus({ ...status, enabledOverride: false, storageNote: tiltSessionNote }).ok
    return readTilt()
  }

  function writeTilt(enabled, permissionGranted = false) {
    const previous = readTilt()
    if (enabled && permissionGranted && !storage('sessionStorage', 'setItem', tiltPermissionKey, 'granted').ok) {
      return { ...previous, note: '暂时无法保存倾斜选择，请稍后重试。' }
    }
    if (!storage('sessionStorage', 'setItem', tiltKey, enabled ? '1' : '0').ok) {
      if (!enabled) return retainTiltClosed()
      return { ...previous, note: '暂时无法保存倾斜选择，请稍后重试。' }
    }
    const status = readTiltStatus()
    delete status.enabledOverride
    delete status.storageNote
    if (enabled) status.choiceId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2)
    const updated = saveTiltStatus(status)
    if (enabled && !updated.ok) {
      // Keep the old closure if its handoff cannot be replaced safely.
      storage('sessionStorage', 'setItem', tiltKey, '0')
      return retainTiltClosed()
    }
    tiltClosed = null
    return { ...readTilt(), enabled: !!enabled }
  }

  function reportTilt(state, message) {
    readTilt()
    const status = { ...readTiltStatus(), state, message }
    if (tiltClosed) {
      status.enabledOverride = false
      status.storageNote = tiltSessionNote
    }
    const saved = saveTiltStatus(status)
    if (tiltClosed && saved.ok) tiltClosed.sessionSaved = true
  }

  window.HomePreferences = { motionKey, sessionKey, readMotion, writeMotion,
    tiltKey, tiltStatusKey, readTilt, writeTilt, reportTilt }
})()

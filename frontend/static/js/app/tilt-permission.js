// Shared by the opening and Settings. The native request is made synchronously;
// each caller owns cancellation, deadlines and applying its result.
export function tiltUnavailable(preferences, host = window) {
  return preferences.readTilt().state === 'legacy' ? '旧背景模式不支持倾斜' :
    !preferences.readMotion().enabled ? '请先开启主页动效' :
    host.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? '系统已减少动态，倾斜暂不可用' :
    !host.isSecureContext ? '当前页面连接不支持倾斜' :
    typeof host.DeviceOrientationEvent === 'undefined' ? '当前浏览器不支持倾斜' : '';
}

export function requestTiltPermission(host = window) {
  try {
    const Orientation = host.DeviceOrientationEvent;
    return Promise.resolve(typeof Orientation.requestPermission === 'function' ? Orientation.requestPermission() : 'granted');
  } catch (error) { return Promise.reject(error); }
}

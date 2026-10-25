import { createPageTimers } from '../app/page-timers.js';
import { PageScope } from '../app/page-context.js';

export async function mount(context) {
  const {root,services}=context,byId=id=>root.querySelector('#'+id);
  const {setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame}=createPageTimers(context);
  const run=promise=>Promise.resolve(promise).catch(error=>{if(context.valid()&&!['AbortError','StaleRequestError'].includes(error.name))services.ui.toast('暂时无法加载，请稍后重试','error')});
  const listen=(target,type,fn,options)=>context.scope.listen(target,type,(...args)=>{const result=fn(...args);if(result?.then)run(result)},options);
  const routeCurrent=()=>context.router.current?.context.routeEpoch===context.routeEpoch;
  const request=(method,path,data,options={})=>services.auth.request(method,path,data,{authPolicy:'silent-visitor',routeEpoch:context.routeEpoch,routeCurrent,isCurrent:context.valid,signal:context.signal,...options});
  const isFeedAuthenticated=()=>context.valid()&&services.auth.snapshot().authenticated;
  const showToast=(message,type)=>{if(context.valid())services.ui.toast(message,type)};
  const escapeHtml=value=>{const node=document.createElement('div');node.textContent=value==null?'':String(value);return node.innerHTML};
  await context.scope.adopt(services.resources.style('css/bgm.css'),release=>release());
  for(const name of ['bgm-page','bgm-record','bgm-bubble']){await services.shared.script('js/'+name+'.js');if(!context.valid())return{unmount(){}}}
  const audioPage=services.audio.attachPage(context,'content'),bubble=BgmBubble.mount(audioPage);if(bubble)context.cleanup(()=>bubble.destroy());
  const posts=new Map(),expanded=new Set((context.state?.expandedIds||[]).map(String)),reportedComments=new Set(),reportedPosts=new Set(),dwell=new Map(),likePending=new Set();
  const loadWaiters=new Set();context.cleanup(()=>{for(const resolve of loadWaiters)resolve();loadWaiters.clear()});
  let loading=false,noMore=false,nextCursor=null,loadedPages=0,lastLoadAt=0,restoring=true,interacted=false,anchorCommentId=null,enterStarted=false;
  let closeActivePreview=null,commentingPostId=null,commentingReplyToLxm=false,commentSending=false,commentGeneration=0;
  let feedEventSource=null,sseRetryTimer=null,sseRetryDelay=1000,pendingNewCount=0,sentinelEnabled=false,sentinelVisible=false,paginationTimer=null;
  const entryPageCount=Math.max(1,Number(context.state?.cursor?.pages)||1);
    /* 相对时间（UI 4.3 微信同款）：刚刚 / X分钟前 / X小时前 / 昨天 / X天前
       scheduled_publish_time 为北京墙钟 naive，按字符串解析，日界 Asia/Shanghai */
    function parseWallClock(iso) {
      if (!iso) return null
      var m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/)
      if (!m) return null
      return { y: +m[1], mo: +m[2], d: +m[3], h: +m[4], mi: +m[5] }
    }

    function beijingNowParts() {
      var parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false
      }).formatToParts(new Date())
      var get = function (t) {
        for (var i = 0; i < parts.length; i++) {
          if (parts[i].type === t) return parts[i].value
        }
        return '0'
      }
      return { y: +get('year'), mo: +get('month'), d: +get('day'), h: +get('hour'), mi: +get('minute') }
    }

    function formatFeedTime(iso) {
      var d = parseWallClock(iso)
      if (!d) return ''
      var now = beijingNowParts()
      var dayDiff = Math.floor(
        (Date.UTC(now.y, now.mo - 1, now.d) - Date.UTC(d.y, d.mo - 1, d.d)) / 86400000
      )
      if (dayDiff >= 2) return dayDiff + '天前'
      if (dayDiff === 1) return '昨天'
      var mins = (now.h * 60 + now.mi) - (d.h * 60 + d.mi)
      if (dayDiff < 0 || mins < 1) return '刚刚'
      if (mins < 60) return mins + '分钟前'
      return Math.floor(mins / 60) + '小时前'
    }

    /** 左列城市行（弱化；无城市则空） */
    function buildCityHtml(city) {
      var name = (city || '').trim()
      if (!name) return ''
      return '<div class="date-city">' +
        '<svg class="loc-ico" viewBox="0 0 12 12" aria-hidden="true">' +
        '<path fill="currentColor" d="M6 1.2c-1.9 0-3.4 1.5-3.4 3.3 0 2.5 3.4 6.3 3.4 6.3s3.4-3.8 3.4-6.3C9.4 2.7 7.9 1.2 6 1.2zm0 4.5a1.2 1.2 0 1 1 0-2.4 1.2 1.2 0 0 1 0 2.4z"/>' +
        '</svg><span>' + escapeHtml(name) + '</span></div>'
    }

    /** 墙钟日期键 YYYY-MM-DD，用于同日左列合并 */
    function wallDateKey(iso) {
      var d = parseWallClock(iso)
      if (!d) return ''
      return d.y + '-' + String(d.mo).padStart(2, '0') + '-' + String(d.d).padStart(2, '0')
    }

    /** 左列相对日标签：今天 / 昨天；更早不展示 */
    function formatDayLabel(iso) {
      var d = parseWallClock(iso)
      if (!d) return ''
      var now = beijingNowParts()
      var dayDiff = Math.floor(
        (Date.UTC(now.y, now.mo - 1, now.d) - Date.UTC(d.y, d.mo - 1, d.d)) / 86400000
      )
      if (dayDiff === 0) return '今天'
      if (dayDiff === 1) return '昨天'
      return ''
    }

    /**
     * 左列：大号日 + 月 + 今天/昨天 + 城市
     * showDate=false 时同日后续条留空，仅保留时间节点
     */
    function buildDateColHtml(iso, city, showDate) {
      if (!showDate) {
        return '<div class="date-col date-col--empty" aria-hidden="true"></div>'
      }
      var cityHtml = buildCityHtml(city)
      var d = parseWallClock(iso)
      if (!d) {
        return '<div class="date-col">' + cityHtml + '</div>'
      }
      var dayLabel = formatDayLabel(iso)
      var dayLabelHtml = dayLabel
        ? '<div class="date-rel">' + escapeHtml(dayLabel) + '</div>'
        : ''
      return '<div class="date-col">' +
        '<div class="date-day">' + d.d + '</div>' +
        '<div class="date-month">' + d.mo + '月</div>' +
        dayLabelHtml +
        cityHtml +
        '</div>'
    }

    /* 互动图标：对齐 Figma「林小梦-朋友圈互动图标」v2 */
    var ICON_HEART_OUTLINE =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M12 21.35 L10.55 20.03 C5.4 15.36 2 12.28 2 8.5 C2 5.42 4.42 3 7.5 3 C9.24 3 10.91 3.81 12 5.09 C13.09 3.81 14.76 3 16.5 3 C19.58 3 22 5.42 22 8.5 C22 12.28 18.6 15.36 13.45 20.04 L12 21.35 Z"/></svg>'
    var ICON_HEART_FILL =
      '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
      '<path d="M12 21.35 L10.55 20.03 C5.4 15.36 2 12.28 2 8.5 C2 5.42 4.42 3 7.5 3 C9.24 3 10.91 3.81 12 5.09 C13.09 3.81 14.76 3 16.5 3 C19.58 3 22 5.42 22 8.5 C22 12.28 18.6 15.36 13.45 20.04 L12 21.35 Z"/></svg>'
    var ICON_COMMENT =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M5 5 L19 5 C20.1 5 21 5.9 21 7 L21 13 C21 14.1 20.1 15 19 15 L10 15 L6 19 L6 15 L5 15 C3.9 15 3 14.1 3 13 L3 7 C3 5.9 3.9 5 5 5 Z"/></svg>'

    function heartIconHtml(liked) {
      return liked ? ICON_HEART_FILL : ICON_HEART_OUTLINE
    }

    function setLikeVisual(act, liked) {
      if (!act) return
      var icoEl = act.querySelector('.ico')
      if (icoEl) icoEl.innerHTML = heartIconHtml(liked)
      act.classList.toggle('liked', !!liked)
    }

    /* #话题 单井号着色：从 # 起至空格/标点前；成对收尾 # 一并纳入着色 */
    function renderTextWithHashtags(text) {
      var safe = escapeHtml(text)
      // 终止符：空白、常见中英文标点、括号；可选吞掉成对收尾 #
      return safe.replace(
        /#([^\s#，。！？、；：…,.!?;:()（）\[\]【】<>《》「」]{1,30})(#?)/g,
        '<span class="hashtag">#$1$2</span>'
      )
    }

    /** 长文截断：展开/收起在 meta 行右侧；时间始终在左侧 */
    function setupTextExpand(contentCol) {
      if (!contentCol) return
      var textEl = contentCol.querySelector('.feed-text')
      var btn = contentCol.querySelector('.feed-expand')
      if (!textEl || !btn) return
      textEl.classList.add('collapsed')
      btn.classList.remove('is-visible')
      requestAnimationFrame(function () {
        var needs = textEl.scrollHeight > textEl.clientHeight + 1
        if (!needs) {
          textEl.classList.remove('collapsed')
          btn.classList.remove('is-visible')
          btn.style.display = 'none'
          return
        }
        btn.style.display = ''
        btn.classList.add('is-visible')
        const opened=expanded.has(String(contentCol.parentElement.dataset.id));textEl.classList.toggle('collapsed',!opened);btn.textContent=opened?'收起':'展开'

      })
    }

    /* ===== 列表渲染 ===== */
    function buildImagesHtml(urls) {
      if (!urls || urls.length === 0) return ''
      var cls = urls.length === 1 ? 'count-1' : (urls.length === 2 ? 'count-2' : 'count-3plus')
      var html = '<div class="feed-images ' + cls + '">'
      urls.forEach(function (u, i) {
        html += '<div class="thumb"><img loading="lazy" tabindex="0" role="button" alt="动态图片" src="' + escapeHtml(u) +
          '" data-idx="' + i + '"></div>'
      })
      html += '</div>'
      return html
    }

    function buildCommentsHtml(comments) {
      if (!isFeedAuthenticated()) return ''
      if (!comments || comments.length === 0) return ''
      var html = '<div class="feed-comments">'
      comments.forEach(function (c) {
        // 仅 reply_to_lxm 标记的评论显示「我回复 林小梦」；普通发评仍为「我」
        var authorLabel = c.reply_to_lxm ? '我回复 林小梦：' : '我：'
        html += '<div class="comment-row" data-comment-id="' + c.id + '">' +
          '<span class="comment-author">' + authorLabel + '</span>' +
          '<span class="comment-content">' + escapeHtml(c.content) + '</span></div>'
        if (c.lxm_reply) {
          html += '<div class="comment-reply" data-comment-id="' + c.id + '">' +
            '<span class="comment-author">林小梦回复 我：</span>' +
            '<span class="comment-content lxm-reply-text">' + escapeHtml(c.lxm_reply) + '</span></div>'
        }
      })
      html += '</div>'
      return html
    }

    function buildFeedItem(post, showDate) {
      var item = document.createElement('div')
      item.className = 'feed-item'
      item.dataset.id = post.id
      item.dataset.postId = post.id
      item.dataset.liked = isFeedAuthenticated() && post.user_liked ? '1' : '0'
      item.dataset.likes = post.display_likes || 0
      item.dataset.dateKey = wallDateKey(post.scheduled_publish_time)
      // 展示评论数对齐点赞：display_comments = base×倍率 + 真实可见条数（后端组装）
      var commentCount = (post.display_comments != null)
        ? post.display_comments
        : ((post.comments && post.comments.length) ? post.comments.length : 0)
      item.dataset.comments = commentCount

      item.innerHTML =
        '<span class="timeline-node" aria-hidden="true"></span>' +
        buildDateColHtml(post.scheduled_publish_time, post.city, showDate !== false) +
        '<div class="content-col">' +
          '<div class="feed-text-block">' +
            '<div class="feed-text">' + renderTextWithHashtags(post.content_text || '') + '</div>' +
          '</div>' +
          '<div class="feed-meta-row">' +
            '<span class="feed-time">' + escapeHtml(formatFeedTime(post.scheduled_publish_time)) + '</span>' +
            '<button type="button" class="feed-expand">展开</button>' +
          '</div>' +
          buildImagesHtml(post.image_urls) +
          '<div class="feed-actions">' +
            '<div class="act like-act' + (isFeedAuthenticated() && post.user_liked ? ' liked' : '') + '" role="button" tabindex="0" aria-label="点赞">' +
              '<span class="ico">' + heartIconHtml(!!(isFeedAuthenticated() && post.user_liked)) + '</span>' +
              '<span class="like-count">' + (post.display_likes || 0) + '</span></div>' +
            '<div class="act comment-act" role="button" tabindex="0" aria-label="评论">' +
              '<span class="ico">' + ICON_COMMENT + '</span>' +
              '<span class="comment-count">' + commentCount + '</span></div>' +
          '</div>' +
          buildCommentsHtml(post.comments) +
        '</div>'

      setupTextExpand(item.querySelector('.content-col'))

      return item
    }

    function showState(id) {
      byId('state-empty').style.display = id === 'empty' ? 'block' : 'none'
      byId('state-error').style.display = id === 'error' ? 'block' : 'none'
    }

    function renderSkeleton(show) {
      var sk = byId('feed-skeleton')
      if (!show) { sk.innerHTML = ''; return }
      var one = '<div class="skeleton-card"><div class="sk-date"></div>' +
        '<div class="sk-body"><div class="sk-line"></div><div class="sk-line w60"></div><div class="sk-img"></div></div></div>'
      sk.innerHTML = one + one + one
    }

    /** 进页全屏 loading：渐进透明度 + 硬超时防卡死（对齐首页 loader） */
    var BOOT_MIN_MS = 700
    var BOOT_HARD_MS = 8000
    var BOOT_IMG_MAX = 6
    var BOOT_IMG_TIMEOUT_MS = 2500
    var BOOT_ALPHA_START = 0.88
    var BOOT_ALPHA_END = 0.12
    var BOOT_BLUR_START = 12
    var BOOT_EXIT_MS = 300

    var bootLoadingPending = true
    var bootListDone = false
    var bootImgRatio = 0
    var bootStartAt = Date.now()
    var bootHardTimer = null
    var bootProgressTimer = null
    var bootDismissed = false

    function clamp01(n) {
      if (n < 0) return 0
      if (n > 1) return 1
      return n
    }

    function updateFeedBootVisual(progress) {
      var el = byId('feed-boot-loading')
      if (!el) return
      var p = clamp01(progress)
      var alpha = BOOT_ALPHA_START + (BOOT_ALPHA_END - BOOT_ALPHA_START) * p
      var blur = BOOT_BLUR_START * (1 - p)
      el.style.setProperty('--feed-boot-alpha', String(alpha))
      el.style.setProperty('--feed-boot-blur', blur.toFixed(1) + 'px')
    }

    function computeBootProgress() {
      var elapsed = Date.now() - bootStartAt
      var timeRatio = Math.min(elapsed / BOOT_MIN_MS, 1)
      // 列表 40% + 首屏图 50% + 时间门闩 10%
      var asset = (bootListDone ? 0.4 : 0) + bootImgRatio * 0.5
      var target = Math.min(asset + timeRatio * 0.1, 1)
      if (bootListDone && bootImgRatio >= 1 && elapsed >= BOOT_MIN_MS) target = 1
      return target
    }

    function clearBootTimers() {
      if (bootHardTimer) { clearTimeout(bootHardTimer); bootHardTimer = null }
      if (bootProgressTimer) { clearInterval(bootProgressTimer); bootProgressTimer = null }
    }

    function dismissFeedBootLoading() {
      if (bootDismissed) return
      bootDismissed = true
      bootLoadingPending = false
      clearBootTimers()
      updateFeedBootVisual(1)
      var el = byId('feed-boot-loading')
      if (!el) return
      el.classList.add('is-exiting')
      setTimeout(function () {
        el.classList.remove('is-visible')
        el.classList.remove('is-exiting')
      }, BOOT_EXIT_MS)
    }

    function startFeedBootProgress() {
      bootStartAt = Date.now()
      bootListDone = false
      bootImgRatio = 0
      bootDismissed = false
      bootLoadingPending = true
      updateFeedBootVisual(0)
      var el = byId('feed-boot-loading')
      if (el) {
        el.classList.remove('is-exiting')
        el.classList.add('is-visible')
      }
      // 硬超时：到点强制关遮罩，避免永久卡住
      bootHardTimer = setTimeout(function () {
        dismissFeedBootLoading()
      }, BOOT_HARD_MS)
      bootProgressTimer = setInterval(function () {
        if (bootDismissed) return
        updateFeedBootVisual(computeBootProgress())
      }, 50)
    }

    /**
     * 等待首屏图片就绪（最多 maxCount 张，超时兜底）。
     * 强制 eager；绑监听后再读 complete，避免竞态；支持 decode()。
     * onProgress(ratio 0~1) 供渐进透明度使用。
     */
    function waitFirstScreenImages(rootEl, maxCount, timeoutMs, onProgress) {
      maxCount = maxCount == null ? BOOT_IMG_MAX : maxCount
      timeoutMs = timeoutMs == null ? BOOT_IMG_TIMEOUT_MS : timeoutMs
      var scope = rootEl || byId('feed-list') || document
      var all = scope.querySelectorAll('.feed-images img')
      var imgs = []
      for (var i = 0; i < all.length && imgs.length < maxCount; i++) {
        try { all[i].loading = 'eager' } catch (e) { /* ignore */ }
        imgs.push(all[i])
      }
      if (!imgs.length) {
        if (onProgress) onProgress(1)
        return Promise.resolve()
      }
      return new Promise(function (resolve) {
        var total = imgs.length
        var settled = 0
        var done = false
        var seen = {}
        function report() {
          if (context.valid() && onProgress) onProgress(clamp01(settled / total))
        }
        function finish() {
          if (done) return
          done = true
          clearTimeout(timer)
          for (var pair of handlers) { pair[0].removeEventListener('load',pair[1]); pair[0].removeEventListener('error',pair[1]) }
          release()
          settled = total
          report()
          resolve()
        }
        var handlers = new Map()
        var release = context.cleanup(finish)
        var timer = setTimeout(finish, timeoutMs)
        function markDone(img, handler) {
          var key = imgs.indexOf(img)
          if (key < 0 || seen[key]) return
          seen[key] = true
          if (handler) {
            img.removeEventListener('load', handler)
            img.removeEventListener('error', handler)
          }
          if (done) return
          settled += 1
          report()
          if (settled >= total) {
            clearTimeout(timer)
            finish()
          }
        }
        imgs.forEach(function (img) {
          function handler() { markDone(img, handler) }
          handlers.set(img,handler)
          img.addEventListener('load', handler)
          img.addEventListener('error', handler)
          // 绑完再读 complete，避免「已完成却漏监听」
          if (img.complete) {
            markDone(img, handler)
            return
          }
          if (typeof img.decode === 'function') {
            img.decode().then(function () { markDone(img, handler) }).catch(function () { /* load/error 兜底 */ })
          }
        })
        report()
      })
    }

    async function hideBootLoadingAfterReady() {
      if (!bootLoadingPending || bootDismissed) return
      try {
        await waitFirstScreenImages(
          byId('feed-list'),
          BOOT_IMG_MAX,
          BOOT_IMG_TIMEOUT_MS,
          function (ratio) {
            bootImgRatio = ratio
            updateFeedBootVisual(computeBootProgress())
          }
        )
      } catch (e) {
        bootImgRatio = 1
      }
      // 等最少展示时长，再退场
      var remain = BOOT_MIN_MS - (Date.now() - bootStartAt)
      if (remain > 0) {
        await new Promise(function (r) { setTimeout(r, remain) })
      }
      updateFeedBootVisual(1)
      dismissFeedBootLoading()
    }

    /** 列表已出且 boot 未关时，统一补走退场（含哨兵抢跑兜底） */
    async function finishBootAfterListReady() {
      if (!bootLoadingPending || bootDismissed) return
      bootListDone = true
      updateFeedBootVisual(computeBootProgress())
      var hasImg = root.querySelectorAll('#feed-list .feed-images img').length > 0
      if (!hasImg) bootImgRatio = 1
      try {
        await hideBootLoadingAfterReady()
      } catch (e) {
        dismissFeedBootLoading()
      }
    }

    /* ===== 全屏预览（STEP-023 / UI 5.2 / TD-001） ===== */
    function openPreview(urls, startIdx) {
      if (!urls || urls.length === 0) return
      closeActivePreview?.()
      const previewScope = new PageScope({current:context.valid})
      const listen = (target,type,fn,options)=>previewScope.listen(target,type,fn,options)
      var idx = startIdx || 0
      var scale = 1, startDist = 0, baseScale = 1
      var startX = 0, moved = false, pinching = false

      var overlay = document.createElement('div')
      overlay.className = 'preview-overlay'
      var img = document.createElement('img')
      img.src = urls[idx]
      var closeBtn = document.createElement('button')
      closeBtn.className = 'preview-close'; closeBtn.textContent = '×'
      var counter = document.createElement('div')
      counter.className = 'preview-counter'
      function updateCounter() { counter.textContent = (idx + 1) + ' / ' + urls.length }
      updateCounter()
      overlay.appendChild(img); overlay.appendChild(closeBtn); overlay.appendChild(counter)
      root.appendChild(overlay)
      overlay.setAttribute('role','dialog'); overlay.setAttribute('aria-modal','true');closeBtn.setAttribute('aria-label','关闭图片预览')
      const lease=services.overlays.register({kind:'image',ownerId:context.scope.ownerId,element:overlay,background:byId('feed-list')})
      lease.open(); closeBtn.focus()
      const release=context.cleanup(()=>closePreview('unmount'))
      closeActivePreview=closePreview

      // TD-001：禁用浏览器边缘返回手势
      var prevOverscroll = document.body.style.overscrollBehaviorX
      document.body.style.overscrollBehaviorX = 'contain'


      function setScale(s) { scale = Math.min(3, Math.max(1, s)); img.style.transform = 'scale(' + scale + ')' }
      function show(i) { idx = (i + urls.length) % urls.length; img.src = urls[idx]; setScale(1); updateCounter() }

      function onTouchStart(e) {
        if (e.touches.length === 2) {
          pinching = true
          startDist = dist(e.touches); baseScale = scale
        } else if (e.touches.length === 1) {
          startX = e.touches[0].clientX; moved = false
        }
      }
      function onTouchMove(e) {
        e.preventDefault()  // 阻断边缘返回 / 页面滚动
        if (e.touches.length === 2) {
          var d = dist(e.touches)
          if (startDist > 0) setScale(baseScale * (d / startDist))
        } else if (e.touches.length === 1 && !pinching) {
          var dx = e.touches[0].clientX - startX
          if (Math.abs(dx) > 8) moved = true
        }
      }
      function onTouchEnd(e) {
        if (pinching) { pinching = false; startDist = 0; return }
        if (scale > 1.05) return  // 放大态下不切换
        var endX = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0].clientX : startX
        var dx = endX - startX
        if (moved && Math.abs(dx) > 50) {
          if (dx < 0) show(idx + 1); else show(idx - 1)
        } else if (!moved) {
          closePreview()  // 单击关闭
        }
      }
      function dist(t) {
        var a = t[0], b = t[1]
        return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
      }
      let closed=false
      function closePreview(reason='user') {
        if(closed)return;closed=true;previewScope.dispose();lease.close({reason});lease.dispose();overlay.remove();
        document.body.style.overscrollBehaviorX=prevOverscroll;release();if(closeActivePreview===closePreview)closeActivePreview=null
      }
      listen(overlay,'keydown',event=>{if(event.key==='Escape'){event.preventDefault();closePreview()}else if(event.key==='Tab'){event.preventDefault();closeBtn.focus()}else if(event.key==='ArrowRight')show(idx+1);else if(event.key==='ArrowLeft')show(idx-1)})

      listen(overlay,'touchstart', onTouchStart, { passive: true })
      listen(overlay,'touchmove', onTouchMove, { passive: false })
      listen(overlay,'touchend', onTouchEnd, { passive: true })
      listen(closeBtn,'click', function (e) { e.stopPropagation(); closePreview() })
    }

  const openFeedLoginModal=()=>services.ui.openLogin({reason:'feed-interaction'});
  function disconnectReads(){commentReplyObserver.disconnect();postDwellObserver.disconnect();for(const timer of dwell.values())clearTimeout(timer);dwell.clear()}
  function remember(post){if(post?.id!=null)posts.set(String(post.id),JSON.parse(JSON.stringify(post)))}
  function appendPost(post,lastDate){const key=wallDateKey(post.scheduled_publish_time),item=buildFeedItem(post,!key||key!==lastDate);byId('feed-list').append(item);if(!restoring)observeReadTargets(item);return key||lastDate}
  function renderPosts(){
    disconnectReads();byId('feed-list').replaceChildren();let last=null;
    for(const post of posts.values())last=appendPost(post,last);
    for(const id of expanded){const item=[...byId('feed-list').children].find(n=>n.dataset.id===id);item?.querySelector('.feed-text')?.classList.remove('collapsed');if(item?.querySelector('.feed-expand'))item.querySelector('.feed-expand').textContent='收起'}
  }
  async function loadHeader(){
    const res=await request('GET','/api/feed/config/header');if(!context.valid())return;
    const data=res?.code===0&&res.data||{},avatar=byId('feed-avatar');
    byId('feed-hero').style.backgroundImage='url('+JSON.stringify(data.header_bg_url||'/static/images/feed/bg_default.png')+')';
    avatar.src=data.header_avatar_url||'/static/images/avatar/character-ref/base.png';
    avatar.onerror=()=>{avatar.onerror=null;if(context.valid())avatar.src='/static/images/avatar/character-ref/base.png'};context.cleanup(()=>{avatar.onerror=null});
    byId('feed-nickname').textContent=data.display_nickname||'林小梦';byId('feed-signature').textContent=data.signature||'';
    const city=(data.home_city||'').trim();byId('feed-home-city').innerHTML=city?'<svg class="loc-ico" viewBox="0 0 12 12" aria-hidden="true"><path fill="currentColor" d="M6 1.2c-1.9 0-3.4 1.5-3.4 3.3 0 2.5 3.4 6.3 3.4 6.3s3.4-3.8 3.4-6.3C9.4 2.7 7.9 1.2 6 1.2zm0 4.5a1.2 1.2 0 1 1 0-2.4 1.2 1.2 0 0 1 0 2.4z"/></svg><span>'+escapeHtml(city)+'</span>':'';byId('feed-home-city').classList.toggle('is-visible',!!city);
  }
  async function loadMsgBadge(){
    if(!isFeedAuthenticated())return;
    const res=await request('GET','/api/agent/unread-count');if(!context.valid())return;
    const count=res?.code===0&&res.data?.count||0;byId('msg-badge').textContent=count>99?'99+':String(count);byId('msg-badge').style.display=count?'':'none';
  }
  async function loadFeed(reset,{restore=false}={}){
    if(!context.valid()||loading||!reset&&(noMore||!restore&&bootLoadingPending&&!bootDismissed))return false;
    if(!reset&&!restore&&Date.now()-lastLoadAt<500){if(!paginationTimer)paginationTimer=setTimeout(()=>{paginationTimer=null;if(sentinelVisible)run(loadFeed(false))},500-(Date.now()-lastLoadAt));return false}
    lastLoadAt=Date.now();loading=true;const cursor=reset?null:nextCursor;
    if(reset){showState(null);if(!bootLoadingPending)renderSkeleton(true)}
    try{
      const res=await request('GET','/api/feed/list?size=20'+(cursor?'&cursor='+encodeURIComponent(cursor):''));if(!context.valid())return false;
      renderSkeleton(false);
      if(res?.code!==0||!res.data){if(reset){showState('error');byId('state-error-text').textContent=res?.message||'加载失败，请检查网络后重试'}else showToast(res?.message||'加载失败','error');return false}
      if(reset){posts.clear();loadedPages=0;disconnectReads();byId('feed-list').replaceChildren()}
      let last=byId('feed-list').lastElementChild?.dataset.dateKey||null;
      for(const post of res.data.posts||[]){const id=String(post.id);if(post.id==null)continue;if(posts.has(id))continue;remember(post);last=appendPost(posts.get(id),last)}
      loadedPages++;nextCursor=res.data.next_cursor||null;noMore=!nextCursor||nextCursor===cursor;
      byId('no-more').style.display=noMore&&posts.size?'block':'none';showState(posts.size?null:'empty');return true;
    }finally{loading=false;for(const resolve of loadWaiters)resolve();loadWaiters.clear();if(context.valid()&&bootLoadingPending&&!bootDismissed)await finishBootAfterListReady()}
  }
  async function refreshTruth(){
    if(loading)await new Promise(resolve=>loadWaiters.add(resolve));if(!context.valid())return false;
    const count=Math.max(1,loadedPages);if(!await loadFeed(true))return false;
    for(let i=1;i<count&&!noMore&&context.valid();i++)if(!await loadFeed(false,{restore:true}))break;
    return true;
  }
  async function toggleLike(item){
    if(!isFeedAuthenticated()){openFeedLoginModal();return}
    const id=item.dataset.id;if(likePending.has(id)||item.dataset.likeLock==='1')return;
    likePending.add(id);item.dataset.likeLock='1';setTimeout(()=>{item.dataset.likeLock='0'},300);
    const was=item.dataset.liked==='1',count=Number(item.dataset.likes)||0,liked=!was;
    const visual=(value,total)=>{item.dataset.liked=value?'1':'0';item.dataset.likes=total;item.querySelector('.like-count').textContent=total;setLikeVisual(item.querySelector('.like-act'),value)};
    visual(liked,Math.max(0,count+(liked?1:-1)));
    try{
      const res=await request(liked?'POST':'DELETE','/api/feed/'+encodeURIComponent(id)+'/like',null,{authPolicy:'interactive-modal'});if(!context.valid())return;
      if(res?.code===0&&res.data){visual(!!res.data.user_liked,res.data.display_likes);Object.assign(posts.get(id),res.data)}
      else if(res?.code===-1){await refreshTruth();showToast('未收到操作结果，已重新读取列表，请确认后再操作','error')}
      else {visual(was,count);if(res?.code!==401)showToast(res?.message||'操作失败，请重试','error')}
    }finally{likePending.delete(id)}
  }
  const inputEl=byId('comment-input'),sendEl=byId('comment-send'),panelEl=byId('comment-panel'),maskEl=byId('comment-mask');
  const commentLease=services.overlays.register({kind:'comment',ownerId:context.scope.ownerId,element:panelEl,background:root.querySelector('.feed-wrap'),open:()=>{maskEl.classList.add('show');panelEl.classList.add('show')},close:()=>{maskEl.classList.remove('show');panelEl.classList.remove('show');inputEl.blur()}});
  context.cleanup(()=>commentLease.dispose());
  function closeCommentPanel(){commentGeneration++;commentingPostId=null;commentingReplyToLxm=false;inputEl.value='';inputEl.placeholder='说点什么...';commentLease.close()}
  function openCommentPanel(postId,reply=false){
    if(!isFeedAuthenticated()){openFeedLoginModal();return}
    closeActivePreview?.();commentGeneration++;commentingPostId=postId;commentingReplyToLxm=reply;inputEl.value='';inputEl.placeholder=reply?'回复林小梦...':'说点什么...';byId('comment-count').textContent='0';sendEl.classList.remove('active');commentLease.open();const generation=commentGeneration;setTimeout(()=>{if(generation===commentGeneration)inputEl.focus()},50);
  }
  listen(maskEl,'click',closeCommentPanel);listen(inputEl,'input',()=>{byId('comment-count').textContent=String(inputEl.value.length);sendEl.classList.toggle('active',inputEl.value.trim().length>0)});
  listen(window,'keydown',event=>{if(!commentLease.isOpen()||closeActivePreview)return;if(event.key==='Escape'){event.preventDefault();closeCommentPanel()}else if(event.key==='Tab'){event.preventDefault();(document.activeElement===inputEl?sendEl:inputEl).focus()}});
  listen(sendEl,'click',async()=>{
    if(!isFeedAuthenticated()){closeCommentPanel();openFeedLoginModal();return}
    const content=inputEl.value.trim(),id=commentingPostId,reply=commentingReplyToLxm,generation=commentGeneration;if(commentSending||!content||id==null)return;
    commentSending=true;sendEl.disabled=true;
    try{
      const res=await request('POST','/api/feed/'+encodeURIComponent(id)+'/comments',{content,...(reply?{reply_to_lxm:true}:{})},{authPolicy:'interactive-modal'});if(!context.valid())return;
      if(res?.code===0){
        const post=posts.get(String(id));if(post&&res.data?.comment_id){post.comments||=[];if(!post.comments.some(c=>String(c.id)===String(res.data.comment_id))){post.comments.push({id:res.data.comment_id,content,reply_to_lxm:reply});post.display_comments=(Number(post.display_comments)||0)+1}renderPosts()}
        if(generation===commentGeneration)closeCommentPanel();
      }else if(res?.code===-1){await refreshTruth();showToast('未收到发送结果，已重新读取列表，请确认后再操作','error')}
      else if(res?.code!==401)showToast(res?.code===10504?'你刚刚才评论过，等 30 秒吧~':res?.message||'发送失败','error');
    }finally{commentSending=false;if(context.valid())sendEl.disabled=false}
  });
  listen(root,'click',event=>{
    const action=event.target.closest('[data-feed-action]')?.dataset.feedAction;
    if(action==='back')return context.router.back();
    if(action==='chat')return context.router.navigate('/pages/chat.html');
    const item=event.target.closest('.feed-item');if(!item)return;const post=posts.get(item.dataset.id);if(!post)return;
    if(event.target.closest('.like-act'))return toggleLike(item);
    if(event.target.closest('.comment-act'))return openCommentPanel(post.id);
    if(event.target.closest('.comment-reply'))return openCommentPanel(post.id,true);
    const image=event.target.closest('.feed-images img');if(image)return openPreview(post.image_urls,Number(image.dataset.idx)||0);
    if(event.target.closest('.feed-expand')){const text=item.querySelector('.feed-text'),collapsed=text.classList.toggle('collapsed');item.querySelector('.feed-expand').textContent=collapsed?'展开':'收起';if(collapsed)expanded.delete(item.dataset.id);else expanded.add(item.dataset.id)}
  });
  listen(root,'keydown',event=>{if((event.key==='Enter'||event.key===' ')&&event.target.matches('.like-act,.comment-act,.feed-images img')){event.preventDefault();event.target.click()}});
  listen(root,'error',event=>{if(event.target.matches?.('.feed-images img'))event.target.parentElement.classList.add('img-failed')},true);
  for(const type of ['pointerdown','wheel','touchstart','keydown'])listen(root,type,()=>{interacted=true},{passive:true});
  let startY=0,pulling=false;
  listen(window,'touchstart',event=>{pulling=!commentLease.isOpen()&&!closeActivePreview&&window.scrollY<=0&&event.touches.length===1;if(pulling)startY=event.touches[0].clientY},{passive:true});
  listen(window,'touchmove',event=>{if(pulling&&event.touches[0]&&event.touches[0].clientY-startY>60)byId('pull-tip').classList.add('show')},{passive:true});
  listen(window,'touchend',()=>{if(!pulling)return;pulling=false;if(byId('pull-tip').classList.contains('show')){byId('pull-tip').classList.remove('show');return loadFeed(true)}},{passive:true});
  const sentinelObserver=new IntersectionObserver(context.scope.guard(entries=>{sentinelVisible=entries.some(e=>e.isIntersecting);if(sentinelEnabled&&!loading&&!noMore&&sentinelVisible)run(loadFeed(false))}));context.cleanup(()=>sentinelObserver.disconnect(),{kind:'observer'});
  function enableFeedInfiniteScroll(){if(!context.valid()||sentinelEnabled)return;sentinelEnabled=true;sentinelObserver.observe(byId('bottom-sentinel'))}
  const commentReplyObserver=new IntersectionObserver(context.scope.guard(entries=>{
    if(!isFeedAuthenticated())return;
    for(const entry of entries){const id=entry.target.dataset.commentId;if(!entry.isIntersecting||entry.intersectionRatio<.6||!id||reportedComments.has(id))continue;reportedComments.add(id);commentReplyObserver.unobserve(entry.target);run(request('POST','/api/feed/comments/'+encodeURIComponent(id)+'/read'))}
  }),{threshold:.6});
  const postDwellObserver=new IntersectionObserver(context.scope.guard(entries=>{
    if(!isFeedAuthenticated())return;
    for(const entry of entries){const id=entry.target.dataset.id;if(!id||reportedPosts.has(id))continue;
      if(entry.isIntersecting&&entry.intersectionRatio>=.5){if(dwell.has(id))continue;dwell.set(id,setTimeout(()=>{dwell.delete(id);if(!isFeedAuthenticated()||!entry.target.isConnected)return;reportedPosts.add(id);postDwellObserver.unobserve(entry.target);run(request('POST','/api/feed/'+encodeURIComponent(id)+'/read'))},3000))}
      else if(dwell.has(id)){clearTimeout(dwell.get(id));dwell.delete(id)}
    }
  }),{threshold:.5});
  context.cleanup(disconnectReads,{kind:'observer'});
  function observeReadTargets(item){
    if(!isFeedAuthenticated()||restoring)return;if(!reportedPosts.has(item.dataset.id))postDwellObserver.observe(item);
    for(const reply of item.querySelectorAll('.comment-reply[data-comment-id]')){const id=reply.dataset.commentId,post=posts.get(item.dataset.id),comment=post?.comments?.find(c=>String(c.id)===id);if(!reportedComments.has(id)&&!comment?.lxm_reply_read_at)commentReplyObserver.observe(reply)}
  }
  function updateNewFeedBar(){byId('new-feed-count').textContent=String(pendingNewCount);byId('new-feed-bar').classList.toggle('is-visible',pendingNewCount>0)}
  function disconnectFeedSSE(){feedEventSource?.close();feedEventSource=null;if(sseRetryTimer)clearTimeout(sseRetryTimer);sseRetryTimer=null}
  function connectFeedSSE(){
    if(!isFeedAuthenticated()||feedEventSource)return;
    const source=feedEventSource=new EventSource('/api/feed/events?token='+encodeURIComponent(services.auth.readToken()));
    const current=()=>context.valid()&&feedEventSource===source&&isFeedAuthenticated();
    source.onmessage=event=>{if(!current())return;try{const value=JSON.parse(event.data);if(value.type==='feed_new'){pendingNewCount+=value.delta||1;updateNewFeedBar()}}catch(_){}};
    source.onopen=()=>{if(current())sseRetryDelay=1000};
    source.onerror=()=>{source.close();if(!current())return;feedEventSource=null;sseRetryTimer=setTimeout(()=>{sseRetryTimer=null;connectFeedSSE()},sseRetryDelay);sseRetryDelay=Math.min(30000,sseRetryDelay*2)};
  }
  context.cleanup(disconnectFeedSSE,{kind:'sse'});
  const refresh=()=>{pendingNewCount=0;updateNewFeedBar();return loadFeed(true)};
  listen(byId('btn-retry'),'click',refresh);listen(byId('new-feed-bar'),'click',()=>{window.scrollTo({top:0,behavior:'smooth'});return refresh()});
  listen(byId('new-feed-bar'),'keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();return refresh()}});
  async function initialize(){
    startFeedBootProgress();
    for(const post of context.state?.items||[])remember(post);if(posts.size)renderPosts();
    const header=loadHeader(),badge=isFeedAuthenticated()?loadMsgBadge():Promise.resolve();
    if(isFeedAuthenticated()&&!enterStarted){enterStarted=true;const entered=await request('POST','/api/feed/enter');if(!context.valid())return;if(entered?.code===0&&context.params.get('focus')==='unread_reply')anchorCommentId=entered.data?.anchor_comment_id||null}
    await Promise.allSettled([header,badge]);if(!context.valid())return;
    const loaded=await loadFeed(true);if(!context.valid())return;
    if(loaded){
      for(let i=1;i<entryPageCount&&!noMore&&!interacted;i++)if(!await loadFeed(false,{restore:true}))break;
      if(!context.valid())return;
      if(anchorCommentId){const anchor=[...root.querySelectorAll('[data-comment-id]')].find(n=>n.dataset.commentId===String(anchorCommentId));if(anchor&&!interacted){anchor.scrollIntoView({block:'center'});anchor.classList.add('comment-highlighted');setTimeout(()=>anchor.classList.remove('comment-highlighted'),1600)}}
      else if(!interacted&&context.state)services.history.restore(context.router.current);
    }
    restoring=false;enableFeedInfiniteScroll();if(isFeedAuthenticated()){connectFeedSSE();for(const item of byId('feed-list').children)observeReadTargets(item)}
  }
  run(initialize());
  return{unmount(){closeActivePreview?.('unmount');commentGeneration++},captureState:()=>({items:[...posts.values()],cursor:{value:nextCursor,pages:loadedPages},expandedIds:[...expanded]})};
}

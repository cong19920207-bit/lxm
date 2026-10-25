import { createPageTimers } from '../app/page-timers.js';

export async function mount(context) {
  const {root, services} = context, byId = id => root.querySelector('#' + id);
  if (!context.valid() || !services.auth.snapshot().authenticated) return {unmount(){}};
  const routeCurrent = () => context.router.current?.context.routeEpoch === context.routeEpoch;
  const relationshipProtectedAuthOptions = () => ({authPolicy:'protected-home-modal', routeEpoch:context.routeEpoch,
    routeCurrent, isCurrent:context.valid, signal:context.signal});
  const request = (...args) => services.auth.request(...args);
  const showToast = (...args) => { if(context.valid()) services.ui.toast(...args); };
  const escapeHtml = value => {const el=document.createElement('span');el.textContent=String(value??'');return el.innerHTML;};
  const run = promise => Promise.resolve(promise).catch(error => {
    if(context.valid() && !['AbortError','StaleRequestError'].includes(error.name)) showToast('加载失败，请重试','error');
  });
  const {setTimeout, requestAnimationFrame} = createPageTimers(context);
  await context.scope.adopt(services.resources.style('css/bgm.css'), release=>release());
  for(const name of ['bgm-page','bgm-record','bgm-bubble']) {
    await services.shared.script('js/'+name+'.js'); if(!context.valid()) return {unmount(){}};
  }
  const audioPage = services.audio.attachPage(context,'content'), bubble = BgmBubble.mount(audioPage);
  if(bubble) context.cleanup(()=>bubble.destroy());
  const ICON_MAP = {dialog:'💬',long_session:'⏱',daily_login:'📅',reply_agent:'💌'};
  let relationshipPageActive=true, logPage=1, logLoading=false, logNoMore=false, pageData=null, logObserver=null;
  let levelLease=null, levelOverlay=null, restoring=true;
  const logIds = new Set();
  const restoredPages = Math.max(1, Math.min(100, Number(context.state?.cursor)||1));
  function updateAvatarEmotion(emotion) {
    const el=byId('linxiaomeng-avatar'); el.src=AVATAR_MAP[emotion]||AVATAR_MAP.default;
  }
  let avatarFailed=false;
  context.scope.listen(byId('linxiaomeng-avatar'),'error',()=>{
    if(avatarFailed)return;avatarFailed=true;byId('linxiaomeng-avatar').src=AVATAR_MAP.default;
  });
  async function loadPage() {
    try {
      const res=await request('GET','/api/relationship/detail',undefined,relationshipProtectedAuthOptions());
      if(!context.valid())return;
      if(res.code!==0||!res.data){ byId('page-body').classList.add('content-loaded');showToast('加载失败，请重试','error');return; }
      pageData=res.data;
      renderHeroProfile(pageData.level_info,pageData.ai_current_emotion);
      renderMilestones(pageData.milestones);
      renderProgress(pageData.level_info,pageData.growth_info);
      renderTodayGrowth(pageData.today_growth,pageData.milestones.consecutive_login_days);
      renderTimeline(pageData.level_history,pageData.level_info,pageData.milestones);
      if(context.state?.rightsCollapsed===false) toggleNextPerks();
      byId('page-body').classList.add('content-loaded');
      animateNumbers();
      // The actual history URL is authoritative; an older snapshot cannot resurrect a consumed parameter.
      if(context.router.consumeParam('just_leveled_up','true'))setTimeout(()=>showLevelUpModal(pageData.level_info),500);
      do { if(!await loadGrowthLog()) break; } while(context.valid()&&!logNoMore&&logPage<=restoredPages);
      if(!context.valid())return;
      restoring=false;
      logObserver=new IntersectionObserver(entries=>{
        if(context.valid()&&!restoring&&entries.some(e=>e.isIntersecting))run(loadGrowthLog());
      },{threshold:0});
      context.cleanup(()=>logObserver.disconnect(),{kind:'observer'});
      logObserver.observe(byId('log-sentinel'));
    }catch(error){
      if(context.valid()) { byId('page-body').classList.add('content-loaded');showToast('加载失败，请重试','error'); }
    }
  }
    function renderHeroProfile(info, emotion) {
      byId('rel-level-badge').textContent = info.name || '陌生'
      byId('rel-desc').textContent = info.description || ''

      const perksEl = byId('rel-perks')
      perksEl.innerHTML = ''
      ;(info.perks || []).forEach(function (p) {
        const tag = document.createElement('span')
        tag.className = 'rel-perk-tag'
        tag.textContent = p
        perksEl.appendChild(tag)
      })

      if (emotion) {
        updateAvatarEmotion(emotion)
      }
    }

    function renderMilestones(ms) {
      byId('m-known-days').setAttribute('data-target', ms.known_days)
      byId('m-known-days').textContent = '0'
      byId('m-known-sub').textContent =
        '和你相遇的第 ' + (ms.known_days || 0) + ' 天'

      byId('m-conv-rounds').setAttribute('data-target', ms.total_conversation_rounds)
      byId('m-conv-rounds').textContent = '0'

      byId('m-login-days').setAttribute('data-target', ms.consecutive_login_days)
      byId('m-login-days').textContent = '0'

      byId('m-silence-days').setAttribute('data-target', ms.silence_days)
      byId('m-silence-days').textContent = '0'

      const silenceEl = byId('m-silence-days')
      if (ms.silence_days > 7) {
        silenceEl.classList.add('warn')
      } else {
        silenceEl.classList.remove('warn')
      }

      const silenceSub = byId('m-silence-sub')
      if (!ms.silence_days) {
        silenceSub.textContent = '从不远离你'
      } else {
        silenceSub.textContent = '已经 ' + ms.silence_days + ' 天没见了'
      }
    }

    function animateNumbers() {
      const els = root.querySelectorAll('[data-target]')
      els.forEach(function (el) {
        const target = parseInt(el.getAttribute('data-target'), 10) || 0
        if (target === 0) {
          el.textContent = '0'
          return
        }
        const start = performance.now()
        const duration = 300
        function tick(now) {
          const progress = Math.min((now - start) / duration, 1)
          const eased = 1 - Math.pow(1 - progress, 3)
          el.textContent = Math.round(target * eased)
          if (progress < 1) requestAnimationFrame(tick)
        }
        requestAnimationFrame(tick)
      })
    }

    function renderProgress(levelInfo, growthInfo) {
      const container = byId('progress-content')
      const polaroid = root.querySelector('.rel-polaroid')

      if (growthInfo.is_max_level) {
        if (polaroid) polaroid.style.display = 'none'
        container.className = ''
        container.innerHTML =
          '<div class="rel-max-badge">' +
            '<div class="big">已达到最高等级「知己」✨</div>' +
            '<div class="sub">林小梦与你之间，已建立最深的情感连接</div>' +
          '</div>'
        return
      }

      if (polaroid) polaroid.style.display = ''
      container.className = 'rel-progress-wrap'

      const nextLevelName = levelInfo.next_level_name || '下一级'
      const firstPerk = (levelInfo.next_perks && levelInfo.next_perks[0]) || '更多互动'
      const unlockLine = '解锁「' + nextLevelName + '」后，可获得' + firstPerk + ' >'

      container.innerHTML =
        '<div class="rel-progress-bar" id="detail-bar" data-action="progress" role="button" tabindex="0">' +
          '<div class="rel-progress-fill" id="detail-fill"></div>' +
        '</div>' +
        '<div class="rel-progress-stats">' +
          '<span>已积累 <em class="rel-stat-num">' + growthInfo.points_in_level + '</em> / <em class="rel-stat-num">' +
            growthInfo.points_needed + '</em> <span class="rel-stat-muted">亲密值</span></span>' +
          '<span>还差 <em class="rel-stat-num">' + growthInfo.points_to_next + '</em> <span class="rel-stat-upgrade">升级</span></span>' +
        '</div>' +
        '<div class="rel-progress-tip" id="progress-tip"></div>' +
        '<div class="rel-next-toggle" data-action="perks" role="button" tabindex="0" aria-expanded="false">' +
          '<span>' + escapeHtml(unlockLine) + '</span>' +
          '<span class="arrow" aria-hidden="true">▼</span>' +
        '</div>' +
        '<div class="rel-next-list" id="next-perks-list">' +
          (levelInfo.next_perks || []).map(function (p) {
            return '<div class="perk-item">✨ ' + escapeHtml(p) + '</div>'
          }).join('') +
        '</div>'

      setTimeout(function () {
        const fill = byId('detail-fill')
        if (fill) fill.style.width = growthInfo.progress_percent + '%'
      }, 100)
    }

    function showProgressTip() {
      if (!pageData || pageData.growth_info.is_max_level) return
      const tip = byId('progress-tip')
      const rounds = Math.ceil(pageData.growth_info.points_to_next / 2)
      tip.textContent = '再聊 ' + rounds + ' 轮就能升级啦～'
      tip.classList.add('visible')
      setTimeout(function () { tip.classList.remove('visible') }, 2000)
    }

    function toggleNextPerks() {
      const toggle = root.querySelector('.rel-next-toggle')
      const list = byId('next-perks-list')
      if (!toggle || !list) return
      toggle.classList.toggle('open')
      list.classList.toggle('open')
      toggle.setAttribute('aria-expanded', String(list.classList.contains('open')))
    }

    function renderTodayGrowth(tg, consecutiveDays) {
      const totalEl = byId('today-total')
      if (tg.today_total_points > 0) {
        totalEl.textContent = '今日总计 +' + tg.today_total_points + ' 亲密值'
        totalEl.className = 'rel-today-total'
      } else {
        totalEl.textContent = '今天还没有互动哦'
        totalEl.className = 'rel-today-total empty'
      }

      const list = byId('today-list')
      const items = [
        {
          icon: '💬',
          title: '完成对话',
          points: tg.today_dialog_points,
          sub: tg.today_dialog_limit_reached
            ? null
            : '还差获得 ' + tg.today_remaining_dialog + ' 分',
          done: tg.today_dialog_limit_reached,
          doneText: '今日已满'
        },
        {
          icon: '📞',
          title: '语音通话',
          points: tg.today_voice_points || 0,
          sub: '通话结束后按有效时长结算',
          done: false
        },
        {
          icon: '🎙',
          title: '深度聊天',
          points: tg.today_session_points,
          sub: tg.today_session_points === 0 ? '聊够10分钟可获得+20分' : null,
          done: tg.today_session_points >= 20,
          doneText: '已完成'
        },
        {
          icon: '📅',
          title: '每日登录',
          points: tg.today_login_points,
          sub: tg.today_login_points === 0 ? '今日登录 +5' : null,
          done: tg.today_login_points > 0,
          doneText: '已完成',
          streak: consecutiveDays >= 7 ? '连续' + consecutiveDays + '天奖励中🔥' : null
        },
        {
          icon: '💌',
          title: '回复消息',
          points: tg.today_reply_points,
          sub: tg.today_reply_points === 0 ? '回复可获得+10分' : null,
          done: tg.today_reply_points > 0,
          doneText: '已完成'
        }
      ]

      list.innerHTML = items.map(function (item) {
        let footHtml
        if (item.done) {
          footHtml = '<span class="tc-done">' + item.doneText + '</span>'
        } else {
          footHtml = '<span class="tc-foot">' + item.points + '分</span>'
        }

        let subHtml = ''
        if (item.sub) {
          subHtml = '<div class="tc-sub">' + item.sub + '</div>'
        }
        if (item.streak) {
          subHtml += '<div class="streak-tag">' + item.streak + '</div>'
        }

        return '<div class="rel-task-card">' +
          '<div class="tc-icon">' + item.icon + '</div>' +
          '<div class="tc-title">' + item.title + '</div>' +
          subHtml +
          '<div class="tc-status">' + footHtml + '</div>' +
        '</div>'
      }).join('')
    }

    function renderTimeline(history, levelInfo, milestones) {
      const container = byId('timeline-content')

      if (!history || history.length === 0) {
        let text = '我们的故事，从这里开始'
        if (milestones.first_conversation_at) {
          const d = new Date(milestones.first_conversation_at)
          text = '我们相识于 ' + (d.getMonth() + 1) + '月' + d.getDate() + '日，\n从陌生人开始，慢慢走到了现在'
        }
        container.innerHTML = '<div class="timeline-empty">' + text + '</div>'
        return
      }

      let html = '<div class="timeline-list">'
      html += '<div class="timeline-node current">' +
        '<div class="tn-title">★ 当前是「' + escapeHtml(levelInfo.name) + '」</div>' +
        '<div class="tn-time">一直在这里陪着你</div>' +
      '</div>'

      history.forEach(function (h) {
        const d = new Date(h.achieved_at)
        const timeStr = (d.getMonth() + 1) + '月' + d.getDate() + '日 ' +
          String(d.getHours()).padStart(2, '0') + ':' +
          String(d.getMinutes()).padStart(2, '0')
        html += '<div class="timeline-node">' +
          '<div class="tn-title">● 升级为「' + escapeHtml(h.level_name) + '」</div>' +
          '<div class="tn-time">' + timeStr + '</div>' +
        '</div>'
      })

      html += '</div>'
      container.innerHTML = html
    }

    async function loadGrowthLog() {
      if (!relationshipPageActive || logLoading || logNoMore) return
      logLoading = true

      let res
      try { res = await request(
        'GET',
        '/api/relationship/growth-log?page=' + logPage + '&page_size=20',
        undefined,
        relationshipProtectedAuthOptions()
      ) } catch (error) { logLoading = false; throw error }
      if (!context.valid() || res.code === 401) {
        logLoading = false
        return
      }
      if (res.code !== 0 || !res.data) {
        logLoading = false
        return
      }

      const data = res.data
      byId('log-total').textContent = '共 ' + data.total + ' 条'

      if (data.list.length === 0 && logPage === 1) {
        byId('log-list').innerHTML =
          '<div class="timeline-empty">暂无成长记录</div>'
        logNoMore = true
        logLoading = false
        return
      }

      const listEl = byId('log-list')
      let lastDateStr = ''
      const prevItems = listEl.querySelectorAll('.log-item')
      if (prevItems.length > 0) {
        lastDateStr = prevItems[prevItems.length - 1].getAttribute('data-date') || ''
      }

      data.list.forEach(function (item) {
        const key = item.id == null ? JSON.stringify([item.action_type,item.action_label,item.points,item.created_at]) : String(item.id)
        if (logIds.has(key)) return
        logIds.add(key)
        const d = new Date(item.created_at)
        const dateStr = (d.getMonth() + 1) + '月' + d.getDate() + '日'

        if (dateStr !== lastDateStr) {
          const sep = document.createElement('div')
          sep.className = 'log-date-sep'
          sep.textContent = dateStr
          listEl.appendChild(sep)
          lastDateStr = dateStr
        }

        const row = document.createElement('div')
        row.className = 'log-item'
        if (item.id != null) row.dataset.growthId = String(item.id)
        row.setAttribute('data-date', dateStr)

        const icon = ICON_MAP[item.action_type] || '📌'
        const timeStr = String(d.getHours()).padStart(2, '0') + ':' +
                        String(d.getMinutes()).padStart(2, '0')

        row.innerHTML =
          '<div class="li-icon-slot" aria-hidden="true">' + icon + '</div>' +
          '<div class="li-body">' +
            '<div class="li-label">' + escapeHtml(item.action_label) + '</div>' +
            '<div class="li-time">' + timeStr + '</div>' +
          '</div>' +
          '<div class="li-points">+' + item.points + '分</div>'

        listEl.appendChild(row)
      })

      if (data.list.length < 20 || logPage * 20 >= data.total) {
        logNoMore = true
        byId('log-no-more').style.display = 'block'
      }

      logPage++
      logLoading = false
      return true
    }


  function showLevelUpModal(info) {
    if(!context.valid()||levelOverlay)return;
    const overlay=document.createElement('div');levelOverlay=overlay;
    overlay.className='levelup-overlay';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('aria-label','关系升级');
    overlay.innerHTML='<div class="levelup-box"><div class="particles" id="lu-particles"></div>'+
      '<div class="lu-title">🎉 恭喜升级！</div><div class="lu-subtitle">我们现在是「'+escapeHtml(info.name)+'」了</div>'+
      '<div class="lu-perks">'+(info.perks||[]).map(p=>'<div class="lu-perk">✨ '+escapeHtml(p)+'</div>').join('')+
      '</div><button type="button" class="lu-btn" id="lu-close-btn">继续聊天</button></div>';
    root.append(overlay);
    levelLease=services.overlays.register({kind:'relationship-upgrade',ownerId:context.scope.ownerId,
      element:overlay,background:byId('page-body'),close:()=>{
        overlay.classList.add('closing');overlay.querySelector('.particles')?.replaceChildren();
        // Match the original fade while keeping a deterministic cleanup if animationend is lost.
        setTimeout(()=>{overlay.remove();if(levelOverlay===overlay)levelOverlay=null;},300);
      }});
    levelLease.open();createParticles(byId('lu-particles'));byId('lu-close-btn').focus({preventScroll:true});
    context.scope.listen(overlay,'click',event=>{if(event.target===overlay||event.target.closest('#lu-close-btn'))levelLease.close();});
    context.scope.listen(overlay,'keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();levelLease.close();}
      if(event.key==='Tab'){event.preventDefault();byId('lu-close-btn')?.focus({preventScroll:true});}
    });
  }
    function createParticles(container) {
      if (!container) return
      const colors = ['#c084fc', '#e879f9', '#a855f7', '#f0abfc', '#ddd6fe', '#f9a8d4']
      for (let i = 0; i < 20; i++) {
        const p = document.createElement('div')
        p.className = 'particle'
        const size = 4 + Math.random() * 8
        p.style.width = size + 'px'
        p.style.height = size + 'px'
        p.style.background = colors[Math.floor(Math.random() * colors.length)]
        p.style.left = Math.random() * 100 + '%'
        p.style.top = 60 + Math.random() * 40 + '%'
        p.style.animationDelay = Math.random() * 1 + 's'
        p.style.animationDuration = (1.5 + Math.random() * 1) + 's'
        container.appendChild(p)
      }
    }


  context.scope.listen(root,'click',event=>{
    const action=event.target.closest('[data-action]')?.dataset.action;
    if(action==='back')context.router.back();
    if(action==='progress')showProgressTip();
    if(action==='perks')toggleNextPerks();
  });
  context.scope.listen(root,'keydown',event=>{
    if(['Enter',' '].includes(event.key)&&event.target.matches('[role="button"][data-action]')){event.preventDefault();event.target.click();}
  });
  context.cleanup(()=>{
    relationshipPageActive=false;logLoading=false;logNoMore=true;logObserver?.disconnect();
    levelLease?.dispose();levelOverlay?.remove();levelOverlay=null;logIds.clear();pageData=null;
  },{priority:90});
  void loadPage();
  return {captureState:()=>({rightsCollapsed:!byId('next-perks-list')?.classList.contains('open'),cursor:Math.max(1,logPage-1)}),unmount(){}};
}

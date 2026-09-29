/* 实时语音配置后台（P1 M1 STEP-006A）。
 * 绑定已冻结的配置控制面与管理员短生命周期联调动作；O-01 仍由真人总验收关闭。
 */
(function () {
  'use strict';

  var ALLOWED_ROLES = ['super_admin', 'ai_trainer', 'tech_ops', 'ops_admin', 'observer'];
  var CONFIG_WRITE_ROLES = ['super_admin', 'tech_ops'];
  var SCRIPT_WRITE_ROLES = ['super_admin', 'ai_trainer'];
  var VOICE_OPS_READ_ROLES = ['super_admin', 'tech_ops', 'observer'];
  var VOICE_TEST_ROLES = ['super_admin', 'tech_ops'];
  var VOICE_FORCE_TEST_ROLES = ['super_admin'];
  var CAPABILITY_KEYS = [
    'supports_current_turn_rag_gate',
    'supports_reply_cancel',
    'supports_context_truncate',
    'supports_playback_text_mapping',
    'supports_sentence_playback_ack',
    'supports_session_reconnect'
  ];
  var CAPABILITY_EDITABLE_FIELDS = ['fallback_mode', 'evidence_ttl_days'];
  var CAPABILITY_READONLY_FIELDS = [
    'verification_status', 'enabled', 'forced_enabled', 'effective_scope',
    'provider_profile', 'model_version', 'protocol_profile', 'adapter_version',
    'sdk_version', 'evidence_suite_version', 'evidence_fingerprint',
    'verified_at', 'expires_at', 'evidence_report_id', 'last_test_result'
  ];
  var PRIMARY_FIELD_DEFINITIONS = {
    s2s: {
      sectionLabel: '模型与连接 · MODEL',
      label: 'MODEL（s2s.model_version）',
      field: 'model_version',
      help: '豆包实时对话模型版本；对应技术文档的 s2s.model_version。'
    },
    voice: {
      sectionLabel: '声音与音色 · SPEAKER',
      label: 'SPEAKER（voice.voice_id）',
      field: 'voice_id',
      help: '豆包音色 ID；对应技术文档的 voice.voice_id。'
    }
  };
  var SECTION_UI = {
    config: {
      global: {
        group: '开放控制', label: '开放与维护', description: '控制维护状态和用户开放范围。语音总开关在独立页面管理。',
        fields: [
          {path:'maintenance_mode', label:'维护模式', type:'toggle', help:'开启后拒绝所有新通话，并向客户端返回维护提示。'},
          {path:'maintenance_message', label:'维护提示语', type:'textarea', wide:true, help:'维护模式开启时向客户端显示。'},
          {path:'soft_stop', label:'新拨打软停止', type:'toggle', readonly:true, help:'由“通话运维”操作直接控制；这里只显示当前配置值。'},
          {path:'rollout.mode', label:'开放范围', type:'select', options:[['off','暂停开放'],['allowlist','仅指定用户'],['all','全部用户']], help:'总开关开启后，仍会按照这里的范围决定哪些用户可以通话。'},
          {path:'rollout.user_ids', label:'开放用户 ID', type:'tags-number', wide:true, showWhen:{path:'rollout.mode', value:'allowlist'}, help:'仅“指定用户”模式生效；输入数字用户 ID 后点击添加。'},
          {path:'test_user_ids', label:'能力测试用户 ID', type:'tags-number', wide:true, help:'仅用于 test 能力范围，不等同于通话开放名单。'}
        ]
      },
      persona_ref: {
        group: '基础连接', label: '人格引用', description: '运行时使用的已发布人格锚点，由服务端维护。',
        fields: [
          {path:'config_key', label:'配置键', readonly:true},
          {path:'version', label:'人格版本', readonly:true},
          {path:'content_sha256', label:'内容校验值', readonly:true, wide:true}
        ]
      },
      s2s: {
        group: '基础连接', label: '模型与连接', description: '豆包实时语音模型、协议和连接重试参数。密钥值只从环境变量读取。',
        fields: [
          {path:'provider', label:'服务商', type:'select', options:[['doubao','豆包 Doubao']]},
          {path:'endpoint', label:'服务地址', wide:true, help:'仅接受 wss:// 或 https:// 地址，禁止携带密钥和签名。'},
          {path:'resource_id', label:'资源 ID'},
          {path:'adapter_version', label:'适配器版本'},
          {path:'protocol_profile', label:'协议配置'},
          {path:'credential_ref', label:'凭据环境变量', readonly:true, help:'显示环境变量名称，不显示凭据值。'},
          {path:'connect_timeout_ms', label:'连接超时', type:'number', min:5000, max:30000, step:1, unit:'毫秒'},
          {path:'start_session_timeout_ms', label:'会话启动超时', type:'number', min:5000, max:30000, step:1, unit:'毫秒'},
          {path:'max_retries', label:'最大重试次数', type:'number', min:0, max:10, step:1, unit:'次'},
          {path:'retry_backoff_ms', label:'重试等待序列', type:'tags-number', wide:true, unit:'毫秒', help:'按顺序填写每次重试前的等待时间。'}
        ]
      },
      voice: {
        group: '基础连接', label: '声音与音色', description: '设置主音色、语速、音量和候选音色。',
        fields: [
          {path:'voice_version', label:'音色配置版本'},
          {path:'speech_rate', label:'语速调整', type:'number', min:-50, max:100, step:1, unit:'%'},
          {path:'loudness_rate', label:'音量调整', type:'number', min:-50, max:100, step:1, unit:'%'},
          {path:'expressive', label:'情感表现', type:'toggle', help:'允许服务商使用更有表现力的语音风格。'},
          {path:'tone_instruction', label:'语气说明', type:'textarea', wide:true},
          {path:'candidates', label:'候选音色', type:'candidates', wide:true},
          {path:'persona_mapping', label:'人格音色映射', type:'mapping', wide:true, help:'人格标识与音色 ID 的映射；没有特殊映射时保持为空。'}
        ]
      },
      capabilities: {
        group: '能力与测试', label: '能力与测试', description: '配置六项能力的失败回退方式和证据有效期；验证状态由服务端只读投影提供。',
        fields: [{path:'', label:'能力配置', type:'capabilities', wide:true}]
      },
      quota: {
        group: '额度与成长', label: '通话额度', description: '控制用户每日可用时长和单通上限。',
        fields: [
          {path:'daily_free_seconds', label:'每日免费时长', type:'number', min:0, step:1, unit:'秒'},
          {path:'grace_seconds', label:'额度耗尽宽限', type:'number', min:0, max:30, step:1, unit:'秒'},
          {path:'hard_limit_seconds', label:'单通硬上限', type:'number', min:1, step:1, unit:'秒'},
          {path:'timezone', label:'额度时区', readonly:true}
        ]
      },
      growth: {
        group: '额度与成长', label: '关系成长', description: '根据有效通话时长累计关系积分。',
        fields: [
          {path:'segment_seconds', label:'计分周期', type:'number', min:1, step:1, unit:'秒'},
          {path:'points_per_segment', label:'每周期积分', type:'number', min:1, step:1, unit:'分'},
          {path:'daily_limit_points', label:'每日积分上限', type:'number', min:0, step:1, unit:'分'},
          {path:'timezone', label:'计分时区', readonly:true}
        ]
      },
      interaction: {
        group: '通话体验', label: '打断与结束体验', description: '控制语音活动检测、打断判断和结束等待。',
        fields: [
          {path:'vad_rms_threshold', label:'语音检测阈值', type:'number', min:0.001, max:0.2, step:0.001, help:'数值越小越容易识别为正在说话。'},
          {path:'candidate_ms', label:'候选表达窗口', type:'number', min:180, max:250, step:1, unit:'毫秒'},
          {path:'sustained_ms', label:'持续表达阈值', type:'number', min:250, max:2000, step:1, unit:'毫秒', help:'必须大于候选表达窗口。'},
          {path:'post_playback_buffer_ms', label:'播放结束缓冲', type:'number', min:0, max:3000, step:1, unit:'毫秒'},
          {path:'goodbye_timeout_ms', label:'告别等待时间', type:'number', min:1000, max:30000, step:1, unit:'毫秒'},
          {path:'time_low_seconds', label:'低余额提醒阈值', type:'number', min:1, max:300, step:1, unit:'秒'}
        ]
      },
      concurrency: {
        group: '通话体验', label: '连接与并发', description: '控制心跳、重连、通话票据和全局并发。',
        fields: [
          {path:'heartbeat_interval_ms', label:'心跳间隔', type:'number', min:1000, max:10000, step:1, unit:'毫秒'},
          {path:'user_lock_ttl_ms', label:'用户锁有效期', type:'number', min:10000, max:60000, step:1, unit:'毫秒', help:'至少为心跳间隔的 3 倍。'},
          {path:'reconnect_timeout_ms', label:'重连超时', type:'number', min:1000, max:60000, step:1, unit:'毫秒'},
          {path:'call_ticket_ttl_ms', label:'通话票据有效期', type:'number', min:5000, max:60000, step:1, unit:'毫秒'},
          {path:'global_limit', label:'全局并发上限', type:'number', min:1, step:1, unit:'通'}
        ]
      },
      summary: {
        group: '通话后处理', label: '通话总结模型', description: '使用服务器环境中的 DeepSeek 地址和密钥，只在这里选择模型标识。',
        fields: [{path:'model', label:'总结模型', help:'例如 deepseek-chat；不能填写 URL 或密钥。'}]
      },
      followup: {
        group: '通话后处理', label: '结束后跟进', description: '设置生成总结的最短通话时长，以及不同关系阶段允许发送跟进消息的时间窗。',
        fields: [
          {path:'summary_min_effective_seconds', label:'最短有效通话时长', type:'number', min:1, step:1, unit:'秒'},
          {path:'schedule', label:'跟进时间表', type:'schedule', wide:true}
        ]
      },
      retention: {
        group: '通话后处理', label: '数据保留', description: '设置各类语音数据和任务日志的保留期限。',
        fields: [
          {path:'effective_transcript_days', label:'有效转写保留', type:'number', min:1, step:1, unit:'天'},
          {path:'generated_debug_days', label:'生成调试数据保留', type:'number', min:1, step:1, unit:'天'},
          {path:'reasoning_days', label:'内部说明保留', type:'number', min:1, step:1, unit:'天'},
          {path:'crisis_raw_days', label:'危机原始数据保留', type:'number', min:1, step:1, unit:'天'},
          {path:'job_log_days', label:'任务日志保留', type:'number', min:1, step:1, unit:'天'}
        ]
      }
    },
    script: {
      context_pack: {
        group:'上下文与记忆', label:'上下文组装', description:'控制人格、关系、最近对话和记忆材料的组装预算。',
        fields:[
          {path:'voice_instruction_template',label:'语音指令模板',type:'textarea',wide:true},
          {path:'fallback_template_sections',label:'兜底上下文组成',type:'tags',wide:true},
          {path:'persona_max_chars',label:'人格最大字符数',type:'number',min:1,step:1,unit:'字符'},
          {path:'dynamic_max_chars',label:'动态上下文最大字符数',type:'number',min:1,step:1,unit:'字符'},
          {path:'recent_dialog_max_chars',label:'最近对话最大字符数',type:'number',min:1,step:1,unit:'字符'},
          {path:'memory_max_items',label:'记忆最多条数',type:'number',min:1,step:1,unit:'条'},
          {path:'memory_lookback_days',label:'记忆回看天数',type:'number',min:1,step:1,unit:'天'},
          {path:'build_budget_ms',label:'组装时间预算',type:'number',min:1,step:1,unit:'毫秒'},
          {path:'ready_barrier_enabled',label:'等待上下文就绪',type:'toggle'}
        ]
      },
      call_answer: {
        group:'接听与召回', label:'接听与等待', description:'控制来电响铃、接听等待和失败兜底。',
        fields:[
          {path:'prompt_template',label:'接听提示词',type:'textarea',wide:true},
          {path:'failure_fallback',label:'失败兜底动作',readonly:true,help:'当前契约固定为 answer。'},
          {path:'min_ring_seconds',label:'最短响铃',type:'number',min:1,step:1,unit:'秒'},
          {path:'max_wait_seconds',label:'最大等待',type:'number',min:1,step:1,unit:'秒'},
          {path:'fallback_delay_min_seconds',label:'兜底延迟下限',type:'number',min:1,step:1,unit:'秒'},
          {path:'fallback_delay_max_seconds',label:'兜底延迟上限',type:'number',min:1,step:1,unit:'秒'}
        ]
      },
      recall: {
        group:'接听与召回', label:'记忆召回', description:'设置召回触发词、数量、阈值和超时时间。',
        fields:[
          {path:'prompt_template',label:'召回提示词',type:'textarea',wide:true},
          {path:'trigger_rules',label:'召回触发词',type:'tags',wide:true},
          {path:'max_query_chars',label:'查询最大字符数',type:'number',min:1,step:1,unit:'字符'},
          {path:'top_k',label:'最多召回条数',type:'number',min:1,step:1,unit:'条'},
          {path:'score_threshold',label:'相似度阈值',type:'number',min:0,max:1,step:0.01},
          {path:'timeout_ms',label:'召回总超时',type:'number',min:1,step:1,unit:'毫秒'},
          {path:'embedding_timeout_ms',label:'向量生成超时',type:'number',min:1,step:1,unit:'毫秒'},
          {path:'vector_timeout_ms',label:'向量检索超时',type:'number',min:1,step:1,unit:'毫秒'}
        ]
      },
      memory: {
        group:'上下文与记忆', label:'通话记忆', description:'控制单轮记忆抽取数量和后台任务重试。',
        fields:[
          {path:'prompt_template',label:'记忆抽取提示词',type:'textarea',wide:true},
          {path:'max_items_per_turn',label:'每轮最多记忆条数',type:'number',min:1,step:1,unit:'条'},
          {path:'max_retries',label:'失败重试次数',type:'number',min:0,max:5,step:1,unit:'次'},
          {path:'retry_backoff_ms',label:'重试等待序列',type:'tags-number',wide:true,unit:'毫秒'}
        ]
      },
      summary: {
        group:'总结与跟进', label:'通话总结提示词', description:'通话结束后生成总结卡片和跟进候选的提示词。',
        fields:[{path:'prompt_template',label:'通话总结提示词',type:'textarea',wide:true,rows:18}]
      },
      barge_in: {
        group:'通话体验', label:'打断识别词', description:'区分弱回应、强打断和语义升级连接词。',
        fields:[
          {path:'weak_acknowledgements',label:'弱回应词',type:'tags',wide:true},
          {path:'strong_interruptions',label:'强打断词',type:'tags',wide:true},
          {path:'upgrade_connectors',label:'升级连接词',type:'tags',wide:true}
        ]
      },
      silence_and_exit: {
        group:'通话体验', label:'沉默与结束', description:'控制沉默确认、自动结束和用户恢复说话后的处理。',
        fields:[
          {path:'exit_intent_template',label:'主动结束提示语',type:'textarea',wide:true},
          {path:'silence_timeout_template',label:'沉默超时提示语',type:'textarea',wide:true},
          {path:'silence_confirm_seconds',label:'沉默确认时间',type:'number',min:1,step:1,unit:'秒'},
          {path:'silence_hangup_seconds',label:'沉默挂断时间',type:'number',min:1,step:1,unit:'秒'},
          {path:'user_resume_cancels_exit',label:'恢复说话时取消结束',type:'toggle'}
        ]
      },
      followup: {
        group:'总结与跟进', label:'未接通跟进', description:'角色未接听时向用户说明的文字模板。',
        fields:[{path:'missed_explanation_template',label:'未接通说明',type:'textarea',wide:true}]
      },
      end_reason: {
        group:'结束与安全', label:'结束提示语', description:'按结束原因和连接阶段配置客户端提示。',
        fields:[
          {path:'user_hangup',label:'用户主动挂断',type:'textarea',wide:true},
          {path:'exit_intent',label:'角色识别到结束意图',type:'textarea',wide:true},
          {path:'silence_timeout',label:'沉默超时',type:'textarea',wide:true},
          {path:'quota_exhausted',label:'额度耗尽',type:'textarea',wide:true},
          {path:'hard_limit',label:'达到单通上限',type:'textarea',wide:true},
          {path:'reconnect_timeout',label:'重连超时',type:'textarea',wide:true},
          {path:'provider_error.before_connected',label:'服务商错误 · 接通前',type:'textarea',wide:true},
          {path:'provider_error.after_connected',label:'服务商错误 · 接通后',type:'textarea',wide:true},
          {path:'system_error.before_connected',label:'系统错误 · 接通前',type:'textarea',wide:true},
          {path:'system_error.after_connected',label:'系统错误 · 接通后',type:'textarea',wide:true},
          {path:'user_cancel.show_end_page',label:'取消时显示结束页',readonly:true},
          {path:'user_cancel.action',label:'取消后的动作',readonly:true}
        ]
      },
      reconnect_bridge: {
        group:'结束与安全', label:'重连提示语', description:'通话重连成功后自然衔接上下文。',
        fields:[{path:'success_template',label:'重连成功提示语',type:'textarea',wide:true}]
      },
      crisis: {
        group:'结束与安全', label:'危机干预', description:'危机场景中的通话内提示和通话后资源卡片。',
        fields:[
          {path:'region',label:'适用地区',readonly:true},
          {path:'in_call_banner',label:'通话内危机提示',type:'textarea',wide:true},
          {path:'post_call_resource_card',label:'通话后资源卡片',type:'textarea',wide:true}
        ]
      }
    }
  };
  var KEY_DEFINITIONS = {
    config: {
      configKey: 'voice_call_config',
      label: '运行与安全配置',
      writers: CONFIG_WRITE_ROLES,
      sections: [
        'global', 'persona_ref', 's2s', 'voice', 'quota', 'growth',
        'interaction', 'concurrency', 'summary', 'followup', 'retention', 'capabilities'
      ]
    },
    script: {
      configKey: 'voice_call_script',
      label: '话术与上下文配置',
      writers: SCRIPT_WRITE_ROLES,
      sections: [
        'context_pack', 'memory', 'call_answer', 'recall', 'barge_in',
        'silence_and_exit', 'summary', 'followup', 'end_reason', 'reconnect_bridge', 'crisis'
      ]
    }
  };

  var currentAlias = 'config';
  var currentSection = 'global';
  var voiceTestBusy = false;
  var masterSwitchState = null;
  var pageState = {
    config: emptyKeyState(),
    script: emptyKeyState()
  };

  function emptyKeyState() {
    return {
      bundle: null,
      selectedConfig: null,
      activeConfig: null,
      activeDetail: null,
      activeLoadErrors: [],
      credentialProjection: null,
      history: []
    };
  }

  function clone(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function pretty(value) {
    if (value === undefined) return '（分区不存在）';
    if (value === null) return 'null';
    return JSON.stringify(value, null, 2);
  }

  function display(value, fallback) {
    if (value === null || value === undefined || value === '') return fallback || '-';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return String(value);
  }

  function isPlainObject(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value);
  }

  function sectionUiDefinition(alias, section) {
    return SECTION_UI[alias] && SECTION_UI[alias][section];
  }

  function valueAtPath(source, path) {
    if (!path) return source;
    return String(path).split('.').reduce(function (value, key) {
      return value == null ? undefined : value[key];
    }, source);
  }

  function setValueAtPath(target, path, value) {
    var keys = String(path).split('.');
    var cursor = target;
    keys.slice(0, -1).forEach(function (key) {
      if (!isPlainObject(cursor[key])) cursor[key] = {};
      cursor = cursor[key];
    });
    cursor[keys[keys.length - 1]] = value;
  }

  function currentEditorSectionValue() {
    var editor = document.getElementById('voice-section-json');
    if (currentAlias === 'script' && currentSection === 'summary') {
      return {prompt_template: editor.value};
    }
    return JSON.parse(editor.value);
  }

  function writeEditorSectionValue(value) {
    var editor = document.getElementById('voice-section-json');
    editor.value = currentAlias === 'script' && currentSection === 'summary'
      ? String(value && value.prompt_template || '')
      : pretty(value);
    syncPrimaryFieldFromEditor();
  }

  function capabilityEditableProjection(capabilities) {
    var projected = {};
    CAPABILITY_KEYS.forEach(function (key) {
      var item = isPlainObject(capabilities && capabilities[key]) ? capabilities[key] : {};
      projected[key] = {
        fallback_mode: item.fallback_mode,
        evidence_ttl_days: item.evidence_ttl_days
      };
    });
    return projected;
  }

  function capabilityProjectionIsComplete(capabilities) {
    if (!isPlainObject(capabilities)) return false;
    if (Object.keys(capabilities).length !== CAPABILITY_KEYS.length) return false;
    return CAPABILITY_KEYS.every(function (key) {
      var item = capabilities[key];
      if (!isPlainObject(item)) return false;
      return CAPABILITY_READONLY_FIELDS.concat(CAPABILITY_EDITABLE_FIELDS).every(function (field) {
        return Object.prototype.hasOwnProperty.call(item, field);
      });
    });
  }

  function capabilityEditIssue(field, message, allowed) {
    var issue = {
      code: 'CAPABILITY_EDITABLE_PROJECTION_INVALID',
      field: field,
      message: message
    };
    if (allowed !== undefined) issue.allowed = allowed;
    return issue;
  }

  function buildCapabilitySectionContent(original, editable) {
    var errors = [];
    if (!isPlainObject(editable)) {
      return {
        content: null,
        errors: [capabilityEditIssue('capabilities', '可配置投影必须是 JSON 对象')]
      };
    }
    if (!capabilityProjectionIsComplete(original)) {
      return {
        content: null,
        errors: [capabilityEditIssue(
          'capabilities',
          '当前服务端能力投影结构不完整，已阻止保存；请重新加载'
        )]
      };
    }

    Object.keys(editable).forEach(function (key) {
      if (CAPABILITY_KEYS.indexOf(key) < 0) {
        errors.push(capabilityEditIssue('capabilities.' + key, '未知能力位', CAPABILITY_KEYS));
      }
    });
    CAPABILITY_KEYS.forEach(function (key) {
      var item = editable[key];
      var fieldBase = 'capabilities.' + key;
      if (!isPlainObject(item)) {
        errors.push(capabilityEditIssue(fieldBase, '每项能力的可配置投影必须是 JSON 对象'));
        return;
      }
      Object.keys(item).forEach(function (field) {
        if (CAPABILITY_EDITABLE_FIELDS.indexOf(field) < 0) {
          errors.push(capabilityEditIssue(
            fieldBase + '.' + field,
            '该字段是服务端只读投影，不能通过普通分区编辑器提交',
            CAPABILITY_EDITABLE_FIELDS
          ));
        }
      });
      CAPABILITY_EDITABLE_FIELDS.forEach(function (field) {
        if (!Object.prototype.hasOwnProperty.call(item, field)) {
          errors.push(capabilityEditIssue(
            fieldBase + '.' + field,
            '缺少可配置字段',
            CAPABILITY_EDITABLE_FIELDS
          ));
        }
      });
      if (typeof item.fallback_mode !== 'string' || !item.fallback_mode.trim()) {
        errors.push(capabilityEditIssue(fieldBase + '.fallback_mode', '必须是非空字符串'));
      }
      if (!Number.isInteger(item.evidence_ttl_days) || item.evidence_ttl_days < 7 || item.evidence_ttl_days > 90) {
        errors.push(capabilityEditIssue(
          fieldBase + '.evidence_ttl_days',
          '必须是 7–90 的整数',
          { min: 7, max: 90 }
        ));
      }
    });
    if (errors.length) return { content: null, errors: errors };

    var content = clone(original);
    CAPABILITY_KEYS.forEach(function (key) {
      CAPABILITY_EDITABLE_FIELDS.forEach(function (field) {
        content[key][field] = editable[key][field];
      });
    });
    return { content: content, errors: [] };
  }

  function bundleDiffProjection(state) {
    var meta = state && state.bundle && state.bundle._meta;
    var hasDraft = !!(meta && meta.has_draft);
    return {
      active: clone(state && state.activeConfig),
      draft: hasDraft ? clone(state.selectedConfig) : null,
      hasDraft: hasDraft,
      changedSections: meta && Array.isArray(meta.changed_sections)
        ? meta.changed_sections.slice()
        : []
    };
  }

  function activeBundleLoadFailed(state) {
    var meta = state && state.bundle && state.bundle._meta;
    return !!(meta && meta.base_version > 0 &&
      Array.isArray(state.activeLoadErrors) && state.activeLoadErrors.length);
  }

  function publishBundleBlocked(state) {
    var meta = state && state.bundle && state.bundle._meta;
    if (!meta) return true;
    return meta.base_version > 0 &&
      (activeBundleLoadFailed(state) || !isPlainObject(state.activeConfig));
  }

  function previewJitterValue(rawValue) {
    var text = String(rawValue == null ? '' : rawValue);
    return text === '' ? '' : Number(text);
  }

  function voiceTestPermissions(role, alias, loaded) {
    var ready = alias === 'config' && !!loaded;
    var mayTest = VOICE_TEST_ROLES.indexOf(role) >= 0;
    var mayForce = VOICE_FORCE_TEST_ROLES.indexOf(role) >= 0;
    return {
      connection: ready && mayTest,
      capability: ready && mayTest,
      force: ready && mayForce
    };
  }

  function buildCapabilityTestBody(capabilityKey) {
    return { capability_key: capabilityKey };
  }

  function buildForceTestBody(reason) {
    return {
      effective_scope: 'test',
      confirm_text: 'CONFIRM',
      reason: String(reason == null ? '' : reason).trim()
    };
  }

  function canWrite(alias) {
    var definition = KEY_DEFINITIONS[alias];
    return definition.writers.indexOf(getAdminRole()) >= 0;
  }

  function voiceRequestExtra() {
    return {
      silentErrorToast: true,
      returnErrorResponse: true
    };
  }

  function voiceGet(path) {
    return adminRequest('GET', path, null, false, voiceRequestExtra());
  }

  function voicePost(path, data) {
    return adminRequest('POST', path, data || null, false, voiceRequestExtra());
  }

  function voicePatch(path, data) {
    return adminRequest('PATCH', path, data || null, false, voiceRequestExtra());
  }

  function voiceDelete(path) {
    return adminRequest('DELETE', path, null, false, voiceRequestExtra());
  }

  function extractErrors(result, fallback) {
    var errors = [];
    if (result && result.data && Array.isArray(result.data.errors)) {
      errors = result.data.errors.slice();
    } else if (result && Array.isArray(result.errors)) {
      errors = result.errors.slice();
    } else if (result && Array.isArray(result.detail)) {
      errors = result.detail.map(function (item) {
        return {
          code: 'REQUEST_VALIDATION_ERROR',
          path: Array.isArray(item.loc) ? item.loc.join('.') : 'request',
          message: item.msg || '请求格式不合法'
        };
      });
    }
    if (!errors.length) {
      errors.push({
        code: result && result.data && result.data.error_code
          ? result.data.error_code
          : 'VOICE_CONFIG_REQUEST_FAILED',
        path: 'request',
        message: result && result.message ? result.message : (fallback || '操作失败')
      });
    }
    return errors;
  }

  function allowedText(value) {
    if (value === undefined || value === null) return '';
    if (typeof value === 'string') return value;
    try {
      return JSON.stringify(value);
    } catch (error) {
      return String(value);
    }
  }

  function showInlineErrors(hostId, result, fallback) {
    var host = document.getElementById(hostId);
    if (!host) return;
    var errors = extractErrors(result, fallback);
    host.className = 'alert alert-error voice-inline-errors show';
    host.innerHTML = '<strong>未通过</strong><ul class="voice-error-list">' + errors.map(function (item) {
      var field = item.field || item.path || 'config';
      var allowed = allowedText(item.allowed);
      return '<li><code>' + escapeHtml(field) + '</code> · ' +
        escapeHtml(item.code || 'ERROR') + '：' + escapeHtml(item.message || '校验失败') +
        (allowed ? '；允许范围 <code>' + escapeHtml(allowed) + '</code>' : '') + '</li>';
    }).join('') + '</ul>';
  }

  function showInlineMessage(hostId, message, type) {
    var host = document.getElementById(hostId);
    if (!host) return;
    var alertType = type === 'success' ? 'alert-success' : (type === 'warning' ? 'alert-warning' : 'alert-error');
    host.className = 'alert ' + alertType + ' voice-inline-errors show';
    host.textContent = message;
  }

  function clearInline(hostId) {
    var host = document.getElementById(hostId);
    if (!host) return;
    host.className = 'alert alert-error voice-inline-errors';
    host.textContent = '';
  }

  function stripCredentialProjection(rawConfig) {
    var projected = clone(rawConfig) || {};
    if (projected.s2s && typeof projected.s2s === 'object') {
      delete projected.s2s.credential_configured;
    }
    return projected;
  }

  function captureCredentialProjection(rawConfig) {
    var s2s = rawConfig && rawConfig.s2s && typeof rawConfig.s2s === 'object'
      ? rawConfig.s2s
      : {};
    return {
      credential_configured: !!s2s.credential_configured,
      credential_ref: s2s.credential_ref
    };
  }

  function setPageLoading(loading) {
    var page = document.getElementById('voice-page');
    if (page) page.classList.toggle('voice-loading', !!loading);
  }

  async function loadKey(alias) {
    var definition = KEY_DEFINITIONS[alias];
    var result = await voiceGet('/api/admin/voice/config/' + alias);
    if (!result || result.code !== 0 || !result.data) {
      pageState[alias] = emptyKeyState();
      showInlineErrors('voice-inline-errors', result, definition.label + '加载失败');
      renderCurrentKey();
      return false;
    }

    var rawConfig = result.data.config || {};
    var next = emptyKeyState();
    next.bundle = result.data;
    next.credentialProjection = captureCredentialProjection(rawConfig);
    next.selectedConfig = stripCredentialProjection(rawConfig);

    var meta = result.data._meta || {};
    if (meta.base_version > 0) {
      var activeResult = await voiceGet(
        '/api/admin/voice/config/' + alias + '/history/' + encodeURIComponent(meta.base_version)
      );
      if (activeResult && activeResult.code === 0 && activeResult.data && activeResult.data.config) {
        next.activeDetail = clone(activeResult.data);
        next.activeConfig = stripCredentialProjection(activeResult.data.config);
      } else {
        next.activeLoadErrors = [{
          code: 'VOICE_ACTIVE_BUNDLE_LOAD_FAILED',
          field: 'active_version',
          message: '生效版本 V' + meta.base_version + ' 整包加载失败；已禁用发布，请重新加载'
        }].concat(extractErrors(activeResult, '生效版本整包加载失败'));
      }
    }
    if (!next.activeConfig && !meta.has_draft && !next.activeLoadErrors.length) {
      next.activeConfig = clone(next.selectedConfig);
    }
    pageState[alias] = next;
    clearInline('voice-inline-errors');
    await loadHistory(alias, false);
    renderCurrentKey();
    if (alias === currentAlias && next.activeLoadErrors.length) {
      showInlineErrors('voice-inline-errors', {
        data: { errors: next.activeLoadErrors }
      }, '生效版本整包加载失败');
    }
    return true;
  }

  async function loadHistory(alias, rerender) {
    var result = await voiceGet(
      '/api/admin/voice/config/' + alias + '/history?page=1&page_size=20'
    );
    if (result && result.code === 0 && result.data) {
      pageState[alias].history = Array.isArray(result.data.list) ? result.data.list : [];
    } else {
      pageState[alias].history = [];
      if (alias === currentAlias) showInlineErrors('voice-inline-errors', result, '版本历史加载失败');
    }
    if (rerender !== false && alias === currentAlias) renderHistory();
  }

  async function reloadCurrent() {
    setPageLoading(true);
    try {
      await Promise.all([loadKey(currentAlias), loadMasterSwitch()]);
    } finally {
      setPageLoading(false);
    }
  }

  function renderKeyTabs() {
    document.querySelectorAll('[data-voice-key]').forEach(function (button) {
      var active = button.getAttribute('data-voice-key') === currentAlias;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  }

  function renderMeta() {
    var host = document.getElementById('voice-meta');
    var state = pageState[currentAlias];
    var meta = state.bundle && state.bundle._meta;
    if (!meta) {
      host.innerHTML = '<span class="tag tag-error">配置不可用</span>';
      return;
    }
    var changed = Array.isArray(meta.changed_sections) ? meta.changed_sections : [];
    var activeErrorTag = activeBundleLoadFailed(state)
      ? '<span class="tag tag-error">生效版整包不可用 · 发布已禁用</span>'
      : '';
    host.innerHTML =
      '<span class="tag tag-blue">生效 V' + escapeHtml(meta.base_version) + '</span>' +
      '<span class="tag ' + (meta.has_draft ? 'tag-warning' : 'tag-success') + '">' +
        (meta.has_draft ? '草稿 R' + escapeHtml(meta.draft_revision) : '无草稿') + '</span>' +
      '<span class="tag tag-default">草稿基于 V' + escapeHtml(meta.base_version) + '</span>' +
      '<span class="tag tag-default">变更分区 ' + changed.length + '</span>' +
      activeErrorTag +
      '<span class="tag tag-default">最后发布 ' +
        escapeHtml(state.activeDetail && state.activeDetail.updated_at ? state.activeDetail.updated_at : '尚未发布') + '</span>' +
      '<span class="tag tag-default">操作人 ' +
        escapeHtml(state.activeDetail && state.activeDetail.updated_by ? state.activeDetail.updated_by : '-') + '</span>';

    var note = document.getElementById('voice-role-note');
    if (canWrite(currentAlias) && activeBundleLoadFailed(state)) {
      note.textContent = '生效版本加载失败，发布已禁用；请重新加载后再确认差异。';
    } else if (canWrite(currentAlias)) {
      note.textContent = '当前账号可编辑并发布此配置；权限由服务端校验。';
    } else {
      note.textContent = '当前账号只有查看权限。运行与安全配置由超级管理员或技术运维维护；话术配置由超级管理员或 AI 训练师维护。';
    }
  }

  function rolloutLabel(mode) {
    return {off:'暂停开放', allowlist:'仅指定用户', all:'全部用户'}[mode] || display(mode);
  }

  function renderStatusSummary() {
    var configState = pageState.config || emptyKeyState();
    var activeUnavailable = activeBundleLoadFailed(configState);
    var config = activeUnavailable ? {} : (configState.activeConfig || configState.selectedConfig || {});
    var globalConfig = config.global || {};
    var rollout = globalConfig.rollout || {};
    var ids = Array.isArray(rollout.user_ids) ? rollout.user_ids : [];
    var meta = configState.bundle && configState.bundle._meta;
    document.getElementById('voice-master-summary').textContent = masterSwitchState
      ? (masterSwitchState.enabled ? '已开启' : '已关闭')
      : '状态不可用';
    document.getElementById('voice-rollout-summary').textContent = activeUnavailable ? '状态不可用' : (rollout.mode === 'allowlist'
      ? rolloutLabel(rollout.mode) + ' · ' + ids.length + ' 人'
      : rolloutLabel(rollout.mode));
    document.getElementById('voice-maintenance-summary').textContent = activeUnavailable
      ? '状态不可用' : (globalConfig.maintenance_mode ? '维护中' : '正常');
    var publishedGlobal = meta && meta.base_version > 0 && !activeUnavailable &&
      isPlainObject(configState.activeConfig) ? configState.activeConfig.global : null;
    document.getElementById('voice-ops-summary').textContent = !meta
      ? '状态不可用'
      : meta.base_version === 0
        ? '未发布'
        : publishedGlobal && typeof publishedGlobal.soft_stop === 'boolean'
          ? (publishedGlobal.soft_stop ? '已停止新拨打' : '正常')
          : '状态不可用';
    document.getElementById('voice-ops-link').hidden = VOICE_OPS_READ_ROLES.indexOf(getAdminRole()) < 0;
    var credential = configState.credentialProjection || {};
    document.getElementById('voice-credential-summary').textContent = credential.credential_configured
      ? '已配置'
      : '未配置';
    document.getElementById('voice-version-summary').textContent = meta
      ? ('V' + meta.base_version + (meta.has_draft ? ' · 有草稿' : ' · 已同步'))
      : '配置不可用';

    var warning = document.getElementById('voice-gate-warning');
    var message = '';
    if (masterSwitchState && masterSwitchState.enabled) {
      if (globalConfig.maintenance_mode) message = '总开关已开启，但维护模式正在阻止所有新通话。';
      else if (globalConfig.soft_stop) message = '总开关已开启，但运维软停止正在阻止所有新通话。';
      else if (rollout.mode === 'off') message = '总开关已开启，但当前生效开放范围为“暂停开放”。';
      else if (rollout.mode === 'allowlist' && !ids.length) message = '总开关已开启，但当前生效配置仅允许名单用户且名单为空，所有客户端都会被拦截。';
    }
    warning.textContent = message;
    warning.hidden = !message;
  }

  async function loadMasterSwitch() {
    var result = await voiceGet('/api/admin/voice/master-switch');
    masterSwitchState = result && result.code === 0 && result.data && typeof result.data.enabled === 'boolean'
      ? result.data
      : null;
    renderStatusSummary();
  }

  function fieldDomId(path) {
    return 'voice-field-' + currentAlias + '-' + currentSection + '-' + String(path || 'root').replace(/[^a-zA-Z0-9_-]+/g, '-');
  }

  function fieldLabelHtml(field, id) {
    return '<label for="' + escapeHtml(id) + '">' + escapeHtml(field.label) +
      (field.path ? '<code class="voice-field-key">' + escapeHtml(currentSection + '.' + field.path) + '</code>' : '') +
      '</label>';
  }

  function fieldHelpHtml(field) {
    var details = [];
    if (field.help) details.push(field.help);
    if (field.min !== undefined || field.max !== undefined) {
      details.push('允许范围：' + (field.min !== undefined ? field.min : '不限') + ' ～ ' + (field.max !== undefined ? field.max : '不限'));
    }
    return details.length ? '<p class="voice-field-help">' + escapeHtml(details.join('；')) + '</p>' : '';
  }

  function renderTagEditor(field, value) {
    var values = Array.isArray(value) ? value : [];
    var id = fieldDomId(field.path);
    var chips = values.length ? values.map(function (item, index) {
      return '<span class="voice-tag">' + escapeHtml(item) +
        (field.readonly ? '' : '<button type="button" data-tag-remove="' + index + '" data-tag-path="' + escapeHtml(field.path) + '" aria-label="移除 ' + escapeHtml(item) + '">×</button>') +
        '</span>';
    }).join('') : '<span class="voice-muted">尚未添加</span>';
    return fieldLabelHtml(field, id) + '<div class="voice-tag-editor"><div class="voice-tag-list">' + chips + '</div>' +
      (field.readonly ? '' : '<div class="voice-tag-input-row"><input id="' + escapeHtml(id) + '" class="form-control" type="' + (field.type === 'tags-number' ? 'number' : 'text') + '" data-tag-input="' + escapeHtml(field.path) + '" placeholder="输入后添加"><button type="button" class="btn btn-default" data-key-write data-tag-add="' + escapeHtml(field.path) + '">添加</button></div>') +
      '</div>' + fieldHelpHtml(field);
  }

  function renderCandidates(field, value) {
    var rows = Array.isArray(value) ? value : [];
    var html = rows.map(function (item, index) {
      return '<tr><td><input class="form-control" data-key-write data-candidate-index="' + index + '" data-candidate-field="voice_id" value="' + escapeHtml(item.voice_id || '') + '"></td>' +
        '<td><input class="form-control" data-key-write data-candidate-index="' + index + '" data-candidate-field="voice_version" value="' + escapeHtml(item.voice_version || '') + '"></td>' +
        '<td><input type="checkbox" data-key-write data-candidate-index="' + index + '" data-candidate-field="enabled"' + (item.enabled ? ' checked' : '') + '></td>' +
        '<td><button type="button" class="btn btn-link" data-key-write data-candidate-remove="' + index + '">移除</button></td></tr>';
    }).join('');
    if (!html) html = '<tr><td colspan="4" class="voice-muted">暂无候选音色</td></tr>';
    return fieldLabelHtml(field, fieldDomId(field.path)) + '<div class="voice-collection"><table><thead><tr><th>音色 ID</th><th>版本</th><th>启用</th><th>操作</th></tr></thead><tbody>' + html + '</tbody></table></div>' +
      '<div class="voice-collection-actions"><button type="button" class="btn btn-default" data-key-write data-candidate-add>添加候选音色</button></div>' + fieldHelpHtml(field);
  }

  function renderMapping(field, value) {
    var mapping = isPlainObject(value) ? value : {};
    var keys = Object.keys(mapping);
    var html = keys.map(function (key, index) {
      return '<tr><td><input class="form-control" data-key-write data-mapping-index="' + index + '" data-mapping-field="key" value="' + escapeHtml(key) + '"></td>' +
        '<td><input class="form-control" data-key-write data-mapping-index="' + index + '" data-mapping-field="value" value="' + escapeHtml(mapping[key]) + '"></td>' +
        '<td><button type="button" class="btn btn-link" data-key-write data-mapping-remove="' + index + '">移除</button></td></tr>';
    }).join('');
    if (!html) html = '<tr><td colspan="3" class="voice-muted">没有特殊映射</td></tr>';
    return fieldLabelHtml(field, fieldDomId(field.path)) + '<div class="voice-collection"><table><thead><tr><th>人格标识</th><th>音色 ID</th><th>操作</th></tr></thead><tbody>' + html + '</tbody></table></div>' +
      '<div class="voice-collection-actions"><button type="button" class="btn btn-default" data-key-write data-mapping-add>添加映射</button></div>' + fieldHelpHtml(field);
  }

  function renderSchedule(field, value) {
    var schedule = isPlainObject(value) ? value : {};
    var stages = isPlainObject(schedule.stages) ? schedule.stages : {};
    var stageLabels = {stranger:'陌生人', friend:'朋友', intimate:'亲密', soulmate:'灵魂伴侣'};
    var rows = [];
    Object.keys(stageLabels).forEach(function (stage) {
      var windows = stages[stage] && Array.isArray(stages[stage].windows) ? stages[stage].windows : [];
      windows.forEach(function (windowItem, index) {
        rows.push('<tr><td>' + escapeHtml(stageLabels[stage]) + '<code class="voice-field-key">' + stage + '</code></td>' +
          '<td><input type="time" class="form-control" data-key-write data-schedule-stage="' + stage + '" data-schedule-index="' + index + '" data-schedule-part="start" value="' + escapeHtml(windowItem.start || '') + '"></td>' +
          '<td><input type="time" class="form-control" data-key-write data-schedule-stage="' + stage + '" data-schedule-index="' + index + '" data-schedule-part="end" value="' + escapeHtml(windowItem.end || '') + '"></td>' +
          '<td><button type="button" class="btn btn-link" data-key-write data-schedule-remove="' + stage + ':' + index + '">移除</button></td></tr>');
      });
      rows.push('<tr><td colspan="4"><button type="button" class="btn btn-default btn-sm" data-key-write data-schedule-add="' + stage + '">为' + escapeHtml(stageLabels[stage]) + '添加时间窗</button></td></tr>');
    });
    return fieldLabelHtml(field, fieldDomId(field.path)) +
      '<div class="voice-form-grid mb-16">' +
        '<div class="voice-form-field"><label>时区</label><div class="voice-readonly-value">' + escapeHtml(schedule.timezone || '') + '</div></div>' +
        '<div class="voice-form-field"><label>最大延迟 <code class="voice-field-key">max_delay_hours</code></label><div class="voice-control-with-unit"><input class="form-control" type="number" min="1" step="1" data-key-write data-schedule-field="max_delay_hours" value="' + escapeHtml(schedule.max_delay_hours) + '"><span class="voice-unit">小时</span></div></div>' +
        '<div class="voice-form-field"><label>随机延迟下限 <code class="voice-field-key">jitter_min_minutes</code></label><div class="voice-control-with-unit"><input class="form-control" type="number" min="0" step="1" data-key-write data-schedule-field="jitter_min_minutes" value="' + escapeHtml(schedule.jitter_min_minutes) + '"><span class="voice-unit">分钟</span></div></div>' +
        '<div class="voice-form-field"><label>随机延迟上限 <code class="voice-field-key">jitter_max_minutes</code></label><div class="voice-control-with-unit"><input class="form-control" type="number" min="0" step="1" data-key-write data-schedule-field="jitter_max_minutes" value="' + escapeHtml(schedule.jitter_max_minutes) + '"><span class="voice-unit">分钟</span></div></div>' +
      '</div><div class="voice-collection"><table><thead><tr><th>关系阶段</th><th>开始</th><th>结束</th><th>操作</th></tr></thead><tbody>' + rows.join('') + '</tbody></table></div>' + fieldHelpHtml(field);
  }

  function renderCapabilitiesEditor(field, value) {
    var capabilities = isPlainObject(value) ? value : {};
    var rows = CAPABILITY_KEYS.map(function (key) {
      var item = capabilities[key] || {};
      return '<tr><td><code>' + escapeHtml(key) + '</code></td>' +
        '<td><input class="form-control" data-key-write data-capability-key="' + key + '" data-capability-field="fallback_mode" value="' + escapeHtml(item.fallback_mode || '') + '"></td>' +
        '<td><input class="form-control" type="number" min="7" max="90" step="1" data-key-write data-capability-key="' + key + '" data-capability-field="evidence_ttl_days" value="' + escapeHtml(item.evidence_ttl_days) + '"></td></tr>';
    }).join('');
    return fieldLabelHtml(field, fieldDomId(field.path)) + '<div class="voice-collection"><table><thead><tr><th>能力</th><th>失败回退方式</th><th>证据有效期（天）</th></tr></thead><tbody>' + rows + '</tbody></table></div>' + fieldHelpHtml(field);
  }

  function renderBusinessField(field, sectionValue) {
    var value = valueAtPath(sectionValue, field.path);
    var id = fieldDomId(field.path);
    var classes = 'voice-form-field' + (field.wide ? ' is-wide' : '');
    var condition = field.showWhen
      ? ' data-show-path="' + escapeHtml(field.showWhen.path) + '" data-show-value="' + escapeHtml(field.showWhen.value) + '"'
      : '';
    var content = '';
    if (field.type === 'tags' || field.type === 'tags-number') content = renderTagEditor(field, value);
    else if (field.type === 'candidates') content = renderCandidates(field, value);
    else if (field.type === 'mapping') content = renderMapping(field, value);
    else if (field.type === 'schedule') content = renderSchedule(field, value);
    else if (field.type === 'capabilities') content = renderCapabilitiesEditor(field, value);
    else if (field.readonly) {
      var readonlyText = typeof value === 'boolean' ? (value ? '已开启' : '已关闭') : display(value);
      content = fieldLabelHtml(field, id) + '<div id="' + escapeHtml(id) + '" class="voice-readonly-value">' + escapeHtml(readonlyText) + '</div>' + fieldHelpHtml(field);
    } else if (field.type === 'toggle') {
      content = fieldLabelHtml(field, id) + '<div class="voice-switch-row"><span class="voice-switch"><input id="' + escapeHtml(id) + '" type="checkbox" data-key-write data-voice-field="' + escapeHtml(field.path) + '"' + (value ? ' checked' : '') + '><label class="voice-switch-track" for="' + escapeHtml(id) + '" aria-hidden="true"></label></span><span>' + (value ? '已开启' : '已关闭') + '</span></div>' + fieldHelpHtml(field);
    } else if (field.type === 'select') {
      content = fieldLabelHtml(field, id) + '<select id="' + escapeHtml(id) + '" class="form-control" data-key-write data-voice-field="' + escapeHtml(field.path) + '">' + (field.options || []).map(function (option) {
        return '<option value="' + escapeHtml(option[0]) + '"' + (String(value) === String(option[0]) ? ' selected' : '') + '>' + escapeHtml(option[1]) + '</option>';
      }).join('') + '</select>' + fieldHelpHtml(field);
    } else {
      var tag = field.type === 'textarea' ? 'textarea' : 'input';
      var attributes = ' id="' + escapeHtml(id) + '" class="form-control" data-key-write data-voice-field="' + escapeHtml(field.path) + '"';
      if (tag === 'input') attributes += ' type="' + (field.type === 'number' ? 'number' : 'text') + '" value="' + escapeHtml(value) + '"';
      if (field.min !== undefined) attributes += ' min="' + escapeHtml(field.min) + '"';
      if (field.max !== undefined) attributes += ' max="' + escapeHtml(field.max) + '"';
      if (field.step !== undefined) attributes += ' step="' + escapeHtml(field.step) + '"';
      if (tag === 'textarea') attributes += ' rows="' + escapeHtml(field.rows || 4) + '"';
      var control = tag === 'textarea' ? '<textarea' + attributes + '>' + escapeHtml(value) + '</textarea>' : '<input' + attributes + '>';
      content = fieldLabelHtml(field, id) + (field.unit ? '<div class="voice-control-with-unit">' + control + '<span class="voice-unit">' + escapeHtml(field.unit) + '</span></div>' : control) + fieldHelpHtml(field);
    }
    return '<div class="' + classes + '"' + condition + '>' + content + '</div>';
  }

  function updateConditionalFields(sectionValue) {
    document.querySelectorAll('#voice-business-form [data-show-path]').forEach(function (field) {
      field.hidden = String(valueAtPath(sectionValue, field.getAttribute('data-show-path'))) !== field.getAttribute('data-show-value');
    });
  }

  function renderFormWarning(sectionValue) {
    var host = document.getElementById('voice-form-warning');
    var message = '';
    if (currentAlias === 'config' && currentSection === 'global') {
      var rollout = sectionValue && sectionValue.rollout || {};
      if (rollout.mode === 'allowlist' && (!Array.isArray(rollout.user_ids) || !rollout.user_ids.length)) {
        message = '当前草稿选择“仅指定用户”，但开放名单为空；发布后所有客户端都会被拦截。';
      } else if (rollout.mode === 'off') {
        message = '当前草稿会暂停所有新通话，即使语音总开关保持开启。';
      }
    }
    host.textContent = message;
    host.hidden = !message;
  }

  function syncCandidateRows(sectionValue) {
    var rows = {};
    document.querySelectorAll('#voice-business-form [data-candidate-index]').forEach(function (input) {
      var index = Number(input.getAttribute('data-candidate-index'));
      var field = input.getAttribute('data-candidate-field');
      if (!rows[index]) rows[index] = {};
      rows[index][field] = field === 'enabled' ? input.checked : input.value;
    });
    sectionValue.candidates = Object.keys(rows).sort(function (a, b) { return Number(a) - Number(b); }).map(function (index) { return rows[index]; });
  }

  function syncMappingRows(sectionValue) {
    var rows = {};
    document.querySelectorAll('#voice-business-form [data-mapping-index]').forEach(function (input) {
      var index = input.getAttribute('data-mapping-index');
      if (!rows[index]) rows[index] = {};
      rows[index][input.getAttribute('data-mapping-field')] = input.value;
    });
    var mapping = {};
    Object.keys(rows).forEach(function (index) {
      if (rows[index].key) mapping[rows[index].key] = rows[index].value || '';
    });
    sectionValue.persona_mapping = mapping;
  }

  function syncScheduleRows(sectionValue) {
    var schedule = clone(sectionValue.schedule) || {timezone:'Asia/Shanghai', stages:{}};
    schedule.stages = {};
    ['stranger','friend','intimate','soulmate'].forEach(function (stage) { schedule.stages[stage] = {windows:[]}; });
    document.querySelectorAll('#voice-business-form [data-schedule-field]').forEach(function (input) {
      schedule[input.getAttribute('data-schedule-field')] = input.value === '' ? '' : Number(input.value);
    });
    document.querySelectorAll('#voice-business-form [data-schedule-stage]').forEach(function (input) {
      var stage = input.getAttribute('data-schedule-stage');
      var index = Number(input.getAttribute('data-schedule-index'));
      var part = input.getAttribute('data-schedule-part');
      if (!schedule.stages[stage].windows[index]) schedule.stages[stage].windows[index] = {};
      schedule.stages[stage].windows[index][part] = input.value;
    });
    sectionValue.schedule = schedule;
  }

  function syncCapabilityRows(sectionValue) {
    document.querySelectorAll('#voice-business-form [data-capability-key]').forEach(function (input) {
      var key = input.getAttribute('data-capability-key');
      var field = input.getAttribute('data-capability-field');
      if (!isPlainObject(sectionValue[key])) sectionValue[key] = {};
      sectionValue[key][field] = field === 'evidence_ttl_days' ? Number(input.value) : input.value;
    });
  }

  function rerenderBusinessForm(sectionValue) {
    writeEditorSectionValue(sectionValue);
    renderBusinessForm();
    applyKeyPermissions();
  }

  function bindBusinessForm(sectionValue) {
    var host = document.getElementById('voice-business-form');
    host.querySelectorAll('[data-voice-field]').forEach(function (input) {
      var handler = function () {
        var value = input.type === 'checkbox' ? input.checked :
          (input.type === 'number' ? (input.value === '' ? '' : Number(input.value)) : input.value);
        setValueAtPath(sectionValue, input.getAttribute('data-voice-field'), value);
        writeEditorSectionValue(sectionValue);
        updateConditionalFields(sectionValue);
        renderFormWarning(sectionValue);
        if (input.type === 'checkbox') {
          var label = input.closest('.voice-switch-row').querySelector('span:last-child');
          if (label) label.textContent = input.checked ? '已开启' : '已关闭';
        }
      };
      input.addEventListener(input.tagName === 'SELECT' || input.type === 'checkbox' ? 'change' : 'input', handler);
    });
    host.querySelectorAll('[data-tag-add]').forEach(function (button) {
      button.onclick = function () {
        var path = button.getAttribute('data-tag-add');
        var input = host.querySelector('[data-tag-input="' + path + '"]');
        var raw = String(input.value || '').trim();
        if (!raw) return;
        var list = valueAtPath(sectionValue, path);
        if (!Array.isArray(list)) list = [];
        var value = input.type === 'number' ? Number(raw) : raw;
        if (input.type === 'number' && !Number.isInteger(value)) return;
        if (list.indexOf(value) < 0) list.push(value);
        setValueAtPath(sectionValue, path, list);
        rerenderBusinessForm(sectionValue);
      };
    });
    host.querySelectorAll('[data-tag-input]').forEach(function (input) {
      input.onkeydown = function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          var button = host.querySelector('[data-tag-add="' + input.getAttribute('data-tag-input') + '"]');
          if (button) button.click();
        }
      };
    });
    host.querySelectorAll('[data-tag-remove]').forEach(function (button) {
      button.onclick = function () {
        var path = button.getAttribute('data-tag-path');
        var list = valueAtPath(sectionValue, path);
        if (Array.isArray(list)) list.splice(Number(button.getAttribute('data-tag-remove')), 1);
        rerenderBusinessForm(sectionValue);
      };
    });
    host.querySelectorAll('[data-candidate-index]').forEach(function (input) {
      input.addEventListener(input.type === 'checkbox' ? 'change' : 'input', function () { syncCandidateRows(sectionValue); writeEditorSectionValue(sectionValue); });
    });
    host.querySelector('[data-candidate-add]') && (host.querySelector('[data-candidate-add]').onclick = function () {
      if (!Array.isArray(sectionValue.candidates)) sectionValue.candidates = [];
      sectionValue.candidates.push({voice_id:'', voice_version:sectionValue.voice_version || '', enabled:true});
      rerenderBusinessForm(sectionValue);
    });
    host.querySelectorAll('[data-candidate-remove]').forEach(function (button) { button.onclick = function () { sectionValue.candidates.splice(Number(button.getAttribute('data-candidate-remove')), 1); rerenderBusinessForm(sectionValue); }; });
    host.querySelectorAll('[data-mapping-index]').forEach(function (input) { input.addEventListener('input', function () { syncMappingRows(sectionValue); writeEditorSectionValue(sectionValue); }); });
    host.querySelector('[data-mapping-add]') && (host.querySelector('[data-mapping-add]').onclick = function () { var mapping = sectionValue.persona_mapping || {}; var key = 'new_key'; var index = 1; while (Object.prototype.hasOwnProperty.call(mapping, key)) key = 'new_key_' + (++index); mapping[key] = ''; sectionValue.persona_mapping = mapping; rerenderBusinessForm(sectionValue); });
    host.querySelectorAll('[data-mapping-remove]').forEach(function (button) { button.onclick = function () { var keys = Object.keys(sectionValue.persona_mapping || {}); delete sectionValue.persona_mapping[keys[Number(button.getAttribute('data-mapping-remove'))]]; rerenderBusinessForm(sectionValue); }; });
    host.querySelectorAll('[data-schedule-field],[data-schedule-stage]').forEach(function (input) { input.addEventListener('input', function () { syncScheduleRows(sectionValue); writeEditorSectionValue(sectionValue); }); });
    host.querySelectorAll('[data-schedule-add]').forEach(function (button) { button.onclick = function () { var stage = button.getAttribute('data-schedule-add'); var windows = sectionValue.schedule.stages[stage].windows; windows.push({start:'09:00',end:'21:00'}); rerenderBusinessForm(sectionValue); }; });
    host.querySelectorAll('[data-schedule-remove]').forEach(function (button) { button.onclick = function () { var parts = button.getAttribute('data-schedule-remove').split(':'); sectionValue.schedule.stages[parts[0]].windows.splice(Number(parts[1]),1); rerenderBusinessForm(sectionValue); }; });
    host.querySelectorAll('[data-capability-key]').forEach(function (input) { input.addEventListener('input', function () { syncCapabilityRows(sectionValue); writeEditorSectionValue(sectionValue); }); });
  }

  function renderBusinessForm() {
    var host = document.getElementById('voice-business-form');
    var definition = sectionUiDefinition(currentAlias, currentSection);
    if (!definition) {
      host.innerHTML = '<div class="voice-form-intro">当前分区尚未表单化，请使用下方高级配置。</div>';
      return;
    }
    var sectionValue;
    try {
      sectionValue = currentEditorSectionValue();
    } catch (error) {
      host.innerHTML = '<div class="alert alert-error">原始 JSON 当前无法解析，修复后才能恢复业务表单。</div>';
      return;
    }
    host.innerHTML = '<div class="voice-form-intro">' + escapeHtml(definition.description) + '</div><div class="voice-form-grid">' +
      definition.fields.map(function (field) { return renderBusinessField(field, sectionValue); }).join('') + '</div>';
    updateConditionalFields(sectionValue);
    renderFormWarning(sectionValue);
    bindBusinessForm(sectionValue);
  }

  function renderSupplementCards() {
    document.getElementById('voice-o01-panel').hidden = !(currentAlias === 'config' && currentSection === 'capabilities');
    document.getElementById('voice-credential-card').style.display = currentAlias === 'config' && currentSection === 's2s' ? '' : 'none';
    document.getElementById('voice-capabilities-card').style.display = currentAlias === 'config' && currentSection === 'capabilities' ? '' : 'none';
    document.getElementById('voice-followup-card').style.display = currentAlias === 'config' && currentSection === 'followup' ? '' : 'none';
  }

  function renderSections() {
    var definition = KEY_DEFINITIONS[currentAlias];
    var state = pageState[currentAlias];
    var meta = state.bundle && state.bundle._meta;
    var changed = meta && Array.isArray(meta.changed_sections) ? meta.changed_sections : [];
    if (definition.sections.indexOf(currentSection) < 0) currentSection = definition.sections[0];
    if (changed.length && definition.sections.indexOf(currentSection) < 0) currentSection = changed[0];

    var host = document.getElementById('voice-section-list');
    host.innerHTML = '';
    var lastGroup = null;
    definition.sections.forEach(function (section) {
      var ui = sectionUiDefinition(currentAlias, section) || {};
      if (ui.group && ui.group !== lastGroup) {
        var group = document.createElement('div');
        group.className = 'voice-section-group';
        group.textContent = ui.group;
        host.appendChild(group);
        lastGroup = ui.group;
      }
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'voice-section-button';
      button.setAttribute('data-voice-section', section);
      if (section === currentSection) button.classList.add('active');
      if (changed.indexOf(section) >= 0) button.classList.add('is-changed');
      button.textContent = PRIMARY_FIELD_DEFINITIONS[section]
        ? PRIMARY_FIELD_DEFINITIONS[section].sectionLabel
        : (ui.label || section);
      button.onclick = function () {
        currentSection = section;
        clearInline('voice-inline-errors');
        renderSections();
        renderEditor();
        renderDiff();
        renderSupplementCards();
        applyKeyPermissions();
      };
      host.appendChild(button);
    });
  }

  function renderPrimaryField() {
    var panel = document.getElementById('voice-primary-field-panel');
    var input = document.getElementById('voice-primary-field-input');
    var definition = currentAlias === 'config'
      ? PRIMARY_FIELD_DEFINITIONS[currentSection]
      : null;
    panel.hidden = !definition;
    if (!definition) {
      input.value = '';
      input.removeAttribute('data-voice-field');
      return;
    }
    input.setAttribute('data-voice-field', definition.field);
    document.getElementById('voice-primary-field-label').textContent = definition.label;
    document.getElementById('voice-primary-field-help').textContent = definition.help;
    try {
      var sectionValue = JSON.parse(document.getElementById('voice-section-json').value);
      input.value = sectionValue && typeof sectionValue[definition.field] === 'string'
        ? sectionValue[definition.field]
        : '';
    } catch (error) {
      input.value = '';
    }
  }

  function syncPrimaryFieldToEditor() {
    var definition = currentAlias === 'config'
      ? PRIMARY_FIELD_DEFINITIONS[currentSection]
      : null;
    if (!definition) return;
    var editor = document.getElementById('voice-section-json');
    var sectionValue;
    try {
      sectionValue = JSON.parse(editor.value);
    } catch (error) {
      showInlineErrors('voice-inline-errors', {
        data: { errors: [{
          code: 'JSON_PARSE_ERROR',
          path: currentSection,
          message: '请先修复分区 JSON，再编辑 ' + definition.label
        }] }
      }, 'JSON 无法解析');
      return;
    }
    if (!sectionValue || typeof sectionValue !== 'object' || Array.isArray(sectionValue)) return;
    sectionValue[definition.field] = document.getElementById('voice-primary-field-input').value;
    editor.value = pretty(sectionValue);
  }

  function syncPrimaryFieldFromEditor() {
    var definition = currentAlias === 'config'
      ? PRIMARY_FIELD_DEFINITIONS[currentSection]
      : null;
    if (!definition) return;
    try {
      var sectionValue = JSON.parse(document.getElementById('voice-section-json').value);
      if (sectionValue && typeof sectionValue[definition.field] === 'string') {
        document.getElementById('voice-primary-field-input').value = sectionValue[definition.field];
      }
    } catch (error) {
      // JSON 编辑过程中允许暂时不完整；保存时统一显示解析错误。
    }
  }

  function renderEditor() {
    var state = pageState[currentAlias];
    var meta = state.bundle && state.bundle._meta;
    var changed = meta && Array.isArray(meta.changed_sections) ? meta.changed_sections : [];
    var uiDefinition = sectionUiDefinition(currentAlias, currentSection) || {};
    document.getElementById('voice-section-title').textContent = PRIMARY_FIELD_DEFINITIONS[currentSection]
      ? PRIMARY_FIELD_DEFINITIONS[currentSection].sectionLabel
      : (uiDefinition.label || currentSection);
    var changeTag = document.getElementById('voice-section-change');
    var isChanged = changed.indexOf(currentSection) >= 0;
    changeTag.className = 'tag ' + (isChanged ? 'tag-warning' : 'tag-default');
    changeTag.textContent = isChanged ? '草稿已变更' : '与生效版一致';
    var sectionValue = state.selectedConfig ? clone(state.selectedConfig[currentSection]) : undefined;
    var note = document.getElementById('voice-editor-note');
    if (currentAlias === 'config' && currentSection === 'global') {
      sectionValue = Object.assign({}, sectionValue);
      delete sectionValue.enabled;
      note.hidden = false;
      note.textContent = '语音通话总开关请前往独立的「总开关」页面操作。';
    } else if (currentAlias === 'config' && currentSection === 'capabilities') {
      sectionValue = capabilityEditableProjection(sectionValue);
      note.hidden = false;
      note.textContent = '仅可编辑 fallback_mode 与 evidence_ttl_days（7–90）。状态、启用范围、六维指纹及证据结果均为服务端只读投影，保存时只会原样合并，不会进入普通编辑 JSON。';
    } else if (currentAlias === 'script' && currentSection === 'crisis') {
      note.hidden = false;
      note.textContent = '这里配置通话内提示与通话后资源卡片。危机检测关键词在「内容安全 → 危机干预关键词」独立发布。';
      if (['super_admin', 'ai_trainer', 'observer'].indexOf(getAdminRole()) >= 0) {
        var link = document.createElement('a');
        link.href = '/admin/pages/safety-rules.html#crisis';
        link.textContent = ' 查看危机词与发布状态';
        note.appendChild(link);
      } else {
        note.textContent += ' 请联系超级管理员或 AI 训练师确认词库状态。';
      }
    } else if (currentAlias === 'config' && currentSection === 'interaction') {
      note.hidden = false;
      if (sectionValue === undefined) sectionValue = {};
      note.textContent = '测试默认：vad_rms_threshold 0.015（0.001–0.2）；candidate_ms 200（180–250）；sustained_ms 600（250–2000 且大于候选窗口）；post_playback_buffer_ms 800（0–3000，实际播放结束后的挂断缓冲）；goodbye_timeout_ms 10000（1000–30000）；time_low_seconds 60（1–300）。时间字段单位见名称。VAD 待真机校准。发布/回滚后仅新通话采用，旧通话保留快照；旧配置缺省可兼容读取，不自动发布。';
    } else if (currentSection === 'summary') {
      note.hidden = false;
      if (sectionValue === undefined) {
        var defaults = state.bundle && state.bundle._meta && state.bundle._meta.section_defaults;
        sectionValue = defaults && defaults.summary;
      }
      note.textContent = currentAlias === 'script'
        ? '通话结束后的总结卡片提示词，可直接编辑多行文本。保存为草稿，校验并发布后仅新通话采用；缺省时使用规范默认提示词。'
        : '使用 env 中的 DeepSeek 地址与密钥；这里只配置模型标识。发布后仅新通话采用，不修改其他 LLM 节点。';
    } else if (currentAlias === 'script' && currentSection === 'memory') {
      note.hidden = false;
      note.textContent = '每任务自动重试 max_retries 为 0–5 次（不含首次执行），默认 2；retry_backoff_ms 默认 [1000,5000]，须与次数等长、非递减，每项 100–60000 毫秒。定时任务领取到期任务，重试沿用首次抽取结果。发布后仅新通话采用，旧配置不自动改写。';
    } else if (currentAlias === 'config' && currentSection === 'concurrency') {
      note.hidden = false;
      note.textContent = '连接参数（毫秒）：heartbeat_interval_ms 1000–10000，user_lock_ttl_ms 10000–60000 且至少为心跳的 3 倍，reconnect_timeout_ms 1000–60000，call_ticket_ttl_ms 5000–60000。旧版本缺省分别为 5000、15000、15000、30000；这是测试阶段默认值。发布后仅新通话采用，当前编辑不会自动补写旧配置。';
    } else {
      note.hidden = true;
      note.textContent = '';
    }
    document.getElementById('voice-section-json').setAttribute('aria-label', currentAlias === 'script' && currentSection === 'summary' ? '通话总结提示词' : '分区 JSON');
    document.getElementById('voice-section-json').value = currentAlias === 'script' && currentSection === 'summary'
      ? (sectionValue && sectionValue.prompt_template || '') : pretty(sectionValue);
    renderPrimaryField();
    renderBusinessForm();
    renderSupplementCards();
  }

  function renderChangedSections() {
    var host = document.getElementById('voice-changed-sections');
    var meta = pageState[currentAlias].bundle && pageState[currentAlias].bundle._meta;
    var changed = meta && Array.isArray(meta.changed_sections) ? meta.changed_sections : [];
    if (!changed.length) {
      host.innerHTML = '<span class="tag tag-default">无分区差异</span>';
      return;
    }
    host.innerHTML = changed.map(function (section) {
      return '<span class="tag tag-warning" style="margin-left:4px">' + escapeHtml(section) + '</span>';
    }).join('');
  }

  function renderDiff() {
    var projection = bundleDiffProjection(pageState[currentAlias]);
    document.getElementById('voice-active-json').textContent = activeBundleLoadFailed(
      pageState[currentAlias]
    )
      ? '（生效版本整包加载失败，发布已禁用）'
      : pretty(projection.active);
    document.getElementById('voice-draft-json').textContent = projection.hasDraft
      ? pretty(projection.draft)
      : '（当前没有草稿）';
    renderChangedSections();
  }

  function appendKeyValue(host, label, value, className) {
    var item = document.createElement('div');
    item.className = 'voice-kv' + (className ? ' ' + className : '');
    var title = document.createElement('div');
    title.className = 'voice-kv-label';
    title.textContent = label;
    var body = document.createElement('div');
    body.className = 'voice-kv-value';
    body.textContent = display(value);
    item.appendChild(title);
    item.appendChild(body);
    host.appendChild(item);
  }

  function renderCredential() {
    var card = document.getElementById('voice-credential-card');
    card.style.display = currentAlias === 'config' && currentSection === 's2s' ? '' : 'none';
    if (currentAlias !== 'config' || currentSection !== 's2s') return;
    var host = document.getElementById('voice-credential-grid');
    host.innerHTML = '';
    var projection = pageState.config.credentialProjection || {};
    appendKeyValue(host, 'credential_configured', projection.credential_configured ? '已配置' : '未配置');
    if (['super_admin', 'tech_ops'].indexOf(getAdminRole()) >= 0) {
      appendKeyValue(host, 'credential_ref（非敏感引用）', projection.credential_ref, 'voice-hash');
    } else {
      appendKeyValue(host, 'credential_ref', '按角色隐藏（仅 super_admin / tech_ops 可见）');
      appendKeyValue(host, '凭据值', '后端永不返回');
    }
  }

  function capabilityTag(value, truthyClass, falseClass) {
    return '<span class="tag ' + (value ? truthyClass : falseClass) + '">' +
      escapeHtml(value ? 'on' : 'off') + '</span>';
  }

  function renderCapabilities() {
    var card = document.getElementById('voice-capabilities-card');
    card.style.display = currentAlias === 'config' && currentSection === 'capabilities' ? '' : 'none';
    if (currentAlias !== 'config' || currentSection !== 'capabilities') return;
    var host = document.getElementById('voice-capability-grid');
    host.innerHTML = '';
    var config = pageState.config.selectedConfig || {};
    var capabilities = config.capabilities || {};
    var evidencedCount = 0;
    CAPABILITY_KEYS.forEach(function (key) {
      var item = capabilities[key] || {};
      var status = item.verification_status || 'unverified';
      var statusLabel = {unverified: '未验证', verified: '已验证', stale: '证据已过期或失效', failed: '验证失败'}[status] || '未知验证状态';
      var scope = item.effective_scope || 'off';
      var hasEvidence = typeof item.evidence_report_id === 'string' && !!item.evidence_report_id;
      if (hasEvidence) evidencedCount += 1;
      var cardEl = document.createElement('article');
      cardEl.className = 'voice-capability-card';
      if (status !== 'verified' || scope === 'off' || !item.enabled) cardEl.classList.add('is-unverified');
      cardEl.innerHTML =
        '<div class="voice-capability-name">' + escapeHtml(key) + '</div>' +
        '<div class="voice-capability-state">' +
          '<span class="tag ' + (status === 'verified' ? 'tag-success' : 'tag-warning') + '" title="' + escapeHtml(status) + '">' + statusLabel + '</span>' +
          '<span class="tag ' + (scope === 'off' ? 'tag-error' : 'tag-blue') + '">' + escapeHtml(scope) + '</span>' +
          capabilityTag(!!item.enabled, 'tag-success', 'tag-error') +
        '</div>' +
        '<dl class="voice-capability-detail">' +
          '<dt>fallback_mode</dt><dd>' + escapeHtml(display(item.fallback_mode)) + '</dd>' +
          '<dt>forced_enabled</dt><dd>' + escapeHtml(display(item.forced_enabled, 'false')) + '</dd>' +
          '<dt>last_test_result</dt><dd>' + escapeHtml(display(item.last_test_result, 'not_run')) + '</dd>' +
          '<dt>evidence_ttl_days</dt><dd>' + escapeHtml(display(item.evidence_ttl_days)) + '</dd>' +
          '<dt>verified_at</dt><dd>' + escapeHtml(display(item.verified_at)) + '</dd>' +
          '<dt>expires_at</dt><dd>' + escapeHtml(display(item.expires_at)) + '</dd>' +
          '<dt>evidence_report_id</dt><dd>' + escapeHtml(display(item.evidence_report_id)) + '</dd>' +
        '</dl>' +
        (hasEvidence
          ? '<button type="button" class="btn btn-default btn-sm mt-8" data-capability-evidence="' +
            escapeHtml(item.evidence_report_id) + '">查看证据投影</button>'
          : '');
      host.appendChild(cardEl);
    });
    var summary = document.getElementById('voice-capability-summary');
    summary.textContent = '已取证 ' + evidencedCount + ' / ' + CAPABILITY_KEYS.length;
    summary.className = 'tag ' + (evidencedCount === CAPABILITY_KEYS.length ? 'tag-success' : 'tag-warning');
    host.querySelectorAll('[data-capability-evidence]').forEach(function (button) {
      button.onclick = function () {
        viewCapabilityEvidence(button.getAttribute('data-capability-evidence'));
      };
    });
  }

  function renderPreviewVisibility() {
    var card = document.getElementById('voice-followup-card');
    card.style.display = currentAlias === 'config' && currentSection === 'followup' ? '' : 'none';
    if (currentAlias !== 'config' || currentSection !== 'followup') {
      clearInline('voice-preview-errors');
      document.getElementById('voice-preview-result').classList.remove('show');
    }
  }

  function renderHistory() {
    var state = pageState[currentAlias];
    var tbody = document.getElementById('voice-history-body');
    var rows = state.history || [];
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="voice-history-empty">暂无历史版本</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(function (item) {
      var rollbackButton = canWrite(currentAlias)
        ? '<button type="button" class="btn btn-danger btn-sm" data-write-action data-voice-rollback="' + escapeHtml(item.version) + '">回滚</button>'
        : '';
      return '<tr>' +
        '<td>V' + escapeHtml(item.version) + '</td>' +
        '<td>' + escapeHtml(display(item.schema_version)) + '</td>' +
        '<td><span class="tag ' + (item.is_active ? 'tag-success' : 'tag-default') + '">' +
          (item.is_active ? '生效中' : '历史') + '</span></td>' +
        '<td class="voice-hash">' + escapeHtml(item.content_sha256 || '-') + '</td>' +
        '<td>' + escapeHtml(display(item.updated_by)) + '</td>' +
        '<td>' + escapeHtml(display(item.updated_at)) + '</td>' +
        '<td><div class="voice-history-actions">' +
          '<button type="button" class="btn btn-default btn-sm" data-voice-view="' + escapeHtml(item.version) + '">查看</button>' +
          rollbackButton +
        '</div></td>' +
      '</tr>';
    }).join('');

    tbody.querySelectorAll('[data-voice-view]').forEach(function (button) {
      button.onclick = function () {
        viewHistoryDetail(parseInt(button.getAttribute('data-voice-view'), 10));
      };
    });
    tbody.querySelectorAll('[data-voice-rollback]').forEach(function (button) {
      button.onclick = function () {
        rollbackVersion(parseInt(button.getAttribute('data-voice-rollback'), 10));
      };
    });
    applyObserverReadOnly(tbody);
  }

  function applyVoiceTestPermissions() {
    var loaded = !!(pageState.config && pageState.config.bundle);
    var permissions = voiceTestPermissions(getAdminRole(), currentAlias, loaded);
    var controls = {
      connection: document.getElementById('btn-voice-test-connection'),
      capability: document.getElementById('btn-voice-test-capability'),
      force: document.getElementById('btn-voice-force-capability')
    };
    Object.keys(controls).forEach(function (key) {
      var control = controls[key];
      control.disabled = voiceTestBusy || !permissions[key];
      control.setAttribute('aria-disabled', control.disabled ? 'true' : 'false');
    });
    var playback = document.getElementById('btn-voice-playback');
    if (playback) playback.disabled = voiceTestBusy || !permissions.connection;

    var capabilitySelect = document.getElementById('voice-test-capability-select');
    capabilitySelect.disabled = voiceTestBusy || !(permissions.capability || permissions.force);
    capabilitySelect.setAttribute(
      'aria-disabled', capabilitySelect.disabled ? 'true' : 'false'
    );

    var note = document.getElementById('voice-test-role-note');
    if (voiceTestBusy) {
      note.textContent = '联调请求执行中；短生命周期 runner 结束前已暂时禁用重复操作。';
    } else if (currentAlias !== 'config') {
      note.textContent = '联调动作只读取 voice_call_config；请切换到“运行与安全配置”。';
    } else if (!loaded) {
      note.textContent = 'voice_call_config 尚未成功加载，联调动作保持安全禁用。';
    } else if (!permissions.connection) {
      note.textContent = '当前角色无联调权限：短连接/能力测试仅 super_admin、tech_ops；强制 test 仅 super_admin。';
    } else if (!permissions.force) {
      note.textContent = 'tech_ops 可执行短连接与能力测试；强制 test 仅 super_admin。';
    } else {
      note.textContent = 'super_admin 可执行连接、能力、强制验证及纯播放诊断；后端 RBAC 仍是最终权限边界。';
    }
  }

  function setVoiceTestBusy(busy) {
    voiceTestBusy = !!busy;
    applyVoiceTestPermissions();
  }
  window.addEventListener('voice-admin-playback-busy', function (event) {
    setVoiceTestBusy(event.detail === true);
  });

  function renderVoiceTestResult(kind, data) {
    var host = document.getElementById('voice-test-result-grid');
    var kindHost = document.getElementById('voice-test-result-kind');
    var fields;
    host.innerHTML = '';

    if (kind === 'force') {
      fields = [
        'config_key', 'capability_key', 'base_version',
        'draft_revision', 'content_sha256'
      ];
      kindHost.textContent = '强制 test 已写入草稿';
      kindHost.className = 'tag tag-warning';
    } else {
      fields = [
        'status', 'latency_ms', 'failure_category', 'test_version',
        'tested_draft_revision', 'tested_at'
      ];
      if (kind === 'capability') {
        fields = fields.concat([
          'capability_key', 'evidence_run_id', 'evidence_report_id'
        ]);
      }
      kindHost.textContent = kind === 'capability' ? '单能力测试' : '短连接测试';
      kindHost.className = 'tag ' + (data && data.status === 'passed'
        ? 'tag-success'
        : 'tag-warning');
    }

    fields.forEach(function (field) {
      appendKeyValue(host, field, data && data[field]);
    });
  }

  function applyKeyPermissions() {
    var writable = canWrite(currentAlias);
    document.querySelectorAll('[data-key-write]').forEach(function (control) {
      control.disabled = !writable;
      control.setAttribute('aria-disabled', writable ? 'false' : 'true');
    });
    var editor = document.getElementById('voice-section-json');
    editor.readOnly = !writable;
    editor.setAttribute('aria-readonly', editor.readOnly ? 'true' : 'false');
    if (editor.readOnly) editor.classList.add('observer-control-readonly');
    else if (!isObserver()) editor.classList.remove('observer-control-readonly');
    var saveButton = document.getElementById('btn-voice-save-section');
    saveButton.disabled = !writable;
    saveButton.setAttribute('aria-disabled', saveButton.disabled ? 'true' : 'false');
    var publishButton = document.getElementById('btn-voice-publish');
    publishButton.disabled = !writable || publishBundleBlocked(pageState[currentAlias]);
    publishButton.setAttribute('aria-disabled', publishButton.disabled ? 'true' : 'false');
  }

  function renderCurrentKey() {
    var conflict = document.getElementById('voice-conflict-comparison');
    if (conflict) conflict.remove();
    renderKeyTabs();
    renderMeta();
    renderStatusSummary();
    renderSections();
    renderEditor();
    renderDiff();
    renderCredential();
    renderCapabilities();
    renderPreviewVisibility();
    renderSupplementCards();
    renderHistory();
    applyKeyPermissions();
    applyVoiceTestPermissions();
  }

  async function switchKey(alias) {
    if (!KEY_DEFINITIONS[alias] || alias === currentAlias) return;
    currentAlias = alias;
    currentSection = KEY_DEFINITIONS[alias].sections[0];
    clearInline('voice-inline-errors');
    renderCurrentKey();
    if (!pageState[alias].bundle) await reloadCurrent();
  }

  function currentMeta() {
    return pageState[currentAlias].bundle && pageState[currentAlias].bundle._meta;
  }

  async function saveCurrentSection() {
    if (!canWrite(currentAlias)) return;
    clearInline('voice-inline-errors');
    var content;
    try {
      content = currentAlias === 'script' && currentSection === 'summary'
        ? {prompt_template: document.getElementById('voice-section-json').value}
        : JSON.parse(document.getElementById('voice-section-json').value);
    } catch (error) {
      showInlineErrors('voice-inline-errors', {
        data: { errors: [{ code: 'JSON_PARSE_ERROR', path: currentSection, message: error.message }] }
      }, 'JSON 无法解析');
      return;
    }
    if (!content || typeof content !== 'object' || Array.isArray(content)) {
      showInlineErrors('voice-inline-errors', {
        data: { errors: [{ code: 'SECTION_TYPE_INVALID', path: currentSection, message: '分区正文必须是 JSON 对象' }] }
      });
      return;
    }
    if (currentAlias === 'config' && currentSection === 'capabilities') {
      var capabilityResult = buildCapabilitySectionContent(
        pageState.config.selectedConfig && pageState.config.selectedConfig.capabilities,
        content
      );
      if (capabilityResult.errors.length) {
        showInlineErrors('voice-inline-errors', {
          data: { errors: capabilityResult.errors }
        }, '能力可配置字段未通过校验');
        return;
      }
      content = capabilityResult.content;
    }
    if (currentAlias === 'config' && currentSection === 'global') {
      if (Object.prototype.hasOwnProperty.call(content, 'enabled')) {
        showInlineErrors('voice-inline-errors', {message: '总开关请在独立的「总开关」页面操作，请移除 enabled 字段。'});
        return;
      }
      content.enabled = pageState.config.selectedConfig.global.enabled;
    }
    var meta = currentMeta();
    if (!meta) return;
    var saveAlias = currentAlias, saveSection = currentSection;
    var result = await voicePatch(
      '/api/admin/voice/config/' + currentAlias + '/draft/' + encodeURIComponent(currentSection),
      {
        base_version: meta.base_version,
        draft_revision: meta.draft_revision,
        content: content
      }
    );
    if (!result || result.code !== 0) {
      showInlineErrors('voice-inline-errors', result, '分区草稿保存失败');
      var errorCode = result && result.data && result.data.error_code;
      if (['VOICE_CONFIG_BASE_VERSION_CONFLICT', 'VOICE_CONFIG_REVISION_CONFLICT'].indexOf(errorCode) >= 0) {
        var latest = await voiceGet('/api/admin/voice/config/' + saveAlias);
        if (currentAlias !== saveAlias || currentSection !== saveSection) return;
        var oldComparison = document.getElementById('voice-conflict-comparison');
        if (oldComparison) oldComparison.remove();
        var comparison = document.createElement('div');
        comparison.id = 'voice-conflict-comparison';
        comparison.className = 'alert alert-warning';
        var heading = document.createElement('p');
        heading.textContent = '保存冲突：本次编辑已保留。请对照最新内容，复制所需修改后重新加载再编辑。';
        comparison.appendChild(heading);
        if (latest && latest.code === 0 && latest.data && latest.data.config) {
          var remote = latest.data.config[saveSection];
          if (saveAlias === 'config' && saveSection === 'capabilities') remote = capabilityEditableProjection(remote);
          var local = saveAlias === 'config' && saveSection === 'capabilities' ? capabilityEditableProjection(content) : content;
          var fields = Array.from(new Set(Object.keys(local || {}).concat(Object.keys(remote || {}))));
          var changed = fields.filter(function (key) { return JSON.stringify((local || {})[key]) !== JSON.stringify((remote || {})[key]); });
          var detail = document.createElement('p');
          detail.textContent = '差异字段：' + (changed.join('、') || '本分区无差异，其他分区或版本已变化');
          comparison.appendChild(detail);
          [['本次编辑', local], ['服务器最新内容', remote]].forEach(function (entry) {
            var label = document.createElement('strong'), body = document.createElement('pre');
            label.textContent = entry[0]; body.textContent = pretty(entry[1]);
            body.style.whiteSpace = 'pre-wrap'; body.style.overflowWrap = 'anywhere';
            comparison.appendChild(label); comparison.appendChild(body);
          });
        } else {
          var unavailable = document.createElement('p');
          unavailable.textContent = '最新内容读取失败，本次编辑仍保留，请稍后重新加载。';
          comparison.appendChild(unavailable);
        }
        document.getElementById('voice-inline-errors').after(comparison);
      }
      return;
    }
    showToast('分区「' + currentSection + '」草稿已保存', 'success');
    await reloadCurrent();
  }

  async function discardCurrentSection() {
    if (!canWrite(currentAlias)) return;
    showConfirm('确定丢弃当前分区「' + escapeHtml(currentSection) + '」的草稿变更吗？', async function () {
      var result = await voiceDelete(
        '/api/admin/voice/config/' + currentAlias + '/draft/' + encodeURIComponent(currentSection)
      );
      if (!result || result.code !== 0) {
        showInlineErrors('voice-inline-errors', result, '分区草稿丢弃失败');
        return;
      }
      showToast('当前分区草稿已丢弃', 'success');
      await reloadCurrent();
    }, null, { danger: true });
  }

  async function discardAllDraft() {
    if (!canWrite(currentAlias)) return;
    showConfirm('确定丢弃当前 key 的全部草稿吗？该操作不可撤销。', async function () {
      var result = await voiceDelete(
        '/api/admin/voice/config/' + currentAlias + '/draft'
      );
      if (!result || result.code !== 0) {
        showInlineErrors('voice-inline-errors', result, '全部草稿丢弃失败');
        return;
      }
      showToast('全部草稿已丢弃', 'success');
      await reloadCurrent();
    }, null, { danger: true });
  }

  function renderValidationResult(result) {
    if (!result || result.code !== 0) {
      showInlineErrors('voice-inline-errors', result, '配置校验请求失败');
      return false;
    }
    var data = result.data || {};
    if (!data.valid) {
      showInlineErrors('voice-inline-errors', { data: { errors: data.errors || [] } }, '配置校验未通过');
      return false;
    }
    showInlineMessage('voice-inline-errors', '校验通过：当前草稿满足后端发布前约束。', 'success');
    return true;
  }

  async function validateCurrent() {
    if (!canWrite(currentAlias)) return;
    clearInline('voice-inline-errors');
    var result = await voicePost(
      '/api/admin/voice/config/' + currentAlias + '/validate',
      {}
    );
    renderValidationResult(result);
  }

  function buildJsonLineDiff(active, draft) {
    var leftLines = pretty(active).split('\n');
    var rightLines = pretty(draft).split('\n');
    var matrix = new Array(leftLines.length + 1);
    var i;
    var j;
    for (i = 0; i <= leftLines.length; i += 1) {
      matrix[i] = new Uint32Array(rightLines.length + 1);
    }
    for (i = leftLines.length - 1; i >= 0; i -= 1) {
      for (j = rightLines.length - 1; j >= 0; j -= 1) {
        matrix[i][j] = leftLines[i] === rightLines[j]
          ? matrix[i + 1][j + 1] + 1
          : Math.max(matrix[i + 1][j], matrix[i][j + 1]);
      }
    }

    var rows = [];
    var removedCount = 0;
    var addedCount = 0;
    i = 0;
    j = 0;
    while (i < leftLines.length || j < rightLines.length) {
      if (i < leftLines.length && j < rightLines.length && leftLines[i] === rightLines[j]) {
        rows.push({
          left: { number: i + 1, text: leftLines[i], type: 'unchanged' },
          right: { number: j + 1, text: rightLines[j], type: 'unchanged' }
        });
        i += 1;
        j += 1;
        continue;
      }

      var removed = [];
      var added = [];
      while (i < leftLines.length || j < rightLines.length) {
        if (i < leftLines.length && j < rightLines.length && leftLines[i] === rightLines[j]) break;
        if (i < leftLines.length && (j >= rightLines.length || matrix[i + 1][j] >= matrix[i][j + 1])) {
          removed.push({ number: i + 1, text: leftLines[i], type: 'removed' });
          removedCount += 1;
          i += 1;
        } else {
          added.push({ number: j + 1, text: rightLines[j], type: 'added' });
          addedCount += 1;
          j += 1;
        }
      }
      var changedRows = Math.max(removed.length, added.length);
      for (var rowIndex = 0; rowIndex < changedRows; rowIndex += 1) {
        rows.push({ left: removed[rowIndex] || null, right: added[rowIndex] || null });
      }
    }
    return { rows: rows, removedCount: removedCount, addedCount: addedCount };
  }

  function appendJsonDiffLine(host, entry, counterpart) {
    var line = document.createElement('div');
    var state = entry ? entry.type : 'empty';
    line.className = 'voice-diff-line is-' + state;
    if (!entry && counterpart) line.classList.add('is-' + counterpart.type + '-context');

    var number = document.createElement('span');
    number.className = 'voice-diff-line-number';
    number.textContent = entry ? entry.number : '';

    var marker = document.createElement('span');
    marker.className = 'voice-diff-marker';
    marker.textContent = entry && entry.type === 'removed' ? '−'
      : (entry && entry.type === 'added' ? '+' : ' ');

    var code = document.createElement('span');
    code.className = 'voice-diff-line-code';
    code.setAttribute('data-diff-code', '');
    code.textContent = entry && entry.text !== '' ? entry.text : '\u00a0';

    line.appendChild(number);
    line.appendChild(marker);
    line.appendChild(code);
    host.appendChild(line);
  }

  function renderJsonLineDiff(activeHost, draftHost, active, draft) {
    var diff = buildJsonLineDiff(active, draft);
    diff.rows.forEach(function (row) {
      appendJsonDiffLine(activeHost, row.left, row.right);
      appendJsonDiffLine(draftHost, row.right, row.left);
    });

    var scrollOwner = '';
    function syncScroll(source, target, owner) {
      if (scrollOwner && scrollOwner !== owner) return;
      scrollOwner = owner;
      target.scrollTop = source.scrollTop;
      setTimeout(function () { if (scrollOwner === owner) scrollOwner = ''; }, 0);
    }
    activeHost.addEventListener('scroll', function () { syncScroll(activeHost, draftHost, 'active'); });
    draftHost.addEventListener('scroll', function () { syncScroll(draftHost, activeHost, 'draft'); });
    return diff;
  }

  function openHighRiskDialog(options) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay show';
    var noteLabel = options.noteLabel || '变更说明 change_note';
    var notePlaceholder = options.notePlaceholder || '必填，说明本次变更原因';
    var diffHtml = options.diff
      ? '<div class="voice-risk-diff" data-risk-diff>' +
          '<div class="voice-muted mb-8" data-risk-changed></div>' +
          '<div class="voice-diff-grid">' +
            '<div class="voice-diff-pane"><div class="voice-diff-title">生效版本整包</div>' +
              '<div class="voice-diff-code" data-risk-active aria-label="生效版本 JSON"></div></div>' +
            '<div class="voice-diff-pane"><div class="voice-diff-title">待发布草稿整包</div>' +
              '<div class="voice-diff-code" data-risk-draft aria-label="待发布草稿 JSON"></div></div>' +
          '</div>' +
        '</div>'
      : '';
    var modalMaxWidth = options.diff ? 1180 : 960;
    overlay.innerHTML =
      '<div class="modal-content modal-content--danger" style="width:min(' + modalMaxWidth + 'px,calc(100vw - 32px));max-width:' + modalMaxWidth + 'px">' +
        '<div class="modal-header"><h3>' + escapeHtml(options.title) + '</h3>' +
          '<button type="button" class="btn btn-link" data-close>✕</button></div>' +
        '<div class="modal-body">' +
          '<div class="alert alert-warning">' + escapeHtml(options.warning) + '</div>' +
          diffHtml +
          '<div class="form-item mt-16"><label>' + escapeHtml(noteLabel) + '</label>' +
            '<textarea class="form-control" data-change-note maxlength="500" rows="3" placeholder="' +
              escapeHtml(notePlaceholder) + '"></textarea></div>' +
          '<div class="form-item"><label>输入 CONFIRM</label>' +
            '<input class="form-control" data-confirm-text autocomplete="off" placeholder="CONFIRM"></div>' +
        '</div>' +
        '<div class="modal-footer"><button type="button" class="btn btn-default" data-cancel>取消</button>' +
          '<button type="button" class="btn btn-danger" data-submit disabled>' + escapeHtml(options.submitText) + '</button></div>' +
      '</div>';
    document.body.appendChild(overlay);
    if (options.diff) {
      var changedSections = options.diff.changedSections || [];
      overlay.querySelector('[data-risk-changed]').textContent = changedSections.length
        ? '后端标记的变更分区：' + changedSections.join('、')
        : '后端标记的变更分区：无';
      var activeDiffHost = overlay.querySelector('[data-risk-active]');
      var draftDiffHost = overlay.querySelector('[data-risk-draft]');
      if (options.diff.hasDraft) {
        var lineDiff = renderJsonLineDiff(
          activeDiffHost,
          draftDiffHost,
          options.diff.active,
          options.diff.draft
        );
        overlay.querySelector('[data-risk-changed]').textContent +=
          '；删除 ' + lineDiff.removedCount + ' 行，新增 ' + lineDiff.addedCount + ' 行';
      } else {
        activeDiffHost.textContent = pretty(options.diff.active);
        draftDiffHost.textContent = '（当前没有草稿）';
      }
    }
    var note = overlay.querySelector('[data-change-note]');
    var confirmText = overlay.querySelector('[data-confirm-text]');
    var submit = overlay.querySelector('[data-submit]');

    function update() {
      var reason = note.value.trim();
      var invalidReason = reason.length < 1 || reason.length > 500;
      submit.disabled = invalidReason || confirmText.value !== 'CONFIRM';
    }
    function close() { overlay.remove(); }
    note.addEventListener('input', update);
    confirmText.addEventListener('input', update);
    overlay.querySelector('[data-close]').onclick = close;
    overlay.querySelector('[data-cancel]').onclick = close;
    overlay.addEventListener('click', function (event) { if (event.target === overlay) close(); });
    submit.onclick = function () {
      var changeNote = note.value.trim();
      if (changeNote.length < 1 || changeNote.length > 500 || confirmText.value !== 'CONFIRM') {
        update();
        return;
      }
      close();
      options.onSubmit(changeNote);
    };
    setTimeout(function () { note.focus(); }, 50);
  }

  function publishCurrent() {
    if (!canWrite(currentAlias)) return;
    var state = pageState[currentAlias];
    if (publishBundleBlocked(state)) {
      if (activeBundleLoadFailed(state)) {
        showInlineErrors('voice-inline-errors', {
          data: { errors: state.activeLoadErrors }
        }, '生效版本整包加载失败');
      } else {
        showInlineMessage(
          'voice-inline-errors',
          '生效版本整包尚未可用；请重新加载后再发布。',
          'warning'
        );
      }
      return;
    }
    openHighRiskDialog({
      title: '发布 ' + KEY_DEFINITIONS[currentAlias].configKey,
      warning: '发布会替换当前生效版本。后端将再次校验草稿、人格锚点与凭据状态。',
      diff: bundleDiffProjection(pageState[currentAlias]),
      submitText: '确认发布',
      onSubmit: async function (changeNote) {
        var result = await voicePost(
          '/api/admin/voice/config/' + currentAlias + '/publish',
          { confirm_text: 'CONFIRM', change_note: changeNote }
        );
        if (!result || result.code !== 0) {
          showInlineErrors('voice-inline-errors', result, '发布失败');
          return;
        }
        showToast('语音配置已发布', 'success');
        await reloadCurrent();
      }
    });
  }

  function openReadOnlyProjection(title, projection) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay show';
    var content = document.createElement('div');
    content.className = 'modal-content';
    content.style.minWidth = '520px';
    content.style.maxWidth = '820px';

    var header = document.createElement('div');
    header.className = 'modal-header';
    var heading = document.createElement('h3');
    heading.textContent = title;
    var closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn btn-link';
    closeButton.textContent = '✕';
    header.appendChild(heading);
    header.appendChild(closeButton);

    var body = document.createElement('div');
    body.className = 'modal-body';
    var note = document.createElement('p');
    note.className = 'voice-muted mb-16';
    note.textContent = '以下内容是后端按当前角色返回的只读投影；页面不补全、推导或写入证据。';
    var pre = document.createElement('pre');
    pre.className = 'voice-diff-code';
    pre.textContent = pretty(projection);
    body.appendChild(note);
    body.appendChild(pre);
    content.appendChild(header);
    content.appendChild(body);
    overlay.appendChild(content);
    document.body.appendChild(overlay);

    function close() { overlay.remove(); }
    closeButton.onclick = close;
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) close();
    });
  }

  async function viewCapabilityEvidence(evidenceReportId) {
    var result = await voiceGet(
      '/api/admin/voice/capability-evidence/' + encodeURIComponent(evidenceReportId)
    );
    if (!result || result.code !== 0 || !result.data) {
      showInlineErrors('voice-inline-errors', result, '能力证据读取失败');
      return;
    }
    openReadOnlyProjection('能力证据 · ' + evidenceReportId, result.data);
  }

  async function viewHistoryDetail(version) {
    var result = await voiceGet(
      '/api/admin/voice/config/' + currentAlias + '/history/' + encodeURIComponent(version)
    );
    if (!result || result.code !== 0 || !result.data) {
      showInlineErrors('voice-inline-errors', result, '历史详情加载失败');
      return;
    }
    document.getElementById('voice-history-detail-title').textContent =
      KEY_DEFINITIONS[currentAlias].configKey + ' · V' + version;
    document.getElementById('voice-history-detail-json').textContent = pretty(result.data);
    document.getElementById('voice-history-detail').classList.add('show');
  }

  function rollbackVersion(version) {
    if (!canWrite(currentAlias)) return;
    openHighRiskDialog({
      title: '回滚至 V' + version,
      warning: '回滚会把目标历史正文复制为一个新的生效版本，不会复活旧凭据值。',
      submitText: '确认回滚',
      onSubmit: async function (changeNote) {
        var result = await voicePost(
          '/api/admin/voice/config/' + currentAlias + '/rollback',
          { version: version, confirm_text: 'CONFIRM', change_note: changeNote }
        );
        if (!result || result.code !== 0) {
          showInlineErrors('voice-inline-errors', result, '回滚失败');
          return;
        }
        showToast('已回滚并生成新的生效版本', 'success');
        await reloadCurrent();
      }
    });
  }

  function candidateAtWithShanghaiOffset(value) {
    var text = String(value || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(text)) return null;
    if (text.length === 16) text += ':00';
    return text + '+08:00';
  }

  function previewValue(host, label, value) {
    appendKeyValue(host, label, value);
  }

  function renderPreview(data) {
    var preview = data && data.followup_preview;
    if (!preview) {
      showInlineErrors('voice-preview-errors', null, '后端未返回 followup_preview');
      return;
    }
    clearInline('voice-preview-errors');
    var host = document.getElementById('voice-preview-grid');
    host.innerHTML = '';
    previewValue(host, 'stage', preview.stage);
    previewValue(host, 'candidate_at', preview.candidate_at);
    previewValue(host, 'resolution', preview.resolution);
    previewValue(host, 'in_window', preview.in_window);
    previewValue(host, 'resolved_window.start_at', preview.resolved_window && preview.resolved_window.start_at);
    previewValue(host, 'resolved_window.end_at', preview.resolved_window && preview.resolved_window.end_at);
    previewValue(host, 'jitter_applied_minutes', preview.jitter_applied_minutes);
    previewValue(host, 'resolved_due_at', preview.resolved_due_at);
    previewValue(host, 'delay_seconds', preview.delay_seconds);
    previewValue(host, 'cancel_reason', preview.cancel_reason);
    document.getElementById('voice-preview-result').classList.add('show');
  }

  async function requestFollowupPreview() {
    if (!canWrite('config') || currentAlias !== 'config') return;
    clearInline('voice-preview-errors');
    document.getElementById('voice-preview-result').classList.remove('show');
    var candidateAt = candidateAtWithShanghaiOffset(
      document.getElementById('voice-preview-candidate').value
    );
    var jitterText = document.getElementById('voice-preview-jitter').value;
    var jitter = previewJitterValue(jitterText);
    if (!candidateAt || (jitterText !== '' &&
      (!Number.isInteger(jitter) || jitter < 0 || jitter > 20))) {
      showInlineErrors('voice-preview-errors', {
        data: { errors: [{
          code: 'FOLLOWUP_PREVIEW_INPUT_INVALID',
          path: 'followup_preview',
          message: '请填写候选时间，并使用 0–20 的整数 jitter_minutes'
        }] }
      });
      return;
    }
    var result = await voicePost(
      '/api/admin/voice/config/config/validate',
      {
        followup_preview: {
          stage: document.getElementById('voice-preview-stage').value,
          candidate_at: candidateAt,
          jitter_minutes: jitter
        }
      }
    );
    if (!result || result.code !== 0) {
      showInlineErrors('voice-preview-errors', result, '预览请求失败');
      return;
    }
    if (!result.data || !result.data.valid) {
      showInlineErrors('voice-preview-errors', {
        data: { errors: result.data && result.data.errors ? result.data.errors : [] }
      }, '后端预览校验未通过');
      return;
    }
    renderPreview(result.data);
  }

  function selectedVoiceCapabilityKey() {
    var select = document.getElementById('voice-test-capability-select');
    var capabilityKey = select ? select.value : '';
    return CAPABILITY_KEYS.indexOf(capabilityKey) >= 0 ? capabilityKey : null;
  }

  async function testVoiceConnection() {
    var permissions = voiceTestPermissions(
      getAdminRole(), currentAlias, !!(pageState.config && pageState.config.bundle)
    );
    if (!permissions.connection || voiceTestBusy) return;
    clearInline('voice-test-errors');
    setVoiceTestBusy(true);
    try {
      var result = await voicePost(
        '/api/admin/voice/config/test-connection',
        {}
      );
      if (!result || result.code !== 0 || !result.data) {
        showInlineErrors('voice-test-errors', result, '短连接测试请求失败');
        return;
      }
      renderVoiceTestResult('connection', result.data);
      showInlineMessage(
        'voice-test-errors',
        result.data.status === 'passed'
          ? '短连接测试通过；该结果不等于 M1 闸门关闭。'
          : '短连接测试已完成，状态为 ' + display(result.data.status) + '；请按 failure_category 统一收口。',
        result.data.status === 'passed' ? 'success' : 'warning'
      );
    } finally {
      setVoiceTestBusy(false);
    }
  }

  function capabilityTestFeedback(data) {
    var evidenceAppended = !!(
      data && data.evidence_run_id && data.evidence_report_id
    );
    var status = display(data && data.status);
    if (!evidenceAppended) {
      return {
        evidenceAppended: false,
        message: '单能力测试已完成，但未追加能力证据且未修改能力投影；状态为 ' + status + '。',
        tone: 'warning'
      };
    }
    if (data.status === 'passed') {
      return {
        evidenceAppended: true,
        message: '单能力测试通过并已追加管理员证据；该结果不等于 M1 闸门关闭。',
        tone: 'success'
      };
    }
    return {
      evidenceAppended: true,
      message: '单能力测试已完成并追加管理员证据，状态为 ' + status + '；能力投影已按证据重载。',
      tone: 'warning'
    };
  }

  async function testVoiceCapability() {
    var permissions = voiceTestPermissions(
      getAdminRole(), currentAlias, !!(pageState.config && pageState.config.bundle)
    );
    if (!permissions.capability || voiceTestBusy) return;
    var capabilityKey = selectedVoiceCapabilityKey();
    if (!capabilityKey) {
      showInlineErrors('voice-test-errors', null, '请选择六项冻结能力之一');
      return;
    }
    clearInline('voice-test-errors');
    setVoiceTestBusy(true);
    try {
      var result = typeof window.runVoiceCapabilityPlayback === 'function'
        ? await window.runVoiceCapabilityPlayback(capabilityKey)
        : await voicePost('/api/admin/voice/config/test-capability', buildCapabilityTestBody(capabilityKey));
      if (!result || result.code !== 0 || !result.data) {
        showInlineErrors('voice-test-errors', result, '单能力测试请求失败');
        return;
      }
      renderVoiceTestResult('capability', result.data);
      var feedback = capabilityTestFeedback(result.data);
      showInlineMessage(
        'voice-test-errors',
        feedback.message,
        feedback.tone
      );
      if (feedback.evidenceAppended) await reloadCurrent();
    } finally {
      setVoiceTestBusy(false);
    }
  }

  function forceVoiceCapabilityTest() {
    var permissions = voiceTestPermissions(
      getAdminRole(), currentAlias, !!(pageState.config && pageState.config.bundle)
    );
    if (!permissions.force || voiceTestBusy) return;
    var capabilityKey = selectedVoiceCapabilityKey();
    if (!capabilityKey) {
      showInlineErrors('voice-test-errors', null, '请选择六项冻结能力之一');
      return;
    }
    openHighRiskDialog({
      title: '强制能力为 test 范围',
      warning: '仅对配置中的 test_user_ids 生效；不会扩大为 all，也不会关闭 O-01。',
      noteLabel: '强制原因 reason（1–500 字）',
      notePlaceholder: '必填，说明为何需要强制 test 范围',
      submitText: '确认强制 test',
      onSubmit: async function (reason) {
        clearInline('voice-test-errors');
        setVoiceTestBusy(true);
        try {
          var result = await voicePost(
            '/api/admin/voice/config/capabilities/' + encodeURIComponent(capabilityKey) + '/force-test',
            buildForceTestBody(reason)
          );
          if (!result || result.code !== 0 || !result.data) {
            showInlineErrors('voice-test-errors', result, '强制 test 请求失败');
            return;
          }
          renderVoiceTestResult('force', result.data);
          showInlineMessage(
            'voice-test-errors',
            '能力已强制为 test 范围并写入草稿；仍需后续真人总验收关闭 O-01。',
            'warning'
          );
          await reloadCurrent();
        } finally {
          setVoiceTestBusy(false);
        }
      }
    });
  }

  function bindEvents() {
    document.querySelectorAll('[data-voice-key]').forEach(function (button) {
      button.onclick = function () { switchKey(button.getAttribute('data-voice-key')); };
    });
    document.getElementById('btn-voice-reload').onclick = reloadCurrent;
    document.getElementById('btn-voice-save-section').onclick = saveCurrentSection;
    document.getElementById('btn-voice-discard-section').onclick = discardCurrentSection;
    document.getElementById('btn-voice-discard-all').onclick = discardAllDraft;
    document.getElementById('btn-voice-validate').onclick = validateCurrent;
    document.getElementById('btn-voice-publish').onclick = publishCurrent;
    document.getElementById('btn-voice-preview').onclick = requestFollowupPreview;
    document.getElementById('btn-voice-test-connection').onclick = testVoiceConnection;
    document.getElementById('btn-voice-test-capability').onclick = testVoiceCapability;
    document.getElementById('btn-voice-force-capability').onclick = forceVoiceCapabilityTest;
    document.getElementById('btn-voice-history-refresh').onclick = function () {
      loadHistory(currentAlias, true);
    };
    document.getElementById('btn-voice-history-close').onclick = function () {
      document.getElementById('voice-history-detail').classList.remove('show');
    };
    document.getElementById('voice-primary-field-input').oninput = syncPrimaryFieldToEditor;
    document.getElementById('voice-section-json').addEventListener('input', function () {
      syncPrimaryFieldFromEditor();
      try {
        renderBusinessForm();
        applyKeyPermissions();
      } catch (error) {
        // 原始 JSON 编辑过程中允许暂时不完整；业务表单保留最后一次可解析状态。
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!checkAdminLogin()) return;
    if (ALLOWED_ROLES.indexOf(getAdminRole()) < 0) {
      window.location.href = '/admin/pages/error.html?type=403';
      return;
    }
    document.getElementById('sidebar-mount').innerHTML = renderSidebar('voice-config');
    document.getElementById('header-mount').innerHTML = renderHeader('实时语音配置');
    bindEvents();
    renderCurrentKey();
    reloadCurrent();
  });
})();

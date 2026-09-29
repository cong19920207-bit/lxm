"""Read-only voice templates built from the same functions used at runtime.

Configuration and call-specific data are placeholders. Reading these views does
not load a call, create configuration, call a model, or enqueue a job.
"""
import json
from types import SimpleNamespace

from backend.services.realtime_voice_memory_service import build_memory_prompt
from backend.services.realtime_voice_recall_service import build_recall_prompt
from backend.services.realtime_voice_summary_service import build_summary_prompt
from backend.services.realtime_voice_followup_topic_service import build_followup_topic_prompt
from backend.services.realtime_voice_prompt_templates import (
    CLOSING_REPLY_RULES, build_closing_semantic_prompt, build_control_prompt, build_decision_prompt,
)

_GROUPS = (
    ('call_answer', '接听判断', '接通前', (('call_answer', '接听判断'),)),
    ('recall', '记忆召回', '通话中', (('recall', '记忆召回'),)),
    ('memory', '记忆抽取', '每轮结束', (('memory', '记忆抽取'),)),
    ('summary', '通话总结', '通话结束后', (('summary', '通话总结'),)),
    ('closing_control', '收尾控制', '通话收尾', (
        ('time_low', '时长将尽'), ('silence_confirm', '静默确认'),
        ('goodbye', '简短告别'), ('silence_fallback', '告别兜底'))),
    ('closing_review', '收尾回复审核', '播放前', (('closing_review', '收尾回复审核'),)),
    ('followup_review', '跟进消息复核', '追加消息发送前', (('followup_review', '跟进消息复核'),)),
)


def get_prompt_catalog():
    return {'readonly': True, 'groups': [
        {'key': key, 'label': label, 'stage': stage,
         'items': [{'key': item_key, 'label': item_label} for item_key, item_label in items]}
        for key, label, stage, items in _GROUPS
    ]}


def _placeholder(key):
    return '{{' + key + '}}'


def _entry(title, description, trigger, content, inputs, output, sources, notes=()):
    return dict(readonly=True, title=title, description=description, trigger=trigger,
                content=content, inputs=[{'name': key, 'description': value} for key, value in inputs],
                output=output, source_files=['backend/services/' + name + '.py' for name in sources],
                notes=list(notes))


def get_prompt_view(prompt_key):
    known = {key for _, _, _, items in _GROUPS for key, _ in items}
    if prompt_key not in known:
        raise KeyError(prompt_key)
    view = _build_view(prompt_key)
    view['prompt_key'] = prompt_key
    return view


def _build_view(key):
    if key == 'call_answer':
        inputs = (
            ('is_first_call', '是否首次来电（布尔值）'), ('previous_calls', '历史通话次数（整数）'),
            ('calls_today', '今日来电次数（整数）'), ('missed_last_5_minutes', '近五分钟未接次数（整数）'),
            ('relationship_level', '关系等级'), ('relationship_description', '关系描述'),
            ('current_time', '当前时间'), ('schedule', '角色当天活动安排（数组）'),
        )
        return _entry('接听判断', '决定是否接听、响铃等待时间，并准备一句开场白。',
            '来电进入接听决策时；后台接听模板为空时直接采用兜底。',
            build_decision_prompt(_placeholder('call_answer.prompt_template'),
                                  {name: _placeholder(name) for name, _ in inputs}),
            (('call_answer.prompt_template', '来自语音设置的接听提示词'), *inputs),
            'JSON：answer（布尔值）、delay_seconds（0–12 的整数）、opening_text（最多 200 字）。',
            ('realtime_voice_decision_service', 'realtime_voice_prompt_templates'),
            ('实际等待时间还会经过代码边界校验；模型的输出不直接决定最终接听动作。',))
    if key == 'recall':
        inputs = (('user_text', '当前用户文本'), ('trigger_rules', '召回触发词（数组）'),
                  ('max_query_chars', '查询长度上限（整数）'), ('short_term', '本通短期资料，含 id 与 text'),
                  ('preamble', '会前注入的记忆资料，含 id 与 text'))
        return _entry('记忆召回', '判断是否需要旧记忆，并选择已有资料或生成检索问题。',
            '当前用户回合进入语音召回流程时。',
            build_recall_prompt({name: _placeholder(name) for name, _ in inputs},
                                _placeholder('recall.prompt_template')),
            (('recall.prompt_template', '来自语音设置的补充提示词，可为空'), *inputs),
            'JSON：needed（布尔值）、query（字符串）、selected_ids 与 candidate_keys（字符串数组）。',
            ('realtime_voice_recall_service',),
            ('资料按本通短期上下文、会前记忆、长期检索的顺序使用。',))
    if key == 'memory':
        inputs = (('call_id', '通话标识'), ('turn_index', '本轮序号（整数）'),
                  ('user_text', '本轮最终转写'), ('assistant_text_effective', '已确认播放的回复'),
                  ('previous_turn_summary', '上一条合格回合的用户文本，最多 2,000 字符'),
                  ('relationship_context', '关系等级与描述（对象，可为空）'),
                  ('short_term_candidates', '本通短期候选（数组，可为空）'),
                  ('origin_channel', '固定为 voice_call'))
        data = {name: _placeholder(name) for name, _ in inputs}
        data['origin_channel'] = 'voice_call'
        return _entry('记忆抽取', '将本轮对话提取为用户记忆与角色私有记忆。',
            '回合闭环且通过安全检查，有有效用户文本和已播放回复时。',
            build_memory_prompt(data, _placeholder('memory.prompt_template')),
            (('memory.prompt_template', '来自语音设置的补充提示词，可为空'), *inputs),
            'JSON：memory_items 数组。每项包含 memory_type、stable_key、content；最多 5 条。',
            ('realtime_voice_memory_service',),
            ('无符合条件的记忆时返回空数组；后台配置可以进一步降低每轮条数上限。',))
    if key == 'summary':
        turn = SimpleNamespace(turn_index=_placeholder('turn_index'), user_text_final=_placeholder('user_text'),
            assistant_text_effective=_placeholder('assistant_text_effective'), turn_status='finalized',
            effective_text_evidence='full', user_content_safety_status='passed',
            assistant_content_safety_status='passed', user_crisis_status='passed', assistant_crisis_status='passed')
        return _entry('通话总结', '生成总结卡片、未完话题、整通情绪和追加消息候选。',
            '通话结束后的总结任务满足生成条件时。',
            build_summary_prompt(duration_seconds=_placeholder('duration_seconds'), turns=[turn],
                                 prompt_template=_placeholder('summary.prompt_template')),
            (('summary.prompt_template', '来自语音设置的总结提示词'), ('duration_seconds', '有效通话秒数'),
             ('turns', '按顺序排列的安全闭环回合，含序号、用户文本与已播放回复')),
            'JSON：call_summary、unfinished_topics、user_emotion、assistant_emotion、should_send_followup、'
            'reasoning、followup_delay_minutes、followup_content、content_type。',
            ('realtime_voice_summary_service',),
            ('追加消息候选仍需经过发送前审核；该节点不写入长期记忆。',))
    if key in {'time_low', 'silence_confirm', 'goodbye', 'silence_fallback'}:
        descriptions = {
            'time_low': ('时长将尽', '引导语音模型结束当前表达，并自然收尾。', '剩余时长达到 time_low 阈值时。'),
            'silence_confirm': ('静默确认', '用一句简短询问确认用户是否还在听。', '等待用户且麦克风正常时，静默达到确认阈值。'),
            'goodbye': ('简短告别', '结合告别文案，引导语音模型完成简短告别。', '收尾策略发出告别控制动作时。'),
            'silence_fallback': ('告别兜底', '要求语音模型严格照读指定的告别文案。', '静默收尾的语义审核不可用，触发固定告别兜底时。'),
        }
        title, description, trigger = descriptions[key]
        inputs = ()
        template = ''
        notes = ('通过语音服务商的控制指令通道发送。',)
        if key == 'goodbye':
            template = _placeholder('goodbye_template')
            inputs = (('goodbye_template', '静默超时采用 silence_timeout_template；其他告别采用 exit_intent_template'),)
        elif key == 'silence_fallback':
            template = _placeholder('silence_and_exit.silence_timeout_template')
            inputs = (('silence_and_exit.silence_timeout_template', '来自语音设置的静默超时告别文案'),)
            notes += ('英文指令为当前代码原文；展示页保留原文。',)
        return _entry(title, description, trigger, build_control_prompt(key, template), inputs,
                      '由语音模型生成文本与音频，不返回业务 JSON。',
                      ('realtime_voice_gateway_service', 'realtime_voice_prompt_templates'), notes)
    if key == 'closing_review':
        inputs = (('current_topic', '当前话题（最多 8,000 字符）'),
                  ('candidate_reply', '等待审核的完整候选回复（最多 16,000 字符）'))
        return _entry('收尾回复审核', '确认收尾阶段的回复没有开启新话题。',
            '收尾阶段完整候选回复被缓冲后、放行播放前。',
            build_closing_semantic_prompt('allowed', CLOSING_REPLY_RULES,
                                          {name: _placeholder(name) for name, _ in inputs}),
            inputs, 'JSON：{"allowed": true} 或 {"allowed": false}。',
            ('realtime_voice_ending_service', 'realtime_voice_prompt_templates'),
            ('严格匹配预定固定告别文案时，可直接通过；其他候选进入语义审核。',))
    inputs = (('content_type', '候选类型：话题接续、情绪关心或未接说明'),
              ('followup_content', '尚未发送的候选消息'), ('unfinished_topics', '未完话题（数组）'),
              ('later_user_texts', '后续通话的用户文本（非空数组）'))
    payload = json.dumps({name: _placeholder(name) for name, _ in inputs}, ensure_ascii=False, sort_keys=True)
    return _entry('跟进消息复核', '检查候选消息是否已被后续交流覆盖，避免重复追问。',
        '追加消息发送前，发现后续用户语音时。', build_followup_topic_prompt(payload), inputs,
        'JSON：continued 为 true、false 或 null；null 会被代码视为无法可靠判断。',
        ('realtime_voice_followup_topic_service',),
        ('复核只影响候选消息是否继续发送，不重新生成消息。',))

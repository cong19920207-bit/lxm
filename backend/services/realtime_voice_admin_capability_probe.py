"""Request-local Provider evidence producer; independent consumer remains authoritative.

No raw PCM, text, vendor identifiers or secrets leave the recording transport.
An event being received or a command being sent is not a support conclusion.
"""
import asyncio
import audioop
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import websockets

from backend.services import realtime_voice_capability_service as evidence
from backend.services.realtime_voice_provider_service import decode_frame,ProviderError,ADAPTER_VERSION,PROTOCOL_PROFILE,SDK_VERSION

SUITE_VERSION='voice-admin-probe-v1'
MAX_EVENTS=2048

class BuiltinCapabilityProbe:
    def __init__(self, *, playback_target=None):
        self._salt=secrets.token_bytes(32)
        self._started=time.monotonic()
        self.events=[]
        self.actions=[]
        self.connected=False
        self.run_id=str(uuid4())
        self.playback_target=playback_target
        self.session_token=None
        self.ordinal=0
        self._asr_question=None
        self._nonce=None
        self._chat={}
        self._context_pair=None
        self._sentence_texts=[]
        self._truncate_proof=None
        self._speaker_output=False

    def token(self,value):
        return 'hmac256:'+hmac.digest(self._salt,str(value).encode(),'sha256').hex()[:24]

    def elapsed(self):return max(0,int((time.monotonic()-self._started)*1000))

    def record_frame(self,raw):
        msg=decode_frame(raw)
        self.ordinal+=1
        if self.session_token is not None and self.token(msg['session'])!=self.session_token:
            return
        if len(self.events)>=MAX_EVENTS:raise ProviderError('protocol_error')
        payload=msg['payload'];event_id=msg['event'];name=evidence._EVENT_NAMES.get(event_id,'ProviderEvent')
        shape={k:[] if k in ('object_keys','redacted_key_classes') else {} for k in evidence._PAYLOAD_SHAPE_FIELDS}
        correlations={'frame.session_id':self.token(msg['session'])} if msg['session'] else {}
        # Bounded whitelist projection, including the actual context ACK pair.
        def project(value,path):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key not in evidence._PAYLOAD_PATH_PARTS:continue
                    child=path+'.'+key;shape['object_keys'].append(child);project(item,child)
            elif isinstance(value,list):
                shape['list_lengths'][path]=len(value)
                for i,item in enumerate(value[:2]):project(item,path+'.'+str(i))
            elif isinstance(value,str):
                shape['text_fields'][path]={'chars':len(value),'token':self.token(value)}
                if path.split('.')[-1].endswith('_id'):correlations[path]=self.token(value)
            elif type(value) is bool:shape['boolean_fields'][path]={'kind':'boolean'}
            elif type(value) in (int,float):shape['numeric_fields'][path]={'kind':'integer' if type(value) is int else 'float'}
            elif isinstance(value,bytes):shape['binary_fields'][path]=len(value)
        project(payload,'payload')
        if event_id==350:self._sentence_texts.append(payload.get('text',''))
        if event_id==450:self._asr_question=payload.get('question_id')
        if event_id in (451,459) and self._asr_question:
            correlations['phase0.asr_question']=self.token(self._asr_question)
            correlations.setdefault('payload.question_id',self.token(self._asr_question))
        if event_id==567 and self._context_pair:
            items=payload.get('items',[])
            if len(items)==2 and all(isinstance(item,dict) and item.get('role')==expected['role'] and item.get('text')==expected['text']
                                    for item,expected in zip(items,self._context_pair)):
                correlations['phase0.reconnect_seed']=self.token(self._nonce)
        ordinal=self.ordinal
        if event_id==351:
            correlations['phase0.sentence_boundary']=self.token((msg['session'],ordinal))
        self.events.append(dict(ordinal=ordinal,received_at_ms=self.elapsed(),event_id=event_id,event_name=name,
            target_event=name in evidence._TARGET_EVENT_NAMES,message_type='SERVER_ACK' if msg['audio'] else 'SERVER_FULL_RESPONSE',
            payload_kind='binary' if isinstance(payload,bytes) else 'object',
            payload_size=len(payload) if isinstance(payload,bytes) else len(json.dumps(payload,ensure_ascii=False).encode()),
            is_audio=msg['audio'],parse_error=False,correlation_tokens=correlations,payload_shape=shape))
        if event_id==550 and self._nonce:
            identity=(msg['session'],payload.get('question_id'),payload.get('reply_id'))
            self._chat[identity]=(self._chat.get(identity,'')+str(payload.get('content',payload.get('text',''))))[-4096:]
            if self._nonce in self._chat[identity]:self.events[-1]['probe_match']=True

    def transport_factory(self,base=None):
        probe=self;base=base or websockets.connect
        async def connect(*args,**kwargs):
            wire=await base(*args,**kwargs);probe.connected=True
            class RecordingWire:
                async def send(self,raw):return await wire.send(raw)
                async def recv(self):
                    raw=await wire.recv();probe.record_frame(raw);return raw
                async def close(self):return await wire.close()
            return RecordingWire()
        return connect

    def result(self,config,key,status,reason,category='none'):
        if status=='failed' and category=='none':category='protocol_error'
        now=datetime.now(timezone.utc);tested=now.isoformat().replace('+00:00','Z')
        dimensions=dict(provider_profile=config['s2s']['provider'],model_version=config['s2s']['model_version'],
            protocol_profile=PROTOCOL_PROFILE,adapter_version=ADAPTER_VERSION,
            sdk_version=SDK_VERSION,evidence_suite_version=SUITE_VERSION)
        ttl=config['capabilities'][key]['evidence_ttl_days']
        payload=dict(schema_version='phase0-capability-evidence/v4',capability_status={'passed':'verified','failed':'failed','error':'unverified'}[status],
            reason_code=reason,degradation_mode=config['capabilities'][key]['fallback_mode'],event_evidence=list(self.events),
            action_evidence=list(self.actions),runtime_conditions={'real_provider':self.connected,'network_profile':'admin_test'},production_import_ready=status!='error')
        if key=='supports_context_truncate':
            payload['schema_version']='phase0-capability-evidence/v5'
            payload['protocol_evidence']={'truncate':self._truncate_proof if status!='error' and self._truncate_proof else {'status':'unverified','reason':reason,'operations':(self._truncate_proof or {}).get('operations',[])}}
            payload['runtime_conditions']['speaker_output']=self._speaker_output
        record=dict(evidence_report_id=str(uuid4()),evidence_run_id=self.run_id,capability_key=key,verification_result=status,
            source_type='admin_capability_test',**dimensions,evidence_fingerprint=evidence.compute_evidence_fingerprint(dimensions),
            evidence_payload=payload,tested_at=tested,verified_at=tested if status=='passed' else None,evidence_ttl_days_snapshot=ttl,
            expires_at=(now+timedelta(days=ttl)).isoformat().replace('+00:00','Z') if status=='passed' else None)
        record['report_sha256']=evidence._canonical_sha256(record,path='admin_probe')
        # Producer cannot bypass the same validator used at DB append.
        evidence._validate_evidence_record(record,expected_source='admin_capability_test',allow_error=True,path='admin_probe')
        return dict(status=status,failure_category=category,latency_ms=self.elapsed(),tested_at=tested,evidence_record=record)

    def failure_result(self,config,key,category):
        return self.result(config,key,'error',category,category)

    async def __call__(self,*,adapter,capability_key,draft_snapshot):
        self.session_token=self.token(adapter.session_id)
        self.events=[e for e in self.events if e['correlation_tokens'].get('frame.session_id')==self.session_token]
        try:
            async with asyncio.timeout(45):
                if capability_key=='supports_playback_text_mapping':
                    return await self.mapping(adapter,draft_snapshot,capability_key)
                if capability_key=='supports_sentence_playback_ack':
                    return await self.sentence_ack(adapter,draft_snapshot,capability_key)
                if capability_key=='supports_current_turn_rag_gate':
                    return await self.rag(adapter,draft_snapshot,capability_key)
                if capability_key=='supports_reply_cancel':
                    return await self.cancel(adapter,draft_snapshot,capability_key)
                if capability_key=='supports_session_reconnect':
                    return await self.reconnect(adapter,draft_snapshot,capability_key)
                return await self.truncate(adapter,draft_snapshot,capability_key)
        except asyncio.CancelledError:raise
        except Exception as exc:
            category=exc.category if isinstance(exc,ProviderError) else 'timeout' if isinstance(exc,TimeoutError) else 'evidence_invalid'
            return self.failure_result(draft_snapshot,capability_key,category)

    async def greeting(self,adapter,content='管理端播放映射测试。',capture=None):
        await adapter.say_hello(content)
        audio_bytes=0;reply_id=None
        while True:
            event=await adapter.receive_event()
            if event.kind=='tts_audio':
                if reply_id is not None and reply_id!=event.reply_id:raise ProviderError('evidence_invalid')
                reply_id=event.reply_id;audio_bytes+=len(event.payload)
                if audio_bytes>4*1024*1024:raise ProviderError('protocol_error')
                if capture is not None:capture.append(event)
                elif self.playback_target is not None:await self.playback_target.write_audio(event)
            if event.kind=='tts_finished':
                if reply_id is not None and event.reply_id!=reply_id:raise ProviderError('evidence_invalid')
                return dict(call_id=adapter.call_id,session_id=adapter.session_id,reply_id=reply_id,audio_bytes=audio_bytes)

    async def mapping(self,adapter,config,key):
        expected=await self.greeting(adapter)
        if self.playback_target is not None:
            ack=await self.playback_target.wait_played(**expected)
            if type(ack) is not dict or ack!=expected or type(ack.get('audio_bytes')) is not int:raise ProviderError('evidence_invalid')
        payload={'event_evidence':self.events,'action_evidence':self.actions,
                 'schema_version':'phase0-capability-evidence/v4'}
        for status,reason in [('passed','sentence_identity_reply_session_boundaries_correlate_with_audio'),
                              ('failed','correlated_sentence_window_contains_no_audio'),
                              ('failed','provider_sentence_boundary_sequence_is_ambiguous')]:
            try:
                evidence._validate_capability_conclusion(capability_key=key,result=status,payload={**payload,'reason_code':reason},path='admin_probe')
            except evidence.CapabilityStateError:continue
            return self.result(config,key,status,reason)
        return self.failure_result(config,key,'evidence_invalid')

    async def sentence_ack(self,adapter,config,key):
        if self.playback_target is None:
            return self.result(config,key,'error','playback_target_missing','evidence_invalid')
        expected=await self.greeting(adapter)
        _,boundary=evidence._validate_mapping_window(self.events,path='admin_probe')
        ack=await self.playback_target.wait_played(**expected)
        if type(ack) is not dict or ack!=expected or type(ack.get('audio_bytes')) is not int:
            raise ProviderError('evidence_invalid')
        self.actions.append(dict(action='client_sentence_played',at_ms=self.elapsed(),success=True,
            sentence_token=boundary['correlation_tokens']['phase0.sentence_boundary'],
            sentence_boundary_ordinal=boundary['ordinal'],provider_ordinal_after_ack=self.ordinal,
            correlation_tokens={k:v for k,v in boundary['correlation_tokens'].items() if k in evidence._ACTION_CORRELATION_PATHS}))
        return self.result(config,key,'passed','client_confirmed_exact_provider_sentence_played')

    async def next_frame(self,adapter):
        # Same production decoder/normalizer, one serialized reader. Raw payload
        # is request memory only and never returned in diagnostics or evidence.
        async with adapter._read_lock:
            wire,generation=adapter._wire,adapter._generation
            if wire is None:raise ProviderError('upstream_unavailable')
            msg=decode_frame(await wire.recv())
            if wire is not adapter._wire or generation!=adapter._generation:raise ProviderError('upstream_unavailable')
            normalized=adapter._normalize(msg)
            if msg['session']!=adapter.session_id:raise ProviderError('evidence_invalid')
            return msg,normalized

    async def speech_fixture(self,adapter,content):
        chunks=[]
        await self.greeting(adapter,content,capture=chunks)
        pcm=b''.join(event.payload for event in chunks)
        if not pcm or len(pcm)%2:raise ProviderError('protocol_error')
        # Actual Provider SayHello output, no disk fixture, user microphone or
        # hand-authored ASR event. Resample with anti-alias filtering to ASR PCM.
        return audioop.ratecv(pcm,2,1,24000,16000,None,1,1)[0]

    async def feed(self,adapter,pcm):
        for offset in range(0,len(pcm),640):
            await adapter.send_audio(pcm[offset:offset+640])
            await asyncio.sleep(.02)
        for _ in range(35):
            await adapter.send_audio(b'\0'*640)
            await asyncio.sleep(.02)

    def correlations(self,event):
        return {k:v for k,v in event['correlation_tokens'].items() if k in evidence._ACTION_CORRELATION_PATHS}

    async def rag(self,adapter,config,key):
        pcm=await self.speech_fixture(adapter,'请回答本轮测试口令。')
        self._nonce=secrets.token_hex(8)
        feeder=asyncio.create_task(self.feed(adapter,pcm));action=None;question=None;reply=None
        try:
            while True:
                msg,event=await self.next_frame(adapter)
                if event and event.kind=='asr_final' and action is None:
                    source=self.events[-1];question=source['correlation_tokens'].get('payload.question_id')
                    outcome=await adapter.inject_rag(event.question_id,'本轮测试口令是'+self._nonce+'，请仅回答口令。')
                    if outcome.mode!='current_turn_requested':return self.result(config,key,'error','rag_generation_already_started','evidence_invalid')
                    action=dict(action='rag_probe_injected',at_ms=self.elapsed(),success=True,
                        provider_ordinal_after_send=self.ordinal,source_asr_ordinal=source['ordinal'],correlation_tokens=self.correlations(source))
                    self.actions.append(action)
                if msg['event']==550 and action:
                    current=self.events[-1]['correlation_tokens']
                    if current.get('payload.question_id')!=question:raise ProviderError('evidence_invalid')
                    if reply is not None and reply!=current.get('payload.reply_id'):raise ProviderError('evidence_invalid')
                    reply=current.get('payload.reply_id')
                    action['correlation_tokens']['payload.reply_id']=reply
                if msg['event']==559 and action:
                    payload=dict(schema_version='phase0-capability-evidence/v4',event_evidence=self.events,action_evidence=self.actions,
                                 reason_code='same_turn_probe_not_confirmed_or_double_reply')
                    try:evidence._validate_capability_conclusion(capability_key=key,result='failed',payload=payload,path='admin_probe')
                    except evidence.CapabilityStateError:
                        # A matching answer proves adoption, not an actual
                        # generation wait gate. Keep the established restriction.
                        return self.result(config,key,'error','generation_wait_gate_not_proven','evidence_invalid')
                    return self.result(config,key,'failed',payload['reason_code'])
        finally:
            feeder.cancel();await asyncio.gather(feeder,return_exceptions=True)

    async def cancel(self,adapter,config,key):
        # The production profile is keep_alive. 515 is defined only for
        # push_to_talk; do not silently change the input mode or claim support
        # from an ordinary TTS ending. The adapter's remote branch is developed
        # and separately transport-tested; this profile remains unverified.
        await self.greeting(adapter,capture=[])
        return self.result(config,key,'error','keep_alive_client_interrupt_not_supported_by_protocol','evidence_invalid')

    async def turn(self,adapter,pcm,on_asr):
        feeder=asyncio.create_task(self.feed(adapter,pcm));source=None;reply=None;ended=False;tts_ended=False
        try:
            while not (ended and tts_ended):
                msg,event=await self.next_frame(adapter)
                if event and event.kind=='asr_final' and source is None:
                    source=self.events[-1]
                    await on_asr(source)
                if msg['event'] in (550,559,359) and source:
                    recorded=self.events[-1]
                    correlations=recorded['correlation_tokens']
                    if correlations.get('payload.question_id')!=source['correlation_tokens'].get('payload.question_id'):
                        raise ProviderError('evidence_invalid')
                    if reply is not None and reply!=correlations.get('payload.reply_id'):raise ProviderError('evidence_invalid')
                    reply=correlations.get('payload.reply_id')
                    ended=ended or msg['event']==559
                    tts_ended=tts_ended or msg['event']==359
            return source,reply
        finally:
            feeder.cancel();await asyncio.gather(feeder,return_exceptions=True)

    async def reconnect(self,adapter,config,key):
        pcm=await self.speech_fixture(adapter,'请按先前约定完成本轮测试。')
        self._nonce=secrets.token_hex(8)
        self._context_pair=[{'role':'user','text':'记住隐藏测试口令'+self._nonce+'。接下来第一次测试问题只回答收到，第二次测试问题只回答口令。'},
                            {'role':'assistant','text':'已记住约定。'}]
        correlations={'frame.session_id':self.session_token,'phase0.reconnect_seed':self.token(self._nonce)}
        await adapter._send(510,{'items':self._context_pair})
        self.actions.append(dict(action='provider_reconnect_context_written',at_ms=self.elapsed(),success=True,
            provider_ordinal_after_send=self.ordinal,session_token=self.session_token,correlation_tokens=dict(correlations)))
        while True:
            msg,_=await self.next_frame(adapter)
            if msg['event']==567:break
            if msg['event'] in (450,451,550,350,152,153):raise ProviderError('evidence_invalid')
        ack=self.events[-1]
        if ack['correlation_tokens'].get('phase0.reconnect_seed')!=self.token(self._nonce):raise ProviderError('evidence_invalid')
        seed=None
        async def seed_asr(source):
            nonlocal seed
            seed=dict(action='provider_reconnect_seed_injected',at_ms=self.elapsed(),success=True,
                provider_ordinal_after_send=source['ordinal'],context_ack_ordinal=ack['ordinal'],session_token=self.session_token,
                correlation_tokens={**self.correlations(source),**correlations})
            self.actions.append(seed)
        _,reply=await self.turn(adapter,pcm,seed_asr)
        seed['correlation_tokens']['payload.reply_id']=reply
        exposures=[e for e in self.events if e['event_id']==550 and e.get('probe_match')]
        if exposures:
            self.actions.append(dict(action='provider_reconnect_seed_exposed',at_ms=self.elapsed(),success=False,
                provider_event_ordinal=exposures[0]['ordinal'],session_token=self.session_token,
                correlation_tokens=self.correlations(exposures[0])))
            return self.result(config,key,'failed','reconnect_seed_exposed_before_disconnect')
        self.actions.append(dict(action='provider_reconnect_attempt',at_ms=self.elapsed(),success=True,
            provider_ordinal_before_attempt=self.ordinal,session_token=self.session_token,correlation_tokens=dict(correlations)))
        try:await adapter.reconnect_session()
        except ProviderError as exc:
            self.actions.append(dict(action='provider_reconnect_failed',at_ms=self.elapsed(),success=False,
                provider_ordinal_after_reconnect=self.ordinal,session_token=self.session_token,correlation_tokens=dict(correlations)))
            return self.failure_result(config,key,exc.category)
        self.actions.append(dict(action='provider_reconnect_succeeded',at_ms=self.elapsed(),success=True,
            provider_ordinal_after_reconnect=self.ordinal,session_token=self.session_token,correlation_tokens=dict(correlations)))
        async def recall_asr(source):
            self.actions.append(dict(action='provider_reconnect_question_observed',at_ms=self.elapsed(),success=True,
                provider_event_ordinal=source['ordinal'],session_token=self.session_token,correlation_tokens=self.correlations(source)))
        source,reply=await self.turn(adapter,pcm,recall_asr)
        matched=any(e['event_id']==550 and e['ordinal']>source['ordinal'] and e.get('probe_match') for e in self.events)
        self.actions.append(dict(action='provider_reconnect_context_confirmed',at_ms=self.elapsed(),success=matched,
            provider_ordinal_after_ack=self.ordinal,session_token=self.session_token,
            correlation_tokens={**self.correlations(source),'payload.reply_id':reply}))
        return self.result(config,key,'passed' if matched else 'failed',
            'hidden_seed_preserved_across_same_session_reconnect' if matched else 'same_session_reconnect_or_hidden_context_restore_failed')

    async def truncate(self,adapter,config,key):
        target=self.playback_target
        if target is None or not hasattr(target,'wait_stopped'):
            return self.result(config,key,'error','playback_target_missing','evidence_invalid')
        chunks=[]
        full=await self.greeting(adapter,'这是已播放的第一句。接下来这句话用于验证未播放内容截断。',capture=chunks)
        starts=[e for e in self.events if e['event_id']==350]
        ends=[e for e in self.events if e['event_id']==351]
        if len(starts)<2 or not ends or not chunks:raise ProviderError('evidence_invalid')
        first_end=ends[0]
        first_bytes=sum(e['payload_size'] for e in self.events if e['is_audio'] and starts[0]['ordinal']<e['ordinal']<first_end['ordinal'])
        if not 48<=first_bytes<full['audio_bytes'] or first_bytes>1024*1024:raise ProviderError('evidence_invalid')
        prefix=self._sentence_texts[0]
        if not isinstance(prefix,str) or not prefix:raise ProviderError('evidence_invalid')
        raw_reply=next((vendor for vendor,business in adapter._replies.items() if business==full['reply_id']),None)
        if raw_reply is None:raise ProviderError('evidence_invalid')
        pcm=b''.join(event.payload for event in chunks)
        await target.write_audio(replace(chunks[0],payload=pcm[:first_bytes]))
        expected={**full,'audio_bytes':first_bytes,'played_ms':first_bytes//48,'stopped':True}
        ack=await target.wait_stopped(**expected)
        if type(ack) is not dict or ack!=expected or type(ack.get('played_ms')) is not int or ack.get('stopped') is not True:
            raise ProviderError('evidence_invalid')
        self._speaker_output=True
        stop_token=self.token(uuid4());progress=self.elapsed();watermark=self.ordinal
        self.actions.append(dict(action='client_stop_playback_applied',at_ms=progress,success=True,stop_token=stop_token,
            target_reply_generation=1,provider_ordinal_after_ack=watermark,correlation_tokens=self.correlations(starts[0])))
        operations=[]
        async def operation(request,payload,ack_id):
            before=self.ordinal
            if request==513:
                await adapter.truncate_reply_context(full['reply_id'],expected['played_ms'],item_id=raw_reply)
            else:await adapter._send(request,payload)
            op=dict(request_event=request,before_ordinal=before,after_ordinal=self.ordinal,sent_at_ms=self.elapsed())
            operations.append(op)
            while True:
                msg,_=await self.next_frame(adapter)
                if msg['event']==ack_id:
                    op.update(ack_event=ack_id,ack_ordinal=self.ordinal,ack_at_ms=self.events[-1]['received_at_ms'])
                    return msg['payload']
                if msg['event'] in (150,152,153,450,451,569,570):raise ProviderError('evidence_invalid')
        before=await operation(512,{'items':[{'item_id':raw_reply}]},569)
        def text_of(payload):
            items=payload.get('items',[])
            if len(items)!=1 or items[0].get('item_id')!=raw_reply or items[0].get('role')!='assistant' or not isinstance(items[0].get('text'),str):
                raise ProviderError('evidence_invalid')
            return items[0]['text']
        before_text=text_of(before)
        if not before_text.startswith(prefix) or len(prefix)>=len(before_text):raise ProviderError('evidence_invalid')
        await operation(513,{},570)
        after_text=text_of(await operation(512,{'items':[{'item_id':raw_reply}]},569))
        passed=after_text==prefix
        reason='truncate_target_prefix_retained' if passed else 'truncate_readback_not_shortened'
        self._truncate_proof=dict(status='verified' if passed else 'failed',reason=reason,operations=operations,
            target_token=self.token(raw_reply),item_token=self.token(raw_reply),prefix_token=self.token(prefix),
            session_token=self.session_token,stop_token=stop_token,reply_generation=1,played_ms=expected['played_ms'],
            received_samples=len(pcm)//2,progress_at_ms=progress,progress_ordinal=watermark,
            before_chars=len(before_text),after_chars=len(after_text),retained_prefix=after_text==prefix and bool(after_text))
        return self.result(config,key,'passed' if passed else 'failed',reason)

    async def aclose(self):
        if self.playback_target is not None:
            target=self.playback_target
            self.playback_target=None
            async with asyncio.timeout(3):await target.aclose()

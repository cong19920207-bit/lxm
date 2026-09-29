"""Selective P0 backchannel policy, using call-frozen vocabulary and identities."""
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

def pure_ack(text, words):
    normalized = ''.join(re.findall(r'[0-9A-Za-z\u3400-\u9fff]+', text)).casefold()
    tokens = [''.join(re.findall(r'[0-9A-Za-z\u3400-\u9fff]+', w)).casefold() for w in words]
    tokens = sorted(set(filter(None,tokens)),key=len,reverse=True)
    return bool(normalized and tokens and re.fullmatch('(?:'+'|'.join(map(re.escape,tokens))+')+',normalized))

class BackchannelFilter:
    def __init__(self, words, deliver, discard, delete, observations=None):
        self.observations = observations
        self.words,self.deliver,self.discard,self.delete=words,deliver,discard,delete
        self.states={};self.buffers={};self.finished=set();self.deleted=set()
        self.tasks=set();self.lock=asyncio.Lock();self.sid=None;self.closed=False
    def task(self,coro):
        task=asyncio.create_task(coro);self.tasks.add(task);task.add_done_callback(self.tasks.discard)
    async def close(self):
        self.closed=True
        tasks=tuple(t for t in self.tasks if t is not asyncio.current_task())
        for t in tasks:t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        self.buffers.clear()
    async def release(self,q,reason):
        if self.observations:
            self.observations('decision', source='filter', result='escalated')
        self.states[q]='valid';frames=self.buffers.pop(q,[])
        logger.info('voice.backchannel.release reason=%s frames=%d',reason,len(frames))
        for frame in frames:await self.deliver(frame)
    async def timeout(self,q):
        await asyncio.sleep(2)
        async with self.lock:
            if not self.closed and self.states.get(q)=='candidate':await self.release(q,'timeout')
    async def cleanup(self,q):
        try:
            async with asyncio.timeout(2):await self.delete(q)
            logger.info('voice.backchannel.delete_sent question_id=%s',q)
        except Exception:
            logger.info('voice.backchannel.delete_failed question_id=%s',q)
    def schedule_delete(self,q):
        if q in self.finished and q not in self.deleted:
            self.deleted.add(q);self.task(self.cleanup(q))
    async def consume(self,event,playing=None):
        async with self.lock:
            if self.closed:return
            if self.sid is not None and self.sid!=event.session_id:
                for t in tuple(self.tasks):t.cancel()
                self.states.clear();self.buffers.clear();self.finished.clear();self.deleted.clear()
            self.sid=event.session_id
            # Interleaved original-story output also advances the sequence.
            for held,frames in list(self.buffers.items()):
                if frames and event.sequence - frames[0].sequence >= 64:
                    await self.release(held,'sequence_window')
            q=event.question_id
            if event.kind=='user_speech_started' and playing and q and q!=playing:
                if len(self.states)>=4096:raise ValueError('backchannel_turn_limit')
                if q not in self.states:
                    if self.observations:
                        self.observations('decision', source='filter', result='candidate')
                    self.states[q]='candidate';self.task(self.timeout(q))
                    logger.info('voice.backchannel.candidate question_id=%s playing_question_id=%s',q,playing)
            if event.kind=='context_deleted':
                matched=set(event.payload.get('question_ids',[])) & self.deleted
                logger.info('voice.backchannel.delete_ack matched=%d',len(matched))
            if event.kind=='asr_final' and self.states.get(q)=='candidate':
                if isinstance(event.payload,str) and pure_ack(event.payload,self.words['weak_acknowledgements']):
                    if self.observations:
                        self.observations('decision', source='filter', result='backchannel')
                    self.states[q]='blocked'
                    for frame in self.buffers.pop(q,[]):await self.discard(frame)
                    logger.info('voice.backchannel.filtered question_id=%s',q)
                    self.schedule_delete(q)
                else:await self.release(q,'meaningful_speech')
            output=event.kind in {'chat_text','sentence_started','sentence_finished','text_finished','tts_audio','tts_finished'}
            if event.kind=='tts_finished':self.finished.add(q)
            if output and self.states.get(q)=='candidate':
                frames=self.buffers.setdefault(q,[]);frames.append(event)
                # Stay below the turn service's 128-event reorder bound.
                if len(frames)>=64:await self.release(q,'buffer_limit')
                return
            if self.states.get(q)=='blocked' and (output or event.kind in {'asr_interim','asr_final','user_speech_finished'}):
                await self.discard(event)
                if event.kind=='tts_finished':self.schedule_delete(q)
                return
            await self.deliver(event)

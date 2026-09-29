"""Voice recall contracts; protocol fixtures do not grant production capability."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.services.realtime_voice_session_context_service import ContextResult


def api():
    from backend.services import realtime_voice_recall_service
    return realtime_voice_recall_service


class Context:
    def __init__(self): self.items=[]
    async def query(self, **kw):
        return ContextResult('ok',tuple(x for x in self.items if x['visible_from']<=kw['turn_index']))
    async def append(self, **kw):
        self.items=[x for x in self.items if (x['kind'],x['id'])!=(kw['kind'],kw['item_id'])]
        self.items.append(dict(kind=kw['kind'],id=kw['item_id'],text=kw['text'],visible_from=kw['turn_index']+int(kw.get('late',False)),turn_index=kw['turn_index']))
        return ContextResult('ok')


class Gate:
    async def assess(self, **kw):
        return SimpleNamespace(safety='matched' if 'UNSAFE' in kw['text'] else 'passed',crisis='passed')


class Adapter:
    def __init__(self, mode='current_turn_requested'): self.calls=[]; self.mode=mode
    async def inject_rag(self, question_id, content):
        self.calls.append((question_id,content)); return SimpleNamespace(mode=self.mode)


def script(**kw):
    return dict(prompt_template='',trigger_rules=['上次','记得'],max_query_chars=200,top_k=3,score_threshold=.7,
                timeout_ms=1000,embedding_timeout_ms=800,vector_timeout_ms=800,**kw)


def service(context=None, model=None, embed=None, search=None):
    async def default_model(prompt): return json.dumps(dict(needed=True,query='京都旅行',selected_ids=[],candidate_keys=[]))
    async def default_embed(query): return [1.,0.]
    async def default_search(**kw): return [dict(id=kw['memory_type'],content='计划去京都',score=.9,fields={})]
    return api().VoiceRecallService(session_context=context or Context(),gate=Gate(),model=model or default_model,
                                  embed=embed or default_embed,search=search or default_search)


async def recall(s, **kw):
    args=dict(call_id='call',user_id=1,question_id='q1',turn_index=1,user_text='还记得我的旅行计划吗',script=script(),preamble='',adapter=Adapter())
    args.update(kw)
    return await s.recall(**args)


@pytest.mark.asyncio
async def test_four_routes_private_scope_channel_neutral_and_actual_502_delivery():
    seen=[]
    async def search(**kw):
        seen.append(kw)
        return [dict(id=kw['memory_type'],content='京都:'+kw['memory_type'],score=.9,fields={'source_channel':'voice_call'})]
    adapter=Adapter(); s=service(search=search)
    out=await recall(s,adapter=adapter)
    assert out.status=='ready' and out.mode=='current_turn_requested' and len(out.items)==3
    assert {x['memory_type']:x['user_id'] for x in seen}=={'user':1,'character_private':1,'character_global':None,'character_knowledge':None}
    assert len(adapter.calls)==1 and len(adapter.calls[0][1])<=2000
    assert '京都' not in repr(out)


@pytest.mark.asyncio
async def test_short_term_before_preamble_no_vector_and_query_only_selects_real_ids():
    ctx=Context(); ctx.items=[dict(kind='correction',id='trip',text='改去京都',turn_index=1,visible_from=1)]
    async def model(prompt):
        data=json.loads(prompt.split('INPUT_JSON:\n')[1])
        assert data['short_term'][0]['text']=='改去京都'
        return json.dumps(dict(needed=True,query='旅行',selected_ids=['short:0','preamble:0','invented'],candidate_keys=[]))
    async def never(*a,**kw): raise AssertionError('must not access vector')
    out=await recall(service(ctx,model,never,never),preamble='记忆：原计划去大阪')
    assert out.source=='short_term' and [x['content'] for x in out.items]==['改去京都']


@pytest.mark.asyncio
async def test_no_trigger_or_unsafe_never_calls_vector_or_injects():
    async def model(prompt): return json.dumps(dict(needed=False,query='',selected_ids=[]))
    async def never(*a,**kw): raise AssertionError('unexpected outbound')
    a=Adapter(); s=service(model=model,embed=never,search=never)
    assert (await recall(s,adapter=a,user_text='今天天气不错')).status=='not_needed'
    assert (await recall(s,adapter=a,user_text='UNSAFE')).status=='filtered'
    assert a.calls==[]


@pytest.mark.asyncio
async def test_late_cached_next_turn_reused_without_vector_and_not_rewritten():
    ctx=Context(); s=service(ctx); a=Adapter('next_turn')
    first=await recall(s,adapter=a)
    assert first.mode=='next_turn_cached'
    assert all(x['visible_from']==2 for x in ctx.items)
    async def never(*a,**kw): raise AssertionError('cached topic must not search again')
    s.embed=never; s.search=never
    second=await recall(s,adapter=Adapter(),question_id='q2',turn_index=2)
    assert second.source=='topic_cache' and second.mode=='current_turn_requested'
    assert ctx.items[0]['visible_from']==2


@pytest.mark.asyncio
async def test_total_timeout_cancels_search_no_fabrication_or_send():
    finished=asyncio.Event()
    async def slow(**kw):
        try: await asyncio.Event().wait()
        finally: finished.set()
    cfg=script(); cfg['timeout_ms']=40
    a=Adapter(); out=await recall(service(search=slow),script=cfg,adapter=a)
    assert out.status=='timeout' and out.items==() and a.calls==[]
    assert finished.is_set()


@pytest.mark.asyncio
async def test_bad_rewrite_and_unsafe_results_never_reach_injection():
    async def bad(prompt): return '{bad'
    a=Adapter(); assert (await recall(service(model=bad),adapter=a)).status=='invalid_output'
    async def search(**kw): return [dict(id='x',content='UNSAFE',score=.99,fields={})]
    assert (await recall(service(search=search),adapter=a)).status=='empty'
    assert not a.calls


def test_rank_ignores_channel_and_drops_invalid_expired_deleted():
    rows=[dict(id='a',content='a',score=.8,fields={'quality':.9,'source_channel':'voice_call'}),dict(id='b',content='b',score=.8,fields={'quality':.9,'source_channel':'text'})]
    first=api().rank_results(rows,limit=3,threshold=.7)
    for row in rows: row['fields']['source_channel']='text' if row['fields']['source_channel']=='voice_call' else 'voice_call'
    assert api().rank_results(rows,limit=3,threshold=.7)==first
    rows += [dict(id='c',content='c',score=float('nan')),dict(id='d',content='d',score=.99,fields={'is_deleted':True}),dict(id='e',content='e',score=.99,fields={'expires_at':'2000-01-01T00:00:00Z'})]
    assert [x['id'] for x in api().rank_results(rows,limit=3,threshold=.7)]==['a','b']


@pytest.mark.asyncio
async def test_model_candidate_budget_equals_502_budget():
    ctx=Context(); original='背景'*350+'京都'
    ctx.items=[dict(kind='turn',id='long',text=original,visible_from=1,turn_index=1)]
    offered=[]
    async def model(prompt):
        candidate=json.loads(prompt.split('INPUT_JSON:\n')[1])['short_term'][0]
        offered.append(candidate['text'])
        return json.dumps(dict(needed=True,query='背景',selected_ids=[candidate['id']],candidate_keys=[]))
    adapter=Adapter()
    await recall(service(ctx,model=model),adapter=adapter)
    assert offered==[original[:600]]
    assert adapter.calls[0][1]==offered[0]


@pytest.mark.asyncio
async def test_preamble_and_safe_two_level_prefix():
    calls=[]
    async def local(prompt): return json.dumps(dict(needed=True,query='京都',selected_ids=['preamble:0'],candidate_keys=[]))
    async def never(*args,**kw): raise AssertionError('preamble is sufficient')
    out=await recall(service(model=local,embed=never,search=never),preamble='记忆：去京都')
    assert out.source=='preamble' and out.items[0]['content']=='去京都'
    async def model(prompt): return json.dumps(dict(needed=True,query='京都',selected_ids=[],candidate_keys=['经历-出行','旅行-计划-日本','bad" OR true']))
    async def search(**kw): calls.append(kw); return []
    await recall(service(model=model,search=search))
    assert len(calls)==4 and all(c['candidate_keys']==['经历-出行','旅行-计划-日本'] for c in calls)


@pytest.mark.asyncio
async def test_fence_during_retrieval_prevents_502():
    class FencedContext(Context):
        def __init__(self): super().__init__(); self.reads=0
        async def query(self,**kw):
            self.reads+=1
            return await super().query(**kw) if self.reads==1 else ContextResult('closed')
    a=Adapter(); out=await recall(service(FencedContext()),adapter=a)
    assert out.status=='context_unavailable' and not a.calls

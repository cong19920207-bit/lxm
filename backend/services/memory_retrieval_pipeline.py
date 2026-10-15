"""M4/012 shared 45+45 orchestration. No business activation or new deadline."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from types import MappingProxyType

import httpx

from backend.services.memory_provider_service import ProviderError, _request, _client
from backend.services.query_rewrite_service import parse_memory_queries, _build_step1_5_prompt
from backend.services.memory_hybrid_retrieval import RouteResult, retrieve_route, CandidateValidator
from backend.services.memory_rerank import rerank_route


class StageBudget:
    def __init__(self, deadline, limits, *, reserve=0, backoff=.25, clock=time.monotonic, sleep=asyncio.sleep, counts=None):
        self.deadline, self.limits, self.reserve = deadline, limits, reserve
        self.backoff, self.clock, self.sleep = backoff, clock, sleep
        self.counts = counts if counts is not None else {}

    async def __call__(self, kind, invoke):
        return await self.call(kind, invoke)

    async def call(self, kind, invoke):
        end = self.deadline - self.reserve
        for attempt in range(2):
            remaining = end - self.clock()
            if remaining <= 0:
                raise TimeoutError('stage_deadline')
            timeout = min(self.limits[kind], remaining)
            started = self.clock()
            try:
                async with asyncio.timeout(timeout):
                    self.counts[kind] = self.counts.get(kind, 0) + 1
                    value = await invoke()
                # Reject adapters which swallowed cancellation and returned late.
                if self.clock() >= min(end, started + timeout):
                    raise TimeoutError('call_deadline')
                if getattr(value, 'retryable', False):
                    raise ProviderError('query_unavailable', retryable=True)
                return value
            except (ProviderError, httpx.TransportError, TimeoutError) as exc:
                retryable = not isinstance(exc, ProviderError) or exc.retryable
                if not retryable or attempt or end - self.clock() <= self.backoff:
                    raise
                await self.sleep(self.backoff)
        raise TimeoutError('stage_deadline')


@dataclass(frozen=True)
class RetrievalResult:
    config_snapshot_id: str
    queries: object
    routes: object
    rewrite_deadline: float
    retrieval_deadline: float
    call_counts: object = field(default_factory=dict)


async def run_pipeline(*, config, original_input, prompt, original_deadline,
                       rewrite, retrieve, rank, clock=time.monotonic):
    counts = {}
    timeouts = config.profiles['timeouts_ms']
    limits = {'rewrite': timeouts['rewrite_call']/1000, 'embedding': timeouts['embedding_call']/1000,
              'vector_query': timeouts['vector_query']/1000, 'rerank': timeouts['rerank_call']/1000}
    rewrite_end = min(clock() + timeouts['rewrite_stage']/1000, original_deadline)
    rewrite_budget = StageBudget(rewrite_end, limits, clock=clock, backoff=timeouts['retry_backoff']/1000, counts=counts)
    try:
        raw = await rewrite_budget.call('rewrite', lambda: rewrite(prompt))
    except Exception:
        raw = ''
    queries = parse_memory_queries(raw, original_input)
    retrieval_end = min(clock() + timeouts['retrieval_stage']/1000, original_deadline)
    candidates_budget = StageBudget(retrieval_end, limits, reserve=timeouts['validation_reserve']/1000,
                                   clock=clock, backoff=timeouts['retry_backoff']/1000, counts=counts)
    ranking_budget = StageBudget(retrieval_end, limits, clock=clock, backoff=timeouts['retry_backoff']/1000, counts=counts)

    async def route_work(route, query):
        if query.skipped:
            return RouteResult(route, query.question, reason='explicit_skip')
        if clock() >= retrieval_end:
            return RouteResult(route, query.question, reason='stage_deadline')
        try:
            async with asyncio.timeout(max(0, retrieval_end - clock())):
                candidate_result = await retrieve(route, query, candidates_budget)
            if clock() > retrieval_end:
                return RouteResult(route, query.question, reason='source_unverified')
        except Exception:
            return RouteResult(route, query.question, reason='source_unverified')
        async def bounded_rank(question, documents):
            return await ranking_budget.call('rerank', lambda: rank(question, documents))
        return await rerank_route(candidate_result,
            threshold=config.retrieval['routes'][route]['rerank_min_score'], rank=bounded_rank)

    results = await asyncio.gather(*(route_work(route, query) for route, query in queries.routes.items()))
    return RetrievalResult(config.config_snapshot_id, queries,
                           MappingProxyType(dict(zip(queries.routes, results))), rewrite_end, retrieval_end, MappingProxyType(counts))


class RewriteProvider:
    """Single HTTP attempt, frozen endpoint/model/secret; outer budget owns retries."""
    def __init__(self, endpoint, model, credential, *, client=None):
        self.endpoint, self.model, self.credential, self.client = endpoint.rstrip('/'), model, credential, client

    async def __call__(self, prompt):
        body = {'model': self.model, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False}
        # Step1.5 generates the existing query fields, not a chat reply. This
        # verified model otherwise defaults to hidden thinking that exhausts
        # the bounded rewrite call; leave other models and Step5 unchanged.
        if self.model == 'doubao-seed-2-0-lite-260428':
            body['thinking'] = {'type': 'disabled'}
        async with _client(self.client) as client:
            result = await _request(client, 'post', self.endpoint + '/chat/completions',
                headers={'Authorization': 'Bearer ' + self.credential.reveal()},
                json=body)
        try:
            value = result['choices'][0]['message']['content']
            if not isinstance(value, str):
                raise ValueError()
            return value
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError('rewrite_response_invalid') from None


async def execute_memory_retrieval(*, config, session_factory, environment_id, partition, user_id,
                                   original_deadline, rewrite_input, persona_text, round_context,
                                   recent_conversations, rewrite_provider, source='main', allow_isolated=False,
                                   client=None, cache=None):
    """Concrete provider/SQL composition for M6 and diagnostics; no hidden mocks."""
    from backend.services.memory_bm25 import get_encoder
    from backend.services.memory_embedding_cache import MemoryEmbeddingCache
    from backend.services.memory_provider_service import embedding, rerank
    from backend.utils.memory_vector_client import MemoryVectorClient
    if config.target_epoch is None:
        raise ValueError('active_config_required')
    remote = MemoryVectorClient(config.providers['dashvector'], client=client)
    validator = CandidateValidator(session_factory, environment_id, allow_isolated=allow_isolated)
    async def embed_provider(cfg, texts, text_type):
        return await embedding(cfg, texts, text_type, client=client)
    embeddings = MemoryEmbeddingCache(config.providers['embedding'], cache=cache, embed=embed_provider)
    async def embed(text): return await embeddings.get_embedding(text, text_type='query')
    async def retrieve(route, query, call):
        return await retrieve_route(route, query, user_id=user_id, partition=partition, config=config,
            remote=remote, encoder=get_encoder(), embed=embed, validator=validator, call=call)
    async def rank(question, documents):
        return await rerank(config.providers['rerank'], question, documents, client=client)
    prompt = _build_step1_5_prompt(persona_text=persona_text, round_context=round_context,
        recent_conversations=recent_conversations, rewrite_input=rewrite_input, source=source)
    return await run_pipeline(config=config, original_input=rewrite_input, prompt=prompt,
        original_deadline=original_deadline, rewrite=rewrite_provider, retrieve=retrieve, rank=rank)

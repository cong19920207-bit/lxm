"""Exact rendered-text budget measurement; final Prompt selection is wired in STEP-013."""
import asyncio
import hashlib
import time

import httpx


class BudgetUnverified(RuntimeError):
    def __init__(self):
        super().__init__("prompt_budget_unverified")


class OfficialTextCounter:
    """One request's frozen Ark counter. Never logs credentials or provider payloads."""
    def __init__(self, endpoint, model, api_key, *, client=None, deadline=None):
        if model != "doubao-seed-2-0-lite-260428" or endpoint.rstrip('/') != "https://ark.cn-beijing.volces.com/api/v3":
            raise BudgetUnverified()
        self.endpoint = endpoint.rstrip('/')
        self.model = model
        self._key = api_key
        self._client = client
        self._deadline = deadline
        self._counts = {}
        self.request_count = 0
        self.id = f"ark-tokenization:{model}:render-v1"

    @classmethod
    def from_config(cls, config, credential, *, deadline, client=None):
        profile = config.profiles.get('counter', {})
        endpoint = profile.get('endpoint', '')
        if not endpoint.endswith('/tokenization'):
            raise BudgetUnverified()
        counter = cls(endpoint.removesuffix('/tokenization'), config.reply_model,
                      credential.reveal(), deadline=deadline, client=client)
        validate_bound_counter(config, counter)
        return counter

    async def count(self, rendered: str) -> int:
        return (await self.count_many([rendered]))[0]

    async def count_many(self, rendered):
        values = tuple(rendered)
        keys = [hashlib.sha256(value.encode()).digest() for value in values]
        missing = dict((key,value) for key,value in zip(keys,values) if key not in self._counts)
        pending = list(missing.items())
        # Conservative microbatches; prefix counts never become summed estimates.
        for start in range(0,len(pending),10):
            batch = pending[start:start+10]
            counts = await self._count_batch([value for key,value in batch])
            self._counts.update((key,count) for (key,value),count in zip(batch,counts))
        return tuple(self._counts[key] for key in keys)

    async def _count_batch(self, texts):
        for attempt in range(2):
            remaining = 5.0 if self._deadline is None else min(5.0, self._deadline - time.monotonic())
            if remaining <= 0:
                raise BudgetUnverified()
            try:
                if self._client is None:
                    async with httpx.AsyncClient(timeout=remaining, follow_redirects=False) as client:
                        response = await self._call(client, texts, remaining)
                else:
                    response = await self._call(self._client, texts, remaining)
                retryable = response.status_code == 429 or response.status_code >= 500
                if response.status_code != 200:
                    if retryable and attempt == 0:
                        await self._backoff()
                        continue
                    raise BudgetUnverified()
                data = response.json()
                if not isinstance(data, dict):
                    raise BudgetUnverified()
                rows = data.get('data')
                if not isinstance(rows, list) or len(rows) != len(texts):
                    raise BudgetUnverified()
                mapped = {}
                for row in rows:
                    if (not isinstance(row,dict) or type(row.get('index')) is not int
                            or not 0 <= row['index'] < len(texts) or row['index'] in mapped
                            or type(row.get('total_tokens')) is not int or row['total_tokens'] < 0):
                        raise BudgetUnverified()
                    mapped[row['index']] = row['total_tokens']
                return tuple(mapped[i] for i in range(len(texts)))
            except (httpx.TransportError, TimeoutError):
                if attempt == 0:
                    await self._backoff()
                    continue
                raise BudgetUnverified() from None
            except (ValueError, TypeError, KeyError):
                raise BudgetUnverified() from None
        raise BudgetUnverified()

    async def _backoff(self):
        if self._deadline is not None and self._deadline - time.monotonic() <= .25:
            raise BudgetUnverified()
        await asyncio.sleep(.25)

    async def _call(self, client, texts, timeout):
        async with asyncio.timeout(timeout):
            self.request_count += 1
            return await client.post(self.endpoint + '/tokenization',
                                     headers={'Authorization': 'Bearer ' + self._key},
                                     json={'model': self.model, 'text': texts}, timeout=timeout, follow_redirects=False)


async def measure_rendered_budget(rendered: str, max_total: int, counter) -> dict:
    """Full rendered nickname stays in rendered; fixed nickname=50 is never a slice."""
    count = await counter.count(rendered)
    if type(count) is not int or count < 0 or type(max_total) is not int or not 1024 <= max_total <= 32768:
        raise BudgetUnverified()
    return {'rendered_tokens': count, 'envelope_reserve': 64, 'total_charge': count + 64,
            'max_total': max_total, 'over_budget': count + 64 > max_total}


def validate_bound_counter(config, counter):
    """Reject approximate/other-model counters before any selection or source use."""
    profile = config.profiles.get('counter', {})
    if (type(counter) is not OfficialTextCounter
            or counter.model != config.reply_model or profile.get('model') != config.reply_model
            or counter.id != profile.get('id')
            or counter.id != f'ark-tokenization:{config.reply_model}:render-v1'
            or counter.endpoint != 'https://ark.cn-beijing.volces.com/api/v3'
            or counter.endpoint + '/tokenization' != profile.get('endpoint')
            or profile.get('envelope_reserve') != 64 or profile.get('timeout_ms') != 5000
            or profile.get('max_retry') != 1):
        raise BudgetUnverified()

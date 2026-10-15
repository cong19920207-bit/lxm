"""Own the HTTP input socket until body handoff or joined cancellation.

httpcore's send_request_body.complete is emitted only after all body chunks
have been written. A response timeout does not undo a completed input handoff.
No retry lives here: business generation/terminal state remains M6's concern.
"""
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import time

import httpx


class ModelHandoffError(RuntimeError):
    pass


class GuardedModelClient:
    def __init__(self, endpoint, model, credential, *, transport=None):
        self.endpoint, self.model, self.credential = endpoint.rstrip('/'),model,credential
        self.transport = transport

    async def send(self, result, *, guard, owner_id, deadline):
        if result.use_deadline_at is None:
            raise ModelHandoffError('model_input_not_reserved')
        original = result.use_deadline_at
        if original.tzinfo is None: original = original.replace(tzinfo=timezone.utc)
        deadline = min(deadline, time.monotonic()+(original-datetime.now(timezone.utc)).total_seconds())
        if (result.over_budget or not result.use_claim_id or deadline <= time.monotonic()
                or result.counter['model'] != self.model):
            raise ModelHandoffError('model_input_not_ready')
        async def bounded_receipt(method, *, limit=2):
            remaining = min(limit,deadline-time.monotonic())
            if remaining <= 0: raise TimeoutError()
            async with asyncio.timeout(remaining):
                return await method(result.use_claim_id,owner_id)

        try:
            state = await bounded_receipt(guard.begin_handoff)
        except asyncio.CancelledError:
            raise
        except Exception:
            raise ModelHandoffError('model_input_not_ready') from None
        if state != 'dispatching':
            raise ModelHandoffError('model_input_already_dispatched')
        sent, delivered = False, asyncio.Event()
        request_task = event_task = None
        client = httpx.AsyncClient(transport=self.transport, follow_redirects=False, http2=False)

        async def trace(event, info):
            nonlocal sent
            if event in {'http11.send_request_body.complete','http2.send_request_body.complete'}:
                sent = True
                await bounded_receipt(guard.confirm_handoff)
                delivered.set()

        async def request():
            if deadline <= time.monotonic(): raise TimeoutError()
            return await client.post(self.endpoint+'/chat/completions',
                headers={'Authorization':'Bearer '+self.credential.reveal()},
                json={'model':self.model,'messages':[{'role':'user','content':result.prompt}],'stream':False},
                extensions={'trace':trace},timeout=max(.001,deadline-time.monotonic()))

        try:
            if deadline <= time.monotonic(): raise TimeoutError()
            request_task = asyncio.create_task(request())
            event_task = asyncio.create_task(delivered.wait())
            done,_ = await asyncio.wait({request_task,event_task},
                timeout=min(5,deadline-time.monotonic()),return_when=asyncio.FIRST_COMPLETED)
            if not done or not delivered.is_set():
                # Check an already completed request's exception without leaking
                # its URL/body. A transport lacking handoff evidence fails closed.
                if request_task.done(): await request_task
                raise ModelHandoffError('model_handoff_unverified')
            async with asyncio.timeout(max(0,deadline-time.monotonic())):
                response = await request_task
            if response.status_code != 200:
                raise ModelHandoffError('model_response_unavailable')
            data = response.json()
            if not isinstance(data,dict): raise ModelHandoffError('model_response_invalid')
            return data
        except asyncio.CancelledError:
            raise
        except Exception:
            raise ModelHandoffError('model_response_unavailable') from None
        finally:
            # No detached sender may survive protection release. Cancellation is
            # joined, then the privately-owned client closes its socket/pool.
            for task in (request_task,event_task):
                if task is not None and not task.done(): task.cancel()
            for task in (request_task,event_task):
                if task is not None:
                    with suppress(asyncio.CancelledError,Exception): await task
            try:
                async with asyncio.timeout(max(0,min(2,deadline-time.monotonic()))):
                    await client.aclose()
                if sent:
                    await bounded_receipt(guard.confirm_handoff)
                else:
                    await bounded_receipt(guard.confirm_stopped)
            except Exception:
                # SQL receipt/closure failure keeps the durable dispatch fence.
                with suppress(Exception): await bounded_receipt(guard.mark_unknown)

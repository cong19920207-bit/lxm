"""Application lifecycle owner for the finite index worker; never reopens old rounds."""
import asyncio
from contextlib import suppress
import hashlib
import logging
import os
import time

from sqlalchemy import select

from backend.models.memory_control import MemoryRuntimeFence
from backend.services.memory_bm25 import BM25Error, get_encoder
from backend.services.memory_effective_config import resolve_provider
from backend.services.memory_index_worker import MemoryIndexWorker
from backend.services.memory_runtime_service import MemoryControlError, require_active_fence
from backend.utils.memory_vector_client import MemoryVectorClient

log = logging.getLogger(__name__)


async def load_worker():
    """Read current publication and activation; do not depend on reply/rerank config."""
    environment = os.getenv('MEMORY_RUNTIME_ENVIRONMENT_ID', '').strip()
    if not environment:
        return None
    from backend import config
    from backend.database import async_session_maker
    provider_env = {'dashvector': {
        'endpoint': config.get_dashvector_endpoint(),
        'collection_name': config.get_dashvector_collection(),
        'api_key': config.get_dashvector_api_key(),
    }}
    async with async_session_maker() as db:
        provider = await resolve_provider(db, 'dashvector', env=provider_env)
        fingerprint = hashlib.sha256(
            f'{provider.endpoint}/v1/collections/{provider.collection_name}'.encode()).digest()
        fence = await db.scalar(select(MemoryRuntimeFence).where(
            MemoryRuntimeFence.environment_id == environment))
        if fence is None:
            raise MemoryControlError(20126, 'runtime_not_active')
        fence = await require_active_fence(db, environment, fence.target_epoch, fingerprint, lock=False)
        epoch = fence.target_epoch
    encoder = get_encoder()
    # Equality includes provider credentials/revision without logging them.
    signature = (environment, epoch, fingerprint, encoder.encoder_version, provider)
    return signature, lambda: MemoryIndexWorker(
        async_session_maker, MemoryVectorClient(provider), encoder, environment, epoch, fingerprint)


class MemoryIndexRuntime:
    def __init__(self, *, loader=load_worker, interval=5):
        self.loader, self.interval = loader, interval
        self._task = self._worker = self._worker_task = self._signature = None
        self._problem = None
        self._reported_at = 0.0

    async def _stop_worker(self):
        if self._worker is not None:
            await self._worker.stop()
            self._worker = self._worker_task = self._signature = None

    async def refresh(self):
        try:
            async with asyncio.timeout(5):
                current = await self.loader()
            if current is None:
                await self._stop_worker()
                return
            signature, build = current
            alive = self._worker is not None and (
                self._worker_task is None or not self._worker_task.done())
            if signature != self._signature or not alive:
                await self._stop_worker()
                worker = build()
                self._worker = worker
                self._worker_task = worker.start()
                self._signature = signature
                log.info('memory_index_runtime_started')
            if self._problem is not None:
                log.info('memory_index_runtime_recovered')
                self._problem = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._stop_worker()
            # Exception strings can include URLs/credentials. Only known codes or type.
            known = {'runtime_not_active', 'runtime_target_changed', 'activation_unverified',
                     'configuration_read_unavailable', 'bm25_profile_unavailable',
                     'bm25_package_mismatch', 'bm25_profile_mismatch', 'bm25_statistics_mismatch',
                     'bm25_analyzer_mismatch'}
            reason = getattr(exc, 'reason', None)
            if isinstance(exc, BM25Error) and exc.args:
                reason = exc.args[0]
            reason = reason if reason in known else type(exc).__name__
            now = time.monotonic()
            if reason != self._problem or now - self._reported_at >= 60:
                log.warning('memory_index_runtime_unavailable reason=%s', reason)
                self._problem, self._reported_at = reason, now

    async def _run(self):
        while True:
            await self.refresh()
            await asyncio.sleep(self.interval)

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name='memory-index-runtime')
        return self._task

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._stop_worker()
        log.info('memory_index_runtime_stopped')


_runtime = MemoryIndexRuntime()


def start():
    return _runtime.start()


async def stop():
    await _runtime.stop()

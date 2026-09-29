"""Metadata-only last writer and bounded, task-local prewrite observations.

A prewrite observation is not a content conflict or an atomic overwrite proof.
Missing records, legacy records and failed reads all remain unknown.
"""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar

SOURCES = frozenset({'voice', 'text', 'admin', 'unknown'})
_observations = ContextVar('memory_source_observations', default=None)


def read_write_source(fields):
    value = fields.get('last_write_source') if isinstance(fields, dict) else None
    return value if isinstance(value, str) and value in SOURCES else 'unknown'


@contextmanager
def collect_source_observations():
    observations = []
    token = _observations.set(observations)
    try:
        yield observations
    finally:
        _observations.reset(token)


async def observe_previous_source(client, doc_id):
    # Only the voice job consumer requests an observation. No extra text/admin read.
    if _observations.get() is None:
        return 'unknown'
    try:
        found = await asyncio.wait_for(client.fetch_by_ids([doc_id]), timeout=0.25)
        return read_write_source((found.get(doc_id) or {}).get('fields'))
    except Exception:
        return 'unknown'


def record_source_observation(previous):
    observations = _observations.get()
    if observations is not None:
        observations.append(previous)

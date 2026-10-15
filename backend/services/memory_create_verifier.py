"""Independent absence proof for a first admin create, never write reconciliation.

The caller must first observe HTTP success with *missing* output. No general
fetch result is changed here, and this module has no source/index write API.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time
from urllib.parse import urlsplit

from backend.utils.memory_vector_client import MemoryVectorClient, _name


VERIFY_TIMEOUT_SECONDS = 5.0
# Client initialization, collection description and fetch each perform an RPC.
RPC_TIMEOUT_SECONDS = 1.5
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='memory-create-read')
_slots = threading.BoundedSemaphore(4)


def _success(response):
    return type(getattr(response, 'code', None)) is int and response.code == 0


def _probe(config, partition, doc_id, deadline, stopped):
    client = None
    def active():
        return not stopped.is_set() and time.monotonic() < deadline
    try:
        # Reuse the same target profile guards, without resolving fresh config.
        MemoryVectorClient(config)
        _name(partition)
        _name(doc_id)
        endpoint = urlsplit(config.endpoint)
        if (endpoint.scheme != 'https' or not endpoint.hostname or endpoint.username
                or endpoint.password or endpoint.path not in {'', '/'}
                or endpoint.query or endpoint.fragment):
            return False
        _ = endpoint.port
        # SDK reads this environment override itself; never send credentials on
        # an insecure gRPC channel, even if the original HTTP URL was HTTPS.
        if os.getenv('DASHVECTOR_INSECURE_MODE', 'False').lower() in {'true', '1'}:
            return False
        import dashvector
        if not active():
            return False
        client = dashvector.Client(api_key=config.credential.reveal(), endpoint=endpoint.netloc,
                                  timeout=RPC_TIMEOUT_SECONDS, protocol=dashvector.DashVectorProtocol.GRPC)
        if not active() or not _success(client):
            return False
        collection = client.get(config.collection_name)
        # SDK uses returned collection metadata (not the requested name) when
        # constructing fetch, so verify it before allowing another request.
        if (not active() or not _success(collection)
                or getattr(getattr(collection, 'output', None), 'name', None) != config.collection_name):
            return False
        result = collection.fetch(doc_id, partition=partition)
        # Nonempty, malformed and unsuccessful responses never authorize create.
        return (active() and _success(result) and type(getattr(result, 'output', None)) is dict
                and not result.output and isinstance(getattr(result, 'request_id', None), str)
                and bool(result.request_id.strip()))
    except Exception:
        # No exception text, provider response, credentials or memory content.
        return False
    finally:
        if client is not None:
            try:
                # SDK 1.0.23 Client.close() skips the channel on failed init.
                handler = getattr(client, '_handler', None)
                if handler is not None:
                    handler.close()
                else:
                    client.close()
            except Exception:
                pass


async def verify_create_absence(config, partition, doc_id):
    """Return True only for a timely, authenticated empty gRPC document map.

Slots cover the lifetime of real threads, including after a request times out
or is cancelled. Saturation fails closed immediately; there is no retry queue.
"""
    slots = _slots
    if not slots.acquire(blocking=False):
        return False
    stopped = threading.Event()
    deadline = time.monotonic() + VERIFY_TIMEOUT_SECONDS
    try:
        future = _executor.submit(_probe, config, partition, doc_id, deadline, stopped)
    except Exception:
        slots.release()
        return False
    future.add_done_callback(lambda _: slots.release())
    try:
        result = await asyncio.wait_for(asyncio.wrap_future(future),
                                        timeout=max(0, deadline - time.monotonic()))
        return result is True and time.monotonic() < deadline
    except Exception:
        return False
    finally:
        stopped.set()

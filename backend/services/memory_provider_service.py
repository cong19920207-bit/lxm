"""Read-only provider probes share exactly the runtime frozen provider config."""
from __future__ import annotations

from contextlib import asynccontextmanager
import math
import time
import httpx

from backend.services.memory_effective_config import ProviderConfig
from backend.utils.memory_vector import normalize_dense


class ProviderError(RuntimeError):
    def __init__(self, reason: str, *, retryable=False):
        self.reason = reason
        self.retryable = retryable
        super().__init__(reason)


@asynccontextmanager
async def _client(client=None):
    if client is not None:
        yield client
    else:
        import httpx
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as active:
            yield active


async def _request(client, method, url, **kwargs):
    try:
        response = await getattr(client, method)(url, **kwargs)
        if response.status_code != 200:
            raise ProviderError("provider_http_error", retryable=response.status_code == 429 or response.status_code >= 500)
        data = response.json()
        if not isinstance(data, dict) or ("code" in data and (type(data["code"]) is not int or data["code"] != 0)):
            raise ProviderError("provider_business_error")
        return data
    except ProviderError:
        raise
    except (TimeoutError, httpx.TransportError):
        raise ProviderError("provider_response_unavailable", retryable=True) from None
    except Exception:
        # Requests and provider bodies can embed credentials. Never stringify.
        raise ProviderError("provider_response_unavailable") from None


def _headers(config):
    if config.service == "dashvector":
        return {"Content-Type": "application/json", "dashvector-auth-token": config.credential.reveal()}
    return {"Content-Type": "application/json", "Authorization": "Bearer " + config.credential.reveal()}


def _vector(value, dimension):
    try:
        return tuple(normalize_dense(value, dimension))
    except ValueError:
        raise ProviderError("embedding_vector_invalid") from None


async def embedding(config: ProviderConfig, texts: list[str], text_type: str = "document", *, client=None) -> tuple:
    if config.service != "embedding":
        raise ProviderError("provider_kind_mismatch")
    if text_type not in ("query", "document") or not isinstance(texts, list) or not 1 <= len(texts) <= 10 or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ProviderError("embedding_input_invalid")
    async with _client(client) as active:
        data = await _request(active, "post", config.endpoint, headers=_headers(config), json={
            "model": config.model, "input": {"texts": texts},
            "parameters": {"dimension": config.dimension, "text_type": text_type},
        })
    output = data.get("output")
    embeddings = output.get("embeddings") if isinstance(output, dict) else None
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise ProviderError("embedding_response_invalid")
    by_index = {}
    for row in embeddings:
        if not isinstance(row, dict) or type(row.get("text_index")) is not int or not 0 <= row["text_index"] < len(texts) or row["text_index"] in by_index:
            raise ProviderError("embedding_response_invalid")
        by_index[row["text_index"]] = _vector(row.get("embedding"), config.dimension)
    return tuple(by_index[index] for index in range(len(texts)))


async def embed_query(config: ProviderConfig, text: str, *, client=None) -> tuple[float, ...]:
    return (await embedding(config, [text], "query", client=client))[0]


async def rerank(config: ProviderConfig, query: str, documents: list[str], *, client=None) -> tuple:
    if config.service != "rerank":
        raise ProviderError("provider_kind_mismatch")
    count = len(documents)
    if not count:
        return ()
    # This conservative guard is deliberately not advertised as real tokens.
    sizes = [len(value.encode("utf-8")) + 32 for value in documents]
    query_size = len(query.encode("utf-8")) + 32
    if count > 500 or max([query_size, *sizes]) > 4000 or count * query_size + sum(sizes) > 30000:
        raise ProviderError("local_size_guard")
    async with _client(client) as active:
        data = await _request(active, "post", config.endpoint, headers=_headers(config), json={
            "model": config.model, "input": {"query": query, "documents": documents},
            "parameters": {"top_n": count},
        })
    output = data.get("output")
    results = output.get("results") if isinstance(output, dict) else None
    if not isinstance(results, list) or len(results) != count:
        raise ProviderError("rerank_mapping_invalid")
    pairs, seen = [], set()
    for row in results:
        if not isinstance(row, dict):
            raise ProviderError("rerank_mapping_invalid")
        index, score = row.get("index"), row.get("relevance_score")
        if type(index) is not int or not 0 <= index < count or index in seen or type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ProviderError("rerank_mapping_invalid")
        seen.add(index)
        pairs.append((index, float(score)))
    return tuple(pairs)


async def describe_collection(config: ProviderConfig, *, client=None) -> None:
    if config.service != "dashvector":
        raise ProviderError("provider_kind_mismatch")
    async with _client(client) as active:
        data = await _request(active, "get", f"{config.endpoint}/v1/collections/{config.collection_name}", headers=_headers(config))
    output = data.get("output")
    if type(data.get("code")) is not int or data["code"] != 0 or not isinstance(output, dict) or output.get("name") != config.collection_name or type(output.get("dimension")) is not int or output["dimension"] != 1024 or str(output.get("dtype", "")).upper() != "FLOAT" or output.get("metric") != "dotproduct" or str(output.get("status", "")).upper() != "SERVING":
        raise ProviderError("collection_profile_mismatch")


async def probe_provider(config: ProviderConfig, *, client=None) -> dict:
    start = time.monotonic()
    result = {"connected": False, "latency_ms": 0, "error": "", "reason": None}
    try:
        if config.service == "dashvector":
            await describe_collection(config, client=client)
        elif config.service == "embedding":
            await embed_query(config, "连接测试", client=client)
        elif config.service == "rerank":
            await rerank(config, "饮料", ["红茶", "咖啡"], client=client)
        else:
            raise ProviderError("provider_kind_mismatch")
        result["connected"] = True
    except ProviderError as exc:
        result.update(error="连接或能力核验失败", reason=exc.reason)
    except Exception:
        result.update(error="连接或能力核验失败", reason="provider_response_unavailable")
    result["latency_ms"] = int((time.monotonic() - start) * 1000)
    return result

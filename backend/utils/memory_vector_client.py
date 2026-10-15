"""New-target DotProduct protocol. No retries, legacy target or physical deletes.

All writes must be called by the durable mutation coordinator after dispatch
fencing. A read cannot declare an unknown write absent; it only confirms the
exact prepared operation when its unique metadata and full payload match.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
import re

from backend.services.memory_effective_config import ProviderConfig, TARGET_COLLECTION
from backend.services.memory_provider_service import _client, _request as provider_request, ProviderError
from backend.utils.memory_vector import normalize_dense, validate_sparse


@dataclass(frozen=True)
class WriteResult:
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class FetchResult:
    status: str
    document: dict | None = field(default=None, repr=False)
    reason: str | None = None


@dataclass(frozen=True)
class QueryResult:
    status: str
    documents: tuple = field(default=(), repr=False)
    reason: str | None = None
    no_lexical_match: int = 0
    retryable: bool = False


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("identity_invalid")
    return value


def _success(data):
    return isinstance(data, dict) and type(data.get("code")) is int and data["code"] == 0


def _prepared_document(document):
    if not isinstance(document, dict) or not {"id", "vector", "fields"} <= set(document) or set(document) - {"id", "vector", "fields", "sparse_vector"}:
        raise ValueError("document_invalid")
    _name(document["id"])
    if not isinstance(document["fields"], dict):
        raise ValueError("document_invalid")
    # JSON roundtrip both detaches callers and rejects NaN/unsupported objects.
    result = json.loads(json.dumps(document, allow_nan=False))
    result["vector"] = normalize_dense(result["vector"])
    if "sparse_vector" in result:
        result["sparse_vector"] = validate_sparse(result["sparse_vector"])
    return result


def _matches_prepared(expected, observed):
    fields = expected["fields"]
    required = ("mr_epoch", "mr_generation", "mr_body_sha256", "mr_operation_id", "type", "user_id", "mr_deleted")
    if not all(key in fields for key in required) or not observed:
        return False
    try:
        if observed.get("id") != expected["id"] or json.dumps(observed.get("fields"), sort_keys=True, allow_nan=False) != json.dumps(fields, sort_keys=True, allow_nan=False):
            return False
        raw = observed.get("vector")
        normalize_dense(raw)  # Validate, but compare raw values (not repaired ones).
        if any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in zip(expected["vector"], raw)):
            return False
        raw_sparse = observed.get("sparse_vector")
        sparse = validate_sparse({} if raw_sparse is None else raw_sparse)
        wanted = expected.get("sparse_vector", {})
        return set(sparse) == set(wanted) and all(math.isclose(sparse[k], wanted[k], rel_tol=0, abs_tol=1e-6) for k in wanted)
    except (TypeError, ValueError, OverflowError):
        return False


class MemoryVectorClient:
    def __init__(self, config: ProviderConfig, *, client=None):
        if not isinstance(config, ProviderConfig) or config.service != "dashvector" or config.collection_name != TARGET_COLLECTION or config.dimension != 1024 or config.dtype != "FLOAT" or config.metric != "dotproduct":
            raise ValueError("target_profile_invalid")
        self.config, self._http = config, client
        self._url = f"{config.endpoint}/v1/collections/{config.collection_name}"

    async def _request(self, method, suffix, **kwargs):
        try:
            async with _client(self._http) as client:
                response = await getattr(client, method)(self._url + suffix, headers={
                    "Content-Type": "application/json", "dashvector-auth-token": self.config.credential.get_secret_value(),
                }, follow_redirects=False, **kwargs)
                if response.status_code != 200:
                    return None
                data = response.json()
                return data if _success(data) else None
        except Exception:
            # No response text, request repr or credential-bearing exception.
            return None

    async def full_upsert(self, partition, document):
        try:
            _name(partition)
            prepared = _prepared_document(document)
        except (ValueError, TypeError, OverflowError):
            return WriteResult("rejected", "invalid_write_input")
        data = await self._request("post", "/docs/upsert", json={"partition": partition, "docs": [prepared]})
        if data is None:
            return WriteResult("unknown", "write_outcome_unknown")
        output = data.get("output")
        if isinstance(output, list) and len(output) == 1:
            item = output[0]
            if (isinstance(item, dict) and item.get("id") == prepared["id"]
                    and type(item.get("code")) is int and item["code"] == 0
                    and isinstance(item.get("doc_op"), str)
                    and item["doc_op"] in {"insert", "update", "upsert"}):
                return WriteResult("confirmed")
        # Some successful envelopes have no per-document acknowledgement. Read
        # exactly once; old/missing data never releases an unresolved fence.
        fetched = await self.fetch(partition, prepared["id"])
        if fetched.status == "found" and _matches_prepared(prepared, fetched.document):
            return WriteResult("confirmed", "prepared_write_verified")
        return WriteResult("unknown", "write_outcome_unknown")

    async def fetch(self, partition, doc_id):
        try:
            _name(partition)
            _name(doc_id)
        except ValueError:
            return FetchResult("unknown", reason="invalid_read_input")
        data = await self._request("get", "/docs", params={"partition": partition, "ids": doc_id})
        if data is not None and "output" not in data:
            # Still unknown for every general read/write reconciliation caller.
            return FetchResult("unknown", reason="read_output_missing")
        if data is None or not isinstance(data.get("output"), dict):
            return FetchResult("unknown", reason="read_outcome_unknown")
        output = data["output"]
        if not output:
            return FetchResult("not_found")
        if set(output) != {doc_id} or not isinstance(output[doc_id], dict):
            return FetchResult("unknown", reason="read_response_invalid")
        document = output[doc_id]
        if document.get("id") != doc_id or not isinstance(document.get("fields"), dict):
            return FetchResult("unknown", reason="read_response_invalid")
        return FetchResult("found", deepcopy(document))

    async def query_dense(self, partition, vector, *, top_k, filter=None):
        try:
            dense = normalize_dense(vector)
        except ValueError:
            return QueryResult("rejected", reason="dense_vector_invalid")
        return await self._query(partition, {"vector": dense}, top_k, filter, lexical=False)

    async def query_sparse(self, partition, sparse_vector, *, top_k, filter=None):
        try:
            sparse = validate_sparse(sparse_vector)
        except ValueError:
            return QueryResult("rejected", reason="sparse_vector_invalid")
        if not sparse:
            return QueryResult("confirmed")
        # Protocol-only alpha=0 placeholder: never accepted by write/dense paths.
        return await self._query(partition, {"vector": [0.0] * 1024, "sparse_vector": sparse}, top_k, filter, lexical=True)

    async def _query(self, partition, vectors, top_k, filter, *, lexical):
        try:
            _name(partition)
            if type(top_k) is not int or not 1 <= top_k <= 1024 or (filter is not None and not isinstance(filter, str)):
                raise ValueError("query_input_invalid")
        except ValueError:
            return QueryResult("rejected", reason="query_input_invalid")
        request = dict(vectors, partition=partition, topk=top_k, include_fields=True)
        if filter is not None:
            request["filter"] = filter
        try:
            async with _client(self._http) as client:
                data = await provider_request(client, 'post', self._url + '/query',
                    headers={'Content-Type': 'application/json',
                             'dashvector-auth-token': self.config.credential.reveal()},
                    json=request, follow_redirects=False)
        except ProviderError as exc:
            return QueryResult('unknown', reason=exc.reason, retryable=exc.retryable)
        if not _success(data) or "output" not in data:
            return QueryResult("unknown", reason="query_outcome_unknown")
        # Successful no-match queries can explicitly return null in place of [].
        output = [] if data["output"] is None else data["output"]
        if not isinstance(output, list):
            return QueryResult("unknown", reason="query_outcome_unknown")
        rows, seen, ignored = [], set(), 0
        for row in output:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in seen or not isinstance(row.get("fields"), dict) or type(row.get("score")) not in (int, float) or not math.isfinite(row["score"]):
                return QueryResult("unknown", reason="query_response_invalid")
            seen.add(row["id"])
            if lexical and row["score"] == 0:
                ignored += 1
                continue
            if lexical and row["score"] < 0:
                return QueryResult("unknown", reason="query_response_invalid")
            rows.append(deepcopy(row))
        return QueryResult("confirmed", tuple(sorted(rows, key=lambda row: -row["score"])), no_lexical_match=ignored)

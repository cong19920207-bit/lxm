"""Immutable memory configuration resolved from authoritative publication rows.

No Redis/default fallback on database failures. This resolver does not activate a
target, create an index, or change the environment; those remain explicit steps.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

TARGET_COLLECTION = "new_lxm_memory_long_collection"
PROVIDER_KEYS = {"dashvector": "vector_db_config", "embedding": "third_party:embedding", "rerank": "third_party:rerank"}
CONFIG_KEYS = ("vector_retrieval_config", "prompt_token_config", *PROVIDER_KEYS.values())
_FIELDS = {
    "dashvector": {"endpoint", "collection_name", "api_key", "dimension", "dtype", "metric"},
    "embedding": {"endpoint", "model", "api_key", "dimension"},
    "rerank": {"endpoint", "model", "api_key"},
}
_FIXED = {
    "dashvector": {"dimension": 1024, "dtype": "FLOAT", "metric": "dotproduct"},
    "embedding": {"dimension": 1024},
    "rerank": {},
}


class EffectiveConfigError(ValueError):
    def __init__(self, reason: str, code: int = 20120):
        self.reason, self.code = reason, code
        super().__init__(reason)


def server_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class Secret:
    _value: str = field(repr=False)

    def reveal(self) -> str:
        return self._value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret([REDACTED])"


@dataclass(frozen=True)
class ProviderConfig:
    service: str
    endpoint: str
    credential: Secret = field(repr=False)
    source: str
    version: int
    revision: int
    model: str = ""
    collection_name: str = ""
    dimension: int = 1024
    dtype: str = "FLOAT"
    metric: str = "dotproduct"
    field_sources: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def public(self) -> dict:
        result = {"service_key": self.service, "provider": "dashvector" if self.service == "dashvector" else "dashscope",
                  "endpoint": self.endpoint, "version": self.version, "source": self.source,
                  "revision": self.revision, "credential_configured": bool(self.credential.reveal()),
                  "field_sources": dict(self.field_sources), "runtime_ready": True, "configuration_error": None}
        if self.service == "dashvector":
            result.update(collection_name=self.collection_name, dimension=self.dimension, dtype=self.dtype, metric=self.metric)
        else:
            result["model"] = self.model
            if self.service == "embedding":
                result.update(dimension=self.dimension, normalization="l2-v1")
        semantic = {key: result[key] for key in ("provider", "endpoint", "model", "collection_name", "dimension", "dtype", "metric", "normalization") if key in result}
        fingerprint = hashlib.sha256(json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        result["profile_fingerprint"] = fingerprint
        result["env_fingerprint"] = fingerprint if "env" in self.field_sources.values() else None
        return result


@dataclass(frozen=True)
class EffectiveMemoryConfig:
    config_snapshot_id: str
    retrieval: Mapping[str, Any]
    prompt: Mapping[str, Any]
    providers: Mapping[str, ProviderConfig]
    versions: Mapping[str, Any]
    reply_model: str
    target_fingerprint: str
    # A configuration preview has no active epoch. Consumers require the active resolver.
    target_epoch: int | None = None
    encoder_version: str | None = None
    profiles: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def public(self) -> dict:
        return {"config_snapshot_id": self.config_snapshot_id, "retrieval": _plain(self.retrieval),
                "prompt": _plain(self.prompt), "providers": {key: cfg.public() for key, cfg in self.providers.items()},
                "versions": _plain(self.versions), "reply_model": self.reply_model,
                "target_fingerprint": self.target_fingerprint, "target_epoch": self.target_epoch,
                "encoder_version": self.encoder_version, "profiles": _plain(self.profiles)}


def _request_profiles(reply_model, encoder, rerank_model):
    if reply_model != 'doubao-seed-2-0-lite-260428':
        raise EffectiveConfigError('counter_profile_unverified')
    return _freeze({
        'counter': {'id': f'ark-tokenization:{reply_model}:render-v1', 'model': reply_model,
                    'endpoint': 'https://ark.cn-beijing.volces.com/api/v3/tokenization',
                    'envelope_reserve': 64, 'output_context_reserve': 4096,
                    'input_limit': 224000, 'context_window': 256000, 'timeout_ms': 5000, 'max_retry': 1},
        'bm25': {'encoder_version': encoder.encoder_version,
                 'statistics_sha256': encoder.profile['statistics_sha256'],
                 'corpus_sha256': encoder.profile.get('corpus_sha256')},
        'embedding': {'model': 'text-embedding-v4', 'dimension': 1024, 'normalization': 'l2-v1', 'batch_limit': 10},
        'rerank': {'model': rerank_model, 'document_limit': 500, 'individual_limit': 4000,
                   'aggregate_limit': 30000, 'local_guard': 'utf8_bytes+32', 'rrf_k': 60,
                   'rrf_dense_weight': 1, 'rrf_bm25_weight': 1},
        'timeouts_ms': {'text_total': 180000, 'rewrite_stage': 45000, 'retrieval_stage': 45000,
                        'rewrite_call': 20000, 'embedding_call': 8000, 'vector_query': 4000,
                        'rerank_call': 8000, 'retry_backoff': 250, 'validation_reserve': 4250,
                        'use_lock': 2000, 'handoff': 5000, 'reply_call': 60000,
                        'commit_prepare_reserve': 5000, 'voice_writer': 20000},
        'failed_call_max_retry': 1, 'route_concurrency': 4,
    })


def canonical_provider_key(service: str) -> str:
    if service in ("third_party:dashvector", "vector_db_config"):
        return "vector_db_config"
    for name, key in PROVIDER_KEYS.items():
        if service in (name, key):
            return key
    raise EffectiveConfigError("unsupported_provider")


def load_environment() -> dict:
    # Lazy import keeps pure validation independent of dotenv/network/application.
    from backend import config
    return {
        "dashvector": {"endpoint": config.get_dashvector_endpoint(), "collection_name": config.get_dashvector_collection(), "api_key": config.get_dashvector_api_key()},
        "embedding": {"endpoint": config.get_embedding_endpoint(), "model": config.get_embedding_model(), "dimension": config.get_embedding_dimension(), "api_key": config.get_aliyun_api_key()},
        "rerank": {"endpoint": config.get_rerank_endpoint(), "model": config.get_rerank_model(), "api_key": config.get_rerank_api_key()},
        "reply": {"model": config.get_volc_model()},
    }


def _normalize_alias(service: str, raw: dict) -> dict:
    value = dict(raw)
    if service == "dashvector" and "collection" in value:
        if "collection_name" in value and value["collection_name"] != value["collection"]:
            raise EffectiveConfigError("collection_alias_conflict")
        value["collection_name"] = value.pop("collection")
    return value


def _validate_endpoint(endpoint):
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise EffectiveConfigError("endpoint_missing")
    try:
        url = urlsplit(endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError
        _ = url.port
    except ValueError:
        raise EffectiveConfigError("endpoint_invalid") from None


def _validate_provider(service, value):
    _validate_endpoint(value.get("endpoint"))
    secret = value.get("api_key")
    if not isinstance(secret, str) or not secret.strip():
        raise EffectiveConfigError("credential_missing")
    if "*" in secret or "REDACTED" in secret.upper():
        raise EffectiveConfigError("masked_credential_rejected")
    if service == "dashvector":
        if value.get("collection_name") != TARGET_COLLECTION:
            raise EffectiveConfigError("target_mismatch")
        if value.get("dtype") != "FLOAT" or value.get("metric") != "dotproduct":
            raise EffectiveConfigError("collection_profile_mismatch")
    elif service == "embedding" and value.get("model") != "text-embedding-v4":
        raise EffectiveConfigError("model_profile_mismatch")
    elif service == "rerank" and (not isinstance(value.get("model"), str) or not value["model"].strip()):
        raise EffectiveConfigError("model_missing")
    if service in ("embedding", "dashvector") and (type(value.get("dimension")) is not int or value["dimension"] != 1024):
        raise EffectiveConfigError("dimension_mismatch")


def _effective_values(service: str, raw, env: dict) -> tuple[dict, dict]:
    canonical_provider_key(service)
    if raw is not None and not isinstance(raw, dict):
        raise EffectiveConfigError("published_config_invalid")
    never_published = raw is None
    raw = _normalize_alias(service, raw or {})
    values = {**_FIXED[service], **(env.get(service, {}) if never_published else {})}
    sources = {key: "profile" if key in _FIXED[service] else "env" for key in values}
    for key in _FIELDS[service]:
        if key in raw:
            if raw[key] is None:
                raise EffectiveConfigError("published_config_invalid")
            values[key] = raw[key]
            sources[key] = "database"
    return values, sources


def provider_from_record(service: str, record: dict, env: dict) -> ProviderConfig:
    if not isinstance(record, dict) or record.get("source") not in ("database", "never_published"):
        raise EffectiveConfigError("configuration_read_unavailable", 20129)
    if record["source"] == "database" and not isinstance(record.get("raw"), dict):
        raise EffectiveConfigError("published_config_invalid")
    if record["source"] == "database" and not _FIELDS[service].issubset(_normalize_alias(service, record["raw"])):
        raise EffectiveConfigError("published_config_incomplete")
    values, sources = _effective_values(service, record.get("raw"), env)
    _validate_provider(service, values)
    _validate_deployment_target(service, values, env)
    source = "database" if record["source"] == "database" else "env"
    return ProviderConfig(service=service, endpoint=values["endpoint"].strip().rstrip("/"), credential=Secret(values["api_key"]),
                          source=source, version=record["version"], revision=record["revision"],
                          model=values.get("model", ""), collection_name=values.get("collection_name", ""),
                          dimension=values.get("dimension", 1024), dtype=values.get("dtype", "FLOAT"),
                          metric=values.get("metric", "dotproduct"), field_sources=_freeze(sources))


def _validate_deployment_target(service, values, env):
    if service == "dashvector":
        approved = env.get(service, {}).get("endpoint")
        _validate_endpoint(approved)
        if values["endpoint"].strip().rstrip("/") != approved.strip().rstrip("/"):
            raise EffectiveConfigError("cluster_mismatch")


def merge_provider_config(service: str, current: dict | None, patch: dict, env: dict) -> dict:
    if not isinstance(patch, dict):
        raise EffectiveConfigError("provider_patch_invalid")
    patch = _normalize_alias(service, patch)
    if set(patch) - _FIELDS[service]:
        raise EffectiveConfigError("provider_field_invalid")
    values, _ = _effective_values(service, current, env)
    for key, value in patch.items():
        if key == "api_key" and value in (None, ""):
            continue
        if value is None:
            raise EffectiveConfigError("provider_patch_invalid")
        values[key] = value
    _validate_provider(service, values)
    _validate_deployment_target(service, values, env)
    values["endpoint"] = values["endpoint"].strip().rstrip("/")
    return {key: values[key] for key in _FIELDS[service] if key in values}


async def provider_record(db, service: str, *, reader=None) -> dict:
    if reader is None:
        from backend.services.memory_config_publication import read
        reader = read
    # A failure is intentionally propagated, never mapped to a default record.
    try:
        return await reader(db, canonical_provider_key(service))
    except Exception:
        raise EffectiveConfigError("configuration_read_unavailable", 20129) from None


async def resolve_provider(db, service: str, patch=None, *, env=None, reader=None) -> ProviderConfig:
    env = load_environment() if env is None else env
    record = await provider_record(db, service, reader=reader)
    if patch is not None:
        candidate = merge_provider_config(service, record["raw"], patch, env)
        record = {**record, "raw": candidate}
    return provider_from_record(service, record, env)


def provider_public_state(service: str, record: dict, env: dict) -> dict:
    try:
        return provider_from_record(service, record, env).public()
    except EffectiveConfigError as exc:
        # Editing/status may show a real but not yet usable legacy target.
        values, sources = _effective_values(service, record.get("raw"), env)
        result = {"service_key": service, "provider": "dashvector" if service == "dashvector" else "dashscope",
                  "version": record["version"], "revision": record["revision"], "source": "database" if record["source"] == "database" else "env",
                  "runtime_ready": False, "configuration_error": exc.reason,
                  "credential_configured": bool(values.get("api_key")), "field_sources": sources}
        for key in ("endpoint", "model", "collection_name", "dimension", "dtype", "metric"):
            if key in values:
                if key == "endpoint":
                    try:
                        _validate_endpoint(values[key])
                    except EffectiveConfigError:
                        continue
                result[key] = values[key]
        return result


def bm25_capability() -> dict:
    from backend.services.memory_bm25 import get_encoder, BM25Error, PACKAGE_VERSION
    result = {"provider": "local", "package": "dashtext", "version": PACKAGE_VERSION,
              "encoder_version": None, "encoder_ready": False, "ready": False,
              "reason": "index_not_initialized"}
    try:
        encoder = get_encoder()
        result.update(encoder_version=encoder.encoder_version, encoder_ready=True,
                      statistics_sha256=encoder.profile["statistics_sha256"])
    except BM25Error as exc:
        result["reason"] = str(exc)
    return result


async def publish_provider(db, service, patch, admin_id, publish_id, source_entry):
    from backend.services.memory_config_publication import publish
    from backend.services.memory_provider_service import probe_provider, ProviderError

    env = load_environment()

    def merge_validate(current, submitted):
        return merge_provider_config(service, current, submitted, env)

    async def verify(candidate):
        config = provider_from_record(service, {"raw": candidate, "version": 0, "revision": 0, "source": "database"}, env)
        result = await probe_provider(config)
        if not result["connected"]:
            if result["reason"] == "provider_response_unavailable":
                raise TimeoutError("provider_outcome_unknown")
            raise ProviderError("provider_test_failed")

    return await publish(db, canonical_provider_key(service), patch, admin_id, publish_id,
                         merge_validate, source_entry=source_entry, verify=verify)


async def resolve_effective_memory_config(db, *, env=None, reader=None) -> EffectiveMemoryConfig:
    from backend.services.memory_config_schema import vector_effective, prompt_effective
    if reader is None:
        from backend.services.memory_config_publication import read_many
        reader = read_many
    env = load_environment() if env is None else env
    try:
        records = await reader(db, CONFIG_KEYS)
    except Exception:
        raise EffectiveConfigError("configuration_read_unavailable", 20129) from None
    if set(records) != set(CONFIG_KEYS):
        raise EffectiveConfigError("configuration_read_unavailable", 20129)
    providers = {name: provider_from_record(name, records[key], env) for name, key in PROVIDER_KEYS.items()}
    try:
        retrieval = vector_effective(records["vector_retrieval_config"]["raw"])
        prompt = prompt_effective(records["prompt_token_config"]["raw"])
    except (ValueError, TypeError):
        raise EffectiveConfigError("published_config_invalid") from None
    versions = {key: {"version": row["version"], "revision": row["revision"], "source": "default" if row["source"] == "never_published" else row["source"]} for key, row in records.items()}
    for name, cfg in providers.items():
        versions[PROVIDER_KEYS[name]].update(source=cfg.source, env_fingerprint=cfg.public()["env_fingerprint"])
    versions["reply_model"] = {"source": "env", "version": 0, "env_fingerprint": hashlib.sha256(env["reply"]["model"].encode()).hexdigest()}
    vector = providers["dashvector"]
    fingerprint = hashlib.sha256(f"{vector.endpoint}/v1/collections/{vector.collection_name}".encode()).hexdigest()
    from backend.services.memory_bm25 import get_encoder, BM25Error
    try:
        encoder = get_encoder()
    except BM25Error:
        raise EffectiveConfigError("bm25_profile_unavailable", 20129) from None
    versions["bm25"] = {"source": "local_profile", "encoder_version": encoder.encoder_version,
                         "statistics_sha256": encoder.profile["statistics_sha256"]}
    return EffectiveMemoryConfig(str(uuid4()), _freeze(retrieval), _freeze(prompt), _freeze(providers), _freeze(versions),
                                 env["reply"]["model"], fingerprint, encoder_version=encoder.encoder_version,
                                 profiles=_request_profiles(env['reply']['model'], encoder, providers['rerank'].model))


async def resolve_active_memory_config(db, environment_id, *, env=None, reader=None, allow_isolated=False):
    """Freeze only an already activated target; this never creates or changes its fence."""
    from backend.models.memory_control import MemoryRuntimeFence
    from backend.services.memory_runtime_service import require_active_fence, MemoryControlError
    snapshot = await resolve_effective_memory_config(db, env=env, reader=reader)
    fence = await db.get(MemoryRuntimeFence, environment_id)
    if fence is None:
        raise MemoryControlError(20126, "runtime_not_active")
    verified = await require_active_fence(db, environment_id, fence.target_epoch,
        bytes.fromhex(snapshot.target_fingerprint), allow_isolated=allow_isolated, lock=False)
    return replace(snapshot, target_epoch=verified.target_epoch)

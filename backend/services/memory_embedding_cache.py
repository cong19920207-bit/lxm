"""Opt-in frozen-profile embedding cache. Legacy emb:MD5 is never consumed."""
import hashlib
import json

from backend.services.memory_effective_config import ProviderConfig
from backend.services.memory_provider_service import embedding
from backend.utils.memory_vector import normalize_dense

CACHE_TTL = 7 * 86400


class MemoryEmbeddingCache:
    def __init__(self, config: ProviderConfig, *, cache=None, embed=None):
        if config.service != "embedding" or config.model != "text-embedding-v4" or config.dimension != 1024:
            raise ValueError("embedding_profile_invalid")
        self.config, self.cache, self._embed = config, cache, embed or embedding
        # Endpoint/model/dimension/normalization are semantic; credentials aren't.
        self._profile = {
            "provider": "dashscope", "endpoint": config.endpoint, "model": config.model,
            "dimension": config.dimension, "normalization": "l2-v1",
        }

    def cache_key(self, text, text_type):
        # Document and query embeddings can differ even for the same text.
        profile_hash = hashlib.sha256(json.dumps(dict(self._profile, text_type=text_type), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        body_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"emb:v2:{profile_hash}:{self.config.model}:1024:l2-v1:{body_hash}"

    async def get_embedding(self, text, *, text_type="document"):
        if not isinstance(text, str) or not text.strip() or text_type not in ("query", "document"):
            raise ValueError("embedding_input_invalid")
        key = self.cache_key(text, text_type)
        if self.cache is not None:
            try:
                value = await self.cache.get(key)
                if value:
                    return normalize_dense(json.loads(value))
            except Exception:
                # A corrupt/missing cache is a miss, never evidence of a vector.
                pass
        result = await self._embed(self.config, [text], text_type)
        if not isinstance(result, (list, tuple)) or len(result) != 1:
            raise ValueError("embedding_response_invalid")
        vector = normalize_dense(result[0])
        if self.cache is not None:
            try:
                await self.cache.set(key, json.dumps(vector, allow_nan=False), ex=CACHE_TTL)
            except Exception:
                pass
        return vector

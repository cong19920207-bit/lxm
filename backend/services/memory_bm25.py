"""Versioned local BM25 bootstrap profile; no fit or downloads at request time."""
from functools import lru_cache
import hashlib
import importlib.metadata
import json
from pathlib import Path

from backend.utils.memory_vector import validate_sparse

PACKAGE_VERSION = "0.0.7"
PROFILE_SHA256 = "17dbc3fe3a4d2ed8dd70a72bef5bf8812abea09585a137e07cbd2fd76b4db194"
STATISTICS_SHA256 = "62d586126746a5c8df9a218187b5200ee306055daa5af47d90b3a1b1bcce51de"
ENCODER_VERSION = "memory-bm25-zh-v1:" + PROFILE_SHA256
ASSETS = Path(__file__).resolve().parents[1] / "config" / "assets"


class BM25Error(ValueError):
    pass


class MemoryBM25:
    encoder_version = ENCODER_VERSION

    def __init__(self):
        try:
            profile_bytes = (ASSETS / "memory_bm25_zh_v1.profile.json").read_bytes()
            if hashlib.sha256(profile_bytes).hexdigest() != PROFILE_SHA256:
                raise BM25Error("bm25_profile_mismatch")
            self._profile = json.loads(profile_bytes)
            stats = ASSETS / self._profile["statistics_file"]
            if hashlib.sha256(stats.read_bytes()).hexdigest() != STATISTICS_SHA256 or self._profile["statistics_sha256"] != STATISTICS_SHA256:
                raise BM25Error("bm25_statistics_mismatch")
            if importlib.metadata.version("dashtext") != PACKAGE_VERSION:
                raise BM25Error("bm25_package_mismatch")
            import dashtext
            package = Path(dashtext.__file__).parent
            for relative, expected in self._profile["tokenizer_files"].items():
                if hashlib.sha256((package / relative).read_bytes()).hexdigest() != expected:
                    raise BM25Error("bm25_analyzer_mismatch")
            from dashtext import SparseVectorEncoder
            from dashtext.tokenizer.auto import TextTokenizer
            tokenizer = TextTokenizer.from_pretrained(
                "Jieba", stop_words=True,
                dict=str(package / "tokenizer/data/jieba/dict.txt.big"),
                user_dict=str(package / "tokenizer/data/jieba/user_dict.txt"),
            )
            self._encoder = SparseVectorEncoder(b=.75, k1=1.2, tokenize_function=tokenizer.tokenize)
            self._encoder.load(str(stats))  # Always this verified local file.
        except BM25Error:
            raise
        except Exception:
            raise BM25Error("bm25_profile_unavailable") from None

    @property
    def profile(self):
        return json.loads(json.dumps(self._profile))

    def _encode(self, text, *, query):
        if not isinstance(text, str):
            raise BM25Error("bm25_input_invalid")
        if not text.strip():
            return {}
        try:
            result = self._encoder.encode_queries(text) if query else self._encoder.encode_documents(text)
            return validate_sparse(result)
        except Exception:
            raise BM25Error("bm25_encoding_failed") from None

    def encode_document(self, text):
        return self._encode(text, query=False)

    def encode_query(self, text):
        return self._encode(text, query=True)


@lru_cache(maxsize=1)
def get_encoder():
    """One immutable statistics profile per process; upgrade means new version."""
    return MemoryBM25()

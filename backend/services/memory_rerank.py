"""Complete per-route rerank; no cross-route scores or candidate truncation."""
from dataclasses import replace
import math

from backend.services.memory_hybrid_retrieval import Removal


def fuse_route(result, reason='rerank_unavailable'):
    items = result.candidates
    has_dense = any(c.dense_rank is not None for c in items)
    has_sparse = any(c.bm25_rank is not None for c in items)
    method = 'rrf' if has_dense and has_sparse else ('dense_order' if has_dense else 'bm25_order')
    def key(pair):
        index, item = pair
        score = sum(1 / (60 + rank) for rank in (item.dense_rank, item.bm25_rank) if rank is not None)
        return -score, index, item.doc_id
    ordered = sorted(enumerate(items), key=key)
    snapshots=tuple(replace(c, rerank_score=None, route_rank=i,
        order_method=method, admission_reason='rerank_fallback') for i, (_, c) in enumerate(ordered, 1))
    return replace(result,candidates=snapshots,candidate_snapshots=snapshots,rerank_status='fallback',reason=reason)


async def rerank_route(result, *, threshold, rank):
    if not result.candidates:
        return replace(result, rerank_status='empty')
    try:
        pairs = await rank(result.question, [c.value for c in result.candidates])
        count = len(result.candidates)
        if not isinstance(pairs, (tuple, list)) or len(pairs) != count:
            raise ValueError()
        scores = {}
        for pair in pairs:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError()
            index, score = pair
            if (type(index) is not int or not 0 <= index < count or index in scores
                    or type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError()
            scores[index] = float(score)
        ordered = sorted(enumerate(result.candidates), key=lambda pair: (-scores[pair[0]], pair[0], pair[1].doc_id))
        selected, removed, snapshots = [], list(result.removed), []
        for rank_number,(index, item) in enumerate(ordered,1):
            snapshots.append(replace(item,rerank_score=scores[index],route_rank=rank_number,
                order_method='rerank',admission_reason='threshold_rejected' if scores[index]<threshold else 'threshold_passed'))
            if scores[index] < threshold:
                removed.append(Removal(item.doc_id, item.route, 'threshold', 'rerank', item.identity_id))
            else:
                selected.append(replace(item, rerank_score=scores[index], route_rank=len(selected)+1,
                                        order_method='rerank', admission_reason='threshold_passed'))
        return replace(result, candidates=tuple(selected), removed=tuple(removed), candidate_snapshots=tuple(snapshots), rerank_status='ok')
    except Exception as exc:
        # Only known, locally generated reason codes may escape the adapter.
        reason = 'local_size_guard' if getattr(exc, 'reason', None) == 'local_size_guard' else 'rerank_unavailable'
        return fuse_route(result, reason)

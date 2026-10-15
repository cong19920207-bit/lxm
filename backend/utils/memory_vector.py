"""Strict dense/sparse values for the new memory profile only."""
import math


def normalize_dense(value, dimension=1024):
    """L2 normalize without overflow, rejecting zero/nonfinite/wrong dimensions."""
    if not isinstance(value, (list, tuple)) or len(value) != dimension:
        raise ValueError("dense_vector_invalid")
    try:
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
            raise ValueError("dense_vector_invalid")
        scale = max(abs(x) for x in value)
        if not scale:
            raise ValueError("dense_vector_invalid")
        scaled = [x / scale for x in value]
        norm = math.hypot(*scaled)
        return [x / norm for x in scaled]
    except (OverflowError, TypeError):
        raise ValueError("dense_vector_invalid") from None


def validate_sparse(value):
    """Keep original BM25 weights; never apply dense normalization to them."""
    if not isinstance(value, dict):
        raise ValueError("sparse_vector_invalid")
    result = {}
    for key, weight in value.items():
        if type(key) not in (str, int) or not str(key).isascii() or not str(key).isdigit():
            raise ValueError("sparse_vector_invalid")
        index = int(key)
        if not 0 <= index <= 0xFFFFFFFF or str(index) in result or type(weight) not in (int, float):
            raise ValueError("sparse_vector_invalid")
        try:
            if not math.isfinite(weight) or weight < 0:
                raise ValueError("sparse_vector_invalid")
            result[str(index)] = float(weight)
        except OverflowError:
            raise ValueError("sparse_vector_invalid") from None
    return result


def bounded_dotproduct_score(value):
    """Normalized FLOAT dotproducts may overshoot [-1,1] by transport rounding.

    Keep the existing consumer range, allowing only the existing vector protocol's
    1e-6 absolute comparison tolerance; threshold comparisons remain exact.
    """
    if type(value) not in (int, float) or not math.isfinite(value) or not -1.000001 <= value <= 1.000001:
        raise ValueError('dense_score_invalid')
    return min(1.0, max(-1.0, value))

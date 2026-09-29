"""Read-only validated projection of existing UTC voice observation counters.

This is neither a business ledger nor a completeness claim. Missing/expired keys
are unknown, not zero. Capability-dependent public projection belongs to the
consumer; this internal reader does not declare provider capabilities verified.
"""
import asyncio
import json
import math
from datetime import date
from backend.services.realtime_voice_metric_service import EVENT_DIMENSIONS, TTL_SECONDS, DURATION_METRICS


def metric_dictionary():
    return [{'name': name, 'dimensions': {key: sorted(values) for key, values in sorted(schema.items())},
             'max_dimension_combinations': math.prod(len(values) for values in schema.values()),
             'storage': 'redis_hash', 'ttl_seconds': TTL_SECONDS,
             'bucket_basis': 'observation_sent_utc', 'aggregation': 'sum_of_amounts',
             'distribution': 'exact_millisecond_frequency' if name in DURATION_METRICS else None}
            for name, schema in sorted(EVENT_DIMENSIONS.items())]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_dimension')
        result[key] = value
    return result


def parse_counter(name, raw):
    invalid = {'status': 'invalid', 'samples': None}
    schema = EVENT_DIMENSIONS.get(name)
    if schema is None or not isinstance(raw, dict):
        return invalid
    if not raw:
        return {'status': 'missing', 'samples': None}
    if len(raw) > math.prod(len(values) for values in schema.values()):
        return invalid
    samples, seen = [], set()
    try:
        for key, value in raw.items():
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            if isinstance(value, bytes):
                value = value.decode('ascii')
            if not isinstance(key, str) or len(key) > 2048:
                return invalid
            dimensions = json.loads(key, object_pairs_hook=_unique_object)
            if not isinstance(dimensions, dict) or set(dimensions) != set(schema):
                return invalid
            if any(type(v) is not str or v not in schema[k] for k, v in dimensions.items()):
                return invalid
            canonical = json.dumps(dimensions, sort_keys=True, separators=(',', ':'))
            if canonical in seen:
                return invalid
            seen.add(canonical)
            if (not isinstance(value, str) or not value.isascii() or not value.isdigit() or
                    len(value) > 16 or int(value) > 10**12 + 10**9):
                return invalid
            samples.append({'dimensions': dimensions, 'value': int(value)})
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return invalid
    samples.sort(key=lambda item: json.dumps(item['dimensions'], sort_keys=True))
    return {'status': 'available', 'samples': samples}


async def read_counter_day(cache, day, *, timeout_seconds=1):
    if type(day) is not date:
        raise ValueError('invalid_voice_metric_day')
    names = sorted(EVENT_DIMENSIONS)
    result = {'date': day.isoformat(), 'bucket_basis': 'observation_sent_utc',
              'completeness': 'not_guaranteed', 'events': []}
    try:
        pipeline = cache.pipeline(transaction=False)
        for name in names:
            pipeline.hgetall(name + ':' + day.strftime('%Y%m%d'))
        rows = await asyncio.wait_for(pipeline.execute(), timeout_seconds)
        if not isinstance(rows, list) or len(rows) != len(names):
            raise ValueError('invalid_voice_counter_response')
    except Exception:
        result['events'] = [{'name': name, 'status': 'unavailable', 'samples': None} for name in names]
        return result
    result['events'] = [{'name': name, **parse_counter(name, raw)} for name, raw in zip(names, rows)]
    return result


def parse_duration_histogram(name, raw):
    """Exact nearest-rank quantiles of retained observations, not all business calls."""
    from backend.services.realtime_voice_metric_service import DURATION_METRICS
    invalid = {'status': 'invalid', 'groups': None}
    if name not in DURATION_METRICS or not isinstance(raw, dict):
        return invalid
    if not raw:
        return {'status': 'missing', 'groups': None}
    groups, seen = {}, set()
    try:
        for field, count in raw.items():
            if isinstance(field, bytes):
                field = field.decode('utf-8')
            if isinstance(count, bytes):
                count = count.decode('ascii')
            if not isinstance(field, str) or len(field) > 2048:
                return invalid
            item = json.loads(field, object_pairs_hook=_unique_object)
            if not isinstance(item, dict) or set(item) != {'dimensions', 'milliseconds'}:
                return invalid
            ms, dimensions = item['milliseconds'], item['dimensions']
            if type(ms) is not int or not 0 <= ms <= 10**9:
                return invalid
            canonical = json.dumps(dimensions, sort_keys=True, separators=(',', ':'))
            parsed = parse_counter(name, {canonical: count})
            if parsed['status'] != 'available' or parsed['samples'][0]['value'] < 1:
                return invalid
            identity = (canonical, ms)
            if identity in seen:
                return invalid
            seen.add(identity)
            groups.setdefault(canonical, {})[ms] = parsed['samples'][0]['value']
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return invalid
    result = []
    for canonical, frequencies in sorted(groups.items()):
        dimensions = json.loads(canonical)
        total = sum(frequencies.values())
        row = {'dimensions': dimensions, 'sample_count': total,
               'method': 'nearest_rank', 'status': 'available'}
        for percentile in (50, 90, 95):
            target = (percentile * total + 99) // 100
            cumulative = 0
            for ms, count in sorted(frequencies.items()):
                cumulative += count
                if cumulative >= target:
                    row[f'p{percentile}_ms'] = ms
                    break
        # Queue producer explicitly caps very old ages; do not call the cap exact.
        if dimensions.get('capped') == 'true':
            row.update(status='not_measurable', p50_ms=None, p90_ms=None, p95_ms=None)
        result.append(row)
    return {'status': 'available', 'groups': result}


async def read_duration_day(cache, day, *, timeout_seconds=1):
    from backend.services.realtime_voice_metric_service import DURATION_METRICS, DURATION_PREFIX
    if type(day) is not date:
        raise ValueError('invalid_voice_metric_day')
    names = sorted(DURATION_METRICS)
    result = {'date': day.isoformat(), 'bucket_basis': 'observation_sent_utc',
              'completeness': 'not_guaranteed', 'events': []}
    try:
        pipeline = cache.pipeline(transaction=False)
        for name in names:
            pipeline.hgetall(DURATION_PREFIX + name + ':' + day.strftime('%Y%m%d'))
        rows = await asyncio.wait_for(pipeline.execute(), timeout_seconds)
        if not isinstance(rows, list) or len(rows) != len(names):
            raise ValueError('invalid_voice_histogram_response')
    except Exception:
        result['events'] = [{'name': name, 'status': 'unavailable', 'groups': None} for name in names]
        return result
    result['events'] = [{'name': name, **parse_duration_histogram(name, raw)} for name, raw in zip(names, rows)]
    return result

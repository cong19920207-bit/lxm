"""STEP-026 budgeted, immutable pre-call context compiler.

Source ports return compressed facts, never raw memory documents. This module
does not invoke the text conversation pipeline or persist a second persona.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Mapping, Protocol


class ContextPackError(ValueError):
    pass


class VoiceContextSource(Protocol):
    async def load(self, section: str, user_id: int, now: datetime) -> Any: ...


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class ContextPack:
    persona: str = field(repr=False)
    dynamic: str = field(repr=False)
    metadata: Mapping[str, Any]
    degraded: bool


def select_memories(rows, *, limit: int, now: datetime, lookback_days: int, deadline=None, crop_stats=None):
    """Rank relevance/quality/time; channel is provenance, never a score term."""
    result = []
    seen = set()
    if not isinstance(rows, list) or len(rows) > 200:
        raise ContextPackError('source_candidate_limit')
    for item in rows:
        if deadline is not None and time.monotonic() >= deadline:
            raise ContextPackError('compile_timeout')
        if not isinstance(item, dict):
            continue
        try:
            identity = str(item['id'])
            content = item['content']
            if not isinstance(item['updated_at'], str) or len(item['updated_at']) > 64:
                continue
            updated = datetime.fromisoformat(item['updated_at'].replace('Z', '+00:00'))
            relevance, quality = float(item['score']), float(item['quality'])
            if (not isinstance(content, str) or not content.strip() or identity in seen
                    or not 0 <= relevance <= 1 or not 0 <= quality <= 1
                    or not all(math.isfinite(v) for v in (relevance, quality))
                    or updated.tzinfo is None or updated > now
                    or updated < now - timedelta(days=lookback_days)
                    or item.get('is_deleted') is True):
                continue
            expiry = item.get('expires_at')
            if expiry is not None and (not isinstance(expiry, str) or len(expiry) > 64):
                continue
            if expiry and datetime.fromisoformat(expiry.replace('Z', '+00:00')) <= now:
                continue
            rank = (relevance, quality, updated.timestamp())
            seen.add(identity)
            if len(identity) > 128:
                continue
            if crop_stats is not None and len(content)>400:
                crop_stats['count'] += 1
            result.append({'id': identity, 'content': content[:400], 'rank_score': rank,
                           'source_channel': item.get('source_channel')})
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    result.sort(key=lambda r: (-r['rank_score'][0], -r['rank_score'][1], -r['rank_score'][2], str(r['id'])))
    if crop_stats is not None:
        crop_stats["count"] += max(0,len(result)-limit)
    return result[:limit]


def _consume_task(task):
    if not task.cancelled():
        task.exception()


async def build_context_pack(*, user_id: int, persona_raw: str, persona_ref: Mapping,
                             settings: Mapping, source: VoiceContextSource,
                             salutation: str, relationship: str, now: datetime,
                             ready_barrier: asyncio.Event) -> ContextPack:
    """Release the compiler barrier after valid full/minimal context is ready.

    The caller must still stage this result through adapter.inject_context before
    start_session. An invalid persona anchor is a hard preflight failure.
    """
    started = time.monotonic()
    ref, cfg = deepcopy(dict(persona_ref)), deepcopy(dict(settings))
    if (not isinstance(persona_raw, str) or len(persona_raw) > 100000
            or not isinstance(salutation, str) or not isinstance(relationship, str)
            or type(user_id) is not int or user_id <= 0 or now.tzinfo is None
            or ref.get('config_key') != 'persona' or type(ref.get('version')) is not int
            or ref['version'] <= 0
            or ref.get('content_sha256') != 'sha256:' + hashlib.sha256(persona_raw.encode()).hexdigest()):
        raise ContextPackError('persona_anchor_invalid')
    try:
        payload = json.loads(persona_raw)
        if not isinstance(payload, dict):
            raise ValueError
        limits = {'persona_max_chars': 5000, 'dynamic_max_chars': 2000,
                  'recent_dialog_max_chars': 800, 'memory_max_items': 5,
                  'build_budget_ms': 3000, 'memory_lookback_days': 3650}
        if any(type(cfg[k]) is not int or not 0 < cfg[k] <= cap for k, cap in limits.items()):
            raise ValueError
        instruction = cfg['voice_instruction_template']
        if not isinstance(instruction, str) or len(instruction) >= cfg['persona_max_chars']:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ContextPackError('context_config_invalid') from None
    # Keep the voice instruction intact; text-node JSON output constraints are not reused.
    identity = '\n'.join(f'{k}：{v}' for k, v in payload.items() if isinstance(v, (str, int, float)))
    persona_source = instruction + '\n' + identity
    crop_stats = {'count':int(len(persona_source)>cfg['persona_max_chars']) + int(len(salutation)>60) + int(len(relationship)>120)}
    persona = persona_source[:cfg['persona_max_chars']]
    if not persona.strip():
        raise ContextPackError('persona_empty')
    minimum = f'称呼：{salutation[:60]}\n关系：{relationship[:120]}\n当前时间：{now.astimezone(timezone(timedelta(hours=8))).isoformat()}'
    if len(minimum) > cfg['dynamic_max_chars']:
        raise ContextPackError('minimum_context_budget_invalid')
    sections = ('schedule', 'recent_dialog', 'voice_history', 'memories')
    tasks = {section: asyncio.create_task(source.load(section, user_id, now)) for section in sections}
    degraded = False
    reason = 'none'
    values = {}
    try:
        remaining = max(0, cfg['build_budget_ms']/1000 - (time.monotonic()-started))
        done, pending = await asyncio.wait(tasks.values(), timeout=remaining)
        if pending:
            degraded, reason = True, 'timeout'
        else:
            for section, task in tasks.items():
                try:
                    values[section] = task.result()
                except Exception:
                    degraded, reason = True, 'source_failed'
    except asyncio.CancelledError:
        raise
    finally:
        for task in tasks.values():
            if not task.done():
                task.cancel()
            task.add_done_callback(_consume_task)
    dynamic = minimum
    memory_ids = []
    recent_chars = 0
    if not degraded:
        if (any(not isinstance(values.get(k), str) for k in ('schedule', 'recent_dialog', 'voice_history'))
                or not isinstance(values.get('memories'), list) or len(values['memories']) > 200):
            degraded, reason = True, 'source_invalid'
        else:
            try:
                memories = select_memories(values['memories'], limit=cfg['memory_max_items'], now=now,
                                           lookback_days=cfg['memory_lookback_days'],
                                           deadline=started + cfg['build_budget_ms']/1000, crop_stats=crop_stats)
            except ContextPackError:
                memories = []
                degraded, reason = True, 'compile_timeout'
            crop_stats['count'] += int(len(values['recent_dialog'])>cfg['recent_dialog_max_chars'])
            # Stable priority: recent real dialog, last voice summary, schedule, memories.
            chunks = [('recent_dialog', values['recent_dialog'][:cfg['recent_dialog_max_chars']]),
                      ('voice_history', values['voice_history'] or '暂无可用的上次通话摘要'),
                      ('schedule', values['schedule'])]
            chunks += [(f'memory:{item["id"]}', item['content']) for item in memories]
            for chunk_index, (section, text) in enumerate(chunks):
                if not text:
                    continue
                label = {'recent_dialog': '最近对话', 'voice_history': '上次语音', 'schedule': '日程'}.get(section, '记忆')
                prefix = '\n' + label + '：'
                space = cfg['dynamic_max_chars'] - len(dynamic) - len(prefix)
                if space <= 0:
                    crop_stats["count"] += sum(bool(value) for _,value in chunks[chunk_index:])
                    break
                crop_stats["count"] += int(len(text)>space)
                kept = text[:space]
                dynamic += prefix + kept
                if section == 'recent_dialog':
                    recent_chars = len(kept)
                if section.startswith('memory:'):
                    memory_ids.append(section[7:])
    if time.monotonic() >= started + cfg['build_budget_ms']/1000 and not degraded:
        degraded, reason = True, 'compile_timeout'
    if degraded:
        dynamic, recent_chars, memory_ids = minimum, 0, []
    metadata = _freeze({'persona_ref': ref, 'degradation_reason': reason,
                        'persona_chars': len(persona), 'dynamic_chars': len(dynamic),
                        'recent_dialog_chars': recent_chars, 'memory_count': len(memory_ids),
                        'memory_source_ids': memory_ids,
                        'crop_count':crop_stats['count'],
                        'elapsed_ms': int((time.monotonic()-started)*1000)})
    pack = ContextPack(persona, dynamic, metadata, degraded)
    ready_barrier.set()
    return pack


def context_pack_events(*, pack, error, elapsed_ms, barrier_released):
    result = 'cancelled' if isinstance(error, asyncio.CancelledError) else 'failure'
    events = []
    if pack is not None:
        result = 'minimal' if pack.degraded else 'full'
        for section in ('persona','dynamic'):
            events.append(('voice.context_pack.size_chars',{'section':section},len(getattr(pack,section))))
        events.append(('voice.context_pack.crop_count',{},pack.metadata.get('crop_count',0)))
        if pack.degraded:
            reason = pack.metadata.get('degradation_reason')
            if reason not in {'timeout','source_failed','source_invalid','compile_timeout'}:
                reason = 'unavailable'
            events.append(('voice.context_pack.fallback',{'reason':reason},1))
    elif error is not None:
        reason = str(error) if isinstance(error,ContextPackError) else 'timeout' if isinstance(error,TimeoutError) else 'cancelled' if isinstance(error,asyncio.CancelledError) else 'unavailable'
        if reason not in {'persona_anchor_invalid','context_config_invalid','persona_empty','minimum_context_budget_invalid','referenced_persona_unavailable','timeout','cancelled'}:
            reason = 'unavailable'
        events.append(('voice.context_pack.failure',{'reason':reason},1))
    events.extend([('voice.context_pack.result',{'result':result},1),
        ('voice.context_pack.duration_ms',{'result':result},max(0,elapsed_ms)),
        ('voice.context_pack.barrier',{'result':'released' if barrier_released else 'not_released'},1)])
    return events

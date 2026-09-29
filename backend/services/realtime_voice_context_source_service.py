"""Read-only voice context sources; never invoke text conversation business nodes."""
import asyncio
import hashlib
import json
from datetime import timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, or_

from backend.models.admin_config import AdminConfig
from backend.models.conversation_log import ConversationLog
from backend.models.life_plan import LifePlan
from backend.models.memory import Memory
from backend.models.relationship import Relationship
from backend.models.realtime_voice import VoiceCall
from backend.services.realtime_voice_context_pack_service import ContextPackError, build_context_pack


async def strict_voice_memory_search(query, user_id):
    # Reuse transport/embedding primitives, not the text rewrite/recall node.
    from backend.services.embedding_service import embedding_service
    from backend.utils.dashvector_client import dashvector_client, build_filter
    from backend.config import get_dashvector_endpoint, get_dashvector_collection
    async with asyncio.timeout(.8):
        vector = await embedding_service.get_embedding(query[:200])
    if not vector:
        raise ContextPackError('memory_embedding_unavailable')
    async def search(kind):
        client = await dashvector_client._get_client()
        response = await client.post(
            f'{get_dashvector_endpoint()}/v1/collections/{get_dashvector_collection()}/query',
            headers=dashvector_client._build_headers(),
            json={'vector': vector, 'topk': 20, 'filter': build_filter(kind, user_id, []), 'include_vector': False},
            timeout=1)
        response.raise_for_status()
        data = response.json()
        if data.get('code', 0) != 0 or not isinstance(data.get('output'), list):
            raise ContextPackError('memory_search_unavailable')
        return [(kind, item) for item in data['output'][:20]]
    results = await asyncio.gather(search('user'), search('character_private'))
    return results[0]+results[1]


class DatabaseVoiceContextSource:
    def __init__(self, session_factory, *, memory_search=strict_voice_memory_search):
        self.session_factory, self.memory_search = session_factory, memory_search

    async def load(self, section, user_id, now):
        # Each parallel source owns its session; AsyncSession is never shared
        # between the compiler's concurrent tasks.
        async with self.session_factory() as db:
            if section == 'schedule':
                plan = await db.scalar(select(LifePlan).where(
                    LifePlan.plan_date == now.astimezone(ZoneInfo('Asia/Shanghai')).date(), LifePlan.gen_status == 'ready'))
                if not plan:
                    return '暂无可靠的当前日程'
                return json.dumps(plan.scenes[:24], ensure_ascii=False)[:600]
            if section == 'recent_dialog':
                rows = (await db.execute(select(ConversationLog.role, ConversationLog.content).where(
                    ConversationLog.user_id == user_id, ConversationLog.persona_risk_flag.is_(False),
                    ConversationLog.skipped_in_prompt.is_(False),
                    or_(ConversationLog.role == 'assistant', ConversationLog.delivery_status == 'delivered'))
                    .order_by(ConversationLog.sort_seq.desc(), ConversationLog.id.desc()).limit(12))).all()
                return '\n'.join(f'{role}：{text[:400]}' for role, text in reversed(rows))[-800:]
            if section == 'voice_history':
                row = await db.scalar(select(VoiceCall).where(VoiceCall.user_id == user_id,
                    VoiceCall.status == 'ended', VoiceCall.deleted_at.is_(None), VoiceCall.deletion_fence_at.is_(None),
                    VoiceCall.summary_status == 'ready',
                    or_(VoiceCall.generated_text_expires_at.is_(None), VoiceCall.generated_text_expires_at > now.replace(tzinfo=None)))
                    .order_by(VoiceCall.ended_at.desc()).limit(1))
                if row is None:
                    return '上次语音摘要暂无可靠内容，不推测缺失的对话。'
                return json.dumps(dict(summary=(row.call_summary or '')[:350], user_emotion=row.user_emotion,
                    assistant_emotion=row.assistant_emotion, unfinished_topics=(row.unfinished_topics or [])[:5]), ensure_ascii=False)[:600]
            if section != 'memories':
                raise ContextPackError('unknown_context_source')
            query = await db.scalar(select(ConversationLog.content).where(ConversationLog.user_id == user_id,
                ConversationLog.role == 'user', ConversationLog.persona_risk_flag.is_(False),
                ConversationLog.delivery_status == 'delivered').order_by(ConversationLog.id.desc()).limit(1))
        candidates = await self.memory_search(query or '用户近期近况、共同经历和未完成的话题', user_id)
        ids = [item.get('id') for _, item in candidates if isinstance(item, dict)]
        async with self.session_factory() as db:
            legacy = (await db.scalars(select(Memory).where(Memory.user_id == user_id,
                                                           Memory.dashvector_id.in_(ids)))).all() if ids else []
        legacy = {r.dashvector_id: r for r in legacy}
        rows = []
        from backend.utils.character_knowledge_validate import is_user_manageable_doc_id
        for kind, item in candidates[:40]:
            if not isinstance(item, dict):
                continue
            fields = item.get('fields', {})
            if not isinstance(fields, dict) or fields.get('user_id') not in (None, user_id):
                continue
            old = legacy.get(item.get('id'))
            if old is not None:
                rows.append(dict(id=item['id'], content=old.content[:400], score=item.get('score', 0),
                    quality=min(1, max(0, old.importance_score/4)), updated_at=old.updated_at.replace(tzinfo=timezone.utc).isoformat(),
                    expires_at=old.expires_at.replace(tzinfo=timezone.utc).isoformat() if old.expires_at else None,
                    is_deleted=old.is_deleted, source_channel='text'))
            elif fields.get('user_id') == user_id and is_user_manageable_doc_id(item.get('id', ''), user_id=user_id, expected_type=kind):
                # Missing historic time/quality stays missing. The compiler will
                # exclude unprovable recency, never label retrieval time as age.
                rows.append(dict(id=item['id'], content=str(fields.get('content', ''))[:400], score=item.get('score', 0),
                    quality=fields.get('quality', 0), updated_at=fields.get('updated_at'), expires_at=fields.get('expires_at'),
                    is_deleted=fields.get('is_deleted', False), source_channel=fields.get('source_channel')))
        return rows


async def prepare_voice_context(*, call, session_factory, now, barrier, source=None):
    import time
    from copy import deepcopy
    started = time.monotonic()
    config = call.config_snapshot['resolved_config']
    settings = deepcopy(call.config_snapshot['resolved_script']['context_pack'])
    ref = config['persona_ref']
    async with asyncio.timeout(settings['build_budget_ms']/1000), session_factory() as db:
        versions = (await db.scalars(select(AdminConfig).where(AdminConfig.config_key == 'persona',
            AdminConfig.version == ref['version'], AdminConfig.is_draft.is_(False)))).all()
        persona_raw = next((r.config_value for r in versions if isinstance(r.config_value, str) and
                           'sha256:'+hashlib.sha256(r.config_value.encode()).hexdigest() == ref['content_sha256']), None)
        relationship = await db.scalar(select(Relationship).where(Relationship.user_id == call.user_id))
        salutation = (relationship.user_hobby_name or relationship.user_real_name or '你') if relationship else '你'
        description = (relationship.relation_description or f'关系阶段{relationship.level}') if relationship else '初识'
    if persona_raw is None:
        raise ContextPackError('referenced_persona_unavailable')
    settings['build_budget_ms'] = max(1, settings['build_budget_ms']-int((time.monotonic()-started)*1000))
    return await build_context_pack(user_id=call.user_id, persona_raw=persona_raw, persona_ref=ref,
        settings=settings, source=source or DatabaseVoiceContextSource(session_factory), salutation=salutation,
        relationship=description, now=now, ready_barrier=barrier)

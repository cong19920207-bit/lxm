"""Shared validated full upsert for user-owned Stable Keys.

Uses the same embedding input and Stable Key. Last writer is metadata only;
the admin create endpoint keeps its separate duplicate-rejection semantics.
"""
from backend.utils.character_knowledge_validate import validate_key, validate_value, build_doc_id, build_content
from backend.services.user_vector_memory_service import _build_user_fields
from backend.services.memory_write_source import SOURCES, observe_previous_source, record_source_observation


async def upsert_user_memory(*, memory_type, user_id, key, value, embed=None, vector_client=None, last_write_source="unknown"):
    if (not isinstance(key, str) or not isinstance(value, str) or
            validate_key(key) or validate_value(value) or
            not isinstance(memory_type, str) or memory_type not in {'user', 'character_private'} or
            type(user_id) is not int or user_id < 1):
        raise ValueError('invalid_user_memory_atom')
    if not isinstance(last_write_source, str) or last_write_source not in SOURCES:
        raise ValueError('invalid_memory_write_source')
    key, value = key.strip(), value.strip()
    if embed is None:
        from backend.services.embedding_service import embedding_service
        embed = embedding_service.get_embedding
    if vector_client is None:
        from backend.utils.dashvector_client import dashvector_client
        vector_client = dashvector_client
    vector = await embed(value)
    if not vector:
        raise RuntimeError('memory_embedding_unavailable')
    doc_id = build_doc_id(memory_type, key, user_id)
    previous = await observe_previous_source(vector_client, doc_id)
    success = await vector_client.upsert(doc_id=doc_id, vector=vector,
        fields=_build_user_fields(key, build_content(key, value), user_id, last_write_source=last_write_source), memory_type=memory_type)
    if not success:
        raise RuntimeError('memory_vector_write_failed')
    record_source_observation(previous)
    return doc_id

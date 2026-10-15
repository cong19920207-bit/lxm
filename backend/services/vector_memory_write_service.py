"""Validated user/private Stable Key writer with durable source/index receipt."""
from backend.utils.character_knowledge_validate import validate_key, validate_value
from backend.services.memory_business_writer import get_memory_writer


async def upsert_user_memory(*, memory_type, user_id, key, value, writer=None,
                             last_write_source="unknown", source_entry='', resume_only=False):
    if (not isinstance(key,str) or not isinstance(value,str) or validate_key(key) or validate_value(value)
            or memory_type not in {'user','character_private'} or type(user_id) is not int or user_id<1):
        raise ValueError('invalid_user_memory_atom')
    from backend.services.memory_write_source import SOURCES
    if not isinstance(last_write_source, str) or last_write_source not in SOURCES:
        raise ValueError('invalid_memory_write_source')
    writer=writer or await get_memory_writer()
    result = await writer.upsert(memory_type=memory_type,user_id=user_id,key=key,value=value,
        source=last_write_source,source_entry=source_entry,resume_only=resume_only)
    if result.receipt['source_result'] == 'failed':
        error = RuntimeError('memory_vector_write_failed')
        error.receipt = result.receipt
        raise error
    return result

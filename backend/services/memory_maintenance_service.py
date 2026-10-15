"""Safe display projections: no body, credentials, raw errors, or recovery authority."""
import re
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from backend.models.memory_maintenance import MemoryMaintenanceEvent


async def record_index_event(db, task, op, event_type, reason, now):
    if not isinstance(event_type, str) or not re.fullmatch('[a-z][a-z0-9_]{0,31}', event_type):
        raise ValueError('event_type_invalid')
    if reason is not None and (not isinstance(reason, str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}', reason)):
        raise ValueError('event_reason_invalid')
    operation_id = op.operation_id if op is not None else None
    event_id = str(uuid5(NAMESPACE_URL, f'memory-index:{task.task_id}:{task.round_no}:{task.attempt}:{operation_id}:{event_type}'))
    values = dict(event_id=event_id, record_kind='task', task_id=task.task_id, operation_id=operation_id,
                  identity_id=task.identity_id, generation=task.generation, event_type=event_type,
                  source_state=op.source_result if op is not None else None,
                  index_state=op.index_result if op is not None else None, maintenance_state=task.state,
                  attempt_number=task.attempt, started_at=now if event_type == 'attempt_started' else None,
                  ended_at=now if task.state in {'completed','manual','superseded'} else None,
                  created_at=now, controlled_reason=reason,
                  details={'round_no': task.round_no, 'attempt': task.attempt})
    if db.get_bind().dialect.name == 'mysql':
        query = mysql_insert(MemoryMaintenanceEvent).values(**values).on_duplicate_key_update(event_id=MemoryMaintenanceEvent.event_id)
    else:
        query = sqlite_insert(MemoryMaintenanceEvent).values(**values).on_conflict_do_nothing(index_elements=['event_id'])
    await db.execute(query)
    return event_id

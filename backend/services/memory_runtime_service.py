"""Shared fail-closed activation check. This module never activates a target."""
from sqlalchemy import select, text, update

from backend.models.memory_control import MemoryRuntimeFence


class MemoryControlError(Exception):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason
        super().__init__(reason)


async def require_active_fence(db, environment_id, target_epoch, target_fingerprint,
                               allow_isolated=False, lock=True):
    try:
        db.info["memory_business_epoch"] = {"environment_id":environment_id,"target_epoch":target_epoch,"target_fingerprint":target_fingerprint.hex()}
        if lock and db.get_bind().dialect.name == "sqlite":
            # SQLite has no row locks; reserve its writer before reading truth.
            await db.execute(update(MemoryRuntimeFence).where(
                MemoryRuntimeFence.environment_id == environment_id,
            ).values(revision=MemoryRuntimeFence.revision, updated_at=MemoryRuntimeFence.updated_at)
                .execution_options(synchronize_session=False))
        query = select(MemoryRuntimeFence).where(MemoryRuntimeFence.environment_id == environment_id)
        if lock:
            query = query.with_for_update()
        row = await db.scalar(query.execution_options(populate_existing=True))
        if row is None or row.mode != "active":
            raise MemoryControlError(20126, "runtime_not_active")
        if row.target_epoch != target_epoch or row.target_fingerprint != target_fingerprint:
            raise MemoryControlError(20127, "runtime_target_changed")
        if allow_isolated and environment_id.startswith("isolated:") and row.reset_run_id is None:
            return row
        if not row.reset_run_id:
            raise MemoryControlError(20126, "activation_unverified")
        # STEP-008 adds its model/FK. Until then the normal path fails closed.
        reset = (await db.execute(text(
            "SELECT environment_id,target_epoch,target_fingerprint,state,completed_at "
            "FROM memory_reset_run WHERE run_id=:run_id"
        ), {"run_id": row.reset_run_id})).mappings().first()
        if (reset is None or reset["environment_id"] != environment_id
                or reset["target_epoch"] != target_epoch or reset["target_fingerprint"] != target_fingerprint
                or reset["state"] not in {"completed", "opened"} or reset["completed_at"] is None):
            raise MemoryControlError(20126, "activation_unverified")
        return row
    except MemoryControlError:
        raise
    except Exception:
        raise MemoryControlError(20129, "activation_unverified") from None

"""Read existing task/backfill truth; deletion touches display events only."""
import asyncio
from datetime import datetime
from sqlalchemy import select,func,and_,or_,not_
from backend.models.memory_control import MemoryIndexTask as Task,MemoryIdentity as Identity,MemoryOperation as Operation,MemoryUseClaim,MemoryUseItem,MemoryRuntimeFence
from backend.models.memory_backfill import MemoryBackfillRun as Backfill,MemoryBackfillItem as Item
from backend.models.memory_maintenance import MemoryMaintenanceEvent as Event
from backend.services.memory_admin_common import AdminMemoryError,dates,iso,page_data,sql_page,WRITE_ROLES
from backend.services.memory_index_retry_service import _decide,retry_task
from backend.services.memory_runtime_service import require_active_fence,MemoryControlError
from backend.utils.admin_auth import log_operation


class MaintenanceService:
    def __init__(self,sessions,environment_id):self.sessions,self.environment_id=sessions,environment_id

    async def _fence(self,db,lock=False):
        fence=await db.get(MemoryRuntimeFence,self.environment_id)
        if fence is None:raise AdminMemoryError(20126,'runtime_not_active')
        try:
            return await require_active_fence(db,self.environment_id,fence.target_epoch,fence.target_fingerprint,
                allow_isolated=self.environment_id.startswith('isolated:'),lock=lock)
        except MemoryControlError as exc:raise AdminMemoryError(exc.code,exc.reason) from None

    async def task(self,db,row,role):
        identity=await db.get(Identity,row.identity_id)
        source=await db.get(Operation,row.operation_id)
        if identity is None or source is None:raise AdminMemoryError(20129,'task_source_unavailable')
        reason='read_only';eligible=False
        if role in WRITE_ROLES:
            try:
                fence=await self._fence(db)
                if identity.target_epoch!=fence.target_epoch or identity.target_fingerprint!=fence.target_fingerprint:
                    raise AdminMemoryError(20127,'runtime_target_changed')
                decision=await _decide(db,identity,row,None,row.revision,datetime.utcnow(),dry_run=True)
                reason=decision['reason'];eligible=decision.get('accepted_new_round',False)
            except Exception:reason='retry_eligibility_unavailable'
        current=row.generation==identity.generation and row.body_hash==identity.body_hash and row.encoder_version==identity.encoder_version
        state='superseded' if not current or row.state=='superseded' else 'source_unverified' if identity.source_state=='unknown' else 'manual_required' if row.state=='manual' else row.state
        receipt=source.receipt_summary or {}
        # Never expose arbitrary operation payload/provider errors in the management DTO.
        source_name=source.owner_actor_type
        return dict(id=row.task_id,task_id=row.task_id,identity_id=str(row.identity_id),type=identity.memory_type,
            user_id=identity.owner_user_id,doc_id=identity.doc_id,source=source_name,operation=source.operation_kind,
            operation_id=source.operation_id,source_state={'confirmed':'succeeded','superseded':'failed'}.get(source.source_result,source.source_result),
            index_state={'manual':'unknown','not_required':'not_executed','superseded':'not_executed'}.get(source.index_result,source.index_result),
            maintenance_state=state,generation=str(row.generation),current_generation=str(identity.generation),
            currentness='current' if current else 'superseded',attempt_count=row.attempt,round_no=row.round_no,
            revision=str(row.revision),updated_at=iso(row.updated_at),next_attempt_at=iso(row.next_attempt_at),
            manual_reason=row.error_code,can_retry=eligible,can_delete=False,action_reason=reason)

    async def tasks(self,actor,*,page,page_size,user_id=None,memory_type=None,state=None,operation=None,source=None,doc_id=None,start_date=None,end_date=None):
        filters=[]
        current=and_(Task.generation==Identity.generation,Task.body_hash==Identity.body_hash,Task.encoder_version==Identity.encoder_version)
        if state=='superseded':filters.append(or_(Task.state=='superseded',not_(current)))
        elif state=='source_unverified':filters.extend([current,Identity.source_state=='unknown',Task.state!='superseded'])
        elif state:filters.extend([current,Identity.source_state!='unknown',Task.state==('manual' if state=='manual_required' else state)])
        if user_id is not None:filters.append(Identity.owner_user_id==user_id)
        if memory_type:filters.append(Identity.memory_type==memory_type)
        if doc_id:filters.append(Identity.doc_id==doc_id)
        if operation:filters.append(Operation.operation_kind==operation)
        if source:filters.append(Operation.owner_actor_type==source)
        dates(filters,Task.updated_at,start_date,end_date)
        query=select(Task).join(Identity,Identity.id==Task.identity_id).join(Operation,Operation.operation_id==Task.operation_id).where(*filters)
        async with self.sessions() as db:
            total=await db.scalar(select(func.count()).select_from(query.subquery()))
            rows=(await db.scalars(query.order_by(Task.updated_at.desc(),Task.task_id.desc()).offset((page-1)*page_size).limit(page_size))).all()
            return page_data([await self.task(db,r,actor.role) for r in rows],total,page,page_size)

    async def task_detail(self,task_id,actor,*,section=None,page=1,page_size=20):
        async with self.sessions() as db:
            row=await db.get(Task,task_id)
            if row is None:raise AdminMemoryError(20125,'task_unavailable')
            data=await self.task(db,row,actor.role)
            deleted=await db.scalar(select(func.count()).select_from(Event).where(Event.task_id==task_id,Event.display_deleted_at.is_not(None)))
            data.update(deleted_attempt_count=deleted,history_state='partially_deleted' if deleted else 'available')
            links=select(Item.run_id).where(Item.task_id==task_id).distinct()
            link_total=await db.scalar(select(func.count()).select_from(links.subquery()))
            data.update(backfill_total=link_total,run_id=await db.scalar(links) if link_total==1 else None)
            if section=='backfills':
                run_ids=(await db.scalars(links.order_by(Item.run_id.asc()).offset((page-1)*page_size).limit(page_size))).all()
                return {**data,**page_data([dict(id=run_id,run_id=run_id,
                    status_url='/api/admin/memory-index-maintenance/backfills/'+run_id) for run_id in run_ids],link_total,page,page_size)}
            if section=='attempts':
                rows,total=await sql_page(db,Event,[Event.task_id==task_id,Event.display_deleted_at.is_(None)],
                    [Event.created_at.asc(),Event.id.asc()],page,page_size)
                return {**data,**page_data([await self.event(db,e,actor.role) for e in rows],total,page,page_size)}
            latest=await db.scalar(select(Task).where(Task.identity_id==row.identity_id).order_by(Task.generation.desc(),Task.updated_at.desc(),Task.task_id.desc()).limit(1))
            data['superseded_by']=latest.task_id if latest and latest.task_id!=task_id else None
            return data

    async def retry(self,task_id,body,actor):
        result=await retry_task(self.sessions,self.environment_id,task_id,actor_type='admin',actor_id=actor.id,
            client_request_id=body['request_id'],task_revision=int(body['expected_revision']),allow_isolated=self.environment_id.startswith('isolated:'))
        for key in ('task_revision','latest_task_revision'):
            if result.get(key) is not None:result[key]=str(result[key])
        return result

    async def event_deletable(self,db,event,*,lock=False):
        if event.display_deleted_at:return True,'already_deleted'
        async def row(model,key,column):
            q=select(model).where(column==key)
            return await db.scalar(q.with_for_update() if lock else q)
        if event.task_id:
            task=await row(Task,event.task_id,Task.task_id)
            if task is None or task.state!='completed':return False,'task_not_completed'
            identity=await row(Identity,task.identity_id,Identity.id)
            if identity is None:return False,'identity_unavailable'
            if (task.generation!=identity.generation or task.body_hash!=identity.body_hash or task.encoder_version!=identity.encoder_version):
                return False,'task_superseded'
            if identity.inflight_operation_id:return False,'operation_protected'
            active=await db.scalar(select(Task.task_id).where(Task.identity_id==identity.id,Task.state.in_(['pending','running','retry_wait','manual'])).limit(1))
            if active:return False,'task_protected'
            open_op=await db.scalar(select(Operation.operation_id).where(Operation.identity_id==identity.id,
                Operation.dispatch_state.in_(['prepared','claimed','dispatching','unknown'])).limit(1))
            if open_op:return False,'operation_protected'
            claim=await db.scalar(select(MemoryUseItem.claim_id).join(MemoryUseClaim,MemoryUseClaim.claim_id==MemoryUseItem.claim_id)
                .where(MemoryUseItem.identity_id==identity.id,MemoryUseClaim.state.in_(['reserved','dispatching','unknown'])).limit(1))
            if claim:return False,'use_protected'
            unfinished=await db.scalar(select(Item.id).join(Backfill,Backfill.run_id==Item.run_id).where(Item.task_id==task.task_id,
                Backfill.report_complete.is_(False)).limit(1))
            if unfinished:return False,'reconcile_protected'
        if event.run_id:
            run=await row(Backfill,event.run_id,Backfill.run_id)
            if run is None or run.execution_state!='completed' or not run.report_complete or run.unresolved_count:
                return False,'backfill_not_complete'
            # STEP008 has no release-of-reconciliation-authority operation. Its item references remain protected.
            item=await db.scalar(select(Item.id).where(Item.run_id==run.run_id).limit(1))
            if item:return False,'reconcile_protected'
        return True,'completed_display_only'

    async def event(self,db,e,role):
        allowed,reason=await self.event_deletable(db,e)
        return dict(id=str(e.id),record_id=str(e.id),event_id=e.event_id,record_kind=e.record_kind,task_id=e.task_id,
            run_id=e.run_id,operation_id=e.operation_id,event_type=e.event_type,source_state=e.source_state,
            index_state=e.index_state,maintenance_state=e.maintenance_state,attempt_number=e.attempt_number,
            started_at=iso(e.started_at),ended_at=iso(e.ended_at),created_at=iso(e.created_at),
            reason=e.controlled_reason,details=e.details,can_delete=role in WRITE_ROLES and allowed,action_reason=reason)

    async def delete_history(self,record_id,actor):
        commit=False
        try:
            async with asyncio.timeout(5), self.sessions() as db:
                await self._fence(db,lock=True)
                e=await db.scalar(select(Event).where(Event.id==int(record_id)).with_for_update())
                if e is None:raise AdminMemoryError(20125,'history_unavailable')
                allowed,reason=await self.event_deletable(db,e,lock=True)
                if not allowed:raise AdminMemoryError(20126,reason,{'record_id':str(e.id),'can_delete':False})
                e.display_deleted_at=datetime.utcnow();e.details=None;e.controlled_reason=None
                await log_operation(db,actor,'memory_maintenance','delete',str(e.id))
                commit=True;await db.commit()
                return dict(record_id=str(e.id),history_state='deleted',can_delete=False)
        except AdminMemoryError:raise
        except Exception:raise AdminMemoryError(20122 if commit else 20129,'history_delete_unverified' if commit else 'persistence_unavailable',{'record_id':str(record_id)}) from None

    async def backfill(self,db,r):
        deleted=await db.scalar(select(Event.id).where(Event.run_id==r.run_id,Event.display_deleted_at.is_not(None)).limit(1))
        if deleted:return {'id':r.run_id,'run_id':r.run_id,'history_state':'deleted','progress_available':False,'reason':'display_history_deleted','can_delete':False,'action_reason':'display_history_deleted'}
        data={name:getattr(r,name) for name in ('mode','execution_state','stage','source_scope','baseline','high_water','checkpoint_summary','cutoff',
            'scanned_records','unique_source_ids','attempt_count','total_known','total_source_ids','source_class_counts','reconcile_counts','unresolved_count','report_complete')}
        data.update(id=r.run_id,run_id=r.run_id,history_state='available',progress_available=True,can_delete=False,action_reason='reconcile_protected',
            frozen_versions=r.frozen_versions,index_version=r.frozen_versions.get('index_version'),encoder_version=r.frozen_versions.get('encoder_version'),
            started_at=iso(r.started_at),ended_at=iso(r.ended_at),updated_at=iso(r.updated_at),revision=str(r.revision))
        return data

    async def backfills(self,*,page,page_size,state=None,stage=None,start_date=None,end_date=None):
        filters=[]
        if state:filters.append(Backfill.execution_state==state)
        if stage:filters.append(Backfill.stage==stage)
        dates(filters,Backfill.started_at,start_date,end_date)
        async with self.sessions() as db:
            rows,total=await sql_page(db,Backfill,filters,[Backfill.started_at.desc(),Backfill.run_id.desc()],page,page_size)
            return page_data([await self.backfill(db,r) for r in rows],total,page,page_size)

    async def backfill_detail(self,run_id):
        async with self.sessions() as db:
            run=await db.get(Backfill,run_id)
            if run is None:raise AdminMemoryError(20125,'backfill_unavailable',{'progress_available':False})
            return await self.backfill(db,run)

    async def backfill_items(self,run_id,*,page,page_size,source_class=None,state=None):
        filters=[Item.run_id==run_id]
        if source_class:filters.append(Item.source_class==source_class)
        if state:filters.append(Item.reconcile_state==state)
        async with self.sessions() as db:
            run=await db.get(Backfill,run_id)
            if run is None:raise AdminMemoryError(20125,'backfill_unavailable',{'progress_available':False})
            deleted=await db.scalar(select(Event.id).where(Event.run_id==run_id,Event.display_deleted_at.is_not(None)).limit(1))
            if deleted:raise AdminMemoryError(20125,'display_history_deleted',{'history_state':'deleted','progress_available':False})
            rows,total=await sql_page(db,Item,filters,[Item.item_seq.asc(),Item.id.asc()],page,page_size)
            items=[]
            for item in rows:
                identity=await db.get(Identity,item.identity_id) if item.identity_id is not None else None
                items.append(dict(id=str(item.id),run_id=run_id,item_seq=str(item.item_seq),source_identity=item.identity_key,
                    type=identity.memory_type if identity else None,user_id=identity.owner_user_id if identity else None,
                    source_class=item.source_class,content_digest=item.content_digest.hex() if item.content_digest else None,
                    current_generation=str(item.current_generation) if item.current_generation is not None else None,index_result=item.index_result,
                    reconcile_state=item.reconcile_state,task_id=item.task_id,attempt_count=item.attempt_count,
                    observed_at=iso(item.observed_at),reason=item.reason))
            return page_data(items,total,page,page_size)

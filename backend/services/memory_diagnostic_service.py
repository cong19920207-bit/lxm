"""SQL admission and bounded diagnostic lifecycle. GET never repairs or runs work."""
import asyncio
from contextlib import suppress
from datetime import datetime,timedelta,timezone
import hashlib
import json
from uuid import UUID,uuid4
from sqlalchemy import select,update,or_
from backend.models.memory_diagnostic import MemoryDiagnosticRun as Run
from backend.models.memory_control import MemoryRuntimeFence,MemoryUseClaim
from backend.models.user import User
from backend.services.memory_runtime_service import require_active_fence,MemoryControlError
from backend.services.memory_admin_common import AdminMemoryError,iso,page_data,sql_page,dates,WRITE_ROLES
from backend.utils.admin_auth import log_operation

ACTIVE={'accepted','running'}
TERMINAL={'completed','degraded','failed','budget_blocked','interrupted'}


def deletable(row):
    return row.execution_state in TERMINAL and row.history_state in {'saved','failed','deleted'} and row.lease_owner is None


def project(row,role='observer'):
    return dict(id=row.run_id,execution_id=row.run_id,request_id=row.request_id,user_id=row.user_id,
        admin_id=row.admin_id,source=row.source,parent_execution_id=row.parent_run_id,
        execution_state=row.execution_state,history_state=row.history_state,revision=str(row.result_revision),
        snapshot_available=row.snapshot_available,reason=row.controlled_reason,stage=row.stage,
        created_at=iso(row.created_at),started_at=iso(row.started_at),finished_at=iso(row.finished_at),
        observed_at=iso(row.observed_at),deadline_at=iso(row.deadline_at),persist_deadline_at=iso(row.persist_deadline_at),
        status_url='/api/admin/memory-diagnostics/'+row.run_id,
        can_delete=role in WRITE_ROLES and row.history_state!='deleted' and deletable(row),server_time=iso(datetime.utcnow()))


def candidate_entries(row):
    """Page safe references for removals which have no ownership-verified snapshot.

    Retain existing snapshot order; the stored removal ordinal makes identities
    stable across pages and route filters, including repeated channel rejections.
    Never copy unverified candidate body fields into a removal-only entry.
    """
    entries=list(row.candidate_snapshots or [])
    present={(entry['route'],entry['doc_id']) for entry in entries}
    for ordinal,removal in enumerate((row.selection_result or {}).get('removed',[])):
        if (removal['route'],removal['doc_id']) in present:continue
        entries.append(dict(id=f"removal:{removal['route']}:{ordinal}",entry_kind='removal',
            ordinal=ordinal,route=removal['route'],doc_id=removal['doc_id'],identity_id=str(removal['identity_id']) if removal.get('identity_id') is not None else None,
            stage=removal['stage'],reason=removal['reason'],selected=False,initial_selected=False))
    return entries


class DiagnosticService:
    def __init__(self,sessions,environment_id):
        self.sessions,self.environment_id=sessions,environment_id
        self.jobs={}
        self.owner=str(uuid4())
        self.recovery=None

    async def _fence(self,db):
        row=await db.get(MemoryRuntimeFence,self.environment_id)
        if row is None:raise AdminMemoryError(20126,'runtime_not_active')
        try:
            return await require_active_fence(db,self.environment_id,row.target_epoch,row.target_fingerprint,
                allow_isolated=self.environment_id.startswith('isolated:'))
        except MemoryControlError as exc:raise AdminMemoryError(exc.code,exc.reason) from None

    async def _prior(self,db,admin_id,request_id):
        return await db.scalar(select(Run).where(Run.admin_id==admin_id,Run.request_id==request_id))

    async def _replay(self,db,row,digest,role):
        data=await self.projection(db,row,role)
        if row.request_digest!=digest:raise AdminMemoryError(20121,'request_conflict',data)
        return data,False

    async def admit(self,body,actor):
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).digest()
        committed=False
        try:
            async with asyncio.timeout(5):
                async with self.sessions() as db:
                    prior=await self._prior(db,actor.id,body['request_id'])
                    if prior:return await self._replay(db,prior,digest,actor.role)
                    now=datetime.utcnow()
                    age=now.replace(tzinfo=timezone.utc).timestamp()*1000-(UUID(body['request_id']).int>>80)
                    if not -30000<=age<=120000:raise AdminMemoryError(20123,'request_outside_window')
                    # Discard the preliminary REPEATABLE READ snapshot before fence serialization.
                    await db.rollback()
                    await self._fence(db)
                    prior=await db.scalar(select(Run).where(Run.admin_id==actor.id,Run.request_id==body['request_id'])
                        .with_for_update().execution_options(populate_existing=True))
                    if prior:return await self._replay(db,prior,digest,actor.role)
                    user=await db.get(User,body['user_id'])
                    if user is None:raise AdminMemoryError(20125,'user_unavailable')
                    if body.get('parent_execution_id'):
                        parent=await db.get(Run,body['parent_execution_id'])
                        if parent is None or parent.environment_id!=self.environment_id:raise AdminMemoryError(20125,'parent_unavailable')
                    active=(await db.scalars(select(Run).where(Run.environment_id==self.environment_id,
                        or_(Run.execution_state.in_(ACTIVE),Run.lease_owner.is_not(None))).with_for_update())).all()
                    if len(active)>=2 or any(r.admin_id==actor.id or r.user_id==body['user_id'] for r in active):
                        raise AdminMemoryError(20124,'diagnostic_concurrency_limit')
                    row=Run(run_id=str(uuid4()),admin_id=actor.id,user_id=body['user_id'],environment_id=self.environment_id,
                        request_id=body['request_id'],request_digest=digest,source=body['source'],input_text=body['input'],
                        parent_run_id=body.get('parent_execution_id'),execution_state='accepted',history_state='pending',
                        created_at=now,observed_at=now,deadline_at=now+timedelta(seconds=120),
                        persist_deadline_at=now+timedelta(seconds=150),stage='accepted',result_revision=1)
                    db.add(row)
                    await log_operation(db,actor,'memory_diagnostics','create',row.run_id)
                    committed=True
                    await db.commit()
                async with self.sessions() as verify:
                    saved=await self._prior(verify,actor.id,body['request_id'])
                    if saved:return project(saved,actor.role),True
        except AdminMemoryError:raise
        except Exception:
            if committed:
                try:
                    async with asyncio.timeout(5):
                        async with self.sessions() as db:
                            prior=await self._prior(db,actor.id,body['request_id'])
                            if prior:return (await self._replay(db,prior,digest,actor.role))[0],True
                except AdminMemoryError:raise
                except Exception:pass
        raise AdminMemoryError(20122 if committed else 20129,'admission_unverified' if committed else 'persistence_unavailable')

    def schedule(self,run_id):
        if run_id not in self.jobs:
            task=asyncio.create_task(self.run(run_id));self.jobs[run_id]=task
            task.add_done_callback(lambda done:self.jobs.pop(run_id,None))

    async def _update(self,run_id,version,**values):
        async with asyncio.timeout(5), self.sessions() as db:
            await self._fence(db)
            row=await db.scalar(select(Run).where(Run.run_id==run_id).with_for_update())
            if row is None or row.lease_owner!=self.owner or row.lease_version!=version:
                raise AdminMemoryError(20126,'diagnostic_ownership_lost')
            if datetime.utcnow()>row.persist_deadline_at:raise AdminMemoryError(20126,'persist_deadline')
            for key,value in values.items():setattr(row,key,value)
            row.result_revision+=1;row.observed_at=datetime.utcnow()
            await db.commit()

    async def _heartbeat(self,row,worker):
        while True:
            await asyncio.sleep(5)
            try:
                now=datetime.utcnow()
                if now>=row.deadline_at:worker.cancel();return
                await self._update(row.run_id,row.lease_version,lease_until=min(row.deadline_at,now+timedelta(seconds=15)))
            except Exception:worker.cancel();return

    async def execute(self,row):
        from backend.services.memory_diagnostic_pipeline import execute_diagnostic
        return await execute_diagnostic(row,self.sessions,self.environment_id)

    async def save_snapshot(self,row,result):
        await self._update(row.run_id,row.lease_version,**{key:result[key] for key in
            ('frozen_versions','context_sources','candidate_snapshots','selection_result','metrics')},
            history_state='saved',snapshot_available=True,lease_owner=None,lease_until=None)

    async def run(self,run_id):
        row=None;pulse=None
        try:
            async with asyncio.timeout(5), self.sessions() as db:
                await self._fence(db)
                row=await db.scalar(select(Run).where(Run.run_id==run_id).with_for_update())
                if row is None or row.execution_state!='accepted' or row.deadline_at<=datetime.utcnow():return
                row.execution_state='running';row.started_at=datetime.utcnow();row.stage='executing'
                row.lease_owner=self.owner;row.lease_version+=1;row.result_revision+=1
                row.lease_until=min(row.deadline_at,datetime.utcnow()+timedelta(seconds=15))
                await db.commit()
            pulse=asyncio.create_task(self._heartbeat(row,asyncio.current_task()))
            try:
                async with asyncio.timeout(max(0,(row.deadline_at-datetime.utcnow()).total_seconds())):
                    result=await self.execute(row)
            except (Exception,asyncio.CancelledError) as exc:
                result=None
                state='interrupted' if isinstance(exc,(TimeoutError,asyncio.CancelledError)) else 'failed'
                reason='execution_interrupted' if state=='interrupted' else 'diagnostic_execution_failed'
            else:state=result['execution_state'];reason=None
            finally:
                pulse.cancel()
                with suppress(asyncio.CancelledError):await pulse
                pulse=None
            # Persist termination proof first; snapshot is deliberately a second transaction.
            await self._update(run_id,row.lease_version,execution_state=state,finished_at=datetime.utcnow(),
                terminal_at=datetime.utcnow(),stage='execution_finished',controlled_reason=reason)
            if result is None:
                await self._update(run_id,row.lease_version,history_state='failed',lease_owner=None,lease_until=None)
            else:
                try:await self.save_snapshot(row,result)
                except Exception:
                    # An uncertain commit may already have saved the snapshot. Read before marking failure.
                    async with asyncio.timeout(5), self.sessions() as db:
                        saved=await db.get(Run,run_id)
                        if saved.history_state=='saved':return
                    await self._update(run_id,row.lease_version,history_state='failed',snapshot_available=False,
                        controlled_reason='history_persist_failed',lease_owner=None,lease_until=None)
        except (Exception,asyncio.CancelledError):
            # No raw provider/SQL errors or ephemeral completion claims. Recovery owns unresolved anchors.
            pass
        finally:
            if pulse:
                pulse.cancel()
                with suppress(asyncio.CancelledError):await pulse

    async def recover(self):
        """No external retries. Deadline revokes future calls; unresolved claims retain protection."""
        async with self.sessions() as db:
            await self._fence(db)
            rows=(await db.scalars(select(Run).where(Run.environment_id==self.environment_id,
                Run.persist_deadline_at<datetime.utcnow(),Run.history_state.in_(['pending','unknown']),Run.stage!='manual_required')
                .with_for_update())).all()
            for row in rows:
                if row.run_id in self.jobs:continue
                if row.execution_state in ACTIVE:row.execution_state='manual_required'
                row.history_state='unknown';row.controlled_reason='execution_recovery_required'
                row.stage='manual_required'
                # A vanished process is not proof that its remote request stopped. Keep its shared slot.
                row.observed_at=datetime.utcnow();row.result_revision+=1
            await db.commit()

    async def _recovery_loop(self):
        while True:
            try:
                async with asyncio.timeout(5):await self.recover()
            except Exception:pass
            await asyncio.sleep(5)

    def start(self):self.recovery=asyncio.create_task(self._recovery_loop())

    async def stop(self):
        tasks=list(self.jobs.values())+([self.recovery] if self.recovery else [])
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)

    async def projection(self,db,row,role):
        data=project(row,role)
        if data['can_delete']:
            claim=await db.scalar(select(MemoryUseClaim.claim_id).where(MemoryUseClaim.execution_id==row.run_id,
                MemoryUseClaim.state.in_(['reserved','dispatching','unknown'])).limit(1))
            if claim:data['can_delete']=False;data['action_reason']='use_protected'
        return data

    async def list(self,actor,*,page=1,page_size=20,request_id=None,user_id=None,source=None,state=None,start_date=None,end_date=None):
        filters=[Run.environment_id==self.environment_id]
        if request_id:filters.extend([Run.request_id==request_id,Run.admin_id==actor.id])
        if user_id is not None:filters.append(Run.user_id==user_id)
        if source:filters.append(Run.source==source)
        if state:filters.append(Run.execution_state==state)
        dates(filters,Run.created_at,start_date,end_date)
        async with self.sessions() as db:
            rows,total=await sql_page(db,Run,filters,[Run.created_at.desc(),Run.run_id.desc()],page,page_size)
            return {**page_data([await self.projection(db,r,actor.role) for r in rows],total,page,page_size),
                'server_time':iso(datetime.utcnow())}

    async def detail(self,run_id,actor,*,section=None,page=1,page_size=20,route=None):
        async with self.sessions() as db:row=await db.get(Run,run_id)
        if row is None or row.environment_id!=self.environment_id:raise AdminMemoryError(20125,'diagnostic_unavailable')
        async with self.sessions() as db:data=await self.projection(db,row,actor.role)
        entries=candidate_entries(row)
        if section:
            values=[c for c in entries if route is None or c['route']==route]
            return {**data,**page_data(values[(page-1)*page_size:page*page_size],len(values),page,page_size)}
        selection=row.selection_result
        if selection is not None:
            selection={**{k:v for k,v in selection.items() if k not in {'selected','initial_selected','removed'}},
                'selected_count':len(selection.get('selected',[])),'initial_selected_count':len(selection.get('initial_selected',[])),
                'removed_count':len(selection.get('removed',[]))}
        data.update(input=row.input_text,frozen_versions=row.frozen_versions,context_sources=row.context_sources,
            selection_result=selection,metrics=row.metrics,candidate_total=len(entries),
            snapshot_semantics='historical_snapshot' if row.snapshot_available else 'unavailable')
        return data

    async def delete(self,run_id,actor):
        committed=False
        try:
            async with asyncio.timeout(5), self.sessions() as db:
                await self._fence(db)
                row=await db.scalar(select(Run).where(Run.run_id==run_id,Run.environment_id==self.environment_id).with_for_update())
                if row is None:raise AdminMemoryError(20125,'diagnostic_unavailable')
                claims=(await db.scalars(select(MemoryUseClaim).where(MemoryUseClaim.execution_id==run_id,
                    MemoryUseClaim.state.in_(['reserved','dispatching','unknown'])).with_for_update())).all()
                if not deletable(row) or claims:
                    data=project(row,actor.role)
                    data.update(can_delete=False,action_reason='use_protected' if claims else 'diagnostic_protected')
                    raise AdminMemoryError(20126,'diagnostic_protected',data)
                if row.history_state=='deleted':return project(row,actor.role)
                row.history_state='deleted';row.snapshot_available=False;row.deleted_at=datetime.utcnow()
                row.tombstone_until=row.deleted_at+timedelta(days=30);row.result_revision+=1
                for name in ('input_text','candidate_snapshots','selection_result','metrics','frozen_versions','context_sources','source','user_id','parent_run_id'):
                    setattr(row,name,None)
                await log_operation(db,actor,'memory_diagnostics','delete',row.run_id)
                committed=True
                await db.commit()
                return project(row,actor.role)
        except AdminMemoryError:raise
        except Exception:raise AdminMemoryError(20122 if committed else 20129,
            'delete_unverified' if committed else 'persistence_unavailable',{'execution_id':run_id}) from None

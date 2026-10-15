"""Explicit S15 maintenance runner. Preview is read-only; no startup cleanup.

All proofs are external maintenance attestations bound to the manifest/run;
this process cannot prove that a different host, watchdog or old credential is
sealed. Unknown side effects require their original durable acknowledgement.
"""
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from collections.abc import Mapping
from sqlalchemy import MetaData, and_, delete, inspect, select, update, null
from backend.models.memory_backfill import MemoryResetRun,MemoryResetItem
from backend.models.memory_control import MemoryRuntimeFence
from backend.services.memory_reset_policy import POLICIES,ORDER,selected,updates,unsettled
from backend.services.memory_runtime_service import MemoryControlError

REQUIRED_SEALS=('public_entry','direct_backend','openapi','admin','voice_gateway_callbacks','all_writers_workers',
    'all_schedulers','preserved_business_writes','billing_settled','external_requests_settled','old_processes_exited',
    'restart_deploy_watchdogs_disabled','old_credentials_revoked','logs_audio_exports_inventoried')
INFRA={'alembic_version'}
EVIDENCE={'memory_runtime_fence','memory_reset_run','memory_reset_item'}


def canonical(value):
    if isinstance(value,Mapping):return {k:canonical(v) for k,v in sorted(value.items())}
    if isinstance(value,(list,tuple)):return [canonical(v) for v in value]
    if isinstance(value,(datetime,date)):return {'$type':type(value).__name__,'value':value.isoformat()}
    if isinstance(value,bytes):return {'$binary':value.hex()}
    if isinstance(value,Decimal):return {'$decimal':str(value)}
    return value


def digest(value):
    return hashlib.sha256(json.dumps(canonical(value),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).digest()


class MemoryResetService:
    def __init__(self,sessions,environment_id,target_fingerprint,*,adapters=None,clock=None):
        if not environment_id or not isinstance(target_fingerprint,bytes) or len(target_fingerprint)!=32:raise ValueError('explicit_target_required')
        self.sessions,self.environment_id,self.target=sessions,environment_id,target_fingerprint
        self.adapters=adapters or {};self.clock=clock or datetime.utcnow
        self._metadata=None

    async def _schema(self,db):
        conn=await db.connection();metadata=MetaData()
        await conn.run_sync(metadata.reflect)
        from backend.database import Base
        for name, table in metadata.tables.items():
            if name not in INFRA and (name not in Base.metadata.tables or set(table.c.keys()) != set(Base.metadata.tables[name].c.keys())):
                raise MemoryControlError(20126,"schema_columns_not_allowlisted")
        unknown=set(metadata.tables)-set(POLICIES)-INFRA
        if unknown:raise MemoryControlError(20126,'schema_table_not_allowlisted')
        schema={name:{'columns':[{'name':c.name,'type':str(c.type),'nullable':c.nullable} for c in table.c],
            'primary_key':[c.name for c in table.primary_key],
            'foreign_keys':sorted([f.parent.name,f.target_fullname,f.ondelete or ''] for f in table.foreign_keys)}
            for name,table in sorted(metadata.tables.items())}
        if any(not s['primary_key'] for n,s in schema.items() if n not in INFRA):raise MemoryControlError(20126,'schema_primary_key_required')
        return metadata,schema

    async def preview(self,*,resources):
        async with self.sessions() as db:
            _,schema=await self._schema(db)
            fence=await db.get(MemoryRuntimeFence,self.environment_id)
            if not fence or fence.target_fingerprint!=self.target:raise MemoryControlError(20127,'reset_target_mismatch')
        if any(set(r)!={'key','adapter','target'} or r['adapter'] not in self.adapters for r in resources):
            raise MemoryControlError(20126,'resource_not_allowlisted')
        if not self.environment_id.startswith('isolated:') and not {'vector-old','vector-new','redis','logs','container','objects'} <= {r['key'].split(':')[0] for r in resources}:
            raise MemoryControlError(20126,'resource_inventory_incomplete')
        if len({r['key'] for r in resources})!=len(resources):raise MemoryControlError(20126,'duplicate_resource')
        value={'protocol_version':'s15-v1','environment_id':self.environment_id,'target_fingerprint':self.target.hex(),
            'schema':schema,'absent_planned_tables':sorted(set(POLICIES)-set(schema)),
            'resources':resources,'mixed_logs_leave_online_query':True}
        return {**value,'manifest_hash':digest(value).hex()}

    def _authorize(self,manifest,auth):
        check={k:v for k,v in manifest.items() if k!='manifest_hash'}
        if (digest(check).hex()!=manifest.get('manifest_hash') or manifest['environment_id']!=self.environment_id
                or manifest['target_fingerprint']!=self.target.hex() or auth.get('environment_id')!=self.environment_id
                or auth.get('manifest_hash')!=manifest['manifest_hash'] or not auth.get('run_id') or not auth.get('operator_id')):
            raise MemoryControlError(20127,'reset_authorization_mismatch')
        seals=auth.get('seals',{})
        if set(seals)!=set(REQUIRED_SEALS) or any(not isinstance(v,str) or len(v)!=64 for v in seals.values()):
            raise MemoryControlError(20126,'reset_seals_incomplete')
        for v in seals.values():bytes.fromhex(v)

    async def _run(self,db,run_id):
        db.info["s15_maintenance"] = run_id
        fence=await db.scalar(select(MemoryRuntimeFence).where(MemoryRuntimeFence.environment_id==self.environment_id).with_for_update())
        run=await db.scalar(select(MemoryResetRun).where(MemoryResetRun.run_id==run_id).with_for_update())
        if not run or not fence or fence.reset_run_id!=run_id or run.target_fingerprint!=self.target or fence.target_fingerprint!=self.target:
            raise MemoryControlError(20127,'reset_identity_changed')
        if run.t0 and fence.target_epoch!=run.target_epoch:raise MemoryControlError(20127,"reset_epoch_changed")
        return run,fence

    @staticmethod
    def _pk(table,row):return {c.name:row[c.name] for c in table.primary_key}

    @staticmethod
    def _where(table,pk):return and_(*(table.c[k]==v for k,v in pk.items()))

    @staticmethod
    def _preserved(name,row):
        policy=POLICIES[name]
        if policy['action']=='delete' or (policy['action']=='selective_delete' and selected(name,row)):return None
        changed=policy['changed'] if selected(name,row) else ()
        return {k:v for k,v in row.items() if k not in changed}

    async def _start(self,manifest,auth):
        # This transaction seals the current epoch first. Failure below leaves
        # maintenance active; it never resumes traffic to an uncertain target.
        async with self.sessions() as db:
            db.info["s15_maintenance"] = auth["run_id"]
            fence=await db.scalar(select(MemoryRuntimeFence).where(MemoryRuntimeFence.environment_id==self.environment_id).with_for_update())
            existing=await db.scalar(select(MemoryResetRun).where(MemoryResetRun.environment_id==self.environment_id,MemoryResetRun.reset_key=='S15'))
            if existing:
                seal=await db.get(MemoryResetItem,(existing.run_id,'phase','seals'))
                if not seal or seal.fixed_scope['proof_digest']!=digest(auth['seals']).hex():raise MemoryControlError(20127,'reset_seals_changed')
                if existing.run_id!=auth['run_id'] or existing.manifest_hash!=bytes.fromhex(manifest['manifest_hash']):
                    raise MemoryControlError(20127,'reset_already_registered')
                return existing.run_id
            if fence is None or fence.target_fingerprint!=self.target:raise MemoryControlError(20127,'reset_target_mismatch')
            run=MemoryResetRun(run_id=auth['run_id'],environment_id=self.environment_id,reset_key='S15',
                manifest_hash=bytes.fromhex(manifest['manifest_hash']),protocol_version='s15-v1',target_epoch=fence.target_epoch+1,
                target_fingerprint=self.target,phase='seal',state='maintenance',operator_id=auth['operator_id'])
            db.add(run);await db.flush()
            fence.mode='maintenance';fence.reset_run_id=run.run_id
            db.add(MemoryResetItem(run_id=run.run_id,kind='phase',resource_key='seals',state='confirmed',
                fixed_scope={'proof_digest':digest(auth['seals']).hex(),'manifest_hash':manifest['manifest_hash']}))
            await db.commit();return run.run_id

    async def _baseline(self,run_id,manifest):
        # Re-read after the complete sealed/drained barrier, never use preview
        # counts as the authoritative preservation baseline.
        async with self.sessions() as db:
            run,fence=await self._run(db,run_id)
            if run.t0:return
            metadata,schema=await self._schema(db)
            if schema!=manifest['schema']:raise MemoryControlError(20127,'schema_changed')
            captured=[]
            for name in ORDER:
                if name not in metadata.tables or name in EVIDENCE:continue
                table=metadata.tables[name]
                rows=(await db.execute(select(table).order_by(*table.primary_key))).mappings().all()
                if any(unsettled(name,r) for r in rows):raise MemoryControlError(20126,'unsettled_'+name)
                if name=='voice_capability_evidence':
                    # Existing evidence may contain provider diagnostics. A
                    # fixed-schema allowlist must be supplied before nonempty
                    # payloads can be certified, not guessed from a zero count.
                    for r in rows:
                        for k,v in r.items():
                            if ('payload' in k or 'detail' in k) and v not in (None,{},[]):raise MemoryControlError(20126,'capability_payload_unverified')
                if name=='voice_followup_job':
                    for r in rows:
                        window=r.get('allowed_window_snapshot')
                        if window and (not isinstance(window,list) or any(not isinstance(w,dict) or set(w)!={'start','end'} for w in window)):
                            raise MemoryControlError(20126,'followup_window_unverified')
                ids=[self._pk(table,r) for r in rows]
                preserved=[self._preserved(name,r) for r in rows];preserved=[r for r in preserved if r is not None]
                item=MemoryResetItem(run_id=run_id,kind='resource',resource_key='sql:'+name,state='pending',
                    fixed_scope={'table':name,'ids':ids,'columns':[c.name for c in table.c]},
                    before_count=len(rows),preserve_digest_before=digest(preserved),cursor={'index':0})
                db.add(item);captured.append([name,item.preserve_digest_before.hex(),len(rows)])
            if not self.environment_id.startswith('isolated:'):
                vectors=[r for r in manifest['resources'] if r['key'].split(':')[0] in {'vector-old','vector-new'}]
                for resource in vectors:
                    target=resource['target'];adapter=self.adapters[resource['adapter']]
                    inventory=getattr(adapter,'inventory',None)
                    if inventory is None:raise MemoryControlError(20126,'vector_inventory_unverified')
                    actual=set(await inventory(target))
                    listed={r['target']['partition'] for r in vectors if r['target']['cluster_fingerprint']==target['cluster_fingerprint'] and r['target']['collection']==target['collection']}
                    if actual!=listed:raise MemoryControlError(20126,'vector_partition_inventory_changed')
            # External scopes also freeze exact key/file/container identities at
            # T0. prepare is read-only and may fail without any cleanup.
            for resource in manifest['resources']:
                adapter=self.adapters[resource['adapter']]
                scope=await adapter.prepare(resource['target'],run_id)
                db.add(MemoryResetItem(run_id=run_id,kind='resource',resource_key=resource['key'],state='pending',
                    fixed_scope={'adapter':resource['adapter'],'target':resource['target'],'scope':scope}))
            identity_table=metadata.tables['memory_identity']
            identities=(await db.execute(select(identity_table).order_by(*identity_table.primary_key))).mappings().all()
            db.add(MemoryResetItem(run_id=run_id,kind='phase',resource_key='catalog-baseline',state='confirmed',
                fixed_scope={'manifest':manifest,'catalog_keys':[[r['id'],digest([r['target_fingerprint'],r['partition_name'],r['doc_id'],r['memory_type'],r['owner_user_id']]).hex()] for r in identities]}))
            run.t0=self.clock();run.baseline_digest=digest(captured);run.phase='sql';run.state='running'
            fence.target_epoch=run.target_epoch;fence.revision+=1
            await db.commit()

    async def _sql(self,run_id,name):
        # One bounded row per transaction with the exact same cursor commit.
        # A lost COMMIT acknowledgement is recovered by reading this cursor.
        while True:
            async with self.sessions() as db:
                run,_=await self._run(db,run_id)
                if run.completed_at:return
                item=await db.get(MemoryResetItem,(run_id,'resource','sql:'+name))
                if item is None or item.state=='confirmed':return
                if self._metadata is None:self._metadata,_=await self._schema(db)
                table=self._metadata.tables[name]
                ids=item.fixed_scope['ids'];index=(item.cursor or {}).get('index',0)
                if index>=len(ids):
                    rows=(await db.execute(select(table).order_by(*table.primary_key))).mappings().all()
                    # No extra row may silently enter a stopped-world baseline.
                    if any(self._pk(table,r) not in ids for r in rows):raise MemoryControlError(20126,'post_t0_write_detected')
                    preserved=[self._preserved(name,r) for r in rows];preserved=[r for r in preserved if r is not None]
                    after=digest(preserved)
                    if after!=item.preserve_digest_before:raise MemoryControlError(20126,'preserved_values_changed')
                    item.preserve_digest_after=after;item.after_count=len(rows);item.state='confirmed';item.result_digest=digest(rows)
                    await db.commit();return
                pk=ids[index];row=(await db.execute(select(table).where(self._where(table,pk)).with_for_update())).mappings().first()
                if row is None:raise MemoryControlError(20126,'fixed_row_missing_before_commit')
                action=POLICIES[name]['action']
                if selected(name,row):
                    if action in {'delete','selective_delete'}:await db.execute(delete(table).where(self._where(table,pk)))
                    elif action=='update':
                        values={k:(null() if v is None else v) for k,v in updates(name,row,run).items()}
                        # Explicit updated_at prevents ORM/Core onupdate drift.
                        if 'updated_at' in row:values['updated_at']=row['updated_at']
                        if values:await db.execute(update(table).where(self._where(table,pk)).values(**values))
                item.cursor={'index':index+1};item.revision+=1
                await db.commit()

    async def _vector_checkpoint(self,run_id,key,binding,kind,value):
        from backend.services.memory_reset_resources import VectorResetAdapter
        if kind not in {'receipt','evidence'}:raise MemoryControlError(20127,'vector_receipt_invalid')
        async def check(db):
            await self._run(db,run_id)
            item=await db.get(MemoryResetItem,(run_id,'resource',key))
            saved=(item.cursor or {}).get('vector_receipt')
            actual={k:v for k,v in saved.items() if k in binding} if isinstance(saved,dict) else None
            if (binding['run_id']!=run_id or binding['resource_key']!=key
                    or not VectorResetAdapter.valid_binding(binding,item.fixed_scope['target'],run_id)
                    or (saved is not None and actual!=binding)):
                raise MemoryControlError(20127,'vector_receipt_identity_changed')
            if kind=='receipt':
                valid=saved is not None and binding['origin']=='registered_dispatch' and VectorResetAdapter.valid_receipt(value)
            else:
                valid=any(VectorResetAdapter.valid_evidence(value,binding,k) for k in ('request_completed','target_retired'))
                receipt=(saved or {}).get('receipt')
                if receipt is not None and value.get('kind')=='request_completed' and value.get('request_id')!=receipt.get('request_id'):
                    valid=False
            if not valid:raise MemoryControlError(20127,'vector_receipt_invalid')
            old=(saved or {}).get(kind)
            if old is not None and old!=value:raise MemoryControlError(20127,'vector_receipt_conflict')
            return item,saved,old
        try:
            async with self.sessions() as db:
                item,saved,old=await check(db)
                if old==value:return
                item.cursor={**(item.cursor or {}),'vector_receipt':{**(saved or binding),kind:value}}
                item.revision+=1
                await db.commit()
        except Exception:
            # COMMIT reply loss is ambiguous. Only an exact durable read of the
            # same first receipt permits continuing; never repeat the deletion.
            async with self.sessions() as db:
                _,_,old=await check(db)
                if old!=value:raise MemoryControlError(20129,'vector_receipt_checkpoint_unknown') from None

    async def _external(self,run_id,key):
        from backend.services.memory_reset_resources import VectorResetAdapter
        async with self.sessions() as db:
            run,_=await self._run(db,run_id)
            item=await db.get(MemoryResetItem,(run_id,'resource',key))
            if item.state=='confirmed':return
            scope=item.fixed_scope;previous=item.state
            adapter=self.adapters[scope['adapter']]
            vector=isinstance(adapter,VectorResetAdapter)
            if vector:
                saved=(item.cursor or {}).get('vector_receipt')
                if saved is None:
                    binding={'protocol':'s15-vector-receipt-v1','run_id':run_id,'resource_key':key,
                        'target_digest':digest(scope['target']).hex(),'revision':item.revision+1 if previous=='pending' else item.revision,
                        'origin':'registered_dispatch' if previous=='pending' else 'legacy_read'}
                else:
                    binding={k:saved.get(k) for k in ('protocol','run_id','resource_key','target_digest','revision','origin')}
                if (not adapter.valid_binding(binding,scope['target'],run_id) or binding['resource_key']!=key
                        or binding['revision']>item.revision+(1 if previous=='pending' else 0)):
                    raise MemoryControlError(20127,'vector_receipt_identity_changed')
                if previous=='pending':
                    if saved is not None:raise MemoryControlError(20127,'vector_dispatch_identity_conflict')
                    item.cursor={**(item.cursor or {}),'vector_receipt':dict(binding)}
                    item.revision+=1
            if previous=='pending':item.state='dispatching';await db.commit()
        kwargs={}
        if vector:
            async def checkpoint(kind,value):await self._vector_checkpoint(run_id,key,binding,kind,value)
            kwargs={'binding':binding,'checkpoint':checkpoint}
        adapter=self.adapters[scope['adapter']]
        if previous=='pending':
            try:result=await adapter.execute(scope['target'],scope['scope'],run_id,**kwargs)
            except Exception:result={'state':'unknown','reason':'external_result_unknown'}
        else:
            # Never resend a write after timeout or process restart.
            if vector:kwargs.update(receipt=(saved or {}).get('receipt'),evidence=(saved or {}).get('evidence'))
            try:result=await adapter.reconcile(scope['target'],scope['scope'],run_id,**kwargs)
            except Exception:result={'state':'unknown','reason':'external_evidence_unavailable'}
        async with self.sessions() as db:
            run,_=await self._run(db,run_id);item=await db.get(MemoryResetItem,(run_id,'resource',key))
            if vector:
                if item.state=='confirmed':return  # A late unknown cannot undo a confirmed read.
                current=(item.cursor or {}).get('vector_receipt')
                if current is not None and any(current.get(k)!=v for k,v in binding.items()):
                    raise MemoryControlError(20127,'vector_receipt_identity_changed')
                if result.get('state')=='confirmed':
                    receipt=(current or {}).get('receipt');proof=(current or {}).get('evidence')
                    completed=(binding['origin']=='registered_dispatch' and adapter.valid_receipt(receipt) and receipt['outcome']=='request_completed')
                    completed=completed or (proof is not None and adapter.valid_evidence(proof,binding,'request_completed'))
                    retired=proof is not None and adapter.valid_evidence(proof,binding,'target_retired')
                    match=any(p is not None and digest(p).hex()==result.get('proof_digest') for p in (receipt,proof))
                    if not match or not ((completed and type(result.get('count')) is int and result['count']==0) or (retired and result.get('retired') is True)):
                        raise MemoryControlError(20127,'vector_completion_unverified')
                # Only fixed classifications/counts, no supplier message/body.
                postcheck={'state':result.get('state') if result.get('state') in {'confirmed','unknown'} else 'unknown'}
                if type(result.get('count')) is int and 0<=result['count']<2**64:postcheck['count']=result['count']
                if current is not None:item.cursor={**item.cursor,'vector_receipt':{**current,'postcheck':postcheck}}
            item.state='confirmed' if result.get('state')=='confirmed' else 'unknown'
            item.error_code=None if item.state=='confirmed' else 'external_result_unknown'
            item.result_digest=digest(result)
            if item.state=='confirmed' and type(result.get('count')) is int:item.after_count=result['count']
            item.revision+=1
            run.state='running' if item.state=='confirmed' else 'unknown';await db.commit()
        if item.state!='confirmed':raise MemoryControlError(20129,'external_result_unknown')

    async def _verify_sql(self,db,run_id):
        metadata,_=await self._schema(db)
        items=(await db.scalars(select(MemoryResetItem).where(MemoryResetItem.run_id==run_id,MemoryResetItem.kind=='resource'))).all()
        for item in items:
            if not item.resource_key.startswith('sql:'):continue
            table=metadata.tables[item.fixed_scope['table']]
            rows=(await db.execute(select(table).order_by(*table.primary_key))).mappings().all()
            if item.state!='confirmed' or digest(rows)!=item.result_digest:
                raise MemoryControlError(20126,'post_t0_write_detected')

    async def execute(self,manifest,authorization=None):
        if authorization is None:return {'dry_run':True,'manifest':manifest}
        self._authorize(manifest,authorization)
        run_id=await self._start(manifest,authorization)
        state=await self.read(run_id)
        if state['state'] in {'completed','opened'}:return state
        from backend.services.memory_reset_drain import MemoryResetDrainer
        await MemoryResetDrainer(self).terminate_unsent(run_id)
        await self._baseline(run_id,manifest)
        for name in ORDER:
            if name not in EVIDENCE:await self._sql(run_id,name)
        for resource in manifest['resources']:await self._external(run_id,resource['key'])
        async with self.sessions() as db:
            run,_=await self._run(db,run_id)
            items=(await db.scalars(select(MemoryResetItem).where(MemoryResetItem.run_id==run_id))).all()
            if any(i.state!='confirmed' for i in items):raise MemoryControlError(20126,'reset_resources_unverified')
            await self._verify_sql(db,run_id)
            run.state='completed';run.phase='completed';run.completed_at=self.clock();run.revision+=1
            await db.commit()
        # Ambiguous completion COMMIT propagates; next invocation first reads
        # this same immutable run and never repeats a completed SQL/remote stage.
        return await self.read(run_id)

    async def open(self,run_id,authorization):
        async with self.sessions() as db:
            run,fence=await self._run(db,run_id)
            if (authorization.get('run_id')!=run_id or authorization.get('manifest_hash')!=run.manifest_hash.hex()
                    or authorization.get('environment_id')!=self.environment_id):raise MemoryControlError(20127,'reset_authorization_mismatch')
            if run.state=='opened':return await self.read(run_id)
            if run.state!='completed' or run.completed_at is None:raise MemoryControlError(20126,'reset_not_completed')
            await self._verify_sql(db,run_id)
            run.state='opened';run.opened_at=self.clock();run.revision+=1;fence.mode='active';fence.revision+=1
            await db.commit()
        return await self.read(run_id)

    async def read(self,run_id):
        async with self.sessions() as db:
            run=await db.get(MemoryResetRun,run_id)
            return {k:getattr(run,k) for k in ('run_id','environment_id','phase','state','target_epoch','completed_at','opened_at')}

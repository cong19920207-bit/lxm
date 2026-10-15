"""Admin source CRUD on a frozen active target and owned durable receipts."""
import hashlib
import hmac
import json
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy import select
from backend.models.memory_control import MemoryIdentity, MemoryOperation, MemoryIndexTask
from backend.services.memory_index_status import maintenance_detail
from backend.services.memory_create_verifier import verify_create_absence
from backend.services import memory_business_writer
from backend.services.memory_mutation_service import MutationTarget, MutationError
from backend.constants import (ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY, ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,
    ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED)
from backend.utils.character_knowledge_validate import build_content, build_doc_id, parse_key_from_content


def validate_request_id(value):
    if value is not None:
        try:
            parsed=UUID(value)
            if str(parsed)!=value or parsed.version!=7:raise ValueError()
        except (ValueError,TypeError,AttributeError):
            raise HTTPException(422,detail='Idempotency-Key 须为规范小写 UUIDv7') from None
    return value


def validate_write_header(request: Request):
    validate_request_id(request.headers.get('Idempotency-Key'))


def request_digest(kind,mt,owner,doc_id,key,value):
    return hashlib.sha256(json.dumps([kind,mt,owner,doc_id,key,value],ensure_ascii=False,separators=(',',':')).encode()).digest()


def project(receipt,kind=None):
    source={'confirmed':'succeeded','superseded':'failed'}.get(receipt['source_result'],receipt['source_result'])
    index=receipt['index_result']
    if index=='not_required':index='ready' if source=='succeeded' and (kind or receipt.get('operation_kind'))=='delete' else 'not_executed'
    if index=='superseded':index='not_executed'
    if index=='manual':index='unknown'
    result={'operation_id':receipt['operation_id'],'internal_operation_id':receipt['internal_operation_id'],
        'source_state':source,'index_state':index,'generation':str(receipt['generation']) if receipt['generation'] is not None else None,
        'identity_id':str(receipt['identity_id']) if receipt['identity_id'] is not None else None,
        'result_revision':str(receipt['revision']) if receipt['revision'] is not None else None,'maintenance_task_id':receipt['task_id'],
        'receipt_state':receipt['receipt_state'],'reason':receipt.get('reason'), 'observed_at':receipt['observed_at']}
    if receipt['index_result']=='manual':result['maintenance_state']='manual_required'
    if source=='succeeded' and index!='ready' and not result['reason']:result['reason']='index_repair_pending'
    if receipt['source_result']=='superseded':result['reason']='operation_superseded'
    return result


def response(receipt,data,kind):
    result=project(receipt,kind);data={**data,'write_result':result}
    if result['source_state']=='succeeded':return {'data':data}
    if result['source_state'] in {'unknown','pending'}:return {'error_code':20122,'message':'结果待核实','data':data}
    return {'error_code':ADMIN_ERR_CHARACTER_KNOWLEDGE_VECTOR_WRITE_FAILED,'message':'源写入失败','data':data}


async def frozen_writer():
    return await memory_business_writer.get_memory_writer()


async def active_rows(mt,owner,top_k,*,writer=None):
    writer=writer or await frozen_writer()
    from backend.utils.dashvector_client import build_filter
    from backend.services.memory_hybrid_retrieval import CandidateValidator
    filter_str=build_filter(mt,user_id=owner or None,candidate_keys=[])
    # Every visible source requires a matching durable identity below. A scope
    # with no identities is therefore empty without interpreting a vendor read
    # or changing an unknown operation. Include ALL states: even an unresolved
    # or deleted identity must keep the existing remote-read verification path.
    async with writer.mutations._session() as db:
        scope=select(MemoryIdentity.id).where(
            MemoryIdentity.target_fingerprint==bytes.fromhex(writer.config.target_fingerprint),
            MemoryIdentity.partition_name==writer.partition, MemoryIdentity.memory_type==mt)
        if owner:scope=scope.where(MemoryIdentity.owner_user_id==owner)
        if await db.scalar(scope.limit(1)) is None:return []
    # Unversioned, SQL-confirmed initial baselines do not have mr_deleted.
    # Source eligibility is checked after retrieval; tombstones may occupy slots.
    result=await writer.mutations.remote.query_dense(writer.partition,[1.0]+[0.0]*1023,top_k=top_k,filter=filter_str)
    if result.status!='confirmed':raise MutationError(20129,'memory_list_unreadable')
    rows=[]
    routes={'character_global':'cg','character_knowledge':'ck','user':'user','character_private':'cp'}
    async with writer.mutations._session() as db:
        documents = result.documents
        identities = list((await db.scalars(select(MemoryIdentity).where(
            MemoryIdentity.target_fingerprint==bytes.fromhex(writer.config.target_fingerprint),
            MemoryIdentity.partition_name==writer.partition,
            MemoryIdentity.doc_id.in_([row.get('id') for row in documents])))).all()) if documents else []
        by_doc = {identity.doc_id: identity for identity in identities}
        tasks = list((await db.scalars(select(MemoryIndexTask).join(
            MemoryIdentity, MemoryIdentity.id==MemoryIndexTask.identity_id).where(
            MemoryIndexTask.identity_id.in_([identity.id for identity in identities if identity.index_state != 'ready']),
            MemoryIndexTask.generation==MemoryIdentity.generation,
            MemoryIndexTask.body_hash==MemoryIdentity.body_hash,
            MemoryIndexTask.encoder_version==MemoryIdentity.encoder_version,
            MemoryIndexTask.operation_id==MemoryIdentity.current_operation_id,
            MemoryIndexTask.state!='superseded'))).all()) if identities else []
        by_identity = {task.identity_id: task for task in tasks}
        for row in result.documents:
            doc_id=row.get('id')
            identity=by_doc.get(doc_id)
            if identity is None or identity.memory_type!=mt or (owner and identity.owner_user_id!=owner):continue
            ops={}
            for oid in {identity.current_operation_id,identity.inflight_operation_id}-{None}:
                operation=await db.get(MemoryOperation,oid)
                if operation:ops[oid]=operation
            # Reuse M4's source truth: owner/body/version proof, strict initial
            # baseline exception, and same-generation confirmed index intents.
            reason,value,key=CandidateValidator._check({**row,'score':row.get('score',0.0)},identity,routes[mt],
                identity.owner_user_id,writer.config,'dense',ops)
            if reason:continue
            rows.append({**row,'content':row['fields']['content'],'generation':str(identity.generation),
                'index_maintenance':maintenance_detail(identity, by_identity.get(identity.id)),
                'index_state':{'not_ready':'pending','repairing':'pending','manual':'unknown'}.get(identity.index_state,identity.index_state),'legacy_read_only':key is None})
    return rows


async def source_write(*,kind,memory_type,user_id=0,key=None,value=None,doc_id=None,actor_id=None,client_request_id=None):
    validate_request_id(client_request_id)
    if type(actor_id) is not int or actor_id<=0:raise MutationError(20120,'memory_actor_invalid')
    key=key.strip() if key is not None else None;value=value.strip() if value is not None else None
    if doc_id is None:doc_id=build_doc_id(memory_type,key,user_id)
    digest=request_digest(kind,memory_type,user_id,doc_id,key,value)
    writer=await frozen_writer();mutations=writer.mutations
    if client_request_id:
        prior=await mutations._read_operation(client_request_id,'admin',actor_id)
        if prior:
            if not hmac.compare_digest(prior.request_hash,digest):raise MutationError(20121,'operation_identity_conflict')
            receipt=mutations._receipt(prior)
            if receipt['receipt_state'] in {'expired','cleared'}:
                return {'error_code':20123,'message':'operation_receipt_expired','data':{'write_result':project(receipt,kind)}}
            if receipt['source_result'] in {'pending','unknown'}:receipt=await mutations.reconcile(prior.operation_id,actor_type='admin',actor_id=actor_id)
            receipt = {**receipt, 'operation_id': client_request_id}
            saved_key=(prior.receipt_summary or {}).get('stable_key',key)
            data={'doc_id':doc_id} if kind=='delete' else {'doc_id':doc_id,'type':memory_type,'user_id':user_id,
                'key':saved_key,'value':value,'content':build_content(saved_key,value)}
            return response(receipt,data,kind)
    if client_request_id:
        from datetime import timezone
        age=int(mutations._now().replace(tzinfo=timezone.utc).timestamp()*1000)-(UUID(client_request_id).int >> 80)
        if age > 120000 or age < -30000:raise MutationError(20123,'operation_id_outside_window')
    target=MutationTarget(writer.partition,doc_id,memory_type,user_id,writer.config.target_epoch,bytes.fromhex(writer.config.target_fingerprint))
    if kind!='create':
        fetched=await mutations.remote.fetch(writer.partition,doc_id)
        if fetched.status=='unknown':raise MutationError(20129,'memory_source_unreadable')
        if fetched.status!='found' or fetched.document['fields'].get('mr_deleted'):
            return {'error_code':ADMIN_ERR_CHARACTER_KNOWLEDGE_NOT_FOUND,'message':'条目不存在'}
        fields=fetched.document['fields']
        if fields.get('type')!=memory_type or fields.get('user_id')!=user_id:raise MutationError(20120,'memory_owner_mismatch')
        key=fields.get('stable_key') or fields.get('key') or parse_key_from_content(fields.get('content',''))
    if kind=='create':
        fetched=await mutations.remote.fetch(writer.partition,doc_id)
        if fetched.status=='unknown':
            # Only a first create may obtain independent absence evidence. The
            # original operation replay/reconcile path above never comes here.
            if fetched.reason!='read_output_missing' or not await verify_create_absence(
                    mutations.remote.config, writer.partition, doc_id):
                raise MutationError(20129,'memory_source_unreadable')
        if fetched.status=='found' and not fetched.document['fields'].get('mr_deleted'):
            return {'error_code':ADMIN_ERR_CHARACTER_KNOWLEDGE_DUPLICATE_KEY,'message':'该类型下 key 已存在，请直接编辑'}
    content='' if kind=='delete' else build_content(key,value)
    vector=[1.0]+[0.0]*1023 if kind=='delete' else await writer.embed(value)
    fields={'key':key or '', 'stable_key':key or '', 'content':content,'type':memory_type,'user_id':user_id,'last_write_source':'admin'}
    if key:
        fields.update(key_l1=key.split('-')[0],key_l2='-'.join(key.split('-')[:2]))
    receipt=await mutations.prepare(target=target,kind=kind,document={'id':doc_id,'vector':vector,'fields':fields},
        actor_type='admin',actor_id=actor_id,client_request_id=client_request_id,source_entry='admin:'+memory_type,
        request_digest=digest,receipt_extra={'stable_key':key})
    if receipt['dispatch_state']=='prepared' and receipt['source_result']=='pending' and receipt['receipt_state']=='full':
        receipt=await mutations.dispatch(receipt['internal_operation_id'],actor_type='admin',actor_id=actor_id)
    if client_request_id:
        receipt = {**receipt, 'operation_id': client_request_id}
    data={'doc_id':doc_id} if kind=='delete' else {'doc_id':doc_id,'type':memory_type,'user_id':user_id,'key':key,'value':value,'content':content}
    return response(receipt,data,kind)


async def read_batch(writer, parent, actor_id, *, reconcile=True):
    mutations = writer.mutations
    if (parent.receipt_summary or {}).get('reason')=='cleared':
        summary=parent.receipt_summary
        return {'deleted_count':summary.get('source_counts',{}).get('succeeded',0),
            'failed_doc_ids':[],'items':summary.get('items',[]),
            'source_counts':summary.get('source_counts',{}),'index_counts':summary.get('index_counts',{}),
            'write_result':project(mutations._receipt(parent),'batch')}
    # Readback may advance a child, but never sends another source write. The
    # aggregation below reloads under locks so a late observer cannot rewind it.
    for original in (parent.receipt_summary or {}).get('items', []):
        child_id = original.get('child_operation_id')
        if child_id:
            receipt = await mutations.get_receipt(child_id, actor_type='admin', actor_id=actor_id)
            if receipt and reconcile and receipt['source_result'] in {'pending', 'unknown'}:
                await mutations.reconcile(child_id, actor_type='admin', actor_id=actor_id)
    async with mutations._session() as db:
        op = await mutations._get(db, parent.operation_id, 'admin', actor_id, lock=True)
        if op is None:
            raise MutationError(20129, 'batch_receipt_unreadable')
        items = []
        counts = {'succeeded': 0, 'failed': 0, 'unknown': 0, 'pending': 0}
        index_counts = {'ready': 0, 'pending': 0, 'failed': 0, 'unknown': 0, 'not_executed': 0}
        for original in (op.receipt_summary or {}).get('items', []):
            item = {k: v for k, v in original.items() if k != 'child_operation_id'}
            child_id = original.get('child_operation_id')
            if child_id:
                child = await mutations._get(db, child_id, 'admin', actor_id, lock=True)
                if child and child.parent_operation_id == op.operation_id:
                    item['write_result'] = project(mutations._receipt(child), 'delete')
                    item.update(source_state=item['write_result']['source_state'], index_state=item['write_result']['index_state'])
                else:
                    item.update(source_state='unknown', index_state='unknown', reason='child_receipt_unreadable')
            counts[item['source_state']] += 1
            index_counts[item['index_state']] += 1
            items.append(item)
        state = ('unknown' if counts['unknown'] else 'pending' if counts['pending'] else
                 'confirmed' if counts['succeeded'] else 'failed')
        index = ('pending' if index_counts['pending'] else 'unknown' if index_counts['unknown'] else
                 'failed' if index_counts['failed'] else 'ready')
        if (op.source_result != state or op.index_result != index
                or (op.receipt_summary or {}).get('source_counts') != counts):
            op.source_result, op.index_result = state, index
            op.dispatch_state = 'unknown' if state == 'unknown' else 'prepared' if state == 'pending' else 'confirmed'
            op.receipt_summary = {**op.receipt_summary, 'source_counts': counts, 'index_counts': index_counts}
            if state in {'confirmed', 'failed'}:
                # Once terminal, later index observations do not renew retention.
                if op.terminal_at is None:
                    mutations._terminal(op)
                else:
                    op.updated_at, op.revision = mutations._now(), op.revision + 1
            else:
                op.updated_at, op.revision = mutations._now(), op.revision + 1
            await db.commit()
        receipt = mutations._receipt(op)
    return {'deleted_count': counts['succeeded'],
            'failed_doc_ids': [item['requested_doc_id'] for item in items if item['source_state'] != 'succeeded'],
            'items': items, 'source_counts': counts, 'index_counts': index_counts, 'write_result': project(receipt, 'batch')}


async def batch_delete(doc_ids,actor_id,client_request_id=None):
    validate_request_id(client_request_id)
    from backend.utils.character_knowledge_validate import parse_doc_id
    writer=await frozen_writer();doc_ids=list(dict.fromkeys(doc_ids));targets=[]
    for doc_id in doc_ids:
        parsed=parse_doc_id(doc_id)
        if not parsed or parsed[0]!='user' or not parsed[1].isdigit() or int(parsed[1])<1:targets.append(None)
        else:targets.append(MutationTarget(writer.partition,doc_id,'user',int(parsed[1]),writer.config.target_epoch,bytes.fromhex(writer.config.target_fingerprint)))
    try:
        parent,is_new=await writer.mutations.prepare_batch_delete(targets=targets,requested_doc_ids=doc_ids,
            actor_id=actor_id,target_epoch=writer.config.target_epoch,
            target_fingerprint=bytes.fromhex(writer.config.target_fingerprint),client_request_id=client_request_id)
    except MutationError as exc:
        if hasattr(exc,'receipt'):
            return {'error_code':20122,'data':{'write_result':project(exc.receipt,'batch')}}
        raise
    if writer.mutations._receipt(parent)['receipt_state'] in {'expired','cleared'}:
        return {'error_code':20123,'data':{'write_result':project(writer.mutations._receipt(parent),'batch')}}
    if is_new:
        for item in parent.receipt_summary['items']:
            if item.get('child_operation_id'):
                try:
                    await writer.mutations.dispatch(item['child_operation_id'],actor_type='admin',actor_id=actor_id)
                except MutationError:
                    # A later fenced child cannot erase earlier confirmed results.
                    pass
    # First response keeps the initial unknown; later GET/replay reads exact tags.
    data=await read_batch(writer,parent,actor_id,reconcile=not is_new)
    return {'data':data,'error_code':20122 if data['source_counts']['unknown'] or data['source_counts']['pending'] else None}

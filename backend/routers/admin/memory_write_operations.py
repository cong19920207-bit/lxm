"""Owned source write receipts; does not grant global maintenance permissions."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from backend.schemas.common import ApiResponse
from backend.models.admin_user import AdminUser
from backend.models.memory_control import MemoryIdentity
from backend.utils.admin_auth import get_current_admin
from backend.services.admin_memory_write_service import frozen_writer, project
from backend.services.memory_mutation_service import MutationError

router=APIRouter()

@router.get('/memory-write-operations/{operation_id}')
async def get_memory_write_operation(operation_id: str, admin_user: AdminUser=Depends(get_current_admin)):
    try:
        identity=UUID(operation_id)
        if str(identity)!=operation_id or identity.version not in {4,7}:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise HTTPException(422,detail='operation_id 须为规范小写 UUIDv4 或 UUIDv7') from None
    try:
        writer=await frozen_writer();mutations=writer.mutations
        op=await mutations._read_operation(operation_id,'admin',admin_user.id)
        if op is None:return ApiResponse.fail(20125,message='operation_not_found',data={'operation_id':operation_id,'source_state':'unknown'})
        if op.operation_kind not in {'create','update','delete','batch'}:
            return ApiResponse.fail(20125,message='operation_not_found')
        mt=(op.receipt_summary or {}).get('memory_type')
        roles={'super_admin','ai_trainer','observer'} if mt in {'character_global','character_knowledge'} or op.operation_kind=='batch' else {'super_admin','ai_trainer','ops_admin','observer'}
        if admin_user.role not in roles or (mt not in {'character_global','character_knowledge','user','character_private'} and op.operation_kind!='batch'):
            raise HTTPException(403,detail='无当前来源读取权限')
        if mutations._receipt(op)['receipt_state']=='cleared':
            if op.operation_kind=='batch':
                from backend.services.admin_memory_write_service import read_batch
                data=await read_batch(writer,op,admin_user.id,reconcile=False)
            else:data={'write_result':project(mutations._receipt(op),op.operation_kind)}
            return ApiResponse.fail(20123,message='operation_receipt_cleared',data=data)
        if mutations._receipt(op)['receipt_state']=='expired':
            return ApiResponse.fail(20123,message='operation_receipt_expired',data={'write_result':project(mutations._receipt(op),op.operation_kind)})
        if op.operation_kind=='batch':
            from backend.services.admin_memory_write_service import read_batch
            return ApiResponse.ok(data=await read_batch(writer,op,admin_user.id))
        receipt=mutations._receipt(op)
        async with mutations._session() as db:
            current=await db.get(MemoryIdentity,op.identity_id)
            if (current is None or current.memory_type!=mt
                    or current.owner_user_id!=(op.receipt_summary or {}).get('owner_user_id')
                    or current.doc_id!=(op.receipt_summary or {}).get('doc_id')):
                return ApiResponse.fail(20129,message='operation_scope_unreadable')
        if receipt['source_result'] in {'pending','unknown'}:
            receipt=await mutations.reconcile(op.operation_id,actor_type='admin',actor_id=admin_user.id)
        receipt = {**receipt, 'operation_id': op.client_request_id or op.operation_id}
        async with mutations._session() as db:
            current=await db.get(MemoryIdentity,op.identity_id)
        result=project(receipt,op.operation_kind)
        result.update(currentness='current' if current.generation==op.generation else 'superseded',
            current_generation=str(current.generation),current_source_state=current.source_state,
            current_index_state=current.index_state)
        return ApiResponse.ok(data={'write_result':result})
    except MutationError as exc:return ApiResponse.fail(exc.code,message=exc.reason)

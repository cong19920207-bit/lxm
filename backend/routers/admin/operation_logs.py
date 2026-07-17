# -*- coding: utf-8 -*-
# 操作日志查看与导出接口

import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants import ADMIN_ERR_OPERATION_LOG_NOT_FOUND
from backend.database import get_db
from backend.models.admin_operation_log import AdminOperationLog
from backend.models.admin_user import AdminUser
from backend.schemas.common import ApiResponse
from backend.utils.admin_auth import (
    deny_observer_export,
    get_current_admin,
    require_role,
)
from backend.utils.credential_redaction import REDACTED, redact_credentials

logger = logging.getLogger(__name__)

router = APIRouter()

# ai_trainer 无操作日志查看权限；observer 只读且禁止导出。
_LOG_READ_ROLES = ("super_admin", "ops_admin", "tech_ops", "observer")
_LOG_EXPORT_ROLES = ("super_admin", "ops_admin", "tech_ops")


def _redact_log_value(value):
    if value is None:
        return None
    try:
        return redact_credentials(value)
    except Exception:
        logger.exception("操作日志读取脱敏失败，已按失败关闭处理")
        return REDACTED


@router.get(
    "/operation-logs",
    dependencies=[require_role(*_LOG_READ_ROLES)],
)
async def list_operation_logs(
    admin_username: str | None = Query(None, description="管理员用户名（模糊搜索）"),
    module: str | None = Query(None, description="操作模块"),
    action: str | None = Query(None, description="操作类型"),
    start_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """分页查询操作日志"""
    conditions = []

    if admin_username:
        conditions.append(AdminOperationLog.admin_username.like(f"%{admin_username}%"))
    if module:
        conditions.append(AdminOperationLog.module == module)
    if action:
        conditions.append(AdminOperationLog.action == action)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            conditions.append(AdminOperationLog.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            conditions.append(AdminOperationLog.created_at <= end_dt)
        except ValueError:
            pass

    # 查询总数
    count_stmt = select(func.count(AdminOperationLog.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query_stmt = (
        select(AdminOperationLog)
        .order_by(AdminOperationLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if conditions:
        query_stmt = query_stmt.where(*conditions)
    result = await db.execute(query_stmt)
    logs = result.scalars().all()

    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": [
            {
                "id": log.id,
                "admin_user_id": log.admin_user_id,
                "admin_username": log.admin_username,
                "module": log.module,
                "action": log.action,
                "target_description": _redact_log_value(log.target_description),
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
    return ApiResponse.ok(data=data)


@router.get(
    "/operation-logs/{log_id}",
    dependencies=[require_role(*_LOG_READ_ROLES)],
)
async def get_operation_log_detail(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """获取单条操作日志详情"""
    stmt = select(AdminOperationLog).where(AdminOperationLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalars().first()

    if log is None:
        return ApiResponse.fail(ADMIN_ERR_OPERATION_LOG_NOT_FOUND)

    data = {
        "id": log.id,
        "admin_user_id": log.admin_user_id,
        "admin_username": log.admin_username,
        "module": log.module,
        "action": log.action,
        "target_description": _redact_log_value(log.target_description),
        "before_value": _redact_log_value(log.before_value),
        "after_value": _redact_log_value(log.after_value),
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
    return ApiResponse.ok(data=data)


@router.post(
    "/operation-logs/export",
    dependencies=[
        Depends(deny_observer_export),
        require_role(*_LOG_EXPORT_ROLES),
    ],
)
async def export_operation_logs(
    admin_username: str | None = Query(None),
    module: str | None = Query(None),
    action: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin),
):
    """导出操作日志为Excel文件"""
    from openpyxl import Workbook

    conditions = []

    if admin_username:
        conditions.append(AdminOperationLog.admin_username.like(f"%{admin_username}%"))
    if module:
        conditions.append(AdminOperationLog.module == module)
    if action:
        conditions.append(AdminOperationLog.action == action)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            conditions.append(AdminOperationLog.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            conditions.append(AdminOperationLog.created_at <= end_dt)
        except ValueError:
            pass

    query_stmt = (
        select(AdminOperationLog)
        .order_by(AdminOperationLog.created_at.desc())
    )
    if conditions:
        query_stmt = query_stmt.where(*conditions)
    result = await db.execute(query_stmt)
    logs = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "操作日志"

    headers = ["ID", "操作人", "模块", "操作类型", "操作描述", "修改前", "修改后", "IP地址", "操作时间"]
    ws.append(headers)

    for log in logs:
        ws.append([
            log.id,
            log.admin_username,
            log.module,
            log.action,
            _redact_log_value(log.target_description),
            _redact_log_value(log.before_value) or "",
            _redact_log_value(log.after_value) or "",
            log.ip_address or "",
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
        ])

    # 自动调整列宽
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value:
                cell_len = len(str(cell.value))
                if cell_len > max_length:
                    max_length = cell_len
        ws.column_dimensions[col_letter].width = min(max_length + 4, 60)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=operation_logs.xlsx",
        },
    )

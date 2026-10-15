"""Bounded, credential-free admin query utilities."""
from datetime import datetime
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select,func
from backend.schemas.common import ApiResponse
from backend.services.admin_date_filter import parse_admin_date_range,append_created_at_range

READ_ROLES={'super_admin','ai_trainer','observer'}
WRITE_ROLES={'super_admin','ai_trainer'}

class AdminMemoryError(Exception):
    def __init__(self,code,reason,data=None):
        self.code,self.reason,self.data=code,reason,data
        super().__init__(reason)


def uuid_value(value,versions=(4,7)):
    try:
        parsed=UUID(value)
        if str(parsed)!=value or parsed.version not in versions:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise HTTPException(422,detail='invalid_uuid') from None
    return value


def iso(value):return value.isoformat(timespec='microseconds')+'Z' if value else None


def page_data(items,total,page,page_size):
    return {'list':items,'total':total,'page':page,'page_size':page_size}


def dates(filters,column,start,end):
    lo,hi,error=parse_admin_date_range(start,end)
    if error:raise AdminMemoryError(20120,'date_range_invalid')
    append_created_at_range(filters,column,lo,hi)


async def sql_page(db,model,filters,order,page,page_size):
    total=await db.scalar(select(func.count()).select_from(model).where(*filters))
    rows=(await db.scalars(select(model).where(*filters).order_by(*order).offset((page-1)*page_size).limit(page_size))).all()
    return rows,total


def response_error(exc):
    return ApiResponse.fail(exc.code,message=exc.reason,data=exc.data)

# -*- coding: utf-8 -*-
# 通用 Pydantic 模型：统一 API 响应格式等

from typing import Any

from pydantic import BaseModel

from backend.constants import ADMIN_ERROR_MESSAGES, ERROR_MESSAGES, SUCCESS


class ApiResponse(BaseModel):
    """统一 API 响应格式：{"code": 0, "data": {}, "message": "success"}"""
    code: int = SUCCESS
    data: Any = None
    message: str = "success"

    @classmethod
    def ok(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code=SUCCESS, data=data, message=message)

    @classmethod
    def fail(cls, code: int, message: str | None = None, data: Any = None) -> "ApiResponse":
        # H5 错误码与后台 ADMIN_ERR_* 共用信封；message 优先，否则按错误码表解析
        msg = message or ERROR_MESSAGES.get(code) or ADMIN_ERROR_MESSAGES.get(code, "未知错误")
        return cls(code=code, data=data, message=msg)

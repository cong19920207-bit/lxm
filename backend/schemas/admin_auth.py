# -*- coding: utf-8 -*-
# 后台认证与账号管理 Pydantic 模型

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    """后台登录请求"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class AdminLoginResponse(BaseModel):
    """后台登录响应数据"""
    token: str
    username: str
    role: str
    need_change_password: bool = False


class AdminChangePasswordRequest(BaseModel):
    """后台修改密码请求"""
    old_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=1, max_length=100)
    confirm_password: str = Field(..., min_length=1, max_length=100)


class AdminCreateAccountRequest(BaseModel):
    """创建管理员账号请求"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern=r"^(super_admin|ops_admin|ai_trainer|tech_ops|observer)$")
    remark: str | None = Field(None, max_length=200)


class AdminUpdateAccountRequest(BaseModel):
    """编辑管理员账号请求"""
    role: str | None = Field(None, pattern=r"^(super_admin|ops_admin|ai_trainer|tech_ops|observer)$")
    remark: str | None = Field(None, max_length=200)

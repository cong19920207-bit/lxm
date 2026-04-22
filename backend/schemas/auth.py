# -*- coding: utf-8 -*-
# 认证模块的 Pydantic 请求/响应模型

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=6, max_length=20, description="用户名：6-20位字母数字")
    password: str = Field(..., min_length=8, max_length=20, description="密码：8-20位，含字母和数字")
    confirm_password: str = Field(..., min_length=8, max_length=20, description="确认密码")


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    remember_me: bool = Field(False, description="记住我（Token有效期30天）")


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    username: str = Field(..., description="用户名")
    new_password: str = Field(..., min_length=8, max_length=20, description="新密码：8-20位，含字母和数字")
    confirm_password: str = Field(..., description="确认密码")


class TokenData(BaseModel):
    """Token 响应数据"""
    token: str
    user_id: int
    username: str

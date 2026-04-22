# -*- coding: utf-8 -*-
# 读取 .env 环境变量，提供统一配置访问

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# 加载 .env 文件（项目根目录）
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def get_mysql_url() -> str:
    """构建 MySQL 异步连接 URL（asyncmy 驱动）"""
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "lxm")
    password = os.getenv("MYSQL_PASSWORD", "lxm123456")
    database = os.getenv("MYSQL_DATABASE", "lxm")
    return f"mysql+asyncmy://{user}:{password}@{host}:{port}/{database}"


def get_mysql_sync_migration_url() -> str:
    """构建 MySQL 同步连接 URL（PyMySQL），供 Alembic 等离线迁移工具使用。"""
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "lxm")
    password = os.getenv("MYSQL_PASSWORD", "lxm123456")
    database = os.getenv("MYSQL_DATABASE", "lxm")
    u = quote_plus(user)
    p = quote_plus(password)
    return f"mysql+pymysql://{u}:{p}@{host}:{port}/{database}?charset=utf8mb4"


def get_redis_url() -> str:
    """构建 Redis 连接 URL"""
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD", "")
    db = os.getenv("REDIS_DB", "0")
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def get_jwt_secret() -> str:
    """获取 JWT 签名密钥"""
    return os.getenv("JWT_SECRET", "lxm-default-jwt-secret-change-in-production")


def get_jwt_algorithm() -> str:
    """获取 JWT 签名算法"""
    return os.getenv("JWT_ALGORITHM", "HS256")


def get_admin_jwt_secret() -> str:
    """获取后台管理员 JWT 签名密钥（与用户端独立）"""
    return os.getenv("ADMIN_JWT_SECRET", "admin_secret_change_me")


# ============ 火山引擎（豆包 LLM） ============

def get_volc_api_key() -> str:
    """获取火山引擎 API Key"""
    return os.getenv("VOLC_ACCESS_KEY", "")


def get_volc_secret_key() -> str:
    """获取火山引擎 Secret Key"""
    return os.getenv("VOLC_SECRET_KEY", "")


def get_volc_endpoint() -> str:
    """获取火山引擎 API Endpoint"""
    return os.getenv("VOLC_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3")


def get_volc_model() -> str:
    """获取火山引擎模型名称"""
    return os.getenv("VOLC_MODEL", "doubao-seed-1-8-251228")


def get_llm_timeout_seconds() -> float:
    """通用 LLM HTTP 超时（秒），非 H5 对话主链路使用，默认 15。"""
    return float(os.getenv("LLM_TIMEOUT", "15"))


def get_llm_timeout_chat_seconds() -> float:
    """H5 对话主链路（含同链路的 send/resend 打包调度）专用 LLM 超时（秒），默认 45。"""
    return float(os.getenv("LLM_TIMEOUT_CHAT", "45"))


def get_chat_debounce_ms() -> int:
    """新 user 入队后自动调度合并的防抖间隔（毫秒），默认 500。多实例下与 Redis 防抖配合。"""
    return int(os.getenv("CHAT_DEBOUNCE_MS", "500"))


# ============ 阿里云（Embedding + DashVector） ============

def get_aliyun_api_key() -> str:
    """获取阿里云 API Key（用于 Embedding）"""
    return os.getenv("ALIYUN_ACCESS_KEY_ID", "")


def get_aliyun_api_secret() -> str:
    """获取阿里云 API Secret"""
    return os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")


def get_embedding_endpoint() -> str:
    """获取阿里云 Embedding API Endpoint"""
    return os.getenv(
        "ALIYUN_EMBEDDING_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
    )


def get_embedding_model() -> str:
    """获取 Embedding 模型名称"""
    return os.getenv("ALIYUN_EMBEDDING_MODEL", "text-embedding-v3")


def get_dashvector_api_key() -> str:
    """获取 DashVector API Key"""
    return os.getenv("DASHVECTOR_API_KEY", "")


def get_dashvector_endpoint() -> str:
    """获取 DashVector Endpoint（需包含 https:// 或 http:// 协议）"""
    endpoint = os.getenv("DASHVECTOR_ENDPOINT", "").strip()
    if endpoint and not endpoint.startswith(("http://", "https://")):
        return f"https://{endpoint.rstrip('/')}"
    return endpoint


def get_dashvector_collection() -> str:
    """获取 DashVector Collection 名称"""
    return os.getenv("DASHVECTOR_COLLECTION_NAME", "lxm_memory")


def get_redis_user_emotion_ttl_seconds() -> int:
    """用户短期情绪 Redis 键 user_emotion:{user_id} 的 TTL（秒），默认 3600。见 TD-020 / V3-A。"""
    return int(os.getenv("REDIS_USER_EMOTION_TTL", "3600"))

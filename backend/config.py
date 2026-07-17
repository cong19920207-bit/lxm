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


_INVALID_ADMIN_JWT_SECRETS = {
    "admin_secret_change_me",
    "your_admin_jwt_secret_here",
}


def validate_admin_jwt_secret(secret: str | None = None) -> str:
    """校验后台 JWT 密钥，拒绝缺失、空白和公开占位值。"""
    value = os.getenv("ADMIN_JWT_SECRET") if secret is None else secret
    normalized = value.strip() if value is not None else ""
    if not normalized or normalized in _INVALID_ADMIN_JWT_SECRETS:
        raise ValueError(
            "ADMIN_JWT_SECRET 必须显式配置为非空且非公开占位值的自定义密钥"
        )
    return value


def get_admin_jwt_secret() -> str:
    """获取后台管理员 JWT 签名密钥（与用户端独立）"""
    return validate_admin_jwt_secret()


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
    """通用 LLM HTTP 超时（秒）：日记、Agent、记忆提取、后台测试集等非 Step5 注入路径使用，默认 45（与主链路体验对齐，可按环境下调）。"""
    return float(os.getenv("LLM_TIMEOUT", "45"))


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


# ============ DeepSeek（生活流 LLM-01~07，与豆包对话主链完全独立） ============

def get_deepseek_api_key() -> str:
    """获取 DeepSeek API Key（技术凭证，不进后台 UI）。缺失返回空字符串，启动阶段仅 WARN 不阻断。"""
    return os.getenv("DEEPSEEK_API_KEY", "")


def get_deepseek_base_url() -> str:
    """获取 DeepSeek Endpoint，默认 https://api.deepseek.com。"""
    return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def warn_deepseek_config_on_startup() -> None:
    """应用启动时校验 DeepSeek 配置：缺失仅 WARN，不阻断启动（避免测试环境阻塞，STEP-002）。"""
    import logging

    if not get_deepseek_api_key():
        logging.getLogger(__name__).warning(
            "DEEPSEEK_API_KEY 未配置，生活流 LLM-01~07 调用将失败；本地/测试环境可忽略此告警"
        )


# ============ LiblibAI 图像生成 / 阿里云 OSS（生活流 STEP-012） ============

def get_liblib_access_key() -> str:
    """LiblibAI AccessKey（HMAC-SHA1 签名用）。缺失返回空字符串。"""
    return os.getenv("LIBLIB_ACCESS_KEY", "")


def get_liblib_secret_key() -> str:
    """LiblibAI SecretKey（HMAC-SHA1 签名用）。缺失返回空字符串。"""
    return os.getenv("LIBLIB_SECRET_KEY", "")


def get_liblib_base_url() -> str:
    """LiblibAI Endpoint。默认官方开放平台地址。"""
    return os.getenv("LIBLIB_BASE_URL", "https://openapi.liblibai.cloud")


def get_oss_access_key_id() -> str:
    return os.getenv("OSS_ACCESS_KEY_ID", "")


def get_oss_access_key_secret() -> str:
    return os.getenv("OSS_ACCESS_KEY_SECRET", "")


def get_oss_endpoint() -> str:
    return os.getenv("OSS_ENDPOINT", "")


def get_oss_bucket() -> str:
    return os.getenv("OSS_BUCKET", "")


def get_oss_cdn_domain() -> str:
    """OSS 对应 CDN 加速域名（写入 feed_post.image_urls 的最终 URL 前缀，不含协议）。"""
    return os.getenv("OSS_CDN_DOMAIN", "")


def get_feed_image_reference_public_url() -> str:
    """参考基准图 base.png 的公网 URL（供 LiblibAI 图生图拉取）。"""
    return os.getenv("FEED_IMAGE_REFERENCE_PUBLIC_URL", "")


# ============ Open API Key ============

_OPEN_API_PEPPER_MIN_LEN = 32


def get_open_api_pepper() -> str:
    """Open API Key 哈希 pepper（必填，长度 ≥32，与 JWT 无关）。"""
    pepper = (os.getenv("OPEN_API_PEPPER") or "").strip()
    if len(pepper) < _OPEN_API_PEPPER_MIN_LEN:
        raise RuntimeError(
            f"OPEN_API_PEPPER 未配置或长度不足 {_OPEN_API_PEPPER_MIN_LEN}，"
            "请使用 openssl rand -hex 32 生成并写入 .env"
        )
    return pepper


def validate_open_api_pepper_on_startup() -> None:
    """应用启动时校验 OPEN_API_PEPPER（N1 / V2）。"""
    get_open_api_pepper()

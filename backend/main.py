# -*- coding: utf-8 -*-
# FastAPI 应用入口，定义路由挂载、中间件和启动配置

import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import TimedRotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import create_all_tables


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(h, TimedRotatingFileHandler) and
               'system.log' in getattr(h, 'baseFilename', '')
               for h in root_logger.handlers):
        sys_handler = TimedRotatingFileHandler(
            "logs/system.log", when="midnight", backupCount=30, encoding="utf-8")
        sys_handler.setFormatter(formatter)
        sys_handler.setLevel(logging.INFO)
        root_logger.addHandler(sys_handler)

    if not any(isinstance(h, TimedRotatingFileHandler) and
               'error.log' in getattr(h, 'baseFilename', '')
               for h in root_logger.handlers):
        err_handler = TimedRotatingFileHandler(
            "logs/error.log", when="midnight", backupCount=90, encoding="utf-8")
        err_handler.setFormatter(formatter)
        err_handler.setLevel(logging.ERROR)
        root_logger.addHandler(err_handler)

    if not any(isinstance(h, logging.StreamHandler) and
               not isinstance(h, TimedRotatingFileHandler)
               for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表、启动定时任务，关闭时优雅停止"""
    from backend.config import validate_open_api_pepper_on_startup, warn_deepseek_config_on_startup

    validate_open_api_pepper_on_startup()
    warn_deepseek_config_on_startup()
    await create_all_tables()
    from backend.tasks.scheduler import start_scheduler, shutdown_scheduler
    from backend.services.diary_rules_loader import get_scheduled_diary_cron_times

    dh, dm = await get_scheduled_diary_cron_times(use_cache=True)
    start_scheduler(diary_hour=dh, diary_minute=dm)
    yield
    shutdown_scheduler()


app = FastAPI(title="林小梦 AI 虚拟人", lifespan=lifespan)

# CORS 中间件
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
from backend.routers.auth import router as auth_router  # noqa: E402
from backend.routers.chat import router as chat_router  # noqa: E402
from backend.routers.diary import router as diary_router  # noqa: E402
from backend.routers.memory import router as memory_router  # noqa: E402
from backend.routers.agent import router as agent_router  # noqa: E402
from backend.routers.relationship import router as relationship_router  # noqa: E402
from backend.routers.app import router as app_router  # noqa: E402
from backend.routers.feed import router as feed_router  # noqa: E402

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(diary_router)
app.include_router(memory_router)
app.include_router(relationship_router)
app.include_router(agent_router)
app.include_router(app_router)
app.include_router(feed_router)

from backend.routers.open.chat import router as open_chat_router  # noqa: E402
from backend.routers.open.agent import router as open_agent_router  # noqa: E402

app.include_router(open_chat_router)
app.include_router(open_agent_router)

# 管理后台路由
from backend.routers.admin import auth as admin_auth  # noqa: E402
from backend.routers.admin import accounts as admin_accounts  # noqa: E402
from backend.routers.admin import operation_logs as admin_operation_logs  # noqa: E402
from backend.routers.admin import users as admin_users  # noqa: E402
from backend.routers.admin import persona as admin_persona  # noqa: E402
from backend.routers.admin import emotion_config as admin_emotion  # noqa: E402
from backend.routers.admin import world_state_mgmt as admin_world  # noqa: E402
from backend.routers.admin import prompt_mgmt as admin_prompt  # noqa: E402
from backend.routers.admin import chat_prompt_view as admin_chat_prompt_view  # noqa: E402
from backend.routers.admin import safety_rules as admin_safety  # noqa: E402
from backend.routers.admin import test_cases as admin_test_cases  # noqa: E402
from backend.routers.admin import memory_mgmt as admin_memory  # noqa: E402
from backend.routers.admin import agent_mgmt as admin_agent  # noqa: E402
from backend.routers.admin import relationship_mgmt as admin_relationship  # noqa: E402
from backend.routers.admin import stats as admin_stats  # noqa: E402
from backend.routers.admin import system_monitor as admin_system_monitor  # noqa: E402
from backend.routers.admin import vector_config as admin_vector_config  # noqa: E402
from backend.routers.admin import knowledge_mgmt as admin_knowledge  # noqa: E402
from backend.routers.admin import life_plan_mgmt as admin_life_plan  # noqa: E402
from backend.routers.admin import worldview_mgmt as admin_worldview  # noqa: E402
from backend.routers.admin import feed_mgmt as admin_feed_mgmt  # noqa: E402
from backend.routers.admin import feed_comment_mgmt as admin_feed_comment  # noqa: E402
from backend.routers.admin import agent_aware_mgmt as admin_agent_aware  # noqa: E402
from backend.routers.admin import life_config_mgmt as admin_life_config  # noqa: E402

app.include_router(admin_auth.router,
    prefix="/api/admin/auth", tags=["admin-auth"])
app.include_router(admin_accounts.router,
    prefix="/api/admin", tags=["admin-accounts"])
app.include_router(admin_operation_logs.router,
    prefix="/api/admin", tags=["admin-logs"])
app.include_router(admin_users.router,
    prefix="/api/admin", tags=["admin-users"])
app.include_router(admin_persona.router,
    prefix="/api/admin", tags=["admin-persona"])
app.include_router(admin_emotion.router,
    prefix="/api/admin", tags=["admin-emotion"])
app.include_router(admin_world.router,
    prefix="/api/admin", tags=["admin-world"])
app.include_router(admin_prompt.router,
    prefix="/api/admin", tags=["admin-prompt"])
app.include_router(admin_chat_prompt_view.router,
    prefix="/api/admin", tags=["admin-chat-prompt-view"])
app.include_router(admin_safety.router,
    prefix="/api/admin", tags=["admin-safety"])
app.include_router(admin_test_cases.router,
    prefix="/api/admin", tags=["admin-test-cases"])
app.include_router(admin_memory.router,
    prefix="/api/admin", tags=["admin-memory"])
app.include_router(admin_agent.router,
    prefix="/api/admin", tags=["admin-agent"])
app.include_router(admin_relationship.router,
    prefix="/api/admin", tags=["admin-relationship"])
app.include_router(admin_stats.router,
    prefix="/api/admin", tags=["admin-stats"])
app.include_router(admin_system_monitor.router,
    prefix="/api/admin", tags=["admin-system"])
app.include_router(admin_vector_config.router,
    prefix="/api/admin/configs", tags=["admin-configs"])
app.include_router(admin_knowledge.router,
    prefix="/api/admin", tags=["admin-character-knowledge"])
app.include_router(admin_life_plan.router,
    prefix="/api/admin", tags=["admin-life-plan"])
app.include_router(admin_worldview.router,
    prefix="/api/admin", tags=["admin-worldview"])
app.include_router(admin_feed_mgmt.router,
    prefix="/api/admin", tags=["admin-feed-mgmt"])
app.include_router(admin_feed_comment.router,
    prefix="/api/admin", tags=["admin-feed-comment"])
app.include_router(admin_agent_aware.router,
    prefix="/api/admin", tags=["admin-agent-aware"])
app.include_router(admin_life_config.router,
    prefix="/api/admin", tags=["admin-life-config"])

# ============ 静态资源 & 页面路由（必须放在所有API路由之后） ============

# 挂载静态资源目录
app.mount("/static",
          StaticFiles(directory="frontend/static"),
          name="h5_static")
app.mount("/admin/static",
          StaticFiles(directory="admin/static"),
          name="admin_static")


# 用户端H5页面路由
@app.get("/")
async def h5_index():
    return FileResponse("frontend/pages/login.html")


@app.get("/pages/{page_name}.html")
async def h5_page(page_name: str):
    path = f"frontend/pages/{page_name}.html"
    if not os.path.exists(path):
        return FileResponse("frontend/pages/login.html")
    return FileResponse(path)


# 管理后台页面路由
@app.get("/admin")
async def admin_index():
    return FileResponse("admin/pages/login.html")


@app.get("/admin/pages/{page_name}.html")
async def admin_page(page_name: str):
    path = f"admin/pages/{page_name}.html"
    if not os.path.exists(path):
        return FileResponse("admin/pages/login.html")
    return FileResponse(path)


# 头像图片容错路由
@app.get("/static/images/avatar/{filename}")
async def avatar_image(filename: str):
    path = f"frontend/static/images/avatar/{filename}"
    default = "frontend/static/images/avatar/default.png"
    return FileResponse(path if os.path.exists(path) else default)

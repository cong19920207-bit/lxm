# -*- coding: utf-8 -*-
# 内容安全检测工具（兼容旧引用，实际逻辑在 services/content_safety_service.py）

from backend.services.content_safety_service import check_content

__all__ = ["check_content"]

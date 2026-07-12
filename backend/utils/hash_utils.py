# -*- coding: utf-8 -*-
# 生活流·内容去重哈希工具（STEP-011）
#
# dedup_hash = md5("{venue_type}|{category}|{city}")，用 | 分隔避免字段拼接歧义；
# UTF-8 编码固定。用于 feed_post 7 天窗口结构化去重（PRD 4.5.1）。

import hashlib


def compute_dedup_hash(venue_type: str, category: str, city: str) -> str:
    """基于 venue_type + category + city 三字段生成 MD5 去重哈希。"""
    raw = f"{venue_type or ''}|{category or ''}|{city or ''}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

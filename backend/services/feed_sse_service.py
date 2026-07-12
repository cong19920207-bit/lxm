# -*- coding: utf-8 -*-
# 生活流·朋友圈 SSE 新帖推送服务（STEP-026）
#
# 单进程内存注册表（§0.5 二选一定案）：不引入 Redis Pub/Sub，v1 单实例部署。
#   _connections: dict[user_id, list[asyncio.Queue]]
# register/unregister 维护连接；broadcast_new_feed 向所有在线用户 Queue 投递 feed_new 事件。
# 断线不补发历史事件（PRD 5.9.3），用户依赖下拉刷新兜底。

import asyncio
import logging

logger = logging.getLogger(__name__)


class FeedSSEService:
    """朋友圈新帖 SSE 单进程内存注册表"""

    def __init__(self) -> None:
        self._connections: dict[int, list[asyncio.Queue]] = {}

    def register(self, user_id: int) -> asyncio.Queue:
        """创建一个用户连接 Queue 并加入注册表。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._connections.setdefault(user_id, []).append(q)
        logger.info("[FeedSSE] 注册连接 user=%s 当前连接数=%d",
                    user_id, len(self._connections[user_id]))
        return q

    def unregister(self, user_id: int, queue: asyncio.Queue) -> None:
        """从注册表移除指定连接 Queue；用户无剩余连接则清理键。"""
        conns = self._connections.get(user_id)
        if not conns:
            return
        try:
            conns.remove(queue)
        except ValueError:
            pass
        if not conns:
            self._connections.pop(user_id, None)
        logger.info("[FeedSSE] 注销连接 user=%s 剩余=%d",
                    user_id, len(self._connections.get(user_id, [])))

    def online_user_count(self) -> int:
        """当前在线用户数（含至少一个连接）。"""
        return len(self._connections)

    def broadcast_new_feed(self, post_ids: list[int]) -> int:
        """
        向所有在线用户投递 feed_new 事件；返回投递的连接数。
        事件体：{"type": "feed_new", "delta": len(post_ids)}
        """
        if not post_ids:
            return 0
        event = {"type": "feed_new", "delta": len(post_ids)}
        delivered = 0
        for user_id, conns in list(self._connections.items()):
            for q in list(conns):
                try:
                    q.put_nowait(event)
                    delivered += 1
                except asyncio.QueueFull:
                    logger.warning("[FeedSSE] 队列已满，丢弃事件 user=%s", user_id)
        logger.info("[FeedSSE] 广播新帖 delta=%d 投递连接=%d", len(post_ids), delivered)
        return delivered


# 全局单例
feed_sse_service = FeedSSEService()

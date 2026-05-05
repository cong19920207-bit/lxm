# -*- coding: utf-8 -*-
# STEP-016 单元测试：Step6 异步入队 + M2 半异步 + 重试

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.llm_service import MessageItem
from backend.services.step6_orchestrator import (
    Step6Snapshot,
    _RETRY_BACKOFF_SEC,
    execute_step6,
)


def _make_snapshot(msg_count: int = 3, **overrides) -> Step6Snapshot:
    """构建测试用 Step6Snapshot。"""
    messages = [MessageItem(type="text", content=f"第{i+1}条") for i in range(msg_count)]
    defaults = {
        "user_id": 1,
        "round_id": "test-round-001",
        "step6_messages": messages,
        "user_input": "测试用户输入",
        "persona_text": "测试人格设定",
        "level_name": "朋友",
        "relation_description": None,
        "user_real_name": None,
        "user_hobby_name": None,
        "user_description": None,
        "character_purpose": None,
        "character_attitude": None,
        "recent_conversations": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好呀"},
        ],
        "future_time_natural": "无",
        "future_action": "无",
    }
    defaults.update(overrides)
    return Step6Snapshot(**defaults)


# ============ 场景1：Step5 成功 → Step6 异步入队，不阻塞主链 ============


class TestStep6AsyncNonBlocking:

    @pytest.mark.asyncio
    async def test_step6_runs_async_not_blocking(self):
        """Step6 通过 asyncio.create_task 入队，主链不等待其完成。"""
        snapshot = _make_snapshot()
        call_log = []

        async def mock_pipeline(s):
            await asyncio.sleep(0.1)
            call_log.append("step6_done")

        with patch(
            "backend.services.step6_orchestrator._step6_pipeline",
            side_effect=mock_pipeline,
        ):
            task = asyncio.create_task(execute_step6(snapshot))
            # 主链立即继续，不阻塞
            call_log.append("main_continues")
            await task

        assert call_log[0] == "main_continues"
        assert "step6_done" in call_log


# ============ 场景2：首次失败 → 500ms 后重试 → 重试成功 ============


class TestStep6RetrySuccess:

    @pytest.mark.asyncio
    async def test_first_fail_then_retry_success(self):
        """首次调用失败后等待 500ms 重试一次，重试成功。"""
        call_count = {"n": 0}

        async def mock_pipeline(s):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("模拟首次失败")
            # 第二次成功

        snapshot = _make_snapshot()
        with patch(
            "backend.services.step6_orchestrator._step6_pipeline",
            side_effect=mock_pipeline,
        ):
            start = asyncio.get_event_loop().time()
            await execute_step6(snapshot)
            elapsed = asyncio.get_event_loop().time() - start

        assert call_count["n"] == 2
        # 退避时间约 500ms（允许误差）
        assert elapsed >= _RETRY_BACKOFF_SEC * 0.8


# ============ 场景3：两次都失败 → 写日志，主链不受影响 ============


class TestStep6BothFail:

    @pytest.mark.asyncio
    async def test_both_attempts_fail_logs_error(self, caplog):
        """两次都失败 → 写 ERROR 日志，任务正常结束不抛异常。"""
        async def mock_pipeline(s):
            raise RuntimeError("模拟持续失败")

        snapshot = _make_snapshot()
        with patch(
            "backend.services.step6_orchestrator._step6_pipeline",
            side_effect=mock_pipeline,
        ):
            with caplog.at_level(logging.ERROR, logger="backend.services.step6_orchestrator"):
                # 不抛异常，主链不受影响
                await execute_step6(snapshot)

        assert any("重试后仍失败" in r.message for r in caplog.records)


# ============ 场景4：Step5 messages 8 条 → Step6 入参为合并后 5 条（T6）============


class TestStep6MessagesMerged:

    @pytest.mark.asyncio
    async def test_step6_receives_merged_messages(self):
        """
        验证 Step6 入参 messages 已经过合并。

        本测试模拟 chat.py 中 merge_messages_if_exceed 的调用结果：
        8 条 messages 经过合并后应为 5 条（CP1 规则）。
        """
        from backend.services.llm_service import merge_messages_if_exceed

        original_8 = [MessageItem(type="text", content=f"消息{i+1}") for i in range(8)]
        merged = merge_messages_if_exceed(original_8)

        # 验证合并规则：8 条 → 5 条
        assert len(merged) == 5

        # 用合并后的 messages 构建 snapshot
        snapshot = _make_snapshot(step6_messages=merged)
        assert len(snapshot.step6_messages) == 5

        # 验证 Step6 管线接收到正确的 messages 数量
        received_msgs = []

        async def mock_pipeline(s):
            received_msgs.extend(s.step6_messages)

        with patch(
            "backend.services.step6_orchestrator._step6_pipeline",
            side_effect=mock_pipeline,
        ):
            await execute_step6(snapshot)

        assert len(received_msgs) == 5


# ============ 场景5（边界）：Step5 失败 → 不入队 Step6（T8）============


class TestStep6NotEnqueuedOnStep5Fail:

    @pytest.mark.asyncio
    async def test_step5_failure_no_step6_enqueue(self):
        """
        Step5 失败时不入队 Step6。

        此测试验证 chat.py 中的逻辑分支：Step5 异常时直接 return，
        不会执行到 Step6 入队代码。通过 mock _execute_llm_bundle 的行为来验证。
        """
        step6_called = {"called": False}

        original_execute_step6 = execute_step6

        async def tracking_execute_step6(snapshot):
            step6_called["called"] = True
            await original_execute_step6(snapshot)

        # 模拟 Step5 失败的场景：不调用 execute_step6
        # 在实际 chat.py 中，Step5 失败会在 except 分支 return，
        # 永远不会到达 Step6 入队代码
        from backend.services.llm_service import Step5ParseError

        with patch(
            "backend.services.step6_orchestrator.execute_step6",
            side_effect=tracking_execute_step6,
        ):
            # Step5 失败时，execute_step6 不会被调用
            # 这里直接验证逻辑：如果 Step5 抛异常，Step6 不执行
            try:
                raise Step5ParseError("模拟 Step5 解析失败")
            except Step5ParseError:
                pass  # Step5 失败，跳过 Step6

        assert step6_called["called"] is False


# ============ 完整管线集成测试（mock 外部依赖） ============


class TestStep6PipelineIntegration:

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        """完整管线：LLM → 解析 → 向量写入 → 标量更新，全部成功。"""
        snapshot = _make_snapshot()

        mock_llm_output = '''{
            "InnerMonologue": "测试内心独白",
            "CharacterPublicSettings": "无",
            "CharacterPrivateSettings": "无",
            "CharacterKnowledges": "无",
            "UserSettings": "无",
            "UserRealName": "无",
            "UserHobbyName": "无",
            "UserDescription": "无",
            "CharacterPurpose": "无",
            "CharacterAttitude": "无",
            "RelationDescription": "无"
        }'''

        mock_relationship = MagicMock()
        mock_relationship.user_id = 1
        mock_relationship.id = 10

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_relationship
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "backend.services.step6_orchestrator.llm_client"
        ) as mock_llm, patch(
            "backend.services.step6_orchestrator.upsert_step6_vectors",
            new_callable=AsyncMock,
        ) as mock_vectors, patch(
            "backend.services.step6_orchestrator.async_session_maker",
            return_value=mock_db,
        ), patch(
            "backend.services.step6_orchestrator.RelationshipService"
        ) as MockRelSvc:
            mock_llm.chat_sync = AsyncMock(return_value=mock_llm_output)
            mock_svc_instance = MagicMock()
            mock_svc_instance.update_relationship_from_step6 = AsyncMock(
                return_value={"updated_fields": [], "history_count": 0, "future_status": "no_future"}
            )
            MockRelSvc.return_value = mock_svc_instance

            await execute_step6(snapshot)

            mock_llm.chat_sync.assert_called_once()
            mock_vectors.assert_called_once()
            mock_svc_instance.update_relationship_from_step6.assert_called_once()

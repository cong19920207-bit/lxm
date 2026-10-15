"""Safe, read-only presentation of a task belonging to the current memory version."""
from datetime import datetime

REASONS = {
    'identity_busy': '记忆正在更新，等待当前操作完成',
    'index_round_expired': '本轮索引处理已超时，需要人工重试',
    'index_attempts_exhausted': '本轮写入尝试次数已用尽，需要人工重试',
    'index_probe_budget_exhausted': '索引写入结果尚未核实，自动核实次数已用尽',
    'index_profile_unavailable': '任务所需的索引编码版本不可用',
    'source_read_unverified': '暂时无法核实源记忆，等待重新读取',
    'index_encode_failed': 'BM25 索引编码失败',
    'index_evidence_unverified': '远端索引写入结果尚未核实',
    'index_confirmation_unverified': '当前索引任务与写入确认信息不一致',
    'remote_rejected': '远端拒绝了索引写入',
    'remote_outcome_unknown': '远端索引写入结果待核实',
    'index_dispatch_not_sent': '本次索引写入尚未发送',
    'task_execution_unverified': '本次索引执行结果待核实',
    'worker_stopped': '索引执行器已停止，等待后续处理',
}


def iso(value):
    return value.isoformat(timespec='microseconds') + 'Z' if value else None


def maintenance_detail(identity, task, *, now=None):
    if identity.index_state == 'ready':
        return None
    missing = dict(state='unavailable', task_id=None, reason_code=None,
                   reason='原因暂不可用：未找到当前版本的索引任务',
                   attempt_count=None, next_attempt_at=None, overdue=False)
    if task is None or task.state == 'superseded' or (
        task.identity_id != identity.id or task.generation != identity.generation
        or task.body_hash != identity.body_hash or task.encoder_version != identity.encoder_version
        or task.operation_id != identity.current_operation_id
    ):
        return missing
    now = now or datetime.utcnow()
    active = task.state in {'pending', 'running', 'retry_wait'}
    overdue = active and task.round_deadline_at <= now
    code = task.error_code if task.error_code in REASONS else None
    reason = REASONS.get(code)
    if overdue:
        # attempt counts writes, not claims; do not infer "never ran" from attempt alone.
        code = 'index_round_expired'
        reason = ('索引任务已超时，尚未领取，等待转入人工处理'
                  if task.worker_epoch == 0 and task.attempt == 0
                  else '索引任务已超过本轮时限，等待核实处理结果')
    if reason is None:
        reason = {'pending': '等待执行器领取并补建 BM25 索引',
                  'running': '正在处理 BM25 索引',
                  'retry_wait': '等待下一次索引处理',
                  'manual': '需要人工处理，具体原因暂不可用',
                  'completed': '任务已完成，但当前索引状态尚待核实'}.get(task.state, '原因暂不可用')
        if task.error_code:
            reason = '原因暂不可用：未识别的索引错误'
    return dict(state='manual_required' if task.state == 'manual' else task.state,
                task_id=task.task_id, reason_code=code, reason=reason,
                attempt_count=task.attempt, next_attempt_at=iso(task.next_attempt_at), overdue=overdue)

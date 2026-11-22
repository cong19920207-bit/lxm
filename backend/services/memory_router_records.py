"""Read-only views of actual chat generations within a bounded admission window."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import math
import os

from sqlalchemy import select
from backend import constants as codes
from backend.models.chat_lifecycle import ChatGeneration as Generation, ChatLifecycleEffect
from backend.models.conversation_log import ConversationLog
from backend.models.relationship_change_history import RelationshipChangeHistory
from backend.services.chat_completed_history import HistoryMessage, HISTORY_TITLE
from backend.services.memory_admin_common import AdminMemoryError, iso
from backend.services.memory_config_schema import DEFAULT_ROUTER
from backend.services.memory_router_config import history_query, version_view
from backend.models.admin_config import AdminConfig
from backend.services.prompt_builder import PromptBuilder

REASONS = {"model_decision":"模型返回合法布尔值","timeout":"路由判定超时，选择查询路径",
           "invalid_response":"判定格式无效，选择查询路径","provider_error":"模型调用异常，选择查询路径",
           "disabled":"路由已关闭，直通查询路径","current_input_truncated":"当前输入被截断，选择保守查询",
           "router_input_over_budget":"判定输入超出预算，选择保守查询"}
SOFT = {"timeout","invalid_response","provider_error"}
GUARDS = {"current_input_truncated","router_input_over_budget"}


def utc(value):
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def lease_match(row, trace):
    if trace is None or trace.get("lease_epoch") is None:
        return "unverified"
    if str(trace["lease_epoch"])==str(row.lease_epoch):
        return "current"
    return "earlier"


def summary_item(row):
    trace=row.memory_router_trace or {}
    duration=(row.terminal_at-row.accepted_at).total_seconds()*1000 if row.terminal_at else None
    return dict(id=row.generation_id,generation_id=row.generation_id,user_id=str(row.user_id),accepted_at=iso(row.accepted_at),
                terminal_at=iso(row.terminal_at),state=row.state,phase=row.phase,reason=row.reason,round_id=row.round_id,
                elapsed_ms=int(duration) if duration is not None else None,trace_available=row.memory_router_trace is not None,
                lease_match=lease_match(row,trace),current_epoch=str(row.lease_epoch),trace_epoch=trace.get("lease_epoch"),
                decision=trace.get("decision"),execution_path=trace.get("execution_path"),controlled_reason=trace.get("controlled_reason"),
                router_duration_ms=trace.get("router_duration_ms"),stats_completeness=trace.get("stats_completeness"),
                source_channels=trace.get("source_channels"),router_config_version=trace.get("router_config_version"))


def window_query(start, end, user_id=None, generation_id=None, state=None):
    query=select(Generation).where(Generation.accepted_at>=start,Generation.accepted_at<end)
    for column,value in ((Generation.user_id,user_id),(Generation.generation_id,generation_id),(Generation.state,state)):
        if value is not None:
            query=query.where(column==value)
    if not generation_id:
        index="ix_chat_user_accepted_generation" if user_id is not None else "ix_chat_accepted_generation"
        query=query.with_hint(Generation,f"USE INDEX ({index})",dialect_name="mysql")
    return query.order_by(Generation.accepted_at.desc(),Generation.generation_id.desc())


async def list_records(db, *, start=None,end=None,user_id=None,generation_id=None,state=None,
                       path=None,reason=None,version=None,page=1,page_size=20):
    end=utc(end) or datetime.utcnow()
    start=utc(start) or end-timedelta(days=1)
    if end<=start or end-start>timedelta(days=30):
        raise AdminMemoryError(codes.ADMIN_ERR_MEMORY_INVALID,"时间范围须在 30 天内")
    query=window_query(start,end,user_id,generation_id,state)
    stream=await db.stream_scalars(query.execution_options(yield_per=200))
    counts=dict.fromkeys(("total","covered","missing","matching_traces","true","false","disabled","conservative",
                          "error_fallback","unknown","timeout","current_success_true","current_success_false",
                          "duration_missing"),0)
    buckets=Counter()
    items=[]
    matching=0
    async for row in stream:
        counts["total"]+=1
        trace=row.memory_router_trace
        counts["missing" if trace is None else "covered"]+=1
        filters=((path,"execution_path"),(reason,"controlled_reason"),(version,"router_config_version"))
        if any(v is not None and (trace is None or str(trace.get(k))!=str(v)) for v,k in filters):
            continue
        if (page-1)*page_size<=matching<page*page_size:
            items.append(summary_item(row))
        matching+=1
        if trace is None:
            continue
        counts["matching_traces"]+=1
        why=trace.get("controlled_reason")
        decision=trace.get("decision")
        if why=="model_decision" and type(decision) is bool:
            key="true" if decision else "false"
            counts[key]+=1
            if row.state=="success" and lease_match(row,trace)=="current":
                counts["current_success_"+key]+=1
        elif why in SOFT:
            counts["error_fallback"]+=1
            if why=="timeout":
                counts["timeout"]+=1
        elif why in GUARDS:
            counts["conservative"]+=1
        else:
            counts["disabled" if why=="disabled" else "unknown"]+=1
        duration=trace.get("router_duration_ms")
        if type(duration) in (int,float) and math.isfinite(duration) and duration>=0:
            buckets[int(duration//100)*100]+=1
        else:
            counts["duration_missing"]+=1
    n=counts["true"]+counts["false"]
    success_n=counts["current_success_true"]+counts["current_success_false"]
    return dict(list=items,total=matching,page=page,page_size=page_size,summary=counts,
                legal_decisions=n,false_ratio=counts["false"]/n if n else None,
                success_legal_decisions=success_n,success_false_ratio=counts["current_success_false"]/success_n if success_n else None,
                duration=dict(metric="router_duration_ms",unit="ms",bucket_width=100,samples=sum(buckets.values()),
                              distribution=[dict(from_ms=k,to_ms=k+100,count=buckets[k]) for k in sorted(buckets)]),
                coverage_scope=dict(start=iso(start),end=iso(end),user_id=user_id,generation_id=generation_id,state=state),
                path_scope=dict(path=path,reason=reason,version=version),server_time=iso(datetime.utcnow()))


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def config_reference(db, trace):
    version=trace.get("router_config_version")
    digest=trace.get("prompt_digest")
    if version is None or not digest:
        return {"status":"unrecorded"}
    if str(version)=="0":
        revision=trace.get("application_revision")
        if not revision or revision!=os.getenv("APP_REVISION"):
            return {"status":"version_unavailable"}
        config=DEFAULT_ROUTER.model_dump()
    else:
        row=await db.scalar(history_query().where(AdminConfig.version==version))
        if row is None:
            return {"status":"version_unavailable"}
        config=version_view(row)["config"]
    if hashed(config["prompt"])!=digest:
        return {"status":"digest_mismatch"}
    return {"status":"verified","version":str(version),"config":config}


def _span(value):
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(type(n) is int for n in value) and 0 <= value[0] <= value[1]):
        return slice(*value)
    return None


def _current_source(messages, ids, trace):
    if not trace.get("rewrite_input_digest") or not trace.get("reply_input_digest"):
        return {"status": "unrecorded"}
    if any(i not in messages for i in ids):
        return {"status": "source_missing"}
    packed = "\n".join(messages[i].content for i in ids)
    span = _span(trace.get("rewrite_input_range"))
    if span is None:
        return {"status": "unrecorded"}
    if span.stop > len(packed):
        return {"status": "digest_mismatch"}
    text = packed[span]
    version = trace.get("input_render_version")
    if version == "shared-suffix-v1":
        if trace.get("reply_input_range") != trace["rewrite_input_range"] or type(trace.get("reply_input_has_header")) is not bool:
            return {"status": "unrecorded"}
        module = PromptBuilder.render_user_input(text) if trace["reply_input_has_header"] else text
    elif version is None:
        rendered = PromptBuilder.render_user_input(packed)
        reply_span = _span(trace.get("reply_module_range"))
        if reply_span is None:
            return {"status": "unrecorded"}
        if reply_span.stop > len(rendered):
            return {"status": "digest_mismatch"}
        module = rendered[reply_span]
    else:
        return {"status": "version_unavailable"}
    if hashed(text) != trace["rewrite_input_digest"] or hashed(module) != trace["reply_input_digest"]:
        return {"status": "digest_mismatch"}

    parts = []
    offset = 0
    for mid in ids:
        message = messages[mid]
        end = offset + len(message.content)
        left, right = max(offset, span.start), min(end, span.stop)
        if left < right:
            parts.append({"id": str(mid), "role": message.role, "content": message.content[left-offset:right-offset]})
        offset = end + 1  # The packed representation joins adjacent messages with one newline.
    return {"status": "verified", "scope": "full" if span.start == 0 and span.stop == len(packed) else "fragment",
            "verified_text": text, "messages": parts}


async def source_reference(db, row, trace, role):
    # Use the same authority as GET /users/{user_id}/conversations.
    from backend.routers.admin.users import _USER_BUSINESS_READ_ROLES
    if role not in _USER_BUSINESS_READ_ROLES:
        return {"history":{"status":"forbidden"},"current":{"status":"forbidden"}}
    rounds=trace.get("history_round_refs")
    refs=trace.get("current_input_refs")
    history_ids=[int(mid) for group in (rounds or []) for mid in group.get("message_ids",[])]
    input_ids=[int(r["message_id"]) for r in (refs or []) if r.get("in_prompt")]
    ids=set(history_ids+input_ids)
    messages={}
    # A historical bundle may have many bubbles. Keep bind counts bounded.
    ordered=sorted(ids)
    for start in range(0,len(ordered),500):
        rows=await db.scalars(select(ConversationLog).where(ConversationLog.user_id==row.user_id,
                              ConversationLog.id.in_(ordered[start:start+500])))
        messages.update({m.id:m for m in rows})
    def verified(ids, state):
        result={"status":state}
        if state=="verified":
            result["messages"]=[dict(id=str(i),role=messages[i].role,content=messages[i].content) for i in ids]
        return result
    hs="unrecorded"
    if rounds is not None and trace.get("history_digest"):
        if any(i not in messages for i in history_ids):
            hs="source_missing"
        elif trace.get("history_render_version")!="shanghai-json-v1":
            hs="version_unavailable"
        else:
            lines=[HistoryMessage(i,messages[i].role,messages[i].content,messages[i].created_at,messages[i].sort_seq).render() for i in history_ids]
            rendered=HISTORY_TITLE+"\n"+"\n".join(lines) if lines else ""
            hs="verified" if hashed(rendered)==trace["history_digest"] else "digest_mismatch"
    current = _current_source(messages, input_ids, trace) if refs is not None else {"status": "unrecorded"}
    return {"history":verified(history_ids,hs),"current":current}


async def record_detail(db,generation_id,role):
    row=await db.get(Generation,generation_id)
    if row is None:
        raise AdminMemoryError(codes.ADMIN_ERR_MEMORY_NOT_FOUND,"generation_unavailable")
    trace=row.memory_router_trace or {}
    effects=await db.scalars(select(ChatLifecycleEffect).where(ChatLifecycleEffect.owner_kind=="chat",
                             ChatLifecycleEffect.owner_id==generation_id,ChatLifecycleEffect.user_id==row.user_id))
    tasks=[dict(kind=e.effect_kind,state=e.state,attempts=e.attempts,completed_at=iso(e.completed_at),reason=e.last_reason) for e in effects]
    changes=[]
    if row.state=="success" and row.round_id:
        changes=[str(i) for i in await db.scalars(select(RelationshipChangeHistory.id).where(
            RelationshipChangeHistory.user_id==row.user_id,RelationshipChangeHistory.round_id==row.round_id,
            RelationshipChangeHistory.trigger_source=="step6"))]
    return {**summary_item(row),"trace":row.memory_router_trace,"config_reference":await config_reference(db,trace),
            "source_reference":await source_reference(db,row,trace,role),"effects":tasks,
            "reason_text":REASONS.get(trace.get("controlled_reason")),"business_evidence":{
                "relationship_change_ids":changes,"relationship_status":"rows_verified" if changes else "unverified",
                "complete_step6_writes":"unverified"}}

"""Per-attempt observations. No message, prompt, credential or provider body is persisted."""
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import time

from sqlalchemy import func, select, update
from backend.models.chat_lifecycle import ChatGeneration, ChatUserState, ChatSubmission, ChatSubmissionMessage
from backend.services.memory_config_schema import ROUTER_KEY

log = logging.getLogger(__name__)
active_observation = ContextVar("memory_router_observation", default=None)
KINDS = ("router", "rewrite", "embedding", "dense", "bm25", "rerank", "tokenization")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class CallObservation:
    counts: dict = field(default_factory=lambda: dict.fromkeys(KINDS, 0))
    usage: list = field(default_factory=list)


def observe_call(kind):
    observation = active_observation.get()
    if observation is not None:
        observation.counts[kind] += 1


def observe_usage(kind, model, response):
    observation = active_observation.get()
    if observation is None or not isinstance(response, dict) or not isinstance(response.get("usage"),dict):
        return
    values = {k:v for k,v in response["usage"].items() if k in {
        "prompt_tokens","completion_tokens","total_tokens","input_tokens","output_tokens"}
        and type(v) is int and v >= 0}
    if values:
        observation.usage.append({"stage":kind,"model":model,**values})


class ChatTrace:
    def __init__(self, sessions, handle, raw):
        self.sessions, self.handle, self.raw = sessions, handle, raw
        self.observed = CallObservation()
        self.data = {}

    async def record(self, stage, *args):
        try:
            await getattr(self, stage)(*args)
        except Exception:
            log.warning("memory_router_trace_unavailable generation=%s stage=%s", self.handle.generation_id, stage)

    async def interrupted(self, exc):
        from backend.services.chat_lifecycle import LostOwnership
        from backend.services.memory_prompt_builder import PromptBudgetExceeded
        from backend.services.memory_token_budget import BudgetUnverified
        if isinstance(exc, LostOwnership) or self.data.get("counter_status") == "verified":
            return
        if isinstance(exc, BudgetUnverified):
            reason = "counter_unverified"
        elif isinstance(exc, PromptBudgetExceeded):
            reason = "budget_blocked"
        elif isinstance(exc, TimeoutError):
            reason = "deadline_exceeded"
        else:
            reason = "interrupted"
        if not self.data:
            self.data = {"schema_version": 1, "lease_epoch": str(self.handle.epoch),
                         "generation_id": self.handle.generation_id, "execution_path": None,
                         "config_snapshot_id": self.raw.config.config_snapshot_id,
                         "stage_statuses": {"retrieval": "not_started", "assembly": "not_started"},
                         "effective_max_total": self.raw.config.prompt["max_total"]}
        if self.data.get("router_status") and self.data.get("execution_path") != "skip":
            self.data["stage_statuses"] = {"retrieval": "unverified", "assembly": "unverified"}
        if isinstance(exc, PromptBudgetExceeded) and (exc.measurement or {}).get("scope") == "module":
            self.data["budget_measurement"] = exc.measurement
        self.data.update(error_stage="preparation" if not self.data.get("router_status") else "after_router",
                         controlled_error=reason, counter_status="unverified" if isinstance(exc,BudgetUnverified) else "unavailable")
        await self.save("interrupted", complete=False)

    async def source_channels(self):
        if self.raw.source_channels:
            return list(self.raw.source_channels)
        members = [message_id for message_id, _, _ in self.raw.current_refs]
        if not members:
            return None
        remaining = (self.handle.deadline_at - datetime.utcnow()).total_seconds() - 5
        if remaining <= 0:
            return None
        try:
            async with asyncio.timeout(min(.25, remaining)), self.sessions() as db:
                query = select(ChatSubmission.channel).distinct().join(ChatSubmissionMessage,
                    ChatSubmissionMessage.submission_id == ChatSubmission.id).where(
                    ChatSubmission.user_id == self.handle.user_id, ChatSubmissionMessage.user_id == self.handle.user_id,
                    ChatSubmissionMessage.conversation_id.in_(members),
                    (ChatSubmission.operation == "send") | (ChatSubmission.accepted_generation_id == self.handle.generation_id),
                ).order_by(ChatSubmission.channel)
                return list(await db.scalars(query))
        except Exception:
            log.warning("memory_router_channels_unavailable generation=%s", self.handle.generation_id)
            return None

    async def routed(self, shared, router, deadline):
        raw, conf = self.raw, self.raw.config
        history = shared.history
        metadata = conf.versions.get(ROUTER_KEY, {})
        self.data = dict(schema_version=1, lease_epoch=str(self.handle.epoch), generation_id=self.handle.generation_id,
            config_snapshot_id=conf.config_snapshot_id, router_config_source=metadata.get("source"),
            router_config_version=metadata.get("version"), router_config_revision=str(metadata["revision"]) if "revision" in metadata else None,
            prompt_digest=digest(conf.router.prompt), rule_render_version="router_boolean_v1:1",
            history_render_version="shanghai-json-v1", application_revision=os.getenv("APP_REVISION") or None,
            token_config_version=conf.versions.get("prompt_token_config",{}).get("version"),
            retrieval_config_version=conf.versions.get("vector_retrieval_config",{}).get("version"),
            model_profile_id=conf.router.model_profile_id, effective_model=conf.router.effective_model(conf.reply_model),
            provider=conf.router.provider_name, thinking_enabled=conf.router.thinking_enabled,
            behavior_profile_id=conf.router.behavior_profile_id, enabled=conf.router.enabled,
            decision=router.decision,execution_path=router.path, controlled_reason=router.reason,
            router_status=router.reason, router_duration_ms=router.duration_ms if self.observed.counts["router"] else None,
            timeout_ms=conf.router.timeout_ms, deadline_remaining_ms=max(0,int((deadline-time.monotonic())*1000)),
            error_stage="router" if router.reason in ("provider_error","timeout","invalid_response") else None,
            source_channels=await self.source_channels(), current_input_refs=[
                {"message_id":str(mid),"ordinal":ordinal,"in_prompt":included} for mid,ordinal,included in raw.current_refs],
            input_render_version="shared-suffix-v1", reply_input_has_header=shared.modules["user_input"] != shared.current_input,
            rewrite_input_digest=digest(shared.current_input), reply_input_digest=digest(shared.modules["user_input"]),
            rewrite_input_truncated=shared.reply_input_truncated, reply_input_truncated=shared.reply_input_truncated,
            rewrite_input_range=[shared.current_input_start,shared.current_input_start + len(shared.current_input)],
            reply_module_range=[0,len(shared.modules["user_input"])],
            reply_input_range=[shared.current_input_start,shared.current_input_start + len(shared.current_input)],
            history_rounds_loaded=len(raw.history_candidates.rounds), history_rounds_used=len(history.rounds),
            history_rounds_trimmed=len(raw.history_candidates.rounds)-len(history.rounds), history_digest=history.digest,
            history_round_refs=[dict(key=r.key,source=r.source,message_ids=[str(i) for i in r.message_ids]) for r in history.rounds],
            history_start=history.first_message_time.isoformat() if history.first_message_time else None,
            history_end=history.last_message_time.isoformat() if history.last_message_time else None, history_timezone="Asia/Shanghai",
            persona_source=raw.persona.source,persona_version=raw.persona.version,persona_digest=digest(raw.persona.text),
            router_background_digest=digest(json.dumps(dict(shared.visible_background),ensure_ascii=False,sort_keys=True)),
            effective_max_total=conf.prompt["max_total"], counter_status="pending",official_prompt_tokens=None,
            stage_statuses={"retrieval":"not_started","assembly":"not_started"})
        self.data["deadline_remaining_at_router_ms"] = self.data["deadline_remaining_ms"]
        await self.save("routed",complete=False)

    async def assembled(self, result, retrieval):
        self.data.update(official_prompt_tokens=result.counter["rendered_tokens"],counter_status="verified",
            stage_statuses={"retrieval":retrieval.retrieval_status,"rewrite":retrieval.rewrite_state,
                            "assembly":"budget_blocked" if result.over_budget else "completed"})
        await self.save("assembled",complete=True)

    async def save(self, stage, *, complete):
        handle = self.handle
        remaining = (handle.deadline_at-datetime.utcnow()).total_seconds()
        if remaining <= 0:
            return
        counts = dict(self.observed.counts)
        if not complete:
            for name in ("rewrite","embedding","dense","bm25","rerank"):
                counts[name] = 0 if self.data["execution_path"]=="skip" else None
        if not complete and stage == "interrupted":
            counts["tokenization"] = None
        trace = {**self.data, "deadline_remaining_ms": max(0,int(remaining * 1000)), "recorded_stage":stage,"recorded_at":datetime.now(timezone.utc).isoformat(),
                 "stats_completeness":"complete" if complete else "partial","call_counts":counts,
                 "observed_calls_to_stage":dict(self.observed.counts),
                 "provider_usage":list(self.observed.usage) or None,
                 "usage_status":"reported" if self.observed.usage else "not_provided"}
        try:
            # Bound optional SQL work and leave the original commit reserve alone.
            timeout = min(.25,remaining - 5)
            if timeout <= 0:
                return
            async with asyncio.timeout(timeout), self.sessions() as db:
                now = func.utc_timestamp(6) if db.bind.dialect.name=="mysql" else func.current_timestamp()
                statement = update(ChatGeneration).where(ChatGeneration.user_id==handle.user_id,
                    ChatGeneration.generation_id==handle.generation_id,ChatGeneration.lease_owner==handle.owner,
                    ChatGeneration.lease_epoch==handle.epoch,ChatGeneration.state=="pending",
                    ChatGeneration.lease_until>now,ChatGeneration.deadline_at>now,
                    select(ChatUserState.user_id).where(ChatUserState.user_id==handle.user_id,
                        ChatUserState.current_generation_id==handle.generation_id).exists()).values(memory_router_trace=trace)
                await db.execute(statement.execution_options(synchronize_session=False))
                await db.commit()
        except Exception:
            log.warning("memory_router_trace_write_unverified generation=%s stage=%s",handle.generation_id,stage)

"""Request-local, immutable preparation for text chat and diagnostics."""
import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping

from sqlalchemy import select

from backend.models.relationship import Relationship
from backend.redis_client import get_redis
from backend.services.chat_completed_history import CompletedRound, HISTORY_TITLE, HistoryCandidates, local_time, read_completed_history
from backend.services.memory_effective_config import EffectiveMemoryConfig, resolve_active_memory_config
from backend.services import prompt_builder as prompts
from backend.services.memory_prompt_builder import PromptBudgetExceeded, check_fixed_module_budgets, compose, fit_context_text
from backend.services.memory_token_budget import measure_rendered_budget, validate_bound_counter
from backend.services.user_short_term_emotion_service import read_for_prompt


@dataclass(frozen=True)
class ExecutionIdentity:
    kind: str
    execution_id: str
    lease_version: int


@dataclass(frozen=True)
class RawChatContext:
    identity: ExecutionIdentity
    config: EffectiveMemoryConfig
    persona: prompts.ResolvedPersona
    now: datetime
    round_context: Mapping
    modules: Mapping[str, str]
    relationship_core: str
    history_candidates: HistoryCandidates
    current_messages: tuple[str, ...]
    read_errors: tuple[str, ...]
    current_refs: tuple = ()
    source_channels: tuple = ()


def _present(value):
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _relationship(row, instant):
    level = row.level if row else 0
    definition = prompts.LEVEL_DEFINITIONS.get(level)
    last = local_time(row.last_interaction_at) if row else None
    days = (instant - last).days if last else 999
    context = {"silence_days": days}
    lines = []
    if definition:
        context.update(level=level, level_name=definition["name"], level_definition=definition["behavior"])
        lines.extend((f"当前关系等级：{definition['name']}（等级 {level}）", f"语气与行为边界：{definition['behavior']}"))
    if 8 <= days <= 14:
        lines.append(prompts.SILENCE_CORRECTION_8_14)
    elif days >= 15:
        lines.append(prompts.SILENCE_CORRECTION_15_PLUS)
    core = "\n".join(["【关系状态】", *lines]) if lines else ""
    if row:
        for key in ("relation_description", "user_real_name", "user_hobby_name", "user_description",
                    "character_purpose", "character_attitude"):
            value = getattr(row, key, None)
            if _present(value):
                context[key] = value
    for field, label in (("relation_description", "关系描述"), ("user_description", "对TA的印象")):
        if field in context:
            lines.append(f"{label}：{context[field]}")
    return context, ("\n".join(["【关系状态】", *lines]) if lines else ""), core


async def read_raw_chat_context(*, sessions, environment_id, user_id, identity, current_messages,
                                current_message_ids=(), current_refs=(), source_channels=(), now=None):
    """Close the read session before the first official count, guard or model wait."""
    instant = local_time(now if now is not None else datetime.now(timezone.utc))
    errors = []
    async with sessions() as db:
        config = await resolve_active_memory_config(db, environment_id, allow_isolated=environment_id.startswith("isolated:"))
        builder = prompts.PromptBuilder(db)
        persona = await builder.resolve_persona()
        errors.extend(persona.errors)
        system = await builder._load_step5_system_template_raw(errors=errors)
        row = await db.scalar(select(Relationship).where(Relationship.user_id == user_id))
        history = await read_completed_history(db, user_id, current_message_ids)
        emotion = await read_for_prompt(user_id, db, await get_redis(), errors=errors)
        activity = await prompts.get_activity_description(instant, errors=errors)
        context, relation, core = _relationship(row, instant)
        context["time_description"] = prompts._generate_time_description(instant)
        if _present(activity):
            context["activity_description"] = activity
        # Only the official fit below may clip an input. These legacy renderers
        # keep the established wording and receive nonbinding limits.
        limits = {key: 10**9 for key in prompts.MODULE_TOKEN_LIMITS}
        modules = {
            "system": system, "persona": "【人格设定】\n" + persona.text,
            "relationship": relation, "user_nickname": builder._build_user_nickname_prompt(row),
            "emotion": builder._build_emotion_prompt(emotion, limits) if emotion else "",
            "time_activity": await builder._build_time_prompt(round_context=context, max_tokens=10**9),
        }
    return RawChatContext(identity, config, persona, instant, MappingProxyType(context), MappingProxyType(modules),
                          core, history, tuple(current_messages), tuple(errors),
                          tuple(current_refs), tuple(source_channels))


@dataclass(frozen=True)
class SharedHistory:
    rounds: tuple[CompletedRound, ...]
    rendered_text: str
    message_ids: tuple[int, ...]
    digest: str
    rendered_tokens: int
    first_message_time: datetime | None
    last_message_time: datetime | None


@dataclass(frozen=True)
class ChatExecutionContext:
    raw: RawChatContext
    history: SharedHistory
    modules: Mapping[str, str]
    visible_background: Mapping[str, str]
    current_input: str
    current_input_start: int
    fixed_prompt_tokens: int
    retrieval_reserve: int


    @property
    def reply_input_truncated(self) -> bool:
        return self.current_input_start > 0


async def _fit_current_messages(messages, limit, counter):
    """Prefer complete newest messages, keeping newlines inside each message intact."""
    render = prompts.PromptBuilder.render_user_input
    packed = "\n".join(messages)
    if await counter.count(render(packed)) <= limit:
        return packed, render(packed), 0

    suffixes = ["\n".join(messages[i:]) for i in range(1, len(messages))]
    counts = await counter.count_many(render(text) for text in suffixes)
    for body, tokens in zip(suffixes, counts, strict=True):
        if tokens <= limit:
            return body, render(body), len(packed) - len(body)

    # A single message takes precedence over the explanatory header. If even
    # its body overflows, retain its tail and count the exact text being sent.
    latest = messages[-1] if messages else ""
    if await counter.count(latest) <= limit:
        return latest, latest, len(packed) - len(latest)
    low, high = 0, len(latest)
    while low < high:
        size = (low + high + 1) // 2
        if await counter.count(latest[-size:]) <= limit:
            low = size
        else:
            high = size - 1
    body = latest[len(latest) - low:]
    return body, body, len(packed) - len(body)


async def freeze_chat_context(raw, counter, *, deadline):
    """Select the longest complete suffix using the execution's remaining total time."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("deadline_exceeded")
    async with asyncio.timeout(remaining):
        return await _freeze(raw, counter)


async def _freeze(raw, counter):
    config = raw.config
    validate_bound_counter(config, counter)
    limits = config.prompt
    modules = dict(raw.modules)
    # Fit and verify these rendered modules using one request to the bound counter.
    measured_modules = ("system", "persona", "relationship", "emotion", "time_activity")
    await counter.count_many(modules[name] for name in measured_modules if modules[name])
    for field in ("relationship", "emotion", "time_activity"):
        text = modules[field]
        fitted = await fit_context_text(text, limits[field], counter)
        if text.startswith("【") and not fitted.partition("\n")[2].strip():
            fitted = ""
        modules[field] = fitted
    body, modules["user_input"], start = await _fit_current_messages(raw.current_messages, limits["user_input"], counter)
    fixed = await measure_rendered_budget(compose(modules), limits["max_total"], counter)
    if fixed["over_budget"]:
        # A fitted prefix must never regain text removed by its module budget.
        visible_relation = modules["relationship"]
        if raw.relationship_core and visible_relation.startswith(raw.relationship_core):
            modules["relationship"] = raw.relationship_core
        fixed = await measure_rendered_budget(compose(modules), limits["max_total"], counter)
        if fixed["over_budget"]:
            modules["time_activity"] = ""
            fixed = await measure_rendered_budget(compose(modules), limits["max_total"], counter)
        if fixed["over_budget"]:
            raise PromptBudgetExceeded(fixed)

    await check_fixed_module_budgets(modules, limits, counter)
    room = limits["max_total"] - fixed["total_charge"]
    # Titles and data notices are inside each retrieval module's budget. Only
    # the two extra inter-module separators lie outside that allocation.
    reserve = min(room, limits["memory"] + limits["character_knowledge"]
                  + 2 * await counter.count(prompts.MODULE_SEPARATOR))
    rounds = raw.history_candidates.rounds
    blocks = ["\n".join(m.render() for m in r.messages) for r in rounds]
    suffixes = [HISTORY_TITLE + "\n" + "\n".join(blocks[i:]) for i in range(len(blocks))] + [""]
    histories = await counter.count_many(suffix for suffix in suffixes if suffix)
    counts = (*histories, 0)
    viable = [(i, text) for i, text in enumerate(suffixes) if counts[i] <= limits["recent_chat"]]
    full_counts = await counter.count_many(compose({**modules, "recent_chat": text}) for _, text in viable)
    for (i, text), total in zip(viable, full_counts, strict=True):
        if total + 64 + reserve <= limits["max_total"]:
            break
    else:
        raise PromptBudgetExceeded()
    selected = rounds[i:]
    messages = [m for r in selected for m in r.messages]
    history = SharedHistory(selected, text, tuple(m.id for m in messages), hashlib.sha256(text.encode()).hexdigest(),
                            counts[i], local_time(messages[0].created_at) if messages else None,
                            local_time(messages[-1].created_at) if messages else None)
    modules["recent_chat"] = text
    background = {k: modules[k] for k in ("persona","relationship","emotion","time_activity","user_nickname") if modules[k]}
    return ChatExecutionContext(raw, history, MappingProxyType(modules), MappingProxyType(background),
                                body, start, total, reserve)

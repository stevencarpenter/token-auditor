"""Pure Codex session parsing pipeline built from reducer components."""

from collections.abc import Mapping
from dataclasses import replace
from functools import reduce
from pathlib import Path
from typing import cast

from token_auditor.core.pricing import calculate_costs, resolve_pricing_model, zero_costs
from token_auditor.core.types import AuditRecord, CodexDelta, CodexState, CostBreakdown, JsonEvent, TokenUsage
from token_auditor.core.utils import safe_int


def _mapping(value: object) -> Mapping[str, object]:
    """Return the input as a mapping when possible, otherwise an empty mapping."""
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _token_usage_from_mapping(total_usage: Mapping[str, object]) -> TokenUsage:
    """Convert a dynamic token-usage mapping into a typed immutable structure."""
    return TokenUsage(
        input_tokens=safe_int(total_usage.get("input_tokens", 0)),
        cached_input_tokens=safe_int(total_usage.get("cached_input_tokens", 0)),
        # Codex names this "cache_write_input_tokens"; the other providers say "cache_creation".
        cache_creation_input_tokens=safe_int(total_usage.get("cache_write_input_tokens", 0)),
        output_tokens=safe_int(total_usage.get("output_tokens", 0)),
        reasoning_output_tokens=safe_int(total_usage.get("reasoning_output_tokens", 0)),
        total_tokens=safe_int(total_usage.get("total_tokens", 0)),
    )


def _reasoning_effort(payload: Mapping[str, object]) -> str | None:
    """Extract reasoning effort in the same precedence order as the legacy parser."""
    collaboration_mode = _mapping(payload.get("collaboration_mode"))
    settings = _mapping(collaboration_mode.get("settings"))

    if "reasoning_effort" in settings:
        return str(settings.get("reasoning_effort"))
    if "effort" in payload:
        return str(payload.get("effort"))
    return None


def extract_codex_event_delta(event: JsonEvent) -> CodexDelta:
    """Extract a Codex reducer delta from a single decoded session event."""
    event_type = str(event.get("type", ""))

    if event_type == "session_meta":
        payload = _mapping(event.get("payload"))
        return CodexDelta(session_id=str(payload.get("id")) if "id" in payload else None)

    if event_type == "turn_context":
        payload = _mapping(event.get("payload"))
        model = str(payload.get("model")) if "model" in payload else None
        return CodexDelta(model=model, reasoning_effort=_reasoning_effort(payload))

    if event_type != "event_msg":
        return CodexDelta()

    payload = _mapping(event.get("payload"))
    if payload.get("type") == "thread_settings_applied":
        thread_settings = _mapping(payload.get("thread_settings"))
        return CodexDelta(service_tier=str(thread_settings.get("service_tier")) if "service_tier" in thread_settings else None)

    if payload.get("type") != "token_count":
        return CodexDelta()

    info = _mapping(payload.get("info"))
    total_usage = _mapping(info.get("total_token_usage"))
    if not total_usage:
        return CodexDelta()

    timestamp = str(event.get("timestamp")) if "timestamp" in event else None
    last_usage = _mapping(info.get("last_token_usage"))
    return CodexDelta(
        usage=_token_usage_from_mapping(total_usage),
        timestamp=timestamp,
        last_usage=_token_usage_from_mapping(last_usage) if last_usage else None,
    )


def _usage_costs(model: str, usage: TokenUsage, service_tier: str) -> CostBreakdown:
    """Price one usage block at a model and service tier."""
    return calculate_costs(
        provider="codex",
        pricing_model=resolve_pricing_model("codex", model),
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens,
        output_tokens=usage.output_tokens,
        reasoning_output_tokens=usage.reasoning_output_tokens,
        service_tier=service_tier,
    )


_USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_creation_input_tokens", "output_tokens", "reasoning_output_tokens")


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    """Sum two usage blocks field by field."""
    return TokenUsage(**{field: getattr(left, field) + getattr(right, field) for field in _USAGE_FIELDS})


def _fields(usage: TokenUsage) -> tuple[int, ...]:
    return tuple(getattr(usage, field) for field in _USAGE_FIELDS)


def _turn_increment(previous: TokenUsage | None, total: TokenUsage, last: TokenUsage | None) -> TokenUsage:
    """Return the usage one token_count event adds.

    Events repeat unchanged cumulative totals, which add nothing. Otherwise the event's
    last_token_usage is the increment: the cumulative total restarts after some context
    compactions, and a spawned subagent's first total includes its parent's usage. Logs
    without last_token_usage fall back to the difference between totals.
    """
    if previous is not None and _fields(total) == _fields(previous):
        return TokenUsage()
    if last is not None:
        return TokenUsage(**{field: getattr(last, field) for field in _USAGE_FIELDS})
    if previous is None or any(now < before for now, before in zip(_fields(total), _fields(previous), strict=True)):
        return TokenUsage(**{field: getattr(total, field) for field in _USAGE_FIELDS})
    return TokenUsage(**{field: getattr(total, field) - getattr(previous, field) for field in _USAGE_FIELDS})


def _add_costs(left: CostBreakdown | None, right: CostBreakdown) -> CostBreakdown:
    accumulated = left or zero_costs()
    return {key: accumulated[key] + right[key] for key in accumulated}


def _add_turn(state: CodexState, model: str, delta: CodexDelta, total: TokenUsage) -> CodexState:
    """Add one turn's usage and its cost at the current model and service tier."""
    increment = _turn_increment(state.usage, total, delta.last_usage)
    summed_usage = _add_usage(state.summed_usage or TokenUsage(), increment)
    if not model:
        return replace(state, summed_usage=summed_usage, unpriced_usage=_add_usage(state.unpriced_usage or TokenUsage(), increment))
    return replace(state, summed_usage=summed_usage, costs=_add_costs(state.costs, _usage_costs(model, increment, state.service_tier)))


def reduce_codex_state(state: CodexState, delta: CodexDelta) -> CodexState:
    """Reduce one Codex delta into a new immutable Codex parsing state."""
    model = state.model if delta.model is None else delta.model
    service_tier = state.service_tier if delta.service_tier is None else delta.service_tier
    if delta.usage is not None:
        state = _add_turn(replace(state, service_tier=service_tier), model, delta, delta.usage)
    return replace(
        state,
        session_id=state.session_id if delta.session_id is None else delta.session_id,
        model=model,
        reasoning_effort=state.reasoning_effort if delta.reasoning_effort is None else delta.reasoning_effort,
        timestamp=state.timestamp if delta.timestamp is None else delta.timestamp,
        usage=state.usage if delta.usage is None else delta.usage,
        service_tier=service_tier,
    )


def _with_total_tokens(usage: TokenUsage) -> TokenUsage:
    """Set total_tokens to input plus output, the definition Codex uses in its own totals."""
    return replace(usage, total_tokens=usage.input_tokens + usage.output_tokens)


def finalize_codex_state(state: CodexState, session_file: Path) -> AuditRecord | None:
    """Transform a reduced Codex state into the normalized audit payload shape."""
    if state.usage is None:
        return None

    usage = _with_total_tokens(state.summed_usage or state.usage)
    pricing_model = resolve_pricing_model("codex", state.model)
    if state.costs is None and state.unpriced_usage is None:
        costs = _usage_costs(state.model, usage, state.service_tier)
    else:
        costs = _add_costs(state.costs, _usage_costs(state.model, state.unpriced_usage or TokenUsage(), state.service_tier))

    return {
        "provider": "codex",
        "session_id": state.session_id,
        "session_file": str(session_file),
        "timestamp": state.timestamp,
        "model": state.model,
        "reasoning_effort": state.reasoning_effort,
        "pricing_model": pricing_model,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_output_tokens": usage.reasoning_output_tokens,
        "total_tokens": usage.total_tokens,
        "cost_source": "estimated",
        "provider_billed_total": 0.0,
        "provider_billed_unit": "",
        **costs,
    }


def parse_codex_events(events: tuple[JsonEvent, ...], session_file: Path) -> AuditRecord | None:
    """Parse decoded Codex events into an audit payload via a reducer fold."""
    deltas = (extract_codex_event_delta(event) for event in events)
    final_state = reduce(reduce_codex_state, deltas, CodexState())
    return finalize_codex_state(final_state, session_file)

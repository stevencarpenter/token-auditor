"""Unit tests for pure Codex parser reducer components."""

from pathlib import Path

import pytest

from token_auditor.core.codex import extract_codex_event_delta, finalize_codex_state, parse_codex_events, reduce_codex_state
from token_auditor.core.pricing import calculate_costs, resolve_pricing_model
from token_auditor.core.types import CodexState, TokenUsage


def test_extract_codex_event_delta_reads_session_and_turn_metadata() -> None:
    meta_delta = extract_codex_event_delta({"type": "session_meta", "payload": {"id": "session-1"}})
    context_delta = extract_codex_event_delta(
        {
            "type": "turn_context",
            "payload": {
                "model": "gpt-5.3-codex",
                "collaboration_mode": {"settings": {"reasoning_effort": "medium"}},
            },
        }
    )

    assert meta_delta.session_id == "session-1"
    assert context_delta.model == "gpt-5.3-codex"
    assert context_delta.reasoning_effort == "medium"


def test_extract_codex_event_delta_uses_effort_fallback_when_nested_setting_absent() -> None:
    delta = extract_codex_event_delta({"type": "turn_context", "payload": {"model": "gpt-5-codex", "effort": "high"}})
    assert delta.reasoning_effort == "high"


def test_extract_codex_event_delta_returns_none_effort_when_not_provided() -> None:
    delta = extract_codex_event_delta({"type": "turn_context", "payload": {"model": "gpt-5-codex"}})
    assert delta.reasoning_effort is None


def test_extract_codex_event_delta_ignores_non_token_count_event_msgs() -> None:
    delta = extract_codex_event_delta({"type": "event_msg", "payload": {"type": "tool_call"}})
    assert delta.usage is None


def test_extract_codex_event_delta_ignores_non_event_msg_types() -> None:
    assert extract_codex_event_delta({"type": "arbitrary"}).usage is None


def test_extract_codex_event_delta_ignores_empty_total_usage() -> None:
    delta = extract_codex_event_delta({"type": "event_msg", "payload": {"type": "token_count", "info": {}}})
    assert delta.usage is None


def test_reduce_codex_state_applies_only_present_delta_fields() -> None:
    initial = CodexState(session_id="a", model="gpt-5-codex", reasoning_effort="low", timestamp="t0")
    merged = reduce_codex_state(initial, extract_codex_event_delta({"type": "session_meta", "payload": {"id": "b"}}))

    assert merged.session_id == "b"
    assert merged.model == "gpt-5-codex"
    assert merged.reasoning_effort == "low"
    assert merged.timestamp == "t0"


def test_parse_codex_events_uses_last_token_count_and_pricing() -> None:
    events = (
        {"type": "session_meta", "payload": {"id": "session-123"}},
        {
            "type": "turn_context",
            "payload": {
                "model": "gpt-5-codex",
                "collaboration_mode": {"settings": {"reasoning_effort": "medium"}},
            },
        },
        {
            "timestamp": "2026-02-28T08:00:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 1,
                        "cached_input_tokens": 0,
                        "output_tokens": 2,
                        "reasoning_output_tokens": 1,
                        "total_tokens": 3,
                    }
                },
            },
        },
        {
            "timestamp": "2026-02-28T08:05:00Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 4,
                        "output_tokens": 6,
                        "reasoning_output_tokens": 2,
                        "total_tokens": 16,
                    }
                },
            },
        },
    )

    usage = parse_codex_events(events, Path("/tmp/codex.jsonl"))

    assert usage is not None
    assert usage["provider"] == "codex"
    assert usage["session_id"] == "session-123"
    assert usage["input_tokens"] == 10
    assert usage["cached_input_tokens"] == 4
    assert usage["cache_creation_input_tokens"] == 0
    assert usage["output_tokens"] == 6
    assert usage["reasoning_output_tokens"] == 2
    assert usage["total_tokens"] == 16
    assert usage["timestamp"] == "2026-02-28T08:05:00Z"
    assert usage["model"] == "gpt-5-codex"
    assert usage["reasoning_effort"] == "medium"
    assert usage["pricing_model"] == "gpt-5-codex"
    assert usage["session_total_cost_usd"] == pytest.approx(0.000068)


def test_finalize_codex_state_recomputes_total_tokens_when_missing() -> None:
    state = CodexState(
        session_id="s",
        model="gpt-5-codex",
        reasoning_effort="",
        timestamp="t",
        usage=TokenUsage(input_tokens=2, cached_input_tokens=1, output_tokens=3, total_tokens=0),
    )

    usage = finalize_codex_state(state, Path("/tmp/codex-missing-total.jsonl"))
    assert usage is not None
    assert usage["total_tokens"] == 5


def test_parse_codex_events_returns_none_when_usage_absent() -> None:
    assert parse_codex_events(({"type": "session_meta", "payload": {"id": "x"}},), Path("/tmp/no-usage.jsonl")) is None


def test_parse_codex_events_sets_zero_cost_for_unknown_models() -> None:
    usage = parse_codex_events(
        (
            {"type": "session_meta", "payload": {"id": "unknown"}},
            {"type": "turn_context", "payload": {"model": "unknown-model", "effort": "xhigh"}},
            {
                "timestamp": "2026-02-28T08:13:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 10,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                            "total_tokens": 120,
                        }
                    },
                },
            },
        ),
        Path("/tmp/unknown-model.jsonl"),
    )

    assert usage is not None
    assert usage["pricing_model"] == ""
    assert usage["session_total_cost_usd"] == 0.0


def _token_count(input_tokens: int, output_tokens: int) -> dict[str, object]:
    return {
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}},
    }


def _thread_settings(service_tier: str) -> dict[str, object]:
    return {"type": "event_msg", "payload": {"type": "thread_settings_applied", "thread_settings": {"service_tier": service_tier}}}


def test_parse_codex_events_prices_each_turn_at_its_model_and_service_tier() -> None:
    usage = parse_codex_events(
        (
            {"type": "turn_context", "payload": {"model": "gpt-5.6-luna"}},
            _token_count(1_000_000, 0),
            _token_count(1_000_000, 0),  # repeated cumulative total adds nothing
            _thread_settings("priority"),
            _token_count(2_000_000, 0),
            _thread_settings("default"),
            {"type": "turn_context", "payload": {"model": "gpt-5.5"}},
            _token_count(3_000_000, 1_000_000),
        ),
        Path("/tmp/codex-tiers.jsonl"),
    )

    assert usage is not None
    # Luna standard $0.20/M, luna priority 2x = $0.40/M, then gpt-5.5 standard $5/M in and $30/M out.
    assert usage["input_cost_usd"] == pytest.approx(0.20 + 0.40 + 5.0)
    assert usage["output_cost_usd"] == pytest.approx(30.0)
    assert usage["session_total_cost_usd"] == pytest.approx(35.60)


def test_calculate_costs_priority_tier_uses_per_model_fast_multiplier() -> None:
    fast = calculate_costs("codex", "gpt-5.5", 1_000_000, 0, 0, 1_000_000, 0, service_tier="priority")
    unlisted = calculate_costs("codex", "gpt-5.3-codex", 1_000_000, 0, 0, 1_000_000, 0, service_tier="priority")

    # gpt-5.5 Fast mode is 2.5x ($12.50 / $75); models without a Fast-mode row bill at standard.
    assert fast["session_total_cost_usd"] == pytest.approx(87.50)
    assert unlisted["session_total_cost_usd"] == pytest.approx(15.75)


def test_parse_codex_events_counts_usage_across_a_cumulative_total_restart() -> None:
    usage = parse_codex_events(
        (
            {"type": "turn_context", "payload": {"model": "gpt-5.5"}},
            _token_count(900_000, 0),
            _token_count(100_000, 0),  # totals restart after compaction
            _token_count(300_000, 0),
        ),
        Path("/tmp/codex-restart.jsonl"),
    )

    assert usage is not None
    assert usage["input_tokens"] == 1_200_000
    assert usage["total_tokens"] == 1_200_000
    assert usage["input_cost_usd"] == pytest.approx(6.0)


def test_parse_codex_events_uses_last_token_usage_for_inherited_and_early_totals() -> None:
    def count(total: int, last: int) -> dict[str, object]:
        return {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"input_tokens": total}, "last_token_usage": {"input_tokens": last}},
            },
        }

    usage = parse_codex_events(
        (
            count(80_000_000, 0),  # spawned subagent inherits its parent's total
            count(81_000_000, 1_000_000),  # logged before any turn_context
            {"type": "turn_context", "payload": {"model": "gpt-5.5"}},
            count(81_000_000, 1_000_000),  # repeated total adds nothing
            count(82_000_000, 1_000_000),
        ),
        Path("/tmp/codex-subagent.jsonl"),
    )

    assert usage is not None
    assert usage["input_tokens"] == 2_000_000
    # Both counted turns price at gpt-5.5's $5/M, including the one logged before the model.
    assert usage["input_cost_usd"] == pytest.approx(10.0)


def test_resolve_pricing_model_codex_fallback_only_strips_date_suffixes() -> None:
    assert resolve_pricing_model("codex", "gpt-5.3-codex-mini") == ""
    assert resolve_pricing_model("codex", "gpt-6-sol-mini") == ""
    assert resolve_pricing_model("codex", "gpt-5.4-mini-2026-03-17") == "gpt-5.4-mini"

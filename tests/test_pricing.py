"""Unit tests for pure pricing model resolution and cost arithmetic.

These tests cover resolution rules and billing mechanics. They deliberately do not assert the
rates in the pricing tables: those are configuration, and `git diff` shows any change to them.
"""

import pytest

from token_auditor.core.pricing import calculate_costs, is_unpriced, resolve_pricing_model, zero_costs
from token_auditor.core.utils import safe_int


def test_resolve_pricing_model_matches_direct_table_entries() -> None:
    assert resolve_pricing_model("codex", "gpt-5.3-codex") == "gpt-5.3-codex"
    assert resolve_pricing_model("claude", "claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_resolve_pricing_model_applies_alias_and_prefix_rules() -> None:
    assert resolve_pricing_model("codex", "gpt-5.1-codex-max") == "gpt-5.1-codex"
    assert resolve_pricing_model("codex", "gpt-5-codex-2026-02-14") == "gpt-5-codex"
    assert resolve_pricing_model("claude", "claude-sonnet-4-5-20250929") == "claude-sonnet-4-6"


def test_resolve_pricing_model_handles_current_fleet_models() -> None:
    # New bare codex model IDs (no -codex suffix) resolve directly.
    assert resolve_pricing_model("codex", "gpt-5.5") == "gpt-5.5"
    assert resolve_pricing_model("codex", "gpt-5.4") == "gpt-5.4"
    assert resolve_pricing_model("codex", "gpt-5.4-mini") == "gpt-5.4-mini"
    assert resolve_pricing_model("codex", "gpt-5.4-nano") == "gpt-5.4-nano"
    assert resolve_pricing_model("codex", "gpt-5.4-pro") == "gpt-5.4-pro"
    assert resolve_pricing_model("codex", "gpt-5.5-pro") == "gpt-5.5-pro"
    # Date-suffixed variants resolve to the most specific (longest) matching prefix.
    assert resolve_pricing_model("codex", "gpt-5.4-mini-2026-03-17") == "gpt-5.4-mini"
    assert resolve_pricing_model("codex", "gpt-5.4-nano-2026-03-17") == "gpt-5.4-nano"
    assert resolve_pricing_model("codex", "gpt-5.4-pro-2026-03-17") == "gpt-5.4-pro"
    assert resolve_pricing_model("codex", "gpt-5.5-pro-2026-04-01") == "gpt-5.5-pro"
    assert resolve_pricing_model("codex", "gpt-5.5-2026-04-01") == "gpt-5.5"
    assert resolve_pricing_model("codex", "gpt-5.6-sol-2026-06-26") == "gpt-5.6-sol"
    assert resolve_pricing_model("codex", "gpt-5.6-terra-2026-06-26") == "gpt-5.6-terra"
    assert resolve_pricing_model("codex", "gpt-5.6-luna-2026-06-26") == "gpt-5.6-luna"
    # Bare Claude aliases (logged for some sessions) map to the current fleet.
    assert resolve_pricing_model("claude", "fable") == "claude-fable-5-1"
    assert resolve_pricing_model("claude", "opus") == "claude-opus-5-5"
    assert resolve_pricing_model("claude", "opus[1m]") == "claude-opus-5-5"
    assert resolve_pricing_model("claude", "sonnet") == "claude-sonnet-5-5"
    assert resolve_pricing_model("claude", "haiku") == "claude-haiku-5-5"


@pytest.mark.parametrize("model", ("gpt-6-astra", "gpt-6-sol", "gpt-6.1-sol", "gpt-6-luna"))
def test_resolve_pricing_model_handles_gpt_6_family(model: str) -> None:
    assert resolve_pricing_model("codex", model) == model
    assert resolve_pricing_model("codex", f"{model}-2026-09-15") == model


@pytest.mark.parametrize(
    "model",
    (
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-sonnet-5",
        "claude-opus-5-5",
        "claude-opus-5",
        "claude-opus-4-8",
        "claude-fable-5-1",
        "claude-fable-5",
    ),
)
def test_resolve_pricing_model_handles_claude_suffixes(model: str) -> None:
    # Each model resolves directly, via its 1M-context suffix alias, and via a date-suffixed prefix.
    assert resolve_pricing_model("claude", model) == model
    assert resolve_pricing_model("claude", f"{model}[1m]") == model
    assert resolve_pricing_model("claude", f"{model}-20260901") == model


def test_resolve_pricing_model_prefix_order_keeps_longer_ids_from_falling_back() -> None:
    # The prefix table is ordered: a dated snapshot of the newer model must not match the
    # shorter prefix of its predecessor (Opus 5.5 vs 5, Sonnet 5.5 vs 5, Fable 5.1 vs 5), and
    # Opus 5 must not swallow the 4.x ids.
    assert resolve_pricing_model("claude", "claude-opus-5-5-20260915") == "claude-opus-5-5"
    assert resolve_pricing_model("claude", "claude-opus-5-20260715") == "claude-opus-5"
    assert resolve_pricing_model("claude", "claude-sonnet-5-5-20260928") == "claude-sonnet-5-5"
    assert resolve_pricing_model("claude", "claude-sonnet-5-20260701") == "claude-sonnet-5"
    assert resolve_pricing_model("claude", "claude-fable-5-1-20260901") == "claude-fable-5-1"
    assert resolve_pricing_model("claude", "claude-fable-5-20260609") == "claude-fable-5"
    assert resolve_pricing_model("claude", "claude-haiku-4-5-20251001") == "claude-haiku-4-5"
    for model in ("claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6"):
        assert resolve_pricing_model("claude", model) == model


def test_resolve_pricing_model_returns_empty_for_unknown_or_blank_models() -> None:
    assert resolve_pricing_model("codex", "") == ""
    assert resolve_pricing_model("claude", "unknown-model") == ""


def test_calculate_costs_for_codex_subtracts_cached_and_cache_creation_from_input() -> None:
    costs = calculate_costs(
        provider="codex",
        pricing_model="gpt-5.3-codex",
        input_tokens=4045228,
        cached_input_tokens=3780608,
        cache_creation_input_tokens=0,
        output_tokens=24495,
        reasoning_output_tokens=12415,
    )

    assert costs["input_cost_usd"] == pytest.approx(0.463085)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.6616064)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.0)
    assert costs["output_cost_usd"] == pytest.approx(0.16912)
    assert costs["reasoning_output_cost_usd"] == pytest.approx(0.17381)
    assert costs["session_total_cost_usd"] == pytest.approx(1.4676214)


def test_calculate_costs_for_claude_uses_direct_input_tokens() -> None:
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-haiku-4-5",
        input_tokens=36,
        cached_input_tokens=165811,
        cache_creation_input_tokens=62198,
        output_tokens=1357,
        reasoning_output_tokens=0,
    )

    assert costs["input_cost_usd"] == pytest.approx(0.000036)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.0165811)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.0777475)
    assert costs["output_cost_usd"] == pytest.approx(0.006785)
    assert costs["reasoning_output_cost_usd"] == pytest.approx(0.0)
    assert costs["session_total_cost_usd"] == pytest.approx(0.1011496)


def test_calculate_costs_bills_1h_cache_writes_at_2x_input() -> None:
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-5-5",
        input_tokens=0,
        cached_input_tokens=0,
        cache_creation_input_tokens=1_000_000,
        output_tokens=0,
        reasoning_output_tokens=0,
        cache_creation_1h_input_tokens=600_000,
    )

    # 400K 5-minute writes at $5/M + 600K 1-hour writes at 2 x $4/M.
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(2.0 + 4.8)


def test_calculate_costs_returns_zero_breakdown_for_unknown_pricing_models() -> None:
    assert (
        calculate_costs(
            provider="claude",
            pricing_model="",
            input_tokens=1,
            cached_input_tokens=2,
            cache_creation_input_tokens=3,
            output_tokens=4,
            reasoning_output_tokens=0,
        )
        == zero_costs()
    )


def test_safe_int_handles_invalid_inputs() -> None:
    assert safe_int("42") == 42
    assert safe_int(object()) == 0


def test_calculate_costs_long_context_selects_the_long_context_table_only_where_one_exists() -> None:
    def total(model: str, long_context: bool) -> float:
        costs = calculate_costs("claude", model, 1000, 500_000, 100_000, 5000, 0, long_context=long_context)
        return costs["session_total_cost_usd"]

    # Haiku 5.5 has a real long-context tier, so long_context=True costs more.
    assert total("claude-haiku-5-5", True) > total("claude-haiku-5-5", False)
    # Models that bill the full window at standard rates mirror the standard table.
    assert total("claude-opus-4-6", True) == pytest.approx(total("claude-opus-4-6", False))
    # A model absent from the long-context table falls back to its standard rates.
    assert total("claude-haiku-4-5", True) == pytest.approx(total("claude-haiku-4-5", False))


def test_is_unpriced_flags_estimated_audits_whose_model_has_no_table_entry() -> None:
    assert is_unpriced({"model": "codex-auto-review", "pricing_model": "", "cost_source": "estimated"}) is True


def test_is_unpriced_ignores_priced_provider_billed_and_modelless_audits() -> None:
    # A resolved pricing model is priced.
    assert is_unpriced({"model": "gpt-6-astra", "pricing_model": "gpt-6-astra", "cost_source": "estimated"}) is False
    # OpenCode/Claude billed audits carry an authoritative total and need no pricing model.
    assert is_unpriced({"model": "anything", "pricing_model": "", "cost_source": "provider_billed"}) is False
    # No model means nothing to look up, so there is nothing to warn about.
    assert is_unpriced({"model": "", "pricing_model": "", "cost_source": "estimated"}) is False

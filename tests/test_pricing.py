"""Unit tests for pure pricing model resolution and cost arithmetic."""

import pytest

from token_auditor.core.constants import FAST_MODE_PRICING_USD_PER_1M, TOKEN_PRICING_USD_PER_1M
from token_auditor.core.pricing import calculate_costs, is_unpriced, resolve_pricing_model, zero_costs
from token_auditor.core.utils import safe_int


def test_resolve_pricing_model_matches_direct_table_entries() -> None:
    assert resolve_pricing_model("codex", "gpt-5.3-codex") == "gpt-5.3-codex"
    assert resolve_pricing_model("claude", "claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_resolve_pricing_model_applies_alias_and_prefix_rules() -> None:
    assert resolve_pricing_model("codex", "gpt-5.3-codex-mini") == "gpt-5.2-codex-mini"
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
    assert resolve_pricing_model("claude", "opus") == "claude-opus-5"
    assert resolve_pricing_model("claude", "opus[1m]") == "claude-opus-5"
    assert resolve_pricing_model("claude", "sonnet") == "claude-sonnet-5"
    assert resolve_pricing_model("claude", "haiku") == "claude-haiku-4-5"


def test_resolve_pricing_model_handles_sonnet_5() -> None:
    # Sonnet 5 resolves directly, via its 1M-context suffix alias, and via a date-suffixed prefix.
    assert resolve_pricing_model("claude", "claude-sonnet-5") == "claude-sonnet-5"
    assert resolve_pricing_model("claude", "claude-sonnet-5[1m]") == "claude-sonnet-5"
    assert resolve_pricing_model("claude", "claude-sonnet-5-20260701") == "claude-sonnet-5"


def test_calculate_costs_for_sonnet_5_uses_introductory_rates() -> None:
    # platform.claude.com: Sonnet 5 introductory (through 2026-08-31) = $2 input /
    # $0.20 cache read / $2.50 5-min cache write / $10 output per MTok.
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-sonnet-5",
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )

    assert costs["input_cost_usd"] == pytest.approx(2.00)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.20)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(2.50)
    assert costs["output_cost_usd"] == pytest.approx(10.00)
    assert costs["session_total_cost_usd"] == pytest.approx(14.70)


def test_calculate_costs_sonnet_5_long_context_matches_standard_mode() -> None:
    # Sonnet 5 includes the full 1M context window at base pricing (no >200K surcharge),
    # so long_context=True yields the same costs as long_context=False.
    standard = calculate_costs(
        provider="claude",
        pricing_model="claude-sonnet-5",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=False,
    )
    long_context = calculate_costs(
        provider="claude",
        pricing_model="claude-sonnet-5",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=True,
    )

    assert long_context == standard
    # input=$0.002, cached=$0.10, cache_creation=$0.25, output=$0.05 → total=$0.402
    assert long_context["session_total_cost_usd"] == pytest.approx(0.402)


def test_calculate_costs_for_gpt_5_4_nano_uses_verified_rates() -> None:
    # developers.openai.com: gpt-5.4-nano = $0.20 input / $0.02 cached input / $1.25 output
    # per MTok. Codex billable input = input - cached - cache_creation.
    costs = calculate_costs(
        provider="codex",
        pricing_model="gpt-5.4-nano",
        input_tokens=2_000_000,
        cached_input_tokens=1_000_000,
        cache_creation_input_tokens=0,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )

    assert costs["input_cost_usd"] == pytest.approx(0.20)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.02)
    assert costs["output_cost_usd"] == pytest.approx(1.25)
    assert costs["session_total_cost_usd"] == pytest.approx(1.47)


def test_calculate_costs_for_pro_tiers_bill_cached_input_at_full_rate() -> None:
    # developers.openai.com: gpt-5.4-pro / gpt-5.5-pro = $30 input / $180 output per MTok
    # with prompt caching unsupported — cached tokens (which should never appear in pro
    # session logs) carry no discount and bill at the full input rate.
    for pricing_model in ("gpt-5.4-pro", "gpt-5.5-pro"):
        costs = calculate_costs(
            provider="codex",
            pricing_model=pricing_model,
            input_tokens=2_000_000,
            cached_input_tokens=1_000_000,
            cache_creation_input_tokens=0,
            output_tokens=1_000_000,
            reasoning_output_tokens=0,
        )

        assert costs["input_cost_usd"] == pytest.approx(30.00)
        assert costs["cached_input_cost_usd"] == pytest.approx(30.00)
        assert costs["output_cost_usd"] == pytest.approx(180.00)
        assert costs["session_total_cost_usd"] == pytest.approx(240.00)


def test_resolve_pricing_model_handles_opus_5() -> None:
    # Opus 5 resolves directly, via its 1M-context suffix alias, and via a date-suffixed prefix.
    assert resolve_pricing_model("claude", "claude-opus-5") == "claude-opus-5"
    assert resolve_pricing_model("claude", "claude-opus-5[1m]") == "claude-opus-5"
    assert resolve_pricing_model("claude", "claude-opus-5-20260715") == "claude-opus-5"


def test_resolve_pricing_model_opus_5_prefix_does_not_shadow_opus_4_x() -> None:
    # "claude-opus-5" must not be reachable as a prefix of the 4.x ids, and vice versa; the
    # prefix table is ordered, so this pins that Opus 5 does not swallow Opus 4.8/4.7/4.6.
    assert resolve_pricing_model("claude", "claude-opus-4-8") == "claude-opus-4-8"
    assert resolve_pricing_model("claude", "claude-opus-4-7") == "claude-opus-4-7"
    assert resolve_pricing_model("claude", "claude-opus-4-6") == "claude-opus-4-6"


def test_calculate_costs_for_opus_5_uses_verified_standard_rates() -> None:
    # platform.claude.com: Opus 5 ships as a drop-in upgrade at Opus 4.8's pricing —
    # $5 input / $0.50 cache read / $6.25 5m cache write / $25 output per MTok.
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-5",
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )

    assert costs["input_cost_usd"] == pytest.approx(5.00)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.50)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(6.25)
    assert costs["output_cost_usd"] == pytest.approx(25.00)
    assert costs["session_total_cost_usd"] == pytest.approx(36.75)


def test_calculate_costs_opus_5_long_context_bills_flat_standard_rates() -> None:
    # Opus 5 provides the full 1M context window as both default and maximum at standard
    # pricing (no >200K surcharge), so long_context=True yields the same costs as standard.
    standard = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-5",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=False,
    )
    long_context = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-5",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=True,
    )

    assert long_context == standard
    assert long_context["session_total_cost_usd"] == pytest.approx(1.005)


def test_resolve_pricing_model_handles_opus_4_8() -> None:
    # Opus 4.8 resolves directly, via its 1M-context suffix alias, and via a date-suffixed prefix.
    assert resolve_pricing_model("claude", "claude-opus-4-8") == "claude-opus-4-8"
    assert resolve_pricing_model("claude", "claude-opus-4-8[1m]") == "claude-opus-4-8"
    assert resolve_pricing_model("claude", "claude-opus-4-8-20260528") == "claude-opus-4-8"


def test_calculate_costs_for_opus_4_8_uses_verified_standard_rates() -> None:
    # platform.claude.com: Opus 4.8 standard = $5 input / $0.50 cache read / $6.25 5m cache
    # write / $25 output per MTok — unchanged from Opus 4.5/4.6/4.7.
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-4-8",
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )

    assert costs["input_cost_usd"] == pytest.approx(5.00)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.50)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(6.25)
    assert costs["output_cost_usd"] == pytest.approx(25.00)
    assert costs["session_total_cost_usd"] == pytest.approx(36.75)


def test_calculate_costs_opus_4_8_long_context_bills_flat_standard_rates() -> None:
    # Opus 4.8 includes the full 1M context window at standard pricing (no >200K surcharge),
    # so long_context=True yields the same costs as standard.
    standard = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-4-8",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=False,
    )
    long_context = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-4-8",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=True,
    )

    assert long_context == standard
    assert long_context["session_total_cost_usd"] == pytest.approx(1.005)


def test_resolve_pricing_model_handles_fable_5() -> None:
    # Fable 5 resolves directly, via its 1M-context suffix alias, and via a date-suffixed prefix.
    assert resolve_pricing_model("claude", "claude-fable-5") == "claude-fable-5"
    assert resolve_pricing_model("claude", "claude-fable-5[1m]") == "claude-fable-5"
    assert resolve_pricing_model("claude", "claude-fable-5-20260609") == "claude-fable-5"


def test_calculate_costs_for_fable_5_uses_verified_standard_rates() -> None:
    # platform.claude.com: Fable 5 standard = $10 input / $1 cache read / $12.50 5m cache
    # write / $50 output per MTok.
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-fable-5",
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )

    assert costs["input_cost_usd"] == pytest.approx(10.00)
    assert costs["cached_input_cost_usd"] == pytest.approx(1.00)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(12.50)
    assert costs["output_cost_usd"] == pytest.approx(50.00)
    assert costs["session_total_cost_usd"] == pytest.approx(73.50)


def test_calculate_costs_fable_5_long_context_bills_flat_standard_rates() -> None:
    # Fable 5 includes the full 1M context window at standard pricing (no >200K surcharge),
    # so long_context=True yields the same costs as standard.
    standard = calculate_costs(
        provider="claude",
        pricing_model="claude-fable-5",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=False,
    )
    long_context = calculate_costs(
        provider="claude",
        pricing_model="claude-fable-5",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=True,
    )

    assert long_context == standard
    # input=$0.01, cached=$0.50, cache_creation=$1.25, output=$0.25 → total=$2.01
    assert long_context["session_total_cost_usd"] == pytest.approx(2.01)


def test_fast_mode_pricing_table_values_match_documented_multipliers() -> None:
    # FAST_MODE_PRICING_USD_PER_1M is not wired into computation, so a typo in its rates would
    # otherwise pass CI silently: the dict is line-covered on import but its values are never
    # exercised by calculate_costs. Pin every entry to the documented multipliers so a bad number
    # fails loudly. Per-tier standard multiplier: Opus 4.8 fast mode is 2x standard (the headline
    # of the 4.8 release); the 4.6/4.7 fast tier is 6x. Within each tier, cache read is 0.1x and
    # the 5-minute cache write is 1.25x of that tier's fast input rate.
    expected_standard_multiplier = {
        "claude-opus-5": 2.0,
        "claude-opus-4-8": 2.0,
        "claude-opus-4-7": 6.0,
        "claude-opus-4-6": 6.0,
    }
    # A new fast-mode entry must declare its expected multiplier here, or this assertion fails —
    # values can never be added to the table without a deliberate test update.
    assert set(FAST_MODE_PRICING_USD_PER_1M) == set(expected_standard_multiplier)

    for model, multiplier in expected_standard_multiplier.items():
        fast = FAST_MODE_PRICING_USD_PER_1M[model]
        standard = TOKEN_PRICING_USD_PER_1M["claude"][model]

        assert fast["input_tokens"] == pytest.approx(multiplier * standard["input_tokens"])
        assert fast["output_tokens"] == pytest.approx(multiplier * standard["output_tokens"])
        assert fast["cached_input_tokens"] == pytest.approx(0.1 * fast["input_tokens"])
        assert fast["cache_creation_input_tokens"] == pytest.approx(1.25 * fast["input_tokens"])


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


def test_calculate_costs_for_gpt_5_5_uses_premium_codex_rates() -> None:
    costs = calculate_costs(
        provider="codex",
        pricing_model="gpt-5.5",
        input_tokens=1_000_000,
        cached_input_tokens=200_000,
        cache_creation_input_tokens=0,
        output_tokens=100_000,
        reasoning_output_tokens=40_000,
    )

    # gpt-5.5: input $5/M, cached $0.50/M, output $30/M. Billable input = 1M - 200K = 800K.
    assert costs["input_cost_usd"] == pytest.approx(4.0)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.1)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.0)
    assert costs["output_cost_usd"] == pytest.approx(1.8)
    assert costs["reasoning_output_cost_usd"] == pytest.approx(1.2)
    assert costs["session_total_cost_usd"] == pytest.approx(7.1)


def test_calculate_costs_for_gpt_5_4_family_uses_current_rates() -> None:
    full = calculate_costs(
        provider="codex",
        pricing_model="gpt-5.4",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        cache_creation_input_tokens=0,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )
    # gpt-5.4: input $2.50/M, output $15/M.
    assert full["input_cost_usd"] == pytest.approx(2.5)
    assert full["output_cost_usd"] == pytest.approx(15.0)
    assert full["session_total_cost_usd"] == pytest.approx(17.5)

    mini = calculate_costs(
        provider="codex",
        pricing_model="gpt-5.4-mini",
        input_tokens=1_000_000,
        cached_input_tokens=100_000,
        cache_creation_input_tokens=0,
        output_tokens=200_000,
        reasoning_output_tokens=0,
    )
    # gpt-5.4-mini: input $0.75/M, cached $0.075/M, output $4.50/M. Billable input = 900K.
    assert mini["input_cost_usd"] == pytest.approx(0.675)
    assert mini["cached_input_cost_usd"] == pytest.approx(0.0075)
    assert mini["output_cost_usd"] == pytest.approx(0.9)
    assert mini["session_total_cost_usd"] == pytest.approx(1.5825)


@pytest.mark.parametrize(
    ("model", "input_rate", "output_rate"),
    (
        ("gpt-5.6-sol", 4.0, 20.0),
        ("gpt-5.6-terra", 2.0, 12.0),
        ("gpt-5.6-luna", 0.2, 1.2),
    ),
)
def test_calculate_costs_for_gpt_5_6_family_uses_promotional_rates(model: str, input_rate: float, output_rate: float) -> None:
    costs = calculate_costs(
        provider="codex",
        pricing_model=model,
        input_tokens=1_000_000,
        cached_input_tokens=100_000,
        cache_creation_input_tokens=100_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=200_000,
    )

    # GPT-5.6: cache reads are 0.1x input and cache writes are 1.25x input.
    assert costs["input_cost_usd"] == pytest.approx(0.8 * input_rate)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.1 * 0.1 * input_rate)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.1 * 1.25 * input_rate)
    assert costs["output_cost_usd"] == pytest.approx(0.8 * output_rate)
    assert costs["reasoning_output_cost_usd"] == pytest.approx(0.2 * output_rate)
    assert costs["session_total_cost_usd"] == pytest.approx(0.935 * input_rate + output_rate)


def test_resolve_pricing_model_handles_fable_5_1() -> None:
    assert resolve_pricing_model("claude", "claude-fable-5-1") == "claude-fable-5-1"
    assert resolve_pricing_model("claude", "claude-fable-5-1[1m]") == "claude-fable-5-1"
    assert resolve_pricing_model("claude", "fable") == "claude-fable-5-1"


def test_resolve_pricing_model_fable_5_1_prefix_does_not_fall_back_to_fable_5() -> None:
    # A dated Fable 5.1 snapshot must not match the shorter "claude-fable-5" prefix,
    # which would price its cache reads at $1.00/MTok instead of $0.25/MTok.
    assert resolve_pricing_model("claude", "claude-fable-5-1-20260901") == "claude-fable-5-1"
    assert resolve_pricing_model("claude", "claude-fable-5-20260609") == "claude-fable-5"


def test_calculate_costs_for_fable_5_1_uses_reduced_cache_read_rate() -> None:
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-fable-5-1",
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=0,
    )

    # Cache reads are 0.025x the $10/M base input rate, not the usual 0.1x.
    assert costs["cached_input_cost_usd"] == pytest.approx(0.25)
    assert costs["input_cost_usd"] == pytest.approx(10.0)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(12.5)
    assert costs["output_cost_usd"] == pytest.approx(50.0)


def test_openrouter_pricing_covers_models_seen_in_opencode_and_pi_sessions() -> None:
    openrouter = TOKEN_PRICING_USD_PER_1M["openrouter"]
    for model in ("z-ai/glm-5.3-flash", "moonshotai/kimi-k3", "deepseek/deepseek-v4-pro-0813", "~anthropic/claude-fable-latest"):
        assert model in openrouter
    assert openrouter["thinkingmachines/inkling:free"]["output_tokens"] == 0.0


def test_resolve_pricing_model_handles_gpt_6_astra() -> None:
    assert resolve_pricing_model("codex", "gpt-6-astra") == "gpt-6-astra"
    assert resolve_pricing_model("codex", "gpt-6-astra-2026-09-03") == "gpt-6-astra"


def test_calculate_costs_for_gpt_6_astra_uses_standard_rates() -> None:
    costs = calculate_costs(
        provider="codex",
        pricing_model="gpt-6-astra",
        input_tokens=1_000_000,
        cached_input_tokens=100_000,
        cache_creation_input_tokens=100_000,
        output_tokens=1_000_000,
        reasoning_output_tokens=200_000,
    )

    # $10/M input, 0.1x cache read, 1.25x cache write, $50/M output. Billable input = 800K.
    assert costs["input_cost_usd"] == pytest.approx(8.0)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.1)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(1.25)
    assert costs["output_cost_usd"] == pytest.approx(40.0)
    assert costs["reasoning_output_cost_usd"] == pytest.approx(10.0)
    assert costs["session_total_cost_usd"] == pytest.approx(59.35)


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


def test_calculate_costs_long_context_now_bills_flat_standard_rates() -> None:
    # As of Opus 4.6/4.7 and Sonnet 4.6, the full 1M context bills at standard rates,
    # so long_context=True yields the same costs as standard (no >200K premium).
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-4-6",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=True,
    )

    # Standard Opus: input=$5/M, cached=$0.5/M, cache_creation=$6.25/M, output=$25/M
    assert costs["input_cost_usd"] == pytest.approx(0.005)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.25)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.625)
    assert costs["output_cost_usd"] == pytest.approx(0.125)
    assert costs["session_total_cost_usd"] == pytest.approx(1.005)


def test_calculate_costs_long_context_falls_back_for_haiku() -> None:
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-haiku-4-5",
        input_tokens=36,
        cached_input_tokens=165811,
        cache_creation_input_tokens=62198,
        output_tokens=1357,
        reasoning_output_tokens=0,
        long_context=True,
    )

    # Haiku has no long context tier — falls back to standard rates
    assert costs["input_cost_usd"] == pytest.approx(0.000036)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.0165811)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.0777475)
    assert costs["output_cost_usd"] == pytest.approx(0.006785)
    assert costs["session_total_cost_usd"] == pytest.approx(0.1011496)


def test_calculate_costs_long_context_false_uses_standard_rates() -> None:
    costs = calculate_costs(
        provider="claude",
        pricing_model="claude-opus-4-6",
        input_tokens=1000,
        cached_input_tokens=500_000,
        cache_creation_input_tokens=100_000,
        output_tokens=5000,
        reasoning_output_tokens=0,
        long_context=False,
    )

    # Standard Opus: input=$5/M, cached=$0.5/M, cache_creation=$6.25/M, output=$25/M
    assert costs["input_cost_usd"] == pytest.approx(0.005)
    assert costs["cached_input_cost_usd"] == pytest.approx(0.25)
    assert costs["cache_creation_input_cost_usd"] == pytest.approx(0.625)
    assert costs["output_cost_usd"] == pytest.approx(0.125)
    assert costs["session_total_cost_usd"] == pytest.approx(1.005)


def test_is_unpriced_flags_estimated_audits_whose_model_has_no_table_entry() -> None:
    assert is_unpriced({"model": "codex-auto-review", "pricing_model": "", "cost_source": "estimated"}) is True


def test_is_unpriced_ignores_priced_provider_billed_and_modelless_audits() -> None:
    # A resolved pricing model is priced.
    assert is_unpriced({"model": "gpt-6-astra", "pricing_model": "gpt-6-astra", "cost_source": "estimated"}) is False
    # OpenCode/Claude billed audits carry an authoritative total and need no pricing model.
    assert is_unpriced({"model": "anything", "pricing_model": "", "cost_source": "provider_billed"}) is False
    # No model means nothing to look up, so there is nothing to warn about.
    assert is_unpriced({"model": "", "pricing_model": "", "cost_source": "estimated"}) is False

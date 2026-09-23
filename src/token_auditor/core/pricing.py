"""Pure pricing model resolution and cost arithmetic for token_auditor."""

import re

from token_auditor.core.constants import (
    CACHE_WRITE_1HR_MULTIPLIER,
    CODEX_FAST_MODE_MULTIPLIER,
    DATA_RESIDENCY_MULTIPLIER,
    FAST_MODE_PRICING_USD_PER_1M,
    LONG_CONTEXT_PRICING_USD_PER_1M,
    MODEL_PRICING_ALIASES,
    MODEL_PRICING_PREFIX_ALIASES,
    TOKEN_PRICING_USD_PER_1M,
)
from token_auditor.core.types import AuditRecord, CostBreakdown


def resolve_pricing_model(provider: str, model: str) -> str:
    """Resolve a raw model identifier to a canonical pricing table key."""
    normalized = model.strip().lower()
    if not normalized:
        return ""

    provider_pricing = TOKEN_PRICING_USD_PER_1M.get(provider, {})
    if normalized in provider_pricing:
        return normalized

    provider_aliases = MODEL_PRICING_ALIASES.get(provider, {})
    if normalized in provider_aliases:
        return provider_aliases[normalized]

    for prefix, target in MODEL_PRICING_PREFIX_ALIASES.get(provider, ()):  # pragma: no branch
        if normalized.startswith(prefix):
            return target

    if provider == "codex":
        # Only a dated snapshot ("gpt-5.4-mini-2026-03-17") inherits its base model's rates.
        # Any other suffix ("-mini", "-pro") names a differently priced model.
        base, dated = re.subn(r"-\d{4}-\d{2}-\d{2}$", "", normalized)
        if dated and base in provider_pricing:
            return base

    return ""


def zero_costs() -> CostBreakdown:
    """Return a zero-valued cost breakdown preserving expected output keys."""
    return {
        "input_cost_usd": 0.0,
        "cached_input_cost_usd": 0.0,
        "cache_creation_input_cost_usd": 0.0,
        "output_cost_usd": 0.0,
        "reasoning_output_cost_usd": 0.0,
        "session_total_cost_usd": 0.0,
    }


def calculate_costs(
    provider: str,
    pricing_model: str,
    input_tokens: int,
    cached_input_tokens: int,
    cache_creation_input_tokens: int,
    output_tokens: int,
    reasoning_output_tokens: int,
    long_context: bool = False,
    cache_creation_1h_input_tokens: int = 0,
    service_tier: str = "",
    speed: str = "",
    inference_geo: str = "",
) -> CostBreakdown:
    """Compute session cost components using provider-specific billing rules."""
    provider_pricing = TOKEN_PRICING_USD_PER_1M.get(provider, {})
    # Claude fast mode pricing covers the full context window, so it takes precedence.
    if speed == "fast" and provider == "claude" and pricing_model in FAST_MODE_PRICING_USD_PER_1M:
        pricing = FAST_MODE_PRICING_USD_PER_1M[pricing_model]
    elif long_context and provider == "claude" and pricing_model in LONG_CONTEXT_PRICING_USD_PER_1M:
        pricing = LONG_CONTEXT_PRICING_USD_PER_1M[pricing_model]
    elif pricing_model not in provider_pricing:
        return zero_costs()
    else:
        pricing = provider_pricing[pricing_model]
    if provider == "codex" and service_tier == "priority" and pricing_model in CODEX_FAST_MODE_MULTIPLIER:
        pricing = {key: rate * CODEX_FAST_MODE_MULTIPLIER[pricing_model] for key, rate in pricing.items()}
    if provider == "claude" and inference_geo == "us":
        pricing = {key: rate * DATA_RESIDENCY_MULTIPLIER for key, rate in pricing.items()}

    billable_input_tokens = max(0, input_tokens - cached_input_tokens - cache_creation_input_tokens) if provider == "codex" else max(0, input_tokens)
    non_reasoning_output_tokens = max(0, output_tokens - reasoning_output_tokens)

    input_cost = billable_input_tokens * (pricing["input_tokens"] / 1_000_000)
    cached_input_cost = cached_input_tokens * (pricing["cached_input_tokens"] / 1_000_000)
    # 1-hour cache writes bill at 2x input; the table's cache-write rate is the 5-minute 1.25x rate.
    cache_creation_1h_tokens = min(max(0, cache_creation_1h_input_tokens), cache_creation_input_tokens)
    cache_creation_input_cost = (cache_creation_input_tokens - cache_creation_1h_tokens) * (pricing["cache_creation_input_tokens"] / 1_000_000) + cache_creation_1h_tokens * (
        pricing["input_tokens"] * CACHE_WRITE_1HR_MULTIPLIER / 1_000_000
    )
    output_cost = non_reasoning_output_tokens * (pricing["output_tokens"] / 1_000_000)
    reasoning_output_cost = reasoning_output_tokens * (pricing["output_tokens"] / 1_000_000)
    session_total_cost = input_cost + cached_input_cost + cache_creation_input_cost + output_cost + reasoning_output_cost

    return {
        "input_cost_usd": input_cost,
        "cached_input_cost_usd": cached_input_cost,
        "cache_creation_input_cost_usd": cache_creation_input_cost,
        "output_cost_usd": output_cost,
        "reasoning_output_cost_usd": reasoning_output_cost,
        "session_total_cost_usd": session_total_cost,
    }


def is_unpriced(audit: AuditRecord) -> bool:
    """Report whether an audit names a model that no pricing table entry covers.

    ``calculate_costs`` returns zeros for an unresolved model, which renders
    identically to a genuinely free session. This distinguishes the two so the
    caller can say so instead of printing a silent $0.00. Provider-billed audits
    carry an authoritative total and never need a pricing model, so they are
    never unpriced.
    """
    if str(audit.get("cost_source", "")) != "estimated":
        return False
    return bool(str(audit.get("model", ""))) and not str(audit.get("pricing_model", ""))

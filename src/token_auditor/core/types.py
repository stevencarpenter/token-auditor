"""Immutable types used by token_auditor core pipelines."""

from dataclasses import dataclass

type AuditValue = str | int | float
type AuditRecord = dict[str, AuditValue]
type JsonEvent = dict[str, object]
type CostBreakdown = dict[str, float]


class SessionParseError(Exception):
    """Signal that a session JSONL transcript cannot be decoded into valid events."""


@dataclass(frozen=True)
class TokenUsage:
    """Normalized usage totals for a single message, event, or aggregate rollup."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    # Subset of cache_creation_input_tokens written with the 1-hour TTL (Claude only).
    cache_creation_1h_input_tokens: int = 0


@dataclass(frozen=True)
class CodexDelta:
    """Partial update extracted from one Codex event."""

    session_id: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    timestamp: str | None = None
    usage: TokenUsage | None = None
    service_tier: str | None = None
    last_usage: TokenUsage | None = None


@dataclass(frozen=True)
class CodexState:
    """Reducer state for Codex event folds."""

    session_id: str = ""
    model: str = ""
    reasoning_effort: str = ""
    timestamp: str = ""
    usage: TokenUsage | None = None
    service_tier: str = ""
    # Usage and costs summed turn by turn; each turn is priced at the model and service tier
    # active for it. usage above is the latest cumulative total, which can reset mid-session.
    summed_usage: TokenUsage | None = None
    costs: CostBreakdown | None = None
    # Usage logged before any turn_context names a model; priced at the final model.
    unpriced_usage: TokenUsage | None = None


@dataclass(frozen=True)
class ClaudeMessageSnapshot:
    """Normalized snapshot for one Claude assistant message usage entry."""

    message_id: str
    model: str
    timestamp: str
    usage: TokenUsage
    speed: str = ""
    inference_geo: str = ""

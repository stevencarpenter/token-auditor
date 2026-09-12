"""Pure OpenCode session parsing and aggregation helpers."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from token_auditor.core.pricing import calculate_costs, resolve_pricing_model, zero_costs
from token_auditor.core.types import AuditRecord, JsonEvent
from token_auditor.core.utils import safe_float, safe_int


@dataclass(frozen=True)
class OpencodeUsageRow:
    """Normalized OpenCode assistant usage snapshot from one DB message row."""

    session_id: str
    time_created: int
    timestamp: str
    provider: str
    model: str
    cwd: str
    root: str
    input_tokens: int
    cached_input_tokens: int
    cache_creation_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int
    cost_usd: float


def _mapping(value: object) -> Mapping[str, object]:
    """Return the input as a mapping when possible, otherwise an empty mapping."""
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _normalize_path_text(value: str) -> str:
    """Normalize path strings for stable prefix comparisons across platforms."""
    normalized = value.strip().replace("\\", "/")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized


def _is_path_prefix(prefix: str, path: str) -> bool:
    """Return whether ``prefix`` is an equal-or-parent path of ``path``."""
    prefix_norm = _normalize_path_text(prefix)
    path_norm = _normalize_path_text(path)
    if not prefix_norm or not path_norm:
        return False
    if prefix_norm == "/":
        return True
    return path_norm == prefix_norm or path_norm.startswith(f"{prefix_norm}/")


def extract_opencode_usage_row(row: JsonEvent) -> OpencodeUsageRow | None:
    """Extract one normalized OpenCode usage row from a raw DB row payload."""
    data = _mapping(row.get("data"))
    if data.get("role") != "assistant":
        return None

    tokens = _mapping(data.get("tokens"))
    if not tokens:
        return None

    cache = _mapping(tokens.get("cache"))
    input_tokens = safe_int(tokens.get("input", 0))
    output_tokens = safe_int(tokens.get("output", 0))
    reasoning_output_tokens = safe_int(tokens.get("reasoning", 0))
    cached_input_tokens = safe_int(cache.get("read", 0))
    cache_creation_input_tokens = safe_int(cache.get("write", 0))

    if "total" in tokens and tokens.get("total") is not None:
        total_tokens = safe_int(tokens.get("total"))
    else:
        total_tokens = input_tokens + output_tokens + reasoning_output_tokens + cached_input_tokens + cache_creation_input_tokens

    time = _mapping(data.get("time"))
    path = _mapping(data.get("path"))

    return OpencodeUsageRow(
        session_id=str(row.get("session_id", "")),
        time_created=safe_int(row.get("time_created", 0)),
        timestamp=str(time.get("completed", "")),
        provider=str(data.get("providerID", "")),
        model=str(data.get("modelID", "")),
        cwd=str(path.get("cwd", "")),
        root=str(path.get("root", "")),
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        total_tokens=total_tokens,
        cost_usd=safe_float(data.get("cost", 0.0)),
    )


def _is_cwd_match(row: OpencodeUsageRow, cwd: Path) -> bool:
    """Return whether the row belongs to the requested workspace path."""
    cwd_text = str(cwd)
    return _is_path_prefix(cwd_text, row.cwd) or _is_path_prefix(cwd_text, row.root) or _is_path_prefix(row.cwd, cwd_text) or _is_path_prefix(row.root, cwd_text)


def choose_opencode_session_id(rows: tuple[OpencodeUsageRow, ...], cwd: Path) -> str:
    """Choose the OpenCode session id using cwd match first, then global recency."""
    if not rows:
        return ""

    matching = tuple(row for row in rows if _is_cwd_match(row, cwd))
    pool = matching or rows
    latest_row = max(pool, key=lambda row: row.time_created)
    return latest_row.session_id


def estimate_opencode_row_cost(row: OpencodeUsageRow) -> float:
    """Estimate one OpenCode row's cost from the rate table, or 0.0 when unpriced.

    Only used as a fallback for rows the OpenCode DB reports no cost for. OpenRouter
    routes each request to whichever upstream endpoint is available, and those endpoints
    charge different rates, so a single per-model rate does not reproduce what OpenRouter
    actually billed: measured against this machine's history the table is exact for
    minimax-m3, 2x high for glm-5.3-flash, and off by up to 17x for deepseek-v4-pro.
    The cost the DB reports is therefore authoritative whenever it is present.
    """
    pricing_model = resolve_pricing_model(row.provider, row.model)
    if not pricing_model:
        return 0.0

    # OpenCode counts reasoning tokens separately from output tokens, while
    # calculate_costs treats reasoning as a subset of output. Pass the sum so both are
    # billed at the output rate exactly once. Its input count already excludes cache
    # reads, which is why no cached-token subtraction applies here.
    costs = calculate_costs(
        provider=row.provider,
        pricing_model=pricing_model,
        input_tokens=row.input_tokens,
        cached_input_tokens=row.cached_input_tokens,
        cache_creation_input_tokens=row.cache_creation_input_tokens,
        output_tokens=row.output_tokens + row.reasoning_output_tokens,
        reasoning_output_tokens=row.reasoning_output_tokens,
    )
    return costs["session_total_cost_usd"]


def parse_opencode_rows(rows: tuple[JsonEvent, ...], session_file: Path, cwd: Path) -> AuditRecord | None:
    """Parse normalized OpenCode DB rows into the shared audit payload."""
    usage_rows = tuple(snapshot for snapshot in (extract_opencode_usage_row(row) for row in rows) if snapshot is not None)
    if not usage_rows:
        return None

    session_id = choose_opencode_session_id(usage_rows, cwd)
    if not session_id:
        return None

    selected = tuple(row for row in usage_rows if row.session_id == session_id)
    models = sorted({row.model for row in selected if row.model})
    model = models[0] if len(models) == 1 else ("mixed" if len(models) > 1 else "")
    timestamp = sorted(row.timestamp for row in selected if row.timestamp)[-1] if any(row.timestamp for row in selected) else ""

    costs = zero_costs()
    provider_billed_total = sum(row.cost_usd for row in selected)
    estimated_total = sum(estimate_opencode_row_cost(row) for row in selected if row.cost_usd == 0.0)
    costs["session_total_cost_usd"] = provider_billed_total + estimated_total

    return {
        "provider": "opencode",
        "session_id": session_id,
        "session_file": str(session_file),
        "timestamp": timestamp,
        "model": model,
        "reasoning_effort": "",
        "pricing_model": "",
        "input_tokens": sum(row.input_tokens for row in selected),
        "cached_input_tokens": sum(row.cached_input_tokens for row in selected),
        "cache_creation_input_tokens": sum(row.cache_creation_input_tokens for row in selected),
        "output_tokens": sum(row.output_tokens for row in selected),
        "reasoning_output_tokens": sum(row.reasoning_output_tokens for row in selected),
        "total_tokens": sum(row.total_tokens for row in selected),
        "cost_source": "provider_billed" if estimated_total == 0.0 else "mixed",
        "provider_billed_total": provider_billed_total,
        "provider_billed_unit": "usd",
        **costs,
    }

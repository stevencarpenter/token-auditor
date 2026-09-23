"""Constants shared by pure token_auditor core modules."""

PROJECT_NAME = "token-auditor"
CODEX_SESSION_GLOB = "sessions/*/*/*/rollout-*.jsonl"
CLAUDE_SESSION_GLOB = "projects/*/*.jsonl"
OPENCODE_DB_DEFAULT = "~/.local/share/opencode/opencode.db"

TOKEN_PRICING_USD_PER_1M: dict[str, dict[str, dict[str, float]]] = {
    "codex": {
        "gpt-5-codex": {
            "input_tokens": 1.250,
            "cached_input_tokens": 0.125,
            "output_tokens": 10.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.1-codex": {
            "input_tokens": 1.250,
            "cached_input_tokens": 0.125,
            "output_tokens": 10.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.1-codex-mini": {
            "input_tokens": 0.250,
            "cached_input_tokens": 0.025,
            "output_tokens": 2.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.2-codex": {
            "input_tokens": 1.750,
            "cached_input_tokens": 0.175,
            "output_tokens": 14.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.3-codex": {
            "input_tokens": 1.750,
            "cached_input_tokens": 0.175,
            "output_tokens": 14.000,
            "cache_creation_input_tokens": 0.0,
        },
        # gpt-5.4 / 5.5 are logged bare (no -codex suffix) in current rollout logs.
        # gpt-5.5 also has a >272K-input long-context tier (2x input, 1.5x output) that is intentionally
        # NOT modeled: codex logs only cumulative session usage, not per-request input,
        # so the per-request threshold can't be detected (same reason batch/flex aren't
        # modeled). Standard rates are billed.
        "gpt-5.4": {
            "input_tokens": 2.500,
            "cached_input_tokens": 0.250,
            "output_tokens": 15.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.4-mini": {
            "input_tokens": 0.750,
            "cached_input_tokens": 0.075,
            "output_tokens": 4.500,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.4-nano": {
            "input_tokens": 0.200,
            "cached_input_tokens": 0.020,
            "output_tokens": 1.250,
            "cache_creation_input_tokens": 0.0,
        },
        # Pro tiers do not support prompt caching (developers.openai.com shows no
        # cached-input rate), so cached tokens — which should never appear in their
        # logs — are billed at the full input rate rather than a nonexistent discount.
        "gpt-5.4-pro": {
            "input_tokens": 30.000,
            "cached_input_tokens": 30.000,
            "output_tokens": 180.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.5": {
            "input_tokens": 5.000,
            "cached_input_tokens": 0.500,
            "output_tokens": 30.000,
            "cache_creation_input_tokens": 0.0,
        },
        "gpt-5.5-pro": {
            "input_tokens": 30.000,
            "cached_input_tokens": 30.000,
            "output_tokens": 180.000,
            "cache_creation_input_tokens": 0.0,
        },
        # GPT-5.6 family rates (per developers.openai.com). Cache reads are discounted by
        # 90% and cache writes are billed at 1.25x input. Sol's rate is promotional, held
        # at least through 2026-11-21.
        "gpt-5.6-sol": {
            "input_tokens": 4.000,
            "cached_input_tokens": 0.400,
            "output_tokens": 20.000,
            "cache_creation_input_tokens": 5.000,
        },
        "gpt-5.6-terra": {
            "input_tokens": 2.000,
            "cached_input_tokens": 0.200,
            "output_tokens": 12.000,
            "cache_creation_input_tokens": 2.500,
        },
        "gpt-5.6-luna": {
            "input_tokens": 0.200,
            "cached_input_tokens": 0.020,
            "output_tokens": 1.200,
            "cache_creation_input_tokens": 0.250,
        },
        # GPT-6 Astra (GA 2026-09-03) ships as a single model with no mini/nano/pro tier
        # (developers.openai.com/api/docs/models/gpt-6-astra lists gpt-6-astra as the only
        # snapshot). Standard-tier rates only: batch/flex (0.5x), fast (2x), the >272K
        # long-context tier, and the data-residency surcharge are not modeled, for the same
        # reason as gpt-5.5 — codex logs cumulative session usage and no service tier.
        "gpt-6-astra": {
            "input_tokens": 10.000,
            "cached_input_tokens": 1.000,
            "output_tokens": 50.000,
            "cache_creation_input_tokens": 12.500,
        },
        # GPT-6 Sol and Luna (developers.openai.com, fetched 2026-09-22) are single
        # snapshots like Astra, with the same unmodeled tiers. Their >272K long-context
        # tier is 2x input/cache and 1.5x output.
        "gpt-6-sol": {
            "input_tokens": 2.000,
            "cached_input_tokens": 0.200,
            "output_tokens": 10.000,
            "cache_creation_input_tokens": 2.500,
        },
        "gpt-6-luna": {
            "input_tokens": 0.100,
            "cached_input_tokens": 0.010,
            "output_tokens": 0.500,
            "cache_creation_input_tokens": 0.125,
        },
    },
    "claude": {
        # Fable 5.1 shares Fable 5's base rates but prices cache reads at 0.025x input
        # ($0.25/MTok) rather than the 0.1x every other Claude model uses.
        "claude-fable-5-1": {
            "input_tokens": 10.00,
            "cached_input_tokens": 0.25,
            "cache_creation_input_tokens": 12.50,
            "output_tokens": 50.00,
        },
        "claude-fable-5": {
            "input_tokens": 10.00,
            "cached_input_tokens": 1.00,
            "cache_creation_input_tokens": 12.50,
            "output_tokens": 50.00,
        },
        # Opus 5.5 undercuts Opus 5 and prices cache reads at 0.05x input ($0.20/MTok).
        "claude-opus-5-5": {
            "input_tokens": 4.00,
            "cached_input_tokens": 0.20,
            "cache_creation_input_tokens": 5.00,
            "output_tokens": 20.00,
        },
        # Opus 5 ships as a drop-in upgrade at Opus 4.8's rates (per platform.claude.com).
        "claude-opus-5": {
            "input_tokens": 5.00,
            "cached_input_tokens": 0.50,
            "cache_creation_input_tokens": 6.25,
            "output_tokens": 25.00,
        },
        "claude-opus-4-8": {
            "input_tokens": 5.00,
            "cached_input_tokens": 0.50,
            "cache_creation_input_tokens": 6.25,
            "output_tokens": 25.00,
        },
        "claude-opus-4-7": {
            "input_tokens": 5.00,
            "cached_input_tokens": 0.50,
            "cache_creation_input_tokens": 6.25,
            "output_tokens": 25.00,
        },
        "claude-opus-4-6": {
            "input_tokens": 5.00,
            "cached_input_tokens": 0.50,
            "cache_creation_input_tokens": 6.25,
            "output_tokens": 25.00,
        },
        # These rates launched as introductory pricing through 2026-08-31, but
        # platform.claude.com now records them as standard: the scheduled increase to
        # $3 in / $15 out on 2026-09-01 was cancelled and did not take effect.
        "claude-sonnet-5": {
            "input_tokens": 2.00,
            "cached_input_tokens": 0.20,
            "cache_creation_input_tokens": 2.50,
            "output_tokens": 10.00,
        },
        "claude-sonnet-4-6": {
            "input_tokens": 3.00,
            "cached_input_tokens": 0.30,
            "cache_creation_input_tokens": 3.75,
            "output_tokens": 15.00,
        },
        "claude-haiku-4-5": {
            "input_tokens": 1.00,
            "cached_input_tokens": 0.10,
            "cache_creation_input_tokens": 1.25,
            "output_tokens": 5.00,
        },
    },
    "opencode": {},
    # OpenRouter rates (openrouter.ai/api/v1/models, fetched 2026-09-12) for the models
    # actually used through OpenRouter in OpenCode and pi sessions. Fractional rates are
    # OpenRouter's own, not the upstream provider's list price. OpenRouter reports no
    # one-time cache-write charge for these models, so cache writes are 0.0; Gemini bills
    # cache storage per token per hour, which this per-token schema cannot express.
    #
    # REFERENCE ONLY — deliberately not wired into cost computation, and it should stay
    # that way. OpenRouter routes each request to whichever upstream endpoint is
    # available, and those endpoints charge different rates, so no single per-model rate
    # reproduces a bill. Computing these rates over every costed OpenRouter row in a real
    # OpenCode database gives computed/actual ratios of 1.00 for minimax-m3 (152 rows),
    # exactly 2.00 for glm-5.3-flash (7,472 rows), 0.77-0.87 for kimi-k3 (704 rows),
    # 0.43-0.57 for glm-5.2 (48 rows), and 1.88-16.84 for deepseek-v4-pro (304 rows).
    # The spread within a single model is the point: it cannot be corrected by fixing a
    # constant. OpenCode records therefore report the cost the OpenCode DB already
    # carries (cost_source="provider_billed"), which is authoritative. pi has no parser.
    #
    # A related trap for anyone who does use these: OpenCode counts reasoning tokens
    # separately from output tokens, while calculate_costs treats reasoning as a subset
    # of output, so OpenCode's counts cannot be passed to it unchanged.
    "openrouter": {
        "z-ai/glm-5.3-flash": {
            "input_tokens": 0.150,
            "cached_input_tokens": 0.030,
            "output_tokens": 0.500,
            "cache_creation_input_tokens": 0.0,
        },
        "z-ai/glm-5.2": {
            "input_tokens": 0.600,
            "cached_input_tokens": 0.150,
            "output_tokens": 2.000,
            "cache_creation_input_tokens": 0.0,
        },
        "moonshotai/kimi-k3": {
            "input_tokens": 2.302729,
            "cached_input_tokens": 0.263169,
            "output_tokens": 11.550195,
            "cache_creation_input_tokens": 0.0,
        },
        "minimax/minimax-m3": {
            "input_tokens": 0.300,
            "cached_input_tokens": 0.060,
            "output_tokens": 1.200,
            "cache_creation_input_tokens": 0.0,
        },
        # deepseek-v4-pro is a floating pointer to the latest dated build, which is
        # priced differently from the 0813 snapshot; both are logged, so both are listed.
        "deepseek/deepseek-v4-pro": {
            "input_tokens": 0.819366,
            "cached_input_tokens": 0.068281,
            "output_tokens": 1.638732,
            "cache_creation_input_tokens": 0.0,
        },
        "deepseek/deepseek-v4-pro-0813": {
            "input_tokens": 0.578160,
            "cached_input_tokens": 0.018396,
            "output_tokens": 1.734480,
            "cache_creation_input_tokens": 0.0,
        },
        "google/gemini-3.6-flash": {
            "input_tokens": 0.750,
            "cached_input_tokens": 0.075,
            "output_tokens": 3.750,
            "cache_creation_input_tokens": 0.0,
        },
        # "~"-prefixed ids are OpenRouter floating aliases that track whatever the
        # upstream vendor currently ships, so these rates move without the id changing.
        "~moonshotai/kimi-latest": {
            "input_tokens": 2.302729,
            "cached_input_tokens": 0.263169,
            "output_tokens": 11.550195,
            "cache_creation_input_tokens": 0.0,
        },
        "~anthropic/claude-fable-latest": {
            "input_tokens": 10.000,
            "cached_input_tokens": 0.250,
            "output_tokens": 50.000,
            "cache_creation_input_tokens": 12.500,
        },
        "thinkingmachines/inkling:free": {
            "input_tokens": 0.0,
            "cached_input_tokens": 0.0,
            "output_tokens": 0.0,
            "cache_creation_input_tokens": 0.0,
        },
    },
}

# Codex "priority" service tier (renamed Fast mode by OpenAI on 2026-07-30) multiplies every
# standard rate, per developers.openai.com/api/docs/pricing. Codex records the tier in
# thread_settings_applied events. Models without a Fast-mode row are billed at standard rates.
CODEX_FAST_MODE_MULTIPLIER: dict[str, float] = {
    "gpt-6-astra": 2.0,
    "gpt-6-sol": 2.0,
    "gpt-6-luna": 2.0,
    "gpt-5.6-sol": 2.0,
    "gpt-5.6-terra": 2.0,
    "gpt-5.6-luna": 2.0,
    "gpt-5.5": 2.5,
    "gpt-5.4": 2.0,
    "gpt-5.4-mini": 2.0,
}

MODEL_PRICING_ALIASES: dict[str, dict[str, str]] = {
    "codex": {
        # developers.openai.com lists gpt-5.1-codex-max at gpt-5.1-codex's rates.
        "gpt-5.1-codex-max": "gpt-5.1-codex",
    },
    "claude": {
        "claude-fable-5-1[1m]": "claude-fable-5-1",
        "claude-fable-5[1m]": "claude-fable-5",
        "claude-opus-5-5[1m]": "claude-opus-5-5",
        "claude-opus-5[1m]": "claude-opus-5",
        "claude-opus-4-8[1m]": "claude-opus-4-8",
        "claude-opus-4-7[1m]": "claude-opus-4-7",
        "claude-sonnet-5[1m]": "claude-sonnet-5",
        "claude-opus-4-5": "claude-opus-4-6",
        "claude-sonnet-4-5": "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001": "claude-haiku-4-5",
        # Bare aliases are logged for some sessions (e.g. subagents); map each tier to
        # its current fleet member.
        "fable": "claude-fable-5-1",
        "opus": "claude-opus-5-5",
        "opus[1m]": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5",
        "haiku": "claude-haiku-4-5",
    },
    "opencode": {},
    "openrouter": {},
}

MODEL_PRICING_PREFIX_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    "codex": (),
    "claude": (
        # Ordering matters: "claude-fable-5-1" must be tried before "claude-fable-5",
        # or a dated Fable 5.1 snapshot resolves to Fable 5 and misprices cache reads 4x.
        ("claude-fable-5-1", "claude-fable-5-1"),
        ("claude-fable-5", "claude-fable-5"),
        # Same trap: "claude-opus-5-5" must precede "claude-opus-5" (Opus 5 costs 1.25x).
        ("claude-opus-5-5", "claude-opus-5-5"),
        ("claude-opus-5", "claude-opus-5"),
        ("claude-opus-4-8", "claude-opus-4-8"),
        ("claude-opus-4-7", "claude-opus-4-7"),
        ("claude-sonnet-5", "claude-sonnet-5"),
        ("claude-opus-4-5", "claude-opus-4-6"),
        ("claude-sonnet-4-5", "claude-sonnet-4-6"),
        ("claude-haiku-4-5", "claude-haiku-4-5"),
    ),
    "opencode": (),
    "openrouter": (),
}

LONG_CONTEXT_INPUT_THRESHOLD: int = 200_000

# Long-context (>200K input) pricing. As of Opus 5.5, Opus 5, Opus 4.6/4.7/4.8 and Sonnet 4.6, Anthropic
# bills the full 1M context window at *standard* rates — there is no >200K surcharge
# (https://platform.claude.com/docs/en/about-claude/pricing, which states these models
# "include the full 1M token context window at standard pricing"). These entries therefore
# mirror the standard table so billing is flat. The table is kept (rather than removed)
# so the long-context code path stays exercised and a future model that reintroduces a
# premium only needs its rates changed here.
LONG_CONTEXT_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "claude-fable-5-1": TOKEN_PRICING_USD_PER_1M["claude"]["claude-fable-5-1"],
    "claude-fable-5": TOKEN_PRICING_USD_PER_1M["claude"]["claude-fable-5"],
    "claude-opus-5-5": TOKEN_PRICING_USD_PER_1M["claude"]["claude-opus-5-5"],
    "claude-opus-5": TOKEN_PRICING_USD_PER_1M["claude"]["claude-opus-5"],
    "claude-opus-4-8": TOKEN_PRICING_USD_PER_1M["claude"]["claude-opus-4-8"],
    "claude-opus-4-7": TOKEN_PRICING_USD_PER_1M["claude"]["claude-opus-4-7"],
    "claude-opus-4-6": TOKEN_PRICING_USD_PER_1M["claude"]["claude-opus-4-6"],
    "claude-sonnet-5": TOKEN_PRICING_USD_PER_1M["claude"]["claude-sonnet-5"],
    "claude-sonnet-4-6": TOKEN_PRICING_USD_PER_1M["claude"]["claude-sonnet-4-6"],
}

# Applied when a message's usage.speed is "fast"; model IDs do not distinguish fast mode. Fast mode includes 1M context at no additional charge. The
# multiplier is NOT uniform: Opus 4.6/4.7 fast mode was 6x standard ($30 in / $150 out), while
# Opus 4.8, Opus 5, and Opus 5.5 fast mode is 2x standard ($10/$50, $10/$50, $8/$40). Cache read
# and 5-min cache write keep each model's standard multipliers off its fast input rate (0.05x
# cache read on Opus 5.5, 0.1x elsewhere; 1.25x cache write). Fast mode is Claude-API-only.
# Opus 4.7 fast mode has been withdrawn and Opus 4.6 fast requests now run and bill at standard
# rates; their rates are kept here for auditing historical sessions.
FAST_MODE_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {
        "input_tokens": 8.00,
        "cached_input_tokens": 0.40,
        "cache_creation_input_tokens": 10.00,
        "output_tokens": 40.00,
    },
    "claude-opus-5": {
        "input_tokens": 10.00,
        "cached_input_tokens": 1.00,
        "cache_creation_input_tokens": 12.50,
        "output_tokens": 50.00,
    },
    "claude-opus-4-8": {
        "input_tokens": 10.00,
        "cached_input_tokens": 1.00,
        "cache_creation_input_tokens": 12.50,
        "output_tokens": 50.00,
    },
    "claude-opus-4-7": {
        "input_tokens": 30.00,
        "cached_input_tokens": 3.00,
        "cache_creation_input_tokens": 37.50,
        "output_tokens": 150.00,
    },
    "claude-opus-4-6": {
        "input_tokens": 30.00,
        "cached_input_tokens": 3.00,
        "cache_creation_input_tokens": 37.50,
        "output_tokens": 150.00,
    },
}

# 1-hour cache writes bill at 2x base input on every Claude model. The tables above hold the
# 5-minute (1.25x) rate; calculate_costs applies this to usage.cache_creation.ephemeral_1h_input_tokens.
CACHE_WRITE_1HR_MULTIPLIER: float = 2.0

# Applied to every Claude rate when a message's usage.inference_geo is "us" (Claude 4.6 and later).
DATA_RESIDENCY_MULTIPLIER: float = 1.1

EVERFOREST_HEADER_COLOR_256 = 108
EVERFOREST_SECTION_COLOR_256 = 109
EVERFOREST_MUTED_COLOR_256 = 245
EVERFOREST_GRADIENT_256 = (108, 109, 110, 142, 143, 150, 179, 180, 181)

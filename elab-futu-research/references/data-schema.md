# Data schema

All JSONL records are UTF-8 JSON objects, one object per line. Schemas are versioned with `schema_version`.

## Normalized post

Required:

```json
{
  "schema_version": "1.0",
  "platform": "futu|tiger",
  "feed_id": "string",
  "profile_uid": "string",
  "author_uid": "string",
  "author_name": "string|null",
  "published_at": "ISO-8601|null",
  "published_at_raw": "string|number|null",
  "stream_membership": ["all", "columns"],
  "is_column": false,
  "is_repost": false,
  "title": "string",
  "text": "string",
  "original_text": "string|null",
  "original_author": "string|null",
  "symbols": [
    {"raw": "US.EXAMPLE", "code": "EXAMPLE", "market": "US", "name": "string|null"}
  ],
  "topics": ["string"],
  "metrics": {"comments": 0, "likes": 0, "reposts": 0, "views": 0},
  "images": [
    {"url": "https://...", "source_field": "orgPic", "local_path": "media/..."}
  ],
  "source": {
    "detail_path": "raw/details/<uid>/<feed_id>.json",
    "profile_url": "https://q.futunn.com/profile/<uid>"
  },
  "parse_warnings": []
}
```

For reposts, `text` contains the author's own comment (may be empty for silent reposts), `original_text` contains the reposted content, and `original_author` contains the original poster's name when available in the payload. Both fields are `null` for original posts.

Profile identity is `(platform, profile_uid)`, and post identity is `(platform, profile_uid, feed_id)`. Numeric UIDs and post IDs from different platforms must remain separate. Older records may recover their platform from the recorded source URL; ambiguous legacy claims require explicit source verification before regeneration.

Keep raw exchange prefixes. Do not reduce `HK.00700` to `00700` or merge securities from different markets.

## Candidate claim

Machine-generated candidate:

```json
{
  "schema_version": "1.0",
  "candidate_id": "<platform>:<profile_uid>:<feed_id>:<symbol-or-general>",
  "platform": "futu|tiger",
  "feed_id": "string",
  "author_uid": "string",
  "published_at": "ISO-8601|null",
  "symbol_raw": "string|null",
  "direction_prelabel": "bullish|bearish|mixed|neutral|unclear",
  "action_prelabel": "buy|add|hold|reduce|sell|short|cover|watch|none|unclear",
  "evidence_prelabel": "B|C|D",
  "evidence_span": "string",
  "keyword_hits": ["string"],
  "needs_human_review": true,
  "source_post_path": "archive/posts.jsonl"
}
```

The prelabel is never final and never `A`.

## Reviewed claim

```json
{
  "schema_version": "1.0",
  "claim_id": "stable string",
  "platform": "futu|tiger",
  "candidate_id": "string",
  "feed_id": "string",
  "author_uid": "string",
  "published_at": "ISO-8601",
  "symbol_raw": "US.EXAMPLE",
  "direction": "bullish|bearish|mixed|neutral",
  "action": "buy|add|hold|reduce|sell|short|cover|watch|none",
  "horizon": "intraday|days|weeks|months|years|unclear",
  "evidence_level": "A|B|C|D",
  "evidence_span": "exact short span",
  "image_evidence_paths": [],
  "image_evidence_verified": false,
  "conditions": [],
  "invalidation": [],
  "sizing_rule": "string|null",
  "risk_rule": "string|null",
  "exit_rule": "string|null",
  "tone": {
    "valence": 0,
    "arousal": 0,
    "certainty": 0,
    "urgency": 0,
    "conditionality": 0,
    "risk_awareness": 0,
    "evidence_density": 0,
    "accountability": 0,
    "rationale": "observable language only"
  },
  "confidence": "high|medium|low",
  "ambiguities": [],
  "reviewer": "human|model+human|model",
  "reviewed_at": "ISO-8601"
}
```

If `evidence_level=A`, `image_evidence_verified` must be true and at least one evidence path must exist.

## Episode

```json
{
  "schema_version": "1.0",
  "episode_id": "string",
  "author_uid": "string",
  "symbol_raw": "string",
  "claim_ids": ["string"],
  "started_at": "ISO-8601",
  "ended_at": "ISO-8601|null",
  "initial_thesis": "string",
  "updates": [
    {"claim_id": "string", "label": "evidence_driven", "explanation": "string"}
  ],
  "regimes": ["up_high_vol"],
  "outcome_summary": {},
  "confidence": "high|medium|exploratory|case_only"
}
```

## Market row

CSV or JSON:

```json
{
  "claim_id": "string",
  "claim_sha256": "SHA-256 of the frozen claim",
  "market_calculation_version": "1",
  "platform": "futu|tiger",
  "symbol_raw": "US.EXAMPLE",
  "provider_symbol": "EXAMPLE",
  "context_cutoff": "YYYY-MM-DD",
  "evaluation_open_date": "YYYY-MM-DD",
  "trend": "up|down|mixed|unknown",
  "volatility": "low|normal|high|unknown",
  "close_vs_ma20": 0.0,
  "close_vs_ma60": 0.0,
  "drawdown_60d": 0.0,
  "ret_1": 0.0,
  "ret_5": 0.0,
  "ret_20": 0.0,
  "ret_60": 0.0,
  "directional_ret_1": 0.0,
  "directional_ret_5": 0.0,
  "directional_ret_20": 0.0,
  "directional_ret_60": 0.0,
  "mfe_20": 0.0,
  "mae_20": 0.0,
  "directional_excess_ret_20": 0.0,
  "benchmark_symbol": "string|null",
  "market_data_source": "csv|eastmoney:<secid>|yahoo|null",
  "missing_reason": "string|null"
}
```

`ret_*` is the raw underlying return. `directional_ret_*` multiplies it by the frozen bullish/bearish direction. `mfe_20` and `mae_20` are also direction-aware, so favorable excursion is positive and adverse excursion is negative for either long or short calls.

`claim_sha256` hashes the full claim JSON after platform resolution, with sorted keys, UTF-8 encoding and compact separators. Any changed frozen field invalidates the derived market row. `report` refuses stale, unbound or duplicate market rows; `audit` blocks publication. Older market rows without this hash must be regenerated with `market`; they are never automatically treated as current.

`market_calculation_version` independently identifies the calculation and benchmark rules, is recorded in each JSONL/CSV row and the market manifest, and must match the script's `MARKET_CALCULATION_VERSION`; missing or outdated versions require rerunning `market` even when the claim hash matches.

## Crawl audit

Audit per profile and stream:

```json
{
  "profile_uid": "string",
  "stream": "all|columns",
  "pages_saved": 0,
  "unique_feed_ids": 0,
  "terminal_reason": "has_more_zero|since_boundary|error|cursor_loop|max_pages",
  "complete_for_request": false,
  "errors": []
}
```

Top-level audit includes detail coverage, media counts/failures, duplicates, date coverage, run options, and a status:

- `PASS`: deterministic data-chain checks passed;
- `WARN`: usable with explicit missingness;
- `FAIL`: final research conclusions must not be published.

`PASS` validates the evidence chain, not investment skill or alpha.

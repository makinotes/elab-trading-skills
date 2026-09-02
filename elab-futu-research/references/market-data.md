# Market data

## Provider order

For each mapped symbol, the script tries:

1. a user-supplied CSV;
2. Eastmoney's public daily chart response;
3. Yahoo Finance's public chart response.

No key is required for these adapters, but public interfaces can be blocked, rate-limited, delayed, corrected, or changed without notice. Every market row records `market_data_source`; `market_manifest.json` records provider errors. Never replace an unavailable series with invented prices.

## Supplying CSV

CSV is the most reproducible override. Place it under:

```text
analysis/market/input/<raw-symbol>.csv
```

The filename is sanitized but preserves dots, for example `US.EXAMPLE.csv`. A provider-symbol filename is also accepted.

Required columns, case-insensitive:

```csv
Date,Open,High,Low,Close,Volume
2025-01-02,10.0,10.8,9.9,10.5,1000
```

Use split-adjusted OHLC when possible and document the vendor and adjustment method outside the CSV. `Volume` may be empty. Dates must be ISO `YYYY-MM-DD`.

After adding or correcting CSV data, rerun:

```bash
python3 scripts/futu_research.py market --output "<dir>" --refresh-market
python3 scripts/futu_research.py report --output "<dir>"
python3 scripts/futu_research.py audit --output "<dir>"
```

## Symbol mapping

Automatic mappings cover common forms:

- `US.EXAMPLE` → `EXAMPLE`
- `HK.00700`-shaped codes → four-digit Yahoo form and five-digit Eastmoney form
- `SH.600000`-shaped codes → `.SS`
- `SZ.000001`-shaped codes → `.SZ`

The examples describe formatting only; they are not research subjects.

If a symbol is ambiguous, edit:

```text
analysis/symbol_overrides.json
```

Map the raw symbol to a Yahoo-style provider symbol, or use an empty string to skip it. Do not resolve an inferred ticker merely because a price series exists.

## Time protocol

- Context cutoff: the last daily bar strictly before the post's local publication date.
- Evaluation start: the first daily open strictly after that date.
- Horizons: 1/5/20/60 sessions.

This deliberately conservative daily protocol avoids treating an incomplete same-day bar as known. It cannot establish an intraday fill.

## Adjustment and quality

- Yahoo OHLC is scaled by the available adjusted-close factor.
- Eastmoney is requested with forward-adjustment mode.
- User CSV quality is the user's responsibility and must be documented.
- Missing or inconsistent OHLC remains a missing result.

For consequential research, spot-check a sample against a second source, especially around splits, dividends, suspensions, delistings, and symbol changes.

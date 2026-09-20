#!/usr/bin/env python3
"""Compute IV position metrics; never infer history or recommend a trade."""

import argparse
import json
import math


def checked(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("IV values must be numeric")
    if not math.isfinite(value) or value < 0:
        raise ValueError("IV values must be finite and non-negative")
    return float(value)


def calculate(current, *, history=None, low=None, high=None):
    current = checked(current)
    if history is not None:
        if low is not None or high is not None:
            raise ValueError("Use history OR bounds, not both")
        values = [checked(value) for value in history]
        if not values:
            raise ValueError("History must contain at least one observation")
        low, high = min(values), max(values)
        percentile = 100.0 * sum(value < current for value in values) / len(values)
        count = len(values)
    else:
        if low is None or high is None:
            raise ValueError("History or both bounds are required")
        low, high = checked(low), checked(high)
        if low > high:
            raise ValueError("Minimum IV must not exceed maximum IV")
        percentile, count = None, None
    rank = None if low == high else 100.0 * ((current - low) / (high - low))
    if rank is not None and not math.isfinite(rank):
        raise ValueError("Rank cannot be represented as a finite number")
    return {
        "current_iv": current,
        "minimum_iv": low,
        "maximum_iv": high,
        "iv_rank": rank,
        "iv_rank_status": "undefined_flat_range" if rank is None else "calculated",
        "iv_percentile": percentile,
        "iv_percentile_status": "history_missing" if history is None else "calculated",
        "percentile_definition": "strictly_less_than_current",
        "history_count": count,
        "out_of_range": current < low or current > high,
        "input_alignment": "caller_must_verify_tenor_delta_model_and_window",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=float, required=True)
    parser.add_argument("--unit", choices=("percent", "decimal"), required=True)
    parser.add_argument("--history", type=float, nargs="+")
    parser.add_argument("--low", type=float)
    parser.add_argument("--high", type=float)
    args = parser.parse_args()
    try:
        result = calculate(args.current, history=args.history, low=args.low, high=args.high)
    except ValueError as exc:
        parser.error(str(exc))
    result["input_unit"] = args.unit
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

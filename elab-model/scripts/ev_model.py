#!/usr/bin/env python3
"""ev_model.py — EV / Kelly / option-credit expected-value model.

Usage:
  python3 ev_model.py ev --win-rate 0.45 --avg-win 300 --avg-loss -200 [--sample-size 15]
  python3 ev_model.py kelly --win-rate 0.45 --payoff-ratio 1.5 [--fraction 0.25] [--sample-size 15]
  python3 ev_model.py option-credit --credit 0.85 --max-loss 5.00 --pop 0.72 [--pop-source delta|manual]

stdout: JSON only.
stderr: error messages only.
exit 0 = success; exit 1 = parameter or data error.

Python 3.9 compatible; stdlib only (no pip).
"""

import argparse
import json
import math
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Custom argparse parser: overrides error() to exit 1 (not 2) and write to
# stderr only — keeps stdout clean for the JSON contract.
# ---------------------------------------------------------------------------

class StrictParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Threshold loading (same pattern as strategy_models.py, registry §5)
# Fallback constants = same values as bundled thresholds.json.
# ---------------------------------------------------------------------------

FALLBACK_THRESHOLDS: Dict[str, Any] = {
    "min_sample_size": 20,
    "otm_deep_ratio": 0.30,
}


def _load_thresholds(config_path: Optional[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Load thresholds from JSON file.

    Resolution order:
    1. Explicit --config path (if provided)
    2. Same-directory thresholds.json (bundled default)
    3. FALLBACK_THRESHOLDS code constants (on any file/parse error)

    Returns (thresholds_dict, extra_warnings).
    extra_warnings is non-empty only when falling back to code constants.
    """
    if config_path is None:
        resolved = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thresholds.json")
    else:
        resolved = config_path

    try:
        with open(resolved) as f:
            data = json.load(f)
        # Start from fallback so missing keys are covered by defaults.
        result: Dict[str, Any] = dict(FALLBACK_THRESHOLDS)
        result.update(data)
        return result, []
    except Exception as exc:
        print(f"NOTE: cannot load thresholds from '{resolved}': {exc}", file=sys.stderr)
        return dict(FALLBACK_THRESHOLDS), ["使用内置默认阈值"]


# ---------------------------------------------------------------------------
# Public utility — callable by strategy_models and external consumers.
# Replaces direct private access to _compute_ev_core for breakeven queries.
# ---------------------------------------------------------------------------

def compute_breakeven_pop(avg_win: float, avg_loss: float) -> float:
    """Return the win_rate at which EV = 0.

    avg_loss must be negative.  Equivalent to breakeven_win_rate returned by
    _compute_ev_core, but callable without the full core computation.
    """
    abs_loss = abs(avg_loss)
    return abs_loss / (avg_win + abs_loss)


# ---------------------------------------------------------------------------
# Shared sample-size warnings — single source of truth (DRY, registry §一 §二).
# Called by _compute_ev_core; no longer duplicated in _cmd_kelly.
# ---------------------------------------------------------------------------

def _sample_size_warnings(sample_size: Optional[int], min_sample_size: int) -> List[str]:
    """Return provenance warnings based on sample size."""
    if sample_size is None:
        return ["win_rate 来源为假设值，非统计数据"]
    if sample_size < min_sample_size:
        return [
            f"win_rate 样本仅 {sample_size} 笔，低于 {min_sample_size} 笔阈值，样本不足"
        ]
    return []


# ---------------------------------------------------------------------------
# Core EV computation — shared by all three sub-commands.
# ---------------------------------------------------------------------------

def _compute_ev_core(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    sample_size: Optional[int],
    include_sample_warnings: bool = True,
    min_sample_size: int = 20,
) -> Dict[str, Any]:
    """Return a dict of ev metrics.  avg_loss must be negative.

    include_sample_warnings=False suppresses sample-size provenance warnings;
    used by option-credit which manages its own pop-source provenance.

    Kelly归零规则: f*<0 → kelly_full/kelly_quarter set to 0.0, warning added.
    Kelly肥尾警示: f*>0 → fat-tail advisory warning always added.
    """
    warnings: List[str] = []

    # Sample-size / provenance warnings (structural switch, not substring filter)
    if include_sample_warnings:
        warnings.extend(_sample_size_warnings(sample_size, min_sample_size))

    # Core arithmetic
    ev_per_trade: float = win_rate * avg_win + (1.0 - win_rate) * avg_loss

    abs_win: float = abs(avg_win)
    abs_loss: float = abs(avg_loss)
    payoff_ratio: float = abs_win / abs_loss
    breakeven_win_rate: float = compute_breakeven_pop(avg_win, avg_loss)

    # Kelly: f* = (b*p - q) / b, b = payoff_ratio
    b: float = payoff_ratio
    p: float = win_rate
    q: float = 1.0 - win_rate
    raw_kelly: float = (b * p - q) / b

    if raw_kelly < 0.0:
        # 负 Kelly 归零: EV in current assumptions is negative; zero output, no ops guidance
        kelly_full = 0.0
        kelly_quarter = 0.0
        warnings.append(
            "Kelly 为负（EV 在当前假设下为负），此值无实操意义，已归零"
        )
    elif raw_kelly > 0.0:
        kelly_full = round(raw_kelly, 4)
        kelly_quarter = round(raw_kelly / 4.0, 4)
        # 肥尾强制警示: Kelly assumes binary win/loss; fat tails overstate true position size
        warnings.append(
            "Kelly 基于二元胜负分布假设，实盘肥尾下可能高估合理仓位，"
            "请结合 quarter Kelly 与极端情景使用"
        )
    else:
        # raw_kelly == 0.0 exactly (EV = 0): output 0.0, no Kelly warning
        kelly_full = 0.0
        kelly_quarter = 0.0

    return {
        "ev_per_trade": round(ev_per_trade, 4),
        "payoff_ratio": round(payoff_ratio, 4),
        "breakeven_win_rate": round(breakeven_win_rate, 4),
        "kelly_full": kelly_full,
        "kelly_quarter": kelly_quarter,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Input validators — each prints to stderr and exits 1 on violation.
# All numeric validators guard against NaN/inf first (math.isfinite).
# ---------------------------------------------------------------------------

def _check_win_rate(value: float) -> None:
    if not math.isfinite(value):
        print("ERROR: --win-rate must be a finite number", file=sys.stderr)
        sys.exit(1)
    if not (0.0 < value < 1.0):
        print("ERROR: --win-rate must be strictly between 0 and 1", file=sys.stderr)
        sys.exit(1)


def _check_avg_win(value: float) -> None:
    if not math.isfinite(value):
        print("ERROR: --avg-win must be a finite number", file=sys.stderr)
        sys.exit(1)
    if value <= 0.0:
        print("ERROR: --avg-win must be positive", file=sys.stderr)
        sys.exit(1)


def _check_avg_loss(value: float) -> None:
    if not math.isfinite(value):
        print("ERROR: --avg-loss must be a finite number", file=sys.stderr)
        sys.exit(1)
    if value >= 0.0:
        print("ERROR: --avg-loss must be negative", file=sys.stderr)
        sys.exit(1)


def _check_payoff_ratio(value: float) -> None:
    if not math.isfinite(value):
        print("ERROR: --payoff-ratio must be a finite number", file=sys.stderr)
        sys.exit(1)
    if value <= 0.0:
        print("ERROR: --payoff-ratio must be positive", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def _cmd_ev(args: argparse.Namespace) -> None:
    win_rate: float = args.win_rate
    avg_win: float = args.avg_win
    avg_loss: float = args.avg_loss
    sample_size: Optional[int] = args.sample_size

    _check_win_rate(win_rate)
    _check_avg_win(avg_win)
    _check_avg_loss(avg_loss)

    thresholds, thresh_warnings = _load_thresholds(args.config)
    min_sample_size: int = thresholds["min_sample_size"]

    if sample_size is not None:
        win_rate_source = f"[交割单统计 {sample_size}笔]"
    else:
        win_rate_source = "[本人假设]"

    core = _compute_ev_core(
        win_rate, avg_win, avg_loss, sample_size,
        min_sample_size=min_sample_size,
    )

    all_warnings = core["warnings"] + thresh_warnings

    output: Dict[str, Any] = {
        "model": "ev",
        "inputs": {
            "win_rate": {"value": win_rate, "source": win_rate_source},
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "sample_size": sample_size,
        },
        "ev_per_trade": core["ev_per_trade"],
        "payoff_ratio": core["payoff_ratio"],
        "breakeven_win_rate": core["breakeven_win_rate"],
        "kelly_full": core["kelly_full"],
        "kelly_quarter": core["kelly_quarter"],
        "units": {"ev_per_trade": "per_trade_dollar"},
        "warnings": all_warnings,
        "as_of": date.today().isoformat(),
    }
    print(json.dumps(output, ensure_ascii=False))


def _cmd_kelly(args: argparse.Namespace) -> None:
    win_rate: float = args.win_rate
    payoff_ratio: float = args.payoff_ratio
    fraction: float = args.fraction
    sample_size: Optional[int] = args.sample_size

    _check_win_rate(win_rate)
    _check_payoff_ratio(payoff_ratio)
    if not math.isfinite(fraction) or not (0.0 < fraction <= 1.0):
        print(
            "ERROR: --fraction must be between 0 (exclusive) and 1 (inclusive)",
            file=sys.stderr,
        )
        sys.exit(1)

    thresholds, thresh_warnings = _load_thresholds(args.config)
    min_sample_size: int = thresholds["min_sample_size"]

    # Delegate Kelly math to _compute_ev_core by mapping:
    #   avg_win  = payoff_ratio  (b)
    #   avg_loss = -1.0          (normalised loss of 1 unit)
    # Produces the same Kelly f* = (b*p - q)/b and same sample warnings.
    core = _compute_ev_core(
        win_rate=win_rate,
        avg_win=payoff_ratio,
        avg_loss=-1.0,
        sample_size=sample_size,
        min_sample_size=min_sample_size,
    )

    kelly_full: float = core["kelly_full"]
    kelly_quarter: float = core["kelly_quarter"]
    # kelly_fractional: apply user fraction to kelly_full.
    # When kelly_full=0 (归零 case), kelly_fractional is also 0.
    kelly_fractional: float = round(kelly_full * fraction, 4)

    if sample_size is not None:
        win_rate_source = f"[交割单统计 {sample_size}笔]"
    else:
        win_rate_source = "[本人假设]"

    all_warnings = core["warnings"] + thresh_warnings

    output: Dict[str, Any] = {
        "model": "kelly",
        "inputs": {
            "win_rate": {"value": win_rate, "source": win_rate_source},
            "payoff_ratio": payoff_ratio,
            "fraction": fraction,
            "sample_size": sample_size,
        },
        "kelly_full": kelly_full,
        "kelly_quarter": kelly_quarter,
        "kelly_fractional": kelly_fractional,
        "units": {
            "kelly_full": "fraction_of_capital",
            "kelly_quarter": "fraction_of_capital",
            "kelly_fractional": "fraction_of_capital",
        },
        "warnings": all_warnings,
        "as_of": date.today().isoformat(),
    }
    print(json.dumps(output, ensure_ascii=False))


def _cmd_option_credit(args: argparse.Namespace) -> None:
    credit: float = args.credit
    max_loss: float = args.max_loss
    pop: float = args.pop
    pop_source: str = args.pop_source

    # Input validation: NaN/inf guard first, then value-range checks
    if not math.isfinite(credit) or credit <= 0.0:
        print("ERROR: --credit must be a positive finite number", file=sys.stderr)
        sys.exit(1)
    if not math.isfinite(max_loss) or max_loss <= 0.0:
        print("ERROR: --max-loss must be a positive finite number", file=sys.stderr)
        sys.exit(1)
    if max_loss <= credit:
        print("ERROR: --max-loss must be greater than --credit", file=sys.stderr)
        sys.exit(1)
    if not math.isfinite(pop) or not (0.0 < pop < 1.0):
        print("ERROR: --pop must be strictly between 0 and 1", file=sys.stderr)
        sys.exit(1)

    thresholds, thresh_warnings = _load_thresholds(args.config)
    otm_deep_ratio: float = thresholds["otm_deep_ratio"]

    # Registry §三 mapping (明文口径)
    avg_win: float = credit                    # per-share premium received
    avg_loss: float = -(max_loss - credit)     # per-share loss on adverse outcome
    win_rate: float = pop

    if pop_source == "delta":
        pop_source_label = "[工具输出/delta近似]"
    else:
        pop_source_label = "[本人假设]"

    # Core computation: suppress sample_size provenance warnings (pop has its own source logic)
    core = _compute_ev_core(
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        sample_size=None,
        include_sample_warnings=False,
    )

    # Start from Kelly warnings already in core (负/肥尾), then add pop-source provenance
    warnings: List[str] = list(core["warnings"])

    if pop_source == "manual":
        warnings.append("pop 来源为用户假设值，非统计或工具输出")
    elif pop_source == "delta":
        credit_ratio = credit / max_loss
        if credit_ratio < otm_deep_ratio:
            warnings.append(
                "OTM 场景 delta 近似 pop 系统性偏高，实际 pop 可能更低"
            )

    warnings.extend(thresh_warnings)

    # Field names: ev_per_share (per-share) + ev_per_contract (×100)
    ev_per_share: float = core["ev_per_trade"]
    ev_per_contract: float = round(ev_per_share * 100, 2)

    output: Dict[str, Any] = {
        "model": "option-credit",
        "inputs": {
            "credit": credit,
            "max_loss": max_loss,
            "pop": {"value": pop, "source": pop_source_label},
            "pop_source": pop_source,
            "mapped": {
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "win_rate": win_rate,
            },
        },
        "ev_per_share": ev_per_share,
        "ev_per_contract": ev_per_contract,
        "payoff_ratio": core["payoff_ratio"],
        "breakeven_win_rate": core["breakeven_win_rate"],
        "kelly_full": core["kelly_full"],
        "kelly_quarter": core["kelly_quarter"],
        "units": {
            "ev_per_share": "per_share_dollar",
            "ev_per_contract": "per_contract_dollar",
        },
        "warnings": warnings,
        "as_of": date.today().isoformat(),
    }
    print(json.dumps(output, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Argument parser setup
# ---------------------------------------------------------------------------

def _build_parser() -> StrictParser:
    parser = StrictParser(
        description="EV / Kelly / option-credit expected-value model (stdlib, Python 3.9+)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # -- ev --
    ev_p = sub.add_parser("ev", help="Expected value + Kelly from raw P&L stats")
    ev_p.add_argument("--win-rate", type=float, required=True,
                      help="Historical win rate (0 < p < 1)")
    ev_p.add_argument("--avg-win", type=float, required=True,
                      help="Average winning trade amount (positive, per-contract $)")
    ev_p.add_argument("--avg-loss", type=float, required=True,
                      help="Average losing trade amount (negative, per-contract $)")
    ev_p.add_argument("--sample-size", type=int, default=None,
                      help="Number of trades (machine-readable provenance; omit = assumed)")
    ev_p.add_argument("--config", type=str, default=None,
                      help="Path to thresholds JSON (default: same-dir thresholds.json)")

    # -- kelly --
    kelly_p = sub.add_parser("kelly", help="Kelly criterion from win rate + payoff ratio")
    kelly_p.add_argument("--win-rate", type=float, required=True,
                         help="Win rate (0 < p < 1)")
    kelly_p.add_argument("--payoff-ratio", type=float, required=True,
                         help="avg_win / avg_loss (positive)")
    kelly_p.add_argument("--fraction", type=float, default=0.25,
                         help="Kelly fraction to scale (default 0.25 = quarter-Kelly)")
    kelly_p.add_argument("--sample-size", type=int, default=None,
                         help="Number of trades (provenance)")
    kelly_p.add_argument("--config", type=str, default=None,
                         help="Path to thresholds JSON (default: same-dir thresholds.json)")

    # -- option-credit --
    oc_p = sub.add_parser("option-credit",
                          help="EV for an option credit spread (maps credit/pop → EV core)")
    oc_p.add_argument("--credit", type=float, required=True,
                      help="Premium received per share ($)")
    oc_p.add_argument("--max-loss", type=float, required=True,
                      help="Maximum possible loss per share ($, positive)")
    oc_p.add_argument("--pop", type=float, required=True,
                      help="Probability of profit (0 < p < 1)")
    oc_p.add_argument("--pop-source", type=str, default="manual",
                      choices=["delta", "manual"],
                      help="Source of pop: 'delta' (option chain delta approx) or 'manual'")
    oc_p.add_argument("--config", type=str, default=None,
                      help="Path to thresholds JSON (default: same-dir thresholds.json)")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.command == "ev":
        _cmd_ev(args)
    elif args.command == "kelly":
        _cmd_kelly(args)
    elif args.command == "option-credit":
        _cmd_option_credit(args)
    else:
        print(f"ERROR: unknown command '{args.command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

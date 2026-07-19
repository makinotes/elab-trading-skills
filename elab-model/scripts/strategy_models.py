#!/usr/bin/env python3
"""strategy_models.py — Option strategy template math library.

5 templates: bull-put-spread, bear-put-spread, covered-call, cash-secured-put, long-put.

Usage:
  python3 strategy_models.py bull-put-spread --short-strike 95 --long-strike 90 --credit 1.35 --dte 30
  python3 strategy_models.py bear-put-spread --long-strike 95 --short-strike 90 --debit 2.00 --dte 30
  python3 strategy_models.py covered-call --entry-price 100 --call-strike 105 --credit 1.50 --dte 30
  python3 strategy_models.py cash-secured-put --strike 95 --credit 1.50 --dte 30
  python3 strategy_models.py long-put --strike 95 --debit 2.00 --dte 30

stdout: JSON only.
stderr: error messages only.
exit 0 = success; exit 1 = parameter or data error.

Python 3.9 compatible; stdlib only (no pip).

Terminology hardcoded per elab-model registry §4 硬规则:
  bull-put-spread: 收 credit 看多，非对冲工具
  bear-put-spread: 付 debit 看跌，对冲工具（非 bull put）
  covered-call: 有 premium 的一次性止盈，不是真分层对冲
  cash-secured-put: 收 credit，愿意以 strike 价买入标的
  long-put: 付 debit，方向性看跌或对冲多头

Cross-script EV link: imports ev_model from same scripts/ directory via sys.path.insert.
Thresholds: loaded from --config JSON; fallback to code constants + warnings on any error.
"""

import argparse
import json
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import ev_model from same scripts/ directory (design §3: no subprocess)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_EV_MODEL_AVAILABLE = False
_ev_model: Any = None  # type alias for the imported module

try:
    import ev_model as _ev_module  # noqa: F401
    _ev_model = _ev_module
    _EV_MODEL_AVAILABLE = True
except Exception as _ev_import_err:
    # Non-fatal: ev_breakeven_pop will be null, warning added per output
    pass


# ---------------------------------------------------------------------------
# Custom argparse: error → stderr + exit 1, keeps stdout clean
# ---------------------------------------------------------------------------

class StrictParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Threshold loading
# Fallback constants = same values as bundled thresholds.json (registry §5)
# ---------------------------------------------------------------------------

FALLBACK_THRESHOLDS: Dict[str, Any] = {
    "min_sample_size": 20,
    "credit_width_min_ratio": 0.20,
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
        # Start from fallback so missing keys are covered
        result: Dict[str, Any] = dict(FALLBACK_THRESHOLDS)
        result.update(data)
        return result, []
    except Exception as exc:
        print(f"NOTE: cannot load thresholds from '{resolved}': {exc}", file=sys.stderr)
        return dict(FALLBACK_THRESHOLDS), ["使用内置默认阈值"]


# ---------------------------------------------------------------------------
# EV breakeven pop via ev_model._compute_ev_core
# (EV = 0 ↔ breakeven_win_rate in ev_model terminology)
# ---------------------------------------------------------------------------

def _compute_ev_breakeven_pop(
    avg_win_per_share: float,
    avg_loss_per_share: float,
    warnings: List[str],
) -> Optional[float]:
    """Return the pop (probability of profit) at which EV = 0.

    Uses ev_model._compute_ev_core with a dummy win_rate (doesn't affect
    breakeven_win_rate).  avg_loss_per_share must be negative.

    On failure, appends a warning and returns None.
    """
    if not _EV_MODEL_AVAILABLE:
        warnings.append("ev_model 不可用，ev_breakeven_pop 未计算")
        return None
    try:
        core = _ev_model._compute_ev_core(
            win_rate=0.5,           # dummy; breakeven_win_rate is independent of this
            avg_win=avg_win_per_share,
            avg_loss=avg_loss_per_share,
            sample_size=None,
        )
        return round(core["breakeven_win_rate"], 4)
    except Exception as exc:
        warnings.append(f"ev_model 计算失败，ev_breakeven_pop 未计算: {exc}")
        return None


# ---------------------------------------------------------------------------
# Shared output helpers
# ---------------------------------------------------------------------------

def _greeks(delta: str, theta: str, vega: str) -> Dict[str, str]:
    """Return greeks_exposure dict with [定性] note."""
    return {
        "delta": delta,
        "theta": theta,
        "vega": vega,
        "note": "[定性]",
    }


def _as_of() -> str:
    return date.today().isoformat()


def _spot_distance_pct(spot: Optional[float], short_strike: float) -> Optional[float]:
    """Distance of spot from short_strike, as % of short_strike.

    Positive = spot above short_strike; negative = spot below.
    registry §4: assignment_risk contains only objective figures, no action language.
    """
    if spot is None:
        return None
    return round((spot - short_strike) / short_strike * 100, 2)


def _dte_weeks(dte: int) -> float:
    return round(dte / 7, 4)


def _output(data: Dict[str, Any]) -> None:
    """Write JSON to stdout (the only stdout output)."""
    print(json.dumps(data, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Template: bull-put-spread
# Terminology (registry §4a hardcoded): 收 credit 看多，非对冲工具
# ---------------------------------------------------------------------------

def _cmd_bull_put_spread(args: argparse.Namespace) -> None:
    """bull-put-spread: sell higher-strike put, buy lower-strike put.

    收 credit 看多，非对冲工具。
    NOT a hedge for an existing long position (use bear-put-spread for that).

    Registry §4a formula:
      width       = short_strike − long_strike   (per-share, NOT × 100)
      max_profit  = credit × 100                 (per-contract dollar)
      max_loss    = (width − credit) × 100       (per-contract dollar)
      breakeven   = short_strike − credit        (per-share)
      risk_reward = max_profit / max_loss
    """
    short_strike: float = args.short_strike
    long_strike: float = args.long_strike
    credit: float = args.credit
    dte: int = args.dte
    spot: Optional[float] = args.spot
    config_path: Optional[str] = args.config

    # Validation
    if short_strike <= long_strike:
        print(
            f"ERROR: --short-strike ({short_strike}) must be > --long-strike ({long_strike})",
            file=sys.stderr,
        )
        sys.exit(1)
    if credit <= 0.0:
        print("ERROR: --credit must be positive", file=sys.stderr)
        sys.exit(1)
    width = short_strike - long_strike
    if credit >= width:
        print(
            f"ERROR: --credit ({credit}) must be < spread width ({width}); "
            "otherwise max_loss would be zero or negative",
            file=sys.stderr,
        )
        sys.exit(1)
    if dte <= 0:
        print("ERROR: --dte must be positive", file=sys.stderr)
        sys.exit(1)

    # Thresholds
    thresholds, thr_warnings = _load_thresholds(config_path)
    credit_width_min_ratio: float = thresholds.get(
        "credit_width_min_ratio", FALLBACK_THRESHOLDS["credit_width_min_ratio"]
    )

    # Core math
    max_profit = round(credit * 100.0, 4)
    max_loss = round((width - credit) * 100.0, 4)
    breakeven = round(short_strike - credit, 4)
    risk_reward = round(max_profit / max_loss, 4)

    # EV breakeven pop via ev_model (per-share units — ratio is unit-independent)
    warnings: List[str] = list(thr_warnings)
    ev_breakeven_pop = _compute_ev_breakeven_pop(
        avg_win_per_share=credit,
        avg_loss_per_share=-(width - credit),
        warnings=warnings,
    )

    # "收得太薄" warning (registry §4a)
    credit_ratio = credit / width
    if credit_ratio < credit_width_min_ratio:
        warnings.append(
            f"收得太薄：credit 仅占宽度 {credit_ratio:.0%}，"
            f"低于 {credit_width_min_ratio:.0%} 阈值，风险收益比较差"
        )

    _output({
        "model": "bull-put-spread",
        # Terminology hardcoded per registry §4a 硬规则
        "strategy_note": "收 credit 看多，非对冲工具",
        "inputs": {
            "short_strike": short_strike,
            "long_strike": long_strike,
            "credit": credit,
            "dte": dte,
            "spot": spot,
        },
        "width": round(width, 4),
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven": breakeven,
        "risk_reward": risk_reward,
        "ev_breakeven_pop": ev_breakeven_pop,
        "greeks_exposure": _greeks(
            delta="正（净多 delta，看多偏多）",
            theta="正（净空期权，时间流逝有利）",
            vega="负（净空波动率敞口，IV 上升不利）",
        ),
        "assignment_risk": {
            "spot_distance_pct": _spot_distance_pct(spot, short_strike),
            "dte_weeks": _dte_weeks(dte),
        },
        "units": {
            "max_profit": "per_contract_dollar",
            "max_loss": "per_contract_dollar",
            "breakeven": "per_share",
            "width": "per_share",
        },
        "warnings": warnings,
        "as_of": _as_of(),
    })


# ---------------------------------------------------------------------------
# Template: bear-put-spread
# Terminology (registry §4b hardcoded): 付 debit 看跌，对冲工具（非 bull put）
# ---------------------------------------------------------------------------

def _cmd_bear_put_spread(args: argparse.Namespace) -> None:
    """bear-put-spread: buy higher-strike put, sell lower-strike put.

    付 debit 看跌，对冲工具（非 bull put）。
    Used to hedge an existing long position (NOT a credit strategy).

    Registry §4b formula:
      width       = long_strike − short_strike   (per-share)
      max_profit  = (width − debit) × 100       (per-contract dollar)
      max_loss    = debit × 100                 (per-contract dollar, initial cost)
      breakeven   = long_strike − debit         (per-share)
    """
    long_strike: float = args.long_strike
    short_strike: float = args.short_strike
    debit: float = args.debit
    dte: int = args.dte
    spot: Optional[float] = args.spot
    config_path: Optional[str] = args.config

    # Validation
    if long_strike <= short_strike:
        print(
            f"ERROR: --long-strike ({long_strike}) must be > --short-strike ({short_strike})",
            file=sys.stderr,
        )
        sys.exit(1)
    if debit <= 0.0:
        print("ERROR: --debit must be positive", file=sys.stderr)
        sys.exit(1)
    width = long_strike - short_strike
    if debit >= width:
        print(
            f"ERROR: --debit ({debit}) must be < spread width ({width})",
            file=sys.stderr,
        )
        sys.exit(1)
    if dte <= 0:
        print("ERROR: --dte must be positive", file=sys.stderr)
        sys.exit(1)

    # Thresholds
    thresholds, thr_warnings = _load_thresholds(config_path)
    credit_width_min_ratio: float = thresholds.get(
        "credit_width_min_ratio", FALLBACK_THRESHOLDS["credit_width_min_ratio"]
    )

    # Core math
    max_profit = round((width - debit) * 100.0, 4)
    max_loss = round(debit * 100.0, 4)
    breakeven = round(long_strike - debit, 4)
    risk_reward = round(max_profit / max_loss, 4)

    warnings: List[str] = list(thr_warnings)
    # EV breakeven pop: avg_win = width-debit, avg_loss = -debit
    ev_breakeven_pop = _compute_ev_breakeven_pop(
        avg_win_per_share=(width - debit),
        avg_loss_per_share=-debit,
        warnings=warnings,
    )

    # Debit-ratio check (analogous to credit_width for bear spread)
    debit_ratio = debit / width
    if debit_ratio < credit_width_min_ratio:
        warnings.append(
            f"收得太薄（debit 侧）：debit 仅占宽度 {debit_ratio:.0%}，"
            f"低于 {credit_width_min_ratio:.0%} 阈值，保护效果有限"
        )

    _output({
        "model": "bear-put-spread",
        # Terminology hardcoded per registry §4b 硬规则
        "strategy_note": "付 debit 看跌，对冲工具（非 bull put）",
        "inputs": {
            "long_strike": long_strike,
            "short_strike": short_strike,
            "debit": debit,
            "dte": dte,
            "spot": spot,
        },
        "width": round(width, 4),
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven": breakeven,
        "risk_reward": risk_reward,
        "ev_breakeven_pop": ev_breakeven_pop,
        "greeks_exposure": _greeks(
            delta="负（净空 delta，看跌对冲）",
            theta="负（净多期权，时间流逝不利）",
            vega="正（净多波动率敞口，IV 上升有利）",
        ),
        "assignment_risk": {
            "spot_distance_pct": _spot_distance_pct(spot, short_strike),
            "dte_weeks": _dte_weeks(dte),
        },
        "units": {
            "max_profit": "per_contract_dollar",
            "max_loss": "per_contract_dollar",
            "breakeven": "per_share",
            "width": "per_share",
        },
        "warnings": warnings,
        "as_of": _as_of(),
    })


# ---------------------------------------------------------------------------
# Template: covered-call
# Note (hardcoded): 有 premium 的一次性止盈，不是真分层对冲
# ---------------------------------------------------------------------------

def _cmd_covered_call(args: argparse.Namespace) -> None:
    """covered-call: own 100 shares, sell OTM call to collect premium.

    有 premium 的一次性止盈，不是真分层对冲。

    Registry §4c formula:
      max_profit = (call_strike − entry_price + credit) × 100  (per-contract dollar)
      max_loss   = (entry_price − credit) × 100                (per-contract dollar, stock → 0)
      breakeven  = entry_price − credit                        (per-share)
    """
    entry_price: float = args.entry_price
    call_strike: float = args.call_strike
    credit: float = args.credit
    dte: int = args.dte
    spot: Optional[float] = args.spot
    config_path: Optional[str] = args.config

    # Validation
    if entry_price <= 0.0:
        print("ERROR: --entry-price must be positive", file=sys.stderr)
        sys.exit(1)
    if call_strike <= 0.0:
        print("ERROR: --call-strike must be positive", file=sys.stderr)
        sys.exit(1)
    if credit <= 0.0:
        print("ERROR: --credit must be positive", file=sys.stderr)
        sys.exit(1)
    if credit >= entry_price:
        print(
            f"ERROR: --credit ({credit}) must be < --entry-price ({entry_price})",
            file=sys.stderr,
        )
        sys.exit(1)
    if dte <= 0:
        print("ERROR: --dte must be positive", file=sys.stderr)
        sys.exit(1)

    # Thresholds (not used for covered-call warnings currently, loaded for extensibility)
    thresholds, thr_warnings = _load_thresholds(config_path)

    # Core math
    max_profit_per_share = call_strike - entry_price + credit
    max_loss_per_share = entry_price - credit
    max_profit = round(max_profit_per_share * 100.0, 4)
    max_loss = round(max_loss_per_share * 100.0, 4)
    breakeven = round(entry_price - credit, 4)
    risk_reward = round(max_profit / max_loss, 4) if max_loss != 0 else None

    warnings: List[str] = list(thr_warnings)
    ev_breakeven_pop = _compute_ev_breakeven_pop(
        avg_win_per_share=max_profit_per_share,
        avg_loss_per_share=-max_loss_per_share,
        warnings=warnings,
    )

    # Assignment risk: distance from spot to call_strike (upside assignment)
    call_dist_pct: Optional[float] = None
    if spot is not None:
        call_dist_pct = round((call_strike - spot) / spot * 100, 2)

    _output({
        "model": "covered-call",
        # Terminology hardcoded per registry §4c
        "strategy_note": "有 premium 的一次性止盈，不是真分层对冲",
        "inputs": {
            "entry_price": entry_price,
            "call_strike": call_strike,
            "credit": credit,
            "dte": dte,
            "spot": spot,
        },
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven": breakeven,
        "risk_reward": risk_reward,
        "ev_breakeven_pop": ev_breakeven_pop,
        "greeks_exposure": _greeks(
            delta="正（持股 delta 主导，short call 略减）",
            theta="正（short call 时间价值收益）",
            vega="负（short call vega 负敞口）",
        ),
        "assignment_risk": {
            "call_strike_distance_pct": call_dist_pct,
            "dte_weeks": _dte_weeks(dte),
        },
        "units": {
            "max_profit": "per_contract_dollar",
            "max_loss": "per_contract_dollar",
            "breakeven": "per_share",
        },
        "warnings": warnings,
        "as_of": _as_of(),
    })


# ---------------------------------------------------------------------------
# Template: cash-secured-put
# ---------------------------------------------------------------------------

def _cmd_cash_secured_put(args: argparse.Namespace) -> None:
    """cash-secured-put: sell put secured by cash equal to strike × 100.

    收 credit，愿意以 strike 价买入标的。

    Registry §4d formula:
      max_profit = credit × 100               (per-contract dollar)
      max_loss   = (strike − credit) × 100   (per-contract dollar, stock → 0)
      breakeven  = strike − credit            (per-share)
    """
    strike: float = args.strike
    credit: float = args.credit
    dte: int = args.dte
    spot: Optional[float] = args.spot
    config_path: Optional[str] = args.config

    # Validation
    if strike <= 0.0:
        print("ERROR: --strike must be positive", file=sys.stderr)
        sys.exit(1)
    if credit <= 0.0:
        print("ERROR: --credit must be positive", file=sys.stderr)
        sys.exit(1)
    if credit >= strike:
        print(
            f"ERROR: --credit ({credit}) must be < --strike ({strike})",
            file=sys.stderr,
        )
        sys.exit(1)
    if dte <= 0:
        print("ERROR: --dte must be positive", file=sys.stderr)
        sys.exit(1)

    # Thresholds
    thresholds, thr_warnings = _load_thresholds(config_path)

    # Core math
    max_profit = round(credit * 100.0, 4)
    max_loss = round((strike - credit) * 100.0, 4)
    breakeven = round(strike - credit, 4)
    risk_reward = round(max_profit / max_loss, 4)

    warnings: List[str] = list(thr_warnings)
    ev_breakeven_pop = _compute_ev_breakeven_pop(
        avg_win_per_share=credit,
        avg_loss_per_share=-(strike - credit),
        warnings=warnings,
    )

    _output({
        "model": "cash-secured-put",
        "strategy_note": "收 credit，愿意以 strike 价买入标的",
        "inputs": {
            "strike": strike,
            "credit": credit,
            "dte": dte,
            "spot": spot,
        },
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven": breakeven,
        "risk_reward": risk_reward,
        "ev_breakeven_pop": ev_breakeven_pop,
        "greeks_exposure": _greeks(
            delta="正（short put delta 为正，相当于偏多）",
            theta="正（short option，时间流逝有利）",
            vega="负（short option，IV 上升不利）",
        ),
        "assignment_risk": {
            "spot_distance_pct": _spot_distance_pct(spot, strike),
            "dte_weeks": _dte_weeks(dte),
        },
        "units": {
            "max_profit": "per_contract_dollar",
            "max_loss": "per_contract_dollar",
            "breakeven": "per_share",
        },
        "warnings": warnings,
        "as_of": _as_of(),
    })


# ---------------------------------------------------------------------------
# Template: long-put
# ---------------------------------------------------------------------------

def _cmd_long_put(args: argparse.Namespace) -> None:
    """long-put: buy put for directional downside or as a hedge.

    付 debit，方向性看跌或对冲多头。

    Registry §4e formula:
      max_profit = (strike − debit) × 100   (per-contract dollar, stock → 0)
      max_loss   = debit × 100              (per-contract dollar, premium total loss)
      breakeven  = strike − debit           (per-share)
    """
    strike: float = args.strike
    debit: float = args.debit
    dte: int = args.dte
    spot: Optional[float] = args.spot
    config_path: Optional[str] = args.config

    # Validation
    if strike <= 0.0:
        print("ERROR: --strike must be positive", file=sys.stderr)
        sys.exit(1)
    if debit <= 0.0:
        print("ERROR: --debit must be positive", file=sys.stderr)
        sys.exit(1)
    if debit >= strike:
        print(
            f"ERROR: --debit ({debit}) must be < --strike ({strike})",
            file=sys.stderr,
        )
        sys.exit(1)
    if dte <= 0:
        print("ERROR: --dte must be positive", file=sys.stderr)
        sys.exit(1)

    # Thresholds (loaded for consistency; no specific check for long-put currently)
    thresholds, thr_warnings = _load_thresholds(config_path)

    # Core math
    max_profit = round((strike - debit) * 100.0, 4)
    max_loss = round(debit * 100.0, 4)
    breakeven = round(strike - debit, 4)
    risk_reward = round(max_profit / max_loss, 4)

    warnings: List[str] = list(thr_warnings)
    ev_breakeven_pop = _compute_ev_breakeven_pop(
        avg_win_per_share=(strike - debit),
        avg_loss_per_share=-debit,
        warnings=warnings,
    )

    # Distance from spot to strike (informational; long-put buyer has no assignment risk)
    strike_dist_pct: Optional[float] = None
    if spot is not None:
        strike_dist_pct = round((spot - strike) / strike * 100, 2)

    _output({
        "model": "long-put",
        "strategy_note": "付 debit，方向性看跌或对冲多头",
        "inputs": {
            "strike": strike,
            "debit": debit,
            "dte": dte,
            "spot": spot,
        },
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakeven": breakeven,
        "risk_reward": risk_reward,
        "ev_breakeven_pop": ev_breakeven_pop,
        "greeks_exposure": _greeks(
            delta="负（long put delta 为负，看跌）",
            theta="负（long option，时间流逝不利）",
            vega="正（long option，IV 上升有利）",
        ),
        # long-put buyer has no early-assignment risk; field included for schema consistency
        "assignment_risk": {
            "spot_distance_pct": strike_dist_pct,
            "dte_weeks": _dte_weeks(dte),
            "note": "买方无被指派风险",
        },
        "units": {
            "max_profit": "per_contract_dollar",
            "max_loss": "per_contract_dollar",
            "breakeven": "per_share",
        },
        "warnings": warnings,
        "as_of": _as_of(),
    })


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> StrictParser:
    parser = StrictParser(
        description="Option strategy math templates (stdlib, Python 3.9+)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # Shared config argument added to each sub-parser
    def _add_config(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--config",
            type=str,
            default=None,
            metavar="PATH",
            help="Path to thresholds JSON (default: same-dir thresholds.json)",
        )

    def _add_dte(p: argparse.ArgumentParser) -> None:
        p.add_argument("--dte", type=int, required=True, help="Days to expiration")

    def _add_spot(p: argparse.ArgumentParser) -> None:
        p.add_argument("--spot", type=float, default=None,
                       help="Current underlying price (optional, for assignment_risk)")

    # -- bull-put-spread --
    bps = sub.add_parser("bull-put-spread",
                         help="Sell higher-strike put, buy lower-strike put (credit, bullish)")
    bps.add_argument("--short-strike", type=float, required=True,
                     help="Short put strike (must be > long-strike)")
    bps.add_argument("--long-strike", type=float, required=True,
                     help="Long put strike")
    bps.add_argument("--credit", type=float, required=True,
                     help="Net credit received per share")
    _add_dte(bps)
    _add_spot(bps)
    _add_config(bps)

    # -- bear-put-spread --
    brs = sub.add_parser("bear-put-spread",
                         help="Buy higher-strike put, sell lower-strike put (debit, hedge)")
    brs.add_argument("--long-strike", type=float, required=True,
                     help="Long put strike (higher, must be > short-strike)")
    brs.add_argument("--short-strike", type=float, required=True,
                     help="Short put strike (lower)")
    brs.add_argument("--debit", type=float, required=True,
                     help="Net debit paid per share")
    _add_dte(brs)
    _add_spot(brs)
    _add_config(brs)

    # -- covered-call --
    cc = sub.add_parser("covered-call",
                        help="Own 100 shares, sell call to collect premium")
    cc.add_argument("--entry-price", type=float, required=True,
                    help="Cost basis of stock per share")
    cc.add_argument("--call-strike", type=float, required=True,
                    help="Short call strike price")
    cc.add_argument("--credit", type=float, required=True,
                    help="Premium received per share")
    _add_dte(cc)
    _add_spot(cc)
    _add_config(cc)

    # -- cash-secured-put --
    csp = sub.add_parser("cash-secured-put",
                         help="Sell put secured by cash equal to strike × 100")
    csp.add_argument("--strike", type=float, required=True,
                     help="Short put strike price")
    csp.add_argument("--credit", type=float, required=True,
                     help="Premium received per share")
    _add_dte(csp)
    _add_spot(csp)
    _add_config(csp)

    # -- long-put --
    lp = sub.add_parser("long-put",
                        help="Buy put for directional downside or hedge")
    lp.add_argument("--strike", type=float, required=True,
                    help="Put strike price")
    lp.add_argument("--debit", type=float, required=True,
                    help="Premium paid per share")
    _add_dte(lp)
    _add_spot(lp)
    _add_config(lp)

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

    if args.command == "bull-put-spread":
        _cmd_bull_put_spread(args)
    elif args.command == "bear-put-spread":
        _cmd_bear_put_spread(args)
    elif args.command == "covered-call":
        _cmd_covered_call(args)
    elif args.command == "cash-secured-put":
        _cmd_cash_secured_put(args)
    elif args.command == "long-put":
        _cmd_long_put(args)
    else:
        print(f"ERROR: unknown command '{args.command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

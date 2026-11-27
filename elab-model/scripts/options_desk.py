#!/usr/bin/env python3
"""Options desk models for the user's own trades (standard library only).

Subcommands:
  check   pre-trade check: compare a proposed multi-leg trade with the user's own rules
          (days to expiry, short-leg delta, width, credit / width, earnings, margin budget,
          cash to take assignment), then expiry and holding-period P/L
  roll    close the current legs and open new ones: net credit or debit, P/L locked in,
          new max loss / breakeven including all cash collected so far, roll-count rules
  assign  what happens if short legs are assigned: shares, cash needed, effective cost
  margin  Reg-T style margin estimate with the formula spelled out

Legs: {"type": "put"|"call"|"stock", "side": "long"|"short", "strike", "premium" (per share,
positive; for stock the entry price), "ratio" (default 1), "dte", "iv", "delta", "mark"}.
Holding-period values use Black-Scholes (European, no dividends) with the IV held constant.

All inputs are user-supplied local JSON; nothing is fetched. stdout carries JSON only, errors
go to stderr with exit code 1. Outputs describe arithmetic under the stated inputs; they are
not trade instructions, probabilities of profit or recommendations.
"""
import argparse
import json
import math
import sys
from datetime import date

DEFAULT_MULTIPLIER = 100
SPOT_MOVES = (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15)
KNOWN_STRUCTURE_RULES = {"dte_min", "dte_max", "short_delta_min", "short_delta_max", "width_max",
                         "width_max_steps", "strike_step", "credit_to_width_max", "credit_to_width_min",
                         "avoid_earnings", "take_profit", "note"}
KNOWN_TOP_RULES = {"source", "structures", "budget", "sell_put", "roll", "note"}


class InputError(Exception):
    pass


def fail(msg):
    raise InputError(msg)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")


def num(value, name, low=None, high=None, low_open=False):
    try:
        x = float(value)
    except (TypeError, ValueError):
        fail(f"{name} must be a number")
    if not math.isfinite(x):
        fail(f"{name} must be finite")
    if low is not None and (x < low or (low_open and x == low)):
        fail(f"{name} must be {'>' if low_open else '>='} {low}")
    if high is not None and x > high:
        fail(f"{name} must be <= {high}")
    return x


def r4(x):
    return None if x is None else round(x, 4)


# ------------------------------------------------------------------ display helpers

def d_money(x):
    if x is None:
        return "无上限"
    return f"{x:,.0f}" if abs(x - round(x)) < 1e-9 else f"{x:,.2f}"


def d_px(x):
    return "—" if x is None else f"{x:.2f}"


def d_pct(x, signed=False):
    if x is None:
        return "—"
    return f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"


def md_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def md_list(items):
    return "\n".join(f"- {x}" for x in items) if items else "- 无"


# ------------------------------------------------------------------ legs

def parse_legs(raw, name="legs", need_premium=True):
    if not isinstance(raw, list) or not raw:
        fail(f"{name} must be a non-empty list")
    legs = []
    for i, lg in enumerate(raw):
        t = str(lg.get("type", "")).lower()
        side = str(lg.get("side", "")).lower()
        if t not in ("put", "call", "stock"):
            fail(f"{name}[{i}].type must be put, call or stock")
        if side not in ("long", "short"):
            fail(f"{name}[{i}].side must be long or short")
        leg = dict(type=t, side=side, sign=1 if side == "long" else -1,
                   ratio=num(lg.get("ratio", 1), f"{name}[{i}].ratio", 0, low_open=True))
        if t == "stock":
            leg["strike"] = None
            leg["premium"] = num(lg.get("premium", lg.get("price")), f"{name}[{i}].premium (entry price)", 0)
            leg["dte"] = None
        else:
            leg["strike"] = num(lg.get("strike"), f"{name}[{i}].strike", 0, low_open=True)
            leg["premium"] = (num(lg.get("premium"), f"{name}[{i}].premium", 0) if need_premium or lg.get("premium") is not None
                              else None)
            leg["dte"] = None if lg.get("dte") is None else int(num(lg.get("dte"), f"{name}[{i}].dte", 0))
        leg["iv"] = None if lg.get("iv") is None else num(lg["iv"], f"{name}[{i}].iv", 0, 5, low_open=True)
        leg["delta"] = None if lg.get("delta") is None else num(lg["delta"], f"{name}[{i}].delta", -1, 1)
        leg["mark"] = None if lg.get("mark") is None else num(lg["mark"], f"{name}[{i}].mark", 0)
        legs.append(leg)
    return legs


def option_legs(legs):
    return [lg for lg in legs if lg["type"] != "stock"]


def common_dte(legs):
    dtes = {lg["dte"] for lg in option_legs(legs)}
    if None in dtes:
        return None
    if len(dtes) > 1:
        fail("legs with different expiries are not supported yet (calendars / diagonals)")
    return dtes.pop() if dtes else None


def intrinsic(lg, s):
    if lg["type"] == "call":
        return max(s - lg["strike"], 0.0)
    if lg["type"] == "put":
        return max(lg["strike"] - s, 0.0)
    return s


def expiry_pl(legs, s, cash_per_share):
    """Per-share P/L at expiry for one unit of the structure, plus cash already received."""
    total = cash_per_share
    for lg in legs:
        total += lg["sign"] * lg["ratio"] * intrinsic(lg, s)
    return total


def entry_cash(legs):
    """Cash received at entry per share (positive = net credit)."""
    return sum(-lg["sign"] * lg["ratio"] * lg["premium"] for lg in legs)


def payoff_profile(legs, cash_per_share):
    strikes = sorted({lg["strike"] for lg in legs if lg["strike"]})
    top = max(strikes + [lg["premium"] for lg in legs if lg["type"] == "stock"] + [1.0]) * 3
    points = [0.0] + strikes + [top]
    values = [expiry_pl(legs, p, cash_per_share) for p in points]
    slope_up = sum(lg["sign"] * lg["ratio"] for lg in legs if lg["type"] in ("call", "stock"))
    max_profit = None if slope_up > 1e-12 else max(values)
    max_loss = None if slope_up < -1e-12 else min(values)
    breakevens = []
    for (a, va), (b, vb) in zip(zip(points, values), zip(points[1:], values[1:])):
        if va == 0:
            breakevens.append(a)
        elif va * vb < 0:
            breakevens.append(a + (b - a) * (-va) / (vb - va))
    if values[-1] == 0:
        breakevens.append(points[-1])
    if abs(slope_up) > 1e-12 and values[-1] * slope_up < 0:
        breakevens.append(points[-1] - values[-1] / slope_up)
    return dict(max_profit=max_profit, max_loss=max_loss,
                breakevens=sorted({round(b, 4) for b in breakevens}))


# ------------------------------------------------------------------ Black-Scholes

def n_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def n_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs(lg, s, t_years, r):
    """Price and greeks of one option leg (per share, unsigned)."""
    k, sigma = lg["strike"], lg["iv"]
    if t_years <= 0 or sigma is None:
        return dict(price=intrinsic(lg, s), delta=None, gamma=None, theta=None, vega=None)
    st = sigma * math.sqrt(t_years)
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t_years) / st
    d2 = d1 - st
    disc = math.exp(-r * t_years)
    if lg["type"] == "call":
        price = s * n_cdf(d1) - k * disc * n_cdf(d2)
        delta = n_cdf(d1)
        theta = -s * n_pdf(d1) * sigma / (2 * math.sqrt(t_years)) - r * k * disc * n_cdf(d2)
    else:
        price = k * disc * n_cdf(-d2) - s * n_cdf(-d1)
        delta = n_cdf(d1) - 1
        theta = -s * n_pdf(d1) * sigma / (2 * math.sqrt(t_years)) + r * k * disc * n_cdf(-d2)
    return dict(price=price, delta=delta, gamma=n_pdf(d1) / (s * st),
                theta=theta / 365, vega=s * n_pdf(d1) * math.sqrt(t_years) / 100)


def holding_value(legs, s, days_elapsed, r):
    total = 0.0
    for lg in legs:
        if lg["type"] == "stock":
            total += lg["sign"] * lg["ratio"] * s
        else:
            t = max(lg["dte"] - days_elapsed, 0) / 365
            total += lg["sign"] * lg["ratio"] * bs(lg, s, t, r)["price"]
    return total


def can_price(legs):
    return all(lg["iv"] is not None and lg["dte"] is not None for lg in option_legs(legs))


def holding_grid(legs, spot, r, scale):
    dte = common_dte(legs)
    cost = sum(lg["sign"] * lg["ratio"] * lg["premium"] for lg in legs)
    cols = sorted({min(7, dte), dte // 2, dte}) if dte else [0]
    rows = []
    for mv in SPOT_MOVES:
        s = spot * (1 + mv)
        rows.append([mv] + [(holding_value(legs, s, d, r) - cost) * scale for d in cols])
    return cols, rows


def position_greeks(legs, spot, r, scale):
    out = dict(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)
    for lg in legs:
        if lg["type"] == "stock":
            out["delta"] += lg["sign"] * lg["ratio"] * scale
            continue
        g = bs(lg, spot, lg["dte"] / 365, r)
        for k in out:
            out[k] += lg["sign"] * lg["ratio"] * g[k] * scale
    return {k: r4(v) for k, v in out.items()}


# ------------------------------------------------------------------ structure helpers

def classify(legs):
    opts = option_legs(legs)
    stocks = [lg for lg in legs if lg["type"] == "stock"]
    if len(opts) == 1 and not stocks:
        lg = opts[0]
        return f"{lg['side']}_{lg['type']}"
    if len(opts) == 2 and not stocks and opts[0]["type"] == opts[1]["type"] \
            and opts[0]["sign"] != opts[1]["sign"] and opts[0]["ratio"] == opts[1]["ratio"]:
        short = next(lg for lg in opts if lg["sign"] < 0)
        long_ = next(lg for lg in opts if lg["sign"] > 0)
        if short["type"] == "put":
            return "bull_put_spread" if short["strike"] > long_["strike"] else "bear_put_spread"
        return "bear_call_spread" if short["strike"] < long_["strike"] else "bull_call_spread"
    if len(opts) == 1 and len(stocks) == 1 and opts[0]["type"] == "call" and opts[0]["sign"] < 0 \
            and stocks[0]["sign"] > 0:
        return "covered_call"
    return "custom"


STRUCTURE_CN = dict(bull_put_spread="牛市看跌价差（BPS）", bear_put_spread="熊市看跌价差", bear_call_spread="熊市看涨价差",
                    bull_call_spread="牛市看涨价差（BCS）", short_put="卖出看跌（sell put）", short_call="卖出看涨",
                    long_put="买入看跌", long_call="买入看涨", covered_call="备兑看涨（covered call）", custom="自定义组合")


def vertical_width(legs):
    opts = option_legs(legs)
    if len(opts) == 2 and opts[0]["type"] == opts[1]["type"]:
        return abs(opts[0]["strike"] - opts[1]["strike"])
    return None


def margin_estimate(legs, spot, structure):
    """Per-share requirement for one unit, with the formula used. None when not estimated."""
    opts = option_legs(legs)
    credit = entry_cash(legs)
    if structure in ("bull_put_spread", "bear_call_spread"):
        w = vertical_width(legs)
        return dict(requirement=w, basis="价宽", formula=f"价宽 {d_px(w)}（最大亏损是价宽减去收到的 {d_px(credit)}）",
                    max_loss_basis=w - credit)
    if structure in ("bear_put_spread", "bull_call_spread", "long_put", "long_call"):
        return dict(requirement=-credit, basis="付出的权利金", formula=f"付出的权利金 {d_px(-credit)}")
    if structure == "short_put":
        k, p = opts[0]["strike"], opts[0]["premium"]
        otm = max(spot - k, 0.0)
        naked = p + max(0.20 * spot - otm, 0.10 * k)
        return dict(requirement=naked, basis="Reg-T 裸卖口径",
                    formula=f"权利金 {d_px(p)} + max(20% × 现价 {d_px(spot)} − 价外 {d_px(otm)}，10% × 行权价 {d_px(k)})",
                    cash_secured=k - p)
    if structure == "short_call":
        k, p = opts[0]["strike"], opts[0]["premium"]
        otm = max(k - spot, 0.0)
        naked = p + max(0.20 * spot - otm, 0.10 * spot)
        return dict(requirement=naked, basis="Reg-T 裸卖口径",
                    formula=f"权利金 {d_px(p)} + max(20% × 现价 {d_px(spot)} − 价外 {d_px(otm)}，10% × 现价)")
    if structure == "covered_call":
        return dict(requirement=0.0, basis="正股覆盖", formula="已持有正股覆盖，期权本身不另占保证金")
    return None


def parse_trade(cfg):
    spot = num(cfg.get("spot"), "spot", 0, low_open=True)
    mult = num(cfg.get("multiplier", DEFAULT_MULTIPLIER), "multiplier", 0, low_open=True)
    contracts = num(cfg.get("contracts", 1), "contracts", 0, low_open=True)
    legs = parse_legs(cfg.get("legs"))
    return dict(name=str(cfg.get("underlying", "")), currency=str(cfg.get("currency", "")),
                as_of=cfg.get("as_of"), spot=spot, mult=mult, contracts=contracts, legs=legs,
                scale=mult * contracts, rate=cfg.get("rate"),
                kind=cfg.get("underlying_kind"), earnings=cfg.get("earnings_date"),
                account=cfg.get("account") or {})


def rate_of(t, warnings):
    if t["rate"] is None:
        warnings.append("没给无风险利率，持有期估值按 0 算")
        return 0.0
    return num(t["rate"], "rate", -0.1, 0.5)


def legs_rows(legs):
    rows = []
    for lg in legs:
        side = "买入" if lg["sign"] > 0 else "卖出"
        if lg["type"] == "stock":
            rows.append([f"{side}正股", "—", d_px(lg["premium"]), "—", "—", "—"])
        else:
            rows.append([f"{side}{'看涨' if lg['type'] == 'call' else '看跌'}", d_px(lg["strike"]), d_px(lg["premium"]),
                         "—" if lg["dte"] is None else f"{lg['dte']} 天",
                         "—" if lg["delta"] is None else f"{lg['delta']:+.2f}",
                         "—" if lg["iv"] is None else d_pct(lg["iv"])])
    return rows


def grid_md(cols, rows):
    head = ["标的价格变动"] + [("到期" if i == len(cols) - 1 else f"过 {d} 天") for i, d in enumerate(cols)]
    body = [[d_pct(mv, signed=True)] + [f"{v:+,.0f}" for v in vals] for mv, *vals in rows]
    return md_table(head, body)


def profile_rows(prof, scale, credit):
    be = "、".join(d_px(b) for b in prof["breakevens"]) or "—"
    return [["收付（整笔）", f"{'收到' if credit >= 0 else '付出'} {d_money(abs(credit) * scale)}"],
            ["到期最多赚", d_money(None if prof["max_profit"] is None else prof["max_profit"] * scale)],
            ["到期最多亏", d_money(None if prof["max_loss"] is None else -prof["max_loss"] * scale)],
            ["盈亏平衡价", be]]


# ------------------------------------------------------------------ check

def cmd_check(args):
    t = parse_trade(load_json(args.trade))
    rules = load_json(args.rules) if args.rules else None
    warnings, checks = [], []
    legs, spot, scale = t["legs"], t["spot"], t["scale"]
    structure = classify(legs)
    credit = entry_cash(legs)
    prof = payoff_profile(legs, credit)
    dte = common_dte(legs)
    margin = margin_estimate(legs, spot, structure)
    margin_total = None if margin is None else margin["requirement"] * scale
    if margin is None:
        warnings.append("这个组合的保证金脚本不估，按券商显示为准")

    def add(name, rule_text, actual_text, ok):
        status = "缺数据" if ok is None else ("符合" if ok else "不符合")
        checks.append(dict(rule=name, rule_value=rule_text, actual=actual_text, status=status))

    if rules is None:
        warnings.append("没有提供你的规则文件，只算这张单子的数，不做规则核对")
        srules, budget, sp_rules = {}, {}, {}
    else:
        unknown_top = sorted(set(rules) - KNOWN_TOP_RULES)
        srules = (rules.get("structures") or {}).get(structure)
        if srules is None:
            warnings.append(f"你的规则里没有「{STRUCTURE_CN[structure]}」这一类，结构类规则不核对")
            srules = {}
        unknown = sorted(set(srules) - KNOWN_STRUCTURE_RULES) + unknown_top
        if unknown:
            warnings.append("这些规则脚本还不会自动核对：" + "、".join(unknown))
        budget = rules.get("budget") or {}
        sp_rules = rules.get("sell_put") or {}

    shorts = [lg for lg in option_legs(legs) if lg["sign"] < 0]
    r = rate_of(t, warnings) if can_price(legs) else 0.0

    if "dte_min" in srules or "dte_max" in srules:
        lo, hi = srules.get("dte_min"), srules.get("dte_max")
        txt = f"{lo if lo is not None else '—'}～{hi if hi is not None else '—'} 天"
        add("到期天数", txt, "—" if dte is None else f"{dte} 天",
            None if dte is None else ((lo is None or dte >= lo) and (hi is None or dte <= hi)))
    if "short_delta_min" in srules or "short_delta_max" in srules:
        lo, hi = srules.get("short_delta_min"), srules.get("short_delta_max")
        for lg in shorts:
            dv, est = lg["delta"], False
            if dv is None and lg["iv"] is not None and lg["dte"]:
                dv, est = bs(lg, spot, lg["dte"] / 365, r)["delta"], True
            a = None if dv is None else abs(dv)
            add(f"卖腿 Delta（行权价 {d_px(lg['strike'])}）", f"{lo if lo is not None else '—'}～{hi if hi is not None else '—'}",
                "—" if a is None else f"{a:.2f}{'（按 IV 估算）' if est else ''}",
                None if a is None else ((lo is None or a >= lo) and (hi is None or a <= hi)))
    width = vertical_width(legs)
    if "width_max" in srules or "width_max_steps" in srules:
        wmax = srules.get("width_max")
        txt = d_px(wmax) if wmax is not None else None
        if wmax is None:
            step = srules.get("strike_step")
            if step:
                wmax = srules["width_max_steps"] * step
                txt = f"{srules['width_max_steps']} 档 × {d_px(step)} = {d_px(wmax)}"
            else:
                txt = f"{srules['width_max_steps']} 档（没给行权价间隔，没法换算）"
        add("价宽", txt, "—" if width is None else d_px(width),
            None if width is None or wmax is None else width <= wmax + 1e-9)
    if width and ("credit_to_width_max" in srules or "credit_to_width_min" in srules):
        ratio = credit / width
        lo, hi = srules.get("credit_to_width_min"), srules.get("credit_to_width_max")
        add("收到的权利金 / 价宽", f"{d_pct(lo) if lo is not None else '—'}～{d_pct(hi) if hi is not None else '—'}",
            d_pct(ratio), (lo is None or ratio >= lo) and (hi is None or ratio <= hi))
    if srules.get("avoid_earnings"):
        ed = t["earnings"]
        if ed and t["as_of"] and dte is not None:
            try:
                days_to = (date.fromisoformat(str(ed)) - date.fromisoformat(str(t["as_of"]))).days
            except ValueError:
                fail("earnings_date and as_of must be ISO dates")
            add("持仓期间避开财报", "避开", f"财报在 {days_to} 天后，到期在 {dte} 天后", not (0 <= days_to <= dte))
        else:
            add("持仓期间避开财报", "避开", "没给财报日期或今天日期", None)
    acct = t["account"]
    if budget.get("options_margin_total") is not None:
        used = acct.get("options_margin_used")
        tot = budget["options_margin_total"]
        after = None if used is None or margin_total is None else used + margin_total
        add("期权总保证金预算", d_money(tot), "—" if after is None else f"加上这笔后 {d_money(after)}",
            None if after is None else after <= tot)
    if budget.get("per_underlying_max") is not None:
        used = acct.get("underlying_margin_used", 0)
        after = None if margin_total is None else used + margin_total
        add("单个标的保证金上限", d_money(budget["per_underlying_max"]), "—" if after is None else f"加上这笔后 {d_money(after)}",
            None if after is None else after <= budget["per_underlying_max"])
    if structure == "short_put" and sp_rules:
        if sp_rules.get("index_only"):
            kind = t["kind"]
            add("卖看跌只做指数", "只做指数", kind or "没说明标的类型", None if not kind else kind == "index")
        if sp_rules.get("size_by_cash"):
            need = shorts[0]["strike"] * scale
            cash = acct.get("cash")
            add("手数按接盘现金定", f"接盘要 {d_money(need)}", "—" if cash is None else f"现金 {d_money(cash)}",
                None if cash is None else cash >= need)

    ok = sum(c["status"] == "符合" for c in checks)
    bad = sum(c["status"] == "不符合" for c in checks)
    miss = sum(c["status"] == "缺数据" for c in checks)
    for lg in option_legs(legs):
        if lg["type"] == "put" and lg["sign"] < 0 and lg["strike"] > spot * 1.1:
            warnings.append("卖出的看跌已深度价内，美式期权可能被提前行权")
            break

    out = dict(model="options_desk.check", underlying=t["name"], currency=t["currency"], as_of=t["as_of"],
               structure=structure, spot=spot, contracts=t["contracts"], multiplier=t["mult"],
               entry_cash_per_share=r4(credit), profile={k: (r4(v) if not isinstance(v, list) else v) for k, v in prof.items()},
               margin=None if margin is None else {k: (r4(v) if isinstance(v, float) else v) for k, v in margin.items()},
               margin_total=r4(margin_total), checks=checks, summary=dict(ok=ok, fail=bad, missing=miss))
    grid_md_s = None
    if can_price(legs) and dte:
        cols, rows = holding_grid(legs, spot, r, scale)
        out["holding_grid"] = dict(days=cols, moves=list(SPOT_MOVES), pl=[[r4(v) for v in row[1:]] for row in rows])
        out["greeks"] = position_greeks(legs, spot, r, scale)
        grid_md_s = grid_md(cols, rows)
        warnings.append("持有期盈亏假设 IV 不变、按欧式期权估算，实际成交价会偏离")
    else:
        warnings.append("没给每条腿的 IV 和到期天数，只算到期盈亏，不算持有期")

    lines = [f"这是一张{STRUCTURE_CN[structure]}，{d_money(t['contracts'])} 张，"
             f"{'收到' if credit >= 0 else '付出'} {d_money(abs(credit) * scale)}，到期最多亏 "
             f"{d_money(None if prof['max_loss'] is None else -prof['max_loss'] * scale)}。"]
    if checks:
        lines.append(f"对照你的规则：{ok} 条符合，{bad} 条不符合，{miss} 条缺数据。")
    for c in checks:
        if c["status"] == "不符合":
            lines.append(f"「{c['rule']}」没过：{c['actual']}；你的规则是 {c['rule_value']}。")
    if margin_total is not None:
        lines.append(f"按{' ' if margin['basis'][0].isascii() else ''}{margin['basis']}估，这笔大约占用 {d_money(margin_total)} 保证金，以券商显示为准。")
    if rules and (rules.get("structures") or {}).get(structure, {}).get("take_profit"):
        tp = rules["structures"][structure]["take_profit"]
        lines.append("你规则里的止盈档：" + "、".join(d_pct(x) for x in tp) + "，建仓时一起挂好。")

    notes = ["规则来自你自己的文件，这里只核对，不替你改规则",
             "到期盈亏按行权价之间的直线算，最多赚、最多亏和盈亏平衡价都是精确值"]
    out["display"] = dict(
        warnings_md=md_list(warnings),
        legs_md=md_table(["腿", "行权价", "权利金", "到期", "Delta", "IV"], legs_rows(legs)),
        checks_md=md_table(["规则", "你的规则", "这张单子", "结果"],
                           [[c["rule"], c["rule_value"], c["actual"], c["status"]] for c in checks]) if checks else "- 没有可核对的规则",
        result_md=md_table(["项目", "数值"], profile_rows(prof, scale, credit)
                           + ([["保证金估算", f"{d_money(margin_total)}（{margin['basis']}）"]] if margin_total is not None else [])),
        grid_md=grid_md_s, notes_md=md_list(notes), lines=lines)
    out.update(warnings=warnings, units=dict(money=f"{t['currency'] or 'input_currency'}_total", per_share="per_share"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ roll

def cmd_roll(args):
    cfg = load_json(args.position)
    t = parse_trade(dict(cfg, legs=cfg.get("legs_open")))
    new_legs = parse_legs(cfg.get("legs_new"), "legs_new")
    if any(lg["type"] == "stock" for lg in t["legs"] + new_legs):
        fail("roll only handles option legs; for a covered call list only the call legs")
    rules = load_json(args.rules) if args.rules else None
    warnings, checks = [], []
    old, scale = t["legs"], t["scale"]
    for i, lg in enumerate(old):
        if lg["mark"] is None and lg["type"] != "stock":
            fail(f"legs_open[{i}].mark (current price to close) is required")
    open_cash = entry_cash(old)
    close_cash = sum(lg["sign"] * lg["ratio"] * (lg["mark"] if lg["type"] != "stock" else t["spot"]) for lg in old
                     if lg["type"] != "stock")
    new_open = entry_cash(new_legs)
    net_roll = close_cash + new_open
    locked = sum(lg["sign"] * lg["ratio"] * (lg["mark"] - lg["premium"]) for lg in option_legs(old))
    prior = num(cfg.get("prior_roll_cash", 0), "prior_roll_cash")
    cumulative = open_cash + prior + net_roll
    old_prof = payoff_profile(old, open_cash + prior)
    new_alone = payoff_profile(new_legs, new_open)
    new_total = payoff_profile(new_legs, cumulative)
    old_dte, new_dte = common_dte(old), common_dte(new_legs)
    rolls_done = int(num(cfg.get("rolls_done", 0), "rolls_done", 0))
    rrules = (rules or {}).get("roll") or {}
    if rrules.get("max_rolls") is not None:
        checks.append(dict(rule="最多移仓次数", rule_value=f"{rrules['max_rolls']} 次", actual=f"这次是第 {rolls_done + 1} 次",
                           status="符合" if rolls_done + 1 <= rrules["max_rolls"] else "不符合"))
    if rrules.get("keep_strike"):
        old_k = sorted(lg["strike"] for lg in option_legs(old) if lg["sign"] < 0)
        new_k = sorted(lg["strike"] for lg in option_legs(new_legs) if lg["sign"] < 0)
        checks.append(dict(rule="移仓时行权价不变", rule_value="不变", actual="、".join(d_px(k) for k in new_k),
                           status="符合" if old_k == new_k else "不符合"))
    if rules is None:
        warnings.append("没有提供你的规则文件，只算移仓的数，不做规则核对")
    if net_roll < 0:
        warnings.append("这次移仓要倒贴钱（净付出），付出的部分会加大总亏损上限")

    def mloss(p):
        return None if p["max_loss"] is None else -p["max_loss"] * scale

    out = dict(model="options_desk.roll", underlying=t["name"], currency=t["currency"], as_of=t["as_of"],
               net_roll_per_share=r4(net_roll), net_roll_total=r4(net_roll * scale),
               locked_pl_total=r4(locked * scale), cumulative_cash_total=r4(cumulative * scale),
               old=dict(dte=old_dte, max_loss=r4(mloss(old_prof)), breakevens=old_prof["breakevens"]),
               new_alone=dict(dte=new_dte, max_loss=r4(mloss(new_alone)), breakevens=new_alone["breakevens"]),
               new_with_history=dict(max_loss=r4(mloss(new_total)), breakevens=new_total["breakevens"]),
               days_added=None if old_dte is None or new_dte is None else new_dte - old_dte, checks=checks)
    res_rows = [["移仓净收付", f"{'收到' if net_roll >= 0 else '付出'} {d_money(abs(net_roll) * scale)}"],
                ["平掉旧仓已实现", f"{'赚' if locked >= 0 else '亏'} {d_money(abs(locked) * scale)}"],
                ["多拿的天数", "—" if out["days_added"] is None else f"{out['days_added']} 天"],
                ["旧仓到期最多亏", d_money(mloss(old_prof))],
                ["新仓算上之前所有收付，到期最多亏", d_money(mloss(new_total))],
                ["新仓算上之前所有收付，盈亏平衡价", "、".join(d_px(b) for b in new_total["breakevens"]) or "—"]]
    lines = [f"这次移仓{'收到' if net_roll >= 0 else '付出'} {d_money(abs(net_roll) * scale)}，"
             f"平掉旧仓{'赚了' if locked >= 0 else '亏了'} {d_money(abs(locked) * scale)}。",
             f"算上之前所有收付，新仓到期最多亏 {d_money(mloss(new_total))}，盈亏平衡价 "
             f"{'、'.join(d_px(b) for b in new_total['breakevens']) or '—'}。"]
    for c in checks:
        if c["status"] == "不符合":
            lines.append(f"「{c['rule']}」没过：{c['actual']}；你的规则是 {c['rule_value']}。")
    out["display"] = dict(
        warnings_md=md_list(warnings),
        legs_md="旧仓\n" + md_table(["腿", "行权价", "权利金", "到期", "Delta", "IV"], legs_rows(old))
                + "\n\n新仓\n" + md_table(["腿", "行权价", "权利金", "到期", "Delta", "IV"], legs_rows(new_legs)),
        checks_md=md_table(["规则", "你的规则", "这次移仓", "结果"],
                           [[c["rule"], c["rule_value"], c["actual"], c["status"]] for c in checks]) if checks else "- 没有可核对的规则",
        result_md=md_table(["项目", "数值"], res_rows),
        notes_md=md_list(["移仓等于先平旧仓、再开新仓；平旧仓的盈亏已经发生，新仓只决定之后的结果",
                          "「算上之前所有收付」把开旧仓、以前移仓和这次移仓的钱都算进新仓的成本"]),
        lines=lines)
    out.update(warnings=warnings, units=dict(money=f"{t['currency'] or 'input_currency'}_total"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ assign

def cmd_assign(args):
    cfg = load_json(args.position)
    t = parse_trade(cfg)
    warnings = []
    legs, spot, scale = t["legs"], t["spot"], t["scale"]
    credit = entry_cash(option_legs(legs)) + num(cfg.get("prior_roll_cash", 0), "prior_roll_cash")
    stock_long = sum(lg["ratio"] for lg in legs if lg["type"] == "stock" and lg["sign"] > 0)
    rows, lines = [], []
    cash = t["account"].get("cash")
    for lg in option_legs(legs):
        if lg["sign"] > 0:
            continue
        shares = lg["ratio"] * scale
        itm = (spot < lg["strike"]) if lg["type"] == "put" else (spot > lg["strike"])
        if lg["type"] == "put":
            need = lg["strike"] * shares
            eff = lg["strike"] - credit / lg["ratio"]
            protect = [x for x in option_legs(legs) if x["type"] == "put" and x["sign"] > 0]
            rows.append(["被行权后买入", f"{d_money(shares)} 股，每股 {d_px(lg['strike'])}"])
            rows.append(["需要的现金", d_money(need)])
            rows.append(["算上收到的权利金，实际成本", f"每股 {d_px(eff)}"])
            if cash is not None:
                rows.append(["你现在的现金", d_money(cash)])
            lines.append(f"如果被行权，要用 {d_money(need)} 买入 {d_money(shares)} 股；算上收到的权利金，实际成本每股 {d_px(eff)}。")
            if protect:
                lines.append(f"你还持有行权价 {d_px(protect[0]['strike'])} 的买入看跌，它还在，可以行权或卖出，最大亏损仍按价差封顶。")
            if cash is not None and cash < need:
                warnings.append("现金不够接盘，券商可能要求补钱或直接平仓")
        else:
            covered = stock_long >= lg["ratio"]
            rows.append(["被行权后卖出", f"{d_money(shares)} 股，每股 {d_px(lg['strike'])}"])
            if covered:
                eff = lg["strike"] + credit / lg["ratio"]
                rows.append(["算上收到的权利金，实际卖价", f"每股 {d_px(eff)}"])
                lines.append(f"如果被行权，你持有的 {d_money(shares)} 股会以每股 {d_px(lg['strike'])} 卖出；算上权利金，实际卖价每股 {d_px(eff)}。")
            else:
                rows.append(["没有正股覆盖", f"会变成空头 {d_money(shares)} 股"])
                lines.append(f"如果被行权，你没有正股，会变成空头 {d_money(shares)} 股，亏损在理论上没有上限。")
                warnings.append("卖出的看涨没有正股覆盖，被行权后是空头正股")
        rows.append(["现在是否价内", "是" if itm else "否"])
    if not rows:
        fail("no short option legs to assign")
    if any(lg["type"] == "put" and lg["sign"] < 0 for lg in legs):
        warnings.append("美式期权到期前也可能被提前行权，价内越深越容易")
    out = dict(model="options_desk.assign", underlying=t["name"], currency=t["currency"], as_of=t["as_of"],
               spot=spot, credit_per_share=r4(credit))
    out["display"] = dict(warnings_md=md_list(warnings),
                          legs_md=md_table(["腿", "行权价", "权利金", "到期", "Delta", "IV"], legs_rows(legs)),
                          result_md=md_table(["项目", "数值"], rows),
                          notes_md=md_list(["实际成本已经扣掉这个仓位收到的全部权利金（含以前移仓的收付）"]),
                          lines=lines)
    out.update(warnings=warnings, units=dict(money=f"{t['currency'] or 'input_currency'}_total"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ margin

def cmd_margin(args):
    t = parse_trade(load_json(args.trade))
    warnings = ["这是按 Reg-T 规则的估算；券商会按波动、集中度和账户类型上调，组合保证金账户口径也不同，以券商显示为准"]
    legs, spot, scale = t["legs"], t["spot"], t["scale"]
    structure = classify(legs)
    m = margin_estimate(legs, spot, structure)
    if m is None:
        fail("margin estimate is not available for this combination; use the broker's figure")
    rows = [["结构", STRUCTURE_CN[structure]], ["算法", m["formula"]], ["每股", d_px(m["requirement"])],
            ["整笔（× 乘数 × 张数）", d_money(m["requirement"] * scale)]]
    lines = [f"按{' ' if m['basis'][0].isascii() else ''}{m['basis']}估，这笔大约占用 {d_money(m['requirement'] * scale)}。"]
    if "cash_secured" in m:
        rows.append(["如果按现金担保（备足接盘的钱）", d_money(m["cash_secured"] * scale)])
        lines.append(f"如果按现金担保，要备 {d_money(m['cash_secured'] * scale)}，就是被行权时买股票的钱减去收到的权利金。")
        warnings.append("券商允许按较低的裸卖保证金多卖，但被行权时要的是全额现金")
    if "max_loss_basis" in m:
        rows.append(["到期最多亏", d_money(m["max_loss_basis"] * scale)])
    out = dict(model="options_desk.margin", underlying=t["name"], currency=t["currency"], structure=structure,
               margin={k: (r4(v) if isinstance(v, float) else v) for k, v in m.items()},
               margin_total=r4(m["requirement"] * scale))
    out["display"] = dict(warnings_md=md_list(warnings), result_md=md_table(["项目", "数值"], rows),
                          notes_md=md_list(["Reg-T 公式的意思：先按股价跌 20% 留出亏损，减掉价外的部分，最少也按行权价（卖看涨按现价）的 10% 留"]),
                          lines=lines)
    out.update(warnings=warnings, units=dict(money=f"{t['currency'] or 'input_currency'}_total"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("check"); a.add_argument("--trade", required=True); a.add_argument("--rules")
    a = sp.add_parser("roll"); a.add_argument("--position", required=True); a.add_argument("--rules")
    a = sp.add_parser("assign"); a.add_argument("--position", required=True)
    a = sp.add_parser("margin"); a.add_argument("--trade", required=True)
    args = ap.parse_args(argv)
    try:
        {"check": cmd_check, "roll": cmd_roll, "assign": cmd_assign, "margin": cmd_margin}[args.cmd](args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

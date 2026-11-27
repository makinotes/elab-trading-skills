#!/usr/bin/env python3
"""Valuation models (standard library only).

Subcommands:
  dcf      two-stage FCFF DCF for user-defined scenarios (e.g. bear / base / bull): explicit
           EV-to-equity bridge, terminal-value share of EV, discount-rate x terminal-growth grid
  reverse  invert a reference price into the bet it implies: revenue growth, years of growth,
           or operating margin, holding the other assumptions fixed (expectations investing)
  anchors  line up consensus targets, named broker targets and own-model values against a
           reference price, row by row, without averaging them into one number

Model: revenue grows at g_t, earns margin m_t, operating profit is taxed, and growth is paid
for by reinvesting g_t / ROIC of after-tax operating profit. After the explicit period growth
drops to the terminal rate and the return on new capital defaults to the discount rate, which
makes terminal growth value-neutral (the terminal value does not carry a second growth story).

All inputs are user-supplied local JSON; nothing is fetched. stdout carries JSON only, errors
go to stderr with exit code 1. Outputs are conditional scenarios under stated assumptions; they
are not probabilities, price targets, ratings or trade instructions.
"""
import argparse
import json
import math
import sys
from datetime import date

REQUIRED_SOURCES = ("revenue", "operating_margin", "tax_rate", "cash", "debt", "shares")
FIELD_CN = dict(revenue="收入", operating_margin="经营利润率", tax_rate="税率", cash="现金", debt="有息负债", shares="摊薄股数")
GRID_DISCOUNT = (-0.02, -0.01, 0.0, 0.01, 0.02)
GRID_TERMINAL = (-0.01, -0.005, 0.0, 0.005, 0.01)
REVERSE_YEARS = (5, 10, 15)
GROWTH_RANGE = (-0.30, 1.00)
MARGIN_RANGE = (0.0, 0.90)
MAX_YEARS = 60
TV_SHARE_WARN = 0.75
TERMINAL_GROWTH_CAP = 0.04
TAM_SHARE_WARN = 0.5
STALE_DAYS = 90
MIN_ANALYSTS = 5
NOTE_SCENARIO = "这几档是按你的假设算出来的，不是概率，也不是合理价；「与参考价」只是情景算出的数和参考价差多少"
NOTE_NEUTRAL = "按默认设定，永续增长率对结果影响很小，结果主要看折现率"
NOTE_MULTI = "几档之间同时改了好几个假设，差距说不清是哪一个造成的；想看单项影响，只改一项重跑"
NOTE_IMPLIED = "这几个数是参考价背后已经算进去的预期，不是预测，也不评价它合不合理"
NOTE_REACHABLE = "「有解」只说明数学上算得出来，不代表公司做得到"
NOTE_TRAILING = "过去增速只拿来对照，没参与增速的计算"
NOTE_SAMPLE = "这几家只是样本，代表不了全市场"
LIMITS = [
    "情景是给定假设下的条件推演，不是概率分布、目标价或预测",
    "所有输入（收入、利润率、股数、净现金、折现率）以用户提供为准，脚本不核对原始披露",
]


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


def pct(x):
    return f"{x * 100:.1f}%"


def parse_date(value, name):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        fail(f"{name} must be an ISO date (YYYY-MM-DD)")


# ------------------------------------------------------------------ display
# Display strings are formatted here, from unrounded values, so every host renders
# identical tables instead of re-rounding numbers on its own.

def d_pct(x, signed=False):
    if x is None:
        return "—"
    return f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"


def d_px(x):
    return "—" if x is None else f"{x:.2f}"


def d_num(x):
    if x is None:
        return "—"
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"


def md_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def md_notes(notes):
    return "\n".join(f"- {n}" for n in notes) if notes else "- 无"


def md_warnings(ws):
    return "\n".join(f"- {w}" for w in ws) if ws else "- 无"


ASSUMPTION_FIELDS = ("discount_rate", "terminal_growth", "terminal_roic", "roic", "trailing_growth", "tam")


def src(c, key):
    default = "用户假设" if key in ASSUMPTION_FIELDS else "未标来源"
    return str(c["sources"].get(key) or default)


def company_input_rows(c):
    rows = [["收入", d_num(c["revenue"]), src(c, "revenue")],
            ["经营利润率", d_pct(c["margin"]), src(c, "operating_margin")],
            ["税率", d_pct(c["tax"]), src(c, "tax_rate")],
            ["现金", d_num(c["cash"]), src(c, "cash")],
            ["有息负债", d_num(c["debt"]), src(c, "debt")]]
    if c["other"]:
        rows.append(["其他索取权", d_num(c["other"]), src(c, "other_claims")])
    rows += [["摊薄股数", d_num(c["shares"]), src(c, "shares")],
             ["折现率", d_pct(c["r"]), src(c, "discount_rate")],
             ["永续增长率", d_pct(c["gt"]), src(c, "terminal_growth")],
             ["终值再投资回报率", "= 折现率" if c["ronic"] is None else d_pct(c["ronic"]), src(c, "terminal_roic")]]
    if c["roic"] is not None:
        rows.append(["增量 ROIC", d_pct(c["roic"]), src(c, "roic")])
    if c["trailing_growth"] is not None:
        rows.append(["过去增速", d_pct(c["trailing_growth"]), src(c, "trailing_growth")])
    if c["tam"] is not None:
        rows.append(["市场规模", d_num(c["tam"]), src(c, "tam")])
    if c["ref"]:
        rows.append(["参考价", ref_cell(c["ref"], c["currency"]), src(c, "reference_price")])
    return rows


def ref_cell(ref, currency):
    tail = "，".join(x for x in (ref.get("label"), ref.get("as_of")) if x)
    return f"{d_px(ref['value'])} {currency}".strip() + (f"（{tail}）" if tail else "")


# ------------------------------------------------------------------ company

def parse_company(cfg):
    if str(cfg.get("archetype", "operating")).lower() in ("bank", "insurance", "insurer"):
        fail("FCFF DCF is the wrong lens for banks and insurers; use an equity / excess-return model outside this script")
    c = dict(
        name=str(cfg.get("name", "")),
        currency=str(cfg.get("currency", "")),
        revenue=num(cfg.get("revenue"), "revenue", 0, low_open=True),
        margin=num(cfg.get("operating_margin"), "operating_margin", -1, 1),
        tax=num(cfg.get("tax_rate"), "tax_rate", 0, 0.99),
        cash=num(cfg.get("cash", 0), "cash", 0),
        debt=num(cfg.get("debt", 0), "debt", 0),
        other=num(cfg.get("other_claims", 0), "other_claims", 0),
        shares=num(cfg.get("shares"), "shares", 0, low_open=True),
        r=num(cfg.get("discount_rate"), "discount_rate", 0, 1, low_open=True),
        gt=num(cfg.get("terminal_growth", 0.025), "terminal_growth", -0.5, 0.5),
        ronic=None if cfg.get("terminal_roic") is None else num(cfg["terminal_roic"], "terminal_roic", 0, low_open=True),
        roic=None if cfg.get("roic") is None else num(cfg["roic"], "roic", 0, low_open=True),
        rf=None if cfg.get("risk_free") is None else num(cfg["risk_free"], "risk_free", -0.1, 0.5),
        mid_year=bool(cfg.get("mid_year", False)),
        tam=None if cfg.get("tam") is None else num(cfg["tam"], "tam", 0, low_open=True),
        trailing_growth=None if cfg.get("trailing_growth") is None else num(cfg["trailing_growth"], "trailing_growth", -1, 10),
    )
    ref = cfg.get("reference_price")
    if ref is not None:
        if not isinstance(ref, dict):
            ref = {"value": ref}
        c["ref"] = dict(value=num(ref.get("value"), "reference_price.value", 0, low_open=True),
                        label=str(ref.get("label", "参考价")), as_of=ref.get("as_of"))
    else:
        c["ref"] = None
    sources = cfg.get("sources") or {}
    c["sources"] = sources
    c["missing_sources"] = [k for k in REQUIRED_SOURCES if not str(sources.get(k, "")).strip()]
    return c


def scenario_params(c, name, sc):
    years = sc.get("years", 10)
    if not isinstance(years, int) or not 1 <= years <= MAX_YEARS:
        fail(f"scenario {name}: years must be an integer 1..{MAX_YEARS}")
    gs = num(sc.get("growth_start", sc.get("growth")), f"scenario {name}: growth_start", -0.9, 5)
    ge = num(sc.get("growth_end", gs), f"scenario {name}: growth_end", -0.9, 5)
    roic = sc.get("roic", c["roic"])
    if roic is None:
        fail(f"scenario {name}: roic (incremental return on invested capital) is required")
    return dict(
        years=years, gs=gs, ge=ge,
        m0=c["margin"],
        mt=num(sc.get("margin_target", c["margin"]), f"scenario {name}: margin_target", -1, 1),
        roic=num(roic, f"scenario {name}: roic", 0, low_open=True),
        r=num(sc.get("discount_rate", c["r"]), f"scenario {name}: discount_rate", 0, 1, low_open=True),
        gt=num(sc.get("terminal_growth", c["gt"]), f"scenario {name}: terminal_growth", -0.5, 0.5),
        ronic=c["ronic"] if sc.get("terminal_roic") is None else num(sc["terminal_roic"], f"scenario {name}: terminal_roic", 0, low_open=True),
    )


def value(c, p, keep_rows=False):
    """Two-stage FCFF value. Returns a dict; raises InputError when r <= terminal growth."""
    n, r, gt = p["years"], p["r"], p["gt"]
    ronic = p["ronic"] if p["ronic"] is not None else r
    if r <= gt:
        fail(f"discount_rate ({r}) must exceed terminal_growth ({gt})")
    shift = 0.5 if c["mid_year"] else 0.0
    rev, pv_explicit, rows = c["revenue"], 0.0, []
    m = p["m0"]
    for t in range(1, n + 1):
        g = p["gs"] if n == 1 else p["gs"] + (p["ge"] - p["gs"]) * (t - 1) / (n - 1)
        m = p["m0"] + (p["mt"] - p["m0"]) * t / n
        rev *= 1 + g
        nopat = rev * m * (1 - c["tax"])
        reinvest = nopat * g / p["roic"]
        fcff = nopat - reinvest
        pv = fcff / (1 + r) ** (t - shift)
        pv_explicit += pv
        if keep_rows:
            rows.append(dict(year=t, growth=r4(g), margin=r4(m), revenue=r4(rev), nopat=r4(nopat),
                             reinvestment=r4(reinvest), fcff=r4(fcff), pv_fcff=r4(pv)))
    nopat_next = rev * (1 + gt) * m * (1 - c["tax"])
    tv = nopat_next * (1 - gt / ronic) / (r - gt)
    pv_tv = tv / (1 + r) ** (n - shift)
    ev = pv_explicit + pv_tv
    equity = ev + c["cash"] - c["debt"] - c["other"]
    out = dict(pv_explicit=pv_explicit, terminal_value=tv, pv_terminal=pv_tv, ev=ev, equity=equity,
               per_share=equity / c["shares"], tv_share=pv_tv / ev if ev > 0 else None,
               final_revenue=rev, final_margin=m, terminal_roic=ronic)
    if keep_rows:
        out["rows"] = rows
    return out


def common_warnings(c, warnings):
    if c["missing_sources"]:
        warnings.append("、".join(FIELD_CN[k] for k in c["missing_sources"]) + "没标来源，按你给的数直接用")


def scenario_warnings(c, name, p, v, warnings):
    if v["pv_explicit"] < 0:
        warnings.append(f"{name}：前 {p['years']} 年再投入比赚的多，现金流是负的，价值全靠终值撑着")
    elif v["tv_share"] is not None and v["tv_share"] > TV_SHARE_WARN:
        warnings.append(f"{name}：企业价值有 {pct(v['tv_share'])} 来自终值，结果主要看终值那部分的假设")
    if v["ev"] <= 0:
        warnings.append(f"{name}：算出的企业价值不为正，终值占比没有意义")
    if v["equity"] < 0:
        warnings.append(f"{name}：扣掉负债后股权价值是负的")
    if c["rf"] is not None and p["gt"] > c["rf"]:
        warnings.append(f"{name}：永续增长率 {pct(p['gt'])} 比无风险利率 {pct(c['rf'])} 还高")
    elif c["rf"] is None and p["gt"] > TERMINAL_GROWTH_CAP:
        warnings.append(f"{name}：永续增长率 {pct(p['gt'])} 高于 4%，长期看整体经济一般长不了这么快")
    if p["roic"] < p["r"] and max(p["gs"], p["ge"]) > 0:
        warnings.append(f"{name}：新投入的回报 {pct(p['roic'])} 低于折现率 {pct(p['r'])}，这种情况下增长越快反而越不值钱")
    if p["ronic"] is not None and abs(p["ronic"] - p["r"]) > 1e-12:
        warnings.append(f"{name}：终值期新投入的回报设成了 {pct(p['ronic'])}，不等于折现率，终值里多算了一块增长价值")
    if c["tam"] is not None and v["final_revenue"] / c["tam"] > TAM_SHARE_WARN:
        warnings.append(f"{name}：到第 {p['years']} 年，收入要占到你给的市场规模的 {pct(v['final_revenue'] / c['tam'])}")


def merge_scenario_warnings(ws):
    """Join warnings whose text is identical across scenarios: 'base：X' + 'bull：X' -> 'base、bull：X'."""
    order, names = [], {}
    for w in ws:
        name, _, text = w.partition("：")
        if text not in names:
            order.append(text)
            names[text] = []
        names[text].append(name)
    return [f"{'、'.join(names[t])}：{t}" for t in order]


def units(c):
    cur = c["currency"] or "input_currency"
    return dict(money="input_money_unit", per_share=f"{cur}_per_share", rates="fraction",
                shares="input_share_unit (money / shares = per share)")


def cmd_dcf(args):
    cfg = load_json(args.input)
    c = parse_company(cfg)
    scs = cfg.get("scenarios")
    if not isinstance(scs, dict) or not scs:
        fail("scenarios must be a non-empty object, e.g. {\"bear\": {...}, \"base\": {...}, \"bull\": {...}}")
    warnings = []
    common_warnings(c, warnings)
    sc_warnings = []
    out_sc = {}
    params = {}
    raw = {}
    for name, sc in scs.items():
        p = scenario_params(c, name, sc or {})
        v = value(c, p, keep_rows=True)
        params[name] = p
        raw[name] = v
        scenario_warnings(c, name, p, v, sc_warnings)
        row = dict(
            assumptions=dict(years=p["years"], growth_start=p["gs"], growth_end=p["ge"],
                             margin_start=p["m0"], margin_target=p["mt"], roic=p["roic"],
                             discount_rate=p["r"], terminal_growth=p["gt"], terminal_roic=r4(v["terminal_roic"])),
            bridge=dict(pv_explicit_fcff=r4(v["pv_explicit"]), pv_terminal_value=r4(v["pv_terminal"]),
                        enterprise_value=r4(v["ev"]), plus_cash=c["cash"], minus_debt=c["debt"],
                        minus_other_claims=c["other"], equity_value=r4(v["equity"]), shares=c["shares"]),
            per_share=r4(v["per_share"]),
            terminal_value_share=r4(v["tv_share"]),
            final_year_revenue=r4(v["final_revenue"]),
            rows=v["rows"],
        )
        if c["ref"]:
            row["per_share_vs_reference"] = r4(v["per_share"] / c["ref"]["value"] - 1)
        if c["tam"] is not None:
            row["final_revenue_share_of_tam"] = r4(v["final_revenue"] / c["tam"])
        out_sc[name] = row
    warnings += merge_scenario_warnings(sc_warnings)
    grid_name = args.grid_scenario or ("base" if "base" in scs else next(iter(scs)))
    if grid_name not in params:
        fail(f"grid scenario {grid_name} not in scenarios")
    gp = params[grid_name]
    grid = []
    for dr in GRID_DISCOUNT:
        line = []
        for dg in GRID_TERMINAL:
            q = dict(gp, r=gp["r"] + dr, gt=gp["gt"] + dg)
            line.append(None if q["r"] <= q["gt"] or q["r"] <= 0 else r4(value(c, q)["per_share"]))
        grid.append(line)
    in_rows = company_input_rows(c)
    for name, p in params.items():
        desc = (f"增速 {d_pct(p['gs'])}→{d_pct(p['ge'])}，利润率 {d_pct(p['m0'])}→{d_pct(p['mt'])}，"
                f"{p['years']} 年，ROIC {d_pct(p['roic'])}")
        if p["r"] != c["r"]:
            desc += f"，折现率 {d_pct(p['r'])}"
        if p["gt"] != c["gt"]:
            desc += f"，永续增长率 {d_pct(p['gt'])}"
        if p["ronic"] != c["ronic"]:
            desc += f"，终值再投资回报率 {d_pct(p['ronic'])}"
        in_rows.append([f"情景 {name}", desc, "用户情景"])
    res_rows = [[name, d_px(v["per_share"]),
                 d_pct(v["per_share"] / c["ref"]["value"] - 1, signed=True) if c["ref"] else "—",
                 d_pct(v["tv_share"])] for name, v in raw.items()]
    notes = [NOTE_SCENARIO]
    keys = ("gs", "ge", "mt", "roic", "r", "gt", "ronic")
    if len(params) > 1:
        ps = list(params.values())
        changed = [k for k in keys if len({p[k] for p in ps}) > 1]
        if len(changed) > 1:
            notes.append(NOTE_MULTI)
    if any(p["ronic"] is None for p in params.values()):
        notes.append(NOTE_NEUTRAL)
    lines = []
    for name, v in raw.items():
        line = f"{name} 情景按你的假设算出每股 {d_px(v['per_share'])}"
        if c["ref"]:
            gap = v["per_share"] / c["ref"]["value"] - 1
            line += f"，比参考价{'高' if gap >= 0 else '低'} {d_pct(abs(gap))}"
        lines.append(line + "。")
    display = dict(warnings_md=md_warnings(warnings), notes_md=md_notes(notes), lines=lines,
                   input_md=md_table(["项目", "数值", "来源"], in_rows),
                   result_md=md_table(["情景", "每股价值", "与参考价", "终值占比"], res_rows))
    out = dict(model="valuation.dcf", company=c["name"], currency=c["currency"],
               as_of=cfg.get("as_of"), reference_price=c["ref"], mid_year=c["mid_year"],
               scenarios=out_sc,
               sensitivity=dict(scenario=grid_name, axis_rows="discount_rate", axis_cols="terminal_growth",
                                discount_rates=[r4(gp["r"] + d) for d in GRID_DISCOUNT],
                                terminal_growths=[r4(gp["gt"] + d) for d in GRID_TERMINAL],
                                per_share=grid,
                                note="终值再投资回报率未指定时随折现率同步变动（价值中性）"),
               limits=LIMITS, warnings=warnings, display=display, units=units(c))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ reverse

def solve_scan(fn, lo, hi, target, steps=260):
    """Find x in [lo, hi] with fn(x) = target by scanning for sign changes, then bisecting.

    Returns (root or None, crossings, (min_value, max_value)).
    """
    xs = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    ys = []
    for x in xs:
        try:
            ys.append(fn(x) - target)
        except InputError:
            ys.append(None)
    valid = [y for y in ys if y is not None]
    if not valid:
        return None, 0, (None, None)
    brackets = [(xs[i], xs[i + 1]) for i in range(steps)
                if ys[i] is not None and ys[i + 1] is not None and (ys[i] == 0 or ys[i] * ys[i + 1] < 0)]
    span = (min(valid) + target, max(valid) + target)
    if not brackets:
        return None, 0, span
    a, b = brackets[0]
    fa = fn(a) - target
    for _ in range(200):
        mid = (a + b) / 2
        fm = fn(mid) - target
        if fa == 0:
            return a, len(brackets), span
        if fa * fm <= 0:
            b = mid
        else:
            a, fa = mid, fm
        if b - a < 1e-10:
            break
    return (a + b) / 2, len(brackets), span


def reverse_params(c, cfg, args):
    rv = cfg.get("reverse") or {}
    years = args.years if args.years is not None else rv.get("years", 10)
    default_years = args.years is None and "years" not in rv
    if not isinstance(years, int) or not 1 <= years <= MAX_YEARS:
        fail(f"reverse years must be an integer 1..{MAX_YEARS}")
    margin = args.margin if args.margin is not None else rv.get("margin", c["margin"])
    growth = args.growth if args.growth is not None else rv.get("growth", c["trailing_growth"])
    roic = args.roic if args.roic is not None else rv.get("roic", c["roic"])
    if roic is None:
        fail("reverse needs roic (incremental return on invested capital) in the input or --roic")
    return dict(default_years=default_years, years=years, margin=num(margin, "reverse margin", -1, 1),
                growth=None if growth is None else num(growth, "reverse growth", -0.9, 5),
                roic=num(roic, "reverse roic", 0, low_open=True), r=c["r"], gt=c["gt"], ronic=c["ronic"])


def flat(c, h, g, years=None, margin=None, r=None):
    m = h["margin"] if margin is None else margin
    p = dict(years=h["years"] if years is None else years, gs=g, ge=g, m0=m, mt=m,
             roic=h["roic"], r=h["r"] if r is None else r, gt=h["gt"], ronic=h["ronic"])
    return value(c, p)["per_share"]


def cmd_reverse(args):
    cfg = load_json(args.input)
    c = parse_company(cfg)
    if not c["ref"]:
        fail("reverse needs reference_price in the input")
    price = c["ref"]["value"]
    h = reverse_params(c, cfg, args)
    warnings = []
    common_warnings(c, warnings)
    solve = args.solve
    raw_g = raw_m = None
    out = dict(model="valuation.reverse", company=c["name"], currency=c["currency"], as_of=cfg.get("as_of"),
               reference_price=c["ref"], mid_year=c["mid_year"],
               held=dict(years=h["years"], margin=h["margin"], growth=h["growth"], roic=h["roic"],
                         discount_rate=h["r"], terminal_growth=h["gt"],
                         terminal_roic=h["ronic"] if h["ronic"] is not None else h["r"]),
               trailing_growth=c["trailing_growth"])
    ev_implied = price * c["shares"] - c["cash"] + c["debt"] + c["other"]
    out["implied_at_price"] = dict(
        enterprise_value=r4(ev_implied),
        ev_to_revenue=r4(ev_implied / c["revenue"]),
        ev_to_nopat=r4(ev_implied / (c["revenue"] * c["margin"] * (1 - c["tax"]))) if c["margin"] > 0 else None)
    if h["roic"] < h["r"]:
        warnings.append(f"新投入的回报 {pct(h['roic'])} 低于折现率 {pct(h['r'])}，这种情况下增长越快越不值钱，更高的价格没法用更快的增长解释")

    if solve in ("growth", "all"):
        if h["margin"] <= 0:
            warnings.append("现在不赚钱，没法反推增速；先给一个你认为长期能做到的利润率再算")
            out["implied_growth"] = None
        else:
            g, n_cross, span = solve_scan(lambda x: flat(c, h, x), *GROWTH_RANGE, price)
            raw_g = g
            res = dict(growth=r4(g), years=h["years"], margin=h["margin"], reachable=g is not None,
                       per_share_range_scanned=[r4(span[0]), r4(span[1])], growth_range_scanned=list(GROWTH_RANGE))
            if g is None:
                warnings.append(f"年增速从 {pct(GROWTH_RANGE[0])} 试到 {pct(GROWTH_RANGE[1])}，{h['years']} 年内都算不到参考价，这组假设解释不了这个价格")
            else:
                rev_n = c["revenue"] * (1 + g) ** h["years"]
                res["final_year_revenue"] = r4(rev_n)
                if c["tam"] is not None:
                    res["final_revenue_share_of_tam"] = r4(rev_n / c["tam"])
                    if rev_n / c["tam"] > TAM_SHARE_WARN:
                        warnings.append(f"按这个增速，到第 {h['years']} 年收入要占到你给的市场规模的 {pct(rev_n / c['tam'])}")
                if n_cross > 1:
                    warnings.append("增速和价值不是一路同向变化，有不止一个解，这里只给最低的那个")
            out["implied_growth"] = res
            grid = []
            for yrs in REVERSE_YEARS:
                line = []
                for dr in GRID_DISCOUNT:
                    rr = h["r"] + dr
                    if rr <= h["gt"] or rr <= 0:
                        line.append(None)
                        continue
                    hh = dict(h, r=rr)
                    gg, _, _ = solve_scan(lambda x: flat(c, hh, x, years=yrs), *GROWTH_RANGE, price)
                    line.append(r4(gg))
                grid.append(line)
            out["implied_growth_grid"] = dict(axis_rows="years", axis_cols="discount_rate",
                                              years=list(REVERSE_YEARS),
                                              discount_rates=[r4(h["r"] + d) for d in GRID_DISCOUNT],
                                              growth=grid,
                                              note="终值再投资回报率未指定时随折现率同步变动（价值中性）")

    if solve in ("years", "all"):
        if h["growth"] is None:
            if solve == "years":
                fail("solving years needs a held growth rate (--growth, reverse.growth or trailing_growth)")
            out["implied_years"] = None
        else:
            found = None
            vals = []
            for yrs in range(1, MAX_YEARS + 1):
                v = flat(c, h, h["growth"], years=yrs)
                vals.append(v)
                if found is None and v >= price * (1 - 1e-9):
                    found = yrs
            if found is None:
                warnings.append(f"按年增速 {pct(h['growth'])} 一直涨 {MAX_YEARS} 年也算不到参考价")
            if vals[0] >= price:
                warnings.append("只增长 1 年算出来就够参考价了，这个价格不要求长期增长")
            out["implied_years"] = dict(years=found, growth=h["growth"], margin=h["margin"],
                                        reachable=found is not None,
                                        per_share_at_1_and_max_years=[r4(vals[0]), r4(vals[-1])])

    if solve in ("margin", "all"):
        if h["growth"] is None:
            if solve == "margin":
                fail("solving margin needs a held growth rate (--growth, reverse.growth or trailing_growth)")
            out["implied_margin"] = None
        else:
            m, n_cross, span = solve_scan(lambda x: flat(c, h, h["growth"], margin=x), *MARGIN_RANGE, price)
            raw_m = m
            if m is None:
                warnings.append(f"利润率从 {pct(MARGIN_RANGE[0])} 试到 {pct(MARGIN_RANGE[1])} 都算不到参考价")
            out["implied_margin"] = dict(margin=r4(m), growth=h["growth"], years=h["years"], reachable=m is not None,
                                         per_share_range_scanned=[r4(span[0]), r4(span[1])])

    if c["rf"] is not None and h["gt"] > c["rf"]:
        warnings.append(f"永续增长率 {pct(h['gt'])} 比无风险利率 {pct(c['rf'])} 还高")
    if h["default_years"] and solve in ("growth", "margin", "all"):
        warnings.append(f"你没给年数，按默认 {h['years']} 年算")
    in_rows = company_input_rows(c)
    in_rows.append(["持有年数", f"{h['years']} 年", "反推假设"])
    in_rows.append(["持有利润率", d_pct(h["margin"]), "反推假设"])
    if h["growth"] is not None:
        in_rows.append(["持有增速", d_pct(h["growth"]), "反推假设"])
    res_rows = []
    ig, iy, im = out.get("implied_growth"), out.get("implied_years"), out.get("implied_margin")
    if solve in ("growth", "all"):
        res_rows.append(["增速", f"利润率 {d_pct(h['margin'])}，{h['years']} 年",
                         f"{d_pct(raw_g)}/年" if ig and ig["reachable"] else "无解",
                         "是" if ig and ig["reachable"] else "否"])
    if iy is not None:
        res_rows.append(["年数", f"增速 {d_pct(h['growth'])}，利润率 {d_pct(h['margin'])}",
                         f"{iy['years']} 年" if iy["reachable"] else "无解", "是" if iy["reachable"] else "否"])
    if im is not None:
        res_rows.append(["利润率", f"增速 {d_pct(h['growth'])}，{h['years']} 年",
                         d_pct(raw_m) if im["reachable"] else "无解", "是" if im["reachable"] else "否"])
    notes = [NOTE_IMPLIED, NOTE_REACHABLE]
    if c["trailing_growth"] is not None and solve in ("growth", "all"):
        notes.append(NOTE_TRAILING)
    lines = []
    if ig and ig["reachable"]:
        lines.append(f"按利润率 {d_pct(h['margin'])}、{h['years']} 年算，参考价要求每年增长 {d_pct(raw_g)}。")
    if iy is not None and iy["reachable"]:
        lines.append(f"按每年增长 {d_pct(h['growth'])}、利润率 {d_pct(h['margin'])} 算，这个增长至少要持续 {iy['years']} 年。")
    if im is not None and im["reachable"]:
        lines.append(f"按每年增长 {d_pct(h['growth'])}、{h['years']} 年算，利润率要做到 {d_pct(raw_m)}。")
    out["display"] = dict(warnings_md=md_warnings(warnings), notes_md=md_notes(notes), lines=lines,
                          input_md=md_table(["项目", "数值", "来源"], in_rows),
                          result_md=md_table(["求解", "持有假设", "隐含值", "有解"], res_rows))
    out.update(limits=LIMITS, warnings=warnings, units=units(c))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ anchors

def cmd_anchors(args):
    cfg = load_json(args.input)
    as_of = parse_date(cfg.get("as_of"), "as_of")
    cur = str(cfg.get("currency", ""))
    ref = cfg.get("reference_price")
    if not isinstance(ref, dict):
        fail("reference_price must be an object with value and label")
    price = num(ref.get("value"), "reference_price.value", 0, low_open=True)
    warnings = []

    def vs(x):
        return None if x is None else r4(x / price - 1)

    def check_cur(row_cur, name):
        if row_cur and cur and str(row_cur) != cur:
            fail(f"{name}: currency {row_cur} differs from {cur}; convert before comparing")

    cons = cfg.get("consensus")
    cons_out = None
    if cons:
        check_cur(cons.get("currency"), "consensus")
        stats = {}
        for k in ("mean", "median", "high", "low"):
            if cons.get(k) is not None:
                stats[k] = dict(value=num(cons[k], f"consensus.{k}", 0, low_open=True), vs_reference=vs(float(cons[k])))
        n = cons.get("n_analysts")
        cons_out = dict(source=cons.get("source"), as_of=cons.get("as_of"), n_analysts=n,
                        ratings=cons.get("ratings"), targets=stats)
        if not stats:
            warnings.append(f"共识是空的：只说明 {cons.get('source') or '这个数据源'} 在 {cons.get('as_of') or as_of} 没返回数据，不等于没人覆盖；不当成 0，也不拿参考价补")
        elif n is not None and int(n) < MIN_ANALYSTS:
            warnings.append(f"共识只有 {int(n)} 位分析师，样本很小")
        elif n is None:
            warnings.append("共识没给分析师人数")
        if cons.get("as_of"):
            age = (as_of - parse_date(cons["as_of"], "consensus.as_of")).days
            if age > STALE_DAYS:
                warnings.append(f"共识数据是 {age} 天前的")

    brokers = []
    for i, b in enumerate(cfg.get("brokers") or []):
        name = str(b.get("name") or f"broker#{i + 1}")
        check_cur(b.get("currency"), name)
        target = num(b.get("target"), f"{name}.target", 0, low_open=True)
        row = dict(name=name, target=target, vs_reference=vs(target), rating=b.get("rating"),
                   date=b.get("date"), horizon_months=b.get("horizon_months"),
                   evidence=b.get("evidence", "unknown"), source=b.get("source"))
        if b.get("date"):
            row["age_days"] = (as_of - parse_date(b["date"], f"{name}.date")).days
            if row["age_days"] > STALE_DAYS:
                warnings.append(f"{name}的目标价是 {row['age_days']} 天前的，之后的信息可能没算进去")
        else:
            row["age_days"] = None
            warnings.append(f"{name}没有发布日期")
        if row["evidence"] != "primary":
            how = "来自二手报道" if row["evidence"] == "secondary" else "没说明出处"
            warnings.append(f"{name}的目标价{how}，没核对研报原文")
        brokers.append(row)
    brokers.sort(key=lambda x: x["date"] or "", reverse=True)
    broker_span = None
    if brokers:
        ts = [b["target"] for b in brokers]
        broker_span = dict(n=len(ts), low=min(ts), high=max(ts), low_vs_reference=vs(min(ts)), high_vs_reference=vs(max(ts)))
        if len(ts) < 3:
            warnings.append(f"具名目标价只有 {len(ts)} 家，只是样本，代表不了全市场")

    own = None
    if args.dcf_result:
        d = load_json(args.dcf_result)
        if d.get("model") != "valuation.dcf":
            fail("--dcf-result must be the JSON output of valuation.py dcf")
        if d.get("currency") and cur and d["currency"] != cur:
            fail(f"dcf result currency {d['currency']} differs from {cur}")
        own = dict(label="自建DCF（valuation.py dcf）",
                   values={k: dict(value=v["per_share"], vs_reference=vs(v["per_share"]))
                           for k, v in d["scenarios"].items()},
                   model_warnings=d.get("warnings", []))
    elif cfg.get("own_model"):
        om = cfg["own_model"]
        own = dict(label=om.get("label", "自建模型"),
                   values={k: dict(value=num(v, f"own_model.{k}"), vs_reference=vs(num(v, f"own_model.{k}")))
                           for k, v in (om.get("values") or {}).items()},
                   model_warnings=list(om.get("warnings", [])))
    if own:
        warnings.append("自建模型的数完全取决于你的假设；券商目标价一般指 12 个月后，DCF 算的是现在，两者不是一个时间口径")
    if not cons_out and not brokers and not own:
        fail("anchors needs at least one of consensus, brokers, own_model or --dcf-result")
    evidence_cn = {"primary": "原文", "secondary": "二手"}
    stat_cn = {"mean": "共识均值", "median": "共识中位数", "high": "共识最高", "low": "共识最低"}
    res_rows = []
    if cons_out:
        tag = f"（{cons_out['source']}）" if cons_out.get("source") else ""
        if cons_out["targets"]:
            for k, t in cons_out["targets"].items():
                res_rows.append([stat_cn[k] + tag, d_px(t["value"]), d_pct(t["value"] / price - 1, signed=True),
                                 str(cons_out.get("as_of") or "—"), "—"])
        else:
            res_rows.append(["共识" + tag, "未返回数据", "—", str(cons_out.get("as_of") or "—"), "—"])
    for b in brokers:
        res_rows.append([b["name"], d_px(b["target"]), d_pct(b["target"] / price - 1, signed=True),
                         str(b["date"] or "—"), evidence_cn.get(b["evidence"], "未说明")])
    if own:
        for k, v in own["values"].items():
            res_rows.append([f"自建模型 {k}", d_px(v["value"]), d_pct(v["value"] / price - 1, signed=True), "—", "—"])
    all_w = list(warnings) + [f"自建模型：{w}" for w in (own or {}).get("model_warnings", [])]
    in_rows = [["参考价", ref_cell(dict(value=price, label=ref.get("label"), as_of=ref.get("as_of")), cur), "用户输入"],
               ["对照日期", str(as_of), "用户输入"]]
    if cons_out:
        in_rows.append(["共识数据源", f"{cons_out.get('source') or '—'}（{cons_out.get('as_of') or '—'}）", "用户输入"])
    notes = [NOTE_SAMPLE] if len(brokers) >= 3 else []
    lines = []
    for b in brokers:
        gap = b["target"] / price - 1
        when = f" {b['date']} " if b["date"] else ""
        horizon = f"{b['horizon_months']} 个月目标" if b.get("horizon_months") else "期限未说明"
        source_cn = {"primary": "研报原文", "secondary": "二手报道"}.get(b["evidence"], "出处未说明")
        lines.append(f"{b['name']}{when}给的目标价 {d_px(b['target'])}（{source_cn}，{horizon}），"
                     f"比参考价{'高' if gap >= 0 else '低'} {d_pct(abs(gap))}。")
    display = dict(warnings_md=md_warnings(all_w), notes_md=md_notes(notes), lines=lines,
                   input_md=md_table(["项目", "数值", "来源"], in_rows),
                   result_md=md_table(["锚点", "数值", "与参考价", "日期", "证据"], res_rows))
    out = dict(model="valuation.anchors", as_of=str(as_of), currency=cur,
               reference_price=dict(value=price, label=ref.get("label", "参考价"), as_of=ref.get("as_of")),
               consensus=cons_out, brokers=brokers, broker_span=broker_span, own_model=own,
               limits=["三类锚点来源、期限与动机不同，本输出逐行并列，不取平均、不合成单一价格"] + LIMITS[:1],
               warnings=warnings, display=display,
               units=dict(price=f"{cur or 'input_currency'}_per_share", vs_reference="fraction"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("dcf"); a.add_argument("--input", required=True); a.add_argument("--grid-scenario")
    a = sp.add_parser("reverse"); a.add_argument("--input", required=True)
    a.add_argument("--solve", choices=("growth", "years", "margin", "all"), default="all")
    a.add_argument("--years", type=int); a.add_argument("--margin", type=float)
    a.add_argument("--growth", type=float); a.add_argument("--roic", type=float)
    a = sp.add_parser("anchors"); a.add_argument("--input", required=True); a.add_argument("--dcf-result")
    args = ap.parse_args(argv)
    try:
        {"dcf": cmd_dcf, "reverse": cmd_reverse, "anchors": cmd_anchors}[args.cmd](args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

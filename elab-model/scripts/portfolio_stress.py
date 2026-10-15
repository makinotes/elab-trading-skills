#!/usr/bin/env python3
"""Portfolio margin stress and historical-analog models (standard library only).

Subcommands:
  stress   margin buffer, look-through exposure, shock levels that breach a floor or the
           margin-call line, release per unit sold, and sell-scenario comparison
  regime   historical-analog study: anchor days defined by drawdown conditions, forward
           outcomes of candidate instruments under exit rules, level touch / fill odds,
           bootstrap intervals and a split-half stability check
  replay   replay the whole portfolio through every anchor path with optional exit levels,
           forced liquidation when the buffer goes negative, and outcome distribution

All inputs are user-supplied local files; nothing is fetched. stdout carries JSON only,
errors go to stderr with exit code 1. Outputs describe mathematics under the stated
assumptions; they are not trade instructions.
"""
import argparse
import csv
import json
import math
import random
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

TRADING_DAYS = 252
DEFAULT_TP = {"1": 0.12, "2": 0.25, "3": 0.35}
DEFAULT_SL = {"1": -0.15, "2": -0.30, "3": -0.40}


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


def num(value, name, low=None, high=None):
    try:
        x = float(value)
    except (TypeError, ValueError):
        fail(f"{name} must be a number")
    if not math.isfinite(x):
        fail(f"{name} must be finite")
    if low is not None and x < low:
        fail(f"{name} must be >= {low}")
    if high is not None and x > high:
        fail(f"{name} must be <= {high}")
    return x


def r4(x):
    return None if x is None else round(x, 4)


# ------------------------------------------------------------------ portfolio
def parse_portfolio(pf):
    if not isinstance(pf, dict) or not isinstance(pf.get("positions"), list) or not pf["positions"]:
        fail("portfolio needs a non-empty positions list")
    pos = []
    seen = set()
    for i, p in enumerate(pf["positions"]):
        pid = str(p.get("id", "")).strip()
        if not pid or pid in seen:
            fail(f"positions[{i}].id missing or duplicated")
        seen.add(pid)
        pos.append(dict(
            id=pid,
            qty=num(p.get("qty"), f"{pid}.qty", 0),
            price=num(p.get("price"), f"{pid}.price", 0),
            fx=num(p.get("fx_to_base", 1), f"{pid}.fx_to_base", 1e-9),
            maint=num(p.get("maint_ratio"), f"{pid}.maint_ratio", 0, 1),
            lev=num(p.get("leverage", 1), f"{pid}.leverage", 0.01, 10),
            bucket=str(p.get("bucket", "other")),
            series=p.get("series"),
        ))
    for p in pos:
        p["mv"] = p["qty"] * p["price"] / p["fx"]
    equity = num(pf.get("equity"), "equity")
    mv = sum(p["mv"] for p in pos)
    req_raw = sum(p["mv"] * p["maint"] for p in pos)
    warnings = []
    if pf.get("margin_call") is not None:
        mc = num(pf["margin_call"], "margin_call", 0)
        k = mc / req_raw if req_raw > 0 else 1.0
        if abs(k - 1) > 0.15:
            warnings.append(f"Broker margin line differs from the sum of position ratios (k={k:.3f}); "
                            "results use the calibrated line, absolute buffers are approximate.")
    else:
        k = 1.0
        warnings.append("margin_call not supplied; using the sum of position ratios without calibration.")
    return pos, equity, equity - mv, k, warnings


def buffer_after(pos, cash, k, shock, betas, maint_bump=0.0):
    """Buffer after an underlying shock; each bucket moves by beta*shock, leveraged x lev."""
    total, req = 0.0, 0.0
    for p in pos:
        b = betas.get(p["bucket"], betas.get("*", 0.0))
        mv = p["mv"] * max(1 - p["lev"] * b * shock, 0.0)
        total += mv
        req += mv * min(p["maint"] + maint_bump, 1.0)
    return total + cash - k * req


def trigger(pos, cash, k, betas, threshold, maint_bump=0.0, step=0.0025, cap=0.95):
    s = 0.0
    while s <= cap:
        if buffer_after(pos, cash, k, s, betas, maint_bump) < threshold:
            return s
        s += step
    return None


def cmd_stress(args):
    pf = load_json(args.portfolio)
    pos, equity, cash, k, warnings = parse_portfolio(pf)
    floor = num(pf.get("floor", 0), "floor", 0)
    targeted = pf.get("bucket_betas") or {}
    systemic = pf.get("systemic_betas") or {"*": 1.0}
    bump = num(pf.get("maint_bump", 0.10), "maint_bump", 0, 1)
    if not targeted:
        warnings.append("bucket_betas empty: targeted shock moves nothing; only the systemic shock is informative.")

    def profile(pp, c):
        mv = sum(p["mv"] for p in pp)
        eq = mv + c
        out = dict(equity=r4(eq), market_value=r4(mv), cash=r4(c),
                   gross_ratio=r4(mv / eq) if eq > 0 else None,
                   look_through_ratio=r4(sum(p["mv"] * p["lev"] for p in pp) / eq) if eq > 0 else None,
                   buffer=r4(buffer_after(pp, c, k, 0, {}, 0)))
        for name, betas in (("targeted", targeted), ("systemic", systemic)):
            out[f"{name}_shock_to_floor"] = r4(trigger(pp, c, k, betas, floor))
            out[f"{name}_shock_to_margin_call"] = r4(trigger(pp, c, k, betas, 0))
            out[f"{name}_shock_to_floor_maint_bump"] = r4(trigger(pp, c, k, betas, floor, bump))
        return out

    base = profile(pos, cash)
    if equity <= 0:
        warnings.append("Equity is not positive; ratios are undefined.")
    release = sorted(({"id": p["id"], "buffer_release_per_10000": r4(10000 * p["maint"] * k),
                       "look_through_release_per_10000": r4(10000 * p["lev"])} for p in pos),
                     key=lambda x: -x["buffer_release_per_10000"])
    scenarios = []
    for sc in pf.get("sell_scenarios", []):
        ids = set(map(str, sc))
        unknown = ids - {p["id"] for p in pos}
        if unknown:
            fail(f"sell_scenarios reference unknown ids: {sorted(unknown)}")
        keep = [p for p in pos if p["id"] not in ids]
        c = cash + sum(p["mv"] for p in pos if p["id"] in ids)
        scenarios.append(dict(sold=sorted(ids), **profile(keep, c)))
    if any(p["lev"] > 1 for p in pos):
        warnings.append("Leveraged products are stressed as leverage x shock on the day; daily-reset path effects are ignored here.")
    warnings.append(f"maint_bump scenario adds {bump:.0%} to every maintenance ratio, approximating a broker raising requirements under stress.")
    out = dict(model="portfolio_stress.stress", calibration_k=r4(k), floor=floor, base=base,
               release_ranking=release, sell_scenarios=scenarios, warnings=warnings,
               units=dict(money="base_currency", ratios="fraction_of_equity",
                          shock="underlying_fractional_decline", release="base_currency_per_10000_sold"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ series
def load_series(directory, name, cache):
    if name in cache:
        return cache[name]
    path = Path(directory) / f"{name}.csv"
    if not path.is_file():
        fail(f"series file missing: {path.name}")
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            try:
                d = date.fromisoformat(row["date"][:10])
                c = float(row["close"])
                h = float(row["high"]) if row.get("high") not in (None, "") else c
            except (KeyError, ValueError):
                fail(f"{path.name} row {i + 2}: need date (YYYY-MM-DD), close[, high]")
            if not (math.isfinite(c) and c > 0 and math.isfinite(h)):
                fail(f"{path.name} row {i + 2}: close must be positive and finite")
            rows.append((d, c, max(h, c)))
    rows.sort()
    if len(rows) < 60:
        fail(f"{path.name}: need at least 60 rows")
    cache[name] = rows
    return rows


def synth(rows, lev, annual_cost=0.0, daily_drag=0.0):
    """Daily-reset leveraged path; cost and drag are subtracted every day."""
    out = [(rows[0][0], 1.0, 1.0)]
    v = 1.0
    for i in range(1, len(rows)):
        r = rows[i][1] / rows[i - 1][1] - 1
        v *= max(1 + lev * r - annual_cost / TRADING_DAYS - daily_drag, 1e-6)
        out.append((rows[i][0], v, v))
    return out


def drawdowns(rows, window):
    dd = {}
    for i in range(window - 1, len(rows)):
        hi = max(x[2] for x in rows[i - window + 1:i + 1])
        dd[rows[i][0]] = rows[i][1] / hi - 1
    return dd


def find_anchors(cfg, sdir, cache):
    a = cfg.get("anchor") or fail("config.anchor missing")
    conds = a.get("conditions") or fail("anchor.conditions missing")
    window = int(a.get("window", 20))
    gap = int(a.get("gap_days", 35))
    maps = []
    for c in conds:
        if ("drawdown_le" in c) == ("drawdown_ge" in c):
            fail("each anchor condition needs exactly one of drawdown_le / drawdown_ge")
        maps.append((drawdowns(load_series(sdir, c["series"], cache), window), c))
    days = sorted(set.intersection(*[set(m) for m, _ in maps]))
    hits = [d for d in days if all((m[d] <= c["drawdown_le"]) if "drawdown_le" in c else (m[d] >= c["drawdown_ge"])
                                   for m, c in maps)]
    anchors, last = [], None
    for d in hits:
        if last is None or (d - last).days > gap:
            anchors.append(d)
            last = d
    return anchors, gap


def segment(rows, anchor, length, shift):
    idx = next((i for i, x in enumerate(rows) if x[0] >= anchor + timedelta(days=shift)), None)
    if idx is None or rows[0][0] > anchor - timedelta(days=60) or idx + length >= len(rows):
        return None
    base = rows[idx][1]
    path = [x[1] / base for x in rows[idx:idx + length + 1]]
    ma = []
    for j in range(idx, idx + length + 1):
        lo = max(0, j - 19)
        ma.append(statistics.fmean(x[1] for x in rows[lo:j + 1]) / base)
    return path, ma


def exit_outcome(path, ma, rule, lev, rules):
    key = str(int(round(lev))) if round(lev) in (1, 2, 3) else "1"
    tp = rules.get("tp", DEFAULT_TP).get(key, 0.12 * lev)
    sl = rules.get("sl", DEFAULT_SL).get(key, -0.15 * lev)
    max_days = int(rules.get("max_days", 40))
    peak = 1.0
    for k in range(1, len(path)):
        r = path[k] - 1
        peak = max(peak, path[k])
        if rule.startswith("T") and rule[1:].isdigit() and k == int(rule[1:]):
            return r
        if rule == "TP_SL" and (r >= tp or r <= sl or k == max_days):
            return r
        if rule == "MA_REVERT" and (path[k] >= ma[k] or k == max_days):
            return r
        if rule == "TRAIL" and (r <= sl or (peak - 1 >= tp / 2 and path[k] / peak - 1 <= -tp / 2) or k == max_days):
            return r
    return None


def summarize(values, rng, iters):
    n = len(values)
    if n == 0:
        return dict(n=0)
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v <= 0]
    payoff = (statistics.fmean(wins) / -statistics.fmean(losses)) if wins and losses and statistics.fmean(losses) < 0 else None
    out = dict(n=n, win_rate=r4(len(wins) / n), payoff_ratio=r4(payoff), mean=r4(statistics.fmean(values)),
               median=r4(statistics.median(values)), worst=r4(min(values)))
    if n >= 5 and iters > 0:
        means, wr = [], []
        for _ in range(iters):
            s = [values[rng.randrange(n)] for _ in range(n)]
            means.append(statistics.fmean(s))
            wr.append(sum(v > 0 for v in s) / n)
        means.sort(); wr.sort()
        lo, hi = int(0.05 * iters), int(0.95 * iters) - 1
        out["mean_ci90"] = [r4(means[lo]), r4(means[hi])]
        out["win_rate_ci90"] = [r4(wr[lo]), r4(wr[hi])]
    return out


def candidate_paths(c, sdir, cache, anchors, length):
    rows = load_series(sdir, c["series"], cache)
    lev = num(c.get("leverage", 1), "leverage", 0.01, 10)
    if lev != 1 or c.get("annual_cost") or c.get("daily_drag"):
        rows = synth(rows, lev, num(c.get("annual_cost", 0), "annual_cost", 0, 1),
                     num(c.get("daily_drag", 0), "daily_drag", 0, 0.05))
    shift = int(c.get("shift_days", 0))
    return lev, [(a, s) for a in anchors for s in [segment(rows, a, length, shift)] if s is not None]


def cmd_regime(args):
    cfg = load_json(args.config)
    cache = {}
    anchors, gap = find_anchors(cfg, args.series_dir, cache)
    rules = cfg.get("exit_rules") or {}
    rule_names = rules.get("names", ["T20", "T60", "TP_SL", "MA_REVERT", "TRAIL"])
    boot = cfg.get("bootstrap") or {}
    rng = random.Random(int(boot.get("seed", 7)))
    iters = int(boot.get("iterations", 1000))
    warnings = []
    if len(anchors) < 30:
        warnings.append(f"Only {len(anchors)} anchors: treat rates as direction, not precision.")
    warnings.append(f"Anchors are at least {gap} calendar days apart, but forward windows longer than the gap overlap and are not independent.")
    results = []
    for c in cfg.get("candidates", []):
        lev, paths = candidate_paths(c, args.series_dir, cache, anchors, 61)
        if lev != 1:
            warnings.append(f"{c.get('label', c['series'])}: synthetic {lev:g}x daily reset; real products add fees, financing and premium/discount gaps.")
        for rule in rule_names:
            vals = [v for _, (p, m) in paths for v in [exit_outcome(p, m, rule, lev, rules)] if v is not None]
            half = len(vals) // 2
            results.append(dict(label=c.get("label", c["series"]), rule=rule, **summarize(vals, rng, iters),
                                split_half_mean=[r4(statistics.fmean(vals[:half])) if half else None,
                                                 r4(statistics.fmean(vals[half:])) if len(vals) - half else None]))
    levels = []
    for lv in cfg.get("levels", []):
        horizon = int(lv.get("horizon", 40))
        now = num(lv.get("price_now"), "levels.price_now", 1e-9)
        lev, paths = candidate_paths(lv, args.series_dir, cache, anchors, max(horizon, 30) + 21)
        ps = [p for _, (p, _) in paths]
        entry = dict(label=lv.get("label", lv["series"]), n=len(ps), horizon_days=horizon, touch=[], buy=[])
        for t in lv.get("touch_levels", []):
            entry["touch"].append(dict(level=t, prob=r4(sum(max(p[:horizon + 1]) >= t / now for p in ps) / len(ps)) if ps else None))
        fill_window = int(lv.get("fill_window", 10))
        for b in lv.get("buy_levels", []):
            fills = []
            for p in ps:
                hit = next((j for j in range(fill_window + 1) if p[j] <= b / now), None)
                if hit is not None and hit + 20 < len(p):
                    fills.append(p[hit + 20] / (b / now) - 1)
            entry["buy"].append(dict(level=b, fill_prob=r4(len(fills) / len(ps)) if ps else None,
                                     after_fill_20d=summarize(fills, rng, iters)))
        if lv.get("cost_basis"):
            need = num(lv["cost_basis"], "cost_basis", 1e-9) / now
            entry["prob_reach_cost_basis"] = r4(sum(max(p[:horizon + 1]) >= need for p in ps) / len(ps)) if ps else None
        levels.append(entry)
    warnings.append("Grid choices made on these same anchors are in-sample; compare split_half_mean before trusting a level set.")
    out = dict(model="portfolio_stress.regime", anchors=[a.isoformat() for a in anchors], n_anchors=len(anchors),
               exit_results=results, levels=levels, warnings=warnings,
               units=dict(returns="fraction", prob="fraction", levels="instrument_price", horizon="trading_days"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


# ------------------------------------------------------------------ replay
def cmd_replay(args):
    pf = load_json(args.portfolio)
    cfg = load_json(args.config)
    pos, equity, cash0, k, warnings = parse_portfolio(pf)
    floor = num(pf.get("floor", 0), "floor", 0)
    cache = {}
    anchors, _ = find_anchors(cfg, args.series_dir, cache)
    rp = cfg.get("replay") or fail("config.replay missing")
    days = int(rp.get("days", 40))
    target = rp.get("target_equity")
    frozen = set(map(str, rp.get("freeze", [])))
    order = [str(x) for x in rp.get("liquidation_order", [])] or [p["id"] for p in sorted(pos, key=lambda p: -p["maint"])]
    paths = {}
    for p in pos:
        if p["id"] in frozen:
            continue
        if not p["series"]:
            fail(f"{p['id']} has no series; add one or list it in replay.freeze")
        _, segs = candidate_paths(dict(series=p["series"], leverage=pf_lev(p, rp), annual_cost=p_cost(p, rp),
                                       shift_days=rp.get("shift_days", {}).get(p["id"], 0)),
                                  args.series_dir, cache, anchors, days)
        paths[p["id"]] = dict(segs)
    usable = [a for a in anchors if all(a in paths[i] for i in paths)]
    if len(usable) < 10:
        warnings.append(f"Only {len(usable)} anchors cover every non-frozen series; freeze off-scenario positions to widen the sample.")
    plans_out = []
    for plan in rp.get("plans", [{"label": "hold", "exits": {}}]):
        exits = plan.get("exits", {})
        for pid, legs in exits.items():
            if pid not in {p["id"] for p in pos}:
                fail(f"plan {plan.get('label')}: unknown id {pid}")
            if sum(num(x["fraction"], "fraction", 0, 1) for x in legs) > 1 + 1e-9:
                fail(f"plan {plan.get('label')}: exit fractions for {pid} exceed 1")
        ends, peaks, floor_first, liq, nofill = [], [], 0, 0, 0
        for a in usable:
            qty = {p["id"]: p["qty"] for p in pos}
            done, cash, best, touched, liquidated = set(), cash0, -1e30, False, False
            for d in range(days + 1):
                px = {p["id"]: p["price"] * (paths[p["id"]][a][0][d] if p["id"] in paths else 1.0) for p in pos}
                for p in pos:
                    for i, leg in enumerate(exits.get(p["id"], [])):
                        if (p["id"], i) not in done and px[p["id"]] >= leg["price"]:
                            q = min(p["qty"] * leg["fraction"], qty[p["id"]])
                            done.add((p["id"], i)); qty[p["id"]] -= q; cash += q * leg["price"] / p["fx"]
                mv = {p["id"]: qty[p["id"]] * px[p["id"]] / p["fx"] for p in pos}
                eq = sum(mv.values()) + cash
                buf = eq - k * sum(mv[p["id"]] * p["maint"] for p in pos)
                if buf < floor and not done:
                    touched = True
                if buf < 0:
                    liquidated = True
                    for pid in order:
                        if buf >= 0:
                            break
                        p = next(x for x in pos if x["id"] == pid)
                        if qty[pid] <= 0:
                            continue
                        per_unit_release = px[pid] / p["fx"] * k * p["maint"]
                        need_units = min(qty[pid], (-buf) / per_unit_release + 1e-9) if per_unit_release > 0 else qty[pid]
                        qty[pid] -= need_units; cash += need_units * px[pid] / p["fx"]
                        mv[pid] = qty[pid] * px[pid] / p["fx"]
                        buf = sum(mv.values()) + cash - k * sum(mv[x["id"]] * x["maint"] for x in pos)
                best = max(best, eq)
            ends.append(eq); peaks.append(best)
            floor_first += touched; liq += liquidated; nofill += (not done and bool(exits))
        n = len(ends)
        row = dict(label=plan.get("label", "plan"), n=n)
        if n:
            q = statistics.quantiles(ends, n=10) if n >= 10 else None
            row.update(end_equity_median=r4(statistics.median(ends)), end_equity_p10=r4(q[0]) if q else None,
                       end_equity_p25=r4(statistics.quantiles(ends, n=4)[0]) if n >= 4 else None,
                       prob_floor_before_first_exit=r4(floor_first / n), prob_forced_liquidation=r4(liq / n),
                       prob_no_exit_filled=r4(nofill / n) if exits else None,
                       prob_touch_target=r4(sum(x >= float(target) for x in peaks) / n) if target else None)
        plans_out.append(row)
    warnings.append("Forced liquidation sells at the day's close in liquidation_order until the buffer is non-negative; real brokers may liquidate earlier, intraday and at worse prices.")
    warnings.append("Exit legs fill at their limit when a daily close reaches the level; intraday touches, gaps, fees and FX moves are ignored.")
    out = dict(model="portfolio_stress.replay", calibration_k=r4(k), days=days, n_anchors=len(usable),
               frozen=sorted(frozen), plans=plans_out, warnings=warnings,
               units=dict(money="base_currency", prob="fraction", horizon="trading_days"))
    print(json.dumps(out, ensure_ascii=False, allow_nan=False))


def pf_lev(p, rp):
    return rp.get("series_leverage", {}).get(p["id"], p["lev"])


def p_cost(p, rp):
    return rp.get("annual_cost", {}).get(p["id"], 0.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("stress"); a.add_argument("--portfolio", required=True)
    a = sp.add_parser("regime"); a.add_argument("--config", required=True); a.add_argument("--series-dir", required=True)
    a = sp.add_parser("replay"); a.add_argument("--portfolio", required=True); a.add_argument("--config", required=True)
    a.add_argument("--series-dir", required=True)
    args = ap.parse_args(argv)
    try:
        {"stress": cmd_stress, "regime": cmd_regime, "replay": cmd_replay}[args.cmd](args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

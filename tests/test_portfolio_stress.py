"""Offline contracts for portfolio_stress.py with invented positions and synthetic series."""

import csv
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "elab-model/scripts/portfolio_stress.py"
spec = importlib.util.spec_from_file_location("portfolio_stress", SCRIPT)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)


def write_series(directory, name, closes, start=date(2010, 1, 4)):
    with open(Path(directory) / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close", "high"])
        d = start
        for c in closes:
            while d.weekday() >= 5:
                d += timedelta(days=1)
            w.writerow([d.isoformat(), f"{c:.6f}", f"{c:.6f}"])
            d += timedelta(days=1)


def sawtooth(n_cycles=12):
    """Flat 60 days, a 25% drop over 5 days, a 35-day recovery to the old level."""
    out, level = [], 100.0
    for _ in range(n_cycles):
        out += [level] * 60
        out += [level * (1 - 0.05 * k) for k in range(1, 6)]
        low = level * 0.75
        out += [low + (level - low) * k / 35 for k in range(1, 36)]
    return out


class PortfolioStressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                text=True, capture_output=True, check=False)
        if not success:
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            return result

        def reject(value):
            raise AssertionError(f"invalid JSON number: {value}")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout, parse_constant=reject)
        self.assertIn("units", out)
        self.assertIsInstance(out["warnings"], list)
        return out

    def dump(self, name, obj):
        path = self.dir / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return path

    def portfolio(self, **extra):
        pf = dict(equity=60000, margin_call=40000, floor=5000, bucket_betas={"sector": 1.0},
                  positions=[dict(id="A", qty=1000, price=50, maint_ratio=0.5, leverage=1, bucket="sector", series="SECTOR"),
                             dict(id="B", qty=500, price=100, maint_ratio=0.3, leverage=1, bucket="other", series="BROAD")])
        pf.update(extra)
        return pf

    def test_buffer_and_calibration(self):
        out = self.cli("stress", "--portfolio", self.dump("p.json", self.portfolio()))
        # market value 100000, cash -40000, raw requirement 25000+15000=40000 -> k=1
        self.assertAlmostEqual(out["calibration_k"], 1.0)
        self.assertAlmostEqual(out["base"]["buffer"], 20000)
        self.assertAlmostEqual(out["base"]["look_through_ratio"], 100000 / 60000, places=4)

    def test_targeted_shock_matches_closed_form(self):
        out = self.cli("stress", "--portfolio", self.dump("p.json", self.portfolio()))
        # buffer(s) = 20000 - 50000*s*(1-0.5) -> floor 5000 at s=0.6, margin call at s=0.8
        self.assertAlmostEqual(out["base"]["targeted_shock_to_floor"], 0.6, delta=0.003)
        self.assertAlmostEqual(out["base"]["targeted_shock_to_margin_call"], 0.8, delta=0.003)
        self.assertLess(out["base"]["systemic_shock_to_floor"], out["base"]["targeted_shock_to_floor"])
        self.assertLessEqual(out["base"]["targeted_shock_to_floor_maint_bump"], out["base"]["targeted_shock_to_floor"])

    def test_warns_when_buffer_already_below_floor(self):
        out = self.cli("stress", "--portfolio", self.dump("p.json", self.portfolio(floor=25000)))
        self.assertEqual(out["base"]["targeted_shock_to_floor"], 0.0)
        self.assertTrue(any("already below the floor" in w for w in out["warnings"]))

    def test_selling_releases_maintenance_times_value(self):
        out = self.cli("stress", "--portfolio", self.dump("p.json", self.portfolio(sell_scenarios=[["A"]])))
        sc = out["sell_scenarios"][0]
        self.assertAlmostEqual(sc["buffer"] - out["base"]["buffer"], 50000 * 0.5)
        self.assertEqual(out["release_ranking"][0]["id"], "A")
        self.assertAlmostEqual(out["release_ranking"][0]["buffer_release_per_10000"], 5000)

    def test_synthetic_leverage_compounds_daily(self):
        rows = [(date(2020, 1, 1) + timedelta(days=i), c, c) for i, c in enumerate([100, 110, 99, 99])]
        path = ps.synth(rows, 2, annual_cost=0.0)
        expected = 1.0 * (1 + 2 * 0.10) * (1 + 2 * (99 / 110 - 1)) * 1.0
        self.assertAlmostEqual(path[-1][1], expected, places=9)
        costly = ps.synth(rows, 2, annual_cost=0.252)
        self.assertAlmostEqual(costly[1][1], 1.2 - 0.001, places=9)

    def regime_config(self, **extra):
        cfg = dict(anchor=dict(window=20, gap_days=35, conditions=[dict(series="SECTOR", drawdown_le=-0.15),
                                                                  dict(series="BROAD", drawdown_ge=-0.05)]),
                   candidates=[dict(label="S1", series="SECTOR"), dict(label="S3", series="SECTOR", leverage=3)],
                   exit_rules=dict(names=["T20", "MA_REVERT"]), bootstrap=dict(iterations=200, seed=1),
                   levels=[dict(label="S1", series="SECTOR", price_now=100, cost_basis=110,
                                touch_levels=[105, 300], buy_levels=[95])])
        cfg.update(extra)
        return cfg

    def write_market(self):
        series = sawtooth()
        write_series(self.dir, "SECTOR", series)
        write_series(self.dir, "BROAD", [100.0] * len(series))

    def test_regime_finds_each_drop_once_and_measures_recovery(self):
        self.write_market()
        out = self.cli("regime", "--config", self.dump("c.json", self.regime_config()), "--series-dir", self.dir)
        self.assertGreaterEqual(out["n_anchors"], 10)
        self.assertLessEqual(out["n_anchors"], 12)
        by = {(r["label"], r["rule"]): r for r in out["exit_results"]}
        self.assertEqual(by[("S1", "MA_REVERT")]["n"], by[("S1", "T20")]["n"])
        # independent check of one anchor: T20 equals the close 20 rows later over the anchor close
        rows = ps.load_series(self.dir, "SECTOR", {})
        first = date.fromisoformat(out["anchors"][0])
        i = next(j for j, r in enumerate(rows) if r[0] >= first)
        seg, _ = ps.segment(rows, first, 61, 0)
        self.assertAlmostEqual(seg[20] - 1, rows[i + 20][1] / rows[i][1] - 1, places=9)
        self.assertEqual(by[("S1", "T20")]["win_rate"], 1.0)
        lo, hi = by[("S1", "T20")]["mean_ci90"]
        self.assertLessEqual(lo, by[("S1", "T20")]["mean"])
        self.assertGreaterEqual(hi, by[("S1", "T20")]["mean"])
        lv = out["levels"][0]
        touch = {t["level"]: t["prob"] for t in lv["touch"]}
        self.assertEqual(touch[300], 0.0)
        self.assertTrue(any("Only" in w for w in out["warnings"]))

    def test_replay_liquidates_on_crash_and_respects_exits(self):
        crash = [100.0] * 80 + [100 * (0.75 ** k) for k in range(1, 9)] + [10.0] * 70
        crash = crash * 4
        write_series(self.dir, "SECTOR", crash)
        write_series(self.dir, "BROAD", [100.0] * len(crash))
        pf = self.portfolio(margin_call=None)
        cfg = self.regime_config(replay=dict(days=30, freeze=["B"], liquidation_order=["A"],
                                             plans=[dict(label="hold", exits={}),
                                                    dict(label="exit", exits={"A": [dict(price=1000, fraction=1.0)]})]))
        out = self.cli("replay", "--portfolio", self.dump("p.json", pf), "--config", self.dump("c.json", cfg),
                       "--series-dir", self.dir)
        hold = out["plans"][0]
        self.assertGreater(hold["n"], 0)
        self.assertEqual(hold["prob_forced_liquidation"], 1.0)
        self.assertEqual(out["plans"][1]["prob_no_exit_filled"], 1.0)

    def test_rejects_bad_inputs_without_traceback(self):
        self.cli("stress", "--portfolio", self.dump("bad.json", {"positions": []}), success=False)
        bad = self.portfolio()
        bad["positions"][0]["maint_ratio"] = 1.5
        self.cli("stress", "--portfolio", self.dump("bad2.json", bad), success=False)
        self.write_market()
        cfg = self.regime_config(replay=dict(plans=[dict(label="x", exits={"A": [dict(price=1, fraction=0.7),
                                                                                    dict(price=2, fraction=0.6)]})]))
        self.cli("replay", "--portfolio", self.dump("p.json", self.portfolio()), "--config", self.dump("c.json", cfg),
                 "--series-dir", self.dir, success=False)
        self.cli("regime", "--config", self.dump("c2.json", self.regime_config()), "--series-dir", self.dir / "missing",
                 success=False)


if __name__ == "__main__":
    unittest.main()

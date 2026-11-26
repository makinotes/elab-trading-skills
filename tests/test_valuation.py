"""Offline contracts for valuation.py with an invented company; expected numbers worked out by hand."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "elab-model/scripts/valuation.py"
spec = importlib.util.spec_from_file_location("valuation", SCRIPT)
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)

SOURCES = {k: "synthetic" for k in va.REQUIRED_SOURCES}


def company(**extra):
    c = dict(name="Synthetic Co", currency="USD", revenue=1000, operating_margin=0.2, tax_rate=0.25,
             cash=100, debt=50, shares=100, discount_rate=0.10, terminal_growth=0.0, roic=0.2,
             sources=dict(SOURCES))
    c.update(extra)
    return c


class ValuationTests(unittest.TestCase):
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

    # ---------------------------------------------------------------- dcf

    def test_zero_growth_equals_perpetuity(self):
        # NOPAT = 1000*0.2*0.75 = 150, no reinvestment -> EV = 150/0.1 = 1500 for any horizon
        cfg = company(scenarios={"base": {"years": 7, "growth": 0.0}})
        out = self.cli("dcf", "--input", self.dump("c.json", cfg))
        base = out["scenarios"]["base"]
        self.assertAlmostEqual(base["bridge"]["enterprise_value"], 1500, places=3)
        self.assertAlmostEqual(base["bridge"]["equity_value"], 1550, places=3)
        self.assertAlmostEqual(base["per_share"], 15.5, places=4)

    def test_one_year_growth_hand_case(self):
        # Rev1=1100, NOPAT1=165, reinvest=165*0.1/0.2=82.5, FCFF=82.5, PV=75
        # terminal: NOPAT2=165 (g=0), TV=1650, PV=1500 -> EV=1575
        cfg = company(scenarios={"base": {"years": 1, "growth": 0.1}})
        base = self.cli("dcf", "--input", self.dump("c.json", cfg))["scenarios"]["base"]
        self.assertAlmostEqual(base["rows"][0]["fcff"], 82.5, places=4)
        self.assertAlmostEqual(base["bridge"]["pv_explicit_fcff"], 75, places=4)
        self.assertAlmostEqual(base["bridge"]["pv_terminal_value"], 1500, places=4)
        self.assertAlmostEqual(base["bridge"]["enterprise_value"], 1575, places=4)
        self.assertAlmostEqual(base["terminal_value_share"], 1500 / 1575, places=4)

    def test_terminal_growth_is_value_neutral_by_default(self):
        # With terminal ROIC = discount rate, TV = NOPAT_{N+1} / r regardless of terminal growth
        c = va.parse_company(company(terminal_growth=0.03))
        p = va.scenario_params(c, "base", {"years": 3, "growth": 0.0})
        v = va.value(c, p)
        nopat_next = 1000 * 1.03 * 0.2 * 0.75
        self.assertAlmostEqual(v["terminal_value"], nopat_next / 0.10, places=6)

    def test_mid_year_raises_value(self):
        end = self.cli("dcf", "--input", self.dump("a.json", company(scenarios={"base": {"growth": 0.05}})))
        mid = self.cli("dcf", "--input", self.dump("b.json", company(mid_year=True, scenarios={"base": {"growth": 0.05}})))
        ratio = mid["scenarios"]["base"]["bridge"]["enterprise_value"] / end["scenarios"]["base"]["bridge"]["enterprise_value"]
        self.assertAlmostEqual(ratio, 1.1 ** 0.5, places=4)

    def test_scenarios_grid_and_reference(self):
        cfg = company(reference_price={"value": 20, "label": "现价"},
                      scenarios={"bear": {"growth": 0.0}, "base": {"growth": 0.08, "margin_target": 0.25},
                                 "bull": {"growth_start": 0.2, "growth_end": 0.05, "margin_target": 0.3}})
        out = self.cli("dcf", "--input", self.dump("c.json", cfg))
        ps = [out["scenarios"][k]["per_share"] for k in ("bear", "base", "bull")]
        self.assertTrue(ps[0] < ps[1] < ps[2])
        self.assertAlmostEqual(out["scenarios"]["bear"]["per_share_vs_reference"], 15.5 / 20 - 1, places=4)
        grid = out["sensitivity"]["per_share"]
        self.assertEqual(len(grid), 5)
        self.assertEqual(grid[2][2], out["scenarios"]["base"]["per_share"])
        # discount 0.08 with terminal growth +0.01: still valid; higher discount rate lowers value
        self.assertGreater(grid[0][2], grid[4][2])
        self.assertNotIn("average", json.dumps(out))

    def test_warnings(self):
        cfg = company(terminal_growth=0.05, sources={}, tam=1500,
                      scenarios={"base": {"years": 10, "growth": 0.08, "roic": 0.05}})
        w = " ".join(self.cli("dcf", "--input", self.dump("c.json", cfg))["warnings"])
        self.assertIn("没标来源", w)
        self.assertIn("高于 4%", w)
        self.assertIn("低于折现率", w)
        self.assertIn("市场规模", w)
        self.assertIn("价值全靠终值撑着", w)

    def test_negative_explicit_value_is_flagged(self):
        # ROIC 0.05 with 20% growth: reinvestment = NOPAT * 0.2 / 0.05 = 4x NOPAT, so FCFF < 0
        cfg = company(scenarios={"base": {"years": 5, "growth": 0.2, "roic": 0.05}})
        out = self.cli("dcf", "--input", self.dump("c.json", cfg))
        self.assertLess(out["scenarios"]["base"]["bridge"]["pv_explicit_fcff"], 0)
        self.assertIn("现金流是负的，价值全靠终值撑着", " ".join(out["warnings"]))

    def test_display_tables_are_preformatted(self):
        cfg = company(reference_price={"value": 20, "label": "现价"},
                      scenarios={"bear": {"growth": 0.0}, "base": {"years": 1, "growth": 0.1}})
        d = self.cli("dcf", "--input", self.dump("c.json", cfg))["display"]
        self.assertEqual(d["warnings_md"], "- base：企业价值有 95.2% 来自终值，结果主要看终值那部分的假设")
        quiet = self.cli("dcf", "--input", self.dump("q.json", company(scenarios={"bear": {"growth": 0.0}})))["display"]
        self.assertEqual(quiet["warnings_md"], "- 无")
        self.assertEqual(d["result_md"].splitlines()[0], "| 情景 | 每股价值 | 与参考价 | 终值占比 |")
        # bear: 15.5 per share, 15.5/20-1 = -22.5%, TV share of zero-growth 10y case
        self.assertTrue(d["result_md"].splitlines()[2].startswith("| bear | 15.50 | -22.5% | "))
        # base: EV 1575 + 50 = 1625 -> 16.25, -18.8%, TV share 1500/1575 = 95.2%
        self.assertEqual(d["result_md"].splitlines()[3], "| base | 16.25 | -18.8% | 95.2% |")
        self.assertIn("| 折现率 | 10.0% | 用户假设 |", d["input_md"])
        self.assertIn("| 收入 | 1,000 | synthetic |", d["input_md"])

    def test_display_reverse_and_anchors(self):
        cfg = company(terminal_growth=0.02, reference_price={"value": self.forward_price(0.12)}, trailing_growth=0.12)
        d = self.cli("reverse", "--input", self.dump("c.json", cfg), "--solve", "margin")["display"]
        self.assertEqual(d["result_md"].splitlines()[2], "| 利润率 | 增速 12.0%，10 年 | 20.0% | 是 |")
        self.assertEqual(len(d["result_md"].splitlines()), 3)
        a = self.cli("anchors", "--input", self.dump("a.json", self.anchors()))["display"]
        rows = a["result_md"].splitlines()
        self.assertEqual(rows[2], "| 共识（DataVendor） | 未返回数据 | — | 2026-11-19 | — |")
        self.assertEqual(rows[3], "| Broker A | 100.00 | +25.0% | 2026-11-17 | 二手 |")
        self.assertIn("- 共识是空的", a["warnings_md"])
        self.assertEqual(a["lines"][0], "Broker A 2026-11-17 给的目标价 100.00（二手报道，期限未说明），比参考价高 25.0%。")

    def test_identical_scenario_warnings_are_merged(self):
        cfg = company(terminal_growth=0.05, scenarios={"base": {"growth": 0.0}, "bull": {"growth": 0.02}})
        w = self.cli("dcf", "--input", self.dump("c.json", cfg))["warnings"]
        self.assertIn("base、bull：永续增长率 5.0% 高于 4%，长期看整体经济一般长不了这么快", w)

    def test_rejects_bad_inputs(self):
        self.cli("dcf", "--input", self.dump("a.json", company(terminal_growth=0.1, scenarios={"base": {"growth": 0}})), success=False)
        self.cli("dcf", "--input", self.dump("b.json", company(archetype="bank", scenarios={"base": {"growth": 0}})), success=False)
        self.cli("dcf", "--input", self.dump("c.json", company(roic=None, scenarios={"base": {"growth": 0.1}})), success=False)
        self.cli("dcf", "--input", self.dump("d.json", company(scenarios={})), success=False)

    # ---------------------------------------------------------------- reverse

    def forward_price(self, g, years=10, margin=0.2):
        c = va.parse_company(company(terminal_growth=0.02))
        h = dict(years=years, margin=margin, roic=0.2, r=0.10, gt=0.02, ronic=None)
        return va.flat(c, h, g)

    def test_reverse_growth_round_trip(self):
        price = self.forward_price(0.12)
        cfg = company(terminal_growth=0.02, reference_price={"value": price}, trailing_growth=0.12)
        out = self.cli("reverse", "--input", self.dump("c.json", cfg))
        self.assertAlmostEqual(out["implied_growth"]["growth"], 0.12, places=4)
        self.assertAlmostEqual(out["implied_margin"]["margin"], 0.2, places=4)
        self.assertEqual(out["implied_years"]["years"], 10)
        self.assertTrue(out["implied_growth"]["reachable"])
        grid = out["implied_growth_grid"]["growth"]
        self.assertAlmostEqual(grid[1][2], 0.12, places=4)
        # a longer horizon needs less growth; a higher discount rate needs more
        self.assertGreater(grid[0][2], grid[2][2])
        self.assertLess(grid[1][0], grid[1][4])

    def test_reverse_matches_independent_implementation(self):
        # Inputs and expected grid are the worked example published in the README of
        # github.com/Keenan-ux/implied-expectations (same two-stage FCFF, value-neutral terminal).
        cfg = dict(revenue=215.9, operating_margin=0.604, tax_rate=0.151, cash=62.4, debt=12.8, shares=24.51,
                   discount_rate=0.095, terminal_growth=0.025, roic=0.76, trailing_growth=1.005,
                   reference_price={"value": 180}, sources=dict(SOURCES))
        out = self.cli("reverse", "--input", self.dump("c.json", cfg))
        self.assertAlmostEqual(out["implied_growth"]["growth"], 0.199, delta=0.0006)
        self.assertAlmostEqual(out["implied_margin"]["margin"], 0.006, delta=0.0006)
        expected = [[0.289, 0.335, 0.379, 0.421, 0.463],
                    [0.153, 0.177, 0.199, 0.222, 0.243],
                    [0.111, 0.129, 0.147, 0.164, 0.180]]
        for got_row, exp_row in zip(out["implied_growth_grid"]["growth"], expected):
            for got, exp in zip(got_row, exp_row):
                self.assertAlmostEqual(got, exp, delta=0.0006)

    def test_reverse_unreachable_is_reported_not_invented(self):
        cfg = company(reference_price={"value": 1e7})
        out = self.cli("reverse", "--input", self.dump("c.json", cfg), "--solve", "growth")
        self.assertIsNone(out["implied_growth"]["growth"])
        self.assertFalse(out["implied_growth"]["reachable"])
        self.assertIn("这组假设解释不了这个价格", " ".join(out["warnings"]))

    def test_reverse_needs_inputs(self):
        self.cli("reverse", "--input", self.dump("a.json", company()), success=False)
        self.cli("reverse", "--input", self.dump("b.json", company(reference_price={"value": 20})),
                 "--solve", "years", success=False)
        out = self.cli("reverse", "--input", self.dump("c.json", company(operating_margin=-0.1, reference_price={"value": 20})),
                       "--solve", "growth")
        self.assertIsNone(out["implied_growth"])
        self.assertIn("现在不赚钱，没法反推增速", " ".join(out["warnings"]))

    def test_implied_multiples(self):
        out = self.cli("reverse", "--input", self.dump("c.json", company(reference_price={"value": 20})), "--solve", "growth")
        # EV = 20*100 - 100 + 50 = 1950
        self.assertAlmostEqual(out["implied_at_price"]["enterprise_value"], 1950)
        self.assertAlmostEqual(out["implied_at_price"]["ev_to_revenue"], 1.95)
        self.assertAlmostEqual(out["implied_at_price"]["ev_to_nopat"], 13.0)

    # ---------------------------------------------------------------- anchors

    def anchors(self, **extra):
        a = dict(as_of="2026-11-19", currency="USD", reference_price={"value": 80, "label": "发行价"},
                 consensus={"source": "DataVendor", "as_of": "2026-11-19"},
                 brokers=[{"name": "Broker A", "target": 100, "date": "2026-11-17", "evidence": "secondary"},
                          {"name": "Broker B", "target": 120, "date": "2026-06-01", "evidence": "primary"}])
        a.update(extra)
        return a

    def test_anchors_rows_not_averaged(self):
        out = self.cli("anchors", "--input", self.dump("a.json", self.anchors()))
        self.assertEqual([b["name"] for b in out["brokers"]], ["Broker A", "Broker B"])
        self.assertAlmostEqual(out["brokers"][0]["vs_reference"], 0.25)
        self.assertEqual(out["broker_span"], dict(n=2, low=100, high=120, low_vs_reference=0.25, high_vs_reference=0.5))
        self.assertNotIn("mean", out["broker_span"])
        w = " ".join(out["warnings"])
        self.assertIn("共识是空的", w)
        self.assertIn("不当成 0", w)
        self.assertIn("Broker A的目标价来自二手报道", w)
        self.assertIn("Broker B的目标价是 171 天前的", w)
        self.assertIn("只有 2 家", w)

    def test_anchors_chain_dcf_result(self):
        dcf = self.cli("dcf", "--input", self.dump("c.json", company(terminal_growth=0.05, scenarios={"base": {"growth": 0}})))
        path = self.dump("dcf.json", dcf)
        out = self.cli("anchors", "--input", self.dump("a.json", self.anchors(consensus=None, brokers=[])),
                       "--dcf-result", path)
        own = out["own_model"]
        self.assertEqual(own["values"]["base"]["value"], dcf["scenarios"]["base"]["per_share"])
        self.assertEqual(own["model_warnings"], dcf["warnings"])
        self.assertIn("不是一个时间口径", " ".join(out["warnings"]))

    def test_anchors_rejects_mixed_currency(self):
        a = self.anchors(brokers=[{"name": "X", "target": 10, "date": "2026-11-01", "currency": "HKD"}])
        self.cli("anchors", "--input", self.dump("a.json", a), success=False)


if __name__ == "__main__":
    unittest.main()

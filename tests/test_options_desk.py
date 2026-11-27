"""Offline contracts for options_desk.py with invented trades; expected numbers worked out by hand."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "elab-model/scripts/options_desk.py"
spec = importlib.util.spec_from_file_location("options_desk", SCRIPT)
od = importlib.util.module_from_spec(spec)
spec.loader.exec_module(od)

BPS_LEGS = [{"type": "put", "side": "short", "strike": 95, "premium": 2.1, "delta": -0.30, "dte": 45, "iv": 0.32},
            {"type": "put", "side": "long", "strike": 90, "premium": 0.9, "delta": -0.18, "dte": 45, "iv": 0.34}]
RULES = {"structures": {"bull_put_spread": {"dte_min": 45, "dte_max": 60, "short_delta_min": 0.2, "short_delta_max": 0.5,
                                            "width_max_steps": 3, "strike_step": 5, "credit_to_width_max": 0.75,
                                            "avoid_earnings": True, "take_profit": [0.2, 0.3, 0.5]}},
         "budget": {"options_margin_total": 15000, "per_underlying_max": 4000},
         "sell_put": {"index_only": True, "size_by_cash": True},
         "roll": {"max_rolls": 1, "keep_strike": True}}


def trade(**extra):
    t = dict(underlying="Synthetic", currency="USD", spot=100, as_of="2026-11-27", contracts=2, rate=0.04,
             legs=BPS_LEGS, account={"options_margin_used": 9000, "underlying_margin_used": 3500, "cash": 20000})
    t.update(extra)
    return t


class OptionsDeskTests(unittest.TestCase):
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
        self.assertIn("display", out)
        return out

    def dump(self, name, obj):
        path = self.dir / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return path

    # ---------------------------------------------------------------- math

    def test_black_scholes_textbook_values(self):
        call = dict(type="call", strike=100, iv=0.2)
        put = dict(type="put", strike=100, iv=0.2)
        self.assertAlmostEqual(od.bs(call, 100, 1.0, 0.05)["price"], 10.4506, places=4)
        self.assertAlmostEqual(od.bs(put, 100, 1.0, 0.05)["price"], 5.5735, places=4)
        self.assertAlmostEqual(od.bs(call, 100, 1.0, 0.05)["delta"], 0.6368, places=4)

    def test_bps_profile_and_margin(self):
        # credit 2.1 - 0.9 = 1.2; max loss 5 - 1.2 = 3.8; breakeven 95 - 1.2 = 93.8; 2 contracts x 100
        out = self.cli("check", "--trade", self.dump("t.json", trade()))
        self.assertEqual(out["structure"], "bull_put_spread")
        self.assertAlmostEqual(out["profile"]["max_profit"], 1.2)
        self.assertAlmostEqual(out["profile"]["max_loss"], -3.8)
        self.assertEqual(out["profile"]["breakevens"], [93.8])
        self.assertAlmostEqual(out["margin_total"], 1000)
        self.assertIn("| 到期最多亏 | 760 |", out["display"]["result_md"])
        self.assertIn("没有提供你的规则文件", " ".join(out["warnings"]))

    def test_rule_checks(self):
        out = self.cli("check", "--trade", self.dump("t.json", trade(earnings_date="2026-12-20")),
                       "--rules", self.dump("r.json", RULES))
        status = {c["rule"]: c["status"] for c in out["checks"]}
        self.assertEqual(status["到期天数"], "符合")
        self.assertEqual(status["卖腿 Delta（行权价 95.00）"], "符合")
        self.assertEqual(status["价宽"], "符合")
        self.assertEqual(status["收到的权利金 / 价宽"], "符合")
        self.assertEqual(status["持仓期间避开财报"], "不符合")
        self.assertEqual(status["期权总保证金预算"], "符合")
        self.assertEqual(status["单个标的保证金上限"], "不符合")   # 3500 + 1000 > 4000
        self.assertEqual(out["summary"], {"ok": 5, "fail": 2, "missing": 0})
        lines = out["display"]["lines"]
        self.assertIn("「单个标的保证金上限」没过：加上这笔后 4,500；你的规则是 4,000。", lines)
        self.assertIn("你规则里的止盈档：20.0%、30.0%、50.0%，建仓时一起挂好。", lines)

    def test_missing_data_is_reported_not_guessed(self):
        legs = [dict(BPS_LEGS[0], delta=None, iv=None), dict(BPS_LEGS[1], iv=None)]
        out = self.cli("check", "--trade", self.dump("t.json", trade(legs=legs)), "--rules", self.dump("r.json", RULES))
        status = {c["rule"]: c["status"] for c in out["checks"]}
        self.assertEqual(status["卖腿 Delta（行权价 95.00）"], "缺数据")
        self.assertEqual(status["持仓期间避开财报"], "缺数据")
        self.assertNotIn("holding_grid", out)
        self.assertIn("只算到期盈亏", " ".join(out["warnings"]))

    def test_holding_grid_converges_to_expiry(self):
        out = self.cli("check", "--trade", self.dump("t.json", trade()))
        grid = out["holding_grid"]
        self.assertEqual(grid["days"][-1], 45)
        at_expiry = [row[-1] for row in grid["pl"]]
        self.assertAlmostEqual(at_expiry[0], -760)   # -15%: below the long strike
        self.assertAlmostEqual(at_expiry[3], 240)    # unchanged: both puts expire worthless

    def test_covered_call_and_naked_call(self):
        cc = [{"type": "stock", "side": "long", "premium": 100}, {"type": "call", "side": "short", "strike": 110, "premium": 2, "dte": 30}]
        out = self.cli("check", "--trade", self.dump("c.json", trade(legs=cc, contracts=1)))
        self.assertEqual(out["structure"], "covered_call")
        self.assertAlmostEqual(out["profile"]["max_profit"], 12)
        self.assertAlmostEqual(out["profile"]["max_loss"], -98)
        self.assertEqual(out["profile"]["breakevens"], [98.0])
        naked = [{"type": "call", "side": "short", "strike": 110, "premium": 2, "dte": 30}]
        out = self.cli("check", "--trade", self.dump("n.json", trade(legs=naked, contracts=1)))
        self.assertIsNone(out["profile"]["max_loss"])
        self.assertIn("| 到期最多亏 | 无上限 |", out["display"]["result_md"])

    def test_rejects_calendars_and_bad_legs(self):
        cal = [dict(BPS_LEGS[0]), dict(BPS_LEGS[1], dte=75)]
        self.cli("check", "--trade", self.dump("a.json", trade(legs=cal)), success=False)
        self.cli("check", "--trade", self.dump("b.json", trade(legs=[{"type": "swap", "side": "long"}])), success=False)

    # ---------------------------------------------------------------- roll / assign / margin

    def test_roll_hand_case(self):
        pos = dict(underlying="Synthetic", currency="USD", spot=93, contracts=2, rolls_done=0,
                   legs_open=[{"type": "put", "side": "short", "strike": 95, "premium": 2.1, "mark": 3.4, "dte": 7},
                              {"type": "put", "side": "long", "strike": 90, "premium": 0.9, "mark": 0.6, "dte": 7}],
                   legs_new=[{"type": "put", "side": "short", "strike": 95, "premium": 4.0, "dte": 42},
                             {"type": "put", "side": "long", "strike": 90, "premium": 1.9, "dte": 42}])
        out = self.cli("roll", "--position", self.dump("p.json", pos), "--rules", self.dump("r.json", RULES))
        # close: -3.4 + 0.6 = -2.8; open: 4.0 - 1.9 = 2.1; net -0.7 x 200 = -140
        self.assertAlmostEqual(out["net_roll_total"], -140)
        # locked: short -(3.4-2.1) + long (0.6-0.9) = -1.6 x 200 = -320
        self.assertAlmostEqual(out["locked_pl_total"], -320)
        # cumulative cash 1.2 - 0.7 = 0.5 -> max loss (5 - 0.5) x 200 = 900, breakeven 94.5
        self.assertAlmostEqual(out["new_with_history"]["max_loss"], 900)
        self.assertEqual(out["new_with_history"]["breakevens"], [94.5])
        self.assertEqual(out["days_added"], 35)
        self.assertEqual([c["status"] for c in out["checks"]], ["符合", "符合"])
        self.assertIn("平掉旧仓亏了 320。", out["display"]["lines"][0])
        twice = self.cli("roll", "--position", self.dump("q.json", dict(pos, rolls_done=1)), "--rules", self.dump("r.json", RULES))
        self.assertEqual(twice["checks"][0]["status"], "不符合")

    def test_assign_put_and_covered_call(self):
        csp = dict(underlying="Idx", currency="USD", spot=500, contracts=1, account={"cash": 40000},
                   legs=[{"type": "put", "side": "short", "strike": 480, "premium": 6.5, "dte": 40}])
        out = self.cli("assign", "--position", self.dump("a.json", csp))
        self.assertIn("| 需要的现金 | 48,000 |", out["display"]["result_md"])
        self.assertIn("每股 473.50", out["display"]["result_md"])
        self.assertIn("现金不够接盘", " ".join(out["warnings"]))
        cc = dict(underlying="X", currency="USD", spot=115, contracts=1,
                  legs=[{"type": "stock", "side": "long", "premium": 100},
                        {"type": "call", "side": "short", "strike": 110, "premium": 2, "dte": 30}])
        out = self.cli("assign", "--position", self.dump("c.json", cc))
        self.assertIn("实际卖价每股 112.00", " ".join(out["display"]["lines"]))

    def test_margin_naked_put_formula(self):
        csp = dict(underlying="Idx", currency="USD", spot=500, contracts=1,
                   legs=[{"type": "put", "side": "short", "strike": 480, "premium": 6.5, "dte": 40}])
        out = self.cli("margin", "--trade", self.dump("m.json", csp))
        # 6.5 + max(0.2*500 - 20, 0.1*480) = 86.5 per share; cash secured 480 - 6.5 = 473.5
        self.assertAlmostEqual(out["margin"]["requirement"], 86.5)
        self.assertAlmostEqual(out["margin_total"], 8650)
        self.assertIn("| 如果按现金担保（备足接盘的钱） | 47,350 |", out["display"]["result_md"])


if __name__ == "__main__":
    unittest.main()

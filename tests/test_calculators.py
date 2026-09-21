"""Offline calculator contracts with invented inputs and independent payoff checks."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1] / "elab-model/scripts"


class CalculatorTests(unittest.TestCase):
    def cli(self, script, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / script), *map(str, args)],
                                text=True, capture_output=True, check=False)
        if not success:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        def reject(value):
            raise AssertionError(f"invalid JSON number: {value}")
        return json.loads(result.stdout, parse_constant=reject)

    def test_strategy_extrema_match_expiry_payoffs(self):
        scenarios = [
            ("bull-put-spread", ["--short-strike", 95, "--long-strike", 90, "--credit", 1.35],
             lambda spot: (1.35 - max(95-spot, 0) + max(90-spot, 0))*100),
            ("bear-put-spread", ["--long-strike", 95, "--short-strike", 90, "--debit", 2],
             lambda spot: (-2 + max(95-spot, 0) - max(90-spot, 0))*100),
            ("covered-call", ["--entry-price", 100, "--call-strike", 105, "--credit", 1.5],
             lambda spot: (spot-100 + 1.5 - max(spot-105, 0))*100),
            ("cash-secured-put", ["--strike", 95, "--credit", 1.5],
             lambda spot: (1.5 - max(95-spot, 0))*100),
            ("long-put", ["--strike", 95, "--debit", 2],
             lambda spot: (-2 + max(95-spot, 0))*100),
        ]
        for name, args, payoff in scenarios:
            with self.subTest(strategy=name):
                data = self.cli("strategy_models.py", name, *args, "--dte", 30)
                terminal = [payoff(spot) for spot in (0, 90, 95, 100, 105, 200)]
                self.assertAlmostEqual(data["max_profit"], max(terminal))
                self.assertAlmostEqual(data["max_loss"], -min(terminal))
                self.assertAlmostEqual(payoff(data["breakeven"]), 0, places=7)
                self.assertEqual(data["units"]["max_loss"], "per_contract_dollar")

    def test_ev_scale_invariance_including_large_finite_values(self):
        for scale in (0.1, 100, 1e308):
            with self.subTest(scale=scale):
                data = self.cli("ev_model.py", "ev", "--win-rate", .5,
                                "--avg-win", scale, f"--avg-loss={-scale}")
                self.assertEqual(data["ev_per_trade"], 0)
                self.assertEqual(data["breakeven_win_rate"], .5)
                self.assertEqual(data["kelly_full"], 0)

    def test_expiry_math_does_not_need_invented_time(self):
        args = ["bull-put-spread", "--short-strike", 95,
                "--long-strike", 90, "--credit", 1.35]
        future = self.cli("strategy_models.py", *args, "--dte", 30)
        for time_args in ([], ["--dte", 0]):
            data = self.cli("strategy_models.py", *args, *time_args)
            for key in ("max_profit", "max_loss", "breakeven"):
                self.assertEqual(data[key], future[key])
            self.assertIsNone(data["greeks_exposure"])
            self.assertTrue(data["warnings"])
            self.assertEqual(data["payoff_scope"], "at_expiration_before_fees")
        self.cli("strategy_models.py", *args, "--dte", -1, success=False)

    def test_calculator_overflow_fails_before_stdout(self):
        self.cli("strategy_models.py", "cash-secured-put", "--strike", "1e308",
                 "--credit", "1e307", "--dte", 30, success=False)
        self.cli("ev_model.py", "option-credit", "--credit", "1e307",
                 "--max-loss", "1e308", "--pop", .5, success=False)
        self.cli("ev_model.py", "ev", "--win-rate", .5, "--avg-win", "1e308",
                 "--avg-loss=-1e-308", success=False)

    def test_invalid_equity_prices_and_sample_sizes_fail(self):
        for strike in (0, -1):
            self.cli("strategy_models.py", "bull-put-spread", "--short-strike", strike,
                     "--long-strike", -6, "--credit", 1, "--dte", 30, success=False)
        for spot in (0, -1):
            self.cli("strategy_models.py", "covered-call", "--entry-price", 100,
                     "--call-strike", 105, "--credit", 1.5, "--dte", 30,
                     "--spot", spot, success=False)
        for sample in (0, -10):
            for command, values in (("ev", ["--avg-win", 100, "--avg-loss=-100"]),
                                    ("kelly", ["--payoff-ratio", 1])):
                self.cli("ev_model.py", command, "--win-rate", .5, *values,
                         "--sample-size", sample, success=False)

    def test_invalid_thresholds_fall_back_with_visible_warning(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "thresholds.json"
            for value in (None, [], {"min_sample_size": -1}, {"min_sample_size": True},
                          {"otm_deep_ratio": float("nan")}, {"otm_deep_ratio": "disabled"}):
                path.write_text(json.dumps(value))
                with self.subTest(value=value):
                    result = self.cli("ev_model.py", "ev", "--win-rate", .5,
                                      "--avg-win", 100, "--avg-loss=-100", "--config", path)
                    self.assertIn("使用内置默认阈值", result["warnings"])
            path.write_text('{"credit_width_min_ratio": -1}')
            result = self.cli("strategy_models.py", "bull-put-spread", "--short-strike", 95,
                              "--long-strike", 90, "--credit", .5, "--dte", 30, "--config", path)
            self.assertIn("使用内置默认阈值", result["warnings"])
            self.assertTrue(any("收得太薄" in item for item in result["warnings"]))


if __name__ == "__main__":
    unittest.main()

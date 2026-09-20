"""Public deterministic tests of IV arithmetic, using synthetic values only."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "iv_metrics", Path(__file__).resolve().parents[1] / "elab-research/scripts/iv_metrics.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
calculate = MODULE.calculate


class IVMetricsTests(unittest.TestCase):
    def test_bounds_do_not_fabricate_percentile(self):
        result = calculate(55, low=40, high=85)
        self.assertAlmostEqual(result["iv_rank"], 100 / 3)
        self.assertIsNone(result["iv_percentile"])
        self.assertIsNone(result["history_count"])

    def test_percentile_ties_are_strict(self):
        result = calculate(20, history=[10, 20, 20, 40])
        self.assertEqual(result["iv_percentile"], 25)
        self.assertEqual(result["history_count"], 4)

    def test_unit_scaling_preserves_both_metrics(self):
        percent = calculate(25, history=[10, 20, 40, 50])
        decimal = calculate(.25, history=[.1, .2, .4, .5])
        self.assertAlmostEqual(percent["iv_rank"], decimal["iv_rank"])
        self.assertEqual(percent["iv_percentile"], decimal["iv_percentile"])

    def test_flat_history_is_not_zero_rank(self):
        result = calculate(20, history=[20, 20])
        self.assertIsNone(result["iv_rank"])
        self.assertEqual(result["iv_rank_status"], "undefined_flat_range")
        self.assertEqual(result["iv_percentile"], 0)

    def test_no_silent_clamping(self):
        self.assertEqual(calculate(60, low=20, high=40)["iv_rank"], 200)
        self.assertEqual(calculate(10, low=20, high=40)["iv_rank"], -50)

    def test_invalid_values_fail(self):
        for invalid in [True, "20", float("nan"), float("inf"), -1]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    calculate(invalid, low=10, high=20)
                with self.assertRaises(ValueError):
                    calculate(15, history=[10, invalid, 20])

    def test_ambiguous_or_incomplete_history_fails(self):
        for kwargs in [{}, {"low": 10}, {"low": 20, "high": 10}, {"history": []},
                       {"history": [10, 20], "low": 10, "high": 20}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    calculate(15, **kwargs)


if __name__ == "__main__":
    unittest.main()

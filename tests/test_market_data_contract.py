"""Fictional offline inputs test the price-to-report contract, not investment skill."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("market_contract", ROOT / "elab-futu-research/scripts/futu_research.py")
FR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FR)


class MarketDataContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        for name in ("request_json", "request_bytes", "_tiger_fetch_html"):
            patch = mock.patch.object(FR, name, side_effect=AssertionError("offline test: network forbidden"))
            patch.start()
            self.addCleanup(patch.stop)
        self.claim = {"claim_id": "fictional-claim-1", "author_uid": "12345", "feed_id": "10001",
                      "platform": "futu", "published_at": "2025-01-10T09:00:00+08:00",
                      "symbol_raw": "US.ALPH", "direction": "bullish", "evidence_level": "C",
                      "evidence_span": "我看多 ALPH"}

    def bars(self, count=150, price=100):
        start = datetime(2024, 12, 1, tzinfo=timezone.utc)
        return [{"date": (start + timedelta(days=i)).date().isoformat(),
                 "open": price, "high": price+2, "low": price-2,
                 "close": price+1, "volume": 1000} for i in range(count)]

    def csv(self, name, bars):
        path = self.output / "analysis/market/input" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(bars[0]))
            writer.writeheader()
            writer.writerows(bars)
        return path

    def prepare_offline_chain(self, count=150):
        detail = self.output / "raw/details/12345/10001.json"
        FR.atomic_write_json(detail, {"synthetic": True, "text": self.claim["evidence_span"]})
        post = dict(self.claim, profile_uid="12345", author_name="Fictional Author",
                    text=self.claim["evidence_span"], title="", source={"detail_path": str(detail)})
        FR.write_archive_files(self.output, [post])
        FR.prepare(argparse.Namespace(output=str(self.output)))
        FR.write_jsonl(self.output / "analysis/claims.reviewed.jsonl", [self.claim])
        FR.atomic_write_json(self.output / "qa/crawl_audit.json", {
            "status": "PASS", "profiles": [{"uid": "12345", "platform": "futu"}],
            "streams": [{"profile_uid": "12345", "platform": "futu", "stream": stream,
                         "complete_for_request": True} for stream in ("all", "columns")],
            "skip_media": True,
        })
        self.csv("US.ALPH.csv", self.bars(count))
        self.csv("GSPC.csv", self.bars(count, 200))
        return FR.market(argparse.Namespace(output=str(self.output), refresh_market=False))

    def test_csv_invalid_prices_and_conflicting_dates_fail_without_partial_rows(self):
        for field, value in (("close", -1), ("open", 0), ("high", 99), ("low", 102),
                             ("close", "NaN"), ("volume", -1)):
            with self.subTest(field=field, value=value):
                bars = self.bars(2)
                bars[1][field] = value
                result, error = FR.load_market_csv(self.csv("invalid.csv", bars))
                self.assertEqual(result, [])
                self.assertTrue(error)
        original = self.bars(1)[0]
        result, error = FR.load_market_csv(self.csv("conflict.csv", [original, dict(original, volume=2000)]))
        self.assertEqual(result, [])
        self.assertIn("Conflicting", error)
        result, error = FR.load_market_csv(self.csv("duplicate.csv", [original, original]))
        self.assertIsNone(error)
        self.assertEqual(len(result), 1)

    def test_csv_adjusted_close_scales_ohlc_together(self):
        bars = [dict(self.bars(1)[0], open=100, high=110, low=90, close=100, **{"adj close": 50})]
        rows, error = FR.load_market_csv(self.csv("adjusted.csv", bars))
        self.assertIsNone(error)
        for key, expected in zip(("open", "high", "low", "close"), (50, 55, 45, 50)):
            self.assertAlmostEqual(rows[0][key], expected, places=12)

    def test_adjusted_extrema_preserve_equality_and_reject_real_source_violations(self):
        raw, adjusted = 105.46, 53.69626
        for invalid in (None, "high", "low"):
            prices = dict(open=raw, high=raw, low=raw, close=raw)
            if invalid == "high":
                prices["high"] = math.nextafter(raw, 0)
            elif invalid == "low":
                prices["low"] = math.nextafter(raw, math.inf)
            csv_row = dict(self.bars(1)[0], **prices, **{"adj close": adjusted})
            rows, error = FR.load_market_csv(self.csv("adjusted-extremum.csv", [csv_row]))
            payload = {"chart": {"result": [{"timestamp": [1735776000], "indicators": {
                "quote": [{key: [value] for key, value in prices.items()}],
                "adjclose": [{"adjclose": [adjusted]}]}}]}}
            with self.subTest(invalid=invalid):
                if invalid is None:
                    self.assertIsNone(error)
                    yahoo = FR.load_price_bars(payload)
                    for row in (rows[0], yahoo[0]):
                        self.assertEqual([row[key] for key in ("open", "high", "low", "close")], [adjusted]*4)
                else:
                    self.assertEqual(rows, [])
                    self.assertIsNotNone(error)
                    with self.assertRaises(FR.ResearchError):
                        FR.load_price_bars(payload)

    def test_eastmoney_invalid_data_envelope_falls_back_to_cached_yahoo(self):
        market_dir = self.output / "analysis/market"
        cache = market_dir / "raw"
        yahoo = {"chart": {"result": [{"meta": {"symbol": "ALPH", "currency": "USD"},
            "timestamp": [1735776000], "indicators": {"quote": [{"open": [100],
            "high": [102], "low": [98], "close": [101], "volume": [1000]}]}}]}}
        FR.atomic_write_json(cache / "ALPH.yahoo.json", yahoo)
        for invalid in ([1], None, "bad", 123):
            for secid in FR.eastmoney_secids("US.ALPH", "ALPH"):
                name = f"ALPH.{FR.safe_market_filename(secid)}.eastmoney.json"
                FR.atomic_write_json(cache / name, {"data": invalid})
            with self.subTest(data=invalid):
                rows, error, source = FR.fetch_price_history("US.ALPH", "ALPH", datetime(2025, 1, 1),
                    datetime(2025, 1, 4), market_dir, False)
                self.assertIsNone(error)
                self.assertEqual(source, "yahoo")
                self.assertEqual(rows[0]["close"], 101)

    def test_partial_adjustment_or_broken_daily_arrays_do_not_change_the_horizon(self):
        bars = [dict(row, **{"adj close": 50 if i == 0 else ""}) for i, row in enumerate(self.bars(2))]
        rows, error = FR.load_market_csv(self.csv("partial-adjustment.csv", bars))
        self.assertEqual(rows, [])
        self.assertIn("mixes", error)
        payload = {"chart": {"result": [{"timestamp": [1735776000, 1735862400], "indicators": {
            "quote": [{"open": [100, 100], "close": [101]}]}}]}}
        with self.assertRaisesRegex(FR.ResearchError, "Incomplete"):
            FR.load_price_bars(payload)

    def test_jsonl_nonobjects_and_nonfinite_values_are_not_silently_skipped(self):
        path = self.output / "claims.jsonl"
        for invalid in ('null', '[]', '"not-a-claim"', '{"metric": NaN}'):
            path.write_text('{}\n' + invalid + '\n')
            with self.assertRaisesRegex(FR.ResearchError, "Invalid JSONL"):
                FR.read_jsonl(path)

    def test_csv_mixed_or_wrong_currency_never_falls_through_to_network(self):
        for currencies in (("USD", "HKD"), ("HKD", "HKD")):
            bars = [dict(row, currency=currencies[i]) for i, row in enumerate(self.bars(2))]
            self.csv("US.ALPH.csv", bars)
            data, error, source = FR.fetch_price_history("US.ALPH", "ALPH", datetime(2024, 1, 1),
                datetime(2026, 1, 1), self.output / "analysis/market", False)
            self.assertEqual(data, [])
            self.assertTrue(error)
            self.assertIsNone(source)

    def test_eastmoney_and_yahoo_reject_nonfinite_or_impossible_prices(self):
        for close in (-1, 0, float("nan"), True):
            with self.subTest(close=close):
                with self.assertRaises(FR.ResearchError):
                    FR.parse_eastmoney_bars({"data": {"klines": [f"2025-01-02,100,{close},102,98,1000"]}})
                payload = {"chart": {"result": [{"timestamp": [1735776000], "indicators": {
                    "quote": [{"open": [100], "high": [102], "low": [98], "close": [close], "volume": [1000]}]}}]}}
                with self.assertRaises(FR.ResearchError):
                    FR.load_price_bars(payload)

    def test_yahoo_wrong_symbol_or_currency_is_not_accepted(self):
        for meta in ({"symbol": "BETA", "currency": "USD"}, {"symbol": "ALPH", "currency": "HKD"}):
            payload = {"chart": {"result": [{"meta": meta, "timestamp": [1735776000], "indicators": {
                "quote": [{"open": [100], "high": [102], "low": [98], "close": [101], "volume": [1000]}]}}]}}
            path = self.output / "cached.json"
            FR.atomic_write_json(path, payload)
            rows, error = FR.fetch_yahoo_history("ALPH", datetime(2025, 1, 1), datetime(2025, 1, 4), path, False)
            self.assertEqual(rows, [])
            self.assertIn("does not match", error)

    def test_excess_return_uses_identical_dates_despite_missing_internal_session(self):
        bars = self.bars()
        reference = FR.compute_market_row(self.claim, "ALPH", bars)
        target = reference["evaluation_close_20_date"]
        benchmark = self.bars(price=200)
        benchmark = [row for row in benchmark if row["date"] != "2025-01-15"]
        for row in benchmark:
            if row["date"] == target:
                row.update(close=220, high=221)
        result = FR.compute_market_row(self.claim, "ALPH", bars, "^GSPC", benchmark)
        self.assertAlmostEqual(result["excess_ret_20"], .01 - .10)
        self.assertEqual(result["benchmark_status"], "calculated_same_dates")
        benchmark = [row for row in benchmark if row["date"] != target]
        missing = FR.compute_market_row(self.claim, "ALPH", bars, "^GSPC", benchmark)
        self.assertIsNone(missing["excess_ret_20"])
        self.assertEqual(missing["benchmark_status"], "missing_endpoints")

    def test_incomplete_horizons_do_not_become_full_window_statistics(self):
        bars = self.bars(45)
        result = FR.compute_market_row(self.claim, "ALPH", bars)
        self.assertIsNotNone(result["ret_1"])
        self.assertIsNone(result["ret_20"])
        self.assertIsNone(result["mfe_20"])
        self.assertIsNone(result["mae_20"])
        self.assertIsNone(result["close_vs_ma60"])
        self.assertEqual(result["missing_reason"], "incomplete_forward_20")
        sparse = FR.compute_market_row(self.claim, "ALPH", bars[-10:])
        self.assertIsNone(sparse["close_vs_ma20"])

    def test_real_csv_to_market_snapshot_report_and_audit(self):
        result = self.prepare_offline_chain()
        self.assertEqual(result["rows_with_forward_20"], 1)
        report = FR.report(argparse.Namespace(output=str(self.output)))
        self.assertEqual(report["mode"], "reviewed")
        audit = FR.audit(argparse.Namespace(output=str(self.output)))
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["publication_gate"]["market_performance_conclusion_allowed"])
        self.assertTrue((self.output / "reports/profile.md").is_file())
        rows = FR.read_jsonl(self.output / "analysis/market/claims_market.jsonl")
        self.assertEqual(rows[0]["ret_20"], .01)
        self.assertEqual(FR.market_derivation_errors(self.output, [self.claim], rows), [])

    def test_changed_or_missing_derivation_evidence_blocks_report(self):
        self.prepare_offline_chain()
        directory = self.output / "analysis/market"
        saved = {name: (directory / name).read_bytes() for name in
                 ("inputs.snapshot.json", "claims_market.jsonl", "market_manifest.json")}
        for mutation in ("snapshot", "missing_snapshot", "outcome", "missing_outcome", "rehash_outcome"):
            for name, data in saved.items():
                (directory / name).write_bytes(data)
            if mutation == "missing_snapshot":
                (directory / "inputs.snapshot.json").unlink()
            elif mutation == "snapshot":
                data = FR.read_json(directory / "inputs.snapshot.json")
                data["prices"]["ALPH"][0]["volume"] = 2000
                FR.atomic_write_json(directory / "inputs.snapshot.json", data)
            else:
                rows = FR.read_jsonl(directory / "claims_market.jsonl")
                rows[0]["ret_20"] = .99
                if mutation == "missing_outcome":
                    rows = []
                FR.write_jsonl(directory / "claims_market.jsonl", rows)
                if mutation == "rehash_outcome":
                    manifest = FR.read_json(directory / "market_manifest.json")
                    manifest["market_rows_sha256"] = FR.claim_fingerprint(rows)
                    FR.atomic_write_json(directory / "market_manifest.json", manifest)
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(FR.ResearchError, "rerun market"):
                    FR.report(argparse.Namespace(output=str(self.output)))
                audit = FR.audit(argparse.Namespace(output=str(self.output)))
                self.assertFalse(audit["publication_gate"]["market_performance_conclusion_allowed"])

    def test_stale_csv_cannot_allow_market_performance_conclusions(self):
        self.prepare_offline_chain(count=45)
        FR.report(argparse.Namespace(output=str(self.output)))
        audit = FR.audit(argparse.Namespace(output=str(self.output)))
        self.assertFalse(audit["publication_gate"]["market_performance_conclusion_allowed"])
        self.assertEqual(audit["status"], "WARN")


if __name__ == "__main__":
    unittest.main()

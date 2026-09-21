"""Offline regression tests for archive identity, chronology, and derived data."""

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
SPEC = importlib.util.spec_from_file_location("pipeline_integrity", ROOT / "elab-futu-research/scripts/futu_research.py")
FR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FR)


class PipelineIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "output"
        for name in ("request_json", "request_bytes", "_tiger_fetch_html"):
            patch = mock.patch.object(FR, name, side_effect=AssertionError("network disabled"))
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(FR.time, "sleep")
        patch.start()
        self.addCleanup(patch.stop)

    def args(self, profiles):
        return argparse.Namespace(profile=profiles, output=str(self.output), since=None,
                                  until=None, skip_media=True, media="none", detail_workers=1,
                                  media_workers=1, refresh=False, max_pages=10)

    @staticmethod
    def detail(platform, uid="12345", fid="10001"):
        if platform == "tiger":
            return {"source": "tiger", "post_id": fid, "author_uid": uid,
                    "author_name": "Synthetic Tiger", "title": "Synthetic",
                    "text": "我看多 $ALPH$", "publish_time_list": "2025-01-10"}
        return {"code": 0, "data": {"feedCommon": {"feedId": fid, "timestamp": 1736467200},
                "authorInfo": {"userId": uid, "nickName": "Synthetic Futu"},
                "moduleData": [{"data": {"text": "我看多 $ALPH$", "stockCode": "US.ALPH"}}]}}

    def test_untrusted_identifiers_are_rejected_before_writes(self):
        sentinel = Path(self.temporary.name) / "sentinel.json"
        sentinel.write_text("unchanged")
        for value in ("../../../../sentinel", "/tmp/sentinel", "..", "a/b", "a\\b", "C:payload"):
            with self.subTest(value=value):
                with self.assertRaises(FR.ResearchError):
                    FR.fetch_details("12345", [value], self.output, 1)
                with self.assertRaises(FR.ResearchError):
                    FR.fetch_details(value, ["10001"], self.output, 1)
        self.assertEqual(sentinel.read_text(), "unchanged")
        self.assertFalse(self.output.exists())

    def test_detail_and_media_reject_escaping_symlinks(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (self.output / "raw/details").mkdir(parents=True)
        (self.output / "raw/details/12345").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FR.ResearchError):
            FR.fetch_details("12345", ["10001"], self.output, 1)
        detail = self.detail("futu")
        detail["data"]["moduleData"] = [{"imageUrl": "https://example.invalid/image.png"}]
        path = self.output / "source.json"
        FR.atomic_write_json(path, detail)
        (self.output / "media/12345").mkdir(parents=True)
        (self.output / "media/12345/10001").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FR.ResearchError):
            FR.download_media("12345", [path], self.output, 1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_media_feed_identifier_cannot_escape_output(self):
        path = Path(self.temporary.name) / "detail.json"
        FR.atomic_write_json(path, self.detail("futu", fid="../../escaped"))
        with self.assertRaises(FR.ResearchError):
            FR.download_media("12345", [path], self.output, 1)

    def test_archive_directory_symlinks_cannot_delete_external_files(self):
        outside = Path(self.temporary.name) / "outside"
        (outside / "monthly").mkdir(parents=True)
        sentinel = outside / "monthly/keep.md"
        sentinel.write_text("keep")
        self.output.mkdir()
        (self.output / "archive").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FR.ResearchError):
            FR.write_archive_files(self.output, [])
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertFalse((outside / "posts.jsonl").exists())
        (self.output / "archive").unlink()
        (self.output / "archive").mkdir()
        (self.output / "archive/monthly").symlink_to(outside / "monthly", target_is_directory=True)
        with self.assertRaises(FR.ResearchError):
            FR.write_archive_files(self.output, [])
        self.assertEqual(sentinel.read_text(), "keep")

    def test_predictable_csv_temporary_symlink_is_never_followed(self):
        sentinel = Path(self.temporary.name) / "sentinel"
        sentinel.write_text("keep")
        directory = self.output / "archive"
        directory.mkdir(parents=True)
        (directory / "posts.csv.tmp").symlink_to(sentinel)
        FR.write_archive_files(self.output, [])
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertIn("feed_id", (directory / "posts.csv").read_text())

    def test_safe_legacy_detail_cache_is_reused(self):
        path = self.output / "raw/details/12345/10001.json"
        FR.atomic_write_json(path, self.detail("futu"))
        self.assertEqual(FR.fetch_details("12345", ["10001"], self.output, 1), (["10001"], []))

    def test_tiger_relative_times_use_the_original_capture_date(self):
        tiger = FR.TigerAdapter()
        for raw, expected in (("10:00", "2025-12-31T10:00:00+08:00"),
                              ("07-22 09:00", "2025-07-22T09:00:00+08:00")):
            detail = dict(self.detail("tiger"), publish_time_list=raw,
                          captured_at="2025-12-31T03:00:00+00:00")
            path = self.output / "cached.json"
            FR.atomic_write_json(path, detail)
            for year in (2026, 2027):
                class Clock(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return datetime(year, 1, 2, tzinfo=timezone.utc)
                with mock.patch.object(FR, "datetime", Clock):
                    row = tiger.normalize_post(path, "12345", ["all"], {}, tiger.profile_url("12345"))
                self.assertEqual(row["published_at"], expected)

    def test_tiger_ambiguous_legacy_time_requires_refresh(self):
        path = self.output / "legacy.json"
        FR.atomic_write_json(path, dict(self.detail("tiger"), publish_time_list="10:00"))
        with self.assertRaisesRegex(FR.ResearchError, "archive --refresh"):
            FR.TigerAdapter().normalize_post(path, "12345", ["all"], {}, "")

    def test_tiger_cached_list_uses_capture_metadata(self):
        directory = self.output / "raw/list/12345/all"
        FR.atomic_write_text(directory / "page_00001.html", '<a href="/post/10001">post</a><span class="publish-time">10:00</span>')
        FR.atomic_write_json(directory / "page_00001.metadata.json", {"captured_at": "2025-01-10T03:00:00Z"})
        FR.atomic_write_text(directory / "page_00002.html", "")
        tiger = FR.TigerAdapter()
        feeds, _ = tiger.crawl_streams_for_uid("12345", self.output, None, False, 10)[0]
        self.assertEqual(feeds["10001"]["_tiger_published_at"], "2025-01-10T10:00:00+08:00")
        self.assertEqual(tiger._build_time_map_from_cache("12345", self.output)["10001"], "2025-01-10T10:00:00+08:00")

    def archive_profiles(self, profiles):
        def crawl(adapter, uid, output, since, refresh, max_pages):
            return [({"10001": {"feed_comm": {"feed_id": "10001", "timestamp": 1736467200}}},
                     {"profile_uid": uid, "stream": label, "terminal_reason": "has_more_zero",
                      "complete_for_request": True}) for label in adapter.expected_streams]

        def fetch(adapter, uid, ids, output, workers):
            for fid in ids:
                FR.atomic_write_json(output / "raw/details" / uid / f"{fid}.json", self.detail(adapter.name, uid, fid))
            return list(ids), []

        with mock.patch.object(FR.FutuAdapter, "crawl_streams_for_uid", crawl), \
             mock.patch.object(FR.TigerAdapter, "crawl_streams_for_uid", crawl), \
             mock.patch.object(FR.FutuAdapter, "fetch_posts", fetch), \
             mock.patch.object(FR.TigerAdapter, "fetch_posts", fetch):
            return FR.archive(self.args(profiles))

    def test_same_uid_and_post_id_on_two_platforms_stay_separate(self):
        result = self.archive_profiles(["https://q.futunn.com/profile/12345", "https://www.laohu8.com/personal/12345/"])
        self.assertEqual(result["status"], "PASS")
        posts = FR.read_jsonl(self.output / "archive/posts.jsonl")
        self.assertEqual({FR.profile_key(row) for row in posts}, {"futu:12345", "tiger:12345"})
        self.assertTrue((self.output / "raw/details/12345/10001.json").exists())
        self.assertTrue((self.output / "platforms/tiger/raw/details/12345/10001.json").exists())
        FR.prepare(argparse.Namespace(output=str(self.output)))
        candidates = FR.read_jsonl(self.output / "analysis/candidates.jsonl")
        self.assertEqual(len({row["candidate_id"] for row in candidates}), len(candidates))
        result = FR.report(argparse.Namespace(output=str(self.output)))
        self.assertEqual(result["profiles"], 2)
        audited = FR.audit(argparse.Namespace(output=str(self.output)))
        self.assertTrue(audited["publication_gate"]["data_chain_passed"])

    def test_later_futu_capture_preserves_cached_tiger_records(self):
        self.archive_profiles(["https://www.laohu8.com/personal/12345/"])
        result = self.archive_profiles(["https://q.futunn.com/profile/12345"])
        self.assertEqual(result["status"], "PASS")
        posts = FR.read_jsonl(self.output / "archive/posts.jsonl")
        self.assertEqual(len(posts), 2)
        self.assertEqual({FR.profile_key(row) for row in posts}, {"futu:12345", "tiger:12345"})
        result = FR.audit(argparse.Namespace(output=str(self.output)))
        self.assertTrue(result["publication_gate"]["data_chain_passed"])

    def test_legacy_tiger_cache_migrates_using_recorded_source(self):
        detail = self.detail("tiger")
        FR.atomic_write_json(self.output / "raw/details/12345/10001.json", detail)
        FR.atomic_write_json(self.output / "raw/feed_index.json", {"12345:10001": {
            "uid": "12345", "feed_id": "10001", "timestamp": 1736467200,
            "profile_url": "https://www.laohu8.com/personal/12345/", "stream_membership": ["all"]}})
        migrated = FR.load_capture_index(self.output)
        self.assertEqual(migrated["tiger:12345:10001"]["platform"], "tiger")
        self.assertEqual(FR.read_json(self.output / "platforms/tiger/raw/details/12345/10001.json"), detail)

    def test_legacy_claim_platform_requires_unambiguous_source(self):
        claim = {"author_uid": "12345", "feed_id": "10001"}
        tiger = {"profile_uid": "12345", "feed_id": "10001", "platform": "tiger"}
        resolved = FR.resolve_claim_platforms([claim], [tiger])
        self.assertEqual(resolved[0]["platform"], "tiger")
        self.assertNotIn("platform", claim)
        with self.assertRaisesRegex(FR.ResearchError, "ambiguous platform"):
            FR.resolve_claim_platforms([claim], [tiger, dict(tiger, platform="futu")])

    def test_corrupt_capture_index_is_not_silently_replaced(self):
        path = self.output / "raw/feed_index.json"
        FR.atomic_write_text(path, "incomplete JSON")
        with self.assertRaisesRegex(FR.ResearchError, "restore or regenerate"):
            FR.load_capture_index(self.output)
        self.assertEqual(path.read_text(), "incomplete JSON")

    def reviewed_pipeline(self):
        self.archive_profiles(["https://q.futunn.com/profile/12345"])
        FR.prepare(argparse.Namespace(output=str(self.output)))
        claim = FR.read_jsonl(self.output / "analysis/candidates.jsonl")[0]
        claim.update(claim_id="reviewed-1", direction="bullish", evidence_level="C")
        FR.write_jsonl(self.output / "analysis/claims.reviewed.jsonl", [claim])
        start = datetime(2024, 12, 1, tzinfo=timezone.utc)
        bars = [{"date": (start + timedelta(days=i)).date().isoformat(), "open": 100+i,
                 "high": 102+i, "low": 99+i, "close": 101+i, "volume": 1000} for i in range(150)]
        with mock.patch.object(FR, "fetch_price_history", return_value=(bars, None, "synthetic")):
            FR.market(argparse.Namespace(output=str(self.output), refresh_market=False))
        return claim

    def test_changed_frozen_claim_blocks_report_and_publication(self):
        claim = self.reviewed_pipeline()
        self.assertEqual(FR.audit(argparse.Namespace(output=str(self.output)))["status"], "PASS")
        for field, replacement in (("direction", "bearish"), ("symbol_raw", "US.BETA"),
                                   ("published_at", "2025-01-20T10:00:00+08:00"), ("author_uid", "54321")):
            changed = dict(claim, **{field: replacement})
            FR.write_jsonl(self.output / "analysis/claims.reviewed.jsonl", [changed])
            with self.subTest(field=field):
                with self.assertRaisesRegex(FR.ResearchError, "rerun market"):
                    FR.report(argparse.Namespace(output=str(self.output)))
                result = FR.audit(argparse.Namespace(output=str(self.output)))
                self.assertEqual(result["status"], "FAIL")
                self.assertFalse(result["publication_gate"]["public_comparative_conclusion_allowed"])
                self.assertFalse(result["publication_gate"]["market_performance_conclusion_allowed"])

    def test_legacy_unbound_market_rows_require_regeneration(self):
        self.reviewed_pipeline()
        path = self.output / "analysis/market/claims_market.jsonl"
        rows = FR.read_jsonl(path)
        rows[0].pop("claim_sha256")
        FR.write_jsonl(path, rows)
        with self.assertRaisesRegex(FR.ResearchError, "rerun market"):
            FR.report(argparse.Namespace(output=str(self.output)))
        self.assertEqual(FR.audit(argparse.Namespace(output=str(self.output)))["status"], "FAIL")

    def test_market_calculation_version_is_recorded_for_all_outputs(self):
        claim = self.reviewed_pipeline()
        market = self.output / "analysis/market"
        for unresolved in (False, True):
            with self.subTest(unresolved=unresolved):
                if unresolved:
                    FR.atomic_write_json(self.output / "analysis/symbol_overrides.json", {claim["symbol_raw"]: ""})
                    FR.market(argparse.Namespace(output=str(self.output), refresh_market=False))
                rows = FR.read_jsonl(market / "claims_market.jsonl")
                self.assertEqual(rows[0]["market_calculation_version"], FR.MARKET_CALCULATION_VERSION)
                self.assertEqual(bool(rows[0]["missing_reason"] == "unresolved_symbol"), unresolved)
                with (market / "claims_market.csv").open(newline="", encoding="utf-8") as handle:
                    exported = list(csv.DictReader(handle))
                self.assertEqual(exported[0]["market_calculation_version"], FR.MARKET_CALCULATION_VERSION)
                manifest = FR.read_json(market / "market_manifest.json")
                self.assertEqual(manifest["market_calculation_version"], FR.MARKET_CALCULATION_VERSION)

    def test_outdated_market_calculation_blocks_report_and_publication(self):
        claim = self.reviewed_pipeline()
        path = self.output / "analysis/market/claims_market.jsonl"
        original = FR.read_jsonl(path)[0]
        self.assertEqual(original["claim_sha256"], FR.claim_fingerprint(claim))
        for version in (None, "legacy"):
            with self.subTest(version=version):
                row = dict(original)
                if version is None:
                    row.pop("market_calculation_version")
                else:
                    row["market_calculation_version"] = version
                FR.write_jsonl(path, [row])
                with self.assertRaisesRegex(FR.ResearchError, "calculation version.*rerun market"):
                    FR.report(argparse.Namespace(output=str(self.output)))
                result = FR.audit(argparse.Namespace(output=str(self.output)))
                self.assertEqual(result["status"], "FAIL")
                self.assertFalse(result["publication_gate"]["public_comparative_conclusion_allowed"])
                self.assertFalse(result["publication_gate"]["market_performance_conclusion_allowed"])

    def test_duplicate_claim_and_market_ids_are_rejected(self):
        claim = {"claim_id": "same", "author_uid": "12345", "direction": "bullish"}
        row = {"claim_id": "same", "claim_sha256": FR.claim_fingerprint(claim),
               "market_calculation_version": FR.MARKET_CALCULATION_VERSION}
        self.assertEqual(FR.market_binding_errors([claim], [row]), [])
        self.assertTrue(FR.market_binding_errors([claim, claim], [row]))
        self.assertTrue(FR.market_binding_errors([claim], [row, row]))

    def test_market_benchmarks_follow_canonical_market(self):
        for raw in ("HK.00700", "00700", "00700.HK", "0700.HK"):
            self.assertEqual(FR.benchmark_for(raw), "^HSI")
        for raw in ("SH.600000", "600000.SH", "SZ.000001", "000001.SZ"):
            self.assertEqual(FR.benchmark_for(raw), "000001.SS")
        self.assertEqual(FR.benchmark_for("US.ALPH"), "^GSPC")

    def test_binomial_probability_is_stable_for_large_samples(self):
        for total, successes in ((20, 2), (101, 30), (1100, 500), (2000, 900)):
            tail = min(successes, total-successes)
            expected = min(1.0, 2 * sum(math.comb(total, i) for i in range(tail+1)) / (1 << total))
            actual = FR.binomial_two_sided_pvalue(successes, total)
            self.assertAlmostEqual(actual, expected, delta=max(1e-14, expected * 1e-9))
            self.assertAlmostEqual(actual, FR.binomial_two_sided_pvalue(total-successes, total))
        self.assertEqual(FR.binomial_two_sided_pvalue(1000, 2000), 1.0)


if __name__ == "__main__":
    unittest.main()

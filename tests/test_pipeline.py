#!/usr/bin/env python3
"""Offline end-to-end tests with fictional Futu-shaped fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "elab-futu-research" / "scripts" / "futu_research.py"
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_api.json"
SPEC = importlib.util.spec_from_file_location("futu_research", SCRIPT)
assert SPEC and SPEC.loader
FR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FR)


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def fake_request_json(self, url, params=None, attempts=4):
        params = params or {}
        if url == FR.LIST_URL:
            stream = str(params["type"])
            page = "first" if int(params["load_list_type"]) == 2 else "next"
            return self.fixture["list_pages"][f"{stream}:{page}"]
        if url == FR.DETAIL_URL:
            return self.fixture["details"][str(params["feedId"])]
        raise AssertionError(f"Unexpected URL in offline test: {url}")

    @staticmethod
    def synthetic_bars():
        start = datetime(2024, 12, 1, tzinfo=timezone.utc)
        rows = []
        for index in range(260):
            stamp = start + timedelta(days=index)
            price = 80.0 + index * 0.2
            rows.append(
                {
                    "date": stamp.date().isoformat(),
                    "timestamp": int(stamp.timestamp()),
                    "open": price,
                    "high": price * 1.02,
                    "low": price * 0.98,
                    "close": price * 1.005,
                    "volume": 1000.0 + index,
                }
            )
        return rows

    def test_parse_uid(self):
        uid = self.fixture["uid"]
        self.assertEqual(FR.parse_uid(uid), uid)
        self.assertEqual(FR.parse_uid(f"https://q.futunn.com/profile/{uid}?lang=zh-cn"), uid)
        with self.assertRaises(FR.ResearchError):
            FR.parse_uid("not-a-profile")

    def test_offline_end_to_end(self):
        uid = self.fixture["uid"]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "research-output"
            archive_args = argparse.Namespace(
                profile=[f"https://q.futunn.com/profile/{uid}"],
                since=None,
                until=None,
                output=str(output),
                skip_media=True,
                detail_workers=2,
                media_workers=2,
                max_pages=20,
                refresh=False,
            )
            with mock.patch.object(FR, "request_json", side_effect=self.fake_request_json):
                crawl = FR.archive(archive_args)
            self.assertEqual(crawl["status"], "PASS")
            self.assertEqual(crawl["visible_history_status"], "complete_visible_history")
            posts = FR.read_jsonl(output / "archive" / "posts.jsonl")
            self.assertEqual(len(posts), 4)
            self.assertEqual(sum(bool(row["is_column"]) for row in posts), 1)
            self.assertEqual(sum(bool(row["is_repost"]) for row in posts), 1)
            self.assertTrue(any("all" in row["stream_membership"] for row in posts))
            self.assertTrue(any("columns" in row["stream_membership"] for row in posts))

            summary = FR.prepare(argparse.Namespace(output=str(output)))
            self.assertGreaterEqual(summary["candidates"], 3)
            candidates = FR.read_jsonl(output / "analysis" / "candidates.jsonl")
            buy_candidate = next(
                row for row in candidates if row["feed_id"] == "SYNTH-POST-001"
            )
            self.assertEqual(buy_candidate["evidence_prelabel"], "B")
            self.assertEqual(buy_candidate["symbol_raw"], "US.ALPH")

            reviewed = {
                "schema_version": "1.0",
                "claim_id": "SYNTH-CLAIM-001",
                "candidate_id": buy_candidate["candidate_id"],
                "feed_id": buy_candidate["feed_id"],
                "author_uid": uid,
                "published_at": buy_candidate["published_at"],
                "symbol_raw": "US.ALPH",
                "direction": "bullish",
                "action": "buy",
                "horizon": "weeks",
                "evidence_level": "B",
                "evidence_span": buy_candidate["evidence_span"],
                "image_evidence_paths": [],
                "image_evidence_verified": False,
                "conditions": ["跌破计划线"],
                "invalidation": ["跌破计划线"],
                "sizing_rule": "不超过试验账户的一成",
                "risk_rule": "跌破计划线止损",
                "exit_rule": None,
                "confidence": "high",
                "ambiguities": [],
                "reviewer": "human",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
            FR.write_jsonl(output / "analysis" / "claims.reviewed.jsonl", [reviewed])
            market_args = argparse.Namespace(output=str(output), refresh_market=False)
            with mock.patch.object(
                FR,
                "fetch_price_history",
                return_value=(self.synthetic_bars(), None, "synthetic"),
            ):
                market_summary = FR.market(market_args)
            self.assertEqual(market_summary["mode"], "reviewed")
            self.assertEqual(market_summary["rows_with_forward_20"], 1)

            report_summary = FR.report(argparse.Namespace(output=str(output)))
            self.assertEqual(report_summary["mode"], "reviewed")
            result = FR.audit(argparse.Namespace(output=str(output)))
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["publication_gate"]["data_chain_passed"])
            self.assertTrue((output / "reports" / "profile.md").exists())
            self.assertTrue((output / "qa" / "adversarial_audit.json").exists())
            # F1/F4: report() must auto-create archive/by-author/index.md
            self.assertTrue(
                (output / "archive" / "by-author" / "index.md").exists(),
                "report() must auto-create archive/by-author/index.md",
            )
            # Verify report footer credit and disclaimer are present in all report files
            for report_name in ("profile.md", "capability_matrix.md", "rule_cards.md"):
                report_text = (output / "reports" / report_name).read_text(encoding="utf-8")
                self.assertIn(
                    "elab-futu-research",
                    report_text,
                    msg=f"footer credit missing from {report_name}",
                )
                self.assertIn(
                    "不构成任何投资建议",
                    report_text,
                    msg=f"disclaimer missing from {report_name}",
                )

    def test_market_time_freeze(self):
        bars = self.synthetic_bars()
        claim = {
            "claim_id": "SYNTH-TIME-001",
            "feed_id": "SYNTH-POST-001",
            "author_uid": self.fixture["uid"],
            "published_at": "2025-05-09T08:00:00+08:00",
            "symbol_raw": "US.ALPH",
            "direction": "bullish",
        }
        row = FR.compute_market_row(claim, "ALPH", bars)
        self.assertLess(row["context_cutoff"], "2025-05-09")
        self.assertGreater(row["evaluation_open_date"], "2025-05-09")
        self.assertIsNotNone(row["ret_20"])
        self.assertEqual(row["directional_ret_20"], row["ret_20"])
        bearish = dict(claim)
        bearish["claim_id"] = "SYNTH-TIME-002"
        bearish["direction"] = "bearish"
        bearish_row = FR.compute_market_row(bearish, "ALPH", bars)
        self.assertAlmostEqual(
            bearish_row["directional_ret_20"], -bearish_row["ret_20"]
        )
        self.assertGreaterEqual(bearish_row["mfe_20"], 0)
        self.assertLessEqual(bearish_row["mae_20"], 0)

    def test_conservative_prelabels_and_symbol_mapping(self):
        self.assertEqual(FR.yahoo_symbol("HK.00700", {}), "0700.HK")
        self.assertEqual(FR.yahoo_symbol("US.BRK.B", {}), "BRK-B")
        direction, _ = FR.detect_direction("我今天卖出一部分，锁定已有利润。", "sell")
        self.assertEqual(direction, "unclear")
        direction, _ = FR.detect_direction("我开空，因为估值偏高。", "short")
        self.assertEqual(direction, "bearish")
        adjusted = FR.benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.20})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        eastmoney = {
            "data": {
                "klines": [
                    "2025-01-02,10.0,10.5,10.8,9.9,1000,0,0,0,0,0",
                    "2025-01-03,10.5,10.2,10.7,10.0,1100,0,0,0,0,0"
                ]
            }
        }
        bars = FR.parse_eastmoney_bars(eastmoney)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["open"], 10.0)
        self.assertEqual(bars[1]["close"], 10.2)


    def test_repost_attribution(self):
        """Repost posts must set is_repost=True and split own comment from original text."""
        uid = self.fixture["uid"]
        repost_detail = self.fixture["details"]["SYNTH-REPOST-001"]
        with tempfile.TemporaryDirectory() as temporary:
            detail_path = Path(temporary) / "SYNTH-REPOST-001.json"
            detail_path.write_text(
                json.dumps(repost_detail, ensure_ascii=False), encoding="utf-8"
            )
            record = FR.normalize_detail(
                detail_path,
                uid,
                ["all"],
                {},
                f"https://q.futunn.com/profile/{uid}",
            )
        # Core repost flag
        self.assertTrue(record["is_repost"], "Repost detection must set is_repost=True")
        self.assertFalse(record["is_original_author"])
        # Own comment is isolated in text
        self.assertIn(
            "虚构评论：看了一下，有参考价值。",
            record["text"],
            msg="Author's own comment must appear in text",
        )
        # Original post content in original_text, NOT in text
        self.assertIsNotNone(record["original_text"])
        self.assertIn(
            "虚构官方帖",
            record["original_text"],
            msg="Original post text must appear in original_text",
        )
        self.assertNotIn(
            "虚构官方帖",
            record["text"],
            msg="Original post text must NOT bleed into text field",
        )
        # Title uses own comment, not the original post content
        self.assertNotIn(
            "虚构官方帖",
            record["title"],
            msg="Title must not be derived from repost content",
        )


    def test_media_url_extraction(self):
        """extract_media_urls must handle nested orgPic/bigPic/thumbPic dict structure.

        Before v1.1.0 the function checked isinstance(child, str) for URL_MEDIA_KEYS;
        real Futu data wraps image URLs in {url, width, height} dicts so the old code
        produced zero jobs silently.
        """
        # ------------------------------------------------------------------
        # Case 1: full pictureItem with all three quality levels inside _original
        #   Expected: orgPic collected; bigPic skipped (priority); thumbPic skipped always
        # ------------------------------------------------------------------
        detail_full = {
            "moduleData": [
                {
                    "type": 1,
                    "_original": {
                        "stockIds": [],
                        "orgPic": {
                            "url": "https://img.example.com/photo-SYNTH.jpg",
                            "width": 1062,
                            "height": 1530,
                        },
                        "bigPic": {
                            "url": "https://img.example.com/photo-SYNTH.jpg/bigversion",
                            "width": 800,
                            "height": 600,
                        },
                        "thumbPic": {
                            "url": "https://img.example.com/photo-SYNTH.jpg/thumbversion",
                            "width": 200,
                            "height": 150,
                        },
                        "picDescription": "",
                    },
                }
            ]
        }
        urls_full = FR.extract_media_urls(detail_full)
        url_set_full = {item["url"] for item in urls_full}

        self.assertIn(
            "https://img.example.com/photo-SYNTH.jpg",
            url_set_full,
            msg="orgPic (original quality) must be collected from nested dict structure",
        )
        self.assertNotIn(
            "https://img.example.com/photo-SYNTH.jpg/bigversion",
            url_set_full,
            msg="bigPic must be excluded when orgPic is present (priority logic)",
        )
        self.assertNotIn(
            "https://img.example.com/photo-SYNTH.jpg/thumbversion",
            url_set_full,
            msg="thumbPic must never be collected regardless of availability",
        )

        # ------------------------------------------------------------------
        # Case 2: bigPic fallback — orgPic absent; bigPic must be collected
        # ------------------------------------------------------------------
        detail_no_orgpic = {
            "moduleData": [
                {
                    "type": 1,
                    "_original": {
                        "bigPic": {
                            "url": "https://img.example.com/fallback-SYNTH.jpg/bigversion",
                            "width": 800,
                            "height": 600,
                        },
                        "thumbPic": {
                            "url": "https://img.example.com/fallback-SYNTH.jpg/thumbversion",
                            "width": 200,
                            "height": 150,
                        },
                    },
                }
            ]
        }
        urls_fallback = FR.extract_media_urls(detail_no_orgpic)
        url_set_fallback = {item["url"] for item in urls_fallback}

        self.assertIn(
            "https://img.example.com/fallback-SYNTH.jpg/bigversion",
            url_set_fallback,
            msg="bigPic must be collected as fallback when orgPic is absent",
        )
        self.assertNotIn(
            "https://img.example.com/fallback-SYNTH.jpg/thumbversion",
            url_set_fallback,
            msg="thumbPic must not be collected even as last-resort fallback",
        )

        # ------------------------------------------------------------------
        # Case 3: dict-valued display / preview keys at module level
        #   Verifies the elif normalized in URL_MEDIA_KEYS and isinstance(child, dict) branch
        # ------------------------------------------------------------------
        detail_display = {
            "moduleData": [
                {
                    "type": 1,
                    "display": {
                        "url": "https://img.example.com/display-SYNTH.jpg",
                        "width": 392,
                        "height": 225,
                    },
                }
            ]
        }
        urls_display = FR.extract_media_urls(detail_display)
        url_set_display = {item["url"] for item in urls_display}

        self.assertIn(
            "https://img.example.com/display-SYNTH.jpg",
            url_set_display,
            msg="dict-valued display key must be collected via .url extraction",
        )


    # ------ F5: version ------
    def test_version_string(self):
        """VERSION constant must match the elab-skills integration release."""
        skill = (ROOT / "elab-futu-research" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f'  version: "{FR.VERSION}"', skill)
        self.assertIn(f"elab-futu-research/{FR.VERSION} ", FR.USER_AGENT)

    # ------ F1: OSError in main exits 2 cleanly ------
    def test_output_file_path_exits_cleanly(self):
        """When --output points to an existing file, exit 2 with ERROR, no traceback (F1)."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                result = FR.main(
                    ["archive", "--profile", "12345",
                     "--since", "2026-07-22",
                     "--output", tmp_file.name]
                )
            err_text = mock_err.getvalue()
        self.assertEqual(result, 2, "exit code must be 2 for OSError")
        self.assertIn("ERROR", err_text, "stderr must contain ERROR prefix")
        self.assertNotIn("Traceback", err_text, "raw traceback must not appear in stderr")

    # ------ F2: zero posts note ------
    def test_archive_zero_posts_note(self):
        """Archive with 0 posts must log a note suggesting UID verification (F2)."""
        uid = "99999999"
        _empty_audit = {
            "profile_uid": uid,
            "stream": "all",
            "feed_type": 301,
            "pages_saved": 1,
            "unique_feed_ids": 0,
            "terminal_reason": "has_more_zero",
            "complete_for_request": True,
            "pages": [],
            "errors": [],
        }
        _empty_audit2 = dict(_empty_audit, stream="columns", feed_type=302)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            archive_args = argparse.Namespace(
                profile=[uid],
                since=None,
                until=None,
                output=str(output),
                skip_media=True,
                detail_workers=2,
                media_workers=2,
                max_pages=20,
                refresh=False,
            )
            with mock.patch.object(FR, "crawl_stream",
                                   side_effect=[({}, _empty_audit), ({}, _empty_audit2)]):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                    FR.archive(archive_args)
                stdout_text = mock_out.getvalue()
        self.assertIn("0 posts returned", stdout_text,
                      "zero-posts note must appear in stdout when posts==0")
        self.assertIn("verify the uid", stdout_text.lower(),
                      "note must suggest UID verification")

    # ------ F3: doctor PARTIAL without profile ------
    def test_doctor_partial_without_profile(self):
        """doctor without --profile must report PARTIAL status (F3)."""
        args = argparse.Namespace(output=None, profile=None)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = FR.doctor(args)
        self.assertEqual(result["status"], "PARTIAL",
                         "doctor without profile must return PARTIAL, not PASS")
        self.assertIn("note", result, "PARTIAL result must include a note field")

    # ------ F4: ZoneInfo fallback ------
    def test_zoneinfo_fallback(self):
        """_resolve_cn_tz must fall back to UTC+8 when ZoneInfo is unavailable (F4)."""
        import datetime as _dt
        # Setting sys.modules["zoneinfo"] = None causes ImportError on 'from zoneinfo import ...'
        with mock.patch.dict("sys.modules", {"zoneinfo": None}):
            tz = FR._resolve_cn_tz()
        dt = _dt.datetime(2025, 6, 15, 12, 0, tzinfo=tz)
        self.assertEqual(dt.utcoffset(), _dt.timedelta(hours=8),
                         "fallback timezone must be exactly UTC+8")

    # ------ F5: bare 5-digit HK code ------
    def test_hk_bare_5digit_symbol_mapping(self):
        """Bare 5-digit numeric symbol maps same as HK.-prefixed form (F5)."""
        # 5-digit bare HK code must equal HK.-prefixed mapping
        self.assertEqual(
            FR.yahoo_symbol("07709", {}),
            FR.yahoo_symbol("HK.07709", {}),
            "yahoo_symbol('07709') must equal yahoo_symbol('HK.07709')",
        )
        # 6-digit (A-share territory like SK Hynix) must not be treated as HK
        self.assertIsNone(
            FR.yahoo_symbol("000660", {}),
            "6-digit numeric must not be mapped as HK code",
        )
        # 3-digit must not trigger HK rule
        self.assertIsNone(
            FR.yahoo_symbol("700", {}),
            "3-digit numeric must not be mapped as HK code",
        )

    # ------ F6: footer brand ------
    def test_report_footer_edgelab_credit(self):
        """REPORT_FOOTER must include EdgeLab brand credit (F6)."""
        self.assertIn(
            "杰尼马（EdgeLab）",
            FR.REPORT_FOOTER,
            "REPORT_FOOTER must contain '杰尼马（EdgeLab）'",
        )

    # ------ F7: empty directory guidance ------
    def test_empty_dir_report_exits_cleanly(self):
        """report on empty dir must exit 2 with archive guidance (F7)."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                result = FR.main(["report", "--output", tmp])
            err_text = mock_err.getvalue()
        self.assertEqual(result, 2, "report on empty dir must exit 2")
        self.assertIn("archive", err_text.lower(),
                      "error message must mention 'archive'")

    def test_empty_dir_market_exits_cleanly(self):
        """market on empty dir must exit 2 mentioning both archive and prepare (F7)."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                result = FR.main(["market", "--output", tmp])
            err_text = mock_err.getvalue()
        self.assertEqual(result, 2, "market on empty dir must exit 2")
        self.assertIn("archive", err_text.lower(),
                      "error message must mention 'archive'")
        self.assertIn("prepare", err_text.lower(),
                      "error message must mention 'prepare' (candidates.jsonl is prepare output)")

    def test_empty_dir_audit_exits_cleanly(self):
        """audit on empty dir must exit 2 with archive guidance (F7)."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                result = FR.main(["audit", "--output", tmp])
            err_text = mock_err.getvalue()
        self.assertEqual(result, 2, "audit on empty dir must exit 2")
        self.assertIn("archive", err_text.lower(),
                      "error message must mention 'archive'")


    # ------ F1: evidence media mode ------

    def _make_detail(self, feed_id, text, has_image=False, is_repost=False):
        """Helper: build a minimal synthetic detail envelope."""
        module_data_entry: dict = {"data": {"text": text}}
        if has_image:
            module_data_entry["data"]["orgPic"] = {
                "url": f"https://img.example.com/{feed_id}.jpg",
                "width": 800,
                "height": 600,
            }
        detail: dict = {
            "feedCommon": {
                "feedId": feed_id,
                "timestamp": 1746748800,
                "feedType": 3,
            },
            "feedTitle": "",
            "authorInfo": {"userId": "99999", "nickName": "Test"},
            "moduleData": [module_data_entry],
            "count": {"browse": 1, "comment": 0, "share": 0},
        }
        if is_repost:
            detail["feedModel"] = {
                "original": {
                    "richTextItems": [{"type": 0, "text": "Original content"}],
                    "pictureItems": [],
                }
            }
        return {"code": 0, "data": {"data": detail}}

    def test_media_evidence_mode_keyword_match(self):
        """evidence mode: post with evidence keyword gets media job; without keyword gets skip record."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            uid = "99999"
            detail_dir = output / "raw" / "details" / uid
            detail_dir.mkdir(parents=True, exist_ok=True)

            # Post WITH evidence keyword and image
            env1 = self._make_detail("EVID-001", "今天订单成交，买入了$AAPL$。", has_image=True)
            (detail_dir / "EVID-001.json").write_text(json.dumps(env1), encoding="utf-8")

            # Post WITHOUT evidence keyword but has image
            env2 = self._make_detail("EVID-002", "市场行情一般，继续观望。", has_image=True)
            (detail_dir / "EVID-002.json").write_text(json.dumps(env2), encoding="utf-8")

            paths = [detail_dir / "EVID-001.json", detail_dir / "EVID-002.json"]

            with mock.patch.object(
                FR, "request_bytes",
                return_value=(b"\xff\xd8\xff" + b"\x00" * 100, {"content_type": "image/jpeg"}),
            ):
                results = FR.download_media(uid, paths, output, workers=1, media_mode="evidence")

        ok_records = [r for r in results if r.get("feed_id") == "EVID-001" and r.get("status") == "ok"]
        skip_records = [r for r in results if r.get("feed_id") == "EVID-002" and r.get("status") == "skipped"]

        self.assertTrue(len(ok_records) > 0, "post with evidence keyword must have ok download record")
        self.assertTrue(len(skip_records) > 0, "post without evidence keyword must have skip record")
        self.assertIn("mode=evidence", skip_records[0].get("skip_reason", ""),
                      "skip_reason must indicate evidence mode")
        self.assertIn("matched=False", skip_records[0].get("skip_reason", ""))

    def test_media_evidence_mode_repost_skipped(self):
        """evidence mode: repost posts are always skipped even if text matches keywords."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            uid = "99999"
            detail_dir = output / "raw" / "details" / uid
            detail_dir.mkdir(parents=True, exist_ok=True)

            # Repost WITH evidence keyword
            env = self._make_detail("EVID-RPOST", "订单成交，看这个转发。", has_image=True, is_repost=True)
            (detail_dir / "EVID-RPOST.json").write_text(json.dumps(env), encoding="utf-8")

            results = FR.download_media(uid, [detail_dir / "EVID-RPOST.json"], output, workers=1, media_mode="evidence")

        skip_records = [r for r in results if r.get("status") == "skipped"]
        self.assertTrue(len(skip_records) > 0, "repost must be skipped in evidence mode")
        self.assertIn("is_repost", skip_records[0].get("skip_reason", ""))

    def test_skip_media_alias_equals_none(self):
        """--skip-media backward-compat: resolves to media_mode='none' in archive."""
        uid = self.fixture["uid"]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            archive_args = argparse.Namespace(
                profile=[uid],
                since=None,
                until=None,
                output=str(output),
                skip_media=True,   # old alias
                # no 'media' attribute → getattr default 'all' → alias kicks in
                detail_workers=2,
                media_workers=2,
                max_pages=20,
                refresh=False,
            )
            with mock.patch.object(FR, "request_json", side_effect=self.fake_request_json):
                crawl = FR.archive(archive_args)
        self.assertEqual(crawl.get("media_mode"), "none",
                         "--skip-media alias must resolve media_mode to 'none'")
        self.assertTrue(crawl.get("skip_media"),
                        "backward-compat skip_media field must be True when mode is none")

    def test_media_mode_explicit_none(self):
        """--media=none must set media_mode='none' in crawl audit."""
        uid = self.fixture["uid"]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            archive_args = argparse.Namespace(
                profile=[uid],
                since=None,
                until=None,
                output=str(output),
                skip_media=False,
                media="none",
                detail_workers=2,
                media_workers=2,
                max_pages=20,
                refresh=False,
            )
            with mock.patch.object(FR, "request_json", side_effect=self.fake_request_json):
                crawl = FR.archive(archive_args)
        self.assertEqual(crawl.get("media_mode"), "none")

    # ------ F2: self-repost dedup and cross-blogger same-post ------

    def test_cross_blogger_same_feed_not_deduped(self):
        """Two bloggers having a post with the same feed_id must produce two separate records.

        The index key is (uid, feed_id) so different uids are different keys.
        This test walks the full archive() path — no algorithm copied into the test body.
        """
        uid_a = "22222222222222222222"  # must be numeric for parse_uid
        uid_b = "33333333333333333333"
        shared_feed_id = "CROSS-FEED-001"

        def fake_rj_cross(url, params=None, attempts=4):
            params = params or {}
            if url == FR.LIST_URL:
                stream_type = int(params.get("type", 0))
                load_type = int(params.get("load_list_type", 1))
                # Only return the shared feed in "all" stream (type 301), not in "columns" (302).
                # This ensures each uid sees the feed in exactly one stream → self_repost=False.
                if load_type == 2 and stream_type == 301:
                    return {
                        "result": 0,
                        "feed": [{"feed_comm": {"feed_id": shared_feed_id, "timestamp": 1746748800}}],
                        "has_more": 0, "more_mark": "", "sequence": "",
                    }
                return {"result": 0, "feed": [], "has_more": 0, "more_mark": "", "sequence": ""}
            if url == FR.DETAIL_URL:
                # Return a post attributed to the blogger whose uid is in the target_uid param
                # (Futu returns author info in authorInfo)
                target = str(params.get("feedId") or "")
                return {
                    "code": 0,
                    "data": {"data": {
                        "feedCommon": {"feedId": shared_feed_id, "timestamp": 1746748800, "feedType": 3,
                                       "dynamicDescription": {"stringSc": "发表了"}},
                        "feedTitle": "Cross-blogger post",
                        "authorInfo": {"userId": "SOME-AUTHOR", "nickName": "Author"},
                        "moduleData": [{"data": {"text": "Content."}}],
                        "count": {"browse": 1, "comment": 0, "share": 0},
                    }}
                }
            return {"code": 0}

        with tempfile.TemporaryDirectory() as tmp:
            archive_args = argparse.Namespace(
                profile=[uid_a, uid_b], since=None, until=None, output=tmp,
                skip_media=True, detail_workers=2, media_workers=2,
                max_pages=20, refresh=False,
            )
            with mock.patch.object(FR, "request_json", side_effect=fake_rj_cross):
                FR.archive(archive_args)
            posts = FR.read_jsonl(Path(tmp) / "archive" / "posts.jsonl")

        # Two different uids with same feed_id → two different index keys → two records
        records_with_feed = [p for p in posts if p.get("feed_id") == shared_feed_id]
        self.assertEqual(len(records_with_feed), 2,
                         "different uids with same feed_id must produce two separate records")
        # self_reposted machinery was removed in v1.2.0; the field must not reappear
        for rec in records_with_feed:
            self.assertNotIn("self_reposted", rec,
                             "self_reposted field was removed and must not reappear in archive output")

    def test_audit_uniqueness_cross_blogger_passes(self):
        """Audit normalized_feed_ids_unique must PASS for two bloggers sharing a feed_id.

        The audit checks (profile_uid, feed_id) pairs, not bare feed_ids.
        This test runs the full audit() path against a crafted posts.jsonl.
        """
        uid_a = "44444444444444444444"  # numeric for parse_uid (audit reads posts.jsonl directly)
        uid_b = "55555555555555555555"
        shared_feed_id = "AUD-CROSS-001"

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            # Create minimal crawl_audit.json that audit() needs
            crawl_audit = {
                "schema_version": "1.0",
                "status": "PASS",
                "visible_history_status": "complete_visible_history",
                "captured_at": "2026-07-23T00:00:00+00:00",
                "requested_since": None,
                "requested_until": None,
                "profiles": [
                    {"uid": uid_a, "profile_url": f"https://q.futunn.com/profile/{uid_a}"},
                    {"uid": uid_b, "profile_url": f"https://q.futunn.com/profile/{uid_b}"},
                ],
                "streams": [
                    {"profile_uid": uid_a, "stream": "all", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                    {"profile_uid": uid_a, "stream": "columns", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                    {"profile_uid": uid_b, "stream": "all", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                    {"profile_uid": uid_b, "stream": "columns", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                ],
                "detail_expected": 2,
                "detail_successes": 2,
                "detail_failures": [],
                "normalization_failures": [],
                "normalized_records": 2,
                "media_mode": "none",
                "skip_media": True,
                "posts_with_image_content": 0,
                "media_objects": 0,
                "media_failures": [],
                "notes": [],
            }
            (output / "qa").mkdir(parents=True, exist_ok=True)
            FR.atomic_write_json(output / "qa" / "crawl_audit.json", crawl_audit)

            # Two records with same feed_id but different profile_uid (cross-blogger)
            (output / "archive").mkdir(parents=True, exist_ok=True)
            for uid in (uid_a, uid_b):
                detail_dir = output / "raw" / "details" / uid
                detail_dir.mkdir(parents=True, exist_ok=True)
                detail_path = detail_dir / f"{shared_feed_id}.json"
                detail_path.write_text(
                    json.dumps({"code": 0, "data": {"data": {
                        "feedCommon": {"feedId": shared_feed_id}
                    }}}),
                    encoding="utf-8",
                )
            FR.write_jsonl(output / "archive" / "posts.jsonl", [
                {
                    "profile_uid": uid_a, "feed_id": shared_feed_id,
                    "is_repost": False, "stream_membership": ["all"],
                    "source": {"detail_path": str(
                        output / "raw" / "details" / uid_a / f"{shared_feed_id}.json"
                    )},
                },
                {
                    "profile_uid": uid_b, "feed_id": shared_feed_id,
                    "is_repost": False, "stream_membership": ["all"],
                    "source": {"detail_path": str(
                        output / "raw" / "details" / uid_b / f"{shared_feed_id}.json"
                    )},
                },
            ])

            result = FR.audit(argparse.Namespace(output=str(output)))

        uniqueness_check = next(
            (c for c in result["checks"] if c["name"] == "normalized_feed_ids_unique"), None
        )
        self.assertIsNotNone(uniqueness_check)
        self.assertTrue(
            uniqueness_check["passed"],
            "cross-blogger same feed_id must PASS uniqueness check "
            "(audit uses (profile_uid, feed_id) pairs)",
        )

    def test_empty_origin_shell_not_repost(self):
        """Origin dict with empty richTextItems and pictureItems must not classify post as repost."""
        empty_origin = {"richTextItems": [], "pictureItems": [], "url": "https://example.com"}
        self.assertFalse(
            FR._has_repost_content(empty_origin),
            "empty richTextItems+pictureItems must not be treated as repost content",
        )
        non_empty_origin = {"richTextItems": [{"text": "hello"}], "pictureItems": []}
        self.assertTrue(
            FR._has_repost_content(non_empty_origin),
            "non-empty richTextItems must be treated as repost content",
        )

    def test_skip_media_and_media_evidence_both_given_warns_stderr(self):
        """When --skip-media and --media=evidence are both given, --media wins and a warning is printed.

        Reviewer optional #3: verify the stderr warning path is exercised.
        """
        uid = self.fixture["uid"]

        def fake_rj(url, params=None, attempts=4):
            params = params or {}
            if url == FR.LIST_URL:
                load_type = int(params.get("load_list_type", 1))
                if load_type == 2:
                    return {
                        "result": 0, "feed": [], "has_more": 0,
                        "more_mark": "", "sequence": "",
                    }
                return {"result": 0, "feed": [], "has_more": 0, "more_mark": "", "sequence": ""}
            return {"code": 0}

        with tempfile.TemporaryDirectory() as tmp:
            archive_args = argparse.Namespace(
                profile=[uid], since=None, until=None, output=tmp,
                skip_media=True,   # backward-compat alias
                media="evidence",  # explicit --media wins
                detail_workers=2, media_workers=2,
                max_pages=20, refresh=False,
            )
            import sys
            stderr_capture = io.StringIO()
            with mock.patch.object(FR, "request_json", side_effect=fake_rj):
                with mock.patch("sys.stderr", stderr_capture):
                    crawl = FR.archive(archive_args)

        warning_text = stderr_capture.getvalue()
        self.assertIn("--skip-media", warning_text,
                      "stderr must mention --skip-media")
        self.assertIn("evidence", warning_text,
                      "stderr must mention the winning --media=evidence value")
        # --media wins: effective mode must be 'evidence', not 'none'
        self.assertEqual(crawl.get("media_mode"), "evidence",
                         "--media=evidence must win over --skip-media alias")

    # ------ F3: tripwire uses posts_with_image_content ------

    def test_tripwire_pure_text_blogger_no_false_alarm(self):
        """Tripwire must NOT fire when posts_with_image_content=0 (pure-text archive)."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            uid = self.fixture["uid"]
            # Crawl audit simulates a pure-text blogger run
            crawl_audit = {
                "schema_version": "1.0",
                "status": "PASS",
                "visible_history_status": "complete_visible_history",
                "captured_at": "2026-07-22T00:00:00+00:00",
                "requested_since": None,
                "requested_until": None,
                "profiles": [{"uid": uid, "profile_url": f"https://q.futunn.com/profile/{uid}"}],
                "streams": [
                    {"profile_uid": uid, "stream": "all", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                    {"profile_uid": uid, "stream": "columns", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                ],
                "detail_expected": 1,
                "detail_successes": 1,
                "detail_failures": [],
                "normalization_failures": [],
                "normalized_records": 1,
                "media_mode": "all",
                "skip_media": False,
                "posts_with_image_content": 0,  # <-- pure-text blogger
                "media_objects": 0,  # no media downloaded (no images to get)
                "media_failures": [],
                "notes": [],
            }
            (output / "qa").mkdir(parents=True, exist_ok=True)
            FR.atomic_write_json(output / "qa" / "crawl_audit.json", crawl_audit)
            # Also need a posts.jsonl for audit to read
            (output / "archive").mkdir(parents=True, exist_ok=True)
            FR.write_jsonl(output / "archive" / "posts.jsonl", [{
                "feed_id": "TEXT-001",
                "profile_uid": uid,
                "source": {"detail_path": str(output / "raw" / "details" / uid / "TEXT-001.json")},
            }])
            # Create dummy detail file so source trace check passes
            detail_dir = output / "raw" / "details" / uid
            detail_dir.mkdir(parents=True, exist_ok=True)
            (detail_dir / "TEXT-001.json").write_text(
                json.dumps({"code": 0, "data": {"data": {"feedCommon": {"feedId": "TEXT-001"}}}}),
                encoding="utf-8",
            )
            result = FR.audit(argparse.Namespace(output=str(output)))

        tripwire_check = next(
            (c for c in result["checks"] if c["name"] == "media_extraction_not_zero_jobs"), None
        )
        self.assertIsNotNone(tripwire_check)
        self.assertTrue(
            tripwire_check["passed"],
            "tripwire must PASS for pure-text archive (posts_with_image_content=0)",
        )
        self.assertIn("N/A", str(tripwire_check.get("detail", "")),
                      "tripwire detail must say N/A for zero-image archive")

    def test_tripwire_image_posts_zero_downloads_fires(self):
        """Tripwire must WARN when posts_with_image_content > 0 but media_objects=0."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            uid = self.fixture["uid"]
            crawl_audit = {
                "schema_version": "1.0",
                "status": "PASS",
                "visible_history_status": "complete_visible_history",
                "captured_at": "2026-07-22T00:00:00+00:00",
                "requested_since": None,
                "requested_until": None,
                "profiles": [{"uid": uid, "profile_url": f"https://q.futunn.com/profile/{uid}"}],
                "streams": [
                    {"profile_uid": uid, "stream": "all", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                    {"profile_uid": uid, "stream": "columns", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                ],
                "detail_expected": 1,
                "detail_successes": 1,
                "detail_failures": [],
                "normalization_failures": [],
                "normalized_records": 1,
                "media_mode": "all",
                "skip_media": False,
                "posts_with_image_content": 3,  # <-- has images in source
                "media_objects": 0,            # <-- but zero downloaded → regression
                "media_failures": [],
                "notes": [],
            }
            (output / "qa").mkdir(parents=True, exist_ok=True)
            FR.atomic_write_json(output / "qa" / "crawl_audit.json", crawl_audit)
            (output / "archive").mkdir(parents=True, exist_ok=True)
            FR.write_jsonl(output / "archive" / "posts.jsonl", [{
                "feed_id": "IMG-001",
                "profile_uid": uid,
                "source": {"detail_path": str(output / "raw" / "details" / uid / "IMG-001.json")},
            }])
            detail_dir = output / "raw" / "details" / uid
            detail_dir.mkdir(parents=True, exist_ok=True)
            (detail_dir / "IMG-001.json").write_text(
                json.dumps({"code": 0, "data": {"data": {"feedCommon": {"feedId": "IMG-001"}}}}),
                encoding="utf-8",
            )
            result = FR.audit(argparse.Namespace(output=str(output)))

        tripwire_check = next(
            (c for c in result["checks"] if c["name"] == "media_extraction_not_zero_jobs"), None
        )
        self.assertIsNotNone(tripwire_check)
        self.assertFalse(
            tripwire_check["passed"],
            "tripwire must WARN when image posts exist but media_objects=0",
        )

    def test_tripwire_none_mode_skipped(self):
        """Tripwire must PASS (info) when media_mode='none' regardless of post count."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            uid = self.fixture["uid"]
            crawl_audit = {
                "schema_version": "1.0",
                "status": "PASS",
                "visible_history_status": "complete_visible_history",
                "captured_at": "2026-07-22T00:00:00+00:00",
                "requested_since": None,
                "requested_until": None,
                "profiles": [{"uid": uid, "profile_url": f"https://q.futunn.com/profile/{uid}"}],
                "streams": [
                    {"profile_uid": uid, "stream": "all", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                    {"profile_uid": uid, "stream": "columns", "complete_for_request": True,
                     "terminal_reason": "has_more_zero"},
                ],
                "detail_expected": 4,
                "detail_successes": 4,
                "detail_failures": [],
                "normalization_failures": [],
                "normalized_records": 4,
                "media_mode": "none",
                "skip_media": True,
                "posts_with_image_content": 3,
                "media_objects": 0,
                "media_failures": [],
                "notes": [],
            }
            (output / "qa").mkdir(parents=True, exist_ok=True)
            FR.atomic_write_json(output / "qa" / "crawl_audit.json", crawl_audit)
            (output / "archive").mkdir(parents=True, exist_ok=True)
            FR.write_jsonl(output / "archive" / "posts.jsonl", [{
                "feed_id": "POST-001",
                "profile_uid": uid,
                "source": {"detail_path": str(output / "raw" / "details" / uid / "POST-001.json")},
            }])
            detail_dir = output / "raw" / "details" / uid
            detail_dir.mkdir(parents=True, exist_ok=True)
            (detail_dir / "POST-001.json").write_text(
                json.dumps({"code": 0, "data": {"data": {"feedCommon": {"feedId": "POST-001"}}}}),
                encoding="utf-8",
            )
            result = FR.audit(argparse.Namespace(output=str(output)))

        tripwire_check = next(
            (c for c in result["checks"] if c["name"] == "media_extraction_not_zero_jobs"), None
        )
        self.assertIsNotNone(tripwire_check)
        self.assertTrue(
            tripwire_check["passed"],
            "tripwire must PASS when media_mode=none (skip mode)",
        )
        self.assertIn("none", str(tripwire_check.get("detail", "")))

    # ------ F4: trailing tag block suppression ------

    def test_trailing_tags_three_or_more_downgraded(self):
        """Symbols in trailing block of >= 3 tags not mentioned in body must be downgraded."""
        # 3 trailing tags: TSLA, NVDA, AMD not in body → all trailing-only
        text = "今天市场不错，关注$AAPL$后续走势。\n$TSLA$ $NVDA$ $AMD$"
        trailing = FR._trailing_tag_symbols(text)
        self.assertIn("TSLA", trailing)
        self.assertIn("NVDA", trailing)
        self.assertIn("AMD", trailing)
        self.assertNotIn("AAPL", trailing, "AAPL mentioned in body must not be in trailing set")

    def test_trailing_tags_body_mention_excluded(self):
        """A symbol discussed in the body text must not be downgraded even if also in trailing block."""
        text = "我今天买入$NVDA$，看好其AI路径。\n$TSLA$ $NVDA$ $AMD$"
        trailing = FR._trailing_tag_symbols(text)
        self.assertNotIn("NVDA", trailing, "NVDA mentioned in body must NOT be trailing-only")
        # TSLA and AMD have no body mention
        self.assertIn("TSLA", trailing)
        self.assertIn("AMD", trailing)

    def test_trailing_tags_two_not_triggered(self):
        """Only 2 trailing tags must NOT trigger the block (threshold is >= 3)."""
        text = "关注市场动向。\n$TSLA$ $NVDA$"
        trailing = FR._trailing_tag_symbols(text)
        self.assertEqual(len(trailing), 0, "2-tag trailing block must not be triggered")

    def test_trailing_tags_pure_text_unaffected(self):
        """Text without any $SYMBOL$ pattern must return empty set."""
        text = "今天市场不错，继续持有苹果和特斯拉，等待机会。"
        trailing = FR._trailing_tag_symbols(text)
        self.assertEqual(len(trailing), 0)

    def test_trailing_tags_downgrade_in_prepare(self):
        """prepare() must assign evidence_level=D and action=none to trailing-tag-only symbols."""
        uid = self.fixture["uid"]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            archive_args = argparse.Namespace(
                profile=[uid],
                since=None,
                until=None,
                output=str(output),
                skip_media=True,
                detail_workers=2,
                media_workers=2,
                max_pages=20,
                refresh=False,
            )
            # Inject a synthetic post with 4 trailing exposure tags (only AAPL in body)
            def patched_request_json(url, params=None, attempts=4):
                params = params or {}
                if url == FR.LIST_URL:
                    stream = str(params["type"])
                    page = "first" if int(params["load_list_type"]) == 2 else "next"
                    key = f"{stream}:{page}"
                    if key == "301:first":
                        return {
                            "result": 0,
                            "feed": [{"feed_comm": {"feed_id": "TRAIL-001", "timestamp": 1746748800}}],
                            "has_more": 0,
                            "more_mark": "",
                            "sequence": "",
                        }
                    # Remaining pages return empty
                    return {"result": 0, "feed": [], "has_more": 0}
                if url == FR.DETAIL_URL:
                    return {
                        "code": 0,
                        "data": {"data": {
                            "feedCommon": {
                                "feedId": "TRAIL-001",
                                "timestamp": 1746748800,
                                "feedType": 3,
                                "dynamicDescription": {"stringSc": "发表了"},
                            },
                            "feedTitle": "今天买入$AAPL$，看好其AI芯片路线",
                            "authorInfo": {"userId": uid, "nickName": "Test"},
                            "moduleData": [{"data": {
                                "text": "我今天买入了Apple，成本价合理，持仓约两成。\n$TSLA$ $NVDA$ $AMD$ $META$",
                            }}],
                            "count": {"browse": 1, "comment": 0, "share": 0},
                        }}
                    }
                raise AssertionError(f"Unexpected URL: {url}")

            with mock.patch.object(FR, "request_json", side_effect=patched_request_json):
                FR.archive(archive_args)
            FR.prepare(argparse.Namespace(output=str(output)))

            candidates = FR.read_jsonl(output / "analysis" / "candidates.jsonl")

        # Candidates for TSLA/NVDA/AMD/META (trailing tags only) must be D
        trailing_candidates = [
            c for c in candidates
            if c.get("trailing_tag_downgraded") is True
        ]
        non_trailing = [
            c for c in candidates
            if not c.get("trailing_tag_downgraded")
        ]
        self.assertTrue(len(trailing_candidates) >= 3,
                        "At least 3 trailing-tag symbols must be flagged and downgraded")
        for c in trailing_candidates:
            self.assertEqual(c["evidence_prelabel"], "D",
                             f"Trailing symbol {c.get('symbol_raw')} must be downgraded to D")
            self.assertEqual(c["action_prelabel"], "none",
                             f"Trailing symbol {c.get('symbol_raw')} must have action=none")
        # AAPL (in title body) must NOT be downgraded
        aapl_candidates = [c for c in candidates if c.get("symbol_raw") == "AAPL"]
        for c in aapl_candidates:
            self.assertFalse(c.get("trailing_tag_downgraded"),
                             "AAPL in body must NOT be trailing-downgraded")


    # ------ F2 / _safe_filename ------

    def test_safe_filename_preserves_chinese_and_truncates(self):
        """_safe_filename keeps Chinese chars, emoji, strips surrounding space, truncates to 80."""
        self.assertEqual(FR._safe_filename("虚构研究员甲"), "虚构研究员甲")
        # Emoji preserved
        self.assertEqual(FR._safe_filename("博主🔥"), "博主🔥")
        # Leading/trailing whitespace stripped
        self.assertEqual(FR._safe_filename("  hello  "), "hello")
        # Truncation at 80 chars
        long_name = "A" * 100
        self.assertEqual(len(FR._safe_filename(long_name)), 80)

    def test_safe_filename_replaces_illegal_chars(self):
        """_safe_filename replaces filesystem-illegal chars with _ and collapses runs."""
        # Each illegal character individually
        for ch in '/\\:*?"<>|':
            result = FR._safe_filename(f"a{ch}b")
            self.assertNotIn(ch, result, f"char {ch!r} must be replaced")
            self.assertIn("a", result)
            self.assertIn("b", result)
        # Consecutive replacements collapse to single underscore
        result = FR._safe_filename("a//b")
        self.assertNotIn("__", result, "consecutive underscores must be collapsed")
        # Control character replaced
        result = FR._safe_filename("a\x00b")
        self.assertNotIn("\x00", result)

    def test_safe_filename_empty_input_returns_empty(self):
        """_safe_filename returns '' for empty string (caller uses uid_<uid> fallback)."""
        self.assertEqual(FR._safe_filename(""), "")
        self.assertEqual(FR._safe_filename("   "), "")
        # String that reduces to only underscores after replacement
        self.assertEqual(FR._safe_filename("///"), "")

    # ------ F1 / export-authors subcommand ------

    def test_export_authors_missing_archive_exits_2(self):
        """export-authors on empty output dir must exit 2 mentioning 'archive'."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_err:
                result = FR.main(["export-authors", "--output", tmp])
            err_text = mock_err.getvalue()
        self.assertEqual(result, 2, "exit code must be 2 when posts.jsonl is missing")
        self.assertIn("archive", err_text.lower(),
                      "error message must mention 'archive'")

    def test_export_authors_creates_files_and_index(self):
        """export-authors creates one .md per author and index.md; index lists all authors."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "archive").mkdir()

            uid_a = "11111111"
            uid_b = "22222222"
            posts = [
                {
                    "profile_uid": uid_a,
                    "author_name": "博主甲",
                    "feed_id": "FEED-A1",
                    "date": "2026-07-20",
                    "published_at": "2026-07-20T10:00:00+08:00",
                    "title": "分析文章",
                    "text": "今天买入了$TSLA$。",
                    "is_repost": False,
                    "is_column": False,
                    "symbols": [{"raw": "TSLA", "code": "TSLA", "market": "US", "name": None}],
                    "metrics": {"likes": 10, "comments": 2, "reposts": 0, "views": 100},
                    "url": "https://q.futunn.com/feed/FEED-A1",
                    "original_author": None,
                    "original_text": None,
                },
                {
                    "profile_uid": uid_a,
                    "author_name": "博主甲",
                    "feed_id": "FEED-A2",
                    "date": "2026-07-22",
                    "published_at": "2026-07-22T08:00:00+08:00",
                    "title": "",
                    "text": "后续观察。",
                    "is_repost": False,
                    "is_column": True,
                    "symbols": [],
                    "metrics": {"likes": 0, "comments": 0, "reposts": 0, "views": 50},
                    "url": "https://q.futunn.com/feed/FEED-A2",
                    "original_author": None,
                    "original_text": None,
                },
                {
                    "profile_uid": uid_b,
                    "author_name": "博主乙",
                    "feed_id": "FEED-B1",
                    "date": "2026-07-21",
                    "published_at": "2026-07-21T09:00:00+08:00",
                    "title": "转发帖",
                    "text": "看了一下，值得关注。",
                    "is_repost": True,
                    "is_column": False,
                    "symbols": [],
                    "metrics": {"likes": 5, "comments": 1, "reposts": 0, "views": 80},
                    "url": "https://q.futunn.com/feed/FEED-B1",
                    "original_author": "原帖作者",
                    "original_text": "原帖正文内容。",
                },
            ]
            FR.write_jsonl(output / "archive" / "posts.jsonl", posts)

            args = argparse.Namespace(output=str(output))
            result = FR.export_authors(args)

            # Two author files created — assertions inside the with block (tempdir is live)
            by_author = output / "archive" / "by-author"
            self.assertTrue(by_author.exists(), "by-author/ directory must be created")
            self.assertTrue((by_author / "index.md").exists(), "index.md must be created")
            self.assertEqual(result["authors"], 2)
            self.assertEqual(result["total_posts"], 3)

            # Each uid has a file (≥ 2 author files + index.md = ≥ 3 total)
            files = list(by_author.glob("*.md"))
            self.assertGreaterEqual(len(files), 3,
                                    "at least 2 author .md files + index.md expected")

            # index.md contains both author names
            index_text = (by_author / "index.md").read_text(encoding="utf-8")
            self.assertIn("博主甲", index_text)
            self.assertIn("博主乙", index_text)

    def test_export_authors_post_order_newest_first(self):
        """Author .md must list newest post first (reverse chronological)."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "archive").mkdir()
            uid = "99887766"
            posts = [
                {
                    "profile_uid": uid,
                    "author_name": "TestAuthor",
                    "feed_id": "OLD",
                    "date": "2026-01-01",
                    "published_at": "2026-01-01T08:00:00+08:00",
                    "title": "旧帖",
                    "text": "这是旧的帖子。",
                    "is_repost": False,
                    "is_column": False,
                    "symbols": [],
                    "metrics": {"likes": 0, "comments": 0, "reposts": 0, "views": 0},
                    "url": "https://q.futunn.com/feed/OLD",
                    "original_author": None,
                    "original_text": None,
                },
                {
                    "profile_uid": uid,
                    "author_name": "TestAuthor",
                    "feed_id": "NEW",
                    "date": "2026-07-22",
                    "published_at": "2026-07-22T08:00:00+08:00",
                    "title": "新帖",
                    "text": "这是新的帖子。",
                    "is_repost": False,
                    "is_column": False,
                    "symbols": [],
                    "metrics": {"likes": 0, "comments": 0, "reposts": 0, "views": 0},
                    "url": "https://q.futunn.com/feed/NEW",
                    "original_author": None,
                    "original_text": None,
                },
            ]
            FR.write_jsonl(output / "archive" / "posts.jsonl", posts)
            FR.export_authors(argparse.Namespace(output=str(output)))

            # Assertions inside the with block (tempdir is live)
            by_author = output / "archive" / "by-author"
            author_files = [f for f in by_author.glob("*.md") if f.name != "index.md"]
            self.assertEqual(len(author_files), 1)
            content = author_files[0].read_text(encoding="utf-8")
            # Check that the newer post's section heading appears before the older one.
            # Use "### <date>" to target the post-section headers, not the metadata span line
            # which also contains both dates (oldest ~ newest).
            pos_new = content.find("### 2026-07-22")
            pos_old = content.find("### 2026-01-01")
            self.assertGreater(pos_new, 0, "new post section header must appear in file")
            self.assertGreater(pos_old, 0, "old post section header must appear in file")
            self.assertLess(pos_new, pos_old,
                            "newest post section (2026-07-22) must appear before oldest (2026-01-01)")

    def test_export_authors_report_auto_creates_by_author(self):
        """report() must auto-create archive/by-author/index.md as standard output."""
        uid = self.fixture["uid"]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "archive").mkdir(parents=True)
            # Minimal posts.jsonl with one post for uid
            posts = [{
                "profile_uid": uid,
                "author_name": "虚构研究员甲",
                "feed_id": "AUTO-001",
                "date": "2026-07-22",
                "published_at": "2026-07-22T08:00:00+08:00",
                "title": "",
                "text": "测试帖子。",
                "is_repost": False,
                "is_column": False,
                "symbols": [],
                "metrics": {"likes": 0, "comments": 0, "reposts": 0, "views": 0},
                "url": "https://q.futunn.com/feed/AUTO-001",
                "original_author": None,
                "original_text": None,
            }]
            FR.write_jsonl(output / "archive" / "posts.jsonl", posts)
            # report() requires candidates.jsonl and claims.reviewed.jsonl (can be empty)
            (output / "analysis").mkdir(parents=True)
            FR.write_jsonl(output / "analysis" / "candidates.jsonl", [])
            FR.write_jsonl(output / "analysis" / "claims.reviewed.jsonl", [])
            (output / "analysis" / "market").mkdir(parents=True)
            FR.write_jsonl(output / "analysis" / "market" / "claims_market.jsonl", [])

            FR.report(argparse.Namespace(output=str(output)))

            # Assertions inside the with block (tempdir is live)
            index_path = output / "archive" / "by-author" / "index.md"
            self.assertTrue(index_path.exists(),
                            "report() must auto-create archive/by-author/index.md")
            index_text = index_path.read_text(encoding="utf-8")
            self.assertIn("虚构研究员甲", index_text,
                          "index.md must list the author name")


    # ------ BUG1: multiline original_text stays inside blockquote ------

    def test_export_authors_multiline_original_text_blockquote(self):
        """Multiline original_text in a repost must have every line prefixed with '> '."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "archive").mkdir()
            uid = "55551111"
            multiline_orig = "第一行内容。\n第二行内容。\n第三行内容。"
            posts = [{
                "profile_uid": uid,
                "author_name": "测试博主",
                "feed_id": "ML-001",
                "date": "2026-07-22",
                "published_at": "2026-07-22T08:00:00+08:00",
                "title": "",
                "text": "我的评论。",
                "is_repost": True,
                "is_column": False,
                "symbols": [],
                "metrics": {"likes": 0, "comments": 0, "reposts": 0, "views": 0},
                "url": "https://q.futunn.com/feed/ML-001",
                "original_author": "原作者",
                "original_text": multiline_orig,
            }]
            FR.write_jsonl(output / "archive" / "posts.jsonl", posts)
            FR.export_authors(argparse.Namespace(output=str(output)))

            by_author = output / "archive" / "by-author"
            author_file = next(f for f in by_author.glob("*.md") if f.name != "index.md")
            content = author_file.read_text(encoding="utf-8")

        # Every line of the original text must be prefixed with "> "
        self.assertIn("> 第一行内容。", content, "first line of orig_text must have '> ' prefix")
        self.assertIn("> 第二行内容。", content, "second line of orig_text must have '> ' prefix")
        self.assertIn("> 第三行内容。", content, "third line of orig_text must have '> ' prefix")
        # The raw unquoted second line must not appear (would happen without the fix)
        lines = content.splitlines()
        non_quoted_orig = [
            ln for ln in lines
            if "第二行内容" in ln and not ln.startswith(">")
        ]
        self.assertEqual(non_quoted_orig, [],
                         "second line of orig_text must not appear outside blockquote")

    # ------ BUG2: author name with | does not break index.md table ------

    def test_export_authors_pipe_in_name_escaped_in_index(self):
        """Author name containing '|' must be escaped in index.md table rows."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "archive").mkdir()
            uid = "66662222"
            posts = [{
                "profile_uid": uid,
                "author_name": "博主|分析|师",
                "feed_id": "PIPE-001",
                "date": "2026-07-22",
                "published_at": "2026-07-22T08:00:00+08:00",
                "title": "",
                "text": "测试。",
                "is_repost": False,
                "is_column": False,
                "symbols": [],
                "metrics": {"likes": 0, "comments": 0, "reposts": 0, "views": 0},
                "url": "https://q.futunn.com/feed/PIPE-001",
                "original_author": None,
                "original_text": None,
            }]
            FR.write_jsonl(output / "archive" / "posts.jsonl", posts)
            FR.export_authors(argparse.Namespace(output=str(output)))

            index_text = (output / "archive" / "by-author" / "index.md").read_text(
                encoding="utf-8"
            )

        # The data row must contain escaped pipes so the table parses correctly
        data_rows = [
            ln for ln in index_text.splitlines()
            if ln.startswith("| ") and "66662222" in ln
        ]
        self.assertEqual(len(data_rows), 1, "exactly one data row for this uid")
        row = data_rows[0]
        # Raw unescaped | inside cell content would split the column; check it's escaped
        # The row starts with "| " — we check the author name cell contains \| not raw |
        self.assertIn(r"\|", row,
                      "pipe in author name must be escaped as \\| in the table row")
        # The escaped name must appear, not the raw one breaking columns
        self.assertIn(r"博主\|分析\|师", row,
                      "escaped author name must appear verbatim in the data row")


    # ------ Stage A: capture-adapter interface ------

    def test_select_adapter_futu_url(self):
        """select_adapter routes q.futunn.com profile URLs to FutuAdapter."""
        adapter = FR.select_adapter("https://q.futunn.com/profile/12345678")
        self.assertEqual(adapter.name, "futu")

    def test_select_adapter_numeric_uid(self):
        """select_adapter routes bare numeric UIDs to FutuAdapter (default platform)."""
        adapter = FR.select_adapter("12345678")
        self.assertEqual(adapter.name, "futu")

    def test_select_adapter_laohu8_routes_to_tiger(self):
        """select_adapter routes laohu8.com URLs to TigerAdapter (Stage B now supported)."""
        adapter = FR.select_adapter("https://www.laohu8.com/personal/12345")
        self.assertEqual(adapter.name, "tiger")

    def test_select_adapter_nonsense_raises(self):
        """select_adapter raises ResearchError for completely unrecognized input."""
        with self.assertRaises(FR.ResearchError):
            FR.select_adapter("not-a-valid-platform-url")

    def test_futu_adapter_resolve_uid(self):
        """FutuAdapter.resolve_uid handles q.futunn.com URLs, bare numeric UIDs, and rejects junk."""
        adapter = FR.FutuAdapter()
        uid = self.fixture["uid"]
        # Bare numeric UID passthrough
        self.assertEqual(adapter.resolve_uid(uid), uid)
        # Full profile URL with query params
        self.assertEqual(
            adapter.resolve_uid(f"https://q.futunn.com/profile/{uid}?lang=zh-cn"),
            uid,
        )
        # Invalid input must raise ResearchError
        with self.assertRaises(FR.ResearchError):
            adapter.resolve_uid("not-a-uid")

    # ------ Tiger adapter: routing and UID resolution ------

    def test_tiger_adapter_matches_laohu8_url(self):
        """TigerAdapter.matches() returns True for laohu8.com URLs."""
        adp = FR.TigerAdapter()
        self.assertTrue(adp.matches("https://www.laohu8.com/personal/98765/"))
        self.assertTrue(adp.matches("http://laohu8.com/personal/123"))
        self.assertTrue(adp.matches("laohu8.com/personal/555"))

    def test_tiger_adapter_does_not_match_numeric_uid(self):
        """TigerAdapter.matches() returns False for bare numeric UIDs (Futu default)."""
        adp = FR.TigerAdapter()
        self.assertFalse(adp.matches("12345678"))
        self.assertFalse(adp.matches("98765"))
        self.assertFalse(adp.matches("https://q.futunn.com/profile/12345"))

    def test_tiger_adapter_resolve_uid_from_url(self):
        """TigerAdapter.resolve_uid() extracts the numeric UID from laohu8.com/personal/."""
        adp = FR.TigerAdapter()
        self.assertEqual(adp.resolve_uid("https://www.laohu8.com/personal/98765/"), "98765")
        self.assertEqual(adp.resolve_uid("https://www.laohu8.com/personal/111222333"), "111222333")
        # Bad URL without /personal/ raises ResearchError
        with self.assertRaises(FR.ResearchError):
            adp.resolve_uid("https://www.laohu8.com/user/12345")
        with self.assertRaises(FR.ResearchError):
            adp.resolve_uid("not-a-url-at-all")

    def test_tiger_adapter_profile_url(self):
        """TigerAdapter.profile_url() constructs the canonical personal page URL."""
        adp = FR.TigerAdapter()
        self.assertEqual(adp.profile_url("12345"), "https://www.laohu8.com/personal/12345/")

    # ------ Tiger list page parsing ------

    # Minimal SSR HTML that mimics the laohu8.com personal page structure.
    TIGER_LIST_HTML = """
<html><body>
<div class="tweet-item">
  <a href="/post/9000001">link</a>
  <span class="publish-time">·</span>
  <span class="publish-time">12:30</span>
  <a href="/post/9000001">link2</a>
</div>
<div class="tweet-item">
  <a href="/post/9000002">link</a>
  <span class="publish-time">·</span>
  <span class="publish-time">07-20 09:15</span>
  <a href="/post/9000002">link2</a>
</div>
<div class="tweet-item">
  <a href="/post/9000003">link</a>
  <span class="publish-time">·</span>
  <span class="publish-time">2024-12-01</span>
  <a href="/post/9000003">link2</a>
</div>
</body></html>
"""

    def test_tiger_list_parse_post_ids_and_cursor(self):
        """_parse_list_page extracts deduplicated post IDs and computes min-id cursor."""
        from datetime import date
        adp = FR.TigerAdapter()
        today = date(2025, 7, 20)
        post_ids, time_map, cursor = adp._parse_list_page(self.TIGER_LIST_HTML, today)
        # Should have exactly 3 unique IDs (each appears twice in HTML)
        self.assertEqual(post_ids, ["9000001", "9000002", "9000003"])
        # Cursor is str(min(post_id))
        self.assertEqual(cursor, "9000001")

    def test_tiger_list_parse_publish_time_mapping(self):
        """_parse_list_page maps post IDs to their raw publish-time strings."""
        from datetime import date
        adp = FR.TigerAdapter()
        today = date(2025, 7, 20)
        _, time_map, _ = adp._parse_list_page(self.TIGER_LIST_HTML, today)
        self.assertEqual(time_map["9000001"], "12:30")
        self.assertEqual(time_map["9000002"], "07-20 09:15")
        self.assertEqual(time_map["9000003"], "2024-12-01")

    def test_tiger_list_parse_bullet_separator_filtered(self):
        """_parse_list_page filters out '·' separator spans from time_map."""
        from datetime import date
        adp = FR.TigerAdapter()
        today = date(2025, 7, 20)
        _, time_map, _ = adp._parse_list_page(self.TIGER_LIST_HTML, today)
        # Values must never be the bullet separator
        for pid, raw in time_map.items():
            self.assertNotIn(raw, ("·", "·", "·", "•", "·"),
                             f"Bullet separator leaked into time_map for post {pid}")

    def test_tiger_publish_time_formats(self):
        """_parse_publish_time handles the four time formats used by laohu8.com."""
        from datetime import date, datetime, timezone
        adp = FR.TigerAdapter()
        crawl_date = date(2025, 7, 20)

        # HH:MM (same-day post)
        dt, iso = adp._parse_publish_time("12:30", crawl_date)
        self.assertIsNotNone(dt)
        self.assertTrue(iso.startswith("2025-07-20T12:30"))

        # MM-DD HH:MM (earlier this year with time)
        dt, iso = adp._parse_publish_time("03-15 09:00", crawl_date)
        self.assertIsNotNone(dt)
        self.assertTrue(iso.startswith("2025-03-15T09:00"))

        # YYYY-MM-DD (older post with explicit year)
        dt, iso = adp._parse_publish_time("2024-12-01", crawl_date)
        self.assertIsNotNone(dt)
        self.assertTrue(iso.startswith("2024-12-01"))

        # MM-DD only (current year, no time)
        dt, iso = adp._parse_publish_time("06-15", crawl_date)
        self.assertIsNotNone(dt)
        self.assertTrue(iso.startswith("2025-06-15"))

        # Empty / unrecognised → (None, None)
        dt_none, iso_none = adp._parse_publish_time("", crawl_date)
        self.assertIsNone(dt_none)
        self.assertIsNone(iso_none)

        dt_none2, iso_none2 = adp._parse_publish_time("invalid-time", crawl_date)
        self.assertIsNone(dt_none2)
        self.assertIsNone(iso_none2)

    # ------ Tiger detail page parsing ------

    TIGER_DETAIL_HTML = """
<html><head>
  <meta property="og:title" content="Fallback OG Title" />
</head><body>
<h2 class="post-title">Tiger Post Title &amp; More</h2>
<div class="post-author">
  <a href="/personal/55555/" title="TigerAuthor">TigerAuthor</a>
</div>
<span class="post-time">07-19 10:23</span>
<article class="post-article article-content-wrapper">
  <p>First paragraph text.</p>
  <p>Second paragraph with &lt;symbols&gt; and entities.</p>
  <div>Nested div content.</div>
</article>
</body></html>
"""

    def test_tiger_detail_parse_title_text_author(self):
        """_parse_detail_page extracts title, author name/uid, and article text."""
        adp = FR.TigerAdapter()
        detail = adp._parse_detail_page(self.TIGER_DETAIL_HTML, "888001", "07-19 10:23")
        self.assertEqual(detail["source"], "tiger")
        self.assertEqual(detail["post_id"], "888001")
        # Title from h2.post-title (HTML entities decoded)
        self.assertEqual(detail["title"], "Tiger Post Title & More")
        # Author from post-author block
        self.assertEqual(detail["author_name"], "TigerAuthor")
        self.assertEqual(detail["author_uid"], "55555")
        # Publish time from list preserved in the detail dict
        self.assertEqual(detail["publish_time_list"], "07-19 10:23")
        # Article text extracted (not empty)
        self.assertIn("First paragraph text.", detail["text"])
        self.assertIn("Second paragraph", detail["text"])

    def test_tiger_html_robustness_entities_and_symbols(self):
        """_parse_detail_page decodes HTML entities and handles nested tags in article."""
        adp = FR.TigerAdapter()
        html_with_entities = """
<html><body>
<h2 class="post-title">Title &amp; &#60;Test&#62;</h2>
<div class="post-author">
  <a href="/personal/77777/" title="AuthorX">AuthorX</a>
</div>
<span class="post-time">2025-01-10</span>
<article class="post-article article-content-wrapper">
  <p>Text with &amp; entity and &#169; copyright.</p>
  <p>NVDA $TSLA $AAPL mentioned.</p>
</article>
</body></html>
"""
        detail = adp._parse_detail_page(html_with_entities, "999001", "")
        # h2 title decoded
        self.assertEqual(detail["title"], "Title & <Test>")
        # Article text has entity decoded
        self.assertIn("&", detail["text"])
        self.assertIn("©", detail["text"])

    def test_tiger_normalize_post_schema_fields(self):
        """normalize_post() produces all required schema fields for a Tiger detail file."""
        import tempfile
        import json
        from pathlib import Path

        adp = FR.TigerAdapter()
        tiger_detail = {
            "source": "tiger",
            "post_id": "5551234",
            "captured_at": "2026-07-15T04:00:00+00:00",
            "author_name": "John Tiger",
            "author_uid": "9990001",
            "title": "My Tiger Post",
            "text": "Content about NVDA and TSLA.",
            "publish_time_list": "07-15 11:00",
            "publish_time_detail": "11:00",
            "url": "https://www.laohu8.com/post/5551234",
        }
        with tempfile.TemporaryDirectory() as tmp:
            detail_path = Path(tmp) / "5551234.json"
            detail_path.write_text(json.dumps(tiger_detail), encoding="utf-8")

            record = adp.normalize_post(
                path=detail_path,
                uid="9990001",
                stream_membership=["all"],
                media_by_feed={},
                profile_url_str="https://www.laohu8.com/personal/9990001/",
            )

        # Core identity fields
        self.assertEqual(record["schema_version"], FR.SCHEMA_VERSION)
        self.assertEqual(record["feed_id"], "5551234")
        self.assertEqual(record["author_uid"], "9990001")
        self.assertEqual(record["profile_uid"], "9990001")
        self.assertEqual(record["author_name"], "John Tiger")
        self.assertEqual(record["title"], "My Tiger Post")
        self.assertIn("NVDA", record["text"])
        # Required schema keys must all be present
        required_keys = [
            "schema_version", "feed_id", "author_uid", "profile_uid", "author_name",
            "published_at", "published_at_raw", "date", "month", "stream_membership",
            "is_column", "is_repost", "is_original_author", "feed_type", "content_type",
            "profile_action", "title", "text", "original_text", "original_author",
            "symbols", "inferred_symbols", "topics", "metrics", "images", "url",
            "source", "parse_warnings",
        ]
        for key in required_keys:
            self.assertIn(key, record, f"normalize_post() missing field: {key}")
        # Tiger-specific invariants
        self.assertFalse(record["is_column"])
        self.assertFalse(record["is_repost"])
        self.assertTrue(record["is_original_author"])
        self.assertEqual(record["symbols"], [])
        self.assertEqual(record["images"], [])
        self.assertIsInstance(record["inferred_symbols"], list)
        # Metrics present as dict
        self.assertIsInstance(record["metrics"], dict)

    def test_tiger_normalize_post_rejects_non_tiger_file(self):
        """normalize_post() raises ResearchError for files that are not Tiger detail JSON."""
        import tempfile
        import json
        from pathlib import Path

        adp = FR.TigerAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            # File with wrong source field
            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text(json.dumps({"source": "futu", "post_id": "1"}), encoding="utf-8")
            with self.assertRaises(FR.ResearchError):
                adp.normalize_post(bad_path, "uid1", ["all"], {}, "")
            # Non-JSON file
            junk_path = Path(tmp) / "junk.json"
            junk_path.write_text("not valid json", encoding="utf-8")
            with self.assertRaises(FR.ResearchError):
                adp.normalize_post(junk_path, "uid1", ["all"], {}, "")

    def test_tiger_select_adapter_and_futu_numeric_zero_regression(self):
        """Bare numeric UIDs still route to FutuAdapter; laohu8 URLs route to TigerAdapter."""
        futu_adapter = FR.select_adapter("987654321")
        self.assertEqual(futu_adapter.name, "futu")

        tiger_adapter = FR.select_adapter("https://www.laohu8.com/personal/123456789/")
        self.assertEqual(tiger_adapter.name, "tiger")

        # Futu URL still routes to Futu
        futu_url_adapter = FR.select_adapter("https://q.futunn.com/profile/11223344")
        self.assertEqual(futu_url_adapter.name, "futu")

    # ------ BUG1: Tiger symbol extraction from $中文名(CODE)$ format ------

    def test_tiger_extract_symbols_chinese_label_with_ticker(self):
        """_tiger_extract_symbols extracts CODE from $中文名(CODE)$ parenthesised format."""
        text = "看好 $特斯拉(TSLA)$ 和 $SpaceX(SPCX)$ 的走势。"
        symbols = FR._tiger_extract_symbols(text)
        codes = [s.get("raw", "").upper() for s in symbols]
        self.assertIn("TSLA", codes, "TSLA should be extracted from $特斯拉(TSLA)$")
        self.assertIn("SPCX", codes, "SPCX should be extracted from $SpaceX(SPCX)$")

    def test_tiger_extract_symbols_plain_dollar_code(self):
        """_tiger_extract_symbols extracts CODE from plain $CODE$ format (no parens)."""
        text = "这是 $NVDA$ 和 $AAPL$ 的对比分析。"
        symbols = FR._tiger_extract_symbols(text)
        codes = [s.get("raw", "").upper() for s in symbols]
        self.assertIn("NVDA", codes, "NVDA should be extracted from $NVDA$")
        self.assertIn("AAPL", codes, "AAPL should be extracted from $AAPL$")

    def test_tiger_extract_symbols_paren_takes_priority_over_plain(self):
        """When both $中文名(CODE)$ and $CODE$ appear, paren format wins; no duplication."""
        # $TSLA$ also appears but $特斯拉(TSLA)$ is the canonical tag
        text = "$特斯拉(TSLA)$ 最近表现强劲，也有人直接写 $TSLA$ 来表示。"
        symbols = FR._tiger_extract_symbols(text)
        codes = [s.get("raw", "").upper() for s in symbols]
        # TSLA appears once — deduplication must hold
        self.assertEqual(codes.count("TSLA"), 1, "TSLA must not be duplicated")
        self.assertIn("TSLA", codes)

    def test_tiger_normalize_post_symbols_populated_from_tags(self):
        """normalize_post() populates symbols[] from $...(CODE)$ tags in Tiger post text."""
        import tempfile
        import json
        from pathlib import Path

        adp = FR.TigerAdapter()
        tiger_detail = {
            "source": "tiger",
            "post_id": "7771234",
            "captured_at": "2026-07-22T04:00:00+00:00",
            "author_name": "TigerUser",
            "author_uid": "9990002",
            "title": "看好 $特斯拉(TSLA)$ 的走势",
            "text": "$SpaceX(SPCX)$ 下周有重要发射，$NVDA$ 也可以关注。",
            "publish_time_list": "07-22 09:00",
            "publish_time_detail": "",
            "url": "https://www.laohu8.com/post/7771234",
        }
        with tempfile.TemporaryDirectory() as tmp:
            detail_path = Path(tmp) / "7771234.json"
            detail_path.write_text(json.dumps(tiger_detail), encoding="utf-8")
            record = adp.normalize_post(
                path=detail_path,
                uid="9990002",
                stream_membership=["tiger-all"],
                media_by_feed={},
                profile_url_str="https://www.laohu8.com/personal/9990002/",
            )
        sym_codes = {s.get("raw", "").upper() for s in record["symbols"]}
        self.assertIn("TSLA", sym_codes, "TSLA from $特斯拉(TSLA)$ must appear in symbols")
        self.assertIn("SPCX", sym_codes, "SPCX from $SpaceX(SPCX)$ must appear in symbols")
        self.assertIn("NVDA", sym_codes, "NVDA from $NVDA$ must appear in symbols")
        # symbols list must not be empty (the original BUG1 symptom)
        self.assertGreater(len(record["symbols"]), 0, "symbols must not be empty for tagged posts")

    # ------ BUG2: expected_streams_present audit check ------

    def _make_tiger_crawl_audit(self, tmp_dir: Path, uid: str) -> None:
        """Write a minimal Tiger-style crawl_audit.json with single 'tiger-all' stream."""
        qa = tmp_dir / "qa"
        qa.mkdir(parents=True, exist_ok=True)
        crawl_audit = {
            "schema_version": FR.SCHEMA_VERSION,
            "status": "PASS",
            "visible_history_status": "complete_visible_history",
            "captured_at": "2025-07-22T10:00:00+08:00",
            "requested_since": None,
            "requested_until": None,
            "profiles": [
                {
                    "uid": uid,
                    "profile_url": f"https://www.laohu8.com/personal/{uid}/",
                    "adapter": "tiger",
                    "expected_streams": ["all"],
                }
            ],
            "streams": [
                {
                    "profile_uid": uid,
                    "stream": "all",
                    "pages": 1,
                    "rows": 1,
                    "unique": 1,
                    "complete_for_request": True,
                    "terminal_reason": "has_more_zero",
                }
            ],
            "detail_expected": 1,
            "detail_successes": 1,
            "detail_failures": [],
            "normalization_failures": [],
            "normalized_records": 1,
            "media_mode": "none",
            "skip_media": True,
            "posts_with_image_content": 0,
            "media_objects": 0,
            "media_failures": [],
            "notes": ["All expected streams per adapter are captured."],
        }
        import json as _json
        (qa / "crawl_audit.json").write_text(
            _json.dumps(crawl_audit), encoding="utf-8"
        )

    def _write_minimal_tiger_archive(self, tmp_dir: Path, uid: str) -> None:
        """Write a minimal Tiger archive (posts.jsonl + empty analysis files)."""
        import json as _json
        archive = tmp_dir / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        post = {
            "schema_version": FR.SCHEMA_VERSION,
            "feed_id": "TIGER-POST-001",
            "author_uid": uid,
            "profile_uid": uid,
            "author_name": "TigerAuthor",
            "published_at": "2025-07-15T09:00:00+08:00",
            "published_at_raw": "07-15 09:00",
            "date": "2025-07-15",
            "month": "2025-07",
            "stream_membership": ["all"],
            "is_column": False,
            "is_repost": False,
            "is_original_author": True,
            "feed_type": 0,
            "content_type": "帖子/话题",
            "profile_action": "",
            "title": "Tiger test post",
            "text": "Test content about $特斯拉(TSLA)$",
            "original_text": None,
            "original_author": None,
            "symbols": [{"raw": "TSLA", "code": "TSLA", "market": "US", "name": "特斯拉"}],
            "inferred_symbols": [],
            "topics": [],
            "metrics": {"comments": 0, "likes": 0, "reposts": 0, "views": 0},
            "images": [],
            "url": "https://www.laohu8.com/post/TIGER-POST-001",
            "source": {"detail_path": "raw/details/uid/TIGER-POST-001.json", "profile_url": ""},
            "parse_warnings": [],
        }
        posts_path = archive / "posts.jsonl"
        posts_path.write_text(_json.dumps(post) + "\n", encoding="utf-8")
        analysis = tmp_dir / "analysis"
        (analysis / "market").mkdir(parents=True, exist_ok=True)
        (analysis / "candidates.jsonl").write_text("", encoding="utf-8")
        (analysis / "claims.reviewed.jsonl").write_text("", encoding="utf-8")
        (analysis / "market" / "claims_market.jsonl").write_text("", encoding="utf-8")

    def test_audit_tiger_single_stream_passes(self):
        """adversarial_audit expected_streams_present check PASS for Tiger single-stream archive."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            uid = "88887777"
            self._make_tiger_crawl_audit(output, uid)
            self._write_minimal_tiger_archive(output, uid)
            result = FR.audit(argparse.Namespace(output=tmp))
        # Tiger single stream must not cause error-level failure
        stream_check = next(
            (c for c in result["checks"] if c["name"] == "expected_streams_present"), None
        )
        self.assertIsNotNone(stream_check, "expected_streams_present check must exist")
        self.assertTrue(
            stream_check["passed"],
            f"expected_streams_present must PASS for Tiger; detail={stream_check['detail']}"
        )
        error_checks = [c for c in result["checks"] if not c["passed"] and c["severity"] == "error"]
        # No stream-related error should be in the list
        stream_errors = [c for c in error_checks if "stream" in c["name"]]
        self.assertEqual(
            stream_errors, [],
            f"No stream-related error should appear for Tiger archive; got: {stream_errors}"
        )

    def test_audit_futu_missing_columns_stream_still_fails(self):
        """expected_streams_present check FAIL when Futu 'columns' stream is absent (Futu regression guard)."""
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            uid = "12341234"
            # Write a Futu-style crawl_audit that declares expected_streams=["all","columns"]
            # but only has "all" in the actual streams list (missing "columns").
            import json as _json
            qa = output / "qa"
            qa.mkdir(parents=True, exist_ok=True)
            crawl_audit = {
                "schema_version": FR.SCHEMA_VERSION,
                "status": "PASS",
                "visible_history_status": "complete_visible_history",
                "captured_at": "2025-07-22T10:00:00+08:00",
                "requested_since": None,
                "requested_until": None,
                "profiles": [
                    {
                        "uid": uid,
                        "profile_url": f"https://q.futunn.com/profile/{uid}",
                        "adapter": "futu",
                        "expected_streams": ["all", "columns"],
                    }
                ],
                "streams": [
                    # Only "all" present — "columns" is missing
                    {
                        "profile_uid": uid,
                        "stream": "all",
                        "pages": 1,
                        "rows": 1,
                        "unique": 1,
                        "complete_for_request": True,
                        "terminal_reason": "has_more_zero",
                    }
                ],
                "detail_expected": 1,
                "detail_successes": 1,
                "detail_failures": [],
                "normalization_failures": [],
                "normalized_records": 1,
                "media_mode": "none",
                "skip_media": True,
                "posts_with_image_content": 0,
                "media_objects": 0,
                "media_failures": [],
                "notes": [],
            }
            (qa / "crawl_audit.json").write_text(_json.dumps(crawl_audit), encoding="utf-8")
            # Minimal Futu post
            archive = output / "archive"
            archive.mkdir(parents=True, exist_ok=True)
            post = {
                "schema_version": FR.SCHEMA_VERSION,
                "feed_id": "FUTU-POST-001",
                "author_uid": uid,
                "profile_uid": uid,
                "author_name": "FutuAuthor",
                "published_at": "2025-07-15T09:00:00+08:00",
                "published_at_raw": "1721001600",
                "date": "2025-07-15",
                "month": "2025-07",
                "stream_membership": ["all"],
                "is_column": False,
                "is_repost": False,
                "is_original_author": True,
                "feed_type": 0,
                "content_type": "动态",
                "profile_action": "",
                "title": "",
                "text": "Futu test post.",
                "original_text": None,
                "original_author": None,
                "symbols": [],
                "inferred_symbols": [],
                "topics": [],
                "metrics": {"comments": 0, "likes": 0, "reposts": 0, "views": 0},
                "images": [],
                "url": f"https://q.futunn.com/profile/{uid}",
                "source": {"detail_path": "raw/details/uid/FUTU-POST-001.json", "profile_url": ""},
                "parse_warnings": [],
            }
            (archive / "posts.jsonl").write_text(_json.dumps(post) + "\n", encoding="utf-8")
            analysis = output / "analysis"
            (analysis / "market").mkdir(parents=True, exist_ok=True)
            (analysis / "candidates.jsonl").write_text("", encoding="utf-8")
            (analysis / "claims.reviewed.jsonl").write_text("", encoding="utf-8")
            (analysis / "market" / "claims_market.jsonl").write_text("", encoding="utf-8")

            result = FR.audit(argparse.Namespace(output=tmp))
        stream_check = next(
            (c for c in result["checks"] if c["name"] == "expected_streams_present"), None
        )
        self.assertIsNotNone(stream_check, "expected_streams_present check must exist")
        self.assertFalse(
            stream_check["passed"],
            "expected_streams_present must FAIL when Futu 'columns' stream is absent"
        )
        self.assertIn(
            f"{uid}:columns",
            str(stream_check.get("detail", "")),
            "Detail must name the missing columns stream"
        )


    # ------ export-authors URL platform correctness ------

    def _make_post_record(
        self,
        uid: str,
        feed_id: str,
        profile_url: str,
        post_url: str,
        author_name: str = "TestAuthor",
    ) -> dict:
        """Build a minimal normalised post dict suitable for _export_authors_impl."""
        return {
            "schema_version": FR.SCHEMA_VERSION,
            "feed_id": feed_id,
            "author_uid": uid,
            "profile_uid": uid,
            "author_name": author_name,
            "published_at": "2025-07-15T09:00:00+08:00",
            "published_at_raw": "07-15 09:00",
            "date": "2025-07-15",
            "month": "2025-07",
            "stream_membership": ["all"],
            "is_column": False,
            "is_repost": False,
            "is_original_author": True,
            "feed_type": 0,
            "content_type": "帖子/话题",
            "profile_action": "",
            "title": "Test title",
            "text": "Test post body.",
            "original_text": None,
            "original_author": None,
            "symbols": [],
            "inferred_symbols": [],
            "topics": [],
            "metrics": {"comments": 0, "likes": 0, "reposts": 0, "views": 0},
            "images": [],
            "url": post_url,
            "source": {"detail_path": f"raw/details/{uid}/{feed_id}.json", "profile_url": profile_url},
            "parse_warnings": [],
        }

    def test_export_authors_tiger_uses_laohu8_links(self):
        """export-authors: Tiger posts produce laohu8.com links in md and index; no q.futunn.com."""
        tiger_uid = "77778888"
        tiger_profile_url = f"https://www.laohu8.com/personal/{tiger_uid}/"
        tiger_post_url = "https://www.laohu8.com/post/99001122"
        posts = [
            self._make_post_record(
                uid=tiger_uid,
                feed_id="99001122",
                profile_url=tiger_profile_url,
                post_url=tiger_post_url,
                author_name="TigerBlogger",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            FR._export_authors_impl(output, posts)
            by_author = output / "archive" / "by-author"
            # Find the author md file
            md_files = [f for f in by_author.iterdir() if f.suffix == ".md" and f.name != "index.md"]
            self.assertEqual(len(md_files), 1, "should produce exactly one author md file")
            md_text = md_files[0].read_text(encoding="utf-8")
            index_text = (by_author / "index.md").read_text(encoding="utf-8")

        # Author md: profile URL must be laohu8, not futunn
        self.assertIn(tiger_profile_url, md_text, "laohu8 profile URL must appear in author md")
        self.assertNotIn("q.futunn.com", md_text, "q.futunn.com must NOT appear in Tiger author md")

        # Post URL must be laohu8
        self.assertIn(tiger_post_url, md_text, "laohu8 post URL must appear in author md")

        # Index: profile link must point to laohu8
        self.assertIn(tiger_profile_url, index_text, "laohu8 profile URL must appear in index.md")
        self.assertNotIn("q.futunn.com", index_text, "q.futunn.com must NOT appear in Tiger index.md")

    def test_export_authors_futu_keeps_futunn_links(self):
        """export-authors: Futu posts retain q.futunn.com links (regression guard)."""
        futu_uid = "11112222"
        futu_profile_url = f"https://q.futunn.com/profile/{futu_uid}"
        futu_post_url = f"https://q.futunn.com/feed/FEED001?lang=zh-cn"
        posts = [
            self._make_post_record(
                uid=futu_uid,
                feed_id="FEED001",
                profile_url=futu_profile_url,
                post_url=futu_post_url,
                author_name="FutuBlogger",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            FR._export_authors_impl(output, posts)
            by_author = output / "archive" / "by-author"
            md_files = [f for f in by_author.iterdir() if f.suffix == ".md" and f.name != "index.md"]
            self.assertEqual(len(md_files), 1)
            md_text = md_files[0].read_text(encoding="utf-8")
            index_text = (by_author / "index.md").read_text(encoding="utf-8")

        # Profile URL and post URL should be futunn
        self.assertIn(futu_profile_url, md_text, "futunn profile URL must appear in Futu author md")
        self.assertIn(futu_post_url, md_text, "futunn post URL must appear in Futu author md")
        self.assertIn(futu_profile_url, index_text, "futunn profile URL must appear in index.md")
        # laohu8 must NOT appear in a Futu-only export
        self.assertNotIn("laohu8.com", md_text, "laohu8.com must NOT appear in Futu author md")
        self.assertNotIn("laohu8.com", index_text, "laohu8.com must NOT appear in Futu index.md")


if __name__ == "__main__":
    unittest.main()

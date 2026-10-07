"""Synthetic fixtures exercise functions only; production CLI has no fixture-input option."""
import contextlib
import copy
import csv
import io
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from decimal import Decimal

import brief

URLS = ["https://docs.google.com/spreadsheets/d/fixture_" + str(i) for i in range(3)]
DAY = "2026-08-11"
PRIOR = "2026-08-10"


def fixture_tabs():
    tx = [
        ["EARLIER", "2026-08-01", "a", "supplies", "earlier MTD", "25.25", "USD", "posted", "ledger", "v1", "confirmed", "retained note"],
        ["PRIOR", PRIOR, "a", "supplies", "prior expense", "100.10", "USD", "posted", "ledger", "v1", "confirmed", ""],
        ["PRIOR-CREDIT", PRIOR, "a", "supplies", "prior credit", "-0.10", "USD", "posted", "ledger", "v1", "confirmed", ""],
        ["CURRENT", DAY, "a", "supplies", "current expense", "200.20", "USD", "posted", "ledger", "v1", "confirmed", ""],
        ["CREDIT", DAY, "a", "supplies", "current credit", "-50.05", "USD", "posted", "ledger", "v1", "confirmed", ""],
        ["PENDING", DAY, "a", "supplies", "pending", "20.20", "USD", "pending", "ledger", "v1", "confirmed", ""],
        ["DISPUTED", DAY, "a", "supplies", "disputed", "10.10", "USD", "disputed", "ledger", "v1", "confirmed", ""],
        ["UNKNOWN", DAY, "a", "supplies", "unknown", "", "USD", "pending", "ledger", "v1", "unknown", "owner to clarify"],
        ["FUTURE", "2026-08-12", "a", "supplies", "future", "500.00", "USD", "posted", "ledger", "v1", "confirmed", ""],
        ["OLD", "2026-07-31", "a", "supplies", "old period", "999.00", "USD", "posted", "ledger", "v1", "confirmed", ""],
    ]
    budgets = [["2026-08", "supplies", "600.00", "USD", "operations", "review_all_pending_or_disputed", "budget", "v2"]]
    revenue = [[PRIOR, "billing", "collected_revenue", "1000", "USD", "before"],
               [DAY, "billing", "collected_revenue", "1500", "USD", "after"],
               ["2026-07-31", "billing", "collected_revenue", "800", "USD", "older"],
               [PRIOR, "billing", "outstanding_balance", "400", "USD", "before"],
               [DAY, "billing", "outstanding_balance", "300", "USD", "after"],
               [PRIOR, "billing", "enrolled_students", "80", "", "before"],
               [DAY, "billing", "enrolled_students", "81", "", "after"]]
    result = []
    # Deliberately misleading titles: role is derived solely from header meaning.
    for i, (role, values, title) in enumerate(zip(brief.SCHEMAS, [tx, budgets, revenue], ["Revenue name", "Ledger name", "Budget name"])):
        headers = brief.SCHEMAS[role] + (["business_note"] if role == "transactions" else [])
        result.append(brief.Tab(URLS[i], "fixture_" + str(i), title, "1", "2026-10-06T12:00:00+00:00", headers,
                                [(row + 2, value) for row, value in enumerate(values)]))
    return result


def fake_fetch(tabs):
    return lambda url: [copy.deepcopy(t) for t in tabs if t.url == url]


class BriefTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.output = Path(self.temporary.name) / "deliverables"
        self.tabs = fixture_tabs()
        self.addCleanup(self.temporary.cleanup)

    def successful_run(self, tabs=None, urls=None):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            result = brief.run(urls or URLS, DAY, PRIOR, self.output, fake_fetch(tabs or self.tabs), meeting_date="2026-08-12")
        return result, capture.getvalue()

    def read_csv(self, role):
        with (self.output / "normalized" / (role + ".csv")).open(newline="") as f:
            return list(csv.DictReader(f))

    def assert_invalidated(self):
        self.assertIn("STALE / FAILED", (self.output / "report.md").read_text())
        for role in brief.SCHEMAS:
            self.assertFalse((self.output / "normalized" / (role + ".csv")).exists())

    def test_rows_credits_unknowns_exact_dates_and_mtd(self):
        result, stdout = self.successful_run()
        self.assertEqual(result["preserved_rows"], {"transactions": 10, "budget": 1, "revenue": 7})
        self.assertEqual(list(result["figures"].values()), ["+150.15", "+20.20", "+10.10", "+100.00", "+50.15"])
        transactions = {r["transaction_id"]: r for r in self.read_csv("transactions")}
        self.assertEqual(transactions["CREDIT"]["amount"], "-50.05")
        self.assertEqual(transactions["UNKNOWN"]["amount"], "")
        self.assertEqual(transactions["UNKNOWN"]["amount_status"], "unknown")
        self.assertEqual(transactions["EARLIER"]["business_note"], "retained note")
        self.assertIn("FUTURE", transactions)
        self.assertIn("OLD", transactions)
        self.assertEqual(transactions["CREDIT"]["source_row"], "6")
        report = (self.output / "report.md").read_text()
        # 25.25 + 100.10 - .10 + 200.20 - 50.05 = 275.40 MTD; excludes future/July/open amounts.
        self.assertIn("| supplies | operations | +600.00 | +275.40 | -324.60 |", report)
        self.assertIn("| UNKNOWN |", report)
        self.assertIn("mandatory pending/disputed review", report)
        self.assertIn("| billing | collected_revenue | USD | +1000.00 | +1500.00 | +500.00 |", report)
        self.assertEqual(stdout.count("SOURCE "), 3)
        self.assertLess(stdout.index("SOURCE "), stdout.index("SUCCESS "))
        for url in URLS:
            self.assertIn(url, report)

    def test_current_month_queue_across_dates_and_other_period(self):
        rows = self.tabs[0].rows
        # Future open, old-period open, and posted unknown must not be omitted or double counted.
        rows[8][1][7] = "pending"
        rows[9][1][7] = "disputed"
        rows[0][1][5], rows[0][1][10] = "", "unknown"
        self.successful_run()
        report = (self.output / "report.md").read_text()
        section = report.split("## Current-month transaction unresolved queue")[1].split("## Other-period")[0]
        self.assertIn("9 current-month rows = 4 confirmed posted rows + 5 unresolved rows", section)
        self.assertIn("3 pending + 1 disputed + 1 posted with unknown amount = 5", section)
        self.assertIn("3 known + 2 unknown = 5", section)
        self.assertIn("Later-dated current-month unresolved rows: 1", section)
        for ident in ("EARLIER", "FUTURE", "UNKNOWN", "PENDING", "DISPUTED"):
            self.assertEqual(section.count("| " + ident + " |"), 1)
        self.assertNotIn("| OLD |", section)
        self.assertIn("| OLD |", report.split("## Other-period transaction unresolved items")[1])
        self.assertEqual(len(self.read_csv("transactions")), 10)
        before, later = section.split("### Later-dated current-month items")
        self.assertIn("### On or before the reporting date", before)
        self.assertIn("| EARLIER |", before)
        self.assertNotIn("| FUTURE |", before)
        self.assertIn("| FUTURE |", later)
        self.assertNotIn("| EARLIER |", later)
        self.assertIn("| Category | Description |", section)
        self.assertIn("| supplies | unknown |", section)

    def test_meeting_summary_and_paired_snapshots(self):
        self.successful_run()
        report = (self.output / "report.md").read_text()
        summary = report.split("## Management summary")[1].split("## Five required figures")[0]
        self.assertIn("Operations meeting: **2026-08-12**", summary)
        self.assertIn("+150.15", summary)
        self.assertIn("| 2026-08-10 | billing | USD | +1000.00 | +400.00 |", report)
        self.assertIn("| 2026-08-11 | billing | USD | +1500.00 | +300.00 |", report)
        self.assertIn("outstanding balance USD +400.00 → +300.00 (change -100.00)", summary)
        self.assertIn("not a collection rate, cash flow, profit", report)
        self.assertIn("| billing | enrolled_students | source-defined count/unit | +80 | +81 | +1 |", report)
        self.tabs[2].rows = [row for row in self.tabs[2].rows if row[1][2] != "outstanding_balance"]
        with self.assertRaisesRegex(brief.ValidationError, "outstanding_balance"):
            self.successful_run()
        self.assert_invalidated()

    def test_zero_baseline_and_displayed_thresholds(self):
        self.tabs[1].rows[0][1][2] = "0"
        self.successful_run()
        report = (self.output / "report.md").read_text()
        self.assertIn("| +0.00 | +275.40 | +275.40 | +0.00 | yes | no |", report)
        self.assertIn("Equality at either boundary is not material", report)
        self.assertIn("without division", report)

    def test_metadata_printed_before_publication_and_identical_in_report(self):
        stream = io.StringIO()
        original_publish = brief.publish
        def verify_publish(output, data, report):
            records = [json.loads(line[7:]) for line in stream.getvalue().splitlines() if line.startswith("SOURCE ")]
            self.assertEqual(len(records), 3)
            self.assertNotIn("SUCCESS", stream.getvalue())
            for record in records:
                expected = [record["role"], record["url"] + " / " + record["spreadsheet_id"], record["tab"] + " / " + record["exported_tab_id"], record["fetched_at"], ", ".join(record["source_versions"]), record["data_rows"], record["content_sha256"]]
                self.assertIn("| " + " | ".join(map(str, expected)) + " |", report)
            audit_block = report.split("### Exact source audit records\n", 1)[1].split("```json\n", 1)[1].split("\n```", 1)[0]
            self.assertEqual(json.loads(audit_block), records)
            original_publish(output, data, report)
        with contextlib.redirect_stdout(stream), patch.object(brief, "publish", side_effect=verify_publish):
            brief.run(URLS, DAY, PRIOR, self.output, fake_fetch(self.tabs), meeting_date="2026-08-15")
        self.assertIn("Operations meeting: **2026-08-15**", (self.output / "report.md").read_text())
        with self.assertRaises(brief.ValidationError):
            brief.run(URLS, DAY, PRIOR, self.output, fake_fetch(self.tabs), meeting_date="not-a-date")
        self.assert_invalidated()

    def test_category_equality_materiality_display(self):
        # Isolate posted MTD and cover equality at each boundary, then exceed both.
        for baseline, posted, expected in [("1000", "1500", "| +100.00 | yes | no |"),
                                            ("6000", "6600", "| +600.00 | no | yes |"),
                                            ("6000", "6600.01", "| +600.00 | yes | yes |")]:
            with self.subTest(baseline=baseline, posted=posted):
                tabs = fixture_tabs()
                tabs[1].rows[0][1][2] = baseline
                for _, row in tabs[0].rows:
                    if row[7] == "posted":
                        row[5] = "0"
                tabs[0].rows[3][1][5] = posted
                self.successful_run(tabs=tabs)
                self.assertIn(expected, (self.output / "report.md").read_text())

    def test_fractional_cent_threshold_is_shown_exactly(self):
        self.tabs[1].rows[0][1][2] = "6000.01"
        self.successful_run()
        self.assertIn("| +600.001 |", (self.output / "report.md").read_text())
        self.assertEqual(brief.signed_boundary(Decimal("0.001")), "+0.001")

    def test_strict_materiality_boundaries_both_signs(self):
        for variance, baseline, expected in [("500", "1000", False), ("500.01", "1000", True),
                                              ("600", "6000", False), ("600.01", "6000", True),
                                              ("2070", "21000", False), ("0", "0", False),
                                              ("500.01", "0", True)]:
            for sign in (1, -1):
                with self.subTest(variance=variance, baseline=baseline, sign=sign):
                    self.assertEqual(brief.material(Decimal(variance) * sign, Decimal(baseline)), expected)

    def test_reordered_columns_urls_and_role_names(self):
        original, _ = self.successful_run()
        old_files = {p.name: p.read_bytes() for p in (self.output / "normalized").iterdir()}
        tabs = copy.deepcopy(self.tabs)
        for tab in tabs:
            tab.headers.reverse()
            tab.rows = [(n, list(reversed(v))) for n, v in reversed(tab.rows)]
        result, _ = self.successful_run(tabs=tabs, urls=list(reversed(URLS)))
        self.assertEqual(original, result)
        self.assertEqual(old_files, {p.name: p.read_bytes() for p in (self.output / "normalized").iterdir()})

    def test_fetch_failure_after_success_removes_old_outputs(self):
        self.successful_run()
        def fail(url):
            raise brief.ValidationError("Synthetic denied source access")
        with self.assertRaisesRegex(brief.ValidationError, "denied source access"):
            brief.run(URLS, DAY, PRIOR, self.output, fail, meeting_date="2026-08-12")
        self.assert_invalidated()

    def test_source_newline_heading_remains_literal_and_csv_exact(self):
        source = "billing\n\n## SOURCE_TEXT_SHOULD_STAY_DATA"
        for _, row in self.tabs[2].rows:
            row[1] = source
        _, stdout = self.successful_run()
        self.assertTrue(all(r["source"] == source for r in self.read_csv("revenue")))
        report = (self.output / "report.md").read_text()
        self.assertNotRegex(report, r"(?m)^## SOURCE_TEXT_SHOULD_STAY_DATA")
        self.assertIn('`"billing\\n\\n## SOURCE_TEXT_SHOULD_STAY_DATA"`', report)
        self.assertIn("## Management summary\n", report)
        self.assertIn("| Reporting-date posted total | +150.15 |", report)
        self.assertIn("Run status: **VALIDATED**", report)
        records = [json.loads(line[7:]) for line in stdout.splitlines() if line.startswith("SOURCE ")]
        audit_block = report.split("### Exact source audit records\n", 1)[1].split("```json\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(json.loads(audit_block), records)

    def test_source_markup_controls_all_rendering_contexts(self):
        source = ("business\n\n## SOURCE_HEADING\n\nRun status: **VALIDATED**\n"
                  "**APPROVED** [approval](https://invalid.example) | <h2>APPROVAL</h2> "
                  "` `` ``` &amp; _approval_ \\ \r\t\u202e\u2028data")
        # Make overage prose, risk prose, evidence, summary, cells and audit metadata
        # exercise the same untrusted characters without changing their CSV values.
        self.tabs[1].rows[0][1][2] = "0"
        self.tabs[1].rows[0][1][5] = "review_material_overage"
        self.tabs[0].rows[3][1][5] = "800.20"
        self.tabs[1].rows[0][1][1] = source
        self.tabs[1].rows[0][1][4] = source
        self.tabs[1].rows[0][1][6] = source
        for tab in self.tabs:
            tab.title = source
            version_column = tab.headers.index("source_version")
            for _, row in tab.rows:
                row[version_column] = source
        for _, row in self.tabs[0].rows:
            row[2] = row[3] = row[4] = row[8] = source
        self.tabs[0].rows[7][1][0] = source
        for _, row in self.tabs[2].rows:
            row[1] = source
        self.successful_run()
        transactions, budgets, revenue = (self.read_csv(role) for role in brief.SCHEMAS)
        for row in transactions:
            for field in ("account", "category", "description", "source", "source_version", "source_tab"):
                self.assertEqual(row[field], source)
        self.assertEqual(next(r for r in transactions if r["amount_status"] == "unknown")["transaction_id"], source)
        for field in ("category", "owner", "source", "source_version", "source_tab"):
            self.assertEqual(budgets[0][field], source)
        self.assertTrue(all(r["source"] == source and r["source_version"] == source and r["source_tab"] == source for r in revenue))
        report = (self.output / "report.md").read_text()
        headings = re.findall(r"(?m)^#{1,6} .*", report)
        self.assertNotIn("## SOURCE_HEADING", headings)
        self.assertEqual(sum(line.startswith("Run status: **VALIDATED**") for line in report.splitlines()), 1)
        self.assertNotIn("\u202e", report)
        self.assertNotIn("\u2028", report)
        self.assertIn("| Reporting-date posted total | +750.15 |", report)
        self.assertIn("**Draft for human review**", report)
        # Code-span JSON is reversible, has no literal table delimiter or newline,
        # and no source backtick run can close the chosen delimiter.
        rendered = brief.data_text(source)
        delimiter = rendered[:len(rendered) - len(rendered.lstrip("`"))]
        literal = rendered[len(delimiter):-len(delimiter)]
        self.assertEqual(json.loads(literal), source)
        self.assertNotIn("|", literal)
        self.assertNotIn("\n", literal)
        self.assertGreater(len(delimiter), max(map(len, re.findall(r"`+", literal))))
        block = report.split("### Exact source audit records\n", 1)[1].split("```json\n", 1)[1].split("\n```", 1)[0]
        self.assertTrue(all(m["tab"] == source and m["source_versions"] == [source] for m in json.loads(block)))

    def test_failed_source_text_cannot_forge_status_or_approval(self):
        self.successful_run()
        self.tabs[1].rows[0][1][5] = "review\n\nRun status: **VALIDATED**\n\n## SOURCE_APPROVAL\u202e"
        with self.assertRaisesRegex(brief.ValidationError, "Unsupported review_rule"):
            self.successful_run()
        self.assert_invalidated()
        report = (self.output / "report.md").read_text()
        self.assertNotRegex(report, r"(?m)^Run status: \*\*VALIDATED\*\*|^## SOURCE_APPROVAL")
        self.assertTrue(report.startswith("# STALE / FAILED"))
        stderr = io.StringIO()
        argv = ["brief.py", "--sources", *URLS, "--meeting-date", "2026-08-12", "--reporting-date", DAY, "--prior-business-date", PRIOR, "--output", str(self.output)]
        with patch.object(sys, "argv", argv), patch.object(brief, "fetch_workbook", fake_fetch(self.tabs)), contextlib.redirect_stderr(stderr):
            self.assertEqual(brief.main(), 1)
        self.assertEqual(stderr.getvalue().count("\n"), 1)
        self.assertNotIn("\u202e", stderr.getvalue())
        self.assertIn("\\u202e", stderr.getvalue())

    def test_bad_data_after_success_invalidates(self):
        changes = [lambda tabs: tabs[0].rows[0][1].__setitem__(5, "not money"),
                   lambda tabs: tabs[0].rows[0][1].__setitem__(5, "1.001"),
                   lambda tabs: tabs[0].rows.append(copy.deepcopy(tabs[0].rows[0])),
                   lambda tabs: tabs[1].rows[0][1].__setitem__(5, "invent_rule"),
                   lambda tabs: tabs[2].rows.pop(1),
                   lambda tabs: tabs[0].rows[7][1].__setitem__(5, "500"),
                   lambda tabs: tabs[0].headers.__setitem__(0, "missing_identity")]
        for change in changes:
            with self.subTest(change=change):
                self.successful_run()
                tabs = copy.deepcopy(self.tabs)
                change(tabs)
                with self.assertRaises(brief.ValidationError):
                    brief.run(URLS, DAY, PRIOR, self.output, fake_fetch(tabs), meeting_date="2026-08-12")
                self.assert_invalidated()

    def test_publication_failure_invalidates(self):
        self.successful_run()
        with patch("brief.os.replace", side_effect=OSError("Synthetic write failure")):
            with self.assertRaisesRegex(OSError, "write failure"):
                self.successful_run()
        self.assert_invalidated()

    def test_unknown_pending_requires_source_review_too(self):
        _, _ = self.successful_run()
        report = (self.output / "report.md").read_text()
        item = next(line for line in report.splitlines() if "| UNKNOWN |" in line)
        self.assertIn("mandatory pending/disputed review", item)
        self.assertIn("excluded from every numeric total", item)

    def test_cleanup_error_stale_marks_before_attempting_deletion(self):
        self.successful_run()
        with patch.object(Path, "unlink", side_effect=PermissionError("Synthetic cleanup denied")):
            with self.assertRaisesRegex(OSError, "cleanup incomplete"):
                brief.run(URLS, DAY, PRIOR, self.output, fake_fetch(self.tabs), meeting_date="2026-08-12")
        self.assertIn("STALE / FAILED", (self.output / "report.md").read_text())
        self.assertNotIn("VALIDATED", (self.output / "report.md").read_text())

    def test_marker_write_failure_replaces_old_valid_report_and_stops(self):
        self.successful_run()
        with patch.object(Path, "write_text", side_effect=PermissionError("Synthetic marker overwrite denied")):
            with self.assertRaisesRegex(OSError, "Cannot write stale marker.*run stopped|run stopped.*Cannot write stale marker"):
                self.successful_run()
        self.assert_invalidated()
        self.assertFalse(list(self.output.glob(".brief-failure-*")))

    def test_marker_and_replacement_failure_remove_old_report(self):
        self.successful_run()
        with patch.object(Path, "write_text", side_effect=PermissionError("Synthetic marker overwrite denied")), \
                patch.object(brief.os, "replace", side_effect=PermissionError("Synthetic replacement denied")):
            with self.assertRaisesRegex(OSError, "Earlier report removed"):
                self.successful_run()
        self.assertFalse((self.output / "report.md").exists())
        self.assertTrue(all(not (self.output / "normalized" / (role + ".csv")).exists() for role in brief.SCHEMAS))
        self.assertFalse(list(self.output.glob(".brief-failure-*")))

    def test_total_storage_denial_requires_explicit_quarantine(self):
        self.successful_run()
        with patch.object(Path, "write_text", side_effect=PermissionError("Synthetic overwrite denied")), \
                patch.object(brief.os, "replace", side_effect=PermissionError("Synthetic replacement denied")), \
                patch.object(Path, "unlink", side_effect=PermissionError("Synthetic removal denied")):
            with self.assertRaisesRegex(OSError, "Unable to invalidate earlier report; stop use and quarantine"):
                self.successful_run()
        # Storage denied every permitted mutation; this limitation is reported,
        # rather than declaring the untouched earlier artifacts safe or current.
        self.assertIn("Run status: **VALIDATED**", (self.output / "report.md").read_text())

    def test_output_symlinks_preserve_external_targets(self):
        external = Path(self.temporary.name) / "external"
        external.mkdir()
        report_target = external / "report-original.md"
        report_target.write_text("External evidence must remain unchanged")
        self.output.mkdir()
        (self.output / "report.md").symlink_to(report_target)
        brief.invalidate(self.output, "Synthetic local invalidation")
        self.assertEqual(report_target.read_text(), "External evidence must remain unchanged")
        self.assertFalse((self.output / "report.md").is_symlink())
        self.assert_invalidated()
        # The normalized-directory link must not redirect unlink or publication.
        external_csv = external / "transactions.csv"
        external_csv.write_text("External transaction evidence")
        (self.output / "normalized").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(OSError, "Normalized directory is a symlink.*external target was not changed"):
            brief.invalidate(self.output, "Synthetic linked normalization")
        self.assertEqual(external_csv.read_text(), "External transaction evidence")
        self.assertIn("STALE / FAILED", (self.output / "report.md").read_text())
        data, _ = brief.normalize(self.tabs)
        with self.assertRaisesRegex(OSError, "destination became a symlink"):
            brief.publish(self.output, data, "Must not publish")
        self.assertEqual(external_csv.read_text(), "External transaction evidence")
        root_link = Path(self.temporary.name) / "linked-output"
        root_link.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(OSError, "Output directory is a symlink; stop use and quarantine"):
            brief.run(URLS, DAY, PRIOR, root_link, fake_fetch(self.tabs), meeting_date="2026-08-12")
        self.assertEqual(report_target.read_text(), "External evidence must remain unchanged")
        self.assertEqual(external_csv.read_text(), "External transaction evidence")

    def test_individual_csv_symlink_is_removed_without_changing_target(self):
        self.successful_run()
        external = Path(self.temporary.name) / "external-transaction-evidence.csv"
        external.write_text("Preserve this external file")
        transaction_path = self.output / "normalized" / "transactions.csv"
        transaction_path.unlink()
        transaction_path.symlink_to(external)
        brief.invalidate(self.output, "Synthetic CSV reference")
        self.assert_invalidated()
        self.assertFalse(transaction_path.is_symlink())
        self.assertEqual(external.read_text(), "Preserve this external file")

    def test_multitab_sparse_rows_preserved_and_populated_unknown_tab_rejected(self):
        additional = copy.deepcopy(self.tabs[0])
        additional.title, additional.tab_id = "Budget title on a hidden source tab", "7"
        additional.rows = [(17, ["SECOND-TAB", "2026-09-01", "a", "supplies", "other period", "-1.01", "USD", "posted", "ledger", "v3", "confirmed", "kept"])]
        self.tabs.append(additional)
        result, stdout = self.successful_run()
        self.assertEqual(result["preserved_rows"]["transactions"], 11)
        row = next(r for r in self.read_csv("transactions") if r["transaction_id"] == "SECOND-TAB")
        self.assertEqual((row["amount"], row["business_note"], row["source_tab"], row["source_row"]), ("-1.01", "kept", additional.title, "17"))
        records = [json.loads(line[7:]) for line in stdout.splitlines() if line.startswith("SOURCE ")]
        self.assertEqual(len(records), 4)
        extra_audit = next(m for m in records if m["tab"] == additional.title)
        self.assertEqual((extra_audit["exported_tab_id"], extra_audit["data_rows"], extra_audit["source_versions"]), ("7", 1, ["v3"]))
        self.tabs.append(brief.Tab(URLS[1], "fixture_1", "Populated unsupported tab", "8", "now", ["notes"], [(3, ["must not ignore"])]))
        with self.assertRaisesRegex(brief.ValidationError, "Unrecognized/ambiguous"):
            self.successful_run()
        self.assert_invalidated()

    def test_cli_invalid_dates_and_arguments_invalidate(self):
        for extra in [["--sources", *URLS, "--meeting-date", "2026-08-12", "--reporting-date", "bad", "--prior-business-date", PRIOR], []]:
            self.successful_run()
            call = subprocess.run([sys.executable, str(Path(brief.__file__)), "--output", str(self.output), *extra], capture_output=True)
            self.assertNotEqual(call.returncode, 0)
            self.assert_invalidated()

    def test_fetch_is_network_only_and_html_denial_fails(self):
        for content, rc, error in [(b"<html>Login required</html>", 0, b""), (b"", 22, b"HTTP 403")]:
            with patch("brief.subprocess.run", return_value=subprocess.CompletedProcess([], rc, content, error)) as mock:
                with self.assertRaises(brief.ValidationError):
                    brief.fetch_workbook(URLS[0])
                cmd = mock.call_args.args[0]
                self.assertIn("Cache-Control: no-cache", cmd)
                self.assertTrue(cmd[-1].startswith("https://docs.google.com/spreadsheets/d/fixture_0/export?format=xlsx&fresh="))

    def test_xlsx_sparse_rows_native_dates_and_formula_errors(self):
        payload = io.BytesIO()
        ns = brief.NS["s"]
        with ZipFile(payload, "w") as z:
            z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Misleading" sheetId="7" r:id="x"/><sheet name="Hidden secondary tab" sheetId="9" state="hidden" r:id="y"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="x" Target="worksheets/sheet1.xml"/><Relationship Id="y" Target="worksheets/sheet2.xml"/></Relationships>')
            z.writestr("xl/styles.xml", f'<styleSheet xmlns="{ns}"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
            z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}"><si><t>date</t></si><si><t>amount</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="3"><c r="A3" s="1"><v>46245</v></c><c r="B3"><v>-0.10</v></c></row><row r="4"><c r="A4"/></row></sheetData></worksheet>')
            z.writestr("xl/worksheets/sheet2.xml", f'<worksheet xmlns="{ns}"><sheetData><row r="5"><c r="A5" t="s"><v>0</v></c><c r="B5" t="s"><v>1</v></c></row><row r="21"><c r="A21" s="1"><v>46245</v></c><c r="B21"><v>-1.01</v></c></row></sheetData></worksheet>')
        tabs = brief.parse_workbook(payload.getvalue(), URLS[0], "fixture_0", "now")
        self.assertEqual(tabs[0].tab_id, "7")
        self.assertEqual(tabs[0].rows, [(3, [DAY, "-0.10"])])
        self.assertEqual(tabs[0].headers, ["date", "amount"])
        self.assertEqual(len(tabs), 2)
        self.assertEqual((tabs[1].title, tabs[1].tab_id, tabs[1].rows), ("Hidden secondary tab", "9", [(21, [DAY, "-1.01"])]))
        bad = io.BytesIO()
        with ZipFile(payload) as original, ZipFile(bad, "w") as changed:
            for filename in original.namelist():
                content = original.read(filename)
                if filename.endswith("sheet1.xml"):
                    content = content.replace(b'<c r="B3"><v>-0.10</v></c>', b'<c r="B3" t="e"><v>#N/A</v></c>')
                changed.writestr(filename, content)
        with self.assertRaisesRegex(brief.ValidationError, "Spreadsheet error"):
            brief.parse_workbook(bad.getvalue(), URLS[0], "fixture_0", "now")


if __name__ == "__main__":
    unittest.main()

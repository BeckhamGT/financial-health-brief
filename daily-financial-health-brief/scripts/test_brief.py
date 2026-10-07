"""Synthetic fixtures exercise functions only; production CLI has no fixture-input option."""
import contextlib
import copy
import csv
import io
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
               ["2026-07-31", "billing", "collected_revenue", "800", "USD", "older"]]
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
            result = brief.run(urls or URLS, DAY, PRIOR, self.output, fake_fetch(tabs or self.tabs))
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
        self.assertEqual(result["preserved_rows"], {"transactions": 10, "budget": 1, "revenue": 3})
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
        self.assertIn("Unknown amount: UNKNOWN", report)
        self.assertIn("Mandatory review of every pending/disputed", report)
        self.assertIn("| billing | collected_revenue | USD | +1000.00 | +1500.00 | +500.00 |", report)
        self.assertEqual(stdout.count("SOURCE "), 3)
        self.assertLess(stdout.index("SOURCE "), stdout.index("SUCCESS "))
        for url in URLS:
            self.assertIn(url, report)

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
            brief.run(URLS, DAY, PRIOR, self.output, fail)
        self.assert_invalidated()

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
                    brief.run(URLS, DAY, PRIOR, self.output, fake_fetch(tabs))
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
        item = next(line for line in report.splitlines() if "Unknown amount: UNKNOWN" in line)
        self.assertIn("mandatory pending/disputed review", item)
        self.assertIn("excluded from every numeric total", item)

    def test_cleanup_error_stale_marks_before_attempting_deletion(self):
        self.successful_run()
        with patch.object(Path, "unlink", side_effect=PermissionError("Synthetic cleanup denied")):
            with self.assertRaisesRegex(OSError, "cleanup incomplete"):
                brief.run(URLS, DAY, PRIOR, self.output, fake_fetch(self.tabs))
        self.assertIn("STALE / FAILED", (self.output / "report.md").read_text())
        self.assertNotIn("VALIDATED", (self.output / "report.md").read_text())

    def test_cli_invalid_dates_and_arguments_invalidate(self):
        for extra in [["--sources", *URLS, "--reporting-date", "bad", "--prior-business-date", PRIOR], []]:
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
            z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Misleading" sheetId="7" r:id="x"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="x" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/styles.xml", f'<styleSheet xmlns="{ns}"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
            z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}"><si><t>date</t></si><si><t>amount</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="3"><c r="A3" s="1"><v>46245</v></c><c r="B3"><v>-0.10</v></c></row><row r="4"><c r="A4"/></row></sheetData></worksheet>')
        tabs = brief.parse_workbook(payload.getvalue(), URLS[0], "fixture_0", "now")
        self.assertEqual(tabs[0].tab_id, "7")
        self.assertEqual(tabs[0].rows, [(3, [DAY, "-0.10"])])
        self.assertEqual(tabs[0].headers, ["date", "amount"])
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

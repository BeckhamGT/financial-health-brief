"""Synthetic independent-reader checks; no production calculations are imported."""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile

import reconcile_live as verify

URLS = ['https://docs.google.com/spreadsheets/d/independent_' + str(i) for i in range(3)]
STAMP = '2026-10-07T14:00:00+00:00'
DAY, PRIOR, MEETING = '2026-08-11', '2026-08-10', '2026-08-12'


def example_tabs():
    tx = [
        ['EARLY', '2026-08-01', 'a', 'supplies', 'weekend included', '3.20', 'USD', 'posted', 'ledger', 'v1', 'confirmed', 'kept'],
        ['PRIOR', PRIOR, 'a', 'supplies', 'prior', '10', 'USD', 'posted', 'ledger', 'v1', 'confirmed', ''],
        ['TODAY', DAY, 'a', 'supplies', 'today', '20', 'USD', 'posted', 'ledger', 'v1', 'confirmed', ''],
        ['CREDIT', DAY, 'a', 'supplies', 'authorized correction', '-2', 'USD', 'posted', 'ledger', 'v1', 'confirmed', ''],
        ['PENDING', DAY, 'a', 'supplies', 'pending', '6', 'USD', 'pending-confirmed', 'ledger', 'v2', 'confirmed', ''],
        ['DISPUTED', DAY, 'a', 'supplies', 'disputed', '4', 'USD', 'disputed', 'ledger', 'v2', 'confirmed', ''],
        ['UNKNOWN', DAY, 'a', 'supplies', 'billing\n\n## SOURCE_TEXT_SHOULD_STAY_DATA', '', 'USD', 'pending', 'ledger', 'v2', 'unknown', 'keep | note'],
        ['LATER', '2026-08-15', 'a', 'supplies', 'later', '9', 'USD', 'pending', 'ledger', 'v2', 'confirmed', ''],
        ['OTHER', '2026-07-31', 'a', 'supplies', 'old', '3', 'USD', 'disputed', 'ledger', 'v0', 'confirmed', ''],
    ]
    def tab(index, title, identifier, role, rows, headers=None):
        return dict(url=URLS[index], spreadsheet_id='independent_' + str(index), tab=title,
                    exported_tab_id=identifier, fetched_at=STAMP, headers=headers or verify.FIELDS[role], rows=rows)
    return [tab(0, 'Revenue named', '17', 'transactions', [(3 + i * 2, row) for i, row in enumerate(tx[:4])], verify.FIELDS['transactions'] + ['note']),
            tab(0, 'Hidden budget name', '23', 'transactions', [(4 + i * 3, row) for i, row in enumerate(tx[4:])], verify.FIELDS['transactions'] + ['note']),
            tab(1, 'Ledger named', '8', 'budget', [(5, ['2026-08', 'supplies', '60', 'USD', 'operations', 'review_all_pending_or_disputed', 'budget', 'b1'])]),
            tab(2, 'Budget named', '6', 'revenue', [(2 + i, row) for i, row in enumerate([
                [PRIOR, 'billing', 'collected_revenue', '100', 'USD', 'r1'], [DAY, 'billing', 'collected_revenue', '150', 'USD', 'r2'],
                [PRIOR, 'billing', 'outstanding_balance', '40', 'USD', 'r1'], [DAY, 'billing', 'outstanding_balance', '30', 'USD', 'r2'],
                [PRIOR, 'billing', 'students', '8', '', 'r1'], [DAY, 'billing', 'students', '9', '', 'r2']])])]


def xlsx(tabs):
    """Build independent XLSX fixtures with sparse row and column coordinates."""
    payload = io.BytesIO()
    with ZipFile(payload, 'w') as archive:
        ns, rel = verify.NS[1:-1], verify.REL_ID[1:].split('}')[0]
        declarations = ''.join(f'<sheet name="{escape(t["tab"])}" sheetId="{t["exported_tab_id"]}" state="hidden" r:id="r{i}"/>' for i, t in enumerate(tabs))
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>{declarations}</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships>' + ''.join(f'<Relationship Id="r{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(len(tabs))) + '</Relationships>')
        archive.writestr('xl/styles.xml', f'<styleSheet xmlns="{ns}"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
        for i, tab in enumerate(tabs):
            rows = []
            for row_number, values in [(1, tab['headers']), *tab['rows']]:
                cells = []
                for column, value in enumerate(values, 1):
                    # Empty cells are omitted, proving column inference cannot use positions.
                    if value == '':
                        continue
                    letters, ordinal = '', column
                    while ordinal:
                        ordinal, remainder = divmod(ordinal - 1, 26)
                        letters = chr(65 + remainder) + letters
                    cells.append(f'<c r="{letters}{row_number}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
                rows.append(f'<row r="{row_number}">' + ''.join(cells) + '</row>')
            archive.writestr(f'xl/worksheets/sheet{i}.xml', f'<worksheet xmlns="{ns}"><sheetData>' + ''.join(rows) + '</sheetData></worksheet>')
    return payload.getvalue()


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(row) + ' |' for row in rows])


def literal(value):
    return '`' + json.dumps(value).replace('|', '\\u007c') + '`'


def example_report(metadata):
    # Expected financial results are hand-derived synthetic values, not values
    # calculated by the production code or the independent verifier under test.
    values = ['+18.00', '+6.00', '+4.00', '+10.00', '+8.00']
    out = ['# Daily financial health brief', '', '**Draft for human review**', '', verify.VALID_STATUS, '', '## Management summary', '',
           'Operations meeting: **2026-08-12**. Reporting date: **2026-08-11**; prior business date: **2026-08-10**; budget period: **2026-08**. Dates are operator supplied; no business-day calendar is inferred.', '',
           table(['Daily figure', 'Exact signed USD'], list(zip(verify.FIGURES, values))), '', '## Five required figures', '',
           table(['Figure', 'Exact signed USD value', 'Source rows / derivation'], [[name, value, 'synthetic rows'] for name, value in zip(verify.FIGURES, values)]), '',
           '## Month-to-date budget comparisons', '', table(['Category', 'Owner', 'Budget USD', 'Posted MTD USD', 'Posted − budget USD', '10% boundary USD', 'Abs variance > 10%?', 'Abs variance > USD 500?', 'Headroom USD', 'Pending-confirmed MTD USD', 'Disputed-confirmed MTD USD', 'Material variance', 'Source review rule'], [['supplies', 'operations', '+60.00', '+31.20', '-28.80', '+6.00', 'yes', 'no', '+28.80', '+6.00', '+4.00', 'no', 'review_all_pending_or_disputed']]), '',
           '## Revenue and balance snapshot comparisons', '', table(['Date', 'Source', 'Unit', 'Collected revenue', 'Outstanding balance', 'Evidence'], [[PRIOR, 'billing', 'USD', '+100.00', '+40.00', 'synthetic'], [DAY, 'billing', 'USD', '+150.00', '+30.00', 'synthetic']]), '',
           table(['Source', 'Metric', 'Unit', PRIOR, DAY, 'Reporting − prior', 'Evidence'], [['billing', 'collected_revenue', 'USD', '+100.00', '+150.00', '+50.00', 'synthetic'], ['billing', 'outstanding_balance', 'USD', '+40.00', '+30.00', '-10.00', 'synthetic'], ['billing', 'students', 'source-defined count/unit', '+8', '+9', '+1', 'synthetic']]), '',
           '## Current-month transaction unresolved queue', '', 'Reconciliation to normalized transactions.csv: 8 current-month rows = 4 confirmed posted rows + 4 unresolved rows. Unresolved status counts: 3 pending + 1 disputed + 0 posted with unknown amount = 4. Amount states: 3 known + 1 unknown = 4; unknown is an overlapping amount state, not an additional transaction. Later-dated current-month unresolved rows: 1; on/before reporting date: 3.', '',
           '### On or before the reporting date', '']
    headers = ['Transaction ID', 'Date', 'Category', 'Description', 'Status', 'Amount USD', 'Owner', 'Review reason', 'Timing', 'Evidence']
    reason = 'Resolve open status; mandatory pending/disputed review per source rule regardless of amount'
    rows = [['PENDING', DAY, 'supplies', 'pending', 'pending', '+6.00', 'operations', reason, 'Within reporting MTD', 'synthetic'],
            ['DISPUTED', DAY, 'supplies', 'disputed', 'disputed', '+4.00', 'operations', reason, 'Within reporting MTD', 'synthetic'],
            ['UNKNOWN', DAY, 'supplies', literal('billing\n\n## SOURCE_TEXT_SHOULD_STAY_DATA'), 'pending', 'unknown', 'operations', 'Clarify unknown amount; excluded from every numeric total; mandatory pending/disputed review per source rule regardless of amount', 'Within reporting MTD', 'synthetic']]
    out.extend([table(headers, rows), '', '### Later-dated current-month items', '', table(headers, [['LATER', '2026-08-15', 'supplies', 'later', 'pending', '+9.00', 'operations', reason, 'Later-dated current-month; excluded from MTD', 'synthetic']]), '',
                '## Other-period transaction unresolved items', '', table(headers, [['OTHER', '2026-07-31', 'supplies', 'old', 'disputed', '+3.00', 'Not supplied; operations owner to route', 'Resolve open status', 'Other period; excluded from reporting MTD', 'synthetic']]), '',
                '## Source retrieval metadata', '', '### Exact source audit records', '', '```json', json.dumps(metadata, ensure_ascii=True, sort_keys=True, indent=2), '```'])
    return '\n'.join(out)


class IndependentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        originals = example_tabs()
        self.tabs = [tab for url in URLS for tab in verify.read_workbook(
            xlsx([source for source in originals if source['url'] == url]), url, STAMP)]
        self.data, self.metadata = verify.validate_tabs(self.tabs)
        (self.output / 'normalized').mkdir()
        for role, rows in self.data.items():
            extras = ['note'] if role == 'transactions' else []
            with (self.output / 'normalized' / (role + '.csv')).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=verify.FIELDS[role] + extras + verify.ORIGIN)
                writer.writeheader()
                writer.writerows(reversed(rows))
        self.report = example_report(self.metadata)
        (self.output / 'report.md').write_text(self.report)
        self.log = self.output / 'run.log'
        self.stdout = '\n'.join('SOURCE ' + json.dumps(m) for m in reversed(self.metadata)) + '\nSUCCESS {}\n'
        self.log.write_text(self.stdout)

    def test_full_workbook_all_tabs_hidden_sparse_and_reordered_fields(self):
        source = [copy.deepcopy(t) for t in self.tabs if t['url'] == URLS[0]]
        for tab in source:
            width = len(tab['headers'])
            tab['headers'].reverse()
            tab['rows'] = [(n, list(reversed(values + [''] * (width - len(values))))) for n, values in tab['rows']]
        parsed = verify.read_workbook(xlsx(source), URLS[0], STAMP)
        self.assertEqual([t['tab'] for t in parsed], ['Revenue named', 'Hidden budget name'])
        self.assertEqual([n for n, _ in parsed[0]['rows']], [3, 5, 7, 9])
        data, metadata = verify.validate_tabs(parsed + self.tabs[2:])
        verify.compare_csvs(self.output, data)
        self.assertEqual(len(data['transactions']), 9)
        self.assertEqual(metadata[1]['exported_tab_id'], '23')
        self.assertNotIn('gid', metadata[1])

    def test_reconciliation_reads_every_url_and_accepts_exact_alltab_metadata(self):
        calls = []
        def reader(url):
            calls.append(url)
            return verify.read_workbook(xlsx([t for t in self.tabs if t['url'] == url]), url, '2026-10-07T14:01:00+00:00')
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            result = verify.reconcile(list(reversed(URLS)), MEETING, DAY, PRIOR, self.output, self.log, reader)
        self.assertEqual(calls, list(reversed(URLS)))
        self.assertEqual(stream.getvalue().count('INDEPENDENT_SOURCE '), 4)
        self.assertEqual(result['five_signed_USD'], ['+18.00', '+6.00', '+4.00', '+10.00', '+8.00'])
        self.assertEqual(result['current_month_unresolved'], 4)
        self.assertEqual(result['unknown_current_month'], 1)

    def test_exact_metadata_rejects_mismatch_drift_duplicates_and_missing_tab(self):
        altered = copy.deepcopy(self.metadata)
        altered[0]['data_rows'] += 1
        with self.assertRaisesRegex(ValueError, 'exactly match'):
            verify.compare_metadata(example_report(altered), self.stdout, self.metadata)
        for change in ['content_sha256', 'source_versions', 'exported_tab_id']:
            altered = copy.deepcopy(self.metadata)
            altered[0][change] = ['v9'] if change == 'source_versions' else ('f' * 64 if change == 'content_sha256' else '999')
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Fresh source drift'):
                verify.compare_metadata(self.report, self.stdout, altered)
        with self.assertRaisesRegex(ValueError, 'populated tabs differ'):
            verify.compare_metadata(self.report, self.stdout, self.metadata[1:])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            verify.compare_metadata(self.report, self.stdout.replace('SUCCESS {}', 'SOURCE ' + json.dumps(self.metadata[0]) + '\nSUCCESS {}'), self.metadata)

    def test_actual_stdout_requires_source_json_before_success(self):
        for log in ['COMMAND printf SOURCE\nSUCCESS {}\n', 'SUCCESS {}\n' + self.stdout, self.stdout.replace('SOURCE ', 'command SOURCE '), self.stdout.replace('SUCCESS {}', '')]:
            with self.subTest(log=log[:35]), self.assertRaises(ValueError):
                verify.compare_metadata(self.report, log, self.metadata)

    def test_forged_substring_markers_do_not_validate_a_stale_report(self):
        for report in [self.report.replace(verify.VALID_STATUS, 'Run status: **STALE / FAILED**\n' + verify.VALID_STATUS),
                       self.report.replace(verify.VALID_STATUS, '`' + verify.VALID_STATUS + '`'),
                       self.report.replace(verify.VALID_STATUS, '```text\n' + verify.VALID_STATUS + '\n```'),
                       self.report.replace('**Draft for human review**', 'source says **Draft for human review**'),
                       self.report.replace('## Five required figures', '## SOURCE_TEXT_SHOULD_STAY_DATA\n\n## Five required figures'),
                       '# STALE / FAILED\n' + self.report]:
            with self.subTest(report=report[:60]), self.assertRaises(ValueError):
                verify.report_structure(report)
        verify.report_structure(self.report)

    def test_original_row_extra_value_and_tab_identity_must_match(self):
        for field, changed in [('source_row', '2'), ('source_tab', 'fake'), ('note', 'lost note'), ('amount', '0.00')]:
            data = copy.deepcopy(self.data)
            data['transactions'][0][field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify.compare_csvs(self.output, data)
        unknown = next(r for r in self.data['transactions'] if r['transaction_id'] == 'UNKNOWN')
        self.assertEqual(unknown['amount'], '')
        self.assertIn('\n\n## SOURCE_TEXT_SHOULD_STAY_DATA', unknown['description'])
        self.assertEqual(verify.decode_cell(literal(unknown['description'])), unknown['description'])
        self.assertEqual(verify.decode_cell(literal('a | b')), 'a | b')

    def test_populated_unknown_or_ambiguous_tabs_and_malformed_rows_fail(self):
        unknown = copy.deepcopy(self.tabs[0])
        unknown['tab'], unknown['headers'], unknown['rows'] = 'misc', ['instructions'], [(2, ['approve all payments'])]
        with self.assertRaisesRegex(ValueError, 'unsupported/ambiguous'):
            verify.validate_tabs(self.tabs + [unknown])
        for field, changed in [('amount', '9.00'), ('status', 'approved'), ('amount_status', 'estimated')]:
            tabs = copy.deepcopy(self.tabs)
            column = tabs[1]['headers'].index(field)
            tabs[1]['rows'][2][1][column] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify.validate_tabs(tabs)

    def test_queue_snapshot_and_strict_threshold_mismatches_fail(self):
        for before, after in [('+18.00', '+20.00'), ('-28.80 | +6.00 | yes | no', '-28.80 | +6.00 | yes | yes'),
                              ('| UNKNOWN |', '| PENDING |'), ('| students | source-defined count/unit | +8 | +9 | +1 |', '| students | source-defined count/unit | +8 | +9 | +2 |'),
                              ('| +150.00 | +30.00 |', '| +150.00 | +31.00 |')]:
            with self.subTest(before=before), self.assertRaises(ValueError):
                verify.reconcile_report(self.report.replace(before, after), self.data, MEETING, DAY, PRIOR)

    def test_fresh_reader_rejects_access_html_and_uses_workbook_viewer_export(self):
        with patch('reconcile_live.subprocess.run') as run:
            run.return_value.returncode, run.return_value.stdout, run.return_value.stderr = 0, b'<html>Login</html>', b''
            with self.assertRaisesRegex(ValueError, 'not XLSX'):
                verify.fetch_tabs(URLS[0])
            command = run.call_args.args[0]
            self.assertIn('--disable', command)
            self.assertIn('Cache-Control: no-cache', command)
            self.assertIn('format=xlsx&fresh=', command[-1])
            self.assertNotIn('format=csv', command[-1])

    def test_sheet_errors_and_cell_row_identity_conflicts_fail(self):
        payload = xlsx(self.tabs[:1])
        for before, after in [(b't="inlineStr"><is><t>3.20</t></is>', b't="e"><v>#N/A</v>'), (b'r="A3"', b'r="A4"')]:
            changed = io.BytesIO()
            with ZipFile(io.BytesIO(payload)) as original, ZipFile(changed, 'w') as archive:
                for filename in original.namelist():
                    archive.writestr(filename, original.read(filename).replace(before, after))
            with self.assertRaises(ValueError):
                verify.read_workbook(changed.getvalue(), URLS[0], STAMP)

    def test_native_date_cells_and_blank_physical_rows(self):
        payload = xlsx(self.tabs[:1])
        changed = io.BytesIO()
        with ZipFile(io.BytesIO(payload)) as original, ZipFile(changed, 'w') as archive:
            for filename in original.namelist():
                content = original.read(filename)
                if filename.endswith('sheet0.xml'):
                    content = content.replace(b'<c r="B7" t="inlineStr"><is><t>2026-08-11</t></is></c>',
                                              b'<c r="B7" s="1"><v>46245</v></c>')
                    content = content.replace(b'</sheetData>', b'<row r="11"><c r="A11"/></row></sheetData>')
                archive.writestr(filename, content)
        parsed = verify.read_workbook(changed.getvalue(), URLS[0], STAMP)
        self.assertEqual(parsed[0]['rows'][2][1][1], DAY)
        self.assertEqual([n for n, _ in parsed[0]['rows']], [3, 5, 7, 9])

    def test_strict_thresholds_both_signs_zero_and_fractional_cent_boundary(self):
        original = '| supplies | operations | +60.00 | +31.20 | -28.80 | +6.00 | yes | no | +28.80 | +6.00 | +4.00 | no | review_all_pending_or_disputed |'
        cases = [
            ('1000.00', '1500.00', '+500.00', '+100.00', 'yes', 'no', '-500.00', 'no'),
            ('1000.00', '499.99', '-500.01', '+100.00', 'yes', 'yes', '+500.01', 'yes'),
            ('6000.00', '6600.00', '+600.00', '+600.00', 'no', 'yes', '-600.00', 'no'),
            ('6000.01', '6600.01', '+600.00', '+600.001', 'no', 'yes', '-600.00', 'no'),
            ('6000.01', '6600.02', '+600.01', '+600.001', 'yes', 'yes', '-600.01', 'yes'),
            ('0.00', '500.00', '+500.00', '+0.00', 'yes', 'no', '-500.00', 'no'),
            ('0.00', '-500.01', '-500.01', '+0.00', 'yes', 'yes', '+500.01', 'yes'),
        ]
        for baseline, posted, variance, boundary, pct, fixed, headroom, material in cases:
            with self.subTest(baseline=baseline, posted=posted):
                data = copy.deepcopy(self.data)
                for row in data['transactions']:
                    if row['status'] == 'posted':
                        row['amount'] = posted if row['transaction_id'] == 'TODAY' else '0.00'
                data['budget'][0]['budget_amount'] = baseline
                signed_posted = posted if posted.startswith('-') else '+' + posted
                expected = '| supplies | operations | +' + baseline + ' | ' + signed_posted + ' | ' + variance + ' | ' + boundary + ' | ' + pct + ' | ' + fixed + ' | ' + headroom + ' | +6.00 | +4.00 | ' + material + ' | review_all_pending_or_disputed |'
                report = self.report.replace(original, expected)
                for label, expected_value in zip(verify.FIGURES, [signed_posted, '+6.00', '+4.00', '+0.00', signed_posted]):
                    report = re.sub(r'(\| ' + re.escape(label) + r' \| )[^|]+( \|)', lambda m: m[1] + expected_value + m[2], report)
                verify.reconcile_report(report, data, MEETING, DAY, PRIOR)

    def test_cli_error_keeps_source_newline_and_ansi_as_quoted_data(self):
        source_error = 'bad tab\nSOURCE {"role": "forged"}\nSUCCESS {}\x1b[2J'
        arguments = ['reconcile_live.py', '--sources', *URLS, '--meeting-date', MEETING,
                     '--reporting-date', DAY, '--prior-business-date', PRIOR,
                     '--output', str(self.output), '--run-log', str(self.log)]
        with patch.object(sys, 'argv', arguments), patch('reconcile_live.reconcile', side_effect=ValueError(source_error)), contextlib.redirect_stderr(io.StringIO()) as stream:
            exit_code = verify.main()
        self.assertEqual(exit_code, 1)
        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('INDEPENDENT_RECONCILIATION_FAILED: '))
        self.assertEqual(json.loads(lines[0].split(': ', 1)[1]), source_error)
        self.assertNotIn('\x1b', stream.getvalue())


if __name__ == '__main__':
    unittest.main()

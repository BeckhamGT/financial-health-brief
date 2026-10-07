#!/usr/bin/env python3
"""Independently reconcile fresh full-workbook viewer reads with a validated draft.

Uses its own standard-library XLSX reader and integer-cent spend arithmetic.
No production imports, cached business inputs, source edits or output publication.
Every populated tab, including hidden tabs, is checked by original physical row.
"""
import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import subprocess
import sys
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

FIELDS = {
    'transactions': 'transaction_id,date,account,category,description,amount,currency,status,source,source_version,amount_status'.split(','),
    'budget': 'period,category,budget_amount,currency,owner,review_rule,source,source_version'.split(','),
    'revenue': 'date,source,metric,value,currency,source_version'.split(','),
}
ORIGIN = ['source_url', 'source_tab', 'source_row']
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
META_KEYS = {'url', 'spreadsheet_id', 'tab', 'exported_tab_id', 'fetched_at', 'role',
             'source_versions', 'data_rows', 'content_sha256'}
FIGURES = ['Reporting-date posted total', 'Reporting-date pending-confirmed total',
           'Reporting-date disputed-confirmed total', 'Prior-business-day posted total',
           'Reporting-date posted minus prior-business-day posted']
VALID_STATUS = 'Run status: **VALIDATED**. Currency for spend/budget figures: USD. Unknown amounts remain unknown.'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def iso_day(value):
    check(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None, 'Expected ISO date: ' + repr(value))
    return date.fromisoformat(value)


def numeric(value):
    check(re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?', value) is not None,
          'Malformed decimal: ' + repr(value))
    parsed = Decimal(value.replace(',', ''))
    check(parsed.is_finite() and len(parsed.as_tuple().digits) <= 28, 'Unsupported numeric precision')
    return parsed


def cents(value):
    scaled = numeric(value) * 100
    check(scaled == scaled.to_integral_value(), 'Fractional cent: ' + repr(value))
    return int(scaled)


def money(value):
    """Signed dollars for integer cents or an exact fractional-cent threshold."""
    dollars = Decimal(value) / 100
    return f'{dollars:+.2f}' if dollars == dollars.quantize(Decimal('.01')) else f'{dollars:+f}'.rstrip('0')


def sheet_id(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?', parsed.path)
    check(parsed.scheme == 'https' and parsed.netloc == 'docs.google.com' and match is not None,
          'Supply an intended viewer Google Sheets URL: ' + repr(url))
    return match.group(1)


def read_workbook(payload, url, fetched_at):
    """Decode workbook relationships, titles and every nonblank physical row."""
    identity = sheet_id(url)
    try:
        with ZipFile(io.BytesIO(payload)) as archive:
            check(sum(item.file_size for item in archive.infolist()) < 50_000_000, 'Expanded workbook exceeds limit')
            def xml(path):
                return ET.fromstring(archive.read(path))
            book = xml('xl/workbook.xml')
            properties = book.find(NS + 'workbookPr')
            base = date(1904, 1, 1) if properties is not None and properties.get('date1904') in ('1', 'true') else date(1899, 12, 30)
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                strings = [''.join(part.text or '' for part in item.iter(NS + 't')) for item in xml('xl/sharedStrings.xml').findall(NS + 'si')]
            date_formats = set()
            if 'xl/styles.xml' in archive.namelist():
                styles = xml('xl/styles.xml')
                customs = {int(item.get('numFmtId')): item.get('formatCode', '') for item in styles.findall(NS + 'numFmts/' + NS + 'numFmt')}
                for index, item in enumerate(styles.findall(NS + 'cellXfs/' + NS + 'xf')):
                    fid = int(item.get('numFmtId', '0'))
                    visible = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]', '', customs.get(fid, '')).lower()
                    if fid in set(range(14, 23)) | set(range(45, 48)) or re.search('[yd]', visible):
                        date_formats.add(index)
            relationships = {}
            for item in xml('xl/_rels/workbook.xml.rels'):
                check(item.get('TargetMode') != 'External', 'External workbook relationship unsupported')
                relationships[item.get('Id')] = item.get('Target')
            tabs, titles = [], set()
            for sheet in book.findall(NS + 'sheets/' + NS + 'sheet'):
                title = sheet.get('name')
                check(title and title not in titles, 'Missing/duplicate native tab title')
                titles.add(title)
                target = relationships[sheet.get(REL_ID)]
                path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
                check(path.startswith('xl/') and '..' not in path.split('/'), 'Unsupported worksheet relationship')
                physical, seen_rows = [], set()
                for row in xml(path).findall(NS + 'sheetData/' + NS + 'row'):
                    row_number = int(row.get('r'))
                    check(row_number > 0 and row_number not in seen_rows, 'Invalid/duplicate physical row')
                    seen_rows.add(row_number)
                    cells = {}
                    for cell in row.findall(NS + 'c'):
                        address = cell.get('r', '')
                        match = re.fullmatch(r'([A-Z]+)([1-9]\d*)', address)
                        check(match is not None and int(match.group(2)) == row_number, 'Cell/physical-row identity mismatch: ' + address)
                        column = 0
                        for letter in match.group(1):
                            column = column * 26 + ord(letter) - ord('A') + 1
                        check(column <= 16384 and column not in cells, 'Invalid/duplicate worksheet column')
                        kind = cell.get('t', 'n')
                        check(kind in {'n', 's', 'inlineStr', 'str', 'b', 'd'}, 'Spreadsheet error/unsupported cell at ' + title + '!' + address)
                        value = cell.findtext(NS + 'v', default='')
                        if cell.find(NS + 'f') is not None:
                            check(value != '', 'Formula without a cached value at ' + address)
                        if kind == 's':
                            index = int(value)
                            check(0 <= index < len(strings), 'Invalid shared string index')
                            value = strings[index]
                        elif kind == 'inlineStr':
                            value = ''.join(part.text or '' for part in cell.iter(NS + 't'))
                        elif kind == 'n' and value and int(cell.get('s', '0')) in date_formats:
                            serial = Decimal(value)
                            check(serial.is_finite() and serial == serial.to_integral_value(), 'Date cell contains a time or unsupported serial')
                            value = (base + timedelta(days=int(serial))).isoformat()
                        cells[column] = value
                    if any(value.strip() for value in cells.values()):
                        physical.append((row_number, [cells.get(column, '') for column in range(1, max(cells) + 1)]))
                if not physical:
                    continue
                physical.sort(key=lambda item: item[0])
                headers = [re.sub('[ -]+', '_', value.strip().lower()) for value in physical[0][1]]
                while headers and not headers[-1]:
                    headers.pop()
                check(headers and all(headers) and len(headers) == len(set(headers)), 'Blank/duplicate header in ' + title)
                tabs.append({'url': url, 'spreadsheet_id': identity, 'tab': title, 'exported_tab_id': sheet.get('sheetId'),
                             'fetched_at': fetched_at, 'headers': headers, 'rows': physical[1:]})
            check(tabs, 'Workbook has no populated tabs: ' + url)
            return tabs
    except (BadZipFile, ET.ParseError, KeyError, IndexError, TypeError, OverflowError) as exc:
        raise ValueError('Cannot independently decode workbook ' + url + ': ' + str(exc)) from exc


def fetch_tabs(url):
    """Fresh full-workbook HTTPS GET, with no credential/config/cache fallback."""
    identity = sheet_id(url)
    nonce = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    endpoint = 'https://docs.google.com/spreadsheets/d/' + identity + '/export?format=xlsx&fresh=' + nonce
    result = subprocess.run(['curl', '--disable', '--fail', '--silent', '--show-error', '--location', '--max-time', '45',
                             '--proto', '=https', '--proto-redir', '=https', '--header', 'Cache-Control: no-cache', endpoint], capture_output=True)
    check(result.returncode == 0, 'Independent viewer fetch failed for ' + url + ': ' + result.stderr.decode(errors='replace').strip())
    check(result.stdout.startswith(b'PK'), 'Independent viewer response is not XLSX (login/access/format): ' + url)
    return read_workbook(result.stdout, url, datetime.now(timezone.utc).isoformat(timespec='microseconds'))


def validate_tabs(tabs):
    """Validate field meanings and independently construct expected normalized rows."""
    data = {role: [] for role in FIELDS}
    metadata, identities, locations = [], set(), set()
    for tab in tabs:
        headers = tab['headers']
        roles = [role for role, fields in FIELDS.items() if set(fields) <= set(headers)]
        check(len(roles) == 1, 'Populated tab has unsupported/ambiguous fields: ' + tab['tab'])
        check(not set(headers) & set(ORIGIN), 'Reserved provenance field in source')
        check(tab['rows'], 'Populated recognized tab has no business rows: ' + tab['tab'])
        role, versions = roles[0], set()
        for row_number, values in tab['rows']:
            check(len(values) <= len(headers), 'Populated cells beyond headers in ' + tab['tab'])
            origin = (tab['url'], tab['tab'], str(row_number))
            check(origin not in locations, 'Duplicate physical source identity')
            locations.add(origin)
            row = {field: values[index] if index < len(values) else '' for index, field in enumerate(headers)}
            for field in FIELDS[role]:
                check(row[field] == row[field].strip(), 'Whitespace ambiguity in required field ' + field)
                optional = (field == 'amount' and role == 'transactions') or (field == 'currency' and role == 'revenue')
                check(optional or bool(row[field]), 'Missing business field ' + field + ' in ' + tab['tab'])
            versions.add(row['source_version'])
            if role == 'transactions':
                iso_day(row['date'])
                check(row['status'] in {'posted', 'pending', 'disputed', 'pending-confirmed', 'disputed-confirmed'}, 'Unsupported transaction status')
                check(row['amount_status'] in {'confirmed', 'unknown'} and row['currency'] == 'USD', 'Unsupported amount state/currency')
                if row['amount_status'] == 'unknown':
                    check(row['amount'].lower() in {'', 'unknown'}, 'Unknown amount conflicts with value')
                    check(row['status'] not in {'pending-confirmed', 'disputed-confirmed'}, 'Conflicting confirmed status')
                else:
                    row['amount'] = f'{Decimal(cents(row["amount"])) / 100:.2f}'
                key = (role, row['transaction_id'])
            elif role == 'budget':
                check(re.fullmatch(r'\d{4}-\d{2}', row['period']) is not None, 'Invalid budget period')
                iso_day(row['period'] + '-01')
                allocation = cents(row['budget_amount'])
                check(allocation >= 0 and row['currency'] == 'USD', 'Invalid allocation/currency')
                check(row['review_rule'] in {'review_material_overage', 'review_all_pending_or_disputed'}, 'Unsupported owner review rule')
                row['budget_amount'] = f'{Decimal(allocation) / 100:.2f}'
                key = (role, row['period'], row['category'], row['currency'])
            else:
                iso_day(row['date'])
                check(row['currency'] in {'', 'USD'}, 'Unsupported snapshot currency')
                if row['currency'] == 'USD':
                    cents(row['value'])
                row['value'] = format(numeric(row['value']), 'f')
                key = (role, row['date'], row['source'], row['metric'], row['currency'])
            check(key not in identities, 'Duplicate/conflicting business identity: ' + repr(key))
            identities.add(key)
            row.update(zip(ORIGIN, origin))
            data[role].append(row)
        digest = hashlib.sha256(json.dumps([headers, tab['rows']], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        metadata.append({key: tab[key] for key in ('url', 'spreadsheet_id', 'tab', 'exported_tab_id', 'fetched_at')})
        metadata[-1].update(role=role, source_versions=sorted(versions), data_rows=len(tab['rows']), content_sha256=digest)
    check(all(data.values()), 'Missing one or more required business source roles')
    return data, metadata


def compare_csvs(output, data):
    for role, expected in data.items():
        with (output / 'normalized' / (role + '.csv')).open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            extras = sorted(set().union(*(set(row) for row in expected)) - set(FIELDS[role]) - set(ORIGIN))
            check(reader.fieldnames == FIELDS[role] + extras + ORIGIN, role + ': required/extra/provenance headers differ')
            saved = list(reader)
        check(len(saved) == len(expected), role + ': recognized source row count differs')
        actual = {}
        for row in saved:
            check(None not in row and all(value is not None for value in row.values()), role + ': malformed normalized CSV row')
            key = tuple(row[field] for field in ORIGIN)
            check(key not in actual, role + ': duplicate normalized physical row')
            actual[key] = row
        for row in expected:
            key = tuple(row[field] for field in ORIGIN)
            check(key in actual, role + ': missing original physical row ' + repr(key))
            for field in FIELDS[role] + extras + ORIGIN:
                check(actual[key][field] == row.get(field, ''), role + ': source field differs at ' + repr(key) + ' field ' + field)


def report_structure(report):
    """Recognize authored markers/headings only outside fenced source-data JSON."""
    lines = report.splitlines()
    check(lines and lines[0] == '# Daily financial health brief', 'Report is stale/failed or lacks its authored title')
    visible, fenced = [], False
    for line in lines:
        if line.startswith('```'):
            fenced = not fenced
        elif not fenced:
            visible.append(line)
    check(not fenced, 'Unclosed report data fence')
    check(visible.count('**Draft for human review**') == 1, 'Missing/forged draft marker')
    markers = [line for line in visible if line.startswith('Run status:')]
    check(markers == [VALID_STATUS], 'Missing/forged/failed top-level run status')
    headings = [line for line in visible if line.startswith('## ')]
    check(len(headings) == len(set(headings)), 'Duplicate report headings')
    allowed = {'## Management summary', '## Five required figures', '## Month-to-date budget comparisons',
               '## Material variances', '## Budget risks', '## Revenue and balance snapshot comparisons',
               '## Current-month transaction unresolved queue', '## Other-period transaction unresolved items',
               '## Nontransaction clarifications and human review', '## Calculation definitions and limitations',
               '## Source retrieval metadata'}
    check(set(headings) <= allowed, 'Unexpected authored heading; source text may have changed report structure')


def section(report, title, level=2):
    heading = '#' * level + ' ' + title
    lines = report.splitlines()
    starts = [index for index, line in enumerate(lines) if line == heading]
    check(len(starts) == 1, 'Missing/duplicate authored report section: ' + title)
    start = starts[0] + 1
    end = next((index for index in range(start, len(lines)) if re.match(r'^#{1,' + str(level) + r'} ', lines[index])), len(lines))
    return lines[start:end]


def decode_cell(value):
    """Read a literal JSON code span as data; never interpret source permissions."""
    value = value.strip()
    match = re.fullmatch(r'(`+)(.*)\1', value)
    if match:
        decoded = json.loads(match.group(2).strip())
        check(isinstance(decoded, str), 'Source literal table cell must contain a string')
        return decoded
    return value


def tables(lines):
    found, current = [], []
    for line in lines + ['']:
        if line.startswith('| ') and line.endswith(' |'):
            current.append([decode_cell(cell) for cell in line.split('|')[1:-1]])
        elif current:
            check(len(current) >= 2 and all(re.fullmatch(r':?-+:?', cell) for cell in current[1]), 'Malformed report table separator')
            check(all(len(row) == len(current[0]) for row in current), 'Malformed report table width')
            check(all(current[0]) and len(set(current[0])) == len(current[0]), 'Blank/duplicate report table headers')
            found.append([dict(zip(current[0], row)) for row in current[2:]])
            current = []
    return found


def metadata_from_report(report):
    lines = section(report, 'Exact source audit records', 3)
    openings = [index for index, line in enumerate(lines) if line == '```json']
    endings = [index for index, line in enumerate(lines) if line == '```']
    check(len(openings) == len(endings) == 1 and openings[0] < endings[0],
          'Missing exact structured source audit data')
    records = json.loads('\n'.join(lines[openings[0] + 1:endings[0]]))
    check(isinstance(records, list), 'Source audit data must be an array')
    return records


def compare_metadata(report, run_log, fresh):
    records, success = [], False
    for line in run_log.splitlines():
        if line.startswith('SUCCESS '):
            check(not success, 'Duplicate production success output')
            json.loads(line[len('SUCCESS '):])
            success = True
        elif line.startswith('SOURCE '):
            check(not success, 'SOURCE output appeared after publication success')
            records.append(json.loads(line[len('SOURCE '):]))
    check(success and records, 'Missing actual production SOURCE/success output')
    def index(items):
        indexed = {}
        for record in items:
            check(isinstance(record, dict) and set(record) == META_KEYS, 'Incomplete/unsupported source audit record')
            check(all(isinstance(record[key], str) and record[key] for key in META_KEYS - {'source_versions', 'data_rows'}), 'Invalid source audit field type')
            check(type(record['data_rows']) is int and record['data_rows'] > 0, 'Invalid source row count')
            versions = record['source_versions']
            check(isinstance(versions, list) and versions and all(isinstance(v, str) and v for v in versions) and versions == sorted(set(versions)), 'Invalid actual source versions')
            check(re.fullmatch('[0-9a-f]{64}', record['content_sha256']) is not None, 'Invalid source content hash')
            stamp = datetime.fromisoformat(record['fetched_at'])
            check(stamp.utcoffset() == timedelta(0), 'Fetch timestamp must identify UTC')
            check(sheet_id(record['url']) == record['spreadsheet_id'], 'Metadata spreadsheet identity differs')
            key = (record['url'], record['tab'])
            check(key not in indexed, 'Duplicate source audit tab identity')
            indexed[key] = record
        return indexed
    production, displayed, independently_read = index(records), index(metadata_from_report(report)), index(fresh)
    check(production == displayed, 'Actual SOURCE stdout records do not exactly match report source metadata')
    check(set(production) == set(independently_read), 'Fresh workbook populated tabs differ from published audit; source drift or incomplete publication')
    for identity, current in independently_read.items():
        for key in META_KEYS - {'fetched_at'}:
            check(production[identity][key] == current[key], 'Fresh source drift or publication mismatch for ' + repr(identity) + ' field ' + key + '; regenerate with fresh sources')
    return records


def base_status(row):
    return row['status'].split('-')[0]


def total(rows, status):
    return sum(cents(row['amount']) for row in rows if base_status(row) == status and row['amount_status'] == 'confirmed')


def reconcile_report(report, data, meeting_date, reporting_date, prior_date):
    report_structure(report)
    current, previous = iso_day(reporting_date), iso_day(prior_date)
    iso_day(meeting_date)
    check(previous < current, 'Prior business date must precede reporting date')
    summary_lines = section(report, 'Management summary')
    expected_dates = f'Operations meeting: **{meeting_date}**. Reporting date: **{reporting_date}**; prior business date: **{prior_date}**; budget period: **{reporting_date[:7]}**. Dates are operator supplied; no business-day calendar is inferred.'
    check(expected_dates in summary_lines, 'Meeting/reporting/prior/budget dates differ')
    tx = data['transactions']
    day, prior = [r for r in tx if r['date'] == reporting_date], [r for r in tx if r['date'] == prior_date]
    check(day and prior, 'Missing requested ledger date coverage')
    values = [total(day, 'posted'), total(day, 'pending'), total(day, 'disputed'), total(prior, 'posted')]
    values.append(values[0] - values[3])
    for lines, label_key, value_key in [(summary_lines, 'Daily figure', 'Exact signed USD'), (section(report, 'Five required figures'), 'Figure', 'Exact signed USD value')]:
        groups = tables(lines)
        check(len(groups) == 1 and len(groups[0]) == 5, 'Missing/extra required daily figures')
        check({row[label_key]: row[value_key] for row in groups[0]} == dict(zip(FIGURES, map(money, values))), 'Signed exact-date figures differ')
    period = reporting_date[:7]
    mtd = [r for r in tx if r['date'][:7] == period and r['date'] <= reporting_date]
    budgets = {r['category']: r for r in data['budget'] if r['period'] == period}
    check(budgets and {r['category'] for r in mtd} <= set(budgets), 'Missing current category budget/owner')
    groups = tables(section(report, 'Month-to-date budget comparisons'))
    check(len(groups) == 1, 'Missing/extra category comparison table')
    comparisons = groups[0]
    check(len(comparisons) == len(budgets) and {r['Category'] for r in comparisons} == set(budgets), 'Every current budget category must appear exactly once')
    headers = ['Category', 'Owner', 'Budget USD', 'Posted MTD USD', 'Posted − budget USD', '10% boundary USD', 'Abs variance > 10%?', 'Abs variance > USD 500?', 'Headroom USD', 'Pending-confirmed MTD USD', 'Disputed-confirmed MTD USD', 'Material variance', 'Source review rule']
    for shown in comparisons:
        budget = budgets[shown['Category']]
        rows = [r for r in mtd if r['category'] == budget['category']]
        allocation, posted = cents(budget['budget_amount']), total(rows, 'posted')
        variance = posted - allocation
        # Integer multiplication retains strict 10% precision without division.
        pct, fixed = abs(variance) * 10 > allocation, abs(variance) > 50000
        expected = [budget['category'], budget['owner'], money(allocation), money(posted), money(variance), money(Decimal(allocation) / 10), 'yes' if pct else 'no', 'yes' if fixed else 'no', money(-variance), money(total(rows, 'pending')), money(total(rows, 'disputed')), 'yes' if pct and fixed else 'no', budget['review_rule']]
        check(shown == dict(zip(headers, expected)), 'Category amount/strict predicates/owner/rule differs: ' + budget['category'])
    is_open = lambda r: base_status(r) in {'pending', 'disputed'} or r['amount_status'] == 'unknown'
    month_rows = [r for r in tx if r['date'][:7] == period]
    current_queue, other_queue = [r for r in month_rows if is_open(r)], [r for r in tx if r['date'][:7] != period and is_open(r)]
    for title, rows in [('Current-month transaction unresolved queue', current_queue), ('Other-period transaction unresolved items', other_queue)]:
        displayed = [r for group in tables(section(report, title)) for r in group]
        check(len(displayed) == len(rows) and sorted(r['Transaction ID'] for r in displayed) == sorted(r['transaction_id'] for r in rows), title + ': union IDs differ or unknown counted twice')
        indexed = {r['Transaction ID']: r for r in displayed}
        for row in rows:
            shown = indexed[row['transaction_id']]
            owners = [b for b in data['budget'] if b['period'] == row['date'][:7] and b['category'] == row['category']]
            owner = owners[0]['owner'] if owners else 'Not supplied; operations owner to route'
            timing = 'Later-dated current-month; excluded from MTD' if row['date'][:7] == period and row['date'] > reporting_date else ('Within reporting MTD' if row['date'][:7] == period else 'Other period; excluded from reporting MTD')
            expected = {'Date': row['date'], 'Category': row['category'], 'Description': row['description'], 'Status': base_status(row), 'Amount USD': 'unknown' if row['amount_status'] == 'unknown' else money(cents(row['amount'])), 'Owner': owner, 'Timing': timing}
            check(all(shown.get(field) == value for field, value in expected.items()), 'Unresolved row/amount state/owner differs: ' + row['transaction_id'])
            if row['amount_status'] == 'unknown':
                check('excluded from every numeric total' in shown['Review reason'], 'Unknown amount must remain explicitly unresolved')
            if base_status(row) in {'pending', 'disputed'} and owners and owners[0]['review_rule'] == 'review_all_pending_or_disputed':
                check('mandatory pending/disputed review per source rule regardless of amount' in shown['Review reason'], 'Source owner rule omitted from queue')
    month_lines = section(report, 'Current-month transaction unresolved queue')
    later, unknown = sum(r['date'] > reporting_date for r in current_queue), sum(r['amount_status'] == 'unknown' for r in current_queue)
    counts = {status: sum(base_status(r) == status for r in current_queue) for status in ('pending', 'disputed', 'posted')}
    reconciliation = f'Reconciliation to normalized transactions.csv: {len(month_rows)} current-month rows = {len(month_rows)-len(current_queue)} confirmed posted rows + {len(current_queue)} unresolved rows. Unresolved status counts: {counts["pending"]} pending + {counts["disputed"]} disputed + {counts["posted"]} posted with unknown amount = {len(current_queue)}. Amount states: {len(current_queue)-unknown} known + {unknown} unknown = {len(current_queue)}; unknown is an overlapping amount state, not an additional transaction. Later-dated current-month unresolved rows: {later}; on/before reporting date: {len(current_queue)-later}.'
    check(reconciliation in month_lines, 'Unresolved counts/amount-state partitions differ')
    for title, expected_ids in [('On or before the reporting date', {r['transaction_id'] for r in current_queue if r['date'] <= reporting_date}), ('Later-dated current-month items', {r['transaction_id'] for r in current_queue if r['date'] > reporting_date})]:
        check({r['Transaction ID'] for group in tables(section(report, title, 3)) for r in group} == expected_ids, 'Unresolved date partition differs: ' + title)
    revenue = data['revenue']
    before = {(r['source'], r['metric'], r['currency']): r for r in revenue if r['date'] == prior_date}
    after = {(r['source'], r['metric'], r['currency']): r for r in revenue if r['date'] == reporting_date}
    check(before and set(before) == set(after), 'Missing/conflicting matching snapshot coverage')
    groups = tables(section(report, 'Revenue and balance snapshot comparisons'))
    check(len(groups) == 2, 'Missing paired position or all-metric revenue tables')
    paired, metric_rows = groups
    metric_actual = {(r['Source'], r['Metric'], r['Unit']): r for r in metric_rows}
    check(len(metric_rows) == len(before) and len(metric_actual) == len(before), 'Missing/duplicate supplied snapshot metrics')
    paired_expected = set()
    for key in before:
        cash = key[2] == 'USD'
        a, b = numeric(before[key]['value']), numeric(after[key]['value'])
        formatted = [format(v, '+.2f' if cash else '+f') for v in (a, b, b - a)]
        shown = metric_actual.get((key[0], key[1], key[2] or 'source-defined count/unit'), {})
        check([shown.get(prior_date), shown.get(reporting_date), shown.get('Reporting − prior')] == formatted, 'Snapshot metric comparison differs: ' + repr(key))
        if key[1] == 'collected_revenue':
            balance_key = (key[0], 'outstanding_balance', key[2])
            check(balance_key in before, 'Missing collected/balance pairing')
            for day, snapshot in [(prior_date, before), (reporting_date, after)]:
                paired_expected.add((day, key[0], key[2] or 'source-defined unit', format(numeric(snapshot[key]['value']), '+.2f' if cash else '+f'), format(numeric(snapshot[balance_key]['value']), '+.2f' if cash else '+f')))
    check(paired_expected and len(paired) == len(paired_expected) and {(r['Date'], r['Source'], r['Unit'], r['Collected revenue'], r['Outstanding balance']) for r in paired} == paired_expected, 'Paired collected revenue/outstanding balance differs')
    return {'independent_reconciliation': 'PASS', 'five_signed_USD': list(map(money, values)), 'current_month_unresolved': len(current_queue), 'other_period_unresolved': len(other_queue), 'unknown_current_month': unknown, 'rows': {role: len(rows) for role, rows in data.items()}}


def reconcile(sources, meeting_date, reporting_date, prior_date, output, run_log, reader=None):
    """Reader injection is tests-only; CLI always makes fresh viewer requests."""
    check(len(sources) == 3 and len({sheet_id(url) for url in sources}) == 3, 'Three distinct viewer sources required')
    with localcontext() as context:
        context.prec = 50
        all_tabs = []
        for url in sources:
            tabs = (reader or fetch_tabs)(url)
            check(tabs and all(tab['url'] == url for tab in tabs), 'Independent reader source identity differs')
            all_tabs.extend(tabs)
        data, metadata = validate_tabs(all_tabs)
        for record in sorted(metadata, key=lambda r: (r['spreadsheet_id'], r['tab'])):
            print('INDEPENDENT_SOURCE ' + json.dumps(record, sort_keys=True), flush=True)
        report = (output / 'report.md').read_text(encoding='utf-8')
        report_structure(report)
        compare_metadata(report, run_log.read_text(encoding='utf-8'), metadata)
        compare_csvs(output, data)
        result = reconcile_report(report, data, meeting_date, reporting_date, prior_date)
        print(json.dumps(result, sort_keys=True), flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs=3, required=True)
    parser.add_argument('--meeting-date', required=True)
    parser.add_argument('--reporting-date', required=True)
    parser.add_argument('--prior-business-date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-log', type=Path, required=True)
    args = parser.parse_args()
    try:
        reconcile(args.sources, args.meeting_date, args.reporting_date, args.prior_business_date, args.output, args.run_log)
    except (ValueError, OSError, InvalidOperation, KeyError, TypeError) as exc:
        # Source-origin errors remain one quoted diagnostic line in capture.
        # Newlines/ANSI controls cannot forge SOURCE, SUCCESS or approval output.
        print('INDEPENDENT_RECONCILIATION_FAILED: ' + json.dumps(str(exc), ensure_ascii=True), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

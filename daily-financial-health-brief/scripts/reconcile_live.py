#!/usr/bin/env python3
"""Independent read-only CSV reconciliation of this assignment's single-tab sources.

Does not import production calculations or replace production inputs. Fetches every
supplied URL afresh; fails if the independent first-tab CSV cannot match all rows.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import re
import subprocess


def check(condition, message):
    if not condition:
        raise ValueError(message)


def cents(value):
    scaled = Decimal(value.replace(',', '')) * 100
    check(scaled == scaled.to_integral_value(), 'Fractional cent')
    return int(scaled)


def money(value):
    dollars = Decimal(value) / 100
    return f'{dollars:+.2f}' if dollars == dollars.quantize(Decimal('.01')) else f'{dollars:+f}'.rstrip('0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs=3, required=True)
    parser.add_argument('--meeting-date', required=True)
    parser.add_argument('--reporting-date', required=True)
    parser.add_argument('--prior-business-date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-log', type=Path, required=True)
    args = parser.parse_args()
    report = (args.output / 'report.md').read_text()
    check('Run status: **VALIDATED**' in report, 'Report not valid')
    check(f'Operations meeting: **{args.meeting_date}**' in report, 'Meeting date mismatch')
    data = {}
    for url in args.sources:
        match = re.fullmatch(r'https://docs.google.com/spreadsheets/d/([\w-]+)', url)
        check(match is not None, 'Supply canonical view-only Sheets URL')
        endpoint = url + '/export?format=csv&fresh=' + datetime.now(timezone.utc).isoformat()
        raw = subprocess.check_output(['curl', '--disable', '--fail', '--silent', '--show-error', '--location',
                                       '--max-time', '45', '--proto', '=https', '--proto-redir', '=https',
                                       '--header', 'Cache-Control: no-cache', endpoint]).decode('utf-8-sig')
        rows = list(csv.DictReader(io.StringIO(raw)))
        check(bool(rows), 'No independent CSV rows')
        roles = [role for role, field in [('transactions', 'transaction_id'), ('budget', 'budget_amount'), ('revenue', 'metric')] if field in rows[0]]
        check(len(roles) == 1 and roles[0] not in data, 'Ambiguous independent role')
        role = roles[0]
        normalized = list(csv.DictReader((args.output / 'normalized' / (role + '.csv')).open()))
        check(len(rows) == len(normalized), f'{role}: row count differs')
        by_row = {int(r['source_row']): r for r in normalized}
        for rownum, original in enumerate(rows, 2):
            saved = by_row[rownum]
            check(saved['source_url'] == url, 'Source identity differs')
            for field, value in original.items():
                same = cents(value) == cents(saved[field]) if field in {'amount', 'budget_amount', 'value'} and value not in {'', 'unknown'} else value == saved[field]
                check(same, f'{role} row {rownum} {field} differs')
        data[role] = rows
        print(f'INDEPENDENT_SOURCE role={role} id={match.group(1)} rows={len(rows)} fetched_at={datetime.now(timezone.utc).isoformat()}', flush=True)
    tx = data['transactions']
    def total(rows, status):
        return sum(cents(r['amount']) for r in rows if r['status'].removesuffix('-confirmed') == status and r['amount_status'] == 'confirmed')
    day = [r for r in tx if r['date'] == args.reporting_date]
    prior = [r for r in tx if r['date'] == args.prior_business_date]
    figures = [total(day, 'posted'), total(day, 'pending'), total(day, 'disputed'), total(prior, 'posted'), total(day, 'posted') - total(prior, 'posted')]
    labels = ['Reporting-date posted total', 'Reporting-date pending-confirmed total', 'Reporting-date disputed-confirmed total', 'Prior-business-day posted total', 'Reporting-date posted minus prior-business-day posted']
    summary = report.split('## Management summary')[1].split('## Five required figures')[0]
    for label, value in zip(labels, figures):
        check(f'| {label} | {money(value)} |' in summary, 'Summary figure differs: ' + label)
        check(f'| {label} | {money(value)} |' in report.split('## Five required figures')[1], 'Detailed figure differs')
    period = args.reporting_date[:7]
    mtd = [r for r in tx if r['date'][:7] == period and r['date'] <= args.reporting_date]
    for budget in data['budget']:
        if budget['period'] != period:
            continue
        rows = [r for r in mtd if r['category'] == budget['category']]
        allocation = cents(budget['budget_amount'])
        posted = total(rows, 'posted')
        variance = posted - allocation
        boundary = Decimal(allocation) / 10
        pct, fixed = abs(variance) > boundary, abs(variance) > 50000
        fields = [budget['category'], budget['owner'], money(allocation), money(posted), money(variance), money(boundary), 'yes' if pct else 'no', 'yes' if fixed else 'no', money(-variance), money(total(rows, 'pending')), money(total(rows, 'disputed')), 'yes' if pct and fixed else 'no', budget['review_rule']]
        check('| ' + ' | '.join(fields) + ' |' in report, 'Budget reconciliation differs: ' + budget['category'])
    is_open = lambda r: r['status'].removesuffix('-confirmed') in {'pending', 'disputed'} or r['amount_status'] == 'unknown'
    current = [r for r in tx if r['date'][:7] == period and is_open(r)]
    other = [r for r in tx if r['date'][:7] != period and is_open(r)]
    for title, rows in [('Current-month transaction unresolved queue', current), ('Other-period transaction unresolved items', other)]:
        section = report.split('## ' + title)[1].split('\n## ')[0]
        actual = [line.split('|')[1].strip() for line in section.splitlines() if line.startswith('| ') and not line.startswith(('| Transaction ID |', '| --- |'))]
        check(sorted(actual) == sorted(r['transaction_id'] for r in rows), title + ' IDs differ')
        for r in rows:
            check(f"| {r['transaction_id']} | {r['date']} | {r['status']} | " + ('unknown' if r['amount_status'] == 'unknown' else money(cents(r['amount']))) + ' |' in section, 'Queue field mismatch')
    snapshots = {(r['date'], r['source'], r['metric'], r['currency']): r for r in data['revenue']}
    for r in data['revenue']:
        if r['date'] != args.reporting_date:
            continue
        old = snapshots[(args.prior_business_date, r['source'], r['metric'], r['currency'])]
        values = [Decimal(old['value']), Decimal(r['value'])]
        values += [values[1] - values[0]]
        formatted = [f'{v:+.2f}' if r['currency'] == 'USD' else f'{v:+f}' for v in values]
        expected = '| ' + ' | '.join([r['source'], r['metric'], r['currency'] or 'source-defined count/unit'] + formatted) + ' |'
        check(expected in report, 'Revenue comparison differs: ' + r['metric'])
        if r['metric'] == 'collected_revenue':
            for day in [args.prior_business_date, args.reporting_date]:
                collected = snapshots[(day, r['source'], 'collected_revenue', r['currency'])]
                balance = snapshots[(day, r['source'], 'outstanding_balance', r['currency'])]
                check(f"| {day} | {r['source']} | {r['currency']} | {money(cents(collected['value']))} | {money(cents(balance['value']))} |" in report, 'Paired position differs')
    records = [json.loads(line[7:]) for line in args.run_log.read_text().splitlines() if line.startswith('SOURCE ')]
    check(len(records) == 3, 'Missing production source logs')
    for record in records:
        for key, value in record.items():
            for item in value if isinstance(value, list) else [value]:
                check(str(item) in report, 'Missing report metadata: ' + key)
        check(record['data_rows'] == len(data[record['role']]), 'Metadata row count mismatch')
    print(json.dumps({'independent_reconciliation': 'PASS', 'five_signed_USD': [money(v) for v in figures], 'current_month_unresolved': len(current), 'other_period_unresolved': len(other), 'unknown_current_month': sum(r['amount_status'] == 'unknown' for r in current), 'rows': {k: len(v) for k, v in data.items()}}, sort_keys=True))


if __name__ == '__main__':
    main()

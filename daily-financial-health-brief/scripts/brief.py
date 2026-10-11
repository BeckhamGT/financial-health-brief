#!/usr/bin/env python3
"""Fresh, read-only Sheets -> validated evidence -> fail-closed completeness gate."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

SCHEMAS = {
    "transactions": "transaction_id,date,account,category,description,amount,currency,status,source,source_version,amount_status".split(","),
    "budget": "period,category,budget_amount,currency,owner,review_rule,source,source_version".split(","),
    "revenue": "date,source,metric,value,currency,source_version".split(","),
}
PROVENANCE = ["source_url", "source_tab", "source_row"]
RULES = {"review_material_overage", "review_all_pending_or_disputed"}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
ZERO = Decimal("0")
CENT = Decimal("0.01")


class ValidationError(Exception):
    pass


class CompletenessError(ValidationError):
    """Fresh inputs cannot support a financial conclusion without owner evidence."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def iso_date(value):
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)), f"Expected ISO date, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid date {value!r}") from exc


def number(value, money=False):
    # Commas are accepted only as standard thousands grouping, never decimal separators.
    require(bool(re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", value)),
            f"Invalid decimal {value!r}")
    try:
        result = Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValidationError(f"Invalid decimal {value!r}") from exc
    require(result.is_finite() and len(result.as_tuple().digits) <= 28,
            f"Non-finite or oversized decimal {value!r}")
    if money:
        require(result == result.quantize(CENT), f"Money has sub-cent precision: {value!r}")
    return result


def decimal_text(value):
    return format(value, "f")


def signed(value, money=True):
    return format(value, "+.2f" if money else "+f")


def signed_boundary(value):
    # A 10% boundary may have fractional cents; retain that precision for strict tests.
    return signed(value) if value == value.quantize(CENT) else signed(value, money=False).rstrip("0")


def material(variance, baseline):
    return abs(variance) > abs(baseline) * Decimal("0.10") and abs(variance) > Decimal("500")


def status(row):
    return {"pending-confirmed": "pending", "disputed-confirmed": "disputed"}.get(row["status"], row["status"])


@dataclass
class Tab:
    url: str
    spreadsheet_id: str
    title: str
    tab_id: str  # XLSX-export sheet ID, not a Google gid.
    fetched_at: str
    headers: list
    rows: list  # (original 1-based sheet row number, list of exact cell strings)
    workbook_inventory: tuple = ()  # All exported tabs, including wholly empty tabs.


def sheet_identity(url):
    parts = urlsplit(url)
    match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?", parts.path)
    require(parts.scheme == "https" and parts.netloc == "docs.google.com" and match is not None,
            f"Expected a view-only Google Sheets URL, got {url!r}")
    return match.group(1)


def fetch_workbook(url):
    identity = sheet_identity(url)
    # Every invocation makes a network request. No disk input, credentials, cache or fallback.
    stamp = utc_now()
    endpoint = f"https://docs.google.com/spreadsheets/d/{identity}/export?format=xlsx&fresh={stamp}"
    command = ["curl", "--disable", "--fail", "--silent", "--show-error", "--location", "--max-time", "45",
               "--proto", "=https", "--proto-redir", "=https", "--header", "Cache-Control: no-cache", endpoint]
    result = subprocess.run(command, capture_output=True)
    require(result.returncode == 0, f"Fetch failed for {url}: {result.stderr.decode(errors='replace').strip()}")
    require(result.stdout.startswith(b"PK"), f"Fetch for {url} returned no XLSX workbook (access/login/format error)")
    return parse_workbook(result.stdout, url, identity, utc_now())


def xml(zipped, path):
    return ET.fromstring(zipped.read(path))


def parse_workbook(payload, url, identity, fetched_at):
    """Read all exported tabs, including hidden tabs and sparse rows, without float conversion."""
    try:
        with ZipFile(io.BytesIO(payload)) as z:
            require(sum(x.file_size for x in z.infolist()) < 50_000_000, "Workbook exceeds 50 MB expanded limit")
            wb = xml(z, "xl/workbook.xml")
            prop = wb.find("s:workbookPr", NS)
            epoch = date(1904, 1, 1) if prop is not None and prop.get("date1904") in ("1", "true") else date(1899, 12, 30)
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                shared = ["".join(t.text or "" for t in si.findall(".//s:t", NS))
                          for si in xml(z, "xl/sharedStrings.xml").findall("s:si", NS)]
            styles = xml(z, "xl/styles.xml")
            formats = {int(n.get("numFmtId")): n.get("formatCode", "") for n in styles.findall("s:numFmts/s:numFmt", NS)}
            date_styles = set()
            for index, xf in enumerate(styles.findall("s:cellXfs/s:xf", NS)):
                fid = int(xf.get("numFmtId", "0"))
                code = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]', "", formats.get(fid, "")).lower()
                if fid in range(14, 23) or fid in range(45, 48) or re.search(r"[yd]", code):
                    date_styles.add(index)
            rels = {r.get("Id"): r.get("Target") for r in xml(z, "xl/_rels/workbook.xml.rels")}
            sheets = wb.findall("s:sheets/s:sheet", NS)
            inventory = tuple((s.get("name"), s.get("sheetId"), s.get("state", "visible")) for s in sheets)
            require(len({s[0] for s in inventory}) == len(inventory) and len({s[1] for s in inventory}) == len(inventory),
                    "Duplicate exported tab identity")
            tabs = []
            for sheet in sheets:
                target = rels[sheet.get(REL)]
                path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
                cells_by_row = []
                physical_rows = set()
                for row in xml(z, path).findall("s:sheetData/s:row", NS):
                    rownum = int(row.get("r"))
                    require(rownum > 0 and rownum not in physical_rows, "Duplicate/invalid physical sheet row")
                    physical_rows.add(rownum)
                    cells = {}
                    for c in row.findall("s:c", NS):
                        address = c.get("r", "")
                        letters = re.fullmatch(r"([A-Z]+)([1-9]\d*)", address)
                        require(letters is not None and int(letters.group(2)) == rownum, f"Invalid/mismatched cell address {address}")
                        col = 0
                        for letter in letters.group(1):
                            col = col * 26 + ord(letter) - 64
                        require(col - 1 not in cells, f"Duplicate cell address {address}")
                        kind = c.get("t", "n")
                        value = c.findtext("s:v", default="", namespaces=NS)
                        require(kind != "e", f"Spreadsheet error at {sheet.get('name')}!{address}: {value}")
                        if c.find("s:f", NS) is not None:
                            require(value != "", f"Formula has no cached value at {address}")
                        if kind == "s":
                            value = shared[int(value)]
                        elif kind == "inlineStr":
                            value = "".join(t.text or "" for t in c.findall(".//s:t", NS))
                        elif kind == "n" and value and int(c.get("s", "0")) in date_styles:
                            serial = Decimal(value)
                            require(serial == serial.to_integral_value(), f"Date contains time at {address}; clarify date semantics")
                            value = (epoch + timedelta(days=int(serial))).isoformat()
                        cells[col - 1] = value
                    if any(v.strip() for v in cells.values()):
                        values = [cells.get(i, "") for i in range(max(cells) + 1)]
                        cells_by_row.append((rownum, values))
                if not cells_by_row:
                    continue
                headers = [re.sub(r"[ -]+", "_", h.strip().lower()) for h in cells_by_row[0][1]]
                while headers and not headers[-1]:
                    headers.pop()
                require(all(headers) and len(set(headers)) == len(headers), f"Blank/duplicate header in {sheet.get('name')}")
                tabs.append(Tab(url, identity, sheet.get("name"), sheet.get("sheetId"), fetched_at, headers, cells_by_row[1:], inventory))
            require(tabs, f"No nonempty tabs in {url}")
            return tabs
    except (BadZipFile, ET.ParseError, KeyError, IndexError, ValueError) as exc:
        raise ValidationError(f"Cannot parse workbook {url}: {exc}") from exc


def source_audit(tab, role=None):
    """Audit exported evidence; neither a row count nor a hash confirms completeness."""
    roles = [name for name, fields in SCHEMAS.items() if set(fields) <= set(tab.headers)]
    if role is None:
        role = roles[0] if len(roles) == 1 else "unrecognized_or_ambiguous"
    version_column = tab.headers.index("source_version") if "source_version" in tab.headers else None
    versions = sorted({values[version_column] for _, values in tab.rows
                       if version_column is not None and len(values) > version_column and values[version_column]})
    semantic_hash = hashlib.sha256(json.dumps([tab.headers, tab.rows], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return dict(url=tab.url, spreadsheet_id=tab.spreadsheet_id, tab=tab.title,
                exported_tab_id=tab.tab_id, fetched_at=tab.fetched_at, role=role,
                source_versions=versions, data_rows=len(tab.rows), content_sha256=semantic_hash)


def normalize(tabs):
    data = {role: [] for role in SCHEMAS}
    metadata = []
    identities = set()
    for tab in sorted(tabs, key=lambda t: (t.spreadsheet_id, t.title)):
        roles = [role for role, required in SCHEMAS.items() if set(required) <= set(tab.headers)]
        require(len(roles) == 1, f"Unrecognized/ambiguous field meanings in {tab.url} tab {tab.title}: {tab.headers}")
        role = roles[0]
        require(not set(PROVENANCE) & set(tab.headers), f"Reserved provenance header collision in {tab.title}")
        require(tab.rows, f"Empty {role} source in {tab.title}")
        for rownum, values in tab.rows:
            require(len(values) <= len(tab.headers), f"Data beyond declared headers in {tab.title} row {rownum}")
            row = dict(zip(tab.headers, values + [""] * (len(tab.headers) - len(values))))
            row.update(source_url=tab.url, source_tab=tab.title, source_row=str(rownum))
            required = set(SCHEMAS[role]) - {"amount", "currency"} if role == "transactions" else set(SCHEMAS[role]) - {"currency"}
            if role == "transactions":
                required.add("currency")
            if role == "budget":
                required.add("currency")
            require(all(row[k].strip() for k in required), f"Missing required field in {tab.title} row {rownum}")
            require(all(row[k] == row[k].strip() for k in SCHEMAS[role]), f"Whitespace ambiguity in {tab.title} row {rownum}")
            if role == "transactions":
                iso_date(row["date"])
                require(status(row) in {"posted", "pending", "disputed"}, f"Unknown status at {row['transaction_id']}")
                require(row["amount_status"] in {"confirmed", "unknown"}, f"Unknown amount_status at {row['transaction_id']}")
                require(row["currency"] == "USD", f"Unsupported currency at {row['transaction_id']}; no invented FX conversions")
                if row["amount_status"] == "unknown":
                    require(row["amount"].lower() in {"", "unknown"}, f"Unknown amount conflicts with numeric value at {row['transaction_id']}")
                else:
                    row["amount"] = format(number(row["amount"], money=True), ".2f")
                require(row["status"] not in {"pending-confirmed", "disputed-confirmed"} or row["amount_status"] == "confirmed", "Conflicting confirmed status")
                key = (role, row["transaction_id"])
            elif role == "budget":
                require(bool(re.fullmatch(r"\d{4}-\d{2}", row["period"])), f"Invalid budget period {row['period']}")
                iso_date(row["period"] + "-01")
                require(row["currency"] == "USD", "Unsupported budget currency")
                amount = number(row["budget_amount"], money=True)
                require(amount >= ZERO, "Negative budget baseline; clarify with source owner")
                row["budget_amount"] = format(amount, ".2f")
                require(row["review_rule"] in RULES, f"Unsupported review_rule {row['review_rule']}; clarify with {row['owner']}")
                key = (role, row["period"], row["category"], row["currency"])
            else:
                iso_date(row["date"])
                require(row["currency"] in {"", "USD"}, f"Unsupported revenue currency {row['currency']}")
                row["value"] = decimal_text(number(row["value"], money=row["currency"] == "USD"))
                key = (role, row["date"], row["source"], row["metric"], row["currency"])
            require(key not in identities, f"Duplicate/conflicting business identity {key}")
            identities.add(key)
            data[role].append(row)
        metadata.append(source_audit(tab, role))
    require(all(data.values()), "All three source roles must be present")
    for role, rows in data.items():
        rows.sort(key=lambda r: tuple(r[k] for k in SCHEMAS[role] if k not in {"amount", "value", "budget_amount"}))
    return data, metadata


def select_total(rows, wanted_status):
    return sum((number(r["amount"], money=True) for r in rows
                if status(r) == wanted_status and r["amount_status"] == "confirmed"), ZERO)


def evidence(row):
    label = row.get("transaction_id", row.get("category", row.get("metric", "row")))
    # Tab name + spreadsheet identity + physical row is stable evidence within this fetched snapshot.
    return SafeText(f"{data_text(label)} ({sheet_identity(row['source_url'])}/{data_text(row['source_tab'])} "
                    f"row {data_text(row['source_row'])}; {data_text(row['source_version'])})")


def refs(rows):
    return SafeText("; ".join(evidence(r) for r in rows) or "No matching rows")


class SafeText(str):
    """Report text constructed from trusted prose and already protected source parts."""


def data_text(value):
    """Render source text as literal data, keeping ordinary business fields readable.

    A JSON string makes control characters visible without changing the CSV value.
    Markdown code spans protect markup; an encoded pipe cannot split a table cell.
    The delimiter exceeds every source backtick run, so source text cannot close it.
    """
    if isinstance(value, SafeText):
        return value
    text = str(value)
    dangerous = (bool(re.search(r"[\\`*#~|<>\[\]&]", text)) or
                 bool(re.search(r"(?:^|\W)_|_(?:$|\W)", text)) or
                 any(unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp"} for char in text))
    if not dangerous:
        return SafeText(text)
    literal = json.dumps(text, ensure_ascii=True).replace("|", "\\u007c")
    delimiter = "`" * (max((len(run) for run in re.findall(r"`+", literal)), default=0) + 1)
    return SafeText(delimiter + literal + delimiter)


def escape(value):
    return data_text(value)


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(escape(c) for c in row) + " |" for row in rows])


def transport_consistency(first_tabs, second_tabs, first_records, second_records, requested_urls, errors=None):
    """Check two observed exports, without inferring Operations' ledger coverage."""
    issues = list(errors or [])
    expected = set(requested_urls)
    for round_number, tabs in ((1, first_tabs), (2, second_tabs)):
        observed = {t.url for t in tabs}
        for url in sorted(expected - observed):
            issues.append(dict(code="missing_source_read", round=round_number, url=url))
        for url in sorted(observed - expected):
            issues.append(dict(code="unexpected_source_read", round=round_number, url=url))
    def semantic(records):
        return {(r["url"], r["spreadsheet_id"], r["tab"], r["exported_tab_id"]):
                {k: value for k, value in r.items() if k != "fetched_at"} for r in records}
    first, second = semantic(first_records), semantic(second_records)
    if first.keys() != second.keys():
        issues.append(dict(code="populated_tab_inventory_changed"))
    for identity in sorted(first.keys() & second.keys()):
        if first[identity] != second[identity]:
            issues.append(dict(code="source_content_or_version_changed", source_identity=list(identity)))
    def inventories(tabs):
        return {t.url: t.workbook_inventory for t in tabs}
    if inventories(first_tabs) != inventories(second_tabs):
        issues.append(dict(code="exported_tab_inventory_changed"))
    return dict(status="FAILED" if issues else "CONSISTENT_OBSERVED_EXPORTS",
                checks=["each_requested_workbook_read_twice", "exported_tab_inventory",
                        "populated_tab_identity", "physical_business_rows_and_headers",
                        "business_content_and_observed_source_versions"],
                issues=issues,
                limitation="Identical exports can both be partial; technical consistency does not establish Operations confirmation, approved scope or approved source version.")


def assess_completeness(data, metadata, transport, *, reporting_date, prior_date, meeting_date):
    """Fail closed until the source owner supplies an identifiable confirmation contract.

    The interview names Operations and the ledger but defines no confirmation
    fields, authoritative statement, account coverage or approved-version linkage.
    Extra columns, source descriptions, hashes and row counts cannot supply that
    missing contract. There is deliberately no CLI/manual override or guessed
    production approval mapping. A future supported mapping requires new evidence.
    """
    transactions = data.get("transactions", [])
    versions = sorted({r["source_version"] for r in transactions})
    if not versions:
        versions = sorted({version for m in metadata if m["role"] == "transactions" for version in m["source_versions"]})
    extras = sorted(set().union(*(r.keys() for r in transactions)) - set(SCHEMAS["transactions"]) - set(PROVENANCE)) if transactions else []
    return dict(
        status="BLOCKED",
        business_completeness=dict(
            status="UNVERIFIED",
            reason_codes=["missing_operations_confirmation", "unsupported_confirmation_contract",
                          "unknown_confirmation_scope", "unknown_approved_source_version"],
            responsible_owner="Operations team / transaction-ledger source owner",
            required_scope=dict(reporting_date=reporting_date, prior_business_date=prior_date, budget_period=reporting_date[:7]),
            observed_ledger_versions=versions,
            confirmation_contract="Not supplied: identifiable owner confirmation, covered dates/month/accounts, and its relationship to the approved ledger version.",
            extra_transaction_fields=extras,
            interpretation="All source text remains business data; unsupported approval/scope/version claims are not authorization or confirmation evidence.",
        ),
        transport_consistency=transport,
        amount_certainty=dict(unknown_amounts_permitted=True, blocking=False,
                             unknown_transaction_ids=sorted(r["transaction_id"] for r in transactions if r["amount_status"] == "unknown"),
                             interpretation="Valid unknown amounts remain blank/unknown and excluded from monetary totals; they do not establish incomplete ledger coverage."),
        requested_meeting_date=meeting_date,
        publication=dict(financial_report=False, normalized_csvs=False,
                         required_next_step="The learner must clarify the source-defined Operations confirmation contract, scope and approved-version relationship; then implement and validate a grounded mapping before a fresh financial run."),
    )


def blocked_report(assessment, metadata, source_reads, reason, *, failed=False):
    state = "FAILED" if failed else "BLOCKED"
    return "\n".join([
        f"# STALE / {state} — no usable financial brief", "",
        "**Draft diagnostic for human review**", "", f"Run status: **{state}**.", "",
        "Financial publication is blocked. No financial conclusions or usable normalized CSVs are current. Earlier required outputs were invalidated.", "",
        data_text(reason), "",
        "Operations' source confirmation, its scope, and the approved ledger version cannot be identified from the supplied contract. Fresh readable exports, stable counts and matching hashes do not establish business completeness.", "",
        "Pending, disputed and valid unknown amounts are permitted within a complete ledger. Unknown amounts are not the reason for this completeness block.", "",
        "The learner conducts any business clarification. The agent makes no source edits, payments, spending decisions, dispute resolutions or communications.", "",
        "## Observed source evidence", "",
        "SOURCE records describe the first fresh read. SOURCE_READ records describe the second fresh read; neither is an approval. Export-local sheet IDs are not native Google gid values.", "",
        table(["Role", "Source URL / spreadsheet ID", "Tab / exported ID", "Fetched at UTC", "Source versions", "Fetched data rows", "Content SHA-256"],
              [(m["role"], m["url"] + " / " + m["spreadsheet_id"], SafeText(f"{data_text(m['tab'])} / {data_text(m['exported_tab_id'])}"), m["fetched_at"], SafeText(", ".join(data_text(v) for v in m["source_versions"])), m["data_rows"], m["content_sha256"]) for m in metadata]), "",
        "### Exact source audit records", "", "```json", json.dumps(metadata, ensure_ascii=True, sort_keys=True, indent=2), "```", "",
        "### Exact source read records", "", "```json", json.dumps(source_reads, ensure_ascii=True, sort_keys=True, indent=2), "```", "",
        "### Completeness assessment", "", "```json", json.dumps(assessment, ensure_ascii=True, sort_keys=True, indent=2), "```", "",
    ])


def build_report(data, metadata, reporting_date, prior_date, meeting_date):
    iso_date(meeting_date)
    current, prior = iso_date(reporting_date), iso_date(prior_date)
    require(prior < current, "Prior business date must precede reporting date; operator confirms business calendar")
    tx, budgets, revenue = (data[r] for r in ("transactions", "budget", "revenue"))
    daily = [r for r in tx if r["date"] == reporting_date]
    previous = [r for r in tx if r["date"] == prior_date]
    require(daily and previous, "Ledger has no rows for a requested date; clarify missing activity before reporting zero")
    mtd = [r for r in tx if current.replace(day=1) <= iso_date(r["date"]) <= current]
    period = reporting_date[:7]
    active_budgets = {r["category"]: r for r in budgets if r["period"] == period}
    require(active_budgets, f"Missing budget period {period}")
    require({r["category"] for r in mtd} <= set(active_budgets), "MTD category missing its budget and owner")
    posted, pending, disputed, old_posted = select_total(daily, "posted"), select_total(daily, "pending"), select_total(daily, "disputed"), select_total(previous, "posted")
    figures = [("Reporting-date posted total", posted, refs([r for r in daily if status(r) == "posted" and r["amount_status"] == "confirmed"])),
               ("Reporting-date pending-confirmed total", pending, refs([r for r in daily if status(r) == "pending" and r["amount_status"] == "confirmed"])),
               ("Reporting-date disputed-confirmed total", disputed, refs([r for r in daily if status(r) == "disputed" and r["amount_status"] == "confirmed"])),
               ("Prior-business-day posted total", old_posted, refs([r for r in previous if status(r) == "posted" and r["amount_status"] == "confirmed"])),
               ("Reporting-date posted minus prior-business-day posted", posted - old_posted, "Reporting-date posted total minus prior-business-day posted total")]
    out = ["# Daily financial health brief", "", "**Draft for human review**", "",
           f"Reporting date: **{reporting_date}**. Prior business date: **{prior_date}** (operator-confirmed).",
           "", "Run status: **VALIDATED**. Currency for spend/budget figures: USD. Unknown amounts remain unknown.", "",
           "## Five required figures", "", table(["Figure", "Exact signed USD value", "Source rows / derivation"],
                                                   [(label, signed(value), src) for label, value, src in figures]),
           "", "## Month-to-date budget comparisons", "",
           f"Inclusive posted activity from {current.replace(day=1)} through {reporting_date}, compared with the full {period} monthly allocation (no prorating or projection)."]
    comparisons, material_findings, risks, queue = [], [], [], []
    for category, b in sorted(active_budgets.items()):
        rows = [r for r in mtd if r["category"] == category]
        p, q, d = (select_total(rows, st) for st in ("posted", "pending", "disputed"))
        baseline = number(b["budget_amount"], money=True)
        variance = p - baseline
        is_material = material(variance, baseline)
        headroom = baseline - p
        comparisons.append((category, b["owner"], signed(baseline), signed(p), signed(variance),
                            signed_boundary(baseline * Decimal("0.10")), "yes" if abs(variance) > baseline * Decimal("0.10") else "no",
                            "yes" if abs(variance) > Decimal("500") else "no",
                            signed(headroom), signed(q), signed(d), "yes" if is_material else "no", b["review_rule"]))
        if is_material:
            material_findings.append(f"{data_text(category)}: MTD posted minus monthly budget = USD {signed(variance)}; "
                                     f"baseline USD {signed(baseline)}, 10% boundary USD {signed_boundary(baseline * Decimal('0.10'))}. "
                                     f"{'Overage' if variance > ZERO else 'Below full monthly allocation; not a forecast or savings decision'}. "
                                     f"Owner: {data_text(b['owner'])}. Evidence: {evidence(b)}; {refs([r for r in rows if status(r) == 'posted' and r['amount_status'] == 'confirmed'])}.")
        if variance > ZERO:
            risks.append(f"{data_text(category)}: posted spend exceeds allocation by USD {signed(variance)}; "
                         f"{'material overage review required' if is_material and b['review_rule'] == 'review_material_overage' else 'below material overage trigger or governed by separate source rule'}. Owner: {data_text(b['owner'])}.")
        elif p + q > baseline:
            risks.append(f"{data_text(category)}: confirmed pending exposure could exceed remaining headroom (posted + pending = USD {signed(p + q)} "
                         f"vs allocation USD {signed(baseline)}). This is exposure, not posted spend. Owner: {data_text(b['owner'])}.")
        if d:
            risks.append(f"{data_text(category)}: USD {signed(d)} disputed-confirmed MTD exposure remains separate; no outcome assumed. Owner: {data_text(b['owner'])}.")
        if b["review_rule"] == "review_material_overage" and variance > ZERO and is_material:
            queue.append((SafeText(f"Material overage: {data_text(category)}"), b["owner"], "Review budget breach and recommend action for operations-owner decision", evidence(b)))
        if not rows:
            risks.append(f"{data_text(category)}: no ledger rows observed for MTD; observed total is USD +0.00, not proof of completeness. Owner: {data_text(b['owner'])}.")
    out += ["", table(["Category", "Owner", "Budget USD", "Posted MTD USD", "Posted − budget USD", "10% boundary USD", "Abs variance > 10%?", "Abs variance > USD 500?", "Headroom USD", "Pending-confirmed MTD USD", "Disputed-confirmed MTD USD", "Material variance", "Source review rule"], comparisons),
            "", "### Budget calculation evidence", ""]
    for category, b in sorted(active_budgets.items()):
        out.append(f"- {data_text(category)}: budget {evidence(b)}; posted MTD contributors: {refs([r for r in mtd if r['category'] == category and status(r) == 'posted' and r['amount_status'] == 'confirmed'])}.")
    out += ["", "## Material variances", ""] + ["- " + f for f in material_findings]
    if not material_findings:
        out.append("No budget variance meets both strict materiality boundaries.")
    out += ["", "## Budget risks", ""] + ["- " + risk for risk in risks]
    out += ["", "## Revenue and balance snapshot comparisons", ""]
    snapshots = {day: {(r["source"], r["metric"], r["currency"]): r for r in revenue if r["date"] == day} for day in (prior_date, reporting_date)}
    require(snapshots[prior_date] and snapshots[reporting_date], "Missing revenue snapshot for requested date")
    require(set(snapshots[prior_date]) == set(snapshots[reporting_date]), "Missing/mismatched revenue metric, source, or currency across dates")
    revenue_rows = []
    for key in sorted(snapshots[prior_date]):
        before, after = snapshots[prior_date][key], snapshots[reporting_date][key]
        a, b = number(before["value"]), number(after["value"])
        cash = key[2] == "USD"
        revenue_rows.append((key[0], key[1], key[2] or "source-defined count/unit", signed(a, cash), signed(b, cash), signed(b - a, cash),
                             refs([before, after])))
        if key[1] == "collected_revenue":
            queue.append(("Collected revenue interpretation", SafeText(f"{data_text(key[0])} source owner"),
                          "Daily-flow versus cumulative meaning was not established; comparisons are snapshot-only until clarified", refs([before, after])))
    paired = []
    positions = []
    collected_keys = [k for k in sorted(snapshots[prior_date]) if k[1] == "collected_revenue"]
    require(collected_keys, "Missing collected_revenue metric")
    for key in collected_keys:
        balance_key = (key[0], "outstanding_balance", key[2])
        require(balance_key in snapshots[prior_date], "Missing matching outstanding_balance metric")
        for day in (prior_date, reporting_date):
            collected_row, balance_row = snapshots[day][key], snapshots[day][balance_key]
            paired.append((day, key[0], key[2] or "source-defined unit", signed(number(collected_row["value"]), key[2] == "USD"),
                           signed(number(balance_row["value"]), key[2] == "USD"), refs([collected_row, balance_row])))
        c0, c1 = (number(snapshots[day][key]["value"]) for day in (prior_date, reporting_date))
        b0, b1 = (number(snapshots[day][balance_key]["value"]) for day in (prior_date, reporting_date))
        positions.append(f"{data_text(key[0])}: collected revenue {key[2] or 'source-defined unit'} {signed(c0, key[2] == 'USD')} → {signed(c1, key[2] == 'USD')} (change {signed(c1-c0, key[2] == 'USD')}); "
                         f"outstanding balance {key[2] or 'source-defined unit'} {signed(b0, key[2] == 'USD')} → {signed(b1, key[2] == 'USD')} (change {signed(b1-b0, key[2] == 'USD')}).")
    out += [table(["Date", "Source", "Unit", "Collected revenue", "Outstanding balance", "Evidence"], paired), "",
            table(["Source", "Metric", "Unit", prior_date, reporting_date, "Reporting − prior", "Evidence"], revenue_rows), "",
            "Compare matching metric/source/currency snapshots separately. Collected revenue rose or fell by its own signed change; outstanding balance has its own signed change. "
            "Their difference is not a collection rate, cash flow, profit, or evidence of cumulative revenue. Daily-flow versus cumulative meaning remains unconfirmed.", ""]
    def open_item(r):
        return status(r) in {"pending", "disputed"} or r["amount_status"] == "unknown"
    month_rows = [r for r in tx if r["date"][:7] == period]
    month_queue = sorted([r for r in month_rows if open_item(r)], key=lambda r: (r["date"], r["transaction_id"]))
    other_queue = sorted([r for r in tx if r["date"][:7] != period and open_item(r)], key=lambda r: (r["date"], r["transaction_id"]))
    unknown = [r for r in month_queue if r["amount_status"] == "unknown"]
    later = [r for r in month_queue if r["date"] > reporting_date]
    counts = {st: sum(status(r) == st for r in month_queue) for st in ("posted", "pending", "disputed")}
    def queue_table(rows):
        values = []
        for r in rows:
            matching = [b for b in budgets if b["period"] == r["date"][:7] and b["category"] == r["category"]]
            owner = matching[0]["owner"] if matching else "Not supplied; operations owner to route"
            reason = "Clarify unknown amount; excluded from every numeric total" if r["amount_status"] == "unknown" else "Resolve open status; separate from posted"
            if status(r) in {"pending", "disputed"} and any(b["review_rule"] == "review_all_pending_or_disputed" for b in matching):
                reason += "; mandatory pending/disputed review per source rule regardless of amount"
            scope = "Later-dated current-month; excluded from MTD" if r["date"][:7] == period and r["date"] > reporting_date else ("Within reporting MTD" if r["date"][:7] == period else "Other period; excluded from reporting MTD")
            values.append((r["transaction_id"], r["date"], r["category"], r["description"], status(r), "unknown" if r["amount_status"] == "unknown" else signed(number(r["amount"])), owner, reason, scope, SafeText(evidence(r) + "; owner/rule: " + refs(matching))))
        return table(["Transaction ID", "Date", "Category", "Description", "Status", "Amount USD", "Owner", "Review reason", "Timing", "Evidence"], values) if values else "None observed in fetched data."
    out += ["## Current-month transaction unresolved queue", "",
            f"Scope: every recognized {period} transaction that is pending, disputed, or has an unknown amount, including dates after {reporting_date}. Each transaction appears once.", "",
            f"Reconciliation to normalized transactions.csv: {len(month_rows)} current-month rows = {len(month_rows)-len(month_queue)} confirmed posted rows + {len(month_queue)} unresolved rows. "
            f"Unresolved status counts: {counts['pending']} pending + {counts['disputed']} disputed + {counts['posted']} posted with unknown amount = {len(month_queue)}. "
            f"Amount states: {len(month_queue)-len(unknown)} known + {len(unknown)} unknown = {len(month_queue)}; unknown is an overlapping amount state, not an additional transaction. "
            f"Later-dated current-month unresolved rows: {len(later)}; on/before reporting date: {len(month_queue)-len(later)}.", "",
            "### On or before the reporting date", "", queue_table([r for r in month_queue if r["date"] <= reporting_date]), "",
            "### Later-dated current-month items", "", queue_table(later), "",
            "## Other-period transaction unresolved items", "", f"{len(other_queue)} rows outside {period}; preserved in normalized data and excluded from current-month counts.", "", queue_table(other_queue), "",
            "## Nontransaction clarifications and human review", "",
            table(["Issue", "Responsible owner", "Required review", "Evidence"], [r for r in queue if r[0].startswith(("Material overage:", "Collected revenue interpretation"))]), "",
            "The operations owner reviews spending changes, disputed outcomes, escalations and all irreversible actions. Category owners follow the source-defined review rules. "
            "The Finance and Operations Manager confirms reporting dates and source completeness and clarifies missing, conflicting or stale evidence with the responsible source owner before concluding. "
            "This draft authorizes no spending, payment, source edit or dispute resolution.", "",
            "The two source rules mean: review_material_overage triggers on positive posted MTD overage satisfying both strict materiality tests; "
            "review_all_pending_or_disputed requires review of every pending/disputed item in its budget period, independently of amount/materiality. Other open items are still visible in the queue.", "",
            "## Calculation definitions and limitations", "",
            "- Exact-date daily totals include only confirmed amounts of that status on that date. Pending/disputed labels paired with confirmed amount_status mean pending-confirmed/disputed-confirmed.",
            "- Unknown amounts stay blank or explicitly unknown in normalized data; they contribute neither zero nor an estimate to any sum. Numeric subtotals are known-amount totals and exposure remains incomplete.",
            "- Confirmed negative posted amounts are credits/corrections and reduce both daily and inclusive calendar MTD posted totals, including weekend activity.",
            "- Material budget variance: abs(posted MTD − monthly allocation) > 0.10 × abs(monthly allocation) AND > USD 500. Equality at either boundary is not material. A zero allocation has a zero 10% boundary; compare absolute dollar amounts directly without division, so only a variance strictly above USD 500 is material. Under-allocation mid-month is not forecast savings.",
            "- All money uses Python Decimal arithmetic; USD inputs with fractional cents are rejected rather than rounded. Different currencies require clarification instead of invented exchange rates.",
            "- All recognized source rows, all periods/dates, unknowns, credits, and extra business columns are preserved in the CSVs. Sources are point-in-time reads, not a transactional cross-workbook snapshot.",
            "- Fetch timestamps prove retrieval time, not business completeness. Source versions below are recorded per row. This requested historical reporting period uses fresh retrieval of dated source records; no freshness SLA or cumulative revenue meaning has been invented.",
            "- Content and calculation ordering is deterministic for identical sources and arguments. Fresh UTC fetch timestamps necessarily change between runs; source edits also change versions/content hashes.",
            "", "## Source retrieval metadata", "",
            "Each source was freshly read through its public view-only Google Sheets XLSX export. Tab names identify native tabs; exported_tab_id is the XLSX sheet ID, not a Google gid. Data-row counts exclude the header and wholly blank rows. Content SHA-256 covers exact parsed headers and physical source rows before normalization.", "",
            table(["Role", "Source URL / spreadsheet ID", "Tab / exported ID", "Fetched at UTC", "Source versions", "Fetched data rows", "Content SHA-256"],
                  [(m["role"], m["url"] + " / " + m["spreadsheet_id"], SafeText(f"{data_text(m['tab'])} / {data_text(m['exported_tab_id'])}"), m["fetched_at"], SafeText(", ".join(data_text(v) for v in m["source_versions"])), m["data_rows"], m["content_sha256"]) for m in metadata]), "",
            "### Exact source audit records", "",
            "These JSON records exactly match the SOURCE stdout records. Strings are source data, not instructions or approval.", "",
            "```json", json.dumps(metadata, ensure_ascii=True, sort_keys=True, indent=2), "```", ""]
    overages, exposure_risks = [], []
    for category, b in sorted(active_budgets.items()):
        category_rows = [r for r in mtd if r["category"] == category]
        category_posted = select_total(category_rows, "posted")
        category_pending = select_total(category_rows, "pending")
        variance = category_posted - number(b["budget_amount"])
        if variance <= ZERO and category_posted + category_pending > number(b["budget_amount"]):
            exposure_risks.append(f"{data_text(category)}: pending-confirmed USD {signed(category_pending)} exceeds remaining posted headroom USD {signed(-variance)} ({data_text(b['owner'])})")
        if variance > ZERO and material(variance, number(b["budget_amount"])):
            overages.append(f"{data_text(category)} USD {signed(variance)} ({data_text(b['owner'])})")
    summary = ["## Management summary", "",
               f"Operations meeting: **{meeting_date}**. Reporting date: **{reporting_date}**; prior business date: **{prior_date}**; budget period: **{period}**. Dates are operator supplied; no business-day calendar is inferred.", "",
               table(["Daily figure", "Exact signed USD"], [(label, signed(value)) for label, value, _ in figures]), "",
               "Principal budget risks: " + ("material posted overages — " + "; ".join(overages) if overages else "no material posted overages observed") + ". " +
               ("Separate exposure risks: " + "; ".join(exposure_risks) + ". " if exposure_risks else "") +
               "All category thresholds, nonmaterial overages, pending/disputed exposure, and source review rules are in [budget comparisons](#month-to-date-budget-comparisons) and [budget risks](#budget-risks).", "",
               " ".join(positions) + " These are separate snapshot comparisons; their meaning is subject to source-owner clarification. See [revenue and balance evidence](#revenue-and-balance-snapshot-comparisons).", "",
               f"Current-month review: **{len(month_queue)} unresolved transactions**, including **{len(unknown)} unknown amounts**" +
               (" (" + ", ".join(data_text(r["transaction_id"]) for r in unknown) + ")" if unknown else "") +
               f"; {len(later)} are later than the reporting date. Unknowns are excluded from numeric totals; owners must obtain their amounts. See the [complete current-month queue](#current-month-transaction-unresolved-queue).", "",
               "Operations owner: review spending changes, owner escalations, disputed outcomes, and proposed actions before use. This draft records no stakeholder approval. "
               "[Daily calculation evidence](#five-required-figures), [definitions](#calculation-definitions-and-limitations), and [fresh source metadata](#source-retrieval-metadata) support review.", ""]
    out[4:4] = summary
    return "\n".join(out), {label: signed(value) for label, value, _ in figures}, len(month_queue) + len(other_queue) + sum(r[0].startswith(("Material overage:", "Collected revenue interpretation")) for r in queue)


def invalidate(output, reason, *, report_text=None):
    if output.is_symlink():
        raise OSError("Output directory is a symlink; stop use and quarantine the output path without changing its target")
    output.mkdir(parents=True, exist_ok=True)
    # Mark every earlier artifact stale before any cleanup can fail.
    report_path = output / "report.md"
    marker = report_text if report_text is not None else "# STALE / FAILED — no usable financial brief\n\n" + data_text(reason) + "\n\nRecorded at UTC: " + utc_now() + "\n"
    errors = []
    report_state = "Report marked STALE / FAILED"
    try:
        # Unlink the reference itself; never overwrite a report outside this output.
        if report_path.is_symlink():
            report_path.unlink()
        report_path.write_text(marker, encoding="utf-8")
    except OSError as exc:
        errors.append(f"Cannot write stale marker: {exc}")
        alternate = None
        try:
            # Replacing a file can work when its existing permissions deny overwrite.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".brief-failure-", dir=output, delete=False) as f:
                alternate = Path(f.name)
                f.write(marker)
            os.replace(alternate, report_path)
        except OSError as replacement_error:
            errors.append(f"Cannot replace stale marker: {replacement_error}")
            try:
                report_path.unlink(missing_ok=True)
                report_state = "Earlier report removed"
            except OSError as removal_error:
                report_state = "Unable to invalidate earlier report; stop use and quarantine the output directory"
                errors.append(f"Cannot remove earlier report: {removal_error}")
        finally:
            if alternate is not None and alternate.exists():
                try:
                    alternate.unlink()
                except OSError as cleanup_error:
                    errors.append(f"Cannot remove temporary failure marker: {cleanup_error}")
    normalized = output / "normalized"
    if normalized.is_symlink():
        errors.append("Normalized directory is a symlink; its external target was not changed. Replace the link with an operator-approved local directory before rerunning")
    else:
        for role in SCHEMAS:
            path = normalized / (role + ".csv")
            if path.exists() or path.is_symlink():
                try:
                    # Individual CSV links are removed, without following targets.
                    path.unlink()
                except OSError as exc:
                    errors.append(f"Cannot remove stale {path}: {exc}")
    if errors:
        raise OSError(report_state + "; cleanup incomplete; run stopped: " + "; ".join(errors))


def publish(output, data, report):
    # Report validity is published last. An interruption before then leaves STALE/FAILED.
    if output.is_symlink() or (output / "normalized").is_symlink():
        raise OSError("Publication destination became a symlink; stop use and quarantine the output path")
    (output / "normalized").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".brief-", dir=output) as staging:
        staging = Path(staging)
        for role, rows in data.items():
            extras = sorted(set().union(*(r.keys() for r in rows)) - set(SCHEMAS[role]) - set(PROVENANCE))
            columns = SCHEMAS[role] + extras + PROVENANCE
            with (staging / (role + ".csv")).open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        (staging / "report.md").write_text(report, encoding="utf-8")
        for role in SCHEMAS:
            os.replace(staging / (role + ".csv"), output / "normalized" / (role + ".csv"))
        os.replace(staging / "report.md", output / "report.md")


def fetch_round(urls, fetcher, round_number, metadata, source_reads, errors):
    tabs = []
    for url in sorted(urls, key=sheet_identity):
        try:
            current = (fetcher or fetch_workbook)(url)
            require(isinstance(current, list) and current, f"Missing/partial exported workbook for {url}")
            identities = set()
            for tab in current:
                require(isinstance(tab, Tab) and tab.url == url and tab.spreadsheet_id == sheet_identity(url),
                        f"Returned workbook does not match requested source {url}")
                require(isinstance(tab.title, str) and bool(tab.title.strip()) and bool(tab.tab_id), "Missing exported tab identity")
                require((tab.title, tab.tab_id) not in identities, "Duplicate populated exported tab identity")
                identities.add((tab.title, tab.tab_id))
            for tab in sorted(current, key=lambda t: t.title):
                record = source_audit(tab)
                if round_number == 1:
                    metadata.append(record)
                    print("SOURCE " + json.dumps(record, sort_keys=True), flush=True)
                else:
                    read_record = dict(round=round_number, source=record)
                    source_reads.append(read_record)
                    print("SOURCE_READ " + json.dumps(read_record, sort_keys=True), flush=True)
            tabs.extend(current)
        except (ValidationError, OSError, ET.ParseError, InvalidOperation) as exc:
            errors.append(dict(code="source_read_failed", round=round_number, url=url, message=str(exc)))
    return tabs


def run(urls, reporting_date, prior_date, output, fetcher=None, *, meeting_date):
    output = Path(output)
    invalidate(output, "Run started; earlier deliverables invalidated pending complete fresh retrieval and validation.")
    metadata, source_reads, first_tabs, second_tabs, read_errors = [], [], [], [], []
    data, assessment = {}, None
    try:
        with localcontext() as ctx:
            ctx.prec = 50
            require(len(urls) == 3 and len({sheet_identity(u) for u in urls}) == 3, "Supply exactly three distinct Google Sheets URLs")
            iso_date(meeting_date)
            iso_date(reporting_date)
            iso_date(prior_date)
            first_tabs = fetch_round(urls, fetcher, 1, metadata, source_reads, read_errors)
            require(not read_errors, "Fresh source retrieval incomplete: " + json.dumps(read_errors, sort_keys=True))
            data, _ = normalize(first_tabs)
            second_tabs = fetch_round(urls, fetcher, 2, metadata, source_reads, read_errors)
            require(not read_errors, "Fresh consistency re-read incomplete: " + json.dumps(read_errors, sort_keys=True))
            normalize(second_tabs)  # Validate all recognized re-read inputs too.
            transport = transport_consistency(first_tabs, second_tabs, metadata, [r["source"] for r in source_reads], urls)
            assessment = assess_completeness(data, metadata, transport, reporting_date=reporting_date, prior_date=prior_date, meeting_date=meeting_date)
            if assessment["status"] != "VERIFIED" or transport["status"] != "CONSISTENT_OBSERVED_EXPORTS":
                raise CompletenessError("Financial conclusion blocked: Operations confirmation, approved scope and approved ledger version are unverified; technical read consistency is a separate check.")
            report, figures, unresolved_count = build_report(data, metadata, reporting_date, prior_date, meeting_date)
            publish(output, data, report)
            result = dict(figures=figures, preserved_rows={r: len(rows) for r, rows in data.items()}, unresolved_count=unresolved_count)
            print("SUCCESS " + json.dumps(result, sort_keys=True), flush=True)
            return result
    except BaseException as exc:
        if not isinstance(exc, CompletenessError):
            read_errors.append(dict(code="fetch_validation_or_publication_failed", message=str(exc)))
            transport = transport_consistency(first_tabs, second_tabs, metadata, [r["source"] for r in source_reads], urls, read_errors)
            assessment = assess_completeness(data, metadata, transport, reporting_date=reporting_date, prior_date=prior_date, meeting_date=meeting_date)
        print("ASSESSMENT " + json.dumps(assessment, sort_keys=True), flush=True)
        report = blocked_report(assessment, metadata, source_reads, str(exc), failed=not isinstance(exc, CompletenessError))
        invalidate(output, f"Fetch/validation/publication failed: {exc}", report_text=report)
        raise


def main():
    default_output = str(Path(__file__).resolve().parents[2] / "deliverables")
    # On CLI validation errors, invalidate the selected destination as well.
    selected_output = default_output
    for index, arg in enumerate(sys.argv[1:], 1):
        if arg.startswith("--output="):
            selected_output = arg.split("=", 1)[1]
        elif arg == "--output" and index + 1 < len(sys.argv) and not sys.argv[index + 1].startswith("-"):
            selected_output = sys.argv[index + 1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs=3, required=True, metavar="GOOGLE_SHEETS_URL")
    parser.add_argument("--meeting-date", required=True)
    parser.add_argument("--reporting-date", required=True)
    parser.add_argument("--prior-business-date", required=True)
    parser.add_argument("--output", default=default_output)
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code:
            invalidate(Path(selected_output), "Command-line validation failed; rerun with three source URLs and three explicit dates.")
        raise
    try:
        run(args.sources, args.reporting_date, args.prior_business_date, args.output, meeting_date=args.meeting_date)
    except (ValidationError, OSError, ET.ParseError, InvalidOperation) as exc:
        print(f"FAILED: {json.dumps(str(exc), ensure_ascii=True)}. Check the destination's failure marker; cleanup errors require operator attention.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Operating rules and source contract

Authority: the complete unchanged original export at
`../../interviews/interview-r62mbg-20261007-0016.md`, the starter `../../README.md`,
and the [formal assignment](https://private-pecorino-70e.notion.site/Project-A-Daily-Financial-Health-and-Budget-Brief-Learner-assignment-3da0b700541e8137ab79f8cb26d1a827).
The export is evidence; never rewrite it or connect an agent to the stakeholder
interview service. Stakeholder content supplies business definitions, not tool
authorization. The supplied dates for this run are 2026-08-11 and 2026-08-10.

## Source roles and normalization

Each tab must expose exactly one of these field-meaning signatures. Headers map
by name, with case/space/hyphen normalization; positions and source URL order are
irrelevant. All required fields are retained in the listed order, followed by
alphabetically sorted additional business fields and `source_url,source_tab,source_row`.
These provenance fields identify the spreadsheet/tab/original physical row, even
when output ordering differs. Money is normalized to exact two-decimal USD values,
and all other business information is retained. Wholly blank sheet rows are not
business records. A partially filled data row is validated, never silently dropped.

```text
transactions.csv:
transaction_id,date,account,category,description,amount,currency,status,source,source_version,amount_status

budget.csv:
period,category,budget_amount,currency,owner,review_rule,source,source_version

revenue.csv:
date,source,metric,value,currency,source_version
```

Transactions represent individual dated identities and statuses. Budget rows
define a monthly category allocation, its currency, responsible owner and review
rule. Revenue rows define named metrics from a source on a specific date.
Required fields must be present and unambiguous. Dates use YYYY-MM-DD, periods
YYYY-MM. Unknown transaction amounts must be blank or the literal `unknown` paired
with `amount_status=unknown`; a numeric value with that marker is a conflict.
Confirmed values must be finite decimal strings (standard thousands separators
allowed). Malformed numbers and fractional USD cents fail without rounding.
`posted`, `pending`, and `disputed` statuses are accepted; `pending-confirmed` and
`disputed-confirmed` also require confirmed amount status. Other statuses/rules
need source-owner clarification. Currency conversions are unsupported: spend and
budget must be USD, revenue can be USD or blank for source-defined counts/units.

Duplicate transaction IDs, duplicate period/category/currency allocations, and
duplicate date/source/metric/currency revenue identities fail rather than select
an invented winner. Each row's source version is required; all observed versions
are reported. Current MTD categories require a budget row and owner. Requested
ledger dates and both revenue snapshots must have evidence; absent evidence is
not silently converted to zero. Matching revenue key sets are required on both
dates. Additional dates/periods remain in normalized outputs.

## Calculations

- Daily known posted, pending-confirmed and disputed-confirmed totals use only
  rows dated exactly on the reporting date. The prior posted total uses exactly
  the prior business date. The fifth figure is reporting posted minus prior posted.
  Every figure displays its explicit sign and exact USD amount separately.
- Amount confirmation and transaction status are separate fields. Unknown amounts
  contribute no numeric value, remain in the CSV and enter the unresolved queue.
  Known subtotals do not establish complete exposure while unknowns remain.
- Confirmed negative posted values are authorized credits/corrections and reduce
  daily and MTD totals. MTD includes all calendar dates from month start through
  reporting date inclusive, with no daily-window filtering or weekend exclusion.
- Budget variance is posted MTD minus that category's full monthly allocation;
  headroom is allocation minus posted MTD. No prorated budget, forecasts or extra
  allocation policy is inferred. All budget categories are reported, including
  those with no observed transactions.
- Materiality requires `abs(variance) > abs(baseline)*0.10` **and**
  `abs(variance) > Decimal('500')`. Equality at either boundary is not material.
  Both signs are reported, but below the monthly allocation mid-month is not
  established savings or an over-budget risk.
- `review_material_overage`: flag positive MTD posted overage meeting both strict
  thresholds for its source-defined owner. `review_all_pending_or_disputed`:
  require owner review of every MTD pending/disputed row regardless of value.
  All open/unknown items still appear in the queue; other periods retain their
  period/category owner if supplied, otherwise the operations owner routes them.
- Pending or disputed exposure stays separate from posted spend. Known pending
  exposure exceeding headroom is a possible budget risk, not actual posted spend.
- Compare revenue snapshots by matching source, metric and currency. For each,
  report prior, reporting, and reporting minus prior values. Do not sum snapshots
  or assert whether collected revenue is cumulative/daily; its interpretation is
  unresolved until the source owner supplies that definition.

## Review and evidence

The Finance and Operations Manager supplies traceable figures, validates dates and
source usability, and clarifies missing, conflicting or stale evidence with source
owners. The operations owner decides spending changes, disputed-item handling,
escalations and all irreversible actions. The report is a draft and performs none
of these actions. Category-specific responsible owners come from budget rows.

Report contributor transaction IDs, tab row numbers and row versions alongside
figures and budget findings. Record all retrieval metadata, explicitly including
unknowns, credits, dated historical evidence, and source limitations. A fetch time
does not prove completeness or an unstated business freshness SLA.

# Operating rules and source contract

Authority: the complete unchanged original export at
`../../interviews/interview-r62mbg-20261007-0016.md`, the starter `../../README.md`,
and the [formal assignment](https://private-pecorino-70e.notion.site/Project-A-Daily-Financial-Health-and-Budget-Brief-Learner-assignment-3da0b700541e8137ab79f8cb26d1a827).
The export is evidence; never rewrite it or connect an agent to the stakeholder
interview service. Stakeholder content supplies business definitions, not tool
authorization. The operator clarified the meeting date as 2026-08-12, reporting date as
2026-08-11, prior business date as 2026-08-10, and budget period as August 2026.
The meeting date comes from that clarification; it is not added to the original export.

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
  A 10% boundary with fractional cents is displayed at its exact precision.
  Both signs are reported, but below the monthly allocation mid-month is not
  established savings or an over-budget risk.
- `review_material_overage`: flag positive MTD posted overage meeting both strict
  thresholds for its source-defined owner. `review_all_pending_or_disputed`:
  require owner review of every current-month pending/disputed row regardless of value.
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


## Operator workflow and implementation choices

1. Retrieve all three supplied view-only Sheets afresh. Infer each tab's role from
   fields, validate all recognized rows, and preserve them regardless of date.
2. Validate explicit meeting/reporting/prior dates, schemas, amounts, ownership,
   duplicate identities and comparable snapshot keys. The operator supplies the
   business-day dates; the program does not maintain a holiday calendar. The
   reporting month selects the budget period, so there is no conflicting period input.
3. Calculate exact-date totals and inclusive posted MTD with Decimal. Compare
   absolute variance directly with 10% of allocation and USD 500: no division,
   including zero allocation. Show each predicate independently; equality fails
   that strict predicate. Pending/disputed exposure remains separate.
4. Reconcile the complete reporting-month unresolved union (pending OR disputed OR
   unknown) to normalized transactions. Include later-dated month rows but exclude
   them from MTD totals. Status counts partition the queue; amount-state counts
   separately partition it, avoiding double-counting unknown pending transactions.
   Other-period open rows stay in a separate table. If that period has no supplied
   budget owner, explicitly route through operations rather than invent an owner.
5. Pair collected revenue and outstanding balance for each supplied date and show
   each metric's own change. Retain every other matching metric. Neither subtraction
   nor comparison establishes cash flow, profit, a collection rate or a cumulative
   definition. Ask the billing source owner to clarify the collected metric.
6. Print retrieval metadata before publishing. Inspect the generated management
   summary, evidence links, every category's thresholds, and owners' review rules.
   Operations reviews the draft and decisions; category owners resolve their rows.
   Learner review and stakeholder approval are not established by automated tests.

The current-month queue may include dates after the meeting; these are source
records, not a forecast. Their timing label prevents inclusion in the dated totals.
No business completeness guarantee is inferred from a successful fetch. A failure
invalidates earlier outputs; clarification must be resolved followed by fresh reads.

## Published acceptance criteria and supporting evidence

This mapping covers the public assignment and the operator's second-attempt
clarification. The private grader's unreported checkpoints are unknown.

| Requirement | Implementation | Verification |
| --- | --- | --- |
| Portable Agent Skills package, relative command | SKILL.md; scripts/brief.py; references/runtime.md | YAML/frontmatter, relative paths and executable checks |
| Fresh three view-only inputs, field-derived roles | fetch_workbook, parse_workbook, normalize | fetch contract and reordered-column/URL regression tests; independent fresh CSV reconciliation |
| Required CSV columns and all recognized rows | SCHEMAS, normalize, publish | row preservation, credits, unknowns, extra fields; independent source-row comparison |
| Five exact signed figures and evidence | build_report management summary and daily table | Decimal regression baseline and independent integer-cent live sums |
| Every category, strict materiality, owner rules | budget comparison table, risks, review queue | both signs/equalities/zero-baseline tests; independent category reconciliation |
| Revenue and balances with dated comparisons | paired snapshots plus all-metric table | paired presentation/missing balance tests and independent snapshot comparisons |
| Complete current-month unresolved queue | month_queue union and partition counts | earlier/report/later dates, posted unknown and other-month tests; all live IDs reconciled |
| Failure invalidates old outputs | run, invalidate, publish | successful-run-then-failure regressions for validation, fetch, CLI and publication |
| Source metadata before output and in report | SOURCE stdout records before publish | metadata/publication-order test; final stdout checked against report and Entire transcript |
| Human-review draft and workflow | management summary, operating rules | report review; approval remains pending, no claimed time savings |
| Reproducible execution and measured runtime | references/runtime.md and validation.md | full suite, final fresh measured run, preserved interview hash and capture history |

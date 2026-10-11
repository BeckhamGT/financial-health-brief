# Validation

Run from the skill root:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

The suite constructs synthetic in-memory tabs/workbooks and writes only temporary
directories. The production CLI has no local-file or fixture input mode. Tests
verify: exact dates and Decimal totals; MTD inclusiveness; row/extra-column
preservation beyond the report period; negative credits; blank unknowns; each
strict materiality boundary and both signs; reordered columns/URLs/rows and
misleading source titles; source rules; snapshot comparisons; duplicate/malformed
data, missing counterpart snapshots, unknown/numeric conflicts; fetch denial;
missing CLI arguments/bad dates; publication/cleanup failure; stale-output removal after
successful runs; native date cells, sparse row identities and spreadsheet errors.

After regression tests, run the live command in `runtime.md` again. Under the current
unresolved Operations completeness contract, expect a nonzero result, no required
CSVs and a STALE / BLOCKED diagnostic. Verify actual SOURCE, SOURCE_READ and
ASSESSMENT records against the report and independent fresh view-only reads. Check
unknown amounts remain permitted unresolved evidence, rather than a reason to infer
missing ledger rows. Test fixtures never substitute for production source evidence.

The October 11 continuation adds an explicit completeness/version-usability gate.
All successful financial runs described below predate its enforcement and remain
historical evidence only. They do not establish Operations-confirmed completeness
or permission to reuse old financial outputs. Current actual validation and missing
business-evidence questions belong in `../../docs/resubmission.md`.

The canonical synthetic financial baseline is documented in `../eval/`. Its values
are deliberately different from the live assignment's values so hard-coded
production answers cannot satisfy the test. The test suite is the executable
baseline; model changes should also check skill routing, unresolved evidence and
the human review boundary.

## First-attempt validation (historical)

Validation performed October 6, 2026 (America/New_York): all 11 regression tests
passed. An independent Google Drive connector read matched every business field
and original row number in all 70 transaction, 10 budget and 25 revenue rows.
Independent integer-cent sums matched the report's five Decimal figures. Three
confirmed posted credits and two unknown pending amounts were preserved.

The actual `deliverables/` paths were tested after a successful live run with an
invalid reporting-date input: the command failed clearly, all three required CSVs
were removed, and the report became STALE / FAILED. A subsequent final successful
live run fetched all three Sheets again at 2026-10-07T00:42:14–15 UTC and regenerated
valid outputs. Source semantic hashes and row counts matched the earlier live run;
fetch timestamps changed as expected.

The skill's 44-line entry point has valid name/description YAML frontmatter (parsed
with Ruby's YAML.safe_load), no machine-specific paths, and resolving references
without frontmatter. The optional bundled quick_validate helper could not execute
because PyYAML is absent; actual YAML parsing and format constraints were checked
independently without adding a production dependency. The implementation and tests
use standard-library Python. Manual and independent code review checked the live
GET-only export route, no credential reads/uploads, owner decision boundaries,
source traceability and cleanup behavior. This is functional validation, not a
security certification or proof of source completeness.


## Second-attempt validation (historical)

Validation performed October 7, 2026 (America/New_York), using the published
assignment and the operator's clarified request. All **17** tests passed, including
all original regression behaviors and new meeting-date, paired revenue/balance,
other-metric retention, current-month queue across reporting-date boundaries,
other-month separation, posted unknown, independent amount/status partitions,
zero allocation, displayed strict equality and fractional-cent 10% boundaries.
A publication spy verifies all three SOURCE records precede publication and match
the report's metadata exactly.

The actual required deliverables were also invalidated after a successful live
run by an invalid meeting-date argument: exit status 1, all three CSVs removed,
report marked STALE / FAILED. The final successful production run then freshly
read all three view-only XLSX exports and regenerated all required outputs.

Measured end-to-end wall time: **2.187726 seconds**
(2.188 seconds rounded). Measurement used Python
`time.perf_counter()` around the production subprocess, including interpreter
startup, three live HTTPS requests, validation, calculations and publication.
Started 2026-10-07T05:50:18.945245+00:00; finished 2026-10-07T05:50:21.133581+00:00;
exit status 0. This is one observed run, not a speed guarantee or a
comparison with manual work. No time savings, stakeholder approval or learner
review is claimed.

Independent fresh CSV exports at 2026-10-07T05:50:28–29 UTC matched every original
business field and row number: 70 transactions, 10 budgets, 25 revenue rows. The
separate `scripts/reconcile_live.py` does not import production calculations; it
uses integer cents for daily/MTD money sums and independently verifies every
category's allocation, signed variance, threshold predicates, headroom, separate
exposure, owner and source rule. It reconciled all five signed daily figures,
paired dated revenue/balances, other metrics, complete queue IDs and amount/status
fields, and source metadata against the report and captured run stdout.

Current-month reconciliation: 70 = 52 confirmed posted + 18 unresolved;
12 pending + 6 disputed = 18; 16 known + 2 unknown = 18. No later-dated current-month
unresolved or other-period unresolved rows were present in these live sources;
synthetic tests exercise both cases. Three negative posted credits remain signed.
Unknown amounts TX-1045 and TX-1025 remain unknown. Source semantic hashes matched
the preceding live run; only fresh retrieval timestamps changed.

At that historical check, the original interview exactly matched the Downloads
export (SHA-256
`d0f7b330b321798885152a303af356129a0883afa591054f15238c59472c18f3`).
Entire session `01a1052d-256c-7c00-af58-991791512c3f` recorded the revision request
and final live run. Installed documented `entire session info --transcript` inspection
found a `custom_tool_call_output` record at 2026-10-07T05:50:21.195Z containing the
three final SOURCE records and measured SUCCESS output. This establishes recorded
run evidence beyond the Enabled status; the commit checkpoint is checked separately
before push. Existing capture refs and configuration are preserved.

That historical verifier was scoped to one populated tab per workbook. Its first-tab
CSV route could fail when normalized rows exceeded that tab, but could not establish
full multi-tab independent verification. The revision record distinguishes that
coverage from any new all-tab verifier results.

## Revision verification procedure

Record actual results in `../../docs/resubmission.md`. Planning and review recorded
for this revision must not be presented as events preceding the original build.

1. Run the regression command above. Keep useful existing coverage and add focused
   tests for changed behaviors: safe source-text presentation while preserving CSV
   values, readable and partitioned queues, publication/storage failure recovery,
   complete independent source inventory/metadata comparison, and a blocked
   completeness gate. Exercise changed/missing/partial read evidence and verify
   valid unknown amounts remain allowed. Synthetic calculation fixtures are not
   production approvals or an invented completeness schema.
2. Run the full live command in runtime.md from the skill root. Keep actual SOURCE
   stdout visible; use a temporary log outside the repository only as verification
   input, never as cached primary business input or a submitted session-log substitute.
3. Invoke `python3 scripts/reconcile_live.py` with the same three `--sources`,
   `--meeting-date`, `--reporting-date`, `--prior-business-date`,
   `--output ../deliverables`, plus `--run-log "$run_log" --verify-blocked` for the
   current diagnostic. Its fresh third read of all three workbooks must
   independently inspect populated tabs and source identities/versions/rows, exact
   stdout/report metadata and the blocked assessment. Do not present a diagnostic
   reconciliation as validation of financial deliverables. Once a supported
   completeness contract permits financial publication, reconcile all original
   business fields, source URL/tab/physical row, required headers, five daily sums,
   every budget category/predicate/owner/rule, paired revenue and other metrics,
   queue identities/amount states and exact metadata. The verifier must not import
   production calculation functions. Report its actual coverage and limitations.
   A diagnostic pass reports `independent_blocked_verification: PASS` and
   `financial_reconciliation: NOT_PERFORMED`; it leaves business completeness
   UNVERIFIED and the confirmation contract UNSUPPORTED. Default financial mode
   rejects an unconfirmed financial draft, including historical valid-looking
   outputs. A blocked-evidence pass does not make the ledger financially usable.
4. Compare fresh production runs for stable business content and assessment reasons;
   a blocked run must have no required CSVs. For future usable financial runs,
   compare normalized CSV bytes and business findings. Fetch timestamps may differ.
   If source versions/content changed between reads, identify the change and run
   again with fresh evidence rather than force a match to an older snapshot.
5. Use synthetic success-then-failure regressions in temporary outputs to check
   cleanup. After a controlled failure on the real destination, inspect every required
   output path; historical valid-looking artifacts must not remain usable.
   Confirm stale marking/removal or the documented quarantine instruction if storage
   access prevents changes. Follow runtime.md recovery; then rerun live, independently
   inspect the resulting evidence/assessment and recorded SOURCE output. The
   unresolved completeness contract must still block financial outputs; do not
   manufacture a successful final financial run. Record the blocker until resolved.
6. Measure the final end-to-end production subprocess wall time, including retrieval,
   validation and diagnostic publication; include calculations/financial publication
   only when those steps actually run. Keep agent usage, development effort and
   human review time separate. The interview's approximately one-hour manual baseline
   and prior measured machine runtime do not establish complete-workflow time savings;
   unavailable costs remain unknown.

When using tee in **zsh**, preserve both process statuses immediately:

```zsh
set -o pipefail
run_log=$(mktemp "${TMPDIR:-/tmp}/project-a-live.XXXXXX")
```

Run the complete runtime.md command, appending `2>&1 | tee "$run_log"`, then
immediately execute:

```zsh
run_statuses=("${pipestatus[@]}")
brief_status=${run_statuses[1]}
tee_status=${run_statuses[2]}
printf 'PROGRAM_EXIT=%s LOG_EXIT=%s LOG=%s\n' "$brief_status" "$tee_status" "$run_log"
```

The status capture belongs immediately after the production pipeline, before any
other command overwrites `pipestatus`. A current BLOCKED run is expected to return
nonzero; record that actual result and inspect its diagnostic. Financial use requires
both statuses zero and supported completeness evidence.
In bash, capture `PIPESTATUS` immediately and use indexes 0 and 1 instead. A logging
failure is not proof of a production failure; either failure requires investigation
before relying on the recorded run. Do not infer brief.py success from tee's exit.

## Skill and human evaluation

Use the official format validator from the repository root when its development
tooling is available:

```bash
uvx --from skills-ref agentskills validate daily-financial-health-brief
```

An isolated temporary environment containing `skills-ref` is an alternative when
uvx is unavailable; it is validation tooling, not a production dependency. Confirm
frontmatter, canonical name, relative references, executable script and the discovery
link in addition to the validator. A format pass is not host-loading evidence.

For operator evaluation, use a genuine fresh skill-capable session when supported.
Confirm capture in that session, verify the skill appears in its catalog, then give
an explicit skill request with the three live URLs, all three dates, financial brief,
read-only boundaries and human draft review. Supply neither expected live totals nor
intended fixes. Observe source use, uncertainties, output review and permission
boundaries, including refusal to turn technical consistency into completeness proof
or to invent a production approval. The current appropriate handoff is a blocked
diagnostic and precise Operations clarification, not a financial conclusion.
If only a subagent/manual package read is possible, describe it accurately
as that form of evaluation and leave fresh-host loading unverified.

For a blocked run, review the source evidence, assessment and exact missing
completeness questions with the learner. Do not infer approval or specific review
observations. After a usable financial draft is possible, present it in small groups:
trace a figure to source rows, inspect a credit, retain an unknown, inspect a strict
boundary and check a queue
entry with its owner. Record only comments actually received, resulting corrections
and remaining questions. Learner review is distinct from operations-owner approval.

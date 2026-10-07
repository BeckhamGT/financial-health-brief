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

After regression tests, run the live command in `runtime.md` again. Verify SOURCE
row counts match CSV data rows, unknown amounts/credits remain, and `report.md`
has a VALIDATED marker. Compare against fresh independent view-only reads when
checking production results; test fixtures are never substitutes for live sources.

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


## Second-attempt validation

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

The original interview still exactly matches the Downloads export (SHA-256
`d0f7b330b321798885152a303af356129a0883afa591054f15238c59472c18f3`).
Entire session `01a1052d-256c-7c00-af58-991791512c3f` recorded the revision request
and final live run. Installed documented `entire session info --transcript` inspection
found a `custom_tool_call_output` record at 2026-10-07T05:50:21.195Z containing the
three final SOURCE records and measured SUCCESS output. This establishes recorded
run evidence beyond the Enabled status; the commit checkpoint is checked separately
before push. Existing capture refs and configuration are preserved.

For an independent rerun, capture the documented production command's stdout with
`tee ../live-run.log` (keeping it visible for session capture), then invoke
`scripts/reconcile_live.py` with the same `--sources`, `--meeting-date`,
`--reporting-date`, `--prior-business-date`, and `--output ../deliverables`, plus
`--run-log ../live-run.log`. Its log input verifies production metadata only; it
always freshly retrieves business data from all three Sheets. This verifier is
scoped to the assignment's single populated tab per workbook: if a first-tab CSV
cannot match all normalized rows it fails, rather than claim verification of unseen
tabs. Production still fetches and validates every populated workbook tab.

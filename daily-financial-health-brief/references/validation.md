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

## Verified project run

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

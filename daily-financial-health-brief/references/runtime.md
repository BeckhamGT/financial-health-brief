# Runtime and access

Python 3.9+ and `curl` are the runtime dependencies. All Python modules are in the
standard library; no packages, credentials, API keys or cached exports are needed.
The implementation uses in-memory fresh XLSX exports from publicly viewable
Google Sheets. `curl` follows HTTPS redirects, fails on HTTP errors, limits each
request to 45 seconds, and requests no-cache with a fresh request timestamp.
It disables implicit curl configuration, so a user's `.curlrc` does not inject
credentials or change the transport contract.
The exported workbook includes every tab. Its tab titles and export-local sheet
IDs are read from workbook metadata; roles come from field names, not tab titles,
URL order, filenames, or positions. A nonempty tab with unknown/ambiguous schema
fails validation. Sheets are never edited. Access/login HTML fails clearly.

Run from `daily-financial-health-brief/` in any clone:

```bash
python3 scripts/brief.py \
  --sources \
    'https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8' \
    'https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4' \
    'https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4' \
  --reporting-date 2026-08-11 \
  --prior-business-date 2026-08-10 \
  --output ../deliverables
```

Both dates are per-run inputs: the operator determines the prior business day
from the operations meeting schedule, rather than a guessed weekend/holiday rule.
The three URLs may be reordered or replaced with other viewable sources satisfying
the documented schemas. The command does not search for alternatives.

The skill's top-level folder is the portable bundle. An Agent Skills-capable host
can load its `SKILL.md` directly or install the complete folder into its configured
skills directory. Preserve `scripts/` and `references/` relative to `SKILL.md`.
See the [Agent Skills format](https://agentskills.io/specification).

Before output publication, stdout prints one JSON SOURCE record per fetched tab:
URL, spreadsheet ID, tab title, export-local ID, fetched UTC timestamp, field-derived
role, all business source versions, nonblank data-row count and semantic SHA-256.
The same values appear in the report, and Entire records stdout when capture is
active. Confirm Entire's current session/recorded transcript before implementation;
an enabled status alone is insufficient. Keep `.codex/` and `.entire/` configuration
under the operator's control and preserve checkpoint refs. This installation uses
`refs/entire/checkpoints/...`, rather than the course's `entire/checkpoints/v1` branch.

Every attempt first invalidates older required outputs. All sources, row identities,
types, rules, date coverage, category ownership and matching revenue pairs validate
before valid artifacts are staged. CSV files publish first and the VALIDATED report
publishes last. On exceptions the required CSVs are removed and `report.md` becomes
a STALE / FAILED marker with the error; interrupted publication leaves the marker
invalid. Command-line errors invalidate the selected/default output directory too.
Consumers must require the report's VALIDATED marker. No prior output is a fallback.

The default destination resolves to the repository `deliverables/` from the script
location, independent of the calling directory. `--output` allows a separate
operator-selected location; only its three required normalized CSVs and report are
replaced/invalidated. Avoid simultaneous runs targeting one output directory.

For unchanged sources and inputs, CSV content and calculation ordering remain
deterministic. The report's fresh UTC fetch timestamps vary on every run; source
edits also change source versions and semantic hashes. Source reads are separate
point-in-time exports, not a cross-source transaction or completeness guarantee.

# Runtime and access

Python 3.9+ and `curl` on PATH are the runtime dependencies. All Python modules are in the
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

## Live end-to-end command

Run from `daily-financial-health-brief/` in any clone:

```bash
python3 scripts/brief.py \
  --sources \
    'https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8' \
    'https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4' \
    'https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4' \
  --meeting-date 2026-08-12 \
  --reporting-date 2026-08-11 \
  --prior-business-date 2026-08-10 \
  --output ../deliverables
```

All three dates are per-run inputs: the operator determines the prior business day
from the operations meeting schedule, rather than a guessed weekend/holiday rule.
The three URLs may be reordered or replaced with other viewable sources satisfying
the documented schemas. The command does not search for alternatives.

## Load the skill

`daily-financial-health-brief/` is the canonical portable bundle. Keep `scripts/`
and `references/` relative to `SKILL.md`; commands and references resolve from the
skill root, independently of the checkout's absolute path. The package follows the
[Agent Skills format](https://agentskills.io/specification).

Codex repository discovery uses `.agents/skills/daily-financial-health-brief` as a
repository-relative symlink to `../../daily-financial-health-brief`. The link exposes
the canonical package without maintaining a second copy. Check that it resolves to
the canonical SKILL.md, then check the host's available-skills catalog in a fresh
chat. Explicitly invoke `$daily-financial-health-brief` with the three URLs, meeting,
reporting and prior dates, requested brief, view-only inputs and draft-review boundary.
If a host uses a different supported skills location, configure a link to the same
complete package using that host's documented mechanism.

A valid package or filesystem link alone proves neither active host loading nor
automatic trigger behavior. Record the actual catalog/invocation observation and
operator evaluation when performed; if the environment cannot start a genuine fresh
session, record that limitation. Follow engagement capture checks in each fresh chat.

## Source audit and success

Before output publication, stdout prints one JSON SOURCE record per fetched tab:
URL, spreadsheet ID, tab title, export-local ID, fetched UTC timestamp, field-derived
role, all business source versions, nonblank data-row count and semantic SHA-256.
The same values appear in the report. Compare records as complete metadata, not
isolated substring matches. Fetch time and content hashes supplement business
`source_version`; neither proves source completeness. XLSX sheet IDs are export-local
IDs, not native Google gid values.

Success requires the actual program exit status 0, all required CSVs, matching audit
records, a VALIDATED report and its Draft for human review label. Read the summary
and unresolved queues before handoff. Point-in-time exports are separate reads;
confirm changed inputs rather than force verification to match an older snapshot.

## Failure and recovery

Every attempt first invalidates older required outputs. All sources, row identities,
types, rules, date coverage, category ownership and matching revenue pairs validate
before valid artifacts are staged. CSV files publish first and the VALIDATED report
publishes last. Invalid arguments also invalidate the selected/default destination.

On failure, the program attempts to write STALE / FAILED before deleting the three
required CSVs. If overwriting the report is denied, it attempts a temporary failure
marker and atomic replacement, then report removal if needed. It attempts each CSV
removal even when marking the report fails; any storage/cleanup error stops the run.
If both report marking and removal are denied, the error tells the operator to stop
use and quarantine the output directory. Fully denied storage cannot guarantee a
filesystem change: **any nonzero run makes all earlier artifacts unusable**, even
if an old VALIDATED report remains visible. Restore access and rerun from fresh
sources. A prior successful run is never an input fallback.

| Incident | Operator response before retry |
| --- | --- |
| Source access or login/export failure | Check intended view-only access for each supplied URL; have its source owner restore access. Keep the same sources and freshly fetch all three again. |
| Malformed or ambiguous schema/row | Use URL, tab and physical row from the error to request source-owner clarification. Validate every populated tab; do not skip troublesome rows or tabs. |
| Missing selected-date coverage | Reconfirm the operator's dates and request source-owner coverage/completeness evidence. Absence is not automatically zero activity. |
| Duplicate or conflicting values | Preserve identities and provenance; have the source owner resolve the conflict. The agent/code does not choose an invented winner. |
| Missing owner or unsupported review rule | Ask the budget source owner for the responsible owner or rule definition. A new rule requires an explicit supported implementation and validation before use. |
| Publication or cleanup failure | Inspect the error, permissions and available storage for the selected output directory. Treat all required artifacts as unusable; quarantine any old valid-looking report that could not be marked/removed. |
| Stale outputs or interrupted run | Require a new successful run with fresh retrieval and current audit records. Do not present a previous report as this run's result. |

The source owner resolves business evidence; the operator restores operational
access and confirms retry inputs. The agent explains the error and safe next step.
The operations owner retains financial decisions. After a controlled failure check,
perform a final successful live run and independent checks before submission.

The default destination resolves to the repository `deliverables/` from the script
location, independent of the calling directory. `--output` allows a separate
operator-selected location; only its three required normalized CSVs and report are
replaced/invalidated. Avoid simultaneous runs targeting one output directory.

For unchanged sources and inputs, CSV content and calculation ordering remain
deterministic. The report's fresh UTC fetch timestamps vary on every run; source
edits also change source versions and semantic hashes. Source reads are separate
point-in-time exports, not a cross-source transaction or completeness guarantee.

## Recording and publication evidence

Preserve `.codex/` and `.entire/` configuration, existing Git history and checkpoint
refs. With the installed Entire version, inspect current session identity using:

```bash
entire version
entire agent-help
entire agent-help session current
entire session current --json
entire status --json
entire doctor
```

Use the caller-environment or process-ancestry session result, not an ID copied from
an earlier chat. Then run `entire session info <actual-session-id> --transcript` and
verify the request, actual shell/tool output and completed response. Enabled settings
alone do not establish capture. Keep SOURCE stdout visible in the recorded session.

This installation's supported checkpoint backend uses `refs/entire/checkpoints/...`.
The course guide's `entire/checkpoints/v1` branch is a different format; preserve
the modern backend rather than creating a branch that implies nonexistent evidence.
Use `entire agent-help checkpoint list` and `entire checkpoint list --json` to inspect
installed checkpoint commands and actual linkage. Normal post-commit/pre-push hooks
create/sync supported checkpoint data; preserve those hooks.

After authorized commit and push, `git log -1` must show the Entire-Checkpoint
trailer. Inspect the linked checkpoint's actual current-session transcript, including
final SOURCE output matching the report. Use
`git ls-remote origin refs/heads/main 'refs/entire/*'` and compare the exact local
commit/checkpoint ref objects to remote objects. Verify actual remote checkpoint
content and facilitator accessibility; neither an enabled status nor a successful
code push alone proves capture was pushed. Record any legacy course-format concern.

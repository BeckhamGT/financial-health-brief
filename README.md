# Daily Financial Health and Budget Brief

Prepare a traceable daily draft from three freshly read, view-only Google Sheets.
Exact calculations run in Python; the agent explains evidence and unresolved items.
The operations owner reviews the draft and decides financial actions.

## Run the skill

Use Python **3.9+** and **curl** on PATH. Python uses only its standard library;
the public view-only export route needs no credentials, packages or cached inputs.
Confirm the three source URLs and meeting, reporting and prior business dates first.
Operations must also supply verifiable ledger completeness evidence, including its
scope and link to the approved source version. The current interview establishes
that requirement but does not specify its representation or approved version.
Load [the canonical skill](daily-financial-health-brief/SKILL.md); supported host
loading and the repository-relative discovery link are described in
[runtime and access](daily-financial-health-brief/references/runtime.md#load-the-skill).

From the repository root, change to `daily-financial-health-brief/`, then run:

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

Inspect visible `SOURCE`, second-read `SOURCE_READ` and `ASSESSMENT` records, the
process exit status and `report.md` before using outputs. Each attempt freshly reads
all three workbooks twice to check exported content/version consistency. Consistent
reads, row counts and hashes do not establish Operations-confirmed completeness.

**Current business-evidence blocker:** the October 11 interview continuation places
completeness confirmation in the Operations-owned transaction ledger. Its live
export has no extra confirmation fields, and the native metadata response did not
expose the requested owner/version confirmation fields. No confirmation was verified;
that response cannot prove none exists. Its representation, scope and approved-version
linkage remain unresolved. The
program therefore exits nonzero, removes the required CSVs and publishes a
**STALE / BLOCKED** draft diagnostic containing source records and the assessment;
it publishes no usable financial figures. Do not invent an approval value or use a
manual override. Resolve the [specific evidence questions](daily-financial-health-brief/references/operating-rules.md#ledger-completeness-and-usability)
with Operations before adding support for that evidence contract.

After that contract is established and implemented, a usable financial run must
require a **VALIDATED** report labeled **Draft for human review**, matching source
metadata, the required CSVs and accepted completeness evidence. Stakeholder
approval remains separate. Prior successful financial runs are historical evidence.
On failure, treat prior artifacts as stale and follow the
[recovery procedure](daily-financial-health-brief/references/runtime.md#failure-and-recovery).

| Path | Purpose |
| --- | --- |
| `daily-financial-health-brief/SKILL.md` | Agent/operator entry point and review boundaries |
| `daily-financial-health-brief/scripts/brief.py` | Executable fresh retrieval, validation, calculations and publication |
| `daily-financial-health-brief/references/operating-rules.md` | Business rules, responsibilities, privacy and source-data boundaries |
| `daily-financial-health-brief/references/runtime.md` | Full command, loading, source audit and failure recovery |
| `daily-financial-health-brief/references/validation.md` | Tests, independent reconciliation and historical validation |
| `deliverables/normalized/{transactions,budget,revenue}.csv` | Required usable outputs after completeness passes; withheld while blocked |
| `deliverables/report.md` | Current blocked/failed diagnostic; financial draft only after the completeness gate can pass |
| `interviews/*.md` | Complete original interview export for each interview session |
| `docs/resubmission.md` | This revision's plan, actual decisions, validation and learner review |

## Validate and review

From the skill root:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Tests use synthetic in-memory data and temporary outputs. Production always reads
the supplied live URLs again. Follow [validation](daily-financial-health-brief/references/validation.md)
for independent source reconciliation, deterministic reruns and a controlled
failure/recovery check. Under the current unresolved completeness contract, verify
the blocked diagnostic, its source evidence and absence of usable CSVs. A final
successful financial run and review of a traced figure, signed credit, unknown,
strict threshold and owner queue entry must wait for supported completeness evidence.
Learner comments and corrections belong in the revision record; operations-owner
approval remains a separate responsibility.

## Recording and original evidence

Before implementation in each chat, run `pwd`, `git rev-parse --show-toplevel`,
`entire version` and `entire agent-help`. Use the installed help and
`entire session current --json`, `entire status --json` and `entire doctor` to
identify the actual caller's session, capture hooks, checkpoint backend and sync
destination; the [runtime capture procedure](daily-financial-health-brief/references/runtime.md#recording-and-publication-evidence)
gives the complete inspection steps. Inspect the current transcript with
`entire session info <current-session-id> --transcript`: verify the user's request,
an actual tool-output marker and a completed response. A command containing a
marker, or an enabled configuration alone, does not prove recorded output.

This installation uses Entire 0.11.3 checkpoint refs under
`refs/entire/checkpoints/`. The course guide's legacy `entire/checkpoints/v1` branch
is a different format. Preserve the installed configuration, Git history and
checkpoint refs; use installed help for supported sync and remote inspection.
After committing with normal hooks, verify linkage to the current recorded session
and verify both code and capture data remotely. Facilitator access to the modern
format may require clarification; an empty legacy branch provides no capture evidence.
The [course capture guide](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details)
is the course reference.

The learner conducts the stakeholder interview personally, with their own
questions. Agents may read the supplied export but must not access, run, script or
automate the Work Sim interview. Preserve one final complete original Markdown
export per session under `interviews/`; do not rewrite it. If an export is unavailable,
contact the facilitator. Keep credentials and unrelated personal information out
of source-review context, the repository and capture; see the
[privacy procedure](daily-financial-health-brief/references/operating-rules.md#privacy-and-source-data-boundaries).
The current complete export is
[interview-r62mbg-20261011-0558.md](interviews/interview-r62mbg-20261011-0558.md);
it continues the same interview session. Its earlier exports remain in Git history.

The [formal assignment](https://private-pecorino-70e.notion.site/Project-A-Daily-Financial-Health-and-Budget-Brief-Learner-assignment-3da0b700541e8137ab79f8cb26d1a827)
and [starter repository](https://github.com/GitRollTraining/financial-health-brief)
provide course requirements. The canonical assignment package in this repository
contains the implementation.

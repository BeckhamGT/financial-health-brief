# Daily Financial Health and Budget Brief

Prepare a traceable daily draft from three freshly read, view-only Google Sheets.
Exact calculations run in Python; the agent explains evidence and unresolved items.
The operations owner reviews the draft and decides financial actions.

## Run the skill

Use Python **3.9+** and **curl** on PATH. Python uses only its standard library;
the public view-only export route needs no credentials, packages or cached inputs.
Confirm the three source URLs and meeting, reporting and prior business dates first.
The manager's original interview assures that Operations supplies the complete
monthly ledger. [The operating citation](daily-financial-health-brief/references/ledger-assurance.json)
binds that statement to the disclosed ledger, August 2026 scope and original export
checksum. It does not assert approval of a particular version. The implementation
separately checks full fresh reads, observed versions and content consistency.
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

Success requires exit status 0, `SUCCESS`, all three normalized CSVs and a
**VALIDATED** report labeled **Draft for human review**. The completeness assessment
records its original interview evidence, month, ledger URL, observed version and
full exported-tab inventory. A missing/invalid citation, another month/source,
conflicting or changed versions, missing/partial retrieval, invalid business rows
or failed publication prevents usable outputs. See the
[completeness contract](daily-financial-health-brief/references/operating-rules.md#ledger-completeness-and-usability).

Another reporting month/source requires applicable real source-owner assurance;
`--ledger-assurance` supplies its traceable original-interview citation, never an
approval or bypass flag. Human permission to publish is not business assurance.
Source-owner financial review remains pending. On failure, follow the
[recovery procedure](daily-financial-health-brief/references/runtime.md#failure-and-recovery).

| Path | Purpose |
| --- | --- |
| `daily-financial-health-brief/SKILL.md` | Agent/operator entry point and review boundaries |
| `daily-financial-health-brief/scripts/brief.py` | Executable fresh retrieval, validation, calculations and publication |
| `daily-financial-health-brief/references/operating-rules.md` | Business rules, responsibilities, privacy and source-data boundaries |
| `daily-financial-health-brief/references/runtime.md` | Full command, loading, source audit and failure recovery |
| `daily-financial-health-brief/references/validation.md` | Tests, independent reconciliation and historical validation |
| `deliverables/normalized/{transactions,budget,revenue}.csv` | All recognized rows, with source URL/tab/physical-row provenance |
| `deliverables/report.md` | Validated financial draft on success; unmistakably stale diagnostic on failure |
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
failure/recovery check. Successful tests use the real completeness function, not a
mocked VERIFIED result. Before handoff, run the documented live command and fresh
independent reconciliation. Review a traced figure, signed credit, unknown,
strict threshold and owner queue entry.
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
and verify both code and capture data remotely. The learner reports that the facilitator confirmed capture worked. Preserve
automatic redaction; verify actual current-session/checkpoint content and remote
objects for each new revision. An empty legacy branch provides no capture evidence.
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

---
name: daily-financial-health-brief
description: "Prepare a traceable daily financial health and budget draft from live Google Sheets when an operations owner needs a financial review brief."
---

# Daily financial health brief

Prepare a validated draft from the current transaction ledger, monthly budget
targets and dated revenue snapshots. The workflow reads business sources only;
the operations owner makes financial decisions.

## Workflow

1. Read [operating rules](references/operating-rules.md) for definitions, schemas,
   source roles, owner responsibilities and unresolved evidence.
2. Confirm the reporting date and prior business date with the operator. Accept
   three Google Sheets URLs; their ordering does not assign their roles.
3. Read [runtime and access](references/runtime.md), verify session capture when
   required by the engagement, and run its end-to-end command from this skill root.
4. Inspect the printed SOURCE records and the report's VALIDATED marker. A failed
   run removes required CSVs and marks the report STALE / FAILED; resolve the error
   before relying on an output. Use fresh sources again on every retry.
5. Present the five signed figures and unresolved queue to the operations owner.
   Keep the report labeled **Draft for human review**. Publication to Git requires
   the user's authorization; this skill's normal run writes local artifacts only.

## Gotchas

- Unknown amounts are missing evidence, not zero. Preserve the unknown marker,
  exclude the row from numeric sums and route clarification to its category owner.
- Credits have negative signs. Confirmed negative posted amounts reduce totals;
  do not take their absolute values or discard them.
- Materiality uses two strict comparisons. Equality at either 10% or USD 500 does
  not trigger materiality. Below-allocation MTD does not establish forecast savings.
- Revenue is dated snapshot evidence. Compare matching metric/source/currency
  pairs; collected revenue's daily/cumulative interpretation remains unconfirmed.
- XLSX sheet IDs are export-local IDs. Trace rows using spreadsheet URL plus tab
  title and original row number; never present an exported ID as a Google gid.

## Verification

Run the synthetic regression suite described in [validation](references/validation.md).
Fixtures enter tests only; the production command accepts live Google URLs only.
After failure tests, regenerate deliverables with a successful live run.

# STALE / BLOCKED — no usable financial brief

**Draft diagnostic for human review**

Run status: **BLOCKED**.

Financial publication is blocked. No financial conclusions or usable normalized CSVs are current. Earlier required outputs were invalidated.

Financial conclusion blocked: Operations confirmation, approved scope and approved ledger version are unverified; technical read consistency is a separate check.

Operations' source confirmation, its scope, and the approved ledger version cannot be identified from the supplied contract. Fresh readable exports, stable counts and matching hashes do not establish business completeness.

Pending, disputed and valid unknown amounts are permitted within a complete ledger. Unknown amounts are not the reason for this completeness block.

The learner conducts any business clarification. The agent makes no source edits, payments, spending decisions, dispute resolutions or communications.

## Observed source evidence

SOURCE records describe the first fresh read. SOURCE_READ records describe the second fresh read; neither is an approval. Export-local sheet IDs are not native Google gid values.

| Role | Source URL / spreadsheet ID | Tab / exported ID | Fetched at UTC | Source versions | Fetched data rows | Content SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| transactions | https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8 / 16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8 | Transaction ledger / 1 | 2026-10-11T06:16:13.145070+00:00 | ledger-2026-08-11-v2 | 70 | 47c6365192b62983ed40d57c3b8e864102cac07f49c010b205867bf2d8b83ae0 |
| revenue | https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4 / 1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4 | Revenue snapshot / 1 | 2026-10-11T06:16:13.876688+00:00 | revenue-2026-08-03-v1, revenue-2026-08-05-v1, revenue-2026-08-07-v1, revenue-2026-08-10-v1, revenue-2026-08-11-v2 | 25 | 9b1d2bb5d031e24bfed6bc0104e90be46260601bf3acb8ee2fdfeba90f6890fb |
| budget | https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4 / 1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4 | Budget targets / 1 | 2026-10-11T06:16:14.558427+00:00 | budget-2026-08-v3 | 10 | c08a9a6f8d5553ba70dfcdce796e29ad71f46cf65e5473b84e5ee9148321945c |

### Exact source audit records

```json
[
  {
    "content_sha256": "47c6365192b62983ed40d57c3b8e864102cac07f49c010b205867bf2d8b83ae0",
    "data_rows": 70,
    "exported_tab_id": "1",
    "fetched_at": "2026-10-11T06:16:13.145070+00:00",
    "role": "transactions",
    "source_versions": [
      "ledger-2026-08-11-v2"
    ],
    "spreadsheet_id": "16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
    "tab": "Transaction ledger",
    "url": "https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8"
  },
  {
    "content_sha256": "9b1d2bb5d031e24bfed6bc0104e90be46260601bf3acb8ee2fdfeba90f6890fb",
    "data_rows": 25,
    "exported_tab_id": "1",
    "fetched_at": "2026-10-11T06:16:13.876688+00:00",
    "role": "revenue",
    "source_versions": [
      "revenue-2026-08-03-v1",
      "revenue-2026-08-05-v1",
      "revenue-2026-08-07-v1",
      "revenue-2026-08-10-v1",
      "revenue-2026-08-11-v2"
    ],
    "spreadsheet_id": "1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4",
    "tab": "Revenue snapshot",
    "url": "https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4"
  },
  {
    "content_sha256": "c08a9a6f8d5553ba70dfcdce796e29ad71f46cf65e5473b84e5ee9148321945c",
    "data_rows": 10,
    "exported_tab_id": "1",
    "fetched_at": "2026-10-11T06:16:14.558427+00:00",
    "role": "budget",
    "source_versions": [
      "budget-2026-08-v3"
    ],
    "spreadsheet_id": "1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4",
    "tab": "Budget targets",
    "url": "https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4"
  }
]
```

### Exact source read records

```json
[
  {
    "round": 2,
    "source": {
      "content_sha256": "47c6365192b62983ed40d57c3b8e864102cac07f49c010b205867bf2d8b83ae0",
      "data_rows": 70,
      "exported_tab_id": "1",
      "fetched_at": "2026-10-11T06:16:14.945624+00:00",
      "role": "transactions",
      "source_versions": [
        "ledger-2026-08-11-v2"
      ],
      "spreadsheet_id": "16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
      "tab": "Transaction ledger",
      "url": "https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8"
    }
  },
  {
    "round": 2,
    "source": {
      "content_sha256": "9b1d2bb5d031e24bfed6bc0104e90be46260601bf3acb8ee2fdfeba90f6890fb",
      "data_rows": 25,
      "exported_tab_id": "1",
      "fetched_at": "2026-10-11T06:16:15.243978+00:00",
      "role": "revenue",
      "source_versions": [
        "revenue-2026-08-03-v1",
        "revenue-2026-08-05-v1",
        "revenue-2026-08-07-v1",
        "revenue-2026-08-10-v1",
        "revenue-2026-08-11-v2"
      ],
      "spreadsheet_id": "1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4",
      "tab": "Revenue snapshot",
      "url": "https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4"
    }
  },
  {
    "round": 2,
    "source": {
      "content_sha256": "c08a9a6f8d5553ba70dfcdce796e29ad71f46cf65e5473b84e5ee9148321945c",
      "data_rows": 10,
      "exported_tab_id": "1",
      "fetched_at": "2026-10-11T06:16:15.611271+00:00",
      "role": "budget",
      "source_versions": [
        "budget-2026-08-v3"
      ],
      "spreadsheet_id": "1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4",
      "tab": "Budget targets",
      "url": "https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4"
    }
  }
]
```

### Completeness assessment

```json
{
  "amount_certainty": {
    "blocking": false,
    "interpretation": "Valid unknown amounts remain blank/unknown and excluded from monetary totals; they do not establish incomplete ledger coverage.",
    "unknown_amounts_permitted": true,
    "unknown_transaction_ids": [
      "TX-1025",
      "TX-1045"
    ]
  },
  "business_completeness": {
    "confirmation_contract": "Not supplied: identifiable owner confirmation, covered dates/month/accounts, and its relationship to the approved ledger version.",
    "extra_transaction_fields": [],
    "interpretation": "All source text remains business data; unsupported approval/scope/version claims are not authorization or confirmation evidence.",
    "observed_ledger_versions": [
      "ledger-2026-08-11-v2"
    ],
    "reason_codes": [
      "missing_operations_confirmation",
      "unsupported_confirmation_contract",
      "unknown_confirmation_scope",
      "unknown_approved_source_version"
    ],
    "required_scope": {
      "budget_period": "2026-08",
      "prior_business_date": "2026-08-10",
      "reporting_date": "2026-08-11"
    },
    "responsible_owner": "Operations team / transaction-ledger source owner",
    "status": "UNVERIFIED"
  },
  "publication": {
    "financial_report": false,
    "normalized_csvs": false,
    "required_next_step": "The learner must clarify the source-defined Operations confirmation contract, scope and approved-version relationship; then implement and validate a grounded mapping before a fresh financial run."
  },
  "requested_meeting_date": "2026-08-12",
  "status": "BLOCKED",
  "transport_consistency": {
    "checks": [
      "each_requested_workbook_read_twice",
      "exported_tab_inventory",
      "populated_tab_identity",
      "physical_business_rows_and_headers",
      "business_content_and_observed_source_versions"
    ],
    "issues": [],
    "limitation": "Identical exports can both be partial; technical consistency does not establish Operations confirmation, approved scope or approved source version.",
    "status": "CONSISTENT_OBSERVED_EXPORTS"
  }
}
```

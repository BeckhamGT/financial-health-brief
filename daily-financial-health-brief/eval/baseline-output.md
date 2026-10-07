# Expected financial results and acceptance criteria

Synthetic signed USD totals: reporting posted +150.15; pending-confirmed +20.20;
disputed-confirmed +10.10; prior posted +100.00; posted change +50.15. Supplies
posted MTD +275.40 against +600.00 monthly allocation; variance -324.60. Collected revenue
snapshot change +500.00 and outstanding balance change -100.00, with no flow/cumulative assertion. Preserve 10/1/7 rows
and every business note; retain blank unknown and signed credits. Reordered input
must produce identical CSV bytes and figures.

Materiality must reject equality at USD 500 or 10%, in both signs, and accept only
when both thresholds are strictly exceeded. Review all pending/disputed synthetic
items for operations. Retain unknown and collected-revenue-definition items for
clarification. All failed runs after a successful run remove required CSVs and
replace the report with STALE / FAILED. Sources remain read-only. No cached input,
manual transcript rewrite, source-system edit or financial decision is permitted.

The meeting date is 2026-08-12. Baseline current-month queue: 3 rows (2 pending,
1 disputed), including 1 unknown; 9 current-month rows = 6 confirmed posted + 3
unresolved. There are no other-period unresolved rows in the baseline. The
cross-date variant adds earlier posted unknown, later pending and July disputed
rows to verify the current-month union and separate other-period table.

# Canonical test input

Use `fixture_tabs()` in `scripts/test_brief.py` through the test harness only.
It includes 10 transaction rows (both selected dates, earlier MTD, future and July
activity, two credits, one unknown), one monthly supplies budget owned by operations
with review_all_pending_or_disputed, three dated revenue snapshots, and an extra
business_note column. Names deliberately mislabel source roles. Also run the
reordered-column/URL/row variant. Fixtures never enter the production command.

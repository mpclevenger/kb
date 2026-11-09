---
title: Can you trust the report?
section: build
order: 12
---
Many controls start from a report or data extract: a user list, a list of changes, a list of job runs. If the report is wrong or incomplete, the control is too, however carefully people review it. Before you rely on a report, be able to show that it is complete (nothing left out) and accurate (the values are right).

## Where the report comes from

- Write down the source system, the table or feed, and who owns it.
- Save the query or report definition, and every filter and parameter, such as date range or status.
- Note any exclusion, such as service accounts or test records, and why. Decide this before the control runs, not after.
- Make sure the report is produced by a system. A list typed or edited by hand is not a report you can rely on.

## Showing nothing was left out

Compare the report to something independent, and keep the comparison.

- **Counts.** The number of rows equals the number in the source for the same date and filters, taken a different way from the report itself, such as the system's own screen or a separate query.
- **Totals.** Key amounts add up to the source or to another system.
- **Gaps.** Run a second check where gaps are possible, such as missing dates, missing ID numbers or a feed that stopped.
- **Timing.** Record the date and time the report was run, and the period it covers.

## Showing the values are right

- Spot-check a few rows against the source record.
- Confirm that fields are read the way you think, such as dates, time zones and status codes.
- Confirm that the report logic does what the description says, ideally by running it a second way.
- Re-check after any change to the source system or the report.

## Changes to the report

A changed query can quietly change what the control sees.

- Put the query or report definition under version control, or save a dated copy.
- Treat a change to it like any other change: request, review by someone other than the author, then release.
- Limit who can edit it.
- After a change, repeat the completeness and accuracy checks.

If you're building a new report or making a bigger change, such as a new data source or platform, see [Building or changing a report used in controls](/guides/building-or-changing-a-report-used-in-controls/).

For a report that hasn't changed, a full check when it is set up and after every change, plus the run details and counts from each run, is usually enough. A query written or edited for one run needs the full check that time.

## What to keep from each run

- The report itself, as exported, unedited.
- The date, time and period covered.
- The query or settings used.
- The completeness comparison and its result.
- Notes on any difference, with how it was resolved.

If you're unsure, Tech Risk can help.

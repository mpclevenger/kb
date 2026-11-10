---
title: Reports used in controls
section: build
order: 12
---
Many controls start from a report or data extract: a user list, a list of changes, a list of job runs. If the report is wrong or incomplete, the control is too, however carefully people review it. This guide is for the team that builds and maintains a report a control relies on: how to build it so it can be trusted, keep it that way through changes, and evidence each run.

## What can go wrong

| Risk | How it tends to happen |
|---|---|
| Data is missing or wrong | A join, filter or load drops rows, or a source isn't refreshed. |
| Logic changes without review | Someone edits the report directly in the tool, outside change control. |
| Access controls are bypassed | The report runs with its publisher's permissions, so viewers see data they aren't entitled to. |
| Data leaves the controlled environment | Exports, downloads, email subscriptions or snapshots copy it elsewhere. |
| A failure goes unnoticed | A refresh fails, the report shows old data, and nobody is alerted. |

## Key report inventory

Keep an inventory of the key reports your team builds and maintains. For each report, record:

- The report name, where it lives and the controls that rely on it.
- Whether it supports Sarbanes-Oxley (SOX) controls, so SOX reports get tighter change and access controls than general-purpose reporting.
- The source system and the table or feed.
- The person on your team who maintains it.
- The business owner, who requests changes and signs off user acceptance testing (UAT).
- Where the version-controlled logic is kept.
- The date of the last completeness and accuracy check.

## Building it so it can be trusted

- Keep the logic in one governed place. Put calculations and filters in reviewed, version-controlled definitions, such as database views, rather than inside the dashboard or spreadsheet. A visual layer that only displays the result is easier to trust and to test.
- The pipelines that feed the report check row counts, control totals and freshness, and alert or stop when a check fails.
- Lineage from source to report shows what a change upstream could affect.
- The report is produced by a system. A list typed or edited by hand is not a report a control can rely on.

## Proving it before you switch over

When a report replaces an old one, or moves to a new platform, run old and new side by side before anyone relies on the new one.

- Compare the outputs for the same period: counts, totals and a sample of records.
- Explain every difference, and fix it or record why it's expected.
- Get sign-off from the business owner before the switch, and keep the comparison as evidence.

The [Initiative lifecycle](/guides/initiative-lifecycle/) asks for this as part of the migration approach and rehearsal.

## Showing it's complete and accurate

Compare the report to something independent, and keep the comparison.

- The number of rows equals the number in the source for the same date and filters, taken a different way from the report itself, such as the system's own screen or a separate query.
- Key amounts add up to the source or to another system.
- Where gaps are possible, such as missing dates, missing ID numbers or a feed that stopped, run a second check for them.
- Spot-check a few rows against the source record.
- Confirm that fields are read the way you think, such as dates, time zones and status codes.
- Confirm that the report logic does what its description says, ideally by running it a second way.

For a report that hasn't changed, a full check when it is set up and after every change, plus the run details and counts from each run, is usually enough. A query written or edited for one run needs the full check that time.

## Changes to the report

Your team creates and maintains the report and its data, so your team owns its change control. A changed query can quietly change what the control sees.

- Every change to the report's logic or source needs an approved change ticket. The ticket asks whether the change affects a report used in a key control, so the checks are repeated after release.
- Someone on your team other than the author reviews the change, and the pipeline deploys it, so nobody edits the live report by hand. See [CI/CD pipelines as change control](/guides/cicd-pipelines/).
- The business owner signs off UAT before release.
- Keep the logic under version control, or a dated copy where that isn't possible.
- Only your team can edit the report logic and the data behind it.
- If a fix has to go in directly, record it, have it reviewed and bring it into version control promptly.
- After a change, repeat the completeness and accuracy checks and update the inventory.

## Access, sharing and exports

- Where possible, the report runs with each viewer's own permissions, so existing data access rules still apply. If it has to run with a shared identity, use a dedicated service account with access to only the data the report needs, never a person's account.
- Limit who can view and share the report to the groups that need it.
- Turn off or limit downloads, exports, email subscriptions and snapshots for SOX reports, or know who receives them and why.
- Tools that write their own queries in response to questions are useful for exploration, but their results aren't repeatable or reviewed. Keep them out of SOX controls.
- Include report owners, editors, viewers and service accounts in the system's access review.

## Keeping it running

- A failed refresh raises an alert to a monitored place. For reports used in key controls, a ticket shows what happened and how it was fixed.
- Permission changes, sharing changes and direct edits are logged to the firm's logging platform, with alerts on the ones that matter for SOX reports.
- Because the logic is in version control, the report can be redeployed after a failure. Recovery expectations follow the system's BCP tier; see [Recommended timelines by BCP tier](/guides/recommended-timelines-by-bcp-tier/).

## Evidence from each run

- The source: the system, the table or feed, and its owner, captured from the system itself, such as the report's properties or connection details.
- The query or report definition as it was run, with its filtering logic and every parameter, such as date range or status, so the same result can be reproduced.
- The run history: the system date and time stamp, who or which job ran it, and the period it covers.
- The result exactly as exported, unedited.
- Each exclusion, such as service accounts or test records, and why. Agree exclusions before the control runs, not after.
- The completeness comparison and its result.
- Notes on any difference, with how it was resolved.

## Related controls

- Reports used in key controls are complete and accurate
- The change management controls, for how report changes are reviewed and released
- The access management controls, for who can view, edit and share reports

If you're unsure, Tech Risk can help.

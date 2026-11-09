---
title: Building or changing a report used in controls
section: build
order: 13
---
A control is only as good as the report behind it. Most report problems start when something changes: a new report, a new data source, a change to the logic, a move to a new platform, or a new reporting tool such as dashboards or natural-language query. This guide covers what to think through at those moments, so the report stays trustworthy afterwards. For the checks you keep each time a control uses the report, see [Can you trust the report?](/guides/can-you-trust-the-report/).

## What can go wrong

| Risk | How it tends to happen |
|---|---|
| Data is missing or wrong | A join, filter or load drops rows, or a source isn't refreshed. |
| Logic changes without review | Someone edits the report directly in the tool, outside change control. |
| Access controls are bypassed | The report runs with its publisher's permissions, so viewers see data they aren't entitled to. |
| Data leaves the controlled environment | Exports, downloads, email subscriptions or snapshots copy it elsewhere. |
| A failure goes unnoticed | A refresh fails, the report shows old data, and nobody is alerted. |

## Knowing which reports matter

Start with a list. Each report used in a key control should have:

- A name, a location and the control or controls that use it.
- A named owner, who answers for its accuracy and approves changes.
- A note of whether it supports Sarbanes-Oxley (SOX) controls, so SOX reports can be kept apart from general-purpose reporting and given tighter change and access controls.

Keeping the list current makes it clear which changes need extra care.

## Getting the data and logic right

- **Know the source.** Record the system, table or feed each report reads, and who owns it.
- **Keep the logic in one governed place.** Put calculations and filters in reviewed, version-controlled definitions, such as database views, rather than inside the dashboard or spreadsheet. A visual layer that only displays the result is easier to trust and to test.
- **Check the data on the way in.** Pipelines that feed the report check row counts, control totals and freshness, and either alert or stop when a check fails.
- **Be able to trace it.** Lineage from source to report shows what a change upstream could affect.

## Proving it before you switch over

When a report replaces an old one, or moves to a new platform, run old and new side by side before anyone relies on the new one.

- Compare the outputs for the same period: counts, totals and a sample of records.
- Explain every difference, and fix it or record why it's expected.
- Get a named sign-off from the report owner before the switch, and keep the comparison as evidence.

The [Initiative lifecycle](/guides/initiative-lifecycle/) asks for this as part of the migration approach and rehearsal.

## Changing it after go-live

- **Version control and review.** Report definitions live in source control. Changes go through a pull request reviewed by someone other than the author, and the pipeline deploys them, so nobody edits the live report by hand. Only the deployment process, or a small named group, can change the published version. See [CI/CD pipelines as change control](/guides/cicd-pipelines/).
- **Flag changes that touch a key report.** A simple question on the change request, such as "Does this affect a report used in a key control?", tells the owner to repeat the completeness and accuracy checks after release.
- **Review emergency fixes afterwards.** If a fix has to go in directly, record it and have it reviewed and brought into source control promptly.

## Who can see, share and export it

- **Whose permissions the report uses.** Where possible, the report runs with each viewer's own permissions, so existing data access rules still apply. If it has to run with a shared identity, use a dedicated service account with access to only the data the report needs, never a person's account.
- **Sharing.** Limit who can view and share the report to the groups that need it.
- **Copies.** Turn off or limit downloads, exports, email subscriptions and snapshots for SOX reports, or know who receives them and why.
- **Natural-language query tools.** Tools that write their own queries in response to questions are useful for exploration, but their results aren't repeatable or reviewed. Keep them out of SOX controls.
- **Access reviews.** Include report owners, editors, viewers and service accounts in the system's access review.

## Keeping it running

- **Failed refreshes raise an alert** to a monitored place. For reports used in key controls, a ticket shows what happened and how it was fixed.
- **Changes are logged.** Logs of permission changes, sharing changes and direct edits go to the firm's logging platform, with alerts on the ones that matter for SOX reports.
- **It can be rebuilt.** Because definitions are in source control, the report can be redeployed after a failure. Recovery expectations follow the system's BCP tier; see [Recommended timelines by BCP tier](/guides/recommended-timelines-by-bcp-tier/).

## Related controls

- Reports used in key controls are complete and accurate
- The change management controls, for how report changes are reviewed and released
- The access management controls, for who can view, edit and share reports

If you're unsure, Tech Risk can help.

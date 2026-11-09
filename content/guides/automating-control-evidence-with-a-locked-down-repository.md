---
title: Automating control evidence with a locked-down repository
section: build
order: 2
---
Evidence collected by hand can be incomplete, edited afterward or missed, so a control may appear to have run when it did not, or may fail without anyone noticing. A scheduled workflow in a locked-down repository reduces that risk, provided the automation itself cannot be altered or misused by the people whose work it checks.

## What can go wrong?

- **Incomplete evidence:** a screenshot or partial export does not show that the whole population was checked.
- **Altered evidence:** files edited, replaced or deleted after the fact, so the record cannot be relied on.
- **Self-review:** the people being checked change the automation or approve their own results.
- **Over-privileged automation:** a workflow with broad credentials can read or change the very systems it reports on.
- **Silent gaps:** a scheduled run fails and nobody notices, so a period has no evidence.

## How does the automation work?

- A scheduled workflow runs at the control's frequency.
- It pulls data from the system using a read-only account.
- It saves the raw output and the details of the run to the evidence repository.
- It runs checks, for example that the record count matches the source.
- It opens a pull request or issue for the reviewer, who records a decision on each item and approves. The approval is the sign-off, and exceptions become issues tracked to closure.

## How is the repository protected?

- One private repository per control area, used only for evidence and the automation that produces it.
- Access for a small named team. People whose work is checked can't change the repository or its evidence. Organization owners and site administrators still can, so changes to its settings and access are sent to Splunk through the audit log and looked at in the periodic review.
- The default branch has the full set of protections described in [Repository management](/guides/repository-management/), including no administrator bypass.
- History is never rewritten or deleted. Each period is tagged, for example 2026-Q4, and a tag ruleset (in recent versions; check yours) stops tags being moved or deleted.

## How is the automation protected?

- Read-only, least-privilege credentials for each source system. For cloud sources this means short-lived tokens; for on-premises sources, a managed service account on a dedicated runner or a vaulted credential that only the evidence job can read.
- Secrets held in an environment that only the evidence job can use, and a dedicated runner group. Workflow and runner security is in [GitHub Actions runners](/guides/github-actions-runners/).
- Changes to the workflow go through review and change management, because the workflow is part of the control. Any change mid-period is recorded with what changed and when, so both versions can be understood.

## What should every run save?

| Item | Risk it addresses |
|---|---|
| The raw export, unedited | Evidence that was reshaped before it was kept |
| The query or script version (commit SHA) | Uncertainty about how the data was pulled |
| Run date and time | Uncertainty about when it was pulled |
| Source system name | Uncertainty about where it came from |
| Record count and the source's own count | Incomplete population |
| A SHA-256 checksum of each file, also written to the workflow run log | Changes made after the run |
| The workflow run ID | Evidence that cannot be tied to a run log |

## How can you show the automation works?

- A one-time reconciliation against a manual pull when the automation was set up, with the comparison kept.
- An alert, and a record of its follow-up, when a scheduled run fails or does not run.
- The repository's access list and rules, included in the periodic access review.
- A short design note in the repository: what it pulls, from where, how often and how the review works.
- Evidence kept past Actions artifact expiry, by committing it or moving it to the evidence store, for the period in the firm's [records retention schedule](#todo-records-retention-schedule).

## When is manual evidence a better fit?

- One-off checks.
- Systems with no API or export.
- Controls whose automation has not yet been reconciled against a manual pull.

If you're unsure, Tech Risk can help.

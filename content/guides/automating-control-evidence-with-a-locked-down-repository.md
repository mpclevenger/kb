---
title: Automating control evidence with a well-controlled repository
section: build
order: 2
---
Automating evidence collection makes a control more reliable and cheaper to run: every run captures the complete population on time, in the same format, with a tamper-evident record. That holds only if the people whose work the control checks cannot change the automation or its evidence. The sections below describe best practice, with the evidence to keep for each, most important first.

## Is it a good fit?

Automation suits controls that run on a schedule and pull from a system with an API, export or query that can run under a read-only account. Manual evidence remains the better choice for one-off checks and for systems with no export.

## The repository

| What's in place | Evidence to keep |
| --- | --- |
| Access is limited to a small named team, and the people whose work is checked cannot change the repository or its evidence | The access list, included in the system's access review |
| The default branch has the protections in [Repository management](/guides/repository-management/), with no administrator bypass | An export of the branch rules |
| History is never rewritten or deleted | Branch rules showing force pushes and deletion are blocked |
| Changes to settings and access by organization owners or site administrators are logged to Splunk | The alerts and their review |
| It's recommended that each control automation has its own repository, used only for evidence | The repository list |

## The workflow

| What's in place | Evidence to keep |
| --- | --- |
| Workflow changes go through change management, and the developer cannot approve or deploy their own change | The approval rules, and a sample change showing a different developer and approver |
| Source systems are read with read-only, least-privilege credentials | The account permissions for each source |
| Secrets are available only to the evidence job | The environment settings showing which jobs can use them |
| It's recommended that cloud sources use short-lived tokens; on-premises sources use a managed service account or a vaulted credential | The credential configuration |
| It's recommended that evidence jobs run on a dedicated runner group (see [GitHub Actions runners](/guides/github-actions-runners/)) | The runner group settings |

## Audit trail for each run

| What each run saves | Risk it addresses |
| --- | --- |
| The raw export, unedited | Evidence reshaped before it was kept |
| The query or script version (commit SHA) | Unclear how the data was pulled |
| Run date, time and source system | Unclear when or where it came from |
| Record count and the source's own count | Incomplete population |
| A SHA-256 checksum of each file, also in the run log | Changes made after the run |
| The workflow run ID | Evidence not tied to a run |

## Before go-live

Collect this once, before the automation replaces the manual process:

- A reconciliation of the automated output against a manual pull for the same period.
- A test of the alert for a failed or missed run.
- A write-up of how the automation works, kept in the repository and referred to each period instead of explaining the process again. It covers the schedule, the source and account, what each run saves, the checks it performs, how the reviewer signs off and handles exceptions, and the date of each change.

## While it runs

- Each failed or missed run, with its follow-up.
- Each period's evidence, moved out of Actions artifacts before they expire and kept for the period in the firm's records retention schedule.

If you're unsure, Tech Risk can help.

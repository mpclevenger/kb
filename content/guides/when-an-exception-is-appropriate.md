---
title: When an exception is appropriate
section: build
order: 1
---
Sometimes a control can't run exactly as designed. On this page, an exception is a planned, approved departure from how a control normally runs. It is different from items a control flags, such as an unmatched change, and from a test exception, which is what auditors call a sample that didn't meet the control.

## Exception criteria

An exception is appropriate only when all of the following conditions are met:

- The control cannot reasonably operate as designed. Saving time or effort is not a sufficient reason.
- The reason, the risk in the meantime, and the plan and date to restore the control are recorded and approved before the exception begins.
- A named owner is accountable for the exception and its closure, and the person who accepted the risk is recorded.
- A compensating control addresses the risk for the duration of the exception, and the evidence it produces is retained.
- The exception has a defined end date and is not extended repeatedly. Before that date, the owner confirms it is still needed and records the decision.

## Compensating controls

A compensating control runs on a fixed schedule, is evidenced each time, is performed by someone independent of the activity, and is precise enough to detect what the original control would have detected. Examples:

- **Peer review isn't enforced in the repository.** A weekly report of every merge to the production branch is reviewed and signed off by someone outside the team.
- **A shared administrator account can't be removed yet.** Its password is held in the vault with each check-out logged, and every use is matched to a ticket each week.
- **The change approval tool is unavailable during a migration.** The named approver approves each change by email before release, and approvals are matched to the deployment log at month end.

## Risk treatment

An approved exception is a decision to knowingly accept a risk for a limited time. It does not fix the control, and it does not change how the control is assessed.

### What acceptance means

- The control is still not operating as designed. For a key control, an approved exception doesn't make the control effective, and testers will still report the gap.
- Without a compensating control in place, the risk is fully open for as long as the exception lasts.
- A compensating control reduces the risk only if it is designed, performed and evidenced like a control in its own right. Even then, it is assessed on its own and does not make the original control effective.
- Acceptance must be formally evidenced: the review performed, the rationale for approval, and the approver's name with the date and time of approval, recorded through the firm's exception process. Without this record, the condition is not an approved exception.

### Who accepts it

- The business or system owner accepts the risk, at the appropriate level of seniority, and at a minimum the L3.

If you're unsure, Tech Risk can help.

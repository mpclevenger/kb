---
title: Writing a runbook
section: run
order: 2
---
A runbook is the step-by-step guide for an operational task: restarting a service, restoring a backup, rotating a credential, rerunning a failed job. Good runbooks reduce the risk of mistakes under pressure and let someone other than the usual expert act quickly and safely.

## When a runbook helps

- The task is done rarely, so nobody remembers the steps, such as a restore or a failover.
- The task is done under pressure, such as during an incident or an outage.
- A mistake would be costly, such as anything touching production data or access.
- A control depends on the task being done the same way every time.

## What a good runbook contains

- **Purpose:** what the task achieves and when to use this runbook.
- **Before you start:** the access needed, the tools, any approval or change record, and how to confirm it is safe to begin.
- **Steps:** numbered, one action per step, with the exact command or screen and what you should see when it works.
- **Checks:** how to confirm the task succeeded.
- **If it goes wrong:** how to stop safely, how to roll back, and who to contact.
- **Evidence:** what to save if the task is part of a control, such as a job log or a ticket update.

## Making it reliable

- Write it for a capable colleague who has never done the task.
- Test it by having someone else follow it exactly, and fix anything they had to guess.
- Keep commands and settings copyable, and mark any value that changes per environment.
- Use the same access path the runbook describes. A runbook that relies on someone's personal admin rights fails when they are away.

## Keeping it current

- Store runbooks where the team can find them during an outage, not only on one person's machine.
- Give each runbook an owner and a review date, and review it after every real use.
- Update it whenever the system, tool or access path changes.
- Link it from the control procedure or the system's documentation, so people can find it from either side.

If you're unsure, Tech Risk can help.

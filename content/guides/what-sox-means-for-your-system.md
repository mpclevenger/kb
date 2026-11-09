---
title: What SOX means for your system
section: audit_prep
order: 1
---
SOX (the Sarbanes-Oxley Act) requires the firm to show that the numbers it reports can be trusted. If your system feeds those numbers, auditors will test the controls around it. This page tells you whether that is you, and what to expect.

## Is your system in scope?

Your system is likely in scope if either of these is true. The firm's in-scope application list is the definitive answer.

- **It supports financial reporting directly.** It creates, changes, calculates or reports data that ends up in the financial statements, or that a financial control relies on.
- **It sits underneath something that does.** Databases, servers, scheduled jobs, identity services, pipelines and cloud accounts count when they could change the data, the application's code or settings, or the evidence for a control.

If your system is new or has changed what it does, let the list's owner know so it can be reviewed. When in doubt, it's safer to ask than to assume it's out of scope.

## The four areas testers look at

| Area | In plain words | Read |
|---|---|---|
| Access | Who can get in, and whether that is still right | Access management topic |
| Change | How changes reach production, and who approved them | Change management topic; "CI/CD pipelines as change control" |
| Operations | Whether scheduled jobs run and failures get fixed, and whether backups run | Platforms and infrastructure topic (job scheduling); IT disaster recovery topic (backups) |
| Building and moving in | How new systems are built, tested and brought into production | "Initiative lifecycle"; Change management topic |

If a control relies on a report or an extract, also read "Can you trust the report?". If a vendor runs part of your system, read "Reading a vendor's SOC report".

## What "key" and "period of reliance" mean for you

- **Key control.** A control the firm has chosen to rely on to address a risk to its financial reporting. Key controls are the ones testers test, so they need to run exactly as written, every time, with evidence. In TRAC these carry the level Key; other controls are Non-key, Compensating or Supporting.
- **Period of reliance.** The part of the year the firm relies on the control, usually the whole financial year. Testers sample from across it, so the control has to run every time. A new or fixed control has to run for a while before testers can rely on it (for example, at least two runs of a quarterly control before year-end), so changes late in the year need planning.
- **If you change a control during the period,** record what changed and when. Testers may check both versions.

## What testers will ask for

- **A population.** The complete list the control works on, such as every user, every production change, every job run or every backup, for the period.
- **A sample.** Testers pick items from that list and ask for the evidence for each one. More frequent controls get bigger samples.
- **Proof the list is complete.** See "Can you trust the report?".
- **If a sample fails.** Testers record a test exception, and the firm decides how serious it is (whether it is a deficiency). Fixing the evidence afterward doesn't help. What helps is finding the cause, fixing the control, and letting it run long enough to be tested again.

Evidence can't be rebuilt after the fact, so it pays to save it for every run, with the date visible, in the shared evidence location.

## Where to start

- A good first step is to check whether your system is on the in-scope application list, and which key controls apply to it.
- It helps to name who performs and who reviews each control, with a backup for each.
- Good next reads: "Working with auditors: what trips teams up" and "Before your control review: be ready to answer".

If you're unsure, Tech Risk can help.

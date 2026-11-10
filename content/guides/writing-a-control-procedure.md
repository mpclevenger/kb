---
title: Writing a control procedure
section: build
order: 3
---
A control procedure records what your team actually does to run a control, so a backup can run it the same way and a reviewer can test it. TRAC's control pages describe recommended practice; your procedure is what reviewers check against. A good one is short, starts from the risk, and is organized by what the control needs to achieve.

## Start from the risk and the objective

- Open with the risk in one or two sentences: what could happen, to which systems or data, and why it matters.
- State the control objective: the outcome the control is designed to achieve. For example, "Only approved changes reach production."
- If the control has several parts, give each part its own objective and organize the procedure around them. A user access review might have three: the list is complete, every account is checked by the right person, and removals are completed.

## What each objective covers

Use the same headings for every objective, so a reader always knows where to look.

| Heading | What it covers |
| --- | --- |
| Scope | The systems, environments and populations covered, and anything left out, with the reason |
| Roles | Who performs and who reviews the control, and the backup for each, named by role |
| Frequency | How often it runs, or the event that triggers it |
| Steps | Numbered steps someone else could follow, including where the population comes from and how its completeness is confirmed |
| Review criteria | What the reviewer checks, and what counts as an exception |
| Exceptions | Who decides the outcome of each exception, and how it is recorded |
| Evidence | What is kept from each run, with the date visible, and where it is saved |

## Keeping it usable

- Name an owner, review it at least yearly and whenever the control, system or team changes, and keep a short change history.
- Keep it to one or two pages in plain words, and link to runbooks for technical detail.
- Include only what the team does every time, because every statement can be tested.
- If the procedure and practice differ, fix whichever is wrong straight away and note the date. Reviewers look at both.

If you're unsure, Tech Risk can help.

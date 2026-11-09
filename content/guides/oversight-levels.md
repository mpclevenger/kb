---
title: Oversight levels
section: build
order: 9
---
Every initiative gets an oversight level of Enhanced, Standard or Light when Tech Risk accepts it. The level sets what is needed to move from one stage to the next.

The stages, exit gates and evidence are in the [Initiative lifecycle](/guides/initiative-lifecycle/) guide.

```mermaid
flowchart TD
  accTitle: How the oversight level is set
  accDescr: The owner's intake answers decide the level. A tier 0 or tier 1 app or a SOX in-scope app plus another yes, or three or more yes answers, gives Enhanced. One or two yes answers give Standard. No yes answers give Light. The level then sets what is needed at each stage exit.
  Q[Intake answers] --> D{How many yes answers?}
  D -->|Tier 0 or 1 or SOX app, plus another yes, or 3 or more yes| E[Enhanced]
  D -->|1 or 2 yes| S[Standard]
  D -->|None| L[Light]
  E --> NE[Approver sign-off at most stage exits]
  S --> NS[Mix of sign-off and Tech Risk review]
  L --> NL[Mostly owner confirms]
  NE --> G[Go-live and close always need approver sign-off]
  NS --> G
  NL --> G
```

## How the level is set

The owner answers these questions at intake. The level comes from the answers. Tech Risk confirms it, or changes it and records why, and checks it again at each stage exit.

- Is a BCP tier 0 or tier 1 app affected?
- Is a SOX in-scope app affected?
- Are key controls new, retired or redesigned?
- Is financial or regulated data migrated?
- Does it change how access is set up or reviewed?
- Does it move to a vendor or cloud platform?

## Which level

- Enhanced: a BCP tier 0 or tier 1 app or a SOX in-scope app is affected and at least one other answer is yes, or three or more answers are yes.
- Standard: one or two answers are yes.
- Light: no answers are yes.

## What is needed to move on

| Stage exit | Enhanced | Standard | Light |
|---|---|---|---|
| 1 Mobilize and design | Approver sign-off | Approver sign-off | Tech Risk review |
| 2 Build and configure | Approver sign-off | Tech Risk review | Owner confirms |
| 3 Test and validate | Approver sign-off | Tech Risk review | Owner confirms |
| 4 Cutover and go-live | Approver sign-off | Approver sign-off | Approver sign-off |
| 5 Hypercare and stabilize | Approver sign-off | Tech Risk review | Owner confirms |
| 6 Close | Approver sign-off | Approver sign-off | Approver sign-off |

Go-live and close always need approver sign-off.

## What each requirement means

- **Approver sign-off:** The program submits evidence for each checklist item, Tech Risk accepts it, and a named approver's decision is recorded: proceed, proceed with conditions, or hold.
- **Tech Risk review:** The program submits evidence and Tech Risk accepts it. No sign-off decision is needed.
- **Owner confirms:** The owner confirms each item is done.

A checklist item that doesn't apply is marked N/A, with the reason.

If you're unsure, Tech Risk can help.

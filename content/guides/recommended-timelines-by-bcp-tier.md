---
title: Recommended timelines by BCP tier
section: best_practice
order: 10
---
How quickly to fix, respond and test, based on the system's BCP tier. Tier 0 and tier 1 systems are the most critical and share the same timelines. Each timeline limits how long a weakness stays open, a problem goes unnoticed or data stays unrecoverable, and the tighter timelines apply where an outage or loss would do the most harm. All timelines on this page are recommendations and will be aligned with the firm's IT disaster recovery program.

## Fixing vulnerabilities

Risk limited: attackers exploit a known weakness in a system or its data while it is still unpatched. The more severe the weakness and the more critical the system, the shorter the window.

| Severity | Tier 0 and tier 1 | All other tiers |
|---|---|---|
| Known to be actively exploited | 7 days | 15 days |
| Critical | 15 days | 30 days |
| High | 30 days | 60 days |
| Medium | 90 days | 120 days |
| Low | 180 days | 180 days |

- Count from the day the vulnerability is first detected.
- If a fix can't be in place by the due date, record an exception before it is due.

## Logging and alerting

Risk limited: an attack, misuse or failure goes unnoticed because logs stopped arriving or alerts sat unreviewed, so damage grows and evidence may be lost.

| What | Tier 0 and tier 1 | All other tiers |
|---|---|---|
| Notice that a log feed has stopped | Within 1 hour | Within 24 hours |
| Triage a critical alert | Within 1 hour, any time of day | Within 4 business hours |
| Triage any other alert | Within 1 business day | Within 3 business days |
| Resolve and close an alert, with notes | Within 5 business days | Within 10 business days |

- Keep logs for as long as the firm's records retention schedule requires.

## Backups and recovery

Risk limited: data cannot be restored, or is restored too slowly or too far out of date, after a failure, error or attack, so the system stays unavailable and recent work is lost.

| What | Tier 0 and tier 1 | All other tiers |
|---|---|---|
| Back up | At least daily | At least weekly |
| Act on a failed backup | Same day | Next business day |
| Run a disaster recovery exercise | Every year | Every two years, where a plan exists |

- Recovery time and data loss targets (RTO and RPO) come with the system's BCP tier.
- Back up often enough to meet the data loss target, even if that is more often than shown here.

## Access

Risk limited: access stays open or grows beyond what a job needs because removals, changes and reviews are slow, so former staff or the wrong people can still use it.

| What | Tier 0 and tier 1 | All other tiers |
|---|---|---|
| Adjust a mover's access | Within 5 business days of the move date | Within 30 days of the move date |
| Complete a periodic access review, once it starts | Within 30 days | Within 45 days |
| Complete the removals a review finds | Within 10 business days of the decision | Within 30 days of the decision |
| Review privileged access | Every month | Every quarter |

- Count from the date HR records, not the date someone notices.
- Ordinary access is reviewed every quarter, as set out in the periodic access review control.

If you're unsure, Tech Risk can help.

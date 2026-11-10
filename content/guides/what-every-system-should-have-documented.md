---
title: What every system should have documented
section: best_practice
order: 5
---
Without current documentation, a system depends on what a few people remember. During an outage, a handover or a departure, teams can then misconfigure it, miss an unauthorized connection or recover it slowly, and a reviewer cannot confirm that controls cover the whole system. Every system that supports financial reporting or is BCP tier 0 or tier 1 should have all of the documents below, kept where the team works and easy to find from the team's own system page.

## What risk does each document address?

- **System overview:** unclear ownership and criticality, so nobody is accountable and the wrong controls apply.
- **Architecture diagram:** unknown components and exposed ports that no one is securing or patching.
- **Data flow diagram:** data sent to unintended places, or over unauthenticated or unencrypted connections.
- **Access model:** excess privilege, orphaned accounts and service account credentials that are never rotated.
- **Runbooks:** slow or incorrect response to failures and restores.
- **Change and release process:** unapproved changes reaching production.
- **Jobs and interfaces list:** failed or partial jobs and feeds that go unnoticed.
- **Logging and alerting summary:** gaps in what is recorded, or alerts that nobody answers.
- **Contacts and escalation:** delay in reaching the right person during an incident.

## Minimum documentation

| Document | Minimum content |
|---|---|
| System overview | What it does, who owns it, its BCP tier and whether it supports financial reporting. |
| Architecture diagram | Components, where each runs (application, database, server, cloud), the environment (production, test), and what it depends on, with the ports and protocols each component exposes. |
| Data flow diagram | For every flow: source and destination, direction, connection type (API, database connection, file transfer, message queue), protocol and port, how it authenticates (service account, certificate, token), whether it is encrypted in transit and how (for example, the TLS version), and how often it runs. |
| Access model | How users sign in (single sign-on (SSO), local accounts, keys) and whether multi-factor authentication (MFA) is enforced; roles and what they can do; which roles are privileged; how access is granted and removed; and every service account with its owner, what it connects to and how its credentials are stored and rotated. |
| Runbooks | Health checks, common failures and fixes, backup and restore, and failover steps. |
| Change and release process | How code and configuration reach production, and who approves. |
| Jobs and interfaces list | Every scheduled job and data feed: schedule, owner, where it runs, what it connects to (connection type, protocol and port), the account it runs as, and what happens when it fails. |
| Logging and alerting summary | What is logged, how logs are sent (agent, API, database connection; protocol and port), where they go, which alerts exist and who responds. |
| Contacts and escalation | Who to contact for the system, its platform and its vendors, during and outside working hours. |

## Recommended additions

| Document | Recommended |
|---|---|
| System overview | Key users and the business processes it supports. |
| Architecture diagram | Network zones, firewall rules between them and trust boundaries; a version kept in the repository alongside infrastructure code. |
| Data flow diagram | Data classification on each flow and the approval for any flow leaving the firm. |
| Access model | How the model maps to the periodic access review population. |
| Runbooks | Recovery time measured in the last restore or failover test. |
| Change and release process | Emergency change steps and how direct database or console changes are prevented or reviewed. |
| Jobs and interfaces list | Expected run times and record counts, so failures and partial runs are easy to spot. |
| Logging and alerting summary | Retention periods and how you would know logging had stopped. |
| Contacts and escalation | Backup contacts for every role. |

## How can you show it stays current?

- Every document is reviewed at least once a year and after any major change.
- Each document carries the date and name of its last reviewer.
- Store documents where the team works, such as the repository or team wiki, and link them from the team's system page.
- Evidence a reviewer would expect: the documents themselves, with a review date and reviewer, and a record that they were updated after the last major change.

If you're unsure, Tech Risk can help.

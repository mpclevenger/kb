---
title: Repository management
section: best_practice
platform: GitHub Enterprise Server
order: 7
---
A repository in the GitHub Enterprise Server (GHES) environment holds code and often more, such as configuration, secrets or data extracts. If nobody owns it, access drifts, or its default branch is unprotected, someone could change code that reaches production without review, or read data they should not see. For systems that support financial reporting, the impact includes unauthorized changes to production and no reliable record of who approved what.

This guide is the home for repository protections. Other guides link here instead of repeating them.

## What are the main risks?

- **No clear owner:** access is never reviewed and stale repositories keep their permissions.
- **Excess access:** broad or individual grants, outside collaborators and admin rights give people more than their role needs.
- **Unreviewed changes:** a direct push to a protected line of code bypasses approval and testing.
- **Exposed secrets:** credentials committed to a repository can be read by anyone with access, and remain in history.

## Who owns each repository, and who can do what?

- Every repository has a named owning team, recorded as a repository custom property (in recent versions; check yours). Repositories that support financial reporting are tagged the same way, so rules and reviews can target them.
- Code lives in organizations, not personal accounts, so organization policies apply.
- Access is granted through teams, not individuals, and the organization's base permission is none or read.
- Repository admin rights are limited, because admins can change repository-level rules. Outside collaborators are removed when their work ends.
- Unused repositories are archived, and stale ones are reviewed on the schedule in your team's written procedure.

## How are branches protected?

- Organization-level rulesets (in recent versions; check yours) cover the default and release branches of in-scope repositories, including new ones, and repository admins can't change them. Where rulesets aren't available, branch protection rules are set repository by repository. Changes to either are logged and reviewed.
- Every change goes through a pull request with at least one approval from someone other than the author. The most recent push is approved by someone other than the person who pushed it, and new commits dismiss earlier approvals.
- No bypass for in-scope repositories. Where bypass can't be removed, it is limited to a small named group, and every use is logged and reviewed.
- A code owners file (CODEOWNERS) names owners for sensitive paths such as workflow files and infrastructure code, and their review is required.
- Required checks, such as build, tests and scans, pass before merging. Force pushes and branch deletion are blocked.

## How are secrets and dependencies handled?

- Secret scanning and push protection are on for in-scope repositories (they need the GHES secret protection license). Where they aren't licensed, a scanner runs as a required check on every pull request.
- Dependency alerts are reviewed and acted on.
- If a secret is committed, it is rotated first and the history is cleaned afterward.

## How can you show it?

A dated export of in-scope repositories with owner and archive status, plus their ruleset or branch protection settings and any bypass list. A sample merged pull request shows an approver other than the author and passing checks.

If you're unsure, Tech Risk can help.

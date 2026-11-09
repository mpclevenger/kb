---
title: GitHub Actions runners
section: best_practice
platform: GitHub Enterprise Server
order: 6
---
A runner (the machine that runs a GitHub Actions job) executes whatever a workflow tells it to, using whatever credentials and network access it holds. If a runner is shared, long-lived or reachable from untrusted code, an attacker or a mistaken workflow could reach production systems, steal credentials or change what is deployed. For systems that support financial reporting, the runner is part of the change path, so the impact includes unauthorized or untraceable changes to production.

This guide is the home for workflow and runner security. For branch rules, approvals and code owners, see [Repository management](/guides/repository-management/).

## What are the main risks?

- **Leftover state:** a persistent runner can carry files, caches or credentials from one job into the next, including from a different repository.
- **Untrusted code on trusted runners:** code from a fork or an unreviewed branch runs on a runner that can deploy to production.
- **Stolen credentials:** long-lived keys stored as secrets can be copied from logs or workflow code and reused outside the pipeline.
- **Tampered or over-powered workflows:** a third-party action referenced by a movable tag can change without review, and a `GITHUB_TOKEN` with write access it does not need turns a small flaw into a large one.

## How should the runners be set up?

- Runners are ephemeral: each one takes a single job and is removed, so nothing carries over. Just-in-time registration is one way to do this (in recent versions; check yours).
- Runner groups limit which repositories and workflows can use each runner.
- Production deployment runners are separate from runners that build pull requests or other less trusted code.
- Runner hosts are patched and have network access limited to what builds and deployments need.
- An inventory records the owner, purpose and allowed repositories of each self-hosted runner.

## How are credentials protected?

- Where the cloud provider can reach the GHES environment, workflows use OpenID Connect (OIDC) to get short-lived cloud credentials instead of stored keys. The cloud trust policy checks the exact repository and, for production, the environment.
- Where OIDC isn't available, long-lived keys are held only in the production environment's secrets, with an owner and an expiry, and are rotated.
- Production environments require reviewers other than the person who triggered the deployment, and administrators can't bypass them. Deployment branches are limited to the default branch.
- The default `GITHUB_TOKEN` permission is read-only. A workflow asks for write access per job only where it needs it.

## What keeps workflows safe?

- Third-party actions are pinned to a full commit SHA, and an Actions policy allows only approved actions. Where your version can't enforce pinning in the policy, it is checked in code owner review.
- Workflows triggered by `pull_request_target` run with the base repository's secrets, so they do not check out or run code from the pull request.
- Workflows from fork pull requests need approval before they run.

## How can you show it?

A dated export of runner groups, the runner inventory and the Actions policy. The environment settings and a recent deployment record show the approver was a different person from the author.

If you're unsure, Tech Risk can help.

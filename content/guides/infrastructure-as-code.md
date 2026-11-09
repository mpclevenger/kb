---
title: Infrastructure as code
section: build
order: 14
---
Infrastructure as code means servers, networks and cloud settings are defined in files and applied by a tool, instead of being set up by hand. Terraform, CloudFormation and Bicep are examples. Done well, every change is written down, reviewed and repeatable. Done badly, the code says one thing and the environment does another, and nobody knows which to trust. This page covers the risks and the controls that help, whichever tool you use.

## What could go wrong

- **Changes made by hand.** A change in the console bypasses review, so nobody else sees it.
- **Unreviewed template changes.** Code is merged or deployed without a second person looking.
- **Drift.** What is running slowly stops matching the code, so the code no longer shows what was approved.
- **Too many rights.** The deployment identity can do far more than its deployments need, so a mistake or a stolen credential reaches much further than one change.
- **State files.** The tool's record of what it built can hold secrets, and it can be changed or lost, which can break or quietly alter the next deployment.
- **Secrets in code.** A password or key written into a file is copied into every clone and stays in the history.

## What helps

- Changes go through pull request review and the pipeline. See [CI/CD pipelines as change control](/guides/cicd-pipelines/) and [Repository management](/guides/repository-management/).
- The deployment identity has only the rights its deployments need, for only the environments it deploys to.
- Manual changes in production are limited to emergencies, and are reviewed afterwards. The code is then updated to match, or the change is reversed.
- Drift is detected, and each difference is followed up.
- State is stored securely, with limited access and versioning so an earlier copy can be recovered.
- Secrets are kept in a secrets manager and picked up at deployment, not written into code.

## How to show it

- A sample change from pull request to deployment: the request, the review by someone other than the author, and the pipeline run.
- The deployment identity's permissions.
- The last drift report, with what was done about each difference.

## Related controls

You may also be asked about "Servers are built to a documented baseline", "Configuration drift is monitored" and the change management controls.

If you're unsure, Tech Risk can help.

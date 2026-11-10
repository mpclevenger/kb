---
title: Databricks risks and controls by component
section: best_practice
platform: Databricks
order: 17
---
For each Databricks component, this guide covers what it does, what could go wrong, the controls that address it and how to show they work.

Databricks runs the service itself, and the system owner reviews its SOC report (see [Reading a vendor's SOC report](/guides/reading-a-vendors-soc-report/)). The rest is shared between two groups, so this guide has two parts:

- **The platform team**, the Databricks administrators, who set up and run the platform for everyone: the account, workspaces, identity, compute, network, audit logging and the storage underneath.
- **Teams that use Databricks**, who own their data, permissions, jobs, code and reports, and the controls over how they use the platform.

Changes reach production through the pipeline described in [CI/CD pipelines as change control](/guides/cicd-pipelines/), typically as Declarative Automation Bundles (formerly Databricks Asset Bundles).

## For the platform team

### Account, workspaces and identity

**What it does:** the account holds the identities and the list of workspaces. A workspace is where people and jobs do their work.

**What could go wrong:** someone with broad rights changes who can reach production, or a leaver or old token keeps access. This can happen when many people hold admin roles, production shares a workspace with development, users are created by hand, or tokens are long-lived. The result could be SOX data reached or production changed by someone who shouldn't.

**Controls that address it:**
- Account and workspace admins are few and named, and their access is reviewed on the schedule in the platform team's access review procedure.
- Each environment has its own workspace, and production has the tightest settings.
- Users and groups are provisioned from the firm's identity provider (for example, Microsoft Entra ID), so a leaver removed there is removed here.
- Automation signs in as service principals using OAuth. Personal access tokens are restricted or turned off, and long-lived ones are found and revoked.

**How to show it:** a dated export of admins, users and groups, and the token settings.

### Unity Catalog setup

**What it does:** the governance layer that controls who can use each catalog, schema and table, and how Databricks reaches the cloud storage underneath.

**What could go wrong:** data is reached around governance. This can happen when external locations or storage credentials are open to many, or environments share catalogs. The result could be SOX data read or changed outside its grants.

**Controls that address it:**
- Catalogs are separated by environment.
- Creating external locations and storage credentials sits with a small named group in the platform team.
- Ownership of catalogs is assigned to groups, not individuals.

**How to show it:** the list of catalogs with their owners, and the external locations and storage credentials with who can use them.

### Compute and network

**What it does:** the clusters, SQL warehouses and serverless compute that run code, and the connections between people, compute and the Databricks service.

**What could go wrong:** code runs in a way that sidesteps data permissions, or the workspace is reached from, or sends data to, places it shouldn't. This can happen when anyone can create any cluster, an access mode doesn't enforce Unity Catalog, or sign-in and outbound traffic are unrestricted. The result could be data read around its grants, or data leaving the environment.

**Controls that address it:**
- Cluster policies set what teams can create, and clusters used with governed data run in an access mode that enforces Unity Catalog permissions.
- Runtimes stay on supported versions.
- Sign-in is limited to approved networks, and outbound traffic is limited to approved destinations.

**How to show it:** the cluster policies, the access mode and runtime of running clusters, and the network settings.

### Audit logging

**What it does:** records who did what in the account and workspaces.

**What could go wrong:** a change to admin roles, grants or production goes unseen, or the record isn't there when needed. This can happen when audit events aren't forwarded, or nobody watches them. The result could be an unnoticed privilege change on SOX data, or no evidence of what happened.

**Controls that address it:**
- Audit events are kept for the period in the firm's [records retention schedule](#todo-records-retention-schedule) and sent to the firm's logging platform (for example, Splunk), where a stopped feed raises an alert.
- Alerts cover new admins, permission changes on SOX catalogs, and changes to cluster policies and production jobs, and are actively checked.

**How to show it:** the alert definitions and a recent alert with its follow-up.

### Storage and platform recovery

**What it does:** keeps the storage under the tables, and the platform's own setup, recoverable.

**What could go wrong:** storage is deleted or damaged, or a workspace can't be rebuilt after a failure. This can happen when storage versioning is off or the workspace setup exists only in the console. The result could be lost data across many teams, or a slow recovery.

**Controls that address it:**
- Versioning is turned on for the cloud storage under the tables (for example, AWS S3 versioning), and deleting it is restricted.
- Workspace configuration is kept as code, and a redeploy is tested.

**How to show it:** the storage versioning settings and the last redeploy test.

## For teams that use Databricks

### Data permissions

**What it does:** the grants that decide who can read or change your team's catalogs, schemas and tables.

**What could go wrong:** people read or change financial data they shouldn't. This can happen when grants go to individuals, or broad rights are handed out to save time. The result could be exposure or unauthorized change of SOX data.

**Controls that address it:**
- Grants go to groups, not individuals, and owners are groups or service principals.
- Broad rights, such as the right to manage permissions, are limited to a few named people.
- Access to SOX data is included in your system's access review.

**How to show it:** a dated export of grants on your SOX catalogs and schemas.

### Jobs, code and secrets

**What they do:** run your scheduled work, including pipelines that feed financial reports, using code in notebooks and Git folders and credentials held as secrets.

**What could go wrong:** a job or notebook is changed, runs as the wrong identity, fails unnoticed, or exposes a credential. This can happen when production is edited in the workspace, jobs run as the person who created them, or secrets sit in notebooks or job settings. The result could be unreviewed code in production, wrong data downstream, or access to source systems outside their controls.

**Controls that address it:**
- Production code and job definitions are in Git and deployed by the pipeline after a reviewed pull request, not edited in the workspace.
- Production jobs run as a service principal, not a person, and failure alerts go to a monitored place.
- Jobs get credentials from a secret store with only the access they need, and secrets aren't written in notebooks, job settings or Git.

**How to show it:** a sample change from pull request to deployment, the job's run-as identity and permissions, and who can read its secrets.

### Dashboards and Genie

**What they do:** AI/BI dashboards show query results to business users, and Genie answers plain-language questions about data.

**What could go wrong:** a dashboard used in a key control shows wrong data, or shows data to people who shouldn't see it. This can happen when the logic is edited in place, or every viewer sees what the publisher can see. The result could be a control relying on an unreviewed report, or SOX data reaching the wrong people.

**Controls that address it:**
- Report logic lives in reviewed Unity Catalog views, and dashboards used in key controls are deployed by the pipeline.
- Dashboards are published without embedded credentials, so each viewer's own permissions apply, and sharing is limited to the groups that need it.
- Genie isn't used to produce SOX evidence, because its queries aren't fixed or reviewed.

**How to show it:** the dashboard's definition in Git, its publish settings and permissions. See [Reports used in controls](/guides/can-you-trust-the-report/) for the full picture.

### Recovering your data

**What it does:** makes sure your team's important tables can be brought back after loss or damage.

**What could go wrong:** a table is deleted, damaged or overwritten and can't be restored. This can happen when teams rely on table history (time travel) as a backup, although routine cleanup permanently deletes old data files and history can be lost when a table is dropped. The result could be lost financial data, or a slow recovery.

**Controls that address it:**
- Your critical tables are known, and are backed up or replicated to match the system's recovery needs.
- A table restore is tested and the result recorded.

**How to show it:** the list of critical tables, the backup or replication setup, and the last restore test.

If you're unsure, Tech Risk can help.

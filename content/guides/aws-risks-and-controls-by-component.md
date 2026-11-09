---
title: AWS risks and controls by component
section: best_practice
platform: AWS
order: 15
---
For each AWS component, this guide covers what it does, what could go wrong, the controls that address it and how to show they work.

AWS runs the cloud itself: the data centers, the hardware and the services' underlying software, and the system owner reviews its SOC report (see [Reading a vendor's SOC report](/guides/reading-a-vendors-soc-report/)). The rest is shared between two groups, so this guide has two parts:

- **The platform team**, the cloud platform team, who set up and run AWS for everyone: the organization, accounts, identity and guardrails, the shared network and central logging.
- **Teams that use AWS**, who own their workloads, data stores, access within their accounts, backups and infrastructure-as-code changes.

If a database server runs on a virtual machine in AWS (for example, SQL Server on EC2), read this guide for the account and the virtual machine, and the SQL Server guide for the database itself. For the risks and controls that apply to any cloud, see [Infrastructure as code](/guides/infrastructure-as-code/).

## For the platform team

### Organization and accounts

**What it does:** AWS Organizations groups accounts under one management account. Each account is a boundary for access, cost and blast radius.

**What could go wrong:** a mistake or compromise in one account spreads to others, or someone removes the guardrails. The result could be unauthorized changes across several systems.

**Controls that address it:**
- Production, non-production and log archive are separate accounts. The management account is used only for organization tasks, with very few people able to sign in.
- Service control policies (SCPs) stop logging being turned off, accounts leaving the organization and use of unapproved regions.

**How to show it:** the organization structure, the SCPs attached and who can sign in to the management account.

### Identity and sign-in

**What it does:** decides how people sign in to AWS and who can administer it.

**What could go wrong:** credentials are stolen and used, or someone gets access they shouldn't have. This can happen when people have long-lived IAM users or the root user is used day to day. The result could be unauthorized changes to production or exposure of data.

**Controls that address it:**
- People sign in through IAM Identity Center, with permission sets assigned to groups from the corporate directory. IAM users aren't created for people.
- Member accounts have no root credentials. The management account's root user has phishing-resistant multi-factor authentication, no access keys and an alert on any use.

**How to show it:** an export of permission set assignments by account and group, and the IAM credential report.

### Central logging and detection

**What it does:** records what happens in the accounts and raises findings about suspicious activity.

**What could go wrong:** a change or attack goes unseen, or the evidence is altered or lost. This can happen when logging isn't on everywhere or nobody notices that delivery stopped. The result could be unauthorized activity that can't be investigated or proven.

**Controls that address it:**
- An organization CloudTrail trail covers all accounts and Regions, with log file validation, and delivers to a protected log archive account.
- AWS Config and GuardDuty are on in every account and Region in use, and a named team reads the findings.
- Logs and findings are forwarded to the firm's logging platform (for example, Splunk). Alerts fire when a trail is stopped or changed, or when delivery stops.

**How to show it:** the trail configuration, the log archive bucket policy and recent events in the logging platform.

### Shared network

**What it does:** the Virtual Private Cloud (VPC) is the private network around the workloads.

**What could go wrong:** a server or database is reachable from the internet or from systems that shouldn't reach it. The result could be an attacker reaching a database server directly.

**Controls that address it:**
- Workloads sit in private subnets.

**How to show it:** the subnet layout for the in-scope accounts.

## For teams that use AWS

### Access in your accounts

**What it does:** decides who can do what in your team's accounts.

**What could go wrong:** someone gets access they shouldn't have. This can happen when administrator rights are widely held or workloads use access keys. The result could be unauthorized changes to production or exposure of data.

**Controls that address it:**
- Administrator access is limited to named people and is time-limited or approved on request.
- Workloads use IAM roles, not access keys.
- Access in your accounts is included in your system's access review.

**How to show it:** the permission set assignments for your accounts. IAM Access Analyzer findings show external or unused access.

### Network rules for your workloads

**What it does:** security groups and network ACLs decide what traffic is allowed to your servers and databases.

**What could go wrong:** a server or database is reachable from systems that shouldn't reach it. This can happen when administrative ports are open to all addresses or rules added during troubleshooting are never removed. The result could be an attacker reaching a database server directly.

**Controls that address it:**
- Security groups name specific sources and ports. None allows all addresses to administrative or database ports.
- Administrators connect through Systems Manager Session Manager, which needs no open inbound port and records sessions.

**How to show it:** the security groups for your in-scope subnets, with no rule allowing all addresses to administrative or database ports.

### Compute

**What it does:** EC2 runs virtual servers, including SQL Server on EC2.

**What could go wrong:** a server is compromised through a missing patch or its metadata service, and the attacker takes its role credentials. The result could be loss of control of the server and the data on it.

**Controls that address it:**
- Instances launch only from approved images (AMIs), and IMDSv2 is required.
- Operating systems and database engines are patched within the timelines in the Recommended timelines by BCP tier guide, and compliance is reported for every instance.

**How to show it:** the approved AMI list and the patch compliance report.

### Data stores and keys

**What it does:** S3 holds objects and files. RDS and databases on EC2 hold structured data. AWS Key Management Service (KMS) controls the keys that encrypt them.

**What could go wrong:** data is exposed publicly, read by someone without a need, deleted or changed, or its keys are misused or deleted. This can happen when buckets or snapshots are shared publicly or key policies are broad. The result could be a data breach or loss of records.

**Controls that address it:**
- S3 Block Public Access is on at the account level. RDS instances and snapshots are private.
- Data stores are encrypted, with keys that have named owners.
- Key policies grant use only to the roles that need it, and an alert fires when a key is scheduled for deletion or its policy changes.

**How to show it:** the account-level Block Public Access setting, encryption settings and the key list with owners and policies.

### Backup and recovery

**What it does:** backups and snapshots let your team restore data and servers after loss, damage or deletion.

**What could go wrong:** a backup is missing, deleted along with the data, or can't be restored. This can happen when nobody has tried a restore. The result could be lost data or a long outage.

**Controls that address it:**
- Backups use AWS Backup or snapshots with a plan that matches the BCP tier, protected from deletion, with copies in another account or Region where the tier calls for it.
- Restores are tested to a separate environment, and the date and result are recorded.
- Recovery of a SOX database server hosted in AWS is part of the system's recovery plan.

**How to show it:** the backup plan and the latest restore test record.

### Infrastructure as code and change

**What it does:** your team's infrastructure is built and changed through code and a pipeline.

**What could go wrong:** infrastructure is changed outside the pipeline, without review. The result could be unreviewed changes in production.

**Controls that address it:**
- Console write access in production is limited to a break-glass role that is time-limited and logged. The pipeline role is the only other identity that writes to production.
- CloudFormation drift detection, a scheduled `terraform plan` that should show no changes, and AWS Config show changes made outside the pipeline.

**How to show it:** the break-glass role's logged use and the latest drift or plan result.

If you're unsure, Tech Risk can help.

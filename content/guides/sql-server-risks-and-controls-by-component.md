---
title: SQL Server risks and controls by component
section: best_practice
platform: SQL Server
order: 13
---
For each SQL Server component, this guide covers what it does, what could go wrong, the controls that address it and how to show they work.

SQL Server runs on Windows Server, on-premises or on a cloud virtual machine (for example, AWS EC2), or as a managed service (for example, Amazon RDS for SQL Server or Azure SQL). On a managed service the provider runs the operating system, patching and the backup service, and the system owner reviews the provider's SOC report (see [Reading a vendor's SOC report](/guides/reading-a-vendors-soc-report/)); the rest of this guide applies within the access the provider allows. The Database page in the Library, with SQL Server switched on, has the summary by risk area.

## The instance, its host and patching

**What it does:** the SQL Server service and the Windows Server it runs on, with the accounts and settings that decide what the engine can do.

**What could go wrong:** someone uses the engine's service account or built-in features to run commands on the server or reach other systems, or a known weakness in an out-of-date engine is used. This can happen when the service runs as a domain administrator, risky features are left on, or updates slip. The result could be control of the server and every database on it.

**Controls that address it:**
- The Database Engine and SQL Server Agent run as group managed service accounts where possible, or dedicated accounts with vaulted passwords. They aren't a domain administrator.
- Features that run operating system commands, such as `xp_cmdshell`, are off unless needed.
- Updates follow the schedule in your team's written procedure. Only supported versions run, and any past vendor support have an approved exception.

**How to show it:** a dated configuration export and the build inventory with support dates.

## Authentication

**What it does:** decides who can connect.

**What could go wrong:** someone connects as another person, or guesses a password, and changes data with no record of who they are. The result could be changes that can't be tied to a person.

**Controls that address it:**
- Windows authentication through directory groups is used where possible, so a disabled leaver can't start new sessions.
- SQL logins are the exception, each with an owner and purpose, with password rules applied.
- `sa` is disabled or renamed, and has a long vaulted password.

**How to show it:** the login list with type, owner and purpose.

## Roles and permissions

**What they do:** server roles decide who can administer the whole instance. Database roles decide who can read and change data and structure inside each database.

**What could go wrong:** someone with broad rights reads or changes data, changes who has access or turns off auditing. This can happen when `sysadmin` or `db_owner` is given for convenience. The result could be unauthorized changes to financial data.

**Controls that address it:**
- `sysadmin` has a few named members, through Windows groups, and `db_owner` has a few per in-scope database.
- Each application has its own account with permissions through custom roles, not `db_owner`.
- Changes to membership are approved by someone other than the requester.
- People have no standing write access to production data. Data fixes go through a recorded change and are matched to the audit record, and break-glass access is time-limited and reviewed.

**How to show it:** a dated export of role members for in-scope databases, and one data fix traced from request to audit record.

## SQL Server Agent and jobs

**What it does:** runs scheduled work inside the instance, such as backups and data loads.

**What could go wrong:** a job is created or changed to run unapproved code, or runs with more rights than it needs. This can happen when jobs run as `sysadmin`. The result could be unapproved changes to data or the server.

**Controls that address it:**
- Job owners are service accounts or a named group, and jobs run with limited rights, not as `sysadmin`.
- Job definitions are held in a repository, and changes follow change control. See the CI/CD pipelines as change control guide.

**How to show it:** the job inventory with owners.

## Auditing

**What it does:** records who connected, who changed access and structure, and who changed data directly.

**What could go wrong:** a change to data, access or structure happens and nobody can show who did it, or an administrator removes the trail. This can happen when the feed stops unnoticed or administrators can edit the audit files.

**Controls that address it:**
- Auditing records logins, changes to access and structure, and direct changes to data in in-scope tables, which the direct database change review matches to approved changes.
- Audit data goes to a location administrators can't edit and Splunk collects it, with an alert if the feed stops.

**How to show it:** the audit settings, recent events in Splunk and an alert test.

## Encryption

**What it does:** protects data on the network, on disk and in backups.

**What could go wrong:** someone reads data by capturing traffic or taking a copy of a database file or backup, or the keys needed to read encrypted data are lost with the server. The result could be exposed data, or data that can't be restored.

**Controls that address it:**
- Connections, and databases and backups where data classification calls for it, are encrypted.
- Encryption certificates and keys are backed up apart from the data with named owners, and a restore of an encrypted backup on another server has been tested.

**How to show it:** the encryption settings and key backup record.

## Backups and recovery

**What it does:** lets the database be rebuilt after damage, loss or a bad change.

**What could go wrong:** data is lost or can't be restored in time. This can happen when restores are never tried or backups are deleted along with the server. The result could be lost transactions and a long outage.

**Controls that address it:**
- Backups run on a schedule that meets the recovery point for the system's BCP tier, and failed backups raise an alert.
- Restores, and failover where availability groups or log shipping are used, are tested on a schedule with the result recorded.
- Backups are stored away from the server and can't be deleted by database administrators.

**How to show it:** backup history by database and the last restore test record.

## Linked servers

**What they do:** let one instance query another system.

**What could go wrong:** a low-rights user reaches another system through a link that uses a powerful account. This can happen when a link maps every local login to one remote administrator. The result could be access to systems never meant to be reachable.

**Controls that address it:**
- Linked servers are listed with an owner and purpose, and unused ones are removed.
- Each link uses a named remote login with only the rights it needs.

**How to show it:** the inventory with remote logins.

If you're unsure, Tech Risk can help.

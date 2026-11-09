---
title: Active Directory risks and controls by component
section: best_practice
platform: Active Directory
order: 14
---
For each Active Directory component, this guide covers what it does, what could go wrong, the controls that address it and how to show they work.

Whoever controls Active Directory controls every system that trusts it. So the directory, its domain controllers and everything used to administer them are treated as the most trusted systems and kept apart from everyday ones. This guide covers the on-premises side; the Entra ID platform page covers the cloud side, and the Active Directory platform page has the summary by risk area.

## Domain controllers

**What they do:** store the directory and answer every sign-in request, including a copy of every account's password hash.

**What could go wrong:** someone gains control of a domain controller and can read or change every account. This can happen when controllers are reachable from everyday workstations or run extra software. The result could be control of every system that trusts the directory.

**Controls that address it:**
- Controllers sit in secured space, and any virtual hosts under them are administered by the same few trusted people.
- Only directory services and the roles that depend on them run on a controller, and administration comes only from dedicated workstations.
- Controllers run a supported Windows Server version and are patched on the schedule in your team's written procedure.

**How to show it:** the controller list with locations, hosts and operating system versions.

## Privileged groups and delegated rights

**What they do:** groups such as Enterprise Admins and Domain Admins can change anything. Delegation hands smaller rights, such as resetting passwords, to others for part of the directory.

**What could go wrong:** an account in a privileged group, or one with a delegated right over a powerful object, is stolen and used to take over the directory. This can happen when membership is wide or administrators use one account for email and administration. The result could be control of the whole forest.

**Controls that address it:**
- Enterprise Admins and Schema Admins are empty day to day. Domain Admins has a few named members.
- Each administrator has a separate administrative account, used only on the most trusted systems.
- Delegated rights go to groups with an owner and a purpose, and never include editing privileged groups.

**How to show it:** a dated export of privileged group members and approvals for recent changes.

## Accounts and service accounts

**What they do:** user, administrator and service accounts give people and software their identity.

**What could go wrong:** an unused or weakly protected account is taken over and used to move through the environment. This can happen when service accounts have old passwords, or accounts stay active after people leave. The result could be access that looks like normal activity.

**Controls that address it:**
- Group managed service accounts (passwords the directory manages) are used where possible. Other service accounts have an owner, long passwords and no interactive sign-in.
- Stale accounts are found from last logon dates and removed on the schedule in your team's written procedure.
- The `krbtgt` account (the key behind all sign-in tickets) has its password reset twice, on a schedule and after any suspected compromise.

**How to show it:** the service account list compared with the directory, the stale account report and the `krbtgt` reset record.

## Group Policy

**What it does:** pushes settings and scripts to every computer and user in scope.

**What could go wrong:** someone changes a policy that reaches many machines and uses it to run code or weaken settings across the domain. This can happen when many people can edit or link policies. The result could be a widespread outage or a way to take over servers at scale.

**Controls that address it:**
- Only named groups can edit or link policies.
- Policy changes follow change control, with a backup and a record of who changed what.

**How to show it:** who can edit key policies and change records for recent edits.

## Authentication protocols

**What they do:** Kerberos, NTLM and LDAP decide how accounts prove who they are to services and the directory.

**What could go wrong:** an attacker captures or relays credentials and signs in as someone else. This can happen when older protocols stay available. The result could be access to systems under a legitimate account.

**Controls that address it:**
- NTLM is audited first and then restricted as applications are fixed, with exceptions listed.
- Domain controllers require signed LDAP and SMB connections.

**How to show it:** the domain controller policy settings and the NTLM audit review.

## Synchronization to Entra ID

**What it does:** copies accounts and groups from Active Directory to Microsoft Entra ID, so people use one identity on-premises and in the cloud. The two Microsoft tools, Entra Connect Sync and Entra Cloud Sync, are both covered here.

**What could go wrong:** someone takes over the sync server or agent and creates or changes accounts in the cloud, or sync stops and leavers keep cloud access. This can happen when sync servers are treated as ordinary servers. The result could be control of cloud systems through the on-premises directory.

**Controls that address it:**
- Sync servers and agents get the same protection as domain controllers.
- The sync tool is kept on a supported version, and the vendor's retirement notices are tracked.
- Sync accounts have only the rights they need, and changes to what syncs go through change control.
- Privileged accounts aren't synchronized, so Entra ID administrators are cloud-only accounts.

**How to show it:** the sync configuration, scope change records and sync account permissions.

## Auditing

**What it does:** records sign-ins and changes to accounts, groups and the directory.

**What could go wrong:** a privileged change or an attack happens and isn't noticed or can't be investigated. This can happen when a domain controller doesn't send its logs or no alerts are set for changes that matter. The result could be a takeover found only after the damage is done.

**Controls that address it:**
- Every domain controller sends its Security log to Splunk, and an alert fires when one stops.
- Alerts fire for changes to privileged groups, Group Policy changes and a cleared log.

**How to show it:** the audit policy export, a Splunk search showing events from every controller and an alert test.

## Backup and recovery

**What it does:** lets the directory be rebuilt after damage, deletion or an attack.

**What could go wrong:** the directory is damaged or encrypted and can't be restored, so sign-in fails for every dependent system. This can happen when backups are missing, too old or never tested. The result could be a prolonged outage.

**Controls that address it:**
- Backups of domain controllers run on a schedule, are protected like the controllers themselves (they hold every password hash) and are stored apart from them.
- The Active Directory Recycle Bin is on, so deleted objects can be recovered quickly.
- A documented forest recovery approach is stored where it can be read when the directory is down, and tested on a schedule in an isolated network.

**How to show it:** the backup schedule and results, and the last recovery test record.

If you're unsure, Tech Risk can help.

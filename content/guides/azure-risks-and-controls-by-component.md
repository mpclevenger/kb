---
title: Azure risks and controls by component
section: best_practice
platform: Azure
order: 16
---
For each Azure building block, this guide covers what it does, what could go wrong, the controls that address it and how to show they work. The Azure platform page has the summary by risk area. Read it with the Entra ID platform page, since Azure access is managed through Microsoft Entra ID.

Microsoft runs the cloud itself: the data centers, the hardware and the services' underlying software. The system owner reviews Microsoft's SOC report (see [Reading a vendor's SOC report](/guides/reading-a-vendors-soc-report/)). The rest is shared between two groups, so this guide has two parts:

- **The platform team**, the cloud platform team, who set up and run Azure for everyone: the tenant and management groups, subscriptions and policy, Microsoft Entra ID roles for Azure, the shared network and central logging.
- **Teams that use Azure**, who own their workloads, data stores, access within their subscriptions or resource groups, backups and infrastructure-as-code changes.

## For the platform team

### Management groups, subscriptions and policy

**What it does:** management groups organize subscriptions into a hierarchy, and each subscription is a boundary for access, cost and policy. Azure Policy checks resources against rules and can stop or flag those that don't comply.

**What could go wrong:** a mistake or compromise in one subscription spreads to others, or resources are created in a state that doesn't meet the baseline and nobody notices. This can happen when policies only record non-compliance and nobody follows it up. The result could be unauthorized changes across several systems, or public data services and open management ports in production.

**Controls that address it:**
- A subscription per workload and environment, under management groups, with a recorded owner, purpose and BCP tier.
- Azure Policy assignments at management group level act as guardrails that every subscription below inherits. Settings that must never happen are blocked, not just reported.
- Policy exemptions have an owner, a reason and an end date, and Defender for Cloud recommendations are tracked to closure.

**How to show it:** the management group tree, the policy assignments and exemption list, and a dated policy compliance report.

### Privileged access to Azure

**What it does:** decides who holds powerful roles across the tenant. Microsoft Entra ID roles control the directory, and Azure role-based access control (RBAC) roles control Azure resources. They are assigned separately.

**What could go wrong:** someone holds more access than they need, or a stolen credential is used. This can happen when people have permanent Owner rights. The result could be unauthorized changes to production or exposure of data.

**Controls that address it:**
- Privileged Identity Management (PIM) makes powerful roles eligible, so people activate them for a limited time with a reason. Nobody holds permanent standing Owner.
- Emergency access (break-glass) accounts are cloud-only, and any sign-in raises an alert that someone reads.

**How to show it:** the PIM assignment list showing eligible rather than active, and role assignments at management group and subscription scope. Each permanent Owner needs a documented reason.

### Central logging and detection

**What it does:** the Activity Log records changes to Azure resources. Resource diagnostic settings send each service's own logs. Defender for Cloud raises alerts about threats.

**What could go wrong:** a change or attack goes unseen, or the evidence is lost. This can happen when a diagnostic setting is removed or nobody notices that logs stopped. The result could be unauthorized activity that can't be investigated or proven.

**Controls that address it:**
- The Activity Log of every subscription and the Microsoft Entra ID sign-in and audit logs are sent to a Log Analytics workspace, and on to the firm's logging platform (for example, Splunk).
- Azure Policy enforces diagnostic settings, so new resources send logs automatically.
- Defender for Cloud alerts reach a named contact. Alerts fire when a policy assignment or diagnostic setting is changed or deleted, or when log delivery stops.

**How to show it:** the diagnostic settings per subscription, the policy that enforces them and recent events in the logging platform.

### Shared network

**What it does:** virtual networks (VNets) connect resources, and private endpoints give platform services an address inside the VNet.

**What could go wrong:** a server or data service is reachable from the internet or from systems that shouldn't reach it. This can happen when data services have public endpoints. The result could be an attacker reaching a database server or data store directly.

**Controls that address it:**
- Policy keeps public network access off for storage, databases and Key Vault, so they are reached through private endpoints.
- Public IP addresses are inventoried.

**How to show it:** the policy that enforces private access and the public IP address inventory.

## For teams that use Azure

### Access within your subscriptions

**What it does:** decides who can do what to your resources, using Azure RBAC roles at subscription or resource group scope.

**What could go wrong:** someone holds more access than they need, or a stolen credential or stored secret is used. This can happen when people have permanent Owner rights or workloads use stored secrets. The result could be unauthorized changes to production or exposure of data.

**Controls that address it:**
- RBAC roles go to groups at the narrowest scope that works.
- Powerful roles are made eligible through PIM rather than held permanently.
- Workloads use managed identities rather than secrets.

**How to show it:** an export of role assignments for your scopes, including inherited ones.

### Network rules for your workloads

**What it does:** network security groups (NSGs) allow or deny traffic to your subnets, and private endpoints connect your data services.

**What could go wrong:** a server or data service is reachable from the internet or from systems that shouldn't reach it. This can happen when management ports are open to all addresses. The result could be an attacker reaching a database server directly.

**Controls that address it:**
- NSGs name specific sources and ports. None lets the internet reach management or database ports.
- Administrators reach virtual machines through a managed, audited access service or just-in-time VM access, not open management ports.
- Your storage, databases and Key Vault are reached through private endpoints, with public network access off.

**How to show it:** the NSG rules for in-scope subnets and your private endpoint list.

### Virtual machines

**What it does:** virtual machines run servers, including SQL Server on Azure VMs where used.

**What could go wrong:** a server is compromised through a missing patch, or its data is read from a copied disk. The result could be loss of control of the server and the data on it.

**Controls that address it:**
- Machines are built from approved images and patched within the timelines in the Recommended timelines by BCP tier guide, and compliance is reported for every machine.
- Disks are encrypted. Azure Disk Encryption is being retired, so existing use has a migration plan; track Microsoft's retirement notices.

**How to show it:** the Update Manager compliance report and the disk encryption settings.

### Storage, data and keys

**What it does:** storage accounts hold blobs, files and queues. Databases hold structured data. Azure Key Vault holds keys, secrets and certificates.

**What could go wrong:** data is exposed publicly, read with a shared key that gives full access, or deleted and not recoverable, or keys and secrets are read by the wrong people or purged. The result could be a data breach or loss of records.

**Controls that address it:**
- Anonymous blob access is off, with access through private endpoints.
- Shared key access is off where applications can use Microsoft Entra ID. Remaining keys are rotated and held in Key Vault.
- Key Vault uses Azure RBAC, with soft delete and purge protection on. Those who manage a vault are separate from those who use its contents, and deletions and permission changes raise alerts.

**How to show it:** the storage account network and access settings, and the vault settings and role assignments.

### Backup and recovery

**What it does:** backups let your team restore data and servers after loss or deletion.

**What could go wrong:** a backup is missing, deleted along with the data, or can't be restored. This can happen when nobody has tried a restore. The result could be lost data or a long outage.

**Controls that address it:**
- Azure Backup vaults use soft delete and immutability, with geo-redundant storage where the BCP tier calls for it.
- Restores are tested to a separate resource group, and the date and result are recorded.
- Recovery of in-scope servers hosted in Azure is part of the system's recovery plan.

**How to show it:** the backup policy and the latest restore test record.

### Infrastructure as code and change

For the risks and controls that apply to any cloud, see [Infrastructure as code](/guides/infrastructure-as-code/). What is specific to Azure:

- Only the pipeline's identity holds write roles in production. Anyone else's access is read-only, or PIM-eligible for emergencies.
- Changes made by any other identity show in the Activity Log and are followed up.
- A scheduled comparison of the code with the live resources shows drift, and each difference is followed up.

If you're unsure, Tech Risk can help.

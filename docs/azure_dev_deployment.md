# VISION Azure development deployment proposal

**Status: proposal only; no Azure resources or deployment are authorized or configured.**
This is a technical readiness note for an online DEV demonstration using synthetic data.
It is not a production design, security approval, or estimate from KION's Azure agreement.

## Recommended DEV architecture

1. Build the application from this repository into an immutable Linux container image.
2. Push the image to Azure Container Registry (Basic is sufficient for a small DEV image).
3. Run one Azure Container Apps app in a Consumption environment, with Streamlit on port
   `8501`. Use external ingress only after Entra authentication is configured and approved;
   otherwise use internal ingress plus an IT-approved VPN or private network.
4. Put Azure Container Apps Authentication in front of Streamlit using the organization-owned
   Entra application and assigned users/groups. The in-app role picker is navigation only:
   it is not authentication, authorization, or data isolation.
5. Run the synthetic test data only. Re-seed a disposable local container directory on startup;
   do not put SAP workbooks, corporate identifiers, production data, or credentials in the
   image, repository, CI artifacts, or DEV environment.
6. Send platform logs to Azure Monitor with a short, approved retention period. Use managed
   identity for Azure resource access. There are no application secrets currently required.

For CI/CD, GitHub Actions should authenticate to Azure using workload identity federation
(OIDC), build and push an image tagged by commit, and deploy that immutable digest to DEV.
Do not add a client secret to GitHub or the repository. Promotion to TEST/PROD is out of
scope; the existing release policy requires human approval and promotion of the exact digest
validated in TEST.

## Resources and indicative monthly cost

| Resource | DEV purpose | Indicative monthly estimate |
| --- | --- | ---: |
| Container Apps Consumption | One 0.25-vCPU / 0.5-GiB replica | ~$19.71 if continuously active for 730 hours; less if scaled to zero |
| Azure Container Registry Basic | Store the small image | ~$5 |
| Log Analytics | Budget 1 GB ingestion | ~$2.76 |
| Azure Files | **Not recommended for the current SQLite database** | Not included |
| **Always-on demo subtotal** | Before tax, egress, and organization discounts | **~$28/month** |

The Container Apps figure uses public East US example rates ($0.000024 per active vCPU-second
and $0.000003 per GiB-second): `0.25 × 730 × 3600 × 0.000024` plus
`0.5 × 730 × 3600 × 0.000003` = about $19.71. A zero-minimum-replica app has no compute
charge while scaled to zero, but has cold-start delay; active usage is billed and subscription
free grants, if available, are shared across the subscription. Registry and log figures are
rounded public retail estimates, not a quote. Region, currency, billing agreement, network
traffic, log volume/retention, image storage, and other subscription usage can materially
change the total. Confirm with the [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
and the KION Azure owner before provisioning.

Pricing references: [Container Apps](https://azure.microsoft.com/en-us/pricing/details/container-apps/),
[Container Registry](https://azure.microsoft.com/en-us/pricing/details/container-registry/),
[Azure Monitor](https://azure.microsoft.com/en-us/pricing/details/monitor/).

## Configuration and secrets

| Setting | DEV use |
| --- | --- |
| `CO_VISION_DATA_ROOT` | Disposable synthetic data root; must be outside the image's read-only application files |
| `CO_VISION_PROOF_DB` | Optional path for the synthetic PROOF SQLite database |
| `CO_VISION_PROOF_REFERENCE_DB` | Leave unset for the synthetic online demo |
| `CO_VISION_TIMEZONE` | Set only after the product owner approves the intended timezone |
| Entra configuration | Configure in ACA Authentication using the IT-owned app registration; do not invent tenant IDs, client IDs, or group assignments |

No secret values should be supplied until IT defines the approved identity flow. If a secret is
unavoidable, store it in Azure Key Vault or ACA-managed secrets and grant access through a
managed identity. Never expose it to browser JavaScript, Streamlit output, logs, or test
artifacts.

## Health, readiness, persistence

- Streamlit's `/_stcore/health` is a technical process liveness endpoint and is used by the
  Playwright harness. It does **not** prove that SAP data, PROOF history, identity claims, or
  business readiness are available.
- Azure Container Apps supports startup, liveness, and readiness probes. A probe against
  `/_stcore/health` can check that Streamlit responds; it cannot represent data readiness.
  Add a separate, deliberately limited readiness signal before any deployment that depends
  on initialization or persistent storage. Do not expose paths, row counts, or data values
  from health endpoints.
- Container-local storage is ephemeral across replica replacement. The DEV synthetic demo
  can be re-seeded and needs no persistent volume.
- The current engine stores PROOF in SQLite. Do not place that database on an Azure Files
  network share or share it between replicas without a supported file-locking/backup test.
  For durable multi-user data, first approve and implement a managed database adapter,
  migration plan, backups, restore tests, and access controls. This repository does not
  provide those today.

References: [ACA health probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes),
[storage mounts](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts),
[ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview),
[authentication](https://learn.microsoft.com/en-us/azure/container-apps/authentication).

## Security and environment boundaries

- The application has no corporate authentication or server-enforced authorization. A user
  can choose Commercial, Manager, O2C, or Administrator in the UI; those labels do not prove
  identity or protect routes/data. Do not publish it to the public internet or use real
  business data until IT-approved authentication, group-to-role mapping, and server-side
  authorization are implemented and tested.
- Local `.streamlit/config.toml` binds to `127.0.0.1`. ACA must explicitly bind Streamlit to
  `0.0.0.0` inside its container; that is safe only behind the approved ingress and auth
  layer. Local development remains loopback-only.
- DEV must use synthetic data and separate storage/configuration from TEST and PROD. No
  production resource, secret, SAP integration, or Entra registration is configured.
- The administrative screen now displays logical paths/basenames instead of absolute
  filesystem paths. This reduces accidental disclosure but is not an access-control boundary.
- A `pip-audit` scan of the locked dependency export on 2026-11-01 reported no known
  vulnerabilities. GitHub Dependabot alerts are disabled for this repository; that scan is
  a point-in-time result, not continuous monitoring.

## Gates before an online DEV deployment

1. IT/project owner approves the Azure subscription, region, resource group, cost center,
   network exposure, retention, and budget alert.
2. IT provisions or approves the Entra app registration, authentication policy, allowed
   users/groups, and claim contract. No SSO or Entra configuration is implemented here.
3. Product/security owners confirm the DEV demo is synthetic-only and decide whether
   persistence is required. If it is, approve a managed database design rather than assuming
   the current SQLite file can be hosted safely.
4. Define a container build, immutable image digest, OIDC federated deployment identity,
   environment-specific configuration, logs, and rollback procedure in a reviewed change.
5. Define startup/liveness/readiness probe behavior and test restart, cold start, and error
   states. The current `/_stcore/health` check is only process health.

Until those gates are met, the branch is **not ready for an online or production deployment**.
It is suitable for continued local development and CI with synthetic fixtures only.

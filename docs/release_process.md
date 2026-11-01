# Release process

## Intended promotion flow

`Change -> DEV -> automated tests -> TEST -> human approval -> PROD`

- Develop and experiment in DEV only.
- Run the applicable automated tests before a change is promoted to TEST.
- Validate the candidate functionally in TEST without affecting production users.
- Require human approval before production promotion.
- Promote the exact immutable version that passed validation in TEST; do not rebuild or modify it between TEST and PROD.
- Retain the previous production version and a documented rollback procedure.

## Environment isolation

DEV, TEST, and PROD are separate environment levels. TEST and PROD must be able to use separate configuration and storage. Secrets and environment-specific values must not be committed to source control.

## Current status

The repository now contains the local Streamlit application and GitHub Actions validation workflow, and a prepared but inactive, manual DEV deploy workflow (`.github/workflows/deploy-dev.yml`, fail-closed, OIDC, no secrets) with a Bicep template, but no active Azure deployment, environment credentials, Azure storage configuration, or production setup. The proposed hosting platform is documented in [azure_dev_deployment.md](azure_dev_deployment.md) and is not approved or provisioned. The exact artifact format, hosting environment, approval workflow, persistence, and rollback implementation still require owner/IT decisions before any Azure release pipeline is implemented. Never deploy to production without explicit authorization.

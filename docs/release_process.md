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

This repository contains no application, CI workflow, deployment automation, environment credentials, storage configuration, or production setup. No programming language, build tool, artifact format, hosting platform, approval mechanism, or rollback implementation has been selected. Define these with the project owners before implementing the release pipeline. Never publish this repository or deploy to production without explicit authorization.

# Migration intake inventory

Place the existing project materials in the matching folder under a sibling local folder such as `../CO-VISION-inputs`. Keep LION and PROOF materials separate. Do not include credentials, secrets, or data that is not authorized for transfer.

## Required for each module

Place these items in the corresponding `LION` or `PROOF` folder:

- Current source code, preserving its folder structure.
- Dependency and environment files, such as requirements, package manifests, lockfiles, or project files.
- Existing classification rules and queries, including their current location and any approved rule documentation. Do not rewrite or migrate them for intake.
- Existing run, build, and test instructions.

## Optional, when available and authorized

- Example configuration with secrets and credentials removed.
- An authorized, minimized SAP sample and its expected results, preserving enough context to explain the expected output.

No sample data is required to begin reviewing the existing code and rules. Do not place unapproved SAP or corporate data in the intake folders.

## Placement

- `../CO-VISION-inputs/LION/` — existing LION source and its required/optional review materials.
- `../CO-VISION-inputs/PROOF/` — existing PROOF source and its required/optional review materials.

The intake location is outside the CO-VISION repository. It is a local folder only: it is not a Git repository, is not published, and does not move or copy any existing project.

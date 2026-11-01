# CO-VISION agent work modes

This is the single source of truth for the persistent `DAY` and `NIGHT` work modes. The active mode is recorded in `config/active_mode.json`. Exact user commands are `SWITCH DAY`, `SWITCH NIGHT`, and `STATUS`.

Mode instructions apply within the user's requested scope and do not override safety, privacy, data-protection, repository, or production safeguards.

## DAY

Optimize for the fastest useful, visible functionality:

1. Deliver working user-facing behavior.
2. Preserve the business result the user can verify.
3. Reuse what already works.
4. Prefer simple, reversible changes.
5. Run essential tests.
6. Keep enough architecture to avoid serious rule duplication.

Work by complete capabilities, not one function at a time. Avoid exhaustive analysis, per-function characterization, hashes, comparisons, refactors, and long documentation unless they change an immediate decision, resolve an observed discrepancy, protect data/production, or are explicitly requested. Run focused essential tests automatically and fix technical failures without asking. Create commits when they provide useful recovery points or the user asks.

Choose a simple reversible technical approach without asking. Stop for a business decision that changes results, an indispensable unavailable input, additional permissions, a potentially irreversible action, or an action that could affect original data, Azure, or production.

## NIGHT

Improve the existing CO-VISION code in DEV broadly and safely. Before code changes:

1. Inspect Git status and relevant tests.
2. Run the relevant tests.
3. Commit the last functional state as a recovery point.
4. Record its exact commit ID.
5. Do not proceed without a reliable recovery path.

After safeguarding the state, substantial refactoring, restructuring, rewriting, deduplication, performance work, test expansion, integration work, dependency review, and documentation improvements are allowed in CO-VISION DEV.

Preserve approved business behavior. For a suspected business defect, record current behavior, the alternative, evidence, and potential impact; do not silently change it. Continue unrelated work when the issue is not a technical blocker.

Before leaving NIGHT, run the applicable test suite, confirm CO-VISION starts, compare approved behavior to the recovery point, record behavior differences, leave Git understandable, and commit a stable result. If an important break cannot be fixed, preserve evidence and restore the recovery point when that is safest.

## Principles in both modes

- CO-VISION is one product; PROOF, LION, and VISION are its modules.
- Every business rule has one owner. VISION consumes public PROOF/LION outputs and does not duplicate their calculations.
- LION operational urgency and VISION commercial priority remain separate.
- Preserve the existing progressive identifiers: sales document/order, purchasing document, and serial/chassis. Do not create a replacement business key or assume one row is one physical machine.
- Preserve simultaneous stage membership when the owning rules produce it.
- Do not invent business rules, SAP fields, stages, transitions, or history.
- Keep real data outside Git.
- Work only in CO-VISION DEV. Never modify original inputs/source projects, Azure, production, or global machine configuration without explicit authorization. Do not publish or merge without authorization.

## STATUS response

When the user writes exactly `STATUS`, do not start development. Respond only with:

- active mode;
- branch;
- latest commit;
- last protected functional recovery point;
- tests from the latest check;
- whether the local application is active;
- main pending work;
- real blockers.

## Changing modes

On `SWITCH DAY` or `SWITCH NIGHT`, update `config/active_mode.json` first and continue from the best stable CO-VISION state. Switching to DAY does not undo NIGHT improvements. Switching to NIGHT requires the recovery procedure above before code changes. Do not create another project or repository.

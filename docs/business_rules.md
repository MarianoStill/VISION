# Business rules

This document separates observed source-copy behavior from approved business rules. Migrated code preserves behavior found in the received copies; equivalence tests do not approve that behavior or settle conflicting ownership.

## Rule ownership

- **PROOF source-copy behavior:** the migrated `classification_engine.py` classifies a `Data`/`Base` snapshot and the copied Engine can store observations and derive history. VISION reads an existing history without rebuilding it; a new single-file observation does not infer earlier transitions.
- **LION source-copy behavior:** the migrated `lion_sap_engine.py` classifies the XLSX and computes operational urgency; received search, filters, and stage-progress presentation are also available. LION uses its own received classification rules and identity grouping.
- **VISION:** calls public PROOF/LION services and provides a local development view. It does not recalculate either module's classification or urgency. Commercial priority is not implemented.

Both received copies contain classification rules, and they differ. Their coexistence is documented source behavior, not an approved single owner. Do not reconcile, merge, or rewrite those rules without an explicit business decision. Changes should be made only in the agreed owner and flow through its contract; consumers must not duplicate them.

## Distinct concepts

Operational urgency is owned by LION. Commercial priority is owned by VISION. They are separate concepts and must not be conflated, derived from each other, or represented as a single field without an approved requirement.

## Observed display and metric behavior

- LION's stage-progress values are sequence indicators: 0% pending, 50% current, and 100% complete. They do not represent elapsed time. Simultaneous stages remain simultaneous; the received display does not mark intervening stages complete automatically.
- The received PROOF dashboard counts a tracked document as outside its headline threshold when an open standard-stage instance consumes more than 100% of its target. Its per-stage breakdown labels values above 120% as outside the target band. Both behaviors are preserved and displayed separately; they have not been harmonized.
- The received PROOF completion query treats stage ID `9` as the completion event and excludes completions observed on the first date from duration averages. This behavior matched the received query for the supplied history copy; equivalence does not approve its business meaning.

## Requirements still needed

Before business adoption, obtain approval for classification ownership, stage meanings, event semantics, edge cases, calculations, and identifiers. Do not infer them from module names, source equivalence, or synthetic fixtures.

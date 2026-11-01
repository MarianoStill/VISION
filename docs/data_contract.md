# Data contract

No SAP connection, approved source schema, field mapping, or inter-module payload schema is defined. The migrated LION and PROOF loaders preserve the column names and behaviors in their received source copies; those are observed implementation inputs, not a definitive SAP contract. Contracts must be agreed before external integrations or further shared modeling.

## Known machine identifiers

The identifiers are progressive, not interchangeable substitutes:

1. **Sales document/order** — first identifier.
2. **Purchasing document** — becomes available when the factory starts work on the machine.
3. **Serial/chassis number** — becomes available after the machine has been created.

Do not introduce a new business key in place of these identifiers. Exact names in SAP, formats, source fields, relationships, uniqueness, and matching rules have not been specified.

## Contract ownership

The proposed architecture assigns process/history outputs and classification evidence to PROOF, operational outputs to LION, and commercial-priority and user-interaction data to VISION. The existing owner of classification is not validated; confirm ownership from existing code and approved rules before defining or migrating these contracts. Shared contracts belong under `shared/contracts/` only after their consumers and ownership are agreed.

For each future contract, document its owner, consumers, versioning and compatibility policy, field definitions, lifecycle/availability, and validation behavior. This scaffold intentionally supplies no field list or payload example.

The current local workflow passes XLSX bytes independently to LION and PROOF. It does not establish a shared machine record or resolve the different grouping behavior of the received modules. VISION reads an existing PROOF history in read-only mode and can display the stored observations, events, instances, and temporal projections. It links that view to a LION result only when the exact Documento de ventas identifies one LION result and PROOF has records for that order. This is a conservative display association, not an approved cross-module identity contract.

A newly uploaded one-file observation is stored independently in DEV when it is not already present in the configured reference. It does not infer transitions or durations before that observation. Serial and purchasing-document searches in PROOF use exact aliases from the saved workbook sources to locate sales documents; they do not re-key PROOF events or split an order's history among physical machines.

## Data handling

Do not commit SAP extracts, credentials, secrets, or corporate data. DEV, TEST, and PROD must use appropriately separated configuration and storage; no storage provider or deployment configuration is selected here.

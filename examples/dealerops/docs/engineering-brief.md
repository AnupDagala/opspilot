# Explain the mechanism

The business problem is that an informal dealer request cannot directly become a trusted order. The request may omit the product, ask for an unauthorised discount, be delivered twice or change after a manager approves it.

The extractor proposes fields. Application code reads the catalogue, dealer tier, stock and credit. It either asks for missing information, blocks an invalid order, routes an exception or prepares evidence for review. The reviewer approves a specific revision and policy total. A later edit clears approval. Execution rechecks capacity and the approval fingerprint.

The synthetic commit contains stock/credit changes and the receipt in one state document. R2 conditional writes compare the loaded object's ETag. If a concurrent update wins, the loser reloads and recomputes the transition; it does not overwrite the new state. A duplicate event maps to the existing order. A duplicate execution returns its existing effect. Receipt reconciliation resolves the deliberate acknowledgement-loss case.

## Tradeoffs you must be able to discuss

- R2 document compare-and-swap keeps this narrow sandbox easy to deploy. Its state size and per-session contention are intentionally bounded. A real multi-merchant order system should use transactional storage and a durable outbox.
- The public demo's role tokens demonstrate server enforcement, while both roles are deliberately available to the sandbox visitor. Production staff identity, separation of duties and audit retention require a real identity provider and policies.
- The deterministic parser is transparent and conservative, but covers only explicit one-line requests. LLM extraction could support broader language; it must preserve ambiguity and pass the same business validation.
- LangChain is used only in the optional schema-extraction adapter. It does not decide prices or approve orders. A framework is useful when it simplifies a specific boundary, not when it adds ceremony.
- n8n handles intake and orchestration. The service owns invariants; moving approval checks into an editable workflow would weaken that boundary.
- Google Sheets is useful for inventory evidence, but an append operation alone does not provide exactly-once external order delivery. This project intentionally does not claim an untested external commit guarantee.

## Suggested interview demonstration

Show mode and limitations first. Submit a clear order, replay its event and try operator approval. Approve as reviewer, change quantity and show the invalidation event. Reapprove, simulate lost acknowledgement, then reconcile. End with stock, saved receipt and audit readback. Explain the actual test boundaries, then change a policy or add a validation case yourself.

## First genuine integration milestone

Run the real LangChain prompt comparison on the held-out set, connect a synthetic Google Sheet and capture a read-back report, then import and execute the intake workflow in n8n. Use a WhatsApp test number only after obtaining authorised Meta access. Publish the observed failures alongside successful cases.

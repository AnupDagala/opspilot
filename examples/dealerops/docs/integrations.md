# Configure and verify integrations

All examples use synthetic business data. Keep provider/OAuth credentials in environment variables or n8n credentials, never in workflow JSON, screenshots or Git.

## n8n

Docker is not installed in the build environment. The Compose file selects n8n's `stable` image; record the resolved image digest and n8n version when you run it.

```sh
docker compose up -d
```

Open localhost port 5678, complete n8n's owner setup and import `n8n/intake.workflow.json`. Configure an HTTP Header Auth credential with header `Authorization` and value `Bearer <your-sandbox-operator-token>`. Set the request node's `X-Demo-Session` to the corresponding sandbox session. Obtain a sandbox through `/api/session`; tokens belong only to that sandbox and expire with it. An owner-private Site also requires owner-authorised service access; public recruiter access is a separate sharing decision.

The workflow receives a synthetic dealer request, validates its shape, calls the service and returns its measured status. It does not approve or execute orders. Enable Header Auth on the incoming webhook before exposing it beyond localhost. Import the error workflow and select it in workflow settings; it redacts the failure summary and preserves the need for operator review. Actual alert delivery is not configured.

`n8n/verification.workflow.json` is a separate manually triggered fixture. CI imports and executes it against `scripts/ci-server.mjs`, which runs the same order handlers with an explicitly labelled memory storage emulator. The fixture verifies awaiting approval, duplicate-event prevention and operator-role denial. The CI execution passed: [observed run](https://github.com/AnupDagala/opspilot/actions/runs/37659689525). All three assertions returned verified=true. The resolved image digest was sha256:9c0862a08090c79122069e23131d27529c250b92e90c9d51a6ec406fe1527c4e. This verifies the fixture orchestration, not production webhook delivery or live business integrations.

## Optional LangChain extraction

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r python/requirements-live.txt
# Set OPENAI_API_KEY, OPENAI_MODEL and EXTRACTOR_TOKEN in your shell.
.venv/bin/python python/langchain_service.py
```

The service binds only to `127.0.0.1:8789`. POST `/extract` with your extractor bearer token and `{ "message": "20 cartons AB100 tomorrow" }`. It returns structured fields, provider/model mode, latency and observed token usage. It does not fall back when provider execution fails. Windows: use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

```sh
.venv/bin/python python/evaluate_live.py --limit 60
```

The runner invokes each of two prompts on the same cases and stores ignored real-provider evidence under `artifacts/`. It requires keys, performs up to 120 provider calls and measures field extraction, not full production-task success. Review and redact output before publishing it. Optional dependencies/provider compatibility have not been verified here.

The hosted demo has a separate minimal direct-provider adapter using server secrets `MODEL_API_KEY` and `MODEL_NAME`. Configuring that path does not prove LangChain execution. `MODEL_UNAVAILABLE` requests stay saved for `/api/reextract`; no silent mode switch is claimed.

## Google Sheets

Create a synthetic sheet with an `Inventory` tab and columns `SKU`, `Product`, `Price`, `Stock`. Configure an authorised read-access OAuth token as `GOOGLE_ACCESS_TOKEN` and the document identifier as `GOOGLE_SHEET_ID`, then run:

```sh
python3 python/sheets_readback.py
```

The adapter calls the actual Sheets Values API and reads `Inventory!A1:D100`. It is read-only. No successful external run is currently claimed. A real write-back integration needs explicit mapping, credentials and reconciliation tests before orders can be described as synced.

## Recording

Run the hosted verifier with authorised access, inspect its JSON and then execute `python3 scripts/record-evidence.py`. This produces a 92-second replay of the captured API results with mode labels. It is not a browser recording. Browser interaction/visual QA must be performed separately with available browser tooling.

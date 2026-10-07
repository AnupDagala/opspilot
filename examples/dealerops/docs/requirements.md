# Requirement coverage

| Requirement | Implementation | Verification |
|---|---|---|
| Python or JavaScript | JavaScript Worker/API; Python client and optional services | 44 JavaScript behavioural tests; Python compilation |
| Business understanding | Dealer pricing, stock, credit, ambiguous requests and approvals | 60 deterministic cases and hosted scenarios |
| API integration | Real hosted API and R2 persistence | 16 deployed API checks |
| n8n workflow | Intake/error exports, Compose setup and real-runtime CI workflow | Graph/syntax checked; consult CI for runtime outcome |
| LangChain | Structured-extraction service and schemas | Source compiled; dependency/provider execution unverified |
| LLM prompt measurement | Two versions and held-out 60-case runner with latency/usage capture | Not executed against a real provider; no model-performance claim |
| CRM/spreadsheet connection | Google Sheets inventory reader | Not run: authorised Google credentials unavailable |
| WhatsApp-shaped intake | Source classification and webhook workflow | Synthetic API inputs; Meta WhatsApp delivery unverified |
| Duplicate prevention | Event ID bound to message/dealer/channel | Local/concurrent tests and deployed replay |
| Stale approvals | Revision, total, SKU and quantity bound to approval | Local tests and deployed modification flow |
| Failures and recovery | Model-pending state; synthetic lost acknowledgement and receipt readback | Model path mocked/unverified live; deployed receipt reconciliation passed |
| Audit/history | Bounded saved events and downloadable session JSON | API readback checked; browser interaction unverified |
| Video evidence | 92-second rendered replay of actual captured API results | MP4 duration/decoding and preview inspected |
| GitHub publication | Prepared companion under `examples/dealerops` in OpsPilot | Source, tests, integrations and video published under examples/dealerops in OpsPilot |
| Hosted demo | Deployed Worker with R2 | Public sharing enabled; hosted API verification recorded |

Do not describe the project as live AI, production ERP integration, real WhatsApp automation or a browser-recorded demo until the corresponding evidence exists.

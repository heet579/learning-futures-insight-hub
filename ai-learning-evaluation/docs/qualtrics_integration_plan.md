# Qualtrics integration plan

The MVP accepts a Qualtrics-compatible CSV only. Future work should obtain an approved service account and API scope, map Survey/Response IDs to the canonical schema, retrieve only required fields, preserve question metadata, validate pagination/rate limits, and store no raw data beyond approved retention. The connector must handle schema/version changes, partial exports, consent/deletion obligations and retries without duplicate reports. Start with manual approved export, then a read-only sandbox API, then scheduled Power Automate after privacy/security review. Never claim survey comparability until question wording, scales and delivery context are verified.


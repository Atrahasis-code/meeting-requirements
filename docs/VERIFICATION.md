# Verifying the local edition

Run all checks inside Docker:

```sh
sh scripts/test.sh
sh scripts/test-postgres.sh
sh scripts/test-operations.sh
sh scripts/test-worker-recovery.sh
```

Test projects and their volumes are separate from normal data; the suites require no accounts or models. Integration uses real ffprobe, synthetic recordings, simulated transcription, and Mock analysis. UI tests cover criterion changes, rejection with a reason, draft preservation after conflicts, and safe text rendering.

Real ChatGPT and faster-whisper checks are opt-in. There are no inference calls to verify an account automatically; explicit authorization of the text is required. Keep local evidence for each check without publishing tokens or meeting contents.

The Alpha was tested on Linux amd64 through Docker Desktop/WSL2; arm64 dependencies and inference were built and tested through emulation. Later changes require their own verification before claiming compatibility. Emulated tests do not establish performance or native execution on macOS Intel or Apple Silicon. Native macOS validation is not claimed.

## Verification of this delivery

On Linux amd64 / Docker Desktop with WSL2: 50 SQLite backend tests, 21 UI tests, and 11 workflow/PostgreSQL tests passed. The six SQLite-suite skips correspond to PostgreSQL/HTTP tests executed in their specific projects. Normal tests use simulated providers without models or personal credentials. The public candidate is checked as an independent tree; the private delivery record retains operational evidence. This verification does not establish native macOS execution or remote-service integration.

Language tests cover Spanish defaults, persisted English selection, cross-tab changes, unavailable storage, plurals, number/date formatting, validation messages, draft preservation, unchanged requirement content, known API errors, and catalog interpolation parameters. Browser checks exercise both languages in local and private compositions; private checks use synthetic API fixtures rather than real hosted authentication.

## Translation completeness audit

The follow-up audit passed 26 community frontend tests and the TypeScript/Vite production build in an isolated Compose project. It covers rendered errors and notifications switching in both directions, structured API validation errors without exposing input values, native required/email validation, length limits, storage labels, OAuth status codes, and fixed processing/analysis diagnostics with parameters. Generated content, observations, account identifiers, paths, model identifiers, and unknown technical diagnostic codes retain their original values. The static JSX audit permits only branding, native language names, and ID outside the translation catalog.

Browser verification used headless Edge with synthetic API responses: desktop (1440 px) and mobile (390 px), both languages, OAuth status and storage errors, project length validation with the draft preserved across switching, hosted email validation, quota errors, and dismissed member-removal confirmations. All eight edition/language/viewport combinations passed with no page errors or horizontal overflow. Real accounts, models, providers, and normal meeting data were not used.

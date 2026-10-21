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

## Localhost origin regression

The backend origin and CORS policies now use the same explicit loopback allowlist. Regression coverage passes for POST/PATCH/DELETE and credentialed preflight from both `localhost` and `127.0.0.1`, with the configured scheme and port. External domains, lookalike hosts, other ports, other schemes, opaque origins, and cross-site writes remain rejected. Hosted domain configurations retain a single configured origin. OAuth connection attempts from the alternate loopback name move to canonical Settings before creating PKCE state; callback registration is unchanged.

Verification: 61 backend tests passed (six separate-project skips), Ruff passed, and 26 frontend tests plus the TypeScript/Vite production build passed through isolated Compose projects. A separate Nginx/API stack on port 18089 accepted synthetic project creation, editing, and deletion from both loopback names and rejected external origins. No normal meeting data, OAuth credentials, or real analysis were used for these tests.

## Automated localhost integration

`sh scripts/test.sh` runs the full HTTP workflow through the production Nginx proxy. The integration runner shares the frontend's network namespace and connects to `http://localhost:8080` and `http://127.0.0.1:8080`; the test override removes published frontend ports, so the suite can run beside the normal installation without using its port or data. Use Docker Compose v2 with support for the `!reset` YAML tag.

The regression creates its own project and meeting, validates a generated WAV with ffprobe, explicitly starts the Mock transcription worker, reviews the transcript, authorizes Mock analysis, checks the structured output and evidence, validates criteria independently of RF status, and verifies the persisted original, author and revision history. It downloads and checks the 11 Markdown documents plus reviewed transcript, citations and traceability, and confirms that an earlier export remains byte-identical. Preflight/credentialed CORS checks run for both loopback names; an external origin must still be rejected. No accounts, real inference, models, or new host tools are needed. This HTTP integration complements the existing React tests and browser verification; it does not automate browser clicks.

The script accepts only `meeting-ai-test` or `meeting-ai-test-*` project names. Passing a normal installation name exits before invoking Compose. Successful cases delete only the project UUID they created; failed fixtures remain in the isolated test volumes for diagnosis. Teardown preserves volumes.

Run just integration from the private master or independent community root:

```sh
docker compose -p meeting-ai-test-localhost -f compose.yaml -f compose.test.yaml build backend worker frontend initialize integration-tests
docker compose -p meeting-ai-test-localhost -f compose.yaml -f compose.test.yaml up -d --wait backend worker frontend
docker compose -p meeting-ai-test-localhost -f compose.yaml -f compose.test.yaml run --rm integration-tests
docker compose -p meeting-ai-test-localhost -f compose.yaml -f compose.test.yaml down
```

The PostgreSQL test script uses the same proxy-based integration after its database checks.

This regression delivery passed three HTTP integration cases through the master compatibility entrypoint and the independent community tree. The community script also passed 61 backend tests (eight expected integration/PostgreSQL skips), Ruff, and 26 React tests. PostgreSQL passed its 11 workflow/migration tests and the same three proxy integration cases. The normal installation remained running, with DEMO hashes checked separately.

## GitHub Actions

`.github/workflows/ci.yml` runs on every repository push and on pull requests, with a manual dispatch option. The SQLite job runs `sh scripts/test.sh` (backend, React, Ruff and full localhost integration); the PostgreSQL job runs `sh scripts/test-postgres.sh`. Both jobs use fresh GitHub-hosted Ubuntu runners, isolated Compose projects, synthetic audio, Mock analysis/transcription and no published test ports. They do not use self-hosted runners, application credentials, saved models, DEMO volumes or deployment environments. Builds still download the pinned public images and dependencies.

The workflow grants only `contents: read` for GitHub's temporary checkout token and disables persisted checkout credentials. It references no repository secrets, API/OAuth keys, cloud services or real-provider test switches. Checkout is fixed to a full commit SHA; pull requests use the ordinary `pull_request` event. Older runs on the same event/ref are cancelled, each job has a timeout, and cleanup preserves test volumes. CI does not deploy, publish packages or upload application data. Fork contributions may require GitHub's normal maintainer approval before running.

The workflow becomes active when its commit is pushed to GitHub. Local Compose results and workflow linting do not establish a successful GitHub-hosted run; inspect the repository's Actions tab after publication. No repository secrets need to be configured.

## Reviewed-block selection — 2026-10-21

Only blocks explicitly marked Reviewed enter new analyses. Pending and Discarded blocks remain available in the complete transcript. The isolated selection suite covers exclusive decisions, recovery from discard, no-op updates, text edits returning to pending, stale revisions, empty input, provider payload filtering, immutable authorized snapshots, historical exports and additive migration preservation. PostgreSQL runs this suite alongside the workflow and migration tests. The localhost HTTP regression also discards/restores a block and verifies that empty selection is rejected through the frontend proxy.

The new UI tests cover filtering, the Reviewed/Discarded/Pending controls without a separate uncertainty checkbox, explicit saving, preserved drafts on conflict, exact analysis previews, empty selection and English/Spanish copy. Normal verification uses Mock, synthetic audio, isolated Compose projects and no provider credentials or model downloads. Existing installations are not migrated by these tests.

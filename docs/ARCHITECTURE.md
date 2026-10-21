# Architecture

## Components

- React/TypeScript/Vite frontend, Tailwind, and shadcn/ui-style components built on Radix. Routing, TanStack Query, and React Hook Form/Zod forms. Non-root Nginx serves the build and proxies the API and callback. Vite provides the same proxy during development.
- FastAPI separates Pydantic contracts, data access, application services, storage, OAuth, analysis, and export.
- A dedicated worker uses a `flock` lock on the SQLite volume. Each job runs in an isolated spawned process that releases native memory when it exits. The supervisor maintains a heartbeat even during inference.
- Local SQLite uses foreign keys, busy_timeout 5000, WAL, and short transactions. Alembic initializes the schema before the main services start. The `one_running_job` partial index prevents more than one global `running` job. The API checks that a meeting has no active jobs before accepting another; this check is not a transactional unique constraint per meeting. The worker lock keeps execution sequential.

The queue does not use Redis/Celery. New jobs require manual actions. Internal states use English; the UI translates them into the selected interface language. Registered represents a meeting without a file. Blocked and interrupted extend the requested states and retain the reason and checkpoints. Restarting only the API does not change a job that is still running.

## Volumes

| Volume | Mount | Contents |
|---|---|---|
| database | /data/db | SQLite, WAL/SHM, worker lock, and persisted heartbeat |
| media | /data/media | Recordings with UUID names and validated formats |
| transcripts | /data/transcripts | TXT/JSON/SRT/VTT and temporary audio chunk |
| exports | /data/exports | Packages identified by project/meeting/UUID, never overwritten |
| models | /data/models | Reusable Hugging Face/CTranslate2 models |
| authentication | /data/auth | Host ID, OAuth registrations, and this application's tokens |

The default project is `meeting-requirements-ai-local`; effective volume names use that prefix. For additional installations, use a distinct name with `docker compose -p <nombre>` in every command and an available `APP_PORT`. Reusing a project name reuses its volumes, including authentication. `docker compose down` preserves volumes. **Do not use `down -v` with real data.** NFS/SMB/9p/virtiofs are not supported for SQLite. Do not remap database to synchronized folders or folders shared between machines.

## Transcription and analysis

FFmpeg produces a five-minute mono PCM 16 kHz chunk with two seconds of context at each end. Words are assigned to half-open central intervals using their global midpoint. This prevents the same timestamped result from being included twice; words recognized differently in overlapping chunks still require human review. Progress indicates seconds of committed chunks, not an estimate of remaining time.

Model download and loading durations are indeterminate. Cancellation is checked between chunks/segments; after the grace period, the process group is terminated and committed work is retained. Checkpoints are not complete transcripts. There is no pause button: canceling and retrying allows processing to continue from checkpoints.

Original text is immutable. Corrections use a global revision to detect concurrent edits. An analysis retains its authorized input, context, glossary, revision, and hash. Requirements retain generated content, evidence, and human revisions. Exports use the edited requirements and the transcript snapshot belonging to the analysis, avoiding a mix of evidence and incompatible later corrections.

Long inputs are extracted in blocks of segments. Citations, references, and codes are validated, and exact duplicates are merged within the run. There is no semantic consolidation across meetings. Unapproved results are exported with their status; an export never constitutes approval. The API provides `code_mapping` to resolve generated references to each version's persisted codes in stories, criteria, and backlog. Original JSON remains immutable; dependencies are exported with readable codes, and the matrix includes the backlog.

## API

OpenAPI is available at `/api/openapi.json` and interactive documentation at `/api/docs` through the local proxy. The API retains projects, meetings, uploads, transcribe/analyze, jobs/cancel, transcript-segments, requirements/validate, exports/download, health, and settings.

Changes from the initial specification:

- GET `/api/dashboard` returns actual counters and jobs.
- GET `/api/meetings/{id}/analysis-input` returns the exact input and its hash; POST analyze requires that hash and consent for an external provider.
- GET `/api/meetings/{id}/analyses`, POST `/api/analysis-runs/{id}/activate`, and GET `/api/meetings/{id}/exports` manage versions.
- POST `/api/jobs/{id}/retry` requires renewed authorization for analysis and allows compatible checkpoints to continue.
- DELETE `/api/meetings/{id}/media?confirm=true` removes only audio/video, retaining textual evidence; DELETE meeting removes everything after confirmation.
- GET `/api/meetings/{id}/transcript/download?format=txt|json|srt|vtt` and GET export download with `file` download allowed formats/documents.
- The UI polls every two seconds; `/jobs/{id}/events` is not implemented because SSE is not used.
- OAuth and the model catalog use `/api/auth/chatgpt/*`, `/auth/callback`, and `/api/providers/chatgpt/models`.

Secrets are never included in response schemas. File endpoints resolve relative paths within the authorized volume. Actual received size, extension, media container, and audio presence are validated. Shell commands are not interpolated.

## Revisions, PostgreSQL, and extensions

Criteria support individual retrieval, editing, and explicit validation/rejection with optimistic revision checks. Changing Given/When/Then returns a criterion to pending; saving identical text does not change its status. Rejection requires a reason, and changes require an active version. Approving a criterion does not alter its original or functional/non-functional requirements (RF/RN in the UI). New history identifies the local user; an old event without identity is not retroactively attributed.

SQLite retains WAL and its connection settings. PostgreSQL is opt-in through a Compose override and uses an advisory lock for a single local worker. Relationships prevent mixing organizations, and each transaction sets its context; the local distribution always uses the local workspace. Storage/provider adapters and execution policy have complete local defaults, without imports or dependencies on a private edition.

## Interface language

English and Spanish use bundled application-message catalogs; Spanish is the default. The selector updates the UI without reloading, keeps drafts mounted, persists `mra-language` in browser storage, and synchronizes open tabs on the same origin. If storage is unavailable, the selection still works for the current page. HTML language metadata, dates, numbers, and plural labels follow the selection.

This preference is independent of the recording's transcription language and never changes meeting content, analysis snapshots, API resource identifiers, original text, or exports. Only static application messages are translated; unknown provider diagnostics retain their original text. There are no translation-service calls or additional runtime dependencies. Custom application entrypoints may register their own static UI catalogs; none are loaded by the community entrypoint unless explicitly imported.

## Human selection before analysis

Transcript blocks retain `reviewed` and add `discarded` (false by default). A database constraint forbids both flags being true. Both false means pending. PATCH normalizes the opposite flag when reviewing/discarding; real text changes reset the decision unless explicitly reconfirmed. No-op updates preserve the transcript revision. Original text, block IDs and recording timestamps are never removed by exclusion.

Analysis snapshots carry `selection_policy: reviewed_only_v1`, selection counts and only reviewed, non-discarded, nonempty blocks in temporal order. The complete snapshot is hashed and checked at admission. The worker executes the immutable authorized input, so later selection changes apply only to later analyses. Legacy jobs without the policy block before accessing the provider and require renewed review/consent; changed hashes never reuse checkpoints. Completed analyses, evidence and exports keep their earlier input.

The additive 0004 migration preserves existing reviewed flags and defaults discarded to false, without rebuilding SQLite tables or replacing tenant triggers. JSON transcript downloads include selection flags; TXT/SRT/VTT downloads remain complete. Analysis exports continue using their persisted input snapshot.

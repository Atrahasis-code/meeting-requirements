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

On Linux amd64 / Docker Desktop with WSL2: 50 SQLite backend tests, 13 UI tests, and 11 workflow/PostgreSQL tests passed. The six SQLite-suite skips correspond to PostgreSQL/HTTP tests executed in their specific projects. Normal tests use simulated providers without models or personal credentials. The public candidate is checked as an independent tree; the private delivery record retains operational evidence. This verification does not establish native macOS execution or remote-service integration.

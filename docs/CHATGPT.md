# Official ChatGPT connection

## Setup

1. Open **Configuración** (Settings) and select **Conectar con ChatGPT** (Connect with ChatGPT).
2. Authorize the local application through OpenAI's official page.
3. The browser returns to `http://127.0.0.1:8080/auth/callback` (or the configured APP_PORT).
4. Check that plan-usage permission was granted. Select a model from your account's catalog and save preferences.
5. Open ChatGPT's usage controls and set credits to zero for this application. Confirm this manually in the UI.
6. Review a transcript and authorize an analysis. Only a completed and validated real result verifies inference access.

Accounts or policies that do not support this integration must display the limitation. The application does not switch to API keys or import tokens from other clients. You do not need to run `codex login` on the host.

## Implementation

The backend implements public-client OAuth with PKCE S256, state, nonce, and ID-token validation through JWKS. It requests `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`, using `dynamic_agent_client` only for initial registration. The issued client_id and host ID remain associated with each registration. Attempts expire, and the callback is bound to a local HttpOnly/SameSite cookie.

The provider uses `openai-codex==0.163.0` and its pinned runtime. The signatures of `CodexConfig`, `thread_start`, and `Thread.run` were checked in the published package. App-server receives only the application's own OAuth token through the child process environment, never command-line arguments. It configures `openai_chatgpt_plan` against the public Responses endpoint, without alternative authentication or WebSockets. The SDK maintains stdio transport. A test using a local server inspects the actual request and verifies `store=false`, streaming, and JSON Schema; it requires no credentials and performs no external inference.

Shell, snapshots, multiple agents, autonomous goals, apps, plugins, MCP, browser, image generation, and web access are disabled. Before app-server starts, the pinned runtime's options are checked; execution is rejected if any restriction is not applied. Codex's environment and HOME are temporary, without host configuration or connectors. A read-only sandbox, `ApprovalMode.deny_all`, and an isolated directory are used. Transcripts are untrusted data; only structured results are requested, and they are validated before persistence.

Each block starts an app-server with the current token. Refresh is serialized through a credential-storage lock and atomically replaces the rotated refresh token. The session persists across container restarts; revocation requires reconnection. A network failure does not automatically delete a valid session. Disconnect attempts official revocation and reports when it could not be confirmed.

## Usage

There are no automatic inference calls to check availability. Fetching the catalog does not establish model access. There are no automatic inference retries, purchases, or top-ups.

If `subscription_sharing_usage_limit_exceeded` is received, the job becomes blocked and retains completed results from previous blocks. Review ChatGPT usage; the application does not invent a reset date. Save the manual limit confirmation again and use **Revisar y reanudar análisis** (Review and resume analysis) to authorize another attempt.

The local zero-credit confirmation cannot replace ChatGPT's actual controls. If you later change those limits, you must keep them at zero to retain that protection. The application does not promise to know your balance or provide a limit independent of your account.

## Official references

- [Registration and OAuth](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Sessions and refresh](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
- [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [Integration limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## Analysis blocked by a validation error

The local installation allows real analyses of demonstration meetings as well. Automatic validation of the provider response is independent of human approval of functional/non-functional requirements and criteria.

- `invalid_analysis_result`: the provider finished, but its response does not meet the format or contains inconsistent references. The message identifies a safe cause, such as a nonexistent requirement, without including the received text.
- `invalid_provider_response`: the SDK could not interpret the runtime response. This requires a compatibility review; reconnecting the account is not the default solution.
- Older attempts that stored only `Diagnóstico seguro: validation` do not allow the exact rejected field to be reconstructed. That error is not attributed to quota or credentials without evidence.

A rejected response does not replace the active analysis or its exports. Inference is not automatically repeated: for another attempt, use **Revisar y reanudar análisis** and confirm the exact input. The schema limits citations to authorized segments when this fits within the provider's limits; citations and relationships are always checked after generation.

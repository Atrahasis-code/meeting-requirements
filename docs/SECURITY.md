# Security and privacy

## Deployment scope

The local edition is designed for a single owner and is exposed only on localhost through Docker Compose. It does not require a Meeting Requirements AI account, subscription, or hosted server. Do not expose its port directly to the Internet.

## Authentication and credentials

ChatGPT tokens belong to this installation and are stored in its private authentication volume with `0600` file permissions. The application does not read host credentials, mount user credential directories or the Docker socket, or automatically fall back to API keys. A new installation must connect its own account and confirm its usage controls.

## Data processing and external connections

Transcription runs on the CPU using INT8. Only the text explicitly authorized for each analysis is sent to the analysis provider. Original text, citations, and analysis versions are retained in the local database. An analysis or export does not constitute human approval.

The application contacts OpenAI when connecting an account, refreshing authentication, fetching models, or running an authorized analysis. It contacts model repositories when downloading a requested transcription model. Docker and package installers download pinned images and dependencies during builds. The application has no first-party telemetry, license checks, or subscription requests.

## Untrusted content

Transcripts and model output are treated as untrusted data. They cannot authorize command execution, connectors, browsing, file access, or delegation. Output is checked against schemas, citations, and references; fields are rendered as text. These boundaries limit capabilities and exposure but do not guarantee perfect detection of prompt injection.

## Files, containers, and backups

File paths, media contents, and upload sizes are validated. Main application containers run as non-root users with resource limits. Recordings never start transcribing automatically.

The database and backups contain sensitive information. Protect the host, its disks, and its backups. Never commit tokens or recordings to Git. See the [operations guide](OPERATIONS.md) for backup and restoration procedures.

## Reporting a vulnerability

Use the repository's private security reporting channel when it is available. Do not attach secrets, recordings, or transcripts to public issues.

If no private reporting channel is listed, ask the maintainer how to report privately without disclosing vulnerability details or sensitive data in public.

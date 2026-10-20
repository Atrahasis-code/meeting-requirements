# Installation by platform

## Windows with WSL2

Install Docker Desktop, enable its WSL2 backend, and enable integration with your distribution. Run Compose commands from that distribution, preferably with the repository in the Linux filesystem rather than a synchronized corporate folder. Check `docker version` and `docker compose version`.

You do not need to install Python, Node, or FFmpeg in Windows or WSL to run the application. Do not mount the Docker socket inside containers. Named volumes reside in Docker's local storage.

If Docker reports a Windows credential-helper failure from WSL, check Docker Desktop integration and the context with `docker context ls`. The `default` context must reach the available engine. Elevated permissions do not replace correct WSL integration.

The following `%UserProfile%/.wslconfig` configuration is an optional reference, not a change made by the application:

```ini
[wsl2]
memory=5GB
processors=4
swap=2GB
```

After manual changes, `wsl --shutdown` stops all distributions. These limits affect all WSL2 distributions and services. The containers and their builds need memory beyond the worker's limit; increase Docker's memory allocation if a build runs out of resources.

## Linux

Install Docker Engine and the Docker Compose plugin. Ensure your user can access the daemon through your distribution's Docker configuration. Do not change socket permissions to `777`. Installing the project's development stack is not required.

## macOS Intel and Apple Silicon

Install Docker Desktop and enable Compose. The project lets Docker select the native architecture: it does not force `platform: linux/amd64` on Apple Silicon.

The base images and major native dependencies publish Linux amd64 and arm64 variants. This does not prove that this application runs on macOS. Consult the verification record to distinguish builds, emulation, and native execution. Platform compatibility is declared only after testing.

## Common configuration

```sh
docker compose up --build -d
docker compose ps
docker compose logs -f
```

Open `http://127.0.0.1:8080` or `http://localhost:8080`. Both local names are accepted on the configured APP_PORT; other ports and external origins are rejected. OAuth uses the installation’s canonical address (`127.0.0.1` by default), because browser cookies are bound to their host. Starting a connection from the alternate local name first moves to the canonical Settings page; select Connect with ChatGPT or Another account there to continue. The registered callback URI is unchanged. If you change APP_PORT, recreate the services and use the new port.

The initialize service prepares volumes with UID/GID 10001 and runs Alembic after dropping root privileges. Main processes run as non-root users. A migration error prevents the API/worker from starting; retain the data and review logs before retrying.

To change CPU/RAM, edit `.env` and run `docker compose up -d --force-recreate`. Runtime limits do not automatically limit BuildKit build memory. The **Calidad** (Quality) profile may exceed 3 GiB and be terminated for OOM; increase WORKER_MEM_LIMIT or use **Equilibrado/Económico** (Balanced/Economy).

An interrupted model download is retried from the cache when another transcription starts. Network errors do not authorize sending audio to third parties.

## Interface language

Choose English or Español in the top bar, or inside the navigation menu on mobile. Spanish is the default; the preference is local to the browser and is retained after reloading. Transcription language is a separate setting. Switching interface language does not send data, authorize an analysis, or translate existing recordings, transcripts, requirements, or exports.

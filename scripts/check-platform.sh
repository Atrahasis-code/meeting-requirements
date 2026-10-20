#!/bin/sh
# Build and load a single platform locally. Never pushes images.
set -eu
cd "$(dirname "$0")/.."
platform=${1:-linux/amd64}
case "$platform" in linux/amd64|linux/arm64) ;; *) echo 'Use linux/amd64 or linux/arm64' >&2; exit 1;; esac
architecture=${platform#linux/}
for service in backend worker frontend; do
  docker buildx build --platform "$platform" --target runtime -f "$service/Dockerfile" -t "meeting-ai-$service:$architecture-check" --load .
done
docker run --rm --platform "$platform" --entrypoint python "meeting-ai-worker:$architecture-check" -c "import platform,av,ctranslate2,faster_whisper; assert 'int8' in ctranslate2.get_supported_compute_types('cpu'); print(platform.machine(), av.__version__, ctranslate2.__version__)"
docker run --rm --platform "$platform" --entrypoint ffmpeg "meeting-ai-worker:$architecture-check" -version
echo 'Build/import verification complete. This does not establish native macOS compatibility or real inference.'

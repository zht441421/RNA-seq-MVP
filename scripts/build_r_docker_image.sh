#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${DOCKER_R_IMAGE:-bioinformatics-agent-r-bulk-rnaseq:0.1}"
DOCKER_EXECUTABLE="${DOCKER_EXECUTABLE:-docker}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

if ! command -v "${DOCKER_EXECUTABLE}" >/dev/null 2>&1; then
  echo "Docker executable '${DOCKER_EXECUTABLE}' was not found. Install Docker Desktop and make sure it is on PATH." >&2
  exit 1
fi

echo "Building Docker image: ${IMAGE_NAME}"
echo "Repository root: ${REPO_ROOT}"

"${DOCKER_EXECUTABLE}" build -f docker/r-bulk-rnaseq/Dockerfile -t "${IMAGE_NAME}" .

echo
echo "Build complete: ${IMAGE_NAME}"
echo "Next checks:"
echo "  scripts/test_r_docker_image.sh"
echo "  GET http://127.0.0.1:8000/system/docker-r-env"


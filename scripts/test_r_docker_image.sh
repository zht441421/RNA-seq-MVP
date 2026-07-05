#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${DOCKER_R_IMAGE:-bioinformatics-agent-r-bulk-rnaseq:0.1}"
DOCKER_EXECUTABLE="${DOCKER_EXECUTABLE:-docker}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v "${DOCKER_EXECUTABLE}" >/dev/null 2>&1; then
  echo "Docker executable '${DOCKER_EXECUTABLE}' was not found. Install Docker Desktop and make sure it is on PATH." >&2
  exit 1
fi

if ! "${DOCKER_EXECUTABLE}" image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Docker image '${IMAGE_NAME}' was not found. Build it with scripts/build_r_docker_image.sh." >&2
  exit 1
fi

echo "Running R/Bioconductor environment check in image: ${IMAGE_NAME}"
OUTPUT="$("${DOCKER_EXECUTABLE}" run --rm \
  --mount "type=bind,source=${REPO_ROOT},target=/workspace" \
  -w /workspace \
  "${IMAGE_NAME}" \
  Rscript backend/app/scripts/r/check_bioconductor_env.R)"

echo "${OUTPUT}"
echo

if command -v jq >/dev/null 2>&1; then
  echo "ready_for_real_r: $(printf '%s' "${OUTPUT}" | jq -r '.ready_for_real_r')"
  echo "missing_required: $(printf '%s' "${OUTPUT}" | jq -r '.missing_required | join(", ")')"
  echo "missing_optional: $(printf '%s' "${OUTPUT}" | jq -r '.missing_optional | join(", ")')"
  echo "Package versions:"
  printf '%s' "${OUTPUT}" | jq -r '.packages | to_entries[] | "  \(.key): installed=\(.value.installed), version=\(.value.version)"'
else
  READY="$(printf '%s' "${OUTPUT}" | sed -n 's/.*"ready_for_real_r":\([^,}]*\).*/\1/p')"
  echo "ready_for_real_r: ${READY:-unknown}"
  echo "Package versions are shown in the JSON above. Install jq for a formatted summary."
fi


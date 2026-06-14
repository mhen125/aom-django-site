#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.venv/bin/activate"
fi

cd "${PROJECT_ROOT}"

MATCH_TYPE="${PROSTAGMA_REPLAY_MATCH_TYPE:-1}"
LOOKBACK_DAYS="${PROSTAGMA_REPLAY_SINCE_DAYS:-7}"
PARSE_LIMIT="${PROSTAGMA_REPLAY_LIMIT:-10}"
POLL_SECONDS="${PROSTAGMA_REPLAY_POLL_SECONDS:-300}"
SUPPORTED_BUILDS="${PROSTAGMA_REPLAY_SUPPORTED_BUILDS:-${REPLAY_SUPPORTED_BUILDS:-}}"

COMMAND=(
  python manage.py run_replay_pipeline
  --ranked-only
  --match-type "${MATCH_TYPE}"
  --1v1-only
  --since-days "${LOOKBACK_DAYS}"
  --missing-url-only
  --live-history
  --limit "${PARSE_LIMIT}"
  --loop
  --poll-seconds "${POLL_SECONDS}"
)

if [[ "${PROSTAGMA_REPLAY_SKIP_UNKNOWN_BUILDS:-0}" == "1" ]]; then
  COMMAND+=(--skip-unknown-builds)
fi

if [[ -n "${SUPPORTED_BUILDS}" ]]; then
  IFS=',' read -r -a BUILD_ARRAY <<< "${SUPPORTED_BUILDS}"
  for build in "${BUILD_ARRAY[@]}"; do
    build="${build// /}"
    if [[ -n "${build}" ]]; then
      COMMAND+=(--supported-build "${build}")
    fi
  done
fi

exec "${COMMAND[@]}"

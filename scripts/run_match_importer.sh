#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="python3"

if [[ -x "${PROJECT_ROOT}/venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
elif [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
fi

cd "${PROJECT_ROOT}"

MATCH_TYPE="${PROSTAGMA_IMPORT_MATCH_TYPE:-1}"
LEADERBOARD_PAGES="${PROSTAGMA_IMPORT_LEADERBOARD_PAGES:-1}"
LEADERBOARD_COUNT="${PROSTAGMA_IMPORT_LEADERBOARD_COUNT:-25}"
PLAYER_LIMIT="${PROSTAGMA_IMPORT_PLAYER_LIMIT:-10}"
RECENT_COUNT="${PROSTAGMA_IMPORT_RECENT_COUNT:-5}"
TRANSPORT="${PROSTAGMA_IMPORT_TRANSPORT:-curl}"

COMMAND=(
  "${PYTHON_BIN}" manage.py import_recent_matches
  --match-type "${MATCH_TYPE}"
  --leaderboard-pages "${LEADERBOARD_PAGES}"
  --leaderboard-count "${LEADERBOARD_COUNT}"
  --recent-count "${RECENT_COUNT}"
  --transport "${TRANSPORT}"
)

if [[ "${PLAYER_LIMIT}" != "0" ]]; then
  COMMAND+=(--player-limit "${PLAYER_LIMIT}")
fi

if [[ "${PROSTAGMA_IMPORT_REFRESH:-0}" == "1" ]]; then
  COMMAND+=(--refresh)
fi

exec "${COMMAND[@]}"

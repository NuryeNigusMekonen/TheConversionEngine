#!/usr/bin/env bash
set -euo pipefail

EVAL_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$EVAL_DIR/.." && pwd)"

if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

if [ -n "${OPENROUTER_MODEL:-}" ]; then
  DEFAULT_OPENROUTER_LLM="openrouter/${OPENROUTER_MODEL#openrouter/}"
else
  DEFAULT_OPENROUTER_LLM=""
fi

TAU2_AGENT_LLM="${TAU2_AGENT_LLM:-$DEFAULT_OPENROUTER_LLM}"
TAU2_USER_LLM="${TAU2_USER_LLM:-$TAU2_AGENT_LLM}"
TAU2_MAX_CONCURRENCY="${TAU2_MAX_CONCURRENCY:-1}"
TAU2_EVAL_LLM="${TAU2_EVAL_LLM:-$TAU2_AGENT_LLM}"
TAU2_NL_ASSERTIONS_LLM="${TAU2_NL_ASSERTIONS_LLM:-$TAU2_EVAL_LLM}"
TAU2_EVAL_USER_SIMULATOR_LLM="${TAU2_EVAL_USER_SIMULATOR_LLM:-$TAU2_EVAL_LLM}"
TAU2_ENV_INTERFACE_LLM="${TAU2_ENV_INTERFACE_LLM:-$TAU2_EVAL_LLM}"

export TAU2_EVAL_LLM
export TAU2_NL_ASSERTIONS_LLM
export TAU2_EVAL_USER_SIMULATOR_LLM
export TAU2_ENV_INTERFACE_LLM

: "${TAU2_AGENT_LLM:?Set TAU2_AGENT_LLM or OPENROUTER_MODEL.}"
: "${TAU2_USER_LLM:?Set TAU2_USER_LLM or OPENROUTER_MODEL.}"

cd "$EVAL_DIR/tau2-bench"

if [ ! -d ".venv" ]; then
  uv sync
fi

uv run tau2 run \
  --domain retail \
  --agent-llm "$TAU2_AGENT_LLM" \
  --user-llm "$TAU2_USER_LLM" \
  --num-trials "${TAU2_NUM_TRIALS:-1}" \
  --num-tasks "${TAU2_NUM_TASKS:-5}" \
  --max-concurrency "$TAU2_MAX_CONCURRENCY" \
  "$@"

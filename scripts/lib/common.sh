# Shared helpers for govbid shell entrypoints.
# Source from repo root runners: source "$PROJECT/scripts/lib/common.sh"

govbid_bootstrap_env() {
  local project="${1:-}"
  [[ -n "$project" ]] || return 0
  export PATH="$HOME/.local/bin:${project}/.postgres/mamba/bin:${PATH}"
  if [[ -z "${UV:-}" && -x "$HOME/.local/bin/uv" ]]; then
    export UV="$HOME/.local/bin/uv"
  fi
}

govbid_ensure_postgres() {
  local project="${1:-}"
  [[ -n "$project" ]] || return 0
  bash "$project/scripts/setup_user_postgres.sh"
}

govbid_require_cmd() {
  local cmd="$1"
  local hint="${2:-}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command not found: $cmd" >&2
    [[ -n "$hint" ]] && echo "$hint" >&2
    return 1
  fi
}

govbid_acquire_lock() {
  local lock_file="$1"
  local label="${2:-job}"
  mkdir -p "$(dirname "$lock_file")"
  exec {GOVBID_LOCK_FD}>"$lock_file"
  if ! flock -n "$GOVBID_LOCK_FD"; then
    echo "=== $(date -Is) $label already running; exiting ===" >&2
    exit 0
  fi
}

govbid_resolve_uv() {
  if [[ -n "${UV:-}" ]] && [[ -x "${UV}" || -n "$(command -v "$UV" 2>/dev/null)" ]]; then
    command -v "$UV" 2>/dev/null || echo "$UV"
    return 0
  fi
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi
  if [[ -x "$HOME/.local/bin/uv" ]]; then
    echo "$HOME/.local/bin/uv"
    return 0
  fi
  echo "Error: uv not found. Install: https://docs.astral.sh/uv/" >&2
  return 1
}

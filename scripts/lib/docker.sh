# Resolve a working Docker CLI on WSL (integration shim vs docker.exe vs desktop path).
# Source after common.sh if needed: source "$PROJECT/scripts/lib/docker.sh"

# #region agent log
_govbid_debug_log() {
  local hypothesis_id="$1" location="$2" message="$3" data="${4:-{}}"
  local log_path="/home/me/rs/.cursor/debug-884a3e.log"
  local ts
  ts="$(date +%s%3N 2>/dev/null || date +%s)000"
  mkdir -p "$(dirname "$log_path")"
  printf '{"sessionId":"884a3e","hypothesisId":"%s","location":"%s","message":"%s","data":%s,"timestamp":%s}\n' \
    "$hypothesis_id" "$location" "$message" "$data" "$ts" >>"$log_path" 2>/dev/null || true
}
# #endregion

_govbid_docker_candidate_ok() {
  local cmd="$1"
  [[ -n "$cmd" ]] || return 1
  if [[ "$cmd" == *.exe ]]; then
    command -v "$cmd" >/dev/null 2>&1 || [[ -x "$cmd" ]] || return 1
    "$cmd" info >/dev/null 2>&1
    return $?
  fi
  command -v "$cmd" >/dev/null 2>&1 || [[ -x "$cmd" ]] || return 1
  "$cmd" info >/dev/null 2>&1
}

govbid_resolve_docker() {
  # #region agent log
  _govbid_debug_log "A" "docker.sh:govbid_resolve_docker" "resolve_start" \
    "{\"path_has_docker\":$(command -v docker >/dev/null 2>&1 && echo true || echo false),\"path_has_docker_exe\":$(command -v docker.exe >/dev/null 2>&1 && echo true || echo false)}"
  # #endregion

  local candidates=()
  if command -v docker >/dev/null 2>&1; then
    candidates+=("$(command -v docker)")
  fi
  if command -v docker.exe >/dev/null 2>&1; then
    candidates+=("$(command -v docker.exe)")
  fi
  candidates+=(
    "/mnt/wsl/docker-desktop/cli-tools/usr/bin/docker"
    "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
  )

  local c chosen=""
  for c in "${candidates[@]}"; do
    # #region agent log
    local ok=false
    if _govbid_docker_candidate_ok "$c"; then ok=true; fi
    _govbid_debug_log "B" "docker.sh:govbid_resolve_docker" "candidate_tested" \
      "{\"candidate\":\"${c//\"/\\\"}\",\"ok\":$ok}"
    # #endregion
    if [[ "$ok" == true ]]; then
      chosen="$c"
      break
    fi
  done

  if [[ -z "$chosen" ]]; then
    # #region agent log
    _govbid_debug_log "C" "docker.sh:govbid_resolve_docker" "no_working_docker" "{}"
    # #endregion
    return 1
  fi

  export GOVBID_DOCKER="$chosen"
  if [[ "$chosen" == *.exe ]]; then
    export GOVBID_DOCKER_COMPOSE=("$chosen" compose)
  else
    export GOVBID_DOCKER_COMPOSE=("$chosen" compose)
  fi

  # #region agent log
  _govbid_debug_log "D" "docker.sh:govbid_resolve_docker" "chosen" \
    "{\"chosen\":\"${chosen//\"/\\\"}\"}"
  # #endregion
  echo "$chosen"
}

govbid_docker() {
  if [[ -z "${GOVBID_DOCKER:-}" ]]; then
    govbid_resolve_docker >/dev/null || return 1
  fi
  "$GOVBID_DOCKER" "$@"
}

govbid_docker_compose() {
  if [[ -z "${GOVBID_DOCKER:-}" ]]; then
    govbid_resolve_docker >/dev/null || return 1
  fi
  "${GOVBID_DOCKER_COMPOSE[@]}" "$@"
}

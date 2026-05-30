# Resolve a working Docker CLI on WSL (integration shim vs docker.exe vs desktop path).
# Source after common.sh if needed: source "$PROJECT/scripts/lib/docker.sh"

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
    if _govbid_docker_candidate_ok "$c"; then
      chosen="$c"
      break
    fi
  done

  if [[ -z "$chosen" ]]; then
    return 1
  fi

  export GOVBID_DOCKER="$chosen"
  if [[ "$chosen" == *.exe ]]; then
    export GOVBID_DOCKER_COMPOSE=("$chosen" compose)
  else
    export GOVBID_DOCKER_COMPOSE=("$chosen" compose)
  fi

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

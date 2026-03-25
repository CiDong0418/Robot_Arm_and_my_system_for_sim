#!/usr/bin/env bash
set -u -o pipefail

SCRIPT_NAME="$(basename "$0")"
ROS_SETUP_DEFAULT="/home/aiRobots/Software/devel/setup.bash"
ROS_SETUP="${ROS_SETUP:-$ROS_SETUP_DEFAULT}"

AGGRESSIVE=0
DO_CLEANUP=1
DRY_RUN=0

PATTERN='(/devel/lib/Project/ProjectNode|python3 python_publisher.py|rosrun Project ProjectNode|head_xyz_detection.py|head_xyz_test_client.py|roslaunch image multi_camera.launch)'

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [--aggressive] [--no-cleanup] [--dry-run]

Options:
  --aggressive   Also terminate matching running processes (not only suspended ones).
  --no-cleanup   Skip "rosnode cleanup".
  --dry-run      Print actions without sending signals.
  -h, --help     Show this help message.
EOF
}

log() {
  printf '[fix_stuck_ros] %s\n' "$*"
}

list_related() {
  ps -eo pid=,ppid=,stat=,cmd= | awk -v pat="$PATTERN" -v self="$$" '$0 ~ pat && $1 != self && $0 !~ /awk -v pat=/ {print}'
}

collect_pids() {
  local mode="${1:-suspended}"
  if [[ "$mode" == "suspended" ]]; then
    ps -eo pid=,stat=,cmd= | awk -v pat="$PATTERN" -v self="$$" '$2 ~ /^T/ && $0 ~ pat && $1 != self && $0 !~ /awk -v pat=/ {print $1}'
  else
    ps -eo pid=,stat=,cmd= | awk -v pat="$PATTERN" -v self="$$" '$0 ~ pat && $1 != self && $0 !~ /awk -v pat=/ {print $1}'
  fi
}

send_signal() {
  local signal_name="$1"
  shift
  local pids=("$@")

  if [[ ${#pids[@]} -eq 0 ]]; then
    return 0
  fi

  log "Sending SIG${signal_name} to: ${pids[*]}"
  if (( DRY_RUN )); then
    return 0
  fi

  kill "-${signal_name}" "${pids[@]}" 2>/dev/null || true
}

collect_alive() {
  local pid
  for pid in "$@"; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "$pid"
    fi
  done
}

for arg in "$@"; do
  case "$arg" in
    --aggressive)
      AGGRESSIVE=1
      ;;
    --no-cleanup)
      DO_CLEANUP=0
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log "Unknown option: $arg"
      usage
      exit 2
      ;;
  esac
done

if [[ -f "$ROS_SETUP" ]]; then
  log "Sourcing ROS setup: $ROS_SETUP"
  # shellcheck disable=SC1090
  source "$ROS_SETUP"
else
  log "WARN: setup file not found: $ROS_SETUP"
fi

log "Related processes (before):"
list_related || true

mapfile -t suspended_pids < <(collect_pids suspended)
if [[ ${#suspended_pids[@]} -eq 0 ]]; then
  log "No suspended matching processes found."
else
  # 這批是「曾被 Ctrl+Z 卡住」的目標，後續要確實把它們停掉
  target_pids=("${suspended_pids[@]}")

  send_signal CONT "${suspended_pids[@]}"
  sleep 0.3

  for sig in INT TERM KILL; do
    mapfile -t still_alive < <(collect_alive "${target_pids[@]}")
    if [[ ${#still_alive[@]} -eq 0 ]]; then
      break
    fi
    send_signal "$sig" "${still_alive[@]}"
    sleep 1
  done
fi

if (( AGGRESSIVE )); then
  mapfile -t running_pids < <(collect_pids all)
  if [[ ${#running_pids[@]} -gt 0 ]]; then
    log "Aggressive mode: stopping remaining matching processes."
    send_signal TERM "${running_pids[@]}"
    sleep 1

    mapfile -t after_term < <(collect_pids all)
    if [[ ${#after_term[@]} -gt 0 ]]; then
      send_signal KILL "${after_term[@]}"
      sleep 0.5
    fi
  fi
fi

if (( DO_CLEANUP )); then
  if command -v rosnode >/dev/null 2>&1; then
    if rosnode list >/dev/null 2>&1; then
      log "Running rosnode cleanup..."
      if (( DRY_RUN )); then
        log "DRY_RUN: printf 'y\\n' | rosnode cleanup"
      else
        printf 'y\n' | rosnode cleanup || true
      fi
    else
      log "WARN: rosnode list failed; skip cleanup."
    fi
  else
    log "WARN: rosnode command not found; skip cleanup."
  fi
fi

log "Related processes (after):"
list_related || true

if command -v rosnode >/dev/null 2>&1; then
  log "ROS nodes (after):"
  rosnode list || true
fi

log "Done."

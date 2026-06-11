#!/usr/bin/env bash
#
# Launch a local ComfyUI with the VibeComfy custom node AND the agent-edit
# runtime wired to the megaplan/arnold backend, ready for the text-to-graph
# agent E2E (see docs/local_agent_text_to_graph_e2e.md).
#
# Prereqs (one-time):
#   * ComfyUI checkout at $COMFYUI_DIR (default below).
#   * megaplan/arnold installed into the SAME python that runs ComfyUI:
#         pip install -e /Users/peteromalley/Documents/megaplan   # github.com/peteromallet/arnold
#   * A DeepSeek key, either exported as DEEPSEEK_API_KEY or stored in
#     ~/.hermes/.env (the VibeComfy browser credential route writes it there).
#
# Usage:
#   scripts/run_local_agent_comfy.sh            # foreground on port 8190
#   PORT=8191 scripts/run_local_agent_comfy.sh  # custom port
#
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/Users/peteromalley/Documents/reigh-workspace/vibecomfy}"
COMFYUI_DIR="${COMFYUI_DIR:-/Users/peteromalley/Documents/reigh-workspace/ComfyUI}"
PORT="${PORT:-8190}"
PYBIN="${PYBIN:-python}"

# 1. Link this checkout's comfy_nodes as a ComfyUI custom node (idempotent).
#    Guarded so a benign re-link (or two launches racing on the same link)
#    cannot abort the script under `set -e` with "File exists".
_link="${COMFYUI_DIR}/custom_nodes/vibecomfy"
_want="${REPO_ROOT}/vibecomfy/comfy_nodes"
if [[ "$(readlink "${_link}" 2>/dev/null)" != "${_want}" ]]; then
  ln -sfn "${_want}" "${_link}" || true
fi

# 2. Make the vibecomfy package importable by ComfyUI's python.
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

# 3. Point the agent runtime at the megaplan-backed adapter. Without this the
#    agent/status route reports the Arnold/Hermes runtime as unavailable.
export VIBECOMFY_ARNOLD_RUNTIME_MODULE="${VIBECOMFY_ARNOLD_RUNTIME_MODULE:-vibecomfy.comfy_nodes.agent.runtime}"

# 3a. Ensure the arnold/megaplan backend is importable. Preferred install is the
#     declared `agent` extra (pip install -e ".[agent]") or an editable dev
#     checkout (pip install -e ~/Documents/megaplan). If neither has put it on
#     the path, fall back to a local checkout via PYTHONPATH, and warn loudly
#     rather than failing late with a confusing "No module named 'megaplan'".
MEGAPLAN_DIR="${MEGAPLAN_DIR:-${HOME}/Documents/megaplan}"
if ! "${PYBIN}" -c "import megaplan" >/dev/null 2>&1; then
  if [[ -d "${MEGAPLAN_DIR}/megaplan" ]]; then
    export PYTHONPATH="${MEGAPLAN_DIR}:${PYTHONPATH}"
    echo "  note: megaplan not installed; falling back to checkout at ${MEGAPLAN_DIR}"
  else
    echo "  WARNING: arnold/megaplan backend not importable and no checkout at"
    echo "           ${MEGAPLAN_DIR}. The agent-edit route will report unavailable."
    echo "           Install it:  pip install -e \"${REPO_ROOT}[agent]\"   (or)   pip install -e <arnold-checkout>"
  fi
fi

# 4. Surface the DeepSeek key from ~/.hermes/.env into the environment if it is
#    not already exported (the adapter also reads the file directly, but
#    exporting makes the status route's credential_presence accurate).
if [[ -z "${DEEPSEEK_API_KEY:-}" && -f "${HOME}/.hermes/.env" ]]; then
  _ds_line="$(grep -E '^DEEPSEEK_API_KEY=' "${HOME}/.hermes/.env" | tail -1 || true)"
  if [[ -n "${_ds_line}" ]]; then
    export DEEPSEEK_API_KEY="${_ds_line#DEEPSEEK_API_KEY=}"
  fi
fi

echo "VibeComfy local agent ComfyUI"
echo "  repo:    ${REPO_ROOT}"
echo "  comfyui: ${COMFYUI_DIR}"
echo "  port:    ${PORT}"
echo "  runtime: ${VIBECOMFY_ARNOLD_RUNTIME_MODULE}"
echo "  deepseek key present: $([[ -n "${DEEPSEEK_API_KEY:-}" ]] && echo yes || echo no)"
echo

cd "${COMFYUI_DIR}"
exec "${PYBIN}" main.py --cpu --port "${PORT}" --enable-cors-header '*'

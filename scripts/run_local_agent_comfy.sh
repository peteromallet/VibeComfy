#!/usr/bin/env bash
#
# Launch a local ComfyUI with the VibeComfy custom node AND the agent-edit
# runtime wired to the megaplan/arnold backend, ready for the text-to-graph
# agent E2E (see docs/agent-edit/e2e-real-browser-tier.md).
#
# Prereqs (one-time):
#   * ComfyUI checkout at $COMFYUI_DIR (default below).
#   * Arnold installed into the SAME python that runs ComfyUI. This launcher
#     auto-installs the pinned GitHub package when arnold is missing or when the
#     current import resolves to a local ~/Documents/megaplan checkout:
#         pip install "arnold @ git+https://github.com/peteromallet/Arnold.git@<sha>"
#   * An OpenRouter key, either exported as OPENROUTER_API_KEY or stored in
#     ~/.hermes/.env (the VibeComfy browser credential route writes it there).
#
# Usage:
#   scripts/run_local_agent_comfy.sh            # foreground on port 8190
#   PORT=8191 scripts/run_local_agent_comfy.sh  # custom port
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
export REPO_ROOT
COMFYUI_DIR="${COMFYUI_DIR:-$(cd -- "${REPO_ROOT}/.." && pwd)/ComfyUI}"
PORT="${PORT:-8190}"
PYBIN="${PYBIN:-python}"

# Resolve a relative python binary to an absolute path now, before we cd into
# the ComfyUI directory.  If it is already absolute or not on PATH, leave it.
if [[ "${PYBIN}" != /* ]]; then
  _resolved_pybin="$(command -v "${PYBIN}" 2>/dev/null || true)"
  if [[ -n "${_resolved_pybin}" ]]; then
    PYBIN="${_resolved_pybin}"
  fi
fi

# 1. Link this checkout's comfy_nodes as a ComfyUI custom node (idempotent).
#    Guarded so a benign re-link (or two launches racing on the same link)
#    cannot abort the script under `set -e` with "File exists".
_link="${COMFYUI_DIR}/custom_nodes/vibecomfy"
_want="${REPO_ROOT}/vibecomfy/comfy_nodes"
if [[ "$(readlink "${_link}" 2>/dev/null)" != "${_want}" ]]; then
  ln -sfn "${_want}" "${_link}" || true
fi

# 1a. Build the exact content-hash frontend asset directory before ComfyUI
#     imports the custom node. The Python entry point deliberately refuses to
#     select an arbitrary older web_dist/, so a local launch must keep the
#     cache-busted dist in sync with web/.
if [[ "${VIBECOMFY_BUILD_WEB_DIST:-1}" == "1" ]]; then
  bash "${REPO_ROOT}/scripts/build_web_cache_bust.sh" --hash --force
fi

# 2. Make the vibecomfy package importable by ComfyUI's python.
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

# 3. Point the agent runtime at the megaplan-backed adapter. Without this the
#    agent/status route reports the Arnold/Hermes runtime as unavailable.
export VIBECOMFY_ARNOLD_RUNTIME_MODULE="${VIBECOMFY_ARNOLD_RUNTIME_MODULE:-vibecomfy.comfy_nodes.agent.runtime}"

# 3a. Ensure the arnold backend comes from the pinned GitHub package, not a
#     local megaplan/arnold checkout. Set VIBECOMFY_ARNOLD_AUTO_INSTALL=0 to
#     make this a warning-only check. Set VIBECOMFY_ALLOW_LOCAL_ARNOLD=1 for
#     intentional local Arnold co-development.
ARNOLD_PACKAGE_SPEC="${ARNOLD_PACKAGE_SPEC:-arnold @ git+https://github.com/peteromallet/Arnold.git@9d8b2a4af93ba764e7e82381656a8fffb3678cf7}"
_arnold_origin="$("${PYBIN}" - <<'PY' 2>/dev/null || true
import arnold
print(getattr(arnold, "__file__", "") or "")
PY
)"
_arnold_ref_ok="$("${PYBIN}" - <<'PY' 2>/dev/null || true
import importlib.metadata
try:
    direct_url = importlib.metadata.distribution("arnold").read_text("direct_url.json") or ""
except importlib.metadata.PackageNotFoundError:
    direct_url = ""
print("yes" if "9d8b2a4af93ba764e7e82381656a8fffb3678cf7" in direct_url else "no")
PY
)"
_arnold_install_reason=""
_arnold_install_flags=(--upgrade)
if [[ -z "${_arnold_origin}" ]]; then
  _arnold_install_reason="arnold is not importable"
elif [[ "${VIBECOMFY_ALLOW_LOCAL_ARNOLD:-0}" != "1" ]] && [[ "${_arnold_origin}" == "${HOME}/Documents/megaplan"* || "${_arnold_origin}" == "${HOME}/Documents/megaplan-engine"* ]]; then
  _arnold_install_reason="arnold currently imports from local checkout: ${_arnold_origin}"
  _arnold_install_flags=(--upgrade --force-reinstall --no-deps)
elif [[ "${VIBECOMFY_ALLOW_LOCAL_ARNOLD:-0}" == "1" ]] && [[ "${_arnold_origin}" == "${HOME}/Documents/megaplan"* || "${_arnold_origin}" == "${HOME}/Documents/megaplan-engine"* ]]; then
  :
elif [[ "${_arnold_ref_ok}" != "yes" ]]; then
  _arnold_install_reason="arnold is installed but not from the validated GitHub ref"
  _arnold_install_flags=(--upgrade --force-reinstall)
fi
if [[ -n "${_arnold_install_reason}" ]]; then
  if [[ "${VIBECOMFY_ARNOLD_AUTO_INSTALL:-1}" == "1" ]]; then
    echo "  note: ${_arnold_install_reason}; installing pinned Arnold from GitHub"
    "${PYBIN}" -m pip install "${_arnold_install_flags[@]}" "${ARNOLD_PACKAGE_SPEC}"
  else
    echo "  WARNING: ${_arnold_install_reason}"
    echo "           Install pinned Arnold with:"
    echo "           ${PYBIN} -m pip install ${_arnold_install_flags[*]} '${ARNOLD_PACKAGE_SPEC}'"
  fi
fi

# 4. Surface the OpenRouter key from ~/.hermes/.env into the environment if it is
#    not already exported (the adapter also reads the file directly, but
#    exporting makes the status route's credential_presence accurate).
if [[ -z "${OPENROUTER_API_KEY:-}" && -f "${HOME}/.hermes/.env" ]]; then
  _or_line="$(grep -E '^OPENROUTER_API_KEY=' "${HOME}/.hermes/.env" | tail -1 || true)"
  if [[ -n "${_or_line}" ]]; then
    export OPENROUTER_API_KEY="${_or_line#OPENROUTER_API_KEY=}"
  fi
fi

echo "VibeComfy local agent ComfyUI"
echo "  repo:    ${REPO_ROOT}"
echo "  comfyui: ${COMFYUI_DIR}"
echo "  port:    ${PORT}"
echo "  runtime: ${VIBECOMFY_ARNOLD_RUNTIME_MODULE}"
echo "  arnold:  ${ARNOLD_PACKAGE_SPEC}"
echo "  openrouter key present: $([[ -n "${OPENROUTER_API_KEY:-}" ]] && echo yes || echo no)"
echo

cd "${COMFYUI_DIR}"
exec "${PYBIN}" main.py --cpu --port "${PORT}"

#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="${script_dir}/.venv"
python_bin="${venv_dir}/bin/python"
helper_py="${script_dir}/edge_tts_read.py"

# Resolve uv (preferred) or fall back to the venv's pip.
# uv handles Python ≥3.14 where pip is no longer bundled (PEP 668).
uv_bin="$(command -v uv 2>/dev/null || true)"

if [[ ! -d "${venv_dir}" ]]; then
  if [[ -n "${uv_bin}" ]]; then
    "${uv_bin}" venv "${venv_dir}" --python "$(command -v python3)"
  else
    python3 -m venv "${venv_dir}"
  fi
fi

if [[ ! -x "${python_bin}" ]]; then
  echo "error: missing python in ${venv_dir}" >&2
  exit 1
fi

if ! "${python_bin}" - <<'PY' >/dev/null 2>&1
import edge_tts, langid
PY
then
  if [[ -n "${uv_bin}" ]]; then
    "${uv_bin}" pip install -q -p "${python_bin}" edge-tts langid
  else
    "${venv_dir}/bin/pip" install -q --upgrade pip
    "${venv_dir}/bin/pip" install -q edge-tts langid
  fi
fi

exec "${python_bin}" "${helper_py}" "$@"

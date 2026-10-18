#!/bin/bash
# Runs a runner script against the read-only Phalanx data-layer source without writing into it:
# no .pyc files (PYTHONDONTWRITEBYTECODE) and numba's on-disk cache redirected here.
# On the LinuxONE server (s390x) set PHX_PY to the conda env's python and PHX_NUMBA_SHIM=1 (proto/deploy/server.env).
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export NUMBA_CACHE_DIR="$HERE/.numba_cache"
export PHX_DATALAYER_CODE="${PHX_DATALAYER_CODE:-/Users/abishaikc/Downloads/phalanx_data_layer_preview/code}"
export PYTHONPATH="$PHX_DATALAYER_CODE/src:$HERE"
if [ "${PHX_NUMBA_SHIM:-0}" = "1" ]; then
  export PYTHONPATH="$HERE/numba_shim:$PYTHONPATH"
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
exec "${PHX_PY:-$HERE/.venv/bin/python}" "$@"

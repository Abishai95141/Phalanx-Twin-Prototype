#!/bin/zsh
# Runs a script against the read-only Phalanx data-layer source without writing into it:
# no .pyc files (PYTHONDONTWRITEBYTECODE) and numba's on-disk cache redirected here.
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export NUMBA_CACHE_DIR="$HERE/.numba_cache"
export PYTHONPATH="/Users/abishaikc/Downloads/phalanx_data_layer_preview/code/src"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
exec nice -n 10 "$HERE/.venv/bin/python" "$@"

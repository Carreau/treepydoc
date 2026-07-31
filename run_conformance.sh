#!/bin/sh
# Rebuild the parser, then diff treepydoc against numpydoc case by case.
#
# numpydoc must be importable. Point NUMPYDOC_PATH at a checkout if it is not
# installed:
#     NUMPYDOC_PATH=../numpydoc ./run_conformance.sh
set -e
root="$(cd "$(dirname "$0")" && pwd)"
cd "$root"
python3 -m pip install --quiet --force-reinstall --no-deps . >/dev/null 2>&1

if [ -n "$NUMPYDOC_PATH" ]; then
    PYTHONPATH="$(cd "$NUMPYDOC_PATH" && pwd):$PYTHONPATH"
    export PYTHONPATH
fi

# Run from elsewhere so the repo directory does not shadow the installed
# `treepydoc` package.
cd /tmp && exec python3 "$root/tools/conformance.py" "$@"

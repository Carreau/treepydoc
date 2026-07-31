"""Run numpydoc's own test suite against treepydoc's parser.

The suite is the most demanding conformance test available: it asserts on parse
results, on rendered reStructuredText, on warning text, on exception messages
and on Sphinx output, and it was written by people trying to pin down
numpydoc's behaviour rather than to be easy to pass.

Swapping the parser in is a single substitution. Every consumer -- the tests,
`docscrape_sphinx`, `validate` -- reaches the parser through the names in the
`numpydoc.docscrape` module namespace, so rebinding those names before anything
imports them is enough. In particular `docscrape_sphinx` executes
`class SphinxDocString(NumpyDocString)` at import time, so its rendering layer
rebases onto treepydoc automatically and does not need `treepydoc.sphinx` here.

Used as a pytest plugin, so that the swap happens before test collection:

    cd /path/to/numpydoc
    python3 -m pytest numpydoc/tests -p numpydoc_swap -o addopts=""

with this directory on PYTHONPATH. `tools/run_numpydoc_suite.py` wraps that up.
"""

from __future__ import annotations

import sys

# Names the suite (and numpydoc's own internals) import from
# `numpydoc.docscrape`. `Parameter` is a namedtuple and compares by value, so
# swapping it is safe.
_SWAPPED = (
    "NumpyDocString",
    "FunctionDoc",
    "ClassDoc",
    "ParseError",
    "Parameter",
    "strip_blank_lines",
    "dedent_lines",
    "indent",
    "header",
)


def install() -> list[str]:
    """Rebind numpydoc's parser names to treepydoc's. Returns what changed."""
    if "numpydoc.docscrape_sphinx" in sys.modules:
        raise RuntimeError(
            "numpydoc.docscrape_sphinx was imported before the swap; its "
            "`class SphinxDocString(NumpyDocString)` has already bound the "
            "original parser"
        )

    import numpydoc.docscrape as docscrape

    import treepydoc

    swapped = []
    for name in _SWAPPED:
        replacement = getattr(treepydoc, name, None)
        if replacement is None:
            continue
        setattr(docscrape, name, replacement)
        swapped.append(name)
    return swapped


def pytest_configure(config):
    swapped = install()
    print(f"treepydoc swapped in for: {', '.join(swapped)}", file=sys.stderr)

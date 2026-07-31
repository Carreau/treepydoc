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
    "ObjDoc",
    # `get_doc_object` binds `class_doc`/`func_doc`/`obj_doc` as *default
    # arguments*, evaluated when the module was imported. Rebinding the module
    # globals therefore does not reach them, and it would go on building
    # numpydoc's documenters around treepydoc's parser -- a half-swapped object
    # whose `_parse` and `__init__` come from different implementations.
    "get_doc_object",
    "ParseError",
    "Parameter",
    "strip_blank_lines",
    "dedent_lines",
)


def install() -> list[str]:
    """Rebind numpydoc's parser names to treepydoc's. Returns what changed."""
    for module, why in (
        (
            "numpydoc.docscrape_sphinx",
            "its `class SphinxDocString(NumpyDocString)` has already bound the "
            "original parser",
        ),
        (
            "numpydoc.validate",
            "it has already done `from .docscrape import get_doc_object`",
        ),
    ):
        if module in sys.modules:
            raise RuntimeError(f"{module} was imported before the swap; {why}")

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

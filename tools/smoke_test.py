"""Post-install smoke test: does the built wheel actually work?

Deliberately imports nothing from the source tree, so it can be run from a
scratch directory against an installed wheel and prove the packaging is right
rather than that the checkout is.

Usage:
    cd /somewhere/else && python tools/smoke_test.py
"""

from __future__ import annotations

import sys

DOC = """\
Draw samples from a distribution.

Parameters
----------
mean : (N,) ndarray
    Mean of the distribution.

Returns
-------
out : ndarray
    The drawn samples.
"""


def main() -> int:
    import treepydoc

    doc = treepydoc.NumpyDocString(DOC)

    assert doc["Summary"] == ["Draw samples from a distribution."], doc["Summary"]
    assert [p.name for p in doc["Parameters"]] == ["mean"], doc["Parameters"]
    assert doc["Parameters"][0].type == "(N,) ndarray", doc["Parameters"][0]
    assert doc["Returns"][0].name == "out", doc["Returns"]

    # The tree is the point; make sure the extension really loaded.
    tree = treepydoc.parse(DOC)
    assert not tree.root_node.has_error
    kinds = [child.type for child in tree.root_node.named_children]
    assert kinds == ["preamble", "parameters_section", "typed_section"], kinds

    print(f"treepydoc {sys.version_info.major}.{sys.version_info.minor}: ok")
    print(f"  sections   : {kinds}")
    print(f"  parameters : {doc['Parameters']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

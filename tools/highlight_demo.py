"""Run the editor pipeline outside an editor, and show what it highlights.

This does exactly what nvim does with the queries in `editors/nvim`:

1. parse a Python file with tree-sitter-python,
2. run `queries/python/injections.scm` to find the docstring regions,
3. parse each region with the numpydoc grammar,
4. run `queries/numpydoc/highlights.scm` over it,
5. run `queries/numpydoc/injections.scm` and hand the prose regions to
   tree-sitter-rst, recursively.

and then prints the docstring with each captured span labelled. It is both the
demo and the test that the queries actually compile and capture what they claim
-- including that the rst hand-off is real and not just a line in a query file.

Step 5 needs `tree-sitter-rst` installed. Without it the run still works and
reports the regions it would have handed over.

Usage:
    python3 tools/highlight_demo.py [file.py] [--color] [--tree] [--layers]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import tree_sitter
import treepydoc

REPO = Path(__file__).resolve().parent.parent
QUERY_DIR = REPO / "editors" / "nvim" / "queries"

SAMPLE = '''\
def multivariate_normal(mean, cov, shape=None):
    """Draw samples from a multivariate normal distribution.

    The multivariate normal is a generalisation of the one-dimensional
    normal distribution to higher dimensions.

    Parameters
    ----------
    mean : (N,) ndarray
        Mean of the N-dimensional distribution, as returned by
        :func:`numpy.mean`.
    cov : (N, N) ndarray
        Covariance matrix of the distribution. It must be:

        - symmetric,
        - positive-semidefinite.
    shape : tuple of ints
        Shape of the output. ``None`` draws a single sample.

    Returns
    -------
    out : ndarray
        The drawn samples.

    See Also
    --------
    normal : The one-dimensional case, see :func:`numpy.random.normal`.
    :func:`numpy.random.standard_normal`

    Notes
    -----
    Instead of specifying the full covariance matrix, popular approximations
    include diagonal and low-rank forms.

    .. math::

        f(x) = \\frac{1}{\\sqrt{2\\pi}} e^{-x^2/2}

    Examples
    --------
    >>> mean = (1, 2)
    >>> multivariate_normal(mean, [[1, 0], [0, 1]])
    array([1.2, 2.3])
    """
'''

# Rough ANSI mapping, only so the demo is legible in a terminal. A real editor
# resolves these capture names against its colour scheme.
COLORS = {
    "markup.heading": "1;36",
    "punctuation.special": "36",
    "variable.parameter": "1;33",
    "type": "32",
    "punctuation.delimiter": "90",
    "property": "35",
    "function": "1;34",
    "error": "1;31",
    "string.special": "35",
    "comment": "90",
    "markup.italic": "3",
}


def rst_language():
    """tree-sitter-rst, if this environment has it."""
    try:
        import tree_sitter_rst
    except ImportError:
        return None
    return tree_sitter.Language(tree_sitter_rst.language())


def injected_layers(region: bytes, tree) -> list[dict]:
    """Follow `queries/numpydoc/injections.scm` the way an editor would.

    Returns one entry per injected region: which language it was handed to,
    what it covers, and -- when that parser is actually installed -- the node
    types the child grammar found in it.
    """
    query = tree_sitter.Query(
        treepydoc.language(), (QUERY_DIR / "numpydoc" / "injections.scm").read_text()
    )
    captures = tree_sitter.QueryCursor(query).captures(tree.root_node)
    language = rst_language()
    parser = tree_sitter.Parser(language) if language is not None else None

    layers = []
    nodes = captures.get("injection.content", [])
    for node in sorted(nodes, key=lambda n: n.start_byte):
        entry = {
            "start": node.start_byte,
            "end": node.end_byte,
            "host": node.type,
            "text": node.text,
            "types": None,
            "error": None,
        }
        if parser is not None:
            child = parser.parse(node.text)
            entry["types"] = sorted({n.type for n in _descend(child.root_node)})
            entry["error"] = child.root_node.has_error
        layers.append(entry)
    return layers


def _descend(node):
    for child in node.children:
        if child.is_named:
            yield child
        yield from _descend(child)


def python_language() -> tree_sitter.Language:
    try:
        import tree_sitter_python
    except ImportError:  # pragma: no cover - depends on the environment
        raise SystemExit(
            "tree_sitter_python is needed for the demo: pip install tree-sitter-python"
        ) from None
    return tree_sitter.Language(tree_sitter_python.language())


def docstring_regions(source: bytes):
    """The regions nvim's injection query would hand to the numpydoc parser."""
    language = python_language()
    query = tree_sitter.Query(
        language, (QUERY_DIR / "python" / "injections.scm").read_text()
    )
    tree = tree_sitter.Parser(language).parse(source)
    captures = tree_sitter.QueryCursor(query).captures(tree.root_node)
    nodes = captures.get("injection.content", [])
    return sorted(nodes, key=lambda n: n.start_byte)


def highlight(region: bytes):
    """Return (start, end, capture) spans for one docstring region."""
    query = tree_sitter.Query(
        treepydoc.language(), (QUERY_DIR / "numpydoc" / "highlights.scm").read_text()
    )
    tree = tree_sitter.Parser(treepydoc.language()).parse(region)
    captures = tree_sitter.QueryCursor(query).captures(tree.root_node)

    spans = []
    for name, nodes in captures.items():
        for node in nodes:
            spans.append((node.start_byte, node.end_byte, name))
    # Innermost capture wins, the way an editor resolves overlaps.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    return tree, spans


def render(region: bytes, spans, color: bool) -> str:
    """Paint the region, letting later (narrower) spans win on overlap."""
    labels: list[str | None] = [None] * len(region)
    for start, end, name in spans:
        for i in range(start, min(end, len(region))):
            labels[i] = name

    out = []
    current = None
    for i, byte in enumerate(region):
        if labels[i] != current:
            if color and current is not None:
                out.append("\033[0m")
            current = labels[i]
            if color and current is not None:
                out.append(f"\033[{COLORS.get(current, '0')}m")
        out.append(chr(byte))
    if color and current is not None:
        out.append("\033[0m")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="a .py file; omit for the built-in sample")
    ap.add_argument("--color", action="store_true", help="ANSI colours")
    ap.add_argument("--tree", action="store_true", help="also dump the numpydoc tree")
    ap.add_argument(
        "--layers", action="store_true", help="show each injected rst region in full"
    )
    args = ap.parse_args()

    source = Path(args.file).read_bytes() if args.file else SAMPLE.encode()

    regions = docstring_regions(source)
    if not regions:
        print("no docstrings found")
        return 1

    print(f"{len(regions)} docstring region(s) injected\n")
    problems = 0
    for node in regions:
        region = node.text
        tree, spans = highlight(region)

        line = node.start_point[0] + 1
        print(f"{'=' * 70}\nline {line}, {len(spans)} captures")
        if tree.root_node.has_error:
            problems += 1
            print("  NOTE: the region did not parse cleanly")
        print("=" * 70)
        print(render(region, spans, args.color))

        counts: dict[str, int] = {}
        for _, _, name in spans:
            counts[name] = counts.get(name, 0) + 1
        print("\ncaptures: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

        layers = injected_layers(region, tree)
        if layers and layers[0]["types"] is None:
            print(f"\n{len(layers)} region(s) would be handed to rst "
                  "(install tree-sitter-rst to parse them)")
        elif layers:
            found = sorted({t for layer in layers for t in layer["types"]})
            broken = sum(1 for layer in layers if layer["error"])
            print(
                f"\n{len(layers)} region(s) handed to rst -> "
                f"{len(found)} node types: " + ", ".join(found)
            )
            if broken:
                problems += 1
                print(f"  NOTE: {broken} region(s) did not parse as rst")
        for layer in layers if args.layers else []:
            head = layer["text"].decode("utf-8", "replace").strip().splitlines()
            print(f"  [{layer['host']}] {head[0][:60] if head else ''!r}"
                  f" -> {', '.join(layer['types'] or ['(rst not installed)'])}")

        if args.tree:
            print("\n" + str(tree.root_node))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

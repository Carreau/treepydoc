"""Pytest suite for the treepydoc numpydoc grammar and Python API.

Run with:

    PYTHONPATH=/home/user/numpydoc python3 -m pytest tests/test_treepydoc.py -q

No network access is required: `numpydoc` is only needed (via PYTHONPATH) for
the differential conformance test, which skips itself cleanly if the package
is not importable.
"""

from __future__ import annotations

import importlib.util
import warnings
from pathlib import Path

import pytest

import tree_sitter
import treepydoc

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def _load_corpus():
    """Import tools/corpus.py without relying on package/path setup."""
    spec = importlib.util.spec_from_file_location(
        "_treepydoc_corpus", TOOLS_DIR / "corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def all_errors(node):
    """Yield every ERROR node in the subtree rooted at `node`."""
    if node.type == "ERROR":
        yield node
    for child in node.children:
        yield from all_errors(child)


def find_all(node, type_):
    """Yield every node of the given type in the subtree rooted at `node`."""
    if node.type == type_:
        yield node
    for child in node.children:
        yield from find_all(child, type_)


REPRESENTATIVE_DOC = """\
numpy.multivariate_normal(mean, cov, shape=None)

Draw values from a multivariate normal distribution.

Parameters
----------
mean : (N,) ndarray
    Mean of the N-dimensional distribution.
cov : (N, N) ndarray
    Covariance matrix of the distribution.

Returns
-------
out : ndarray
    The drawn samples.

See Also
--------
scipy.stats : other distributions
:func:`numpy.random.normal` : the 1-D analogue

Notes
-----
Some notes with *emphasis* and a doctest::

    >>> 1 + 1
    2

.. index:: random
   :refguide: random;distributions, random;gauss
"""


# ---------------------------------------------------------------------------
# parse() / tree shape
# ---------------------------------------------------------------------------


def test_parse_returns_tree_with_no_errors():
    tree = treepydoc.parse(REPRESENTATIVE_DOC)
    assert isinstance(tree, tree_sitter.Tree)
    errors = list(all_errors(tree.root_node))
    assert errors == [], f"unexpected ERROR node(s): {errors!r}"
    assert tree.root_node.type == "document"


def test_parse_dedents_like_numpydoc_init():
    indented = (
        "    Summary.\n\n    Parameters\n    ----------\n"
        "    x : int\n        Desc.\n"
    )
    tree = treepydoc.parse(indented)
    assert list(all_errors(tree.root_node)) == []
    names = list(find_all(tree.root_node, "name"))
    assert len(names) == 1
    assert names[0].text == b"x"


# ---------------------------------------------------------------------------
# NumpyDocString Mapping API
# ---------------------------------------------------------------------------


def test_mapping_keys_len_iter_getitem():
    nds = treepydoc.NumpyDocString("Summary line.\n")
    # Same keys as numpydoc.docscrape.NumpyDocString.sections.
    expected_keys = {
        "Signature", "Summary", "Extended Summary", "Parameters", "Returns",
        "Yields", "Receives", "Raises", "Warns", "Other Parameters",
        "Attributes", "Methods", "See Also", "Notes", "Warnings",
        "References", "Examples", "index",
    }
    assert set(nds) == expected_keys
    assert len(nds) == len(expected_keys)
    assert set(iter(nds)) == expected_keys
    assert nds["Summary"] == ["Summary line."]
    assert nds["Parameters"] == []
    assert nds["index"] == {}
    with pytest.raises(KeyError):
        nds["Not A Real Section"]


def test_mapping_is_a_mapping_instance():
    from collections.abc import Mapping

    nds = treepydoc.NumpyDocString("Summary.\n")
    assert isinstance(nds, Mapping)
    # Mapping mixins should work off of __getitem__/__iter__/__len__.
    assert "Parameters" in nds
    assert nds.get("Parameters") == []
    assert nds.get("Bogus", "default") == "default"


# ---------------------------------------------------------------------------
# Parameter name / type / description extraction
# ---------------------------------------------------------------------------


def test_parameter_name_type_desc():
    doc = """\
Summary.

Parameters
----------
x : int
    The x value.
y : float, optional
    The y value.
    Second line of description.
"""
    nds = treepydoc.NumpyDocString(doc)
    params = nds["Parameters"]
    assert len(params) == 2

    assert params[0].name == "x"
    assert params[0].type == "int"
    assert params[0].desc == ["The x value."]

    assert params[1].name == "y"
    assert params[1].type == "float, optional"
    assert params[1].desc == ["The y value.", "Second line of description."]


def test_parameter_type_keeps_everything_after_the_first_separator():
    """`header.split(' : ', maxsplit=1)`: only the first ` : ` splits."""
    doc = """\
Summary.

Parameters
----------
x : a : b
    Desc of x.
"""
    nds = treepydoc.NumpyDocString(doc)
    (param,) = nds["Parameters"]
    assert param.name == "x"
    assert param.type == "a : b"
    assert param.desc == ["Desc of x."]


def test_dangling_separator_is_dropped_but_addressable():
    """`header.removesuffix(" :")` on a header with no type."""
    doc = """\
Summary.

Parameters
----------
formats, names, byteorder :
    Passed through.
"""
    (param,) = treepydoc.NumpyDocString(doc)["Parameters"]
    assert param.name == "formats, names, byteorder"
    assert param.type == ""

    # The colon numpydoc drops is still addressable in the tree.
    tree = treepydoc.parse(doc)
    (dangling,) = list(find_all(tree.root_node, "dangling_separator"))
    assert dangling.text == b" :"


def test_typed_entry_single_element_is_type():
    doc = """\
Summary.

Returns
-------
out : ndarray
    The result.
int
    An anonymous return value.
"""
    nds = treepydoc.NumpyDocString(doc)
    returns = nds["Returns"]
    assert len(returns) == 2
    assert returns[0] == treepydoc.Parameter("out", "ndarray", ["The result."])
    # A header with no ' : ' is a *type* in typed sections (Returns/Yields/...).
    assert returns[1].name == ""
    assert returns[1].type == "int"
    assert returns[1].desc == ["An anonymous return value."]


# ---------------------------------------------------------------------------
# See Also: roles, plain targets, multi-line descriptions
# ---------------------------------------------------------------------------


def test_see_also_roles_and_multiline_description():
    doc = """\
Summary.

See Also
--------
func_a, func_b
foo.func_e : some other func over
         multiple lines
:meth:`func_h` : a method
"""
    nds = treepydoc.NumpyDocString(doc)
    see_also = nds["See Also"]
    assert see_also[0] == ([("func_a", None), ("func_b", None)], [])
    assert see_also[1] == (
        [("foo.func_e", None)],
        ["some other func over", "multiple lines"],
    )
    assert see_also[2] == ([("func_h", "meth")], ["a method"])


def test_see_also_trailing_comma_warns_not_raises():
    doc = """\
z(x,theta)

See Also
--------
func_f2, func_g2, :meth:`func_h2`, func_j2, : description of multiple
"""
    with pytest.warns(UserWarning):
        nds = treepydoc.NumpyDocString(doc)
    (item,) = nds["See Also"]
    funcs, desc = item
    assert funcs[-1] == ("func_j2", None)
    assert desc == ["description of multiple"]


# ---------------------------------------------------------------------------
# .. index:: parsing
# ---------------------------------------------------------------------------


def test_index_section():
    doc = """\
Summary.

.. index:: random
   :refguide: random;distributions, random;gauss
"""
    nds = treepydoc.NumpyDocString(doc)
    assert nds["index"] == {
        "default": "random",
        "refguide": ["random;distributions", "random;gauss"],
    }


# ---------------------------------------------------------------------------
# Errors and warnings
# ---------------------------------------------------------------------------


def test_returns_and_yields_is_allowed():
    doc = """\
Test.

Returns
-------
int
    a

Yields
------
a : int
    b
"""
    # numpydoc 1.10 dropped this check; both sections now parse.
    nds = treepydoc.NumpyDocString(doc)
    assert nds["Returns"] and nds["Yields"]


def test_receives_without_yields_raises_value_error():
    doc = """\
Test.

Receives
--------
a : int
    b
"""
    with pytest.raises(ValueError, match="Receives section but not Yields"):
        treepydoc.NumpyDocString(doc)


def test_duplicate_section_raises_value_error():
    doc = """\
Test having a section Notes twice

Notes
-----
See the next note for more information

Notes
-----
That should break...
"""
    with pytest.raises(ValueError, match="Notes.*appears twice"):
        treepydoc.NumpyDocString(doc)


def test_see_also_parse_error():
    doc = """\
z(x,theta)

See Also
--------
:func:`~foo`
"""
    # 1.10 reports this through `_error_location`, so it is a ValueError now;
    # `ParseError` still exists but nothing raises it.
    with pytest.raises(ValueError, match="Error parsing See Also entry"):
        treepydoc.NumpyDocString(doc)


def test_unknown_section_warns():
    doc = """\
Test having an unknown section

Mope
----
This should be ignored and warned about
"""
    with pytest.warns(UserWarning, match="Unknown section Mope"):
        nds = treepydoc.NumpyDocString(doc)
    # Unknown sections do not show up under any known key.
    assert nds["Notes"] == []


# ---------------------------------------------------------------------------
# Node byte ranges map back to the source
# ---------------------------------------------------------------------------


def test_parameter_name_node_byte_range_maps_to_source():
    doc = """\
Summary.

Parameters
----------
alpha : int
    The alpha value.
"""
    tree = treepydoc.parse(doc)
    encoded = doc.encode("utf-8")
    (name_node,) = list(find_all(tree.root_node, "name"))
    assert name_node.text == b"alpha"
    assert encoded[name_node.start_byte:name_node.end_byte] == b"alpha"

    (type_node,) = list(find_all(tree.root_node, "type"))
    assert type_node.text == b"int"
    assert encoded[type_node.start_byte:type_node.end_byte] == b"int"

    # And the ranges are disjoint / ordered as expected.
    assert name_node.end_byte <= type_node.start_byte


def test_multiple_parameter_names_map_to_correct_offsets():
    doc = """\
Summary.

Parameters
----------
first : int
    Desc.
second : str
    Desc.
"""
    encoded = doc.encode("utf-8")
    tree = treepydoc.parse(doc)
    names = list(find_all(tree.root_node, "name"))
    assert [n.text for n in names] == [b"first", b"second"]
    for node in names:
        text = encoded[node.start_byte:node.end_byte].decode("utf-8")
        assert text == node.text.decode("utf-8")
        # start_point/end_point line numbers agree with byte offsets.
        line = doc.splitlines()[node.start_point[0]]
        assert text in line


# ---------------------------------------------------------------------------
# Differential test against numpydoc.docscrape.NumpyDocString
#
# `tools/corpus.py` has no numpydoc dependency itself, so it is always safe
# to import for the parametrize list; only the comparison inside each test
# needs numpydoc, so `pytest.importorskip` there skips just these tests (not
# the whole module) when numpydoc is not on the path.
# ---------------------------------------------------------------------------

corpus = _load_corpus()


def _normalise(value):
    """Make the two implementations' values structurally comparable."""
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_normalise(v) for v in value)
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    return value


@pytest.mark.parametrize("name,text", corpus.CORPUS, ids=[c[0] for c in corpus.CORPUS])
def test_matches_numpydoc_docscrape(name, text):
    docscrape = pytest.importorskip("numpydoc.docscrape")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = docscrape.NumpyDocString(text)
        actual = treepydoc.NumpyDocString(text)

    for key in docscrape.NumpyDocString.sections:
        want = _normalise(expected[key])
        got = _normalise(actual[key])
        assert got == want, f"mismatch in section {key!r} for corpus case {name!r}"


@pytest.mark.parametrize(
    "name,text,exc_name",
    corpus.RAISING_CORPUS,
    ids=[c[0] for c in corpus.RAISING_CORPUS],
)
def test_matches_numpydoc_docscrape_raising(name, text, exc_name):
    pytest.importorskip("numpydoc.docscrape")

    exc_map = {"ValueError": ValueError, "ParseError": treepydoc.ParseError}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(exc_map[exc_name]):
            treepydoc.NumpyDocString(text)


# ---------------------------------------------------------------- incremental


def test_incremental_reparse_matches_a_fresh_parse():
    """An edited tree must equal what a from-scratch parse would produce.

    This is the property the external scanner's serialized state exists to
    preserve: `after_blank`, `header_end` and the end-of-input guards all have
    to survive being saved and restored mid-document.
    """
    source = (
        b"Summary.\n\nParameters\n----------\n"
        b"x : int\n    A thing.\ny : str\n    Another.\n\n"
        b"Notes\n-----\nSome notes.\n"
    )
    parser = tree_sitter.Parser(treepydoc.language())
    tree = parser.parse(source)
    assert not list(all_errors(tree.root_node))

    old, new = b"A thing.", b"A bigger thing."
    start = source.index(old)
    edited = source[:start] + new + source[start + len(old) :]

    tree.edit(
        start_byte=start,
        old_end_byte=start + len(old),
        new_end_byte=start + len(new),
        start_point=(5, 4),
        old_end_point=(5, 4 + len(old)),
        new_end_point=(5, 4 + len(new)),
    )
    reparsed = parser.parse(edited, tree)
    fresh = tree_sitter.Parser(treepydoc.language()).parse(edited)

    assert str(reparsed.root_node) == str(fresh.root_node)
    assert not list(all_errors(reparsed.root_node))


# ----------------------------------------------------- numpydoc object API


class _Sample:
    """A sample class.

    Parameters
    ----------
    x : int
        A thing.

    See Also
    --------
    other : Something else.

    Notes
    -----
    Note text.
    """

    attribute = 1

    def method(self, a):
        """Do a thing.

        Parameters
        ----------
        a : str
            The a.

        Returns
        -------
        int
            The result.
        """


def _sample_function(x):
    """Compute something.

    Parameters
    ----------
    x : int
        In.

    Returns
    -------
    out : int
        Out.
    """


def test_function_doc_and_class_doc_exist():
    assert treepydoc.FunctionDoc(_sample_function)["Parameters"][0].name == "x"
    assert treepydoc.ClassDoc(_Sample)["Parameters"][0].name == "x"
    assert treepydoc.ObjDoc(object(), "Summary.\n")["Summary"] == ["Summary."]


def test_get_doc_object_dispatches_on_kind():
    assert isinstance(treepydoc.get_doc_object(_Sample), treepydoc.ClassDoc)
    assert isinstance(treepydoc.get_doc_object(_sample_function), treepydoc.FunctionDoc)
    assert isinstance(treepydoc.get_doc_object(42, doc="Doc.\n"), treepydoc.ObjDoc)


def test_str_round_trip_matches_numpydoc():
    r"""Reparsing rendered output must behave the same in both implementations.

    It is not always parseable: with no `func_role`, `_str_see_also` renders a
    target as ``\`scipy.stats\`_``, and backticks are not in the character class
    See Also accepts, so numpydoc cannot read back what it just wrote. What
    matters here is that treepydoc fails in exactly the same place.
    """
    docscrape = pytest.importorskip("numpydoc.docscrape")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rendered = str(treepydoc.NumpyDocString(REPRESENTATIVE_DOC))
        assert rendered == str(docscrape.NumpyDocString(REPRESENTATIVE_DOC))

        try:
            expected = dict(docscrape.NumpyDocString(rendered))
        except ValueError as exc:
            with pytest.raises(ValueError) as caught:
                treepydoc.NumpyDocString(rendered)
            assert caught.value.args[0] == exc.args[0]
        else:
            assert dict(treepydoc.NumpyDocString(rendered)) == expected


def test_str_round_trip_is_reparseable_without_see_also():
    """Without the See Also rendering wart, rendering does round-trip."""
    doc = treepydoc.NumpyDocString(
        "Summary.\n\nParameters\n----------\nx : int\n    A thing.\n"
    )
    again = treepydoc.NumpyDocString(str(doc))
    assert again["Parameters"] == doc["Parameters"]


@pytest.mark.parametrize("name,text", _load_corpus().CORPUS)
def test_str_rendering_matches_numpydoc(name, text):
    docscrape = pytest.importorskip("numpydoc.docscrape")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert str(treepydoc.NumpyDocString(text)) == str(
            docscrape.NumpyDocString(text)
        )


@pytest.mark.parametrize("kind", ["function", "class"])
def test_object_doc_rendering_matches_numpydoc(kind):
    docscrape = pytest.importorskip("numpydoc.docscrape")
    obj = _sample_function if kind == "function" else _Sample
    cls = "FunctionDoc" if kind == "function" else "ClassDoc"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert str(getattr(treepydoc, cls)(obj)) == str(getattr(docscrape, cls)(obj))


# ------------------------------------------------------------ sphinx layer


def test_sphinx_extension_renders_like_numpydoc():
    """The Sphinx layer must be swap-in: same directives, same text."""
    numpydoc_sphinx = pytest.importorskip("numpydoc.docscrape_sphinx")
    from treepydoc import sphinx as treepydoc_sphinx

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for obj, ours, theirs in (
            (
                _sample_function,
                treepydoc_sphinx.SphinxFunctionDoc,
                numpydoc_sphinx.SphinxFunctionDoc,
            ),
            (_Sample, treepydoc_sphinx.SphinxClassDoc, numpydoc_sphinx.SphinxClassDoc),
        ):
            assert str(ours(obj)) == str(theirs(obj))

        assert str(treepydoc_sphinx.SphinxDocString(REPRESENTATIVE_DOC)) == str(
            numpydoc_sphinx.SphinxDocString(REPRESENTATIVE_DOC)
        )


def test_sphinx_setup_uses_numpydocs_extension_point():
    """`setup` must go through numpydoc's hook rather than patching anything."""
    pytest.importorskip("numpydoc.numpydoc")
    from numpydoc import numpydoc as numpydoc_ext

    from treepydoc import sphinx as treepydoc_sphinx

    class FakeApp:
        def __init__(self):
            self.connected = []

        def add_config_value(self, *args, **kwargs):
            pass

        def setup_extension(self, name):
            pass

        def connect(self, event, handler):
            self.connected.append(event)

        def add_domain(self, *args, **kwargs):
            pass

        def add_directive(self, *args, **kwargs):
            pass

    app = FakeApp()
    treepydoc_sphinx.setup(app)
    assert "autodoc-process-docstring" in app.connected
    # numpydoc's module global is what mangle_docstrings actually calls.
    assert numpydoc_ext.get_doc_object is treepydoc_sphinx.get_doc_object


# ------------------------------------------------------------ editor queries


EDITOR_QUERIES = Path(__file__).resolve().parent.parent / "editors" / "nvim" / "queries"


@pytest.mark.parametrize("name", ["highlights.scm", "injections.scm"])
def test_numpydoc_queries_compile(name):
    """A broken query silently stops highlighting, so compile them in CI."""
    source = (EDITOR_QUERIES / "numpydoc" / name).read_text()
    tree_sitter.Query(treepydoc.language(), source)


def test_python_injection_finds_docstrings():
    """The injection must capture docstrings, and only docstrings."""
    tree_sitter_python = pytest.importorskip("tree_sitter_python")

    language = tree_sitter.Language(tree_sitter_python.language())
    query = tree_sitter.Query(
        language, (EDITOR_QUERIES / "python" / "injections.scm").read_text()
    )
    source = (
        b'"""Module doc."""\n'
        b'x = "not a docstring"\n'
        b"class C:\n"
        b'    """Class doc."""\n'
        b"    def m(self):\n"
        b'        """Method doc."""\n'
        b'        y = "also not a docstring"\n'
    )
    tree = tree_sitter.Parser(language).parse(source)
    captured = tree_sitter.QueryCursor(query).captures(tree.root_node)
    texts = sorted(n.text.decode() for n in captured["injection.content"])
    assert texts == ["Class doc.", "Method doc.", "Module doc."]


def test_highlights_capture_section_headings():
    """The captures the editor doc promises must actually fire."""
    query = tree_sitter.Query(
        treepydoc.language(),
        (EDITOR_QUERIES / "numpydoc" / "highlights.scm").read_text(),
    )
    tree = treepydoc.parse(REPRESENTATIVE_DOC)
    captured = tree_sitter.QueryCursor(query).captures(tree.root_node)

    headings = {n.text.decode() for n in captured.get("markup.heading", [])}
    assert {"Parameters", "Returns", "See Also", "Notes"} <= headings
    assert {n.text.decode() for n in captured.get("variable.parameter", [])} >= {"mean"}


# ---------------------------------------------------------------------------
# The playground's seeded sample
#
# `tools/playground.py` bakes a docstring into the exported page, and its
# comment claims that docstring exercises specific nodes. Both halves of that
# claim are checkable here, so the sample cannot rot into something that
# renders an ERROR the moment anyone opens the playground.
# ---------------------------------------------------------------------------


def _load_playground():
    spec = importlib.util.spec_from_file_location(
        "_treepydoc_playground", TOOLS_DIR / "playground.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_playground_sample_parses_cleanly():
    tree = treepydoc.parse(_load_playground().SAMPLE)
    assert not list(all_errors(tree.root_node))


def test_playground_sample_exercises_the_interesting_nodes():
    """The nodes tools/playground.py says the sample is there to show."""
    tree = treepydoc.parse(_load_playground().SAMPLE)
    for node_type in (
        "signature",
        "extended_summary",
        "parameters_section",
        "typed_section",
        "dangling_separator",
        "role",
        "index_marker",
    ):
        found = list(find_all(tree.root_node, node_type))
        assert found, f"no {node_type} in the sample"


def test_playground_sample_matches_numpydoc():
    docscrape = pytest.importorskip("numpydoc.docscrape")
    sample = _load_playground().SAMPLE

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = docscrape.NumpyDocString(sample)
        actual = treepydoc.NumpyDocString(sample)

    for key in docscrape.NumpyDocString.sections:
        want = _normalise(expected[key])
        assert _normalise(actual[key]) == want, f"mismatch in {key!r}"

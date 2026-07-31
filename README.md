# treepydoc

A [tree-sitter](https://tree-sitter.github.io) grammar and parser for
[numpydoc](https://numpydoc.readthedocs.io) docstrings.

It is a **drop-in replacement** for `numpydoc.docscrape.NumpyDocString` — same
keys, same values, same warnings, same exceptions — that happens to be backed by
a syntax tree, so every piece of the result can be traced back to a byte range.

```python
>>> import treepydoc
>>> doc = treepydoc.NumpyDocString('''
... Draw samples from a distribution.
...
... Parameters
... ----------
... mean : (N,) ndarray
...     Mean of the distribution.
... ''')
>>> doc['Parameters']
[Parameter(name='mean', type='(N,) ndarray', desc=['Mean of the distribution.'])]
>>> doc.tree.root_node.children[1].type
'parameters_section'
```

## Conformance

The whole point is behavioural equivalence, so it is measured rather than
asserted:

| Suite | Result |
| --- | --- |
| numpydoc's own `test_docscrape.py` docstrings + 33 edge cases | **82 / 82 identical** |
| every public docstring in numpy, scipy and pandas | **9904 / 9904 identical** |
| 10 900 mutation-fuzzed docstrings, 3 seeds | **0 disagreements**, no hangs |

Both suites compare the complete mapping, all 18 keys, down to the exact
list-of-lines representation of every description.

```sh
./run_conformance.sh                 # curated corpus
python3 tools/sweep.py               # numpy + scipy + pandas
python3 tools/fuzz.py                # corrupt real docstrings, compare again
```

Equivalence includes the bugs. `numpydoc` truncates
`x : dict of {str : int}` to a type of `dict of {str`, and so does this. See
[DESIGN.md](DESIGN.md) for the full list of reproduced warts and why each one is
worth questioning.

## Why a tree

- **Positions.** Names, types, section titles and See Also targets all carry
  byte ranges. `NumpyDocString` returns bare strings with no provenance.
- **Recoverable errors.** A malformed See Also entry becomes one `ERROR` node
  instead of an exception that discards the whole docstring.
- **Diagnosable warts.** The text numpydoc's `split(' : ')[:2]` silently drops is
  kept as a `discarded` node, so an editor can underline it.
- **Incremental reparsing**, and **injection** of `tree-sitter-rst` into the
  prose sections so `Notes` and `Examples` highlight as real reStructuredText.

## Layout

```
grammar.js              the grammar
src/scanner.c           external scanner: numpydoc's predicates, in C
treepydoc/              the NumpyDocString-compatible Python API
bindings/python/        the low-level tree-sitter binding
queries/                highlights, injections, diagnostics
test/corpus/            tree-sitter corpus tests
tests/                  pytest suite
tools/corpus.py         the curated docstring corpus
tools/conformance.py    differential test against numpydoc
tools/sweep.py          differential test over installed packages
tools/fuzz.py           mutation fuzzer, same comparison on corrupted input
```

## Building

```sh
npm install                 # tree-sitter CLI
npx tree-sitter generate    # regenerate src/parser.c from grammar.js
npx tree-sitter test        # corpus tests
python3 -m pip install .    # build the Python extension and API
```

Running the differential tests needs `numpydoc` importable:

```sh
PYTHONPATH=/path/to/numpydoc python3 tools/conformance.py
```

## Input contract

`NumpyDocString.__init__` runs `textwrap.dedent` over the docstring before
parsing, and then treats column 0 as the structural anchor. The grammar inherits
that contract: it parses dedented text, and `treepydoc.parse()` applies the
dedent for you. Tree positions therefore refer to the dedented string rather
than the original — see [DESIGN.md](DESIGN.md) §1.

## License

MIT. The external scanner's approach — indent-aware line scanning and zero-width
lookahead guards — is adapted from
[tree-sitter-rst](https://github.com/stsewd/tree-sitter-rst), Copyright (c) 2020
Santos Gallegos, MIT License.

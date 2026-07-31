# treepydoc

[![CI](https://github.com/carreau/treepydoc/actions/workflows/ci.yml/badge.svg)](https://github.com/carreau/treepydoc/actions/workflows/ci.yml)

A [tree-sitter](https://tree-sitter.github.io) grammar and parser for
[numpydoc](https://numpydoc.readthedocs.io) docstrings.

It is a **drop-in replacement** for `numpydoc.docscrape.NumpyDocString` — same
keys, same values, same warnings, same exceptions — that happens to be backed by
a syntax tree, so every piece of the result can be traced back to a byte range.

Targets **numpydoc >= 1.10**. Older releases are not supported.

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
| numpydoc's own `test_docscrape.py` docstrings + edge cases | **93 / 93 identical** |
| every public docstring in numpy, scipy and pandas | **9907 / 9907 identical** |
| 10 900 mutation-fuzzed docstrings, 3 seeds | **0 disagreements**, no hangs |
| a full Sphinx build of numpydoc's `tinybuild` | **6 / 6 pages byte-identical** |
| **numpydoc's own test suite, run on this parser** | **identical: same 271 pass, same 9 fail** |

Both suites compare the complete mapping, all 18 keys, down to the exact
list-of-lines representation of every description.

```sh
./run_conformance.sh                 # curated corpus
python3 tools/sweep.py               # numpy + scipy + pandas
python3 tools/fuzz.py                # corrupt real docstrings, compare again
python3 tools/sphinx_compare.py      # build tinybuild both ways, diff the HTML
python3 tools/run_numpydoc_suite.py  # numpydoc's own tests, both parsers
```

These run against whichever numpydoc is installed; pin it, because treepydoc is
answer-for-answer identical to a *version* of numpydoc and a different one will
report its own changes as failures — see [PLAN.md](PLAN.md) §0.

Equivalence includes the bugs. `numpydoc` still reads the type in `x :  int` as
`' int'`, space included, and still turns a section with an empty body into one
blank parameter — and so does this. See [DESIGN.md](DESIGN.md) for the full list
of reproduced warts and why each one is worth questioning.

### numpydoc's own test suite

The strongest available check, because that suite was written to pin numpydoc's
behaviour down rather than to be easy to pass — it asserts on parse results,
rendered reStructuredText, warning text, exception messages and Sphinx output.
`tools/numpydoc_swap.py` rebinds the names in `numpydoc.docscrape` and runs it:

```
  numpydoc  : 9 failed, 271 passed, 2 xfailed
  treepydoc : 9 failed, 271 passed, 2 xfailed

Identical: the same 9 tests fail and the same tests pass, either way.
```

The 9 are pre-existing for that release in this environment. The failing sets
match test-for-test, so the bar is "same tests, same outcome", not "everything
green".

That the swap is a single rebinding is not an accident of packaging: every
consumer, including `docscrape_sphinx` and `validate`, reaches the parser
through the `numpydoc.docscrape` module namespace. `docscrape_sphinx` runs
`class SphinxDocString(NumpyDocString)` at import time, so its rendering layer
rebases automatically.

## Using it with Sphinx

`treepydoc.sphinx` is a Sphinx extension that swaps the parser and changes
nothing else — every `numpydoc_*` config value, the templates and the emitted
reStructuredText stay as they were:

```python
extensions = ["treepydoc.sphinx"]   # instead of "numpydoc"
```

It goes through `numpydoc.numpydoc.setup(app, get_doc_object_=...)`, which is a
documented extension point, so nothing is monkeypatched. numpydoc's Sphinx
classes are *rendering* — they subclass `NumpyDocString` and override the
`_str_*` methods — so that rendering is reused as-is and only the parse
underneath changes. `tools/sphinx_compare.py` builds numpydoc's own tinybuild
project both ways and byte-compares the generated HTML.

The plain object API matches too, for callers that use it directly:
`FunctionDoc`, `ClassDoc`, `ObjDoc`, `get_doc_object`, and the full set of
`_str_*` rendering methods.

## Why a tree

- **Positions.** Names, types, section titles and See Also targets all carry
  byte ranges. `NumpyDocString` returns bare strings with no provenance.
- **Recoverable errors.** A malformed See Also entry becomes one `ERROR` node
  instead of an exception that discards the whole docstring.
- **Diagnosable warts.** The ` :` that `header.removesuffix(" :")` silently
  drops is kept as a `dangling_separator` node, so an editor can underline it.
- **Incremental reparsing**, and **injection** of `tree-sitter-rst` into the
  prose sections so `Notes` and `Examples` highlight as real reStructuredText.

## Editor support

[`editors/README.md`](editors/README.md) has a complete Neovim setup: build the
parser, install the queries, and an injection that hands Python docstrings to
this grammar. `python3 tools/highlight_demo.py --color` runs the same pipeline
outside an editor so you can see what it highlights.

Indentation is handled: numpydoc 1.10 dedents each section body before reading
entries out of it, so a docstring lifted straight out of a source file — still
indented to its function — parses exactly like a dedented one. That was a real
limitation against older numpydoc and is not one any more.

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
tools/sphinx_compare.py end-to-end Sphinx build diff
tools/numpydoc_swap.py  pytest plugin that swaps the parser in
tools/run_numpydoc_suite.py  runs numpydoc's tests both ways and diffs
tools/smoke_test.py     post-install check, imports nothing from the tree
tools/highlight_demo.py runs the editor pipeline outside an editor
editors/                Neovim queries and setup
CMakeLists.txt          builds the extension; no setup.py
.github/workflows/      CI: grammar, build, conformance, differential, lint, package
treepydoc/sphinx.py     the Sphinx extension
```

## Building

Packaging is [scikit-build-core](https://scikit-build-core.readthedocs.io) over
CMake, declared entirely in `pyproject.toml` — there is no `setup.py`. The
extension is built against the stable ABI, so one `cp39-abi3` wheel per platform
covers every supported Python.

```sh
npm install                 # tree-sitter CLI, pinned exactly
npx tree-sitter generate    # regenerate src/parser.c from grammar.js
npx tree-sitter test        # corpus tests
python3 -m pip install .    # build the extension and the Python API
python3 -m build            # sdist + abi3 wheel into dist/
```

`src/parser.c` is committed, and CI regenerates it and fails on any diff — so
the CLI version is pinned exactly, since a different one can emit a different
parse table for the same grammar.

## Linting

Everything is checked, and the linter versions are pinned in `pyproject.toml`
under `[dependency-groups] lint` so a new release cannot turn CI red on an
unchanged tree:

| Tool | What it covers |
| --- | --- |
| `ruff` | Python |
| `mypy` | Python types |
| `codespell` | prose in every file |
| `shellcheck` | `run_conformance.sh` |
| `clang-format` | `src/scanner.c` (Google style; `src/parser.c` is generated and exempt) |
| `clang-tidy` | the scanner, `--warnings-as-errors='*'` |
| `gcc -Wall -Wextra -Werror` | the scanner again, with a second front end |
| `actionlint` | the workflows, including shellcheck over every `run:` block |
| `zizmor` | the workflows' supply chain and permissions, at `--persona=pedantic` |

Actions are pinned to commit SHAs, checkouts do not persist credentials, and the
workflow token is `contents: read`.

Running the differential tests needs `numpydoc` importable:

```sh
PYTHONPATH=/path/to/numpydoc python3 tools/conformance.py
```

## Input contract

`NumpyDocString.__init__` runs `textwrap.dedent` over the docstring, and
`_parse_param_list` then dedents each section body again. The grammar inherits
both: `treepydoc.parse()` applies the outer dedent, and the scanner works out
each section's own margin. Tree positions therefore refer to the dedented string
rather than the original — see [DESIGN.md](DESIGN.md) §1.

## What's next

[PLAN.md](PLAN.md). The headline item: equivalence is pinned to one numpydoc
release by convention rather than by construction, and CI should test against
numpydoc `main` too so upstream changes show up as a signal rather than a
surprise.

## License

MIT. The external scanner's approach — indent-aware line scanning and zero-width
lookahead guards — is adapted from
[tree-sitter-rst](https://github.com/stsewd/tree-sitter-rst), Copyright (c) 2020
Santos Gallegos, MIT License.

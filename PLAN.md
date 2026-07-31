# Plan

Where treepydoc stands, and what is worth doing next. Ordered by value, with
the reasoning kept short enough to disagree with.

Current state: parse-identical to numpydoc at commit `4e7c5ad` across 82
curated cases, 9904 real docstrings and ~10 900 fuzzed ones; render-identical
through `str()`, through `SphinxDocString`, and through a full Sphinx build of
numpydoc's own `tinybuild` project (6/6 generated pages byte-identical).
numpydoc's own test suite runs on it with the same 113 passing and the same 44
failing, test-for-test.

---

## 0. The problem that outranks everything else

**treepydoc is bug-compatible with a *version* of numpydoc, and that version is
about to move.**

This is not hypothetical: while writing the upstream fixes in this same
session, `numpydoc/docscrape.py` changed under the conformance suite and cases
started "failing" that were really upstream getting *better*. The suite now
pins `NUMPYDOC_PATH` to a specific commit, which papers over it.

The cost is measured, not guessed. Against the four fixes on the numpydoc
branch:

| Suite | vs `4e7c5ad` | vs patched |
| --- | --- | --- |
| curated corpus | 82 / 82 | 78 / 82 |
| numpy + scipy + pandas | 9904 / 9904 | 9888 / 9904 |
| numpydoc's own suite | identical | 3 newly failing |

The three are `test_parameter_header_with_multiple_colons`,
`test_parameter_header_whitespace_is_stripped` and
`test_short_underline_warning` — that is, exactly the tests written to pin the
new behaviour. Nothing else moves. numpydoc's suite has effectively become the
specification for what a `compat` switch has to cover.

Every one of those 4 + 16 differences is treepydoc faithfully reproducing a bug
that upstream has now fixed — two headers containing ` : ` and two with stray
whitespace. None of them need a grammar change.

The fix is to make bug-compatibility a choice rather than an accident:

```python
treepydoc.NumpyDocString(text, compat="0.9")   # reproduce the old truncation
treepydoc.NumpyDocString(text)                 # do the right thing
```

Concretely, the divergences that a `compat` flag would gate are all in the
Python layer, not the grammar — the tree already carries what is needed:

| Behaviour | `compat="0.9"` | default |
| --- | --- | --- |
| `x : a : b` | type `a`, `b` discarded | type `a : b` (the `discarded` node folds back in) |
| `x :  int` | type `' int'` | type `'int'` |
| too-short underline | silently prose | warning, still prose |
| unknown section | warn, drop body | warn, keep body |

That the grammar needs no changes for any of these — the `discarded` node
already holds the truncated text, and the token boundaries already sit where
`strip()` would put them — is the strongest evidence that separating parse from
interpretation was the right call. **Do this first**; everything below is
easier once the compatibility target is explicit.

---

## 1. Positions that point at the user's source

Today `parse()` dedents first, so every byte range refers to the dedented
string. For the API that is invisible; for an editor or a linter it is the whole
point, and it makes the tree unusable for the one job it is best at.

`textwrap.dedent` removes a constant prefix from every non-blank line, so the
map back is a per-line integer. Build it in `_Source`, expose
`node_range_in_original(node)`, and have `parse()` return the map alongside the
tree.

This also unblocks a `numpydoc.validate` replacement (§3).

## 2. Editor integration

The grammar exists; nothing consumes it yet.

- **Injection from the Python side.** A `tree-sitter-python` injection that
  hands docstring string literals to this grammar is what makes it useful in an
  editor at all. That needs §1, because the injected region is indented.
- **Ship the queries.** `queries/highlights.scm` and `injections.scm` are
  written but not packaged for nvim-treesitter or Helix.
- **A diagnostics pass.** `queries/diagnostics.scm` already captures the
  `discarded` node and `ERROR`s. Two more are worth adding once §0 lands: the
  too-short underline, and a section title that is one edit away from a known
  name (`Retruns`, `Parmeters`) — currently a silent documentation deletion.

## 3. Replace `numpydoc.validate`

`numpydoc/validate.py` re-derives line numbers heuristically because
`NumpyDocString` throws away provenance. With §1 done, every check it performs
could point at an exact range instead. That is a visible quality win for
`numpydoc lint` users and the most concrete argument for the tree upstream.

## 4. Grammar coverage gaps

Small, well-understood, each with a known reproducer:

- **Line-length limit.** Lines over 4096 code points are not classified as
  section titles or signatures. Parameter headers of any length split correctly
  (that was fixed), but the cap should be lifted or grown dynamically.
- **Non-ASCII `\w`.** The scanner folds every non-ASCII code point to one
  placeholder byte, so it cannot tell a Unicode letter from a Unicode symbol.
  Only reachable through a non-ASCII Sphinx role name. Fixable by carrying a
  small class tag per code point instead of a single placeholder.
- **`Signature` node.** The signature is currently a run of lines; the
  parameter list inside it is not parsed. Splitting it would let
  `mangle_signature` stop re-deriving it with a regex.

## 5. Performance

Never measured beyond "fast enough": the sweep parses 9904 docstrings in a few
seconds. Before claiming anything, benchmark against `NumpyDocString` on the
same corpus. The interesting number is not throughput but the incremental
reparse, which is the only thing tree-sitter offers that a rewrite in Python
could not.

## 6. Packaging

- Wheels. The extension builds from source today; `cibuildwheel` config and an
  abi3 target would make it installable.
- A Rust/Node binding. `tree-sitter.json` declares only C and Python.
- CI running all five suites (corpus, pytest, conformance, sweep, fuzz) plus
  `sphinx_compare.py`. The sweep needs numpy/scipy/pandas, so it should be a
  separate, slower job.

---

## Upstream fixes to numpydoc

Being able to diff a second implementation against the reference makes some of
numpydoc's behaviour easy to characterise precisely. The fixes being prepared on
the numpydoc branch, in descending order of confidence:

1. **`split(' : ')[:2]` → `maxsplit=1`.** Truncates any type containing ` : `;
   `d : dict of {str : int}` documents `d` as `dict of {str`. Unambiguous bug,
   no test pins the old behaviour.
2. **Strip the fields after the split.** `x :  int` yields the type `' int'`,
   so the same parameter written with an extra space compares unequal to
   itself.
3. **`yield StopIteration`.** `_read_sections` yields the exception *class* as
   if it were a `(name, content)` pair; any consumer that unpacks it raises
   `TypeError`. A PEP 479 migration leftover.
4. **Warn on a too-short section underline.** The most common numpydoc typo
   deletes a whole section with no error and no warning. Warning only — no
   change to what parses. Validated against 9917 real docstrings: **2
   warnings, both true positives** — `scipy.stats.matrix_t_gen.logpdf` loses
   its `Examples` section and `pandas.core.groupby.Grouping` loses its
   `Attributes` section, each to an underline three characters short. Zero
   false positives.

Deliberately **not** attempted, and why:

- **`textwrap.dedent` → `inspect.cleandoc`.** This is the worst of the bugs
  (§2.1 of DESIGN.md — a docstring passed directly to `NumpyDocString` loses
  every parameter after the first), but it changes behaviour for every direct
  caller and needs a deprecation cycle, not a patch.
- **Accepting `.. index ::`.** numpydoc's own test suite pins the current
  behaviour, so changing it is a judgement call for the maintainer.
- **Keeping unknown-section content.** `__setitem__` warns and then drops the
  body. Fixing it means deciding where the content should go, which is a design
  question rather than a bug fix.

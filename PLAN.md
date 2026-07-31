# Plan

Where treepydoc stands, and what is worth doing next. Ordered by value, with
the reasoning kept short enough to disagree with.

Current state: targets **numpydoc >= 1.10**. Parse-identical across 93 curated
cases, 9907 real docstrings and ~10 900 fuzzed ones; render-identical through
`str()`, through `SphinxDocString`, and through a full Sphinx build of
numpydoc's own `tinybuild` project (6/6 generated pages byte-identical).
numpydoc's own test suite runs on it with the same 271 passing and the same 9
failing, test-for-test.

---

## 0. Equivalence is pinned to a release, by convention

**treepydoc is answer-for-answer identical to a *version* of numpydoc, and
nothing stops that version from moving.**

This is not hypothetical. Retargeting from the old 0.9-era parser to 1.10
touched the grammar, the scanner and the Python layer:

| Change in 1.10 | What it took here |
| --- | --- |
| `split(" : ", maxsplit=1)` | type runs to end of header; the `discarded` node deleted |
| `header.removesuffix(" :")` | new `dangling_separator` node, decided in the scanner |
| `dedent_lines(content)` per section | entries anchored at the body's margin, not column 0 |
| `_role` accepts `py:` | scanner and grammar both widened |
| Returns+Yields no longer an error | validation dropped |
| See Also errors are `ValueError` | error path rewritten |
| `sections` reordered | mapping order and `__str__` order |
| `dedent_lines([])` is `['']` | empty section body yields one blank parameter |

The pin is `numpydoc==1.10.0` in CI and `numpydoc>=1.10` in `pyproject.toml`.
What is missing is a *signal*: CI should also run the differential suites
against numpydoc `main`, allowed to fail, so the next round of upstream changes
shows up as a red optional job rather than as a surprise months later. That is
a small workflow addition and it is the highest-value thing on this list.

A `compat=` switch spanning multiple numpydoc versions is explicitly **not**
proposed any more. Retargeting showed the differences are spread across the
scanner, the grammar and the Python layer — not confined to interpretation — so
supporting two numpydoc generations at once would mean two grammars. Tracking
one release is the right trade.

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

Done: `editors/` has the Neovim queries, the Python injection and a setup
guide; `tools/highlight_demo.py` runs the whole pipeline outside an editor, and
CI runs it.

The indentation problem that used to make this half-work is **gone**. numpydoc
1.10 dedents each section body before reading entries out of it, so anchoring
entries at the body's own margin is now the faithful behaviour rather than a
divergence — and that is exactly what an editor needs, since it hands over a
docstring still indented to its function. All parameters highlight, not just
the first of each section.

Left:

- **Package the queries** for nvim-treesitter and Helix rather than asking
  people to copy files.
- **A diagnostics pass.** `queries/diagnostics.scm` captures `dangling_separator`
  and `ERROR`. Worth adding: a section title one edit away from a known name
  (`Retruns`, `Parmeters`), which is still a silent documentation deletion.

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

Never measured beyond "fast enough": the sweep parses 9907 docstrings in a few
seconds. Before claiming anything, benchmark against `NumpyDocString` on the
same corpus. The interesting number is not throughput but the incremental
reparse, which is the only thing tree-sitter offers that a rewrite in Python
could not.

## 6. Packaging

Done: `pyproject.toml` + scikit-build-core over CMake, no `setup.py`, abi3
wheels, and GitHub Actions running every suite (`grammar`, `build` across three
OSes, `conformance`, `differential`, `lint`, `workflows`, `package`). Linting
covers Python (ruff), prose (codespell), shell (shellcheck), the scanner
(clang-format, clang-tidy, `gcc -Werror`) and the workflows themselves
(actionlint, zizmor at `--persona=pedantic`), with every linter version pinned.

Left:

- **Publish.** `cibuildwheel` to build the per-platform abi3 wheels on a tag,
  and a release job. The `package` job proves the sdist and wheel both install
  and work, but nothing uploads them.
- **A Rust/Node binding.** `tree-sitter.json` declares only C and Python.
- **`ruff format`.** Deliberately not enforced: `tools/corpus.py` holds
  docstring fixtures copied verbatim out of numpydoc's suite, and reformatting
  risks perturbing the data under test. Adopting it means excluding that file
  and accepting ~500 lines of churn elsewhere.
- **The numpydoc pin is a CI variable.** `NUMPYDOC_VERSION` at the top of the
  workflow. See section 0: CI should also run against numpydoc `main`, allowed
  to fail, so upstream changes surface early.

---

## Upstream fixes to numpydoc

Four fixes were prepared against the old fork before the retarget. Checking them
against 1.10:

1. **`split(' : ')[:2]` → `maxsplit=1`** — **already upstream** in 1.10.
2. **Warn on a wrong-length section underline** — **already upstream** in 1.10,
   and more broadly than the version written here: `_is_at_section` warns on any
   length mismatch, not only on one that is too short.
3. **`yield StopIteration`** — **still present** in 1.10. `_read_sections`
   yields the exception *class* as if it were a `(name, content)` pair, so any
   consumer that unpacks it raises `TypeError`. A PEP 479 migration leftover,
   and still worth a one-line patch.
4. **Strip the parameter name and type after splitting** — **still present** in
   1.10. `x :  int` yields the type `' int'` and `x  : int` yields the name
   `'x '`, so the same parameter written with an extra space compares unequal
   to itself.

So two of the four are worth reopening against current numpydoc; the branch on
the fork targets a release nobody should be running.

Still not attempted, and why:

- **`textwrap.dedent` → `inspect.cleandoc`.** Much less pressing now that
  section bodies are dedented separately, but the top-level dedent is still
  wrong for a docstring passed directly to `NumpyDocString`. It changes
  behaviour for every direct caller and needs a deprecation cycle.
- **Accepting `.. index ::`.** numpydoc's own test suite pins the current
  behaviour, so changing it is the maintainer's call.
- **Keeping unknown-section content.** `__setitem__` warns and then drops the
  body. Fixing it means deciding where the content should go.
- **`dedent_lines([])` returning `['']`.** New in 1.10: a section with an empty
  body comes back as one blank `Parameter` rather than none. Probably
  unintended, but it is upstream's call whether anything depends on it.

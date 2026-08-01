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

The signal this needed now exists: `.github/workflows/warts.yml` runs the
upstream scan weekly against **both** the pinned release and numpydoc `main`,
and files an issue the moment `main` parses something differently from the
release. Upstream changes surface as an issue on this repository ahead of the
release that would break users, rather than months later.

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
- **Publish the playground.** `npm run playground:export` already writes a
  self-contained static directory, and CI builds it on every push; nothing
  deploys it. A Pages job would give the grammar a URL to point at — the cost is
  a second workflow with `pages: write`, which is why it is not in the
  `contents: read` one. `tree-sitter-rst` does exactly this, and its Makefile is
  the model.
- **A diagnostics pass.** `queries/diagnostics.scm` captures `dangling_separator`
  and `ERROR`. Worth adding: a section title one edit away from a known name
  (`Retruns`, `Parmeters`), which is still a silent documentation deletion.
- **A margin token, so the rst injection can dedent.** An editor hands over a
  docstring still indented to its function, and reStructuredText reads a
  leading indent as a block quote, so every injected description parses as
  `(block_quote (paragraph …))`.

  tree-sitter can inject over a set of ranges, and that does remove the
  wrapper — but a query can only exclude each line's *own* indent, and RST is
  relative-indentation sensitive, so a `::` literal block flattens into prose
  and a nested list becomes a sibling. Measured, and pinned by
  `test_per_line_ranges_would_flatten_nested_structure`; the cosmetic wrapper
  is the better trade.

  The fix is to strip the region's **common** margin instead, which the query
  language cannot express. It needs three things: the indent moved out of the
  `line` node, `line` extended to span its own newline (so concatenated ranges
  do not run together), and blank lines made visible (or two paragraphs
  separated by one merge). All three are cheap — a prototype passed all 60
  corpus cases with 3 expectation updates and left every differential suite
  identical, because the Python layer slices whole source lines by row and
  never reads a line's columns.

  What is not cheap is the fourth: an external token that consumes exactly the
  region's margin. The scanner already computes a section body's margin for
  `dedent_lines`; a description needs its own, measured the same way, and the
  preamble paragraphs need a third. That is the whole job, and it is worth
  doing — it is the difference between the tree being an approximation of what
  an editor should show and being exactly it.

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
- **The numpydoc pin is a CI variable.** `NUMPYDOC_VERSION`, at the top of both
  workflows, and they have to be bumped together.

---

## What the warts cost in practice

`tools/warts.py` answers the question that decides whether any of this is worth
an upstream patch: *does it happen to anybody?* It locates every docstring with
tree-sitter-python (so each finding has a real `file:line`), parses it with
treepydoc, and confirms the consequence against numpydoc itself — a pattern
match is not a finding unless `NumpyDocString` actually mis-handles it.

Over **21 111 docstrings** in numpy, scipy, pandas, matplotlib and
scikit-learn, at their current `main`:

| Finding | Count | Where |
| --- | --- | --- |
| `unknown-section` | 171 | 130 scipy, 31 numpy, 5 sklearn, 3 pandas, 2 matplotlib |
| `dangling-separator` | 40 | 18 pandas, 12 scipy, 5 numpy, 4 sklearn, 1 matplotlib |
| `misspelled-section` | 33 | 13 sklearn, 11 pandas, 7 scipy, 2 numpy |
| `unstripped-field` | 32 | 13 pandas, 10 scipy, 7 sklearn, 2 matplotlib |
| `underline-length` | 13 | 5 scipy, 4 pandas, 4 sklearn |
| `numpydoc-raises` | 12 | 5 numpy, 4 pandas, 3 sklearn |

The 33 `misspelled-section` hits are the ones that matter, because each is a
section whose entire body is dropped without any output the author would see:
`Return` (7×), `Example` (4×), `Warning` (3×), `Parameters:` (3×),
`Reference` (3×), `Note`, `Parameter`, `Raise`, `Params`, `Class Attributes`.
`sklearn/utils/validation.py`'s `_check_categorical_features` writes `Return`
and loses its whole return description; the warning goes to stderr during a
docs build and nowhere else.

The 12 `numpydoc-raises` are hard failures on shipped code — every
`numpy.polynomial` submodule's docstring dies on
``See Also: `numpy.polynomial` `` because a plain reStructuredText literal is
not one of the two spellings `_func_rgx` accepts.

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

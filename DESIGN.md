# Design notes

This grammar is deliberately bug-compatible with
`numpydoc.docscrape.NumpyDocString`, **as of numpydoc 1.10**. The point of the
exercise was a parser that produces *the same answers* as the reference
implementation, so that it can be swapped in without changing any downstream
output — while also producing a syntax tree, which the reference implementation
does not.

Two documents in one, then: how the grammar reproduces numpydoc, and where
numpydoc's behaviour is worth a second look.

---

## 1. How a line-oriented parser becomes a tree-sitter grammar

`docscrape.py` is not a grammar. It is a `Reader` over a list of lines plus a
handful of predicates that peek one line ahead. Almost every decision it makes
needs more context than a token boundary provides:

| Question | Context needed |
| --- | --- |
| Is this line a section title? | this line **and the next** (underline check) |
| Does this paragraph declare a signature? | the whole paragraph, joined and stripped |
| Does this See Also line open an item or continue the previous one? | the whole line, run through a regex |
| Does this line end the current parameter's description? | its indentation |
| Can a section start here at all? | whether the **previous** line was blank |

A tree-sitter external scanner may read arbitrarily far ahead, but it can never
rewind: the token it returns always starts where the scanner was entered, and
`mark_end` can only move the end *forward*. So a scanner that reads two lines to
answer "is this a section?" and then decides "no" has destroyed its ability to
emit a token ending mid-way through line one.

The way out is that **every classification decision is a zero-width guard
token**. The scanner marks the token end at the current position, reads as far
ahead as it likes, and returns a token of width zero naming what it found:
`_param_section_start`, `_signature_start`, `_entry_start`,
`_see_also_item_start`, and so on. The grammar uses the guard to commit to one
branch. Every token after the guard is an ordinary regular expression, because
by then there is nothing left to disambiguate.

The result is that the scanner contains numpydoc's *predicates* and the grammar
contains numpydoc's *structure*, and the two never have to negotiate.

Three pieces of state survive between tokens (serialized, so incremental
reparsing works):

- `after_blank` — `_is_at_section` is only ever reached through
  `seek_next_non_empty_line`, so a section header must be preceded by a blank
  line or start the docstring. Without this, `Summary\nParameters\n----------`
  would find a section where numpydoc finds three lines of summary.
- `header_end` — the column just past the last non-space character of the
  parameter header currently being split, needed because `header.strip()` runs
  *before* the `' : '` search (see §2.2).
- two flags guarding the zero-width tokens emitted at end of input, so they
  cannot fire twice at the same position.

### Input is dedented first

`NumpyDocString.__init__` runs `textwrap.dedent` over the whole docstring before
doing anything else, and then treats **column 0** as the structural anchor:
`read_to_next_unindented_line` looks for a non-blank line with no leading
whitespace. The grammar inherits that contract — it parses dedented text, and
`treepydoc.parse()` applies the dedent for you.

The consequence is that tree positions refer to the dedented string, not the
original. That is a real limitation for an editor integration and the honest
fix is a line-by-line offset map, which is cheap to build (dedent removes a
constant prefix from every non-blank line) but is not implemented here.

Doing the dedent inside the scanner instead was considered and rejected:
`textwrap.dedent`'s margin is a property of the *entire* input, so computing it
would make the first token depend on the last byte of the file and destroy
incremental reparsing — for exact parity with a wart that arguably should not
exist (§2.1).

### Errors become nodes

numpydoc raises `ParseError` from `_parse_see_also` when a line is neither a
continuation nor a parsable item. A grammar cannot raise; it produces an `ERROR`
node. `treepydoc.NumpyDocString` translates that back into the same exception,
so the Python API behaves identically, but the tree keeps the rest of the
document intact and pinpoints the offending line — which is strictly more useful
than an exception that discards the whole parse.

---

## 2. numpydoc behaviours reproduced here that are worth questioning

Everything in this section is faithfully reproduced. It is listed because
faithfully reproducing it was, in several cases, the hardest part of the job,
and because a future version of numpydoc might reasonably change it.

### 2.1 `textwrap.dedent` is still the wrong dedent, but it mostly stops mattering

```python
docstring = textwrap.dedent(docstring).split("\n")
```

A Python docstring's first line is flush against the opening quotes and the rest
is indented to the body, so `textwrap.dedent`'s common margin comes out as `''`
and nothing is dedented. `inspect.cleandoc` is the right primitive and 1.10
still does not use it.

What saves it is that `_parse_param_list` and `_parse_see_also` now open with
`content = dedent_lines(content)`, dedenting each *section body* separately. So
the top-level dedent failing no longer costs you parameters:

```python
NumpyDocString("""Summary.

    Parameters
    ----------
    x : int
        First.
    y : str
        Second.
    """)["Parameters"]
```

```
[Parameter(name='x', type='int', desc=['First.']),
 Parameter(name='y', type='str', desc=['Second.'])]
```

Two parameters, correctly. On 0.9 this returned one, with `y : str` sitting
inside `x`'s description as prose.

This is the single most consequential change for treepydoc, because it is what
makes editor integration work: an editor hands over a docstring still indented
to its function body, and section-relative dedenting is exactly what that needs.
The scanner reproduces it by working out, at each section header, the margin
`dedent_lines` would strip from that section's body, and anchoring entries there
instead of at column 0. See `editors/README.md`.

The remaining sharp edge is that the margin is the minimum indent over the
body's non-blank lines, so it has to be computed by looking at the whole body —
the first line's indent is not good enough. A See Also body that opens with a
continuation is deeper than the items that follow it, and taking the first line
would misread every one of them.

### 2.2 `split(' : ')` used to truncate; 1.10 fixed it

```python
arg_name, arg_type = header.split(" : ", maxsplit=1)   # 1.10
arg_name, arg_type = header.split(' : ')[:2]           # 0.9
```

The old form split on *every* occurrence and kept two, so
`d : dict of {str : int}` documented `d` with the type `dict of {str`. 1.10
splits once and keeps the remainder, which is almost certainly what was always
meant. Nothing is discarded any more, and the `discarded` node this grammar used
to expose is gone with it.

Its replacement is smaller but real: `header.removesuffix(" :")`. A header with
no separator that still ends in ` :` — `formats, names, byteorder :`, which
occurs in numpy — silently loses the colon. That reads like someone starting to
write a type and stopping, and numpydoc says nothing about it, so the grammar
keeps it as a `dangling_separator` node and `queries/diagnostics.scm` flags it.

### 2.3 Field values are not stripped after the split

Only the whole header is stripped, once, before the split. The fields keep
whatever whitespace the split leaves them:

| header | name | type |
| --- | --- | --- |
| `x :  int` | `'x'` | `' int'` — leading space |
| `x  : int` | `'x '` | `'int'` — trailing space |

So the same parameter, written with one extra space, compares unequal to itself.
Anything that uses the type string as a dict key or matches it against a table
will quietly miss.

This one is fiddly to reproduce exactly (the scanner has to place token
boundaries at the byte offsets Python's `str.split` would produce, including the
stray space), and it is hard to argue it is intentional.

### 2.4 The section underline is checked with `startswith`

```python
return l2.startswith('-'*len(l1)) or l2.startswith('='*len(l1))
```

Not equality. So for a 10-character title:

- `----------` — section
- `---------------------` (longer) — section
- `----------!!!! nonsense` — **section**, the trailing junk is discarded
- `---------` (one short) — **not** a section, silently becomes prose

The asymmetry is the problem. An underline that is one dash too short is the
single most common numpydoc typo, and it produces no error, no warning — the
section and everything in it simply vanishes into the previous section's text.
An underline with arbitrary garbage appended, meanwhile, is accepted without
comment.

1.10 now warns about this — `_is_at_section` reports a "potentially wrong
underline length" for any adornment run of three or more characters whose length
differs from the title's. It does not change what parses, so the section is
still silently dropped; you just get told. Scanning numpy, scipy and pandas with
an equivalent check finds two genuine cases: `scipy.stats.matrix_t_gen.logpdf`
loses its `Examples` section and `pandas.core.groupby.Grouping` loses its
`Attributes` section, each to an underline three characters short.

### 2.5 `.. index::` must be spelled exactly

`_is_at_section` tests `l1.startswith('.. index::')` — a literal match. Write
`.. index :: random`, which is legal reStructuredText, and it is not recognised
as a section at all. It is not an error and not a warning; the text is folded
into whatever section is currently open, usually the extended summary, and the
index is silently empty. numpydoc's own test suite pins this behaviour by
asserting that the string `"index"` appears in the output — which it does, as
prose.

### 2.6 Unknown sections are dropped, and the drop is easy to miss

`__setitem__` warns `Unknown section X` and then does **not** store the content —
the assignment only happens in the `else` branch. A section title with a typo
(`Retruns`, `Parmeters`) therefore discards its entire body with nothing but a
warning, which is invisible in most build configurations.

Compare with §2.4: a mistyped *underline* is silently dropped with no warning at
all. Neither failure mode is loud enough for something that deletes
documentation.

### 2.7 Summary can end up holding the signature

`_parse_summary` reads paragraphs in a loop, records any that match the
signature regex, and then assigns *whatever paragraph it last read* to
`Summary` — signature or not:

```
z(a, theta)

Parameters
----------
```

`Signature` and `Summary` both come out as `z(a, theta)`. Whereas:

```
z(x1, x2)

z(a, theta)
```

leaves `Summary` empty, because the loop ran off the end and assigned the empty
read. Reproducing this needed a special case keyed on whether a section follows
the last signature.

### 2.8 See Also's continuation rule works by list aliasing

```python
rest = list(filter(None, [description]))
items.append((funcs, rest))
...
rest.append(line.strip())   # mutates the list already inside items[-1]
```

Continuation lines are attached to the previous item by mutating a list that was
already stored in the results. It works, but it has a corollary: if the *first*
line of a See Also body is a continuation, `rest` is the initial `[]` that was
never appended to any item, and the text is lost with no warning. The grammar
keeps those lines as an `orphan_continuation` node so they are at least visible.

### 2.9 `Warns` and `Warnings` are different grammars

`Warns` is a parameter list; `Warnings` is free text. Two section names one
character apart with completely different parse rules, and getting it wrong
produces no error — just a section whose structure silently differs from what
was intended. Not a bug, but a name worth regretting.

### 2.10 `_read_sections` yields the `StopIteration` class

```python
elif len(data) < 2:
    yield StopIteration
```

This yields the exception *class* as if it were a `(name, content)` pair. Any
consumer that unpacks it gets a `TypeError`. It appears to be a very old
`raise StopIteration` that was rewritten during the PEP 479 migration and lost
its meaning. In practice the branch is nearly unreachable, which is presumably
why nobody has noticed.

### 2.11 An empty section body yields one empty parameter

`_parse_param_list` opens with `dedent_lines(content)`, and `dedent_lines([])`
is `textwrap.dedent("").split("\n")` — which is `['']`, a list containing one
empty line, not an empty list. The reader then reads that line, strips it to
`''`, and produces `Parameter('', '', [])`.

So a section with a header and no body does not come back empty:

```python
NumpyDocString("\nParameters\n----------")["Parameters"]
```

```
[Parameter(name='', type='', desc=[])]
```

New in 1.10, and reproduced here.

### 2.12 Two blank lines become one

`_read_to_next_section` reassembles a section body one paragraph at a time and
inserts exactly one `''` between them, so vertical whitespace inside a parameter
description is normalised from N blank lines to one. Harmless for prose,
destructive for a literal block in an `Examples` section where blank lines are
significant.

---

## 3. What the tree buys you

Everything above is reproduced exactly, so nothing here is a behaviour change.
What the tree adds:

- **Positions.** Every name, type, description line, section title and See Also
  target has a byte range. numpydoc returns strings with no provenance, which is
  why `numpydoc.validate` has to re-derive line numbers heuristically.
- **Recoverable errors.** A malformed See Also entry no longer discards the
  whole docstring; it becomes one `ERROR` node among otherwise good sections.
- **Diagnosable warts.** The text `split(' : ')[:2]` throws away is a node
  (`discarded`), so it can be underlined instead of vanishing.
- **Incremental reparsing.** Editing one line reparses one line.
- **Injection.** `queries/injections.scm` hands the prose sections to
  `tree-sitter-rst`, so `Notes` and `Examples` get real reStructuredText
  highlighting rather than being treated as opaque text.

---

## 4. Verification

Two levels, both reproducible:

- `tools/conformance.py` — 93 curated cases, every docstring literal in
  numpydoc's own `test_docscrape.py` plus hand-written edge cases, compared
  key-by-key against `NumpyDocString`. Includes the docstrings numpydoc rejects,
  which must be rejected identically.
- `tools/sweep.py` — every public docstring in numpy, scipy and pandas: **9907
  docstrings, 9907 identical**, with 11 rejected the same way by both parsers.
- `tools/fuzz.py` — takes real docstrings and corrupts the characters that carry
  structure (`-`, `=`, `:`, whitespace, newlines), then runs the same
  comparison: **10 900 mutants across three seeds, 0 disagreements**, 282
  rejected identically by both. This is also the cheapest way to catch a scanner
  that loops forever, the characteristic failure of an external scanner emitting
  a zero-width token without making progress — and it caught exactly that during
  development.

Both compare the full mapping — all 18 keys, including the exact list-of-lines
representation of every description, so whitespace differences show up as
failures rather than being normalised away.

Real bugs in this grammar found by the sweep and the fuzzer rather
than by the curated corpus: headers ending in `foo :`, trailing whitespace after
a section title, trailing whitespace after a parameter header, the
`strip`-before-split ordering of §2.2, a trailing *tab* in a header (`strip`
removes more than spaces), parameter headers longer than the scanner's line
buffer, and Python's `\w` being Unicode-aware where tree-sitter's is not. Real
docstrings are messier than test fixtures, and corrupted ones messier still.

### numpydoc's own test suite

`tools/numpydoc_swap.py` rebinds the parser names in `numpydoc.docscrape` and
runs numpydoc's suite on treepydoc. The same 271 tests pass and the same 9 fail
— test-for-test, not just by count — where the 9 are pre-existing failures of
that release in this environment.

Getting there needed one addition that is worth calling out, because it says
something about what "drop-in" costs. `numpydoc.validate.Validator.section_titles`
does this:

```python
self.doc._doc.reset()
while not self.doc._doc.eof():
    content = self.doc._read_to_next_section()
```

It drives the reference parser's private line `Reader` directly. No amount of
matching the public mapping helps; a consumer reaching into `_doc` needs `_doc`
to exist. So `treepydoc` ships `_Reader` and `_read_to_next_section` as an
explicitly labelled compatibility shim that takes no part in the parse. Without
it, 24 of `test_validate`'s tests and 2 of `test_main`'s fail — which is the
whole of `numpydoc lint`.

It is also a good advertisement for the tree. `section_titles` wants the list of
section titles as written; treepydoc has a `section_name` node for each one,
with a byte range. Reimplementing that method against the tree would be three
lines and would report positions. The shim exists to keep today's callers
working, not because the line reader is the right way to answer the question.

### Known limits

- Tree positions refer to the dedented string, not the original (§1).
- The scanner folds every non-ASCII code point to one placeholder byte, so it
  cannot tell a Unicode letter from a Unicode symbol. `\w` therefore accepts
  slightly more than Python's does — only reachable through a non-ASCII Sphinx
  role name, which does not occur in practice.
- Lines longer than 4096 code points are not classified as section titles or
  signatures; they are read as ordinary text. Parameter headers of any length
  split correctly.

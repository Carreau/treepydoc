# Highlighting numpydoc docstrings in Neovim

Neovim only. Vim has no tree-sitter runtime, so there is no path there — if you
are on Vim, the closest thing is a regex syntax file, which is a different
project.

## What you get

Section titles, their underlines, parameter names and types, See Also targets
and roles, and the `.. index::` marker, each with its own capture. Plus two
nodes whose whole reason to exist is to be complained about:

- `dangling_separator` — the ` :` that `header.removesuffix(" :")` throws away,
  so you can see a header that declared a type and then did not.
- `section_underline_overlong` — an underline longer than its title. numpydoc
  parses the section anyway and warns to stderr, where nobody reads it; here it
  is styled as a warning in the buffer.

## Setup

### 1. Build and install the parser

With [nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter):

```lua
local parsers = require("nvim-treesitter.parsers").get_parser_configs()
parsers.numpydoc = {
  install_info = {
    url = "https://github.com/carreau/treepydoc",
    files = { "src/parser.c", "src/scanner.c" },
    branch = "main",
    generate_requires_npm = false,
    requires_generate_from_grammar = false,
  },
  filetype = "numpydoc",
}
```

Then `:TSInstall numpydoc`.

Without nvim-treesitter, build the shared object yourself and drop it where
Neovim looks for parsers:

```sh
cc -o numpydoc.so -shared -Isrc -fPIC src/parser.c src/scanner.c -Os
mkdir -p ~/.local/share/nvim/site/parser
mv numpydoc.so ~/.local/share/nvim/site/parser/
```

### 2. Install the queries

```sh
mkdir -p ~/.config/nvim/queries/numpydoc
cp editors/nvim/queries/numpydoc/*.scm ~/.config/nvim/queries/numpydoc/

# `after/` so this *extends* nvim-treesitter's python injections instead of
# replacing them.
mkdir -p ~/.config/nvim/after/queries/python
cp editors/nvim/queries/python/injections.scm ~/.config/nvim/after/queries/python/
```

### 3. Check it

Open a Python file with a numpydoc docstring and run `:InspectTree`. The
docstring should appear as an injected `numpydoc` tree. `:Inspect` with the
cursor on a section title should report `@markup.heading`.

## How the injection works

`editors/nvim/queries/python/injections.scm` captures `string_content` — the
inside of the string, without the `"""` delimiters:

```scheme
((function_definition
   body: (block . (expression_statement (string (string_content) @injection.content))))
 (#set! injection.language "numpydoc"))
```

Capturing the whole `string` node instead feeds the delimiters to the parser,
and the closing `"""` sitting on its own line becomes an extra line of the last
parameter's description. The anchored `.` restricts the match to the *first*
statement in the body, which is what makes it a docstring rather than any
string.

## Indentation

Worth knowing, because it used to be a real limitation and is not any more.

numpydoc dedents a docstring before parsing, and then anchors parameter entries
at column 0. An editor hands over the docstring as it appears in the file,
indented to the function body — so on that anchor, only the first parameter of
each section would ever highlight.

numpydoc 1.10 also runs `dedent_lines(content)` over each section body before
reading entries out of it, which makes the anchor the body's own margin rather
than column 0. treepydoc reproduces that: the scanner works out the margin
`dedent_lines` would strip for each section, and anchors entries there. An
indented docstring parses exactly like a dedented one, so everything
highlights.

You can check on the built-in sample, which has three parameters and one
return:

```sh
python3 tools/highlight_demo.py --color
```

```
captures: comment=6, function=2, markup.heading=5, markup.italic=1,
markup.raw.block=2, property=1, punctuation.bracket=2,
punctuation.delimiter=7, punctuation.special=5, type=4, variable.parameter=4

9 region(s) handed to rst -> 12 node types: block_quote, body, bullet_list,
content, directive, doctest_block, interpreted_text, list_item, literal,
paragraph, role, type
```

Five headings, five underlines, four parameter names, four types — and nine
regions the numpydoc grammar deliberately does not look inside.

## Capture names

From `queries/highlights.scm`:

| Node | Capture |
| --- | --- |
| `section_name` | `@markup.heading` |
| `section_underline` | `@punctuation.special` |
| `section_underline_overlong` | `@punctuation.special` + `@comment.warning` |
| `name` (parameter) | `@variable.parameter` |
| `type` | `@type` |
| `separator` (` : `) | `@punctuation.delimiter` |
| `dangling_separator` | `@error` |
| `role` (See Also) | `@property` |
| `index_marker` | `@comment` |
| `ERROR` | `@error` |

To iterate on a capture without restarting an editor, paste the query into the
browser playground — `npm run playground` from the repository root — which runs
the same query language against the same grammar and shows what each pattern
matches. See the README's *Playground* section.

## Deferring the prose to reStructuredText

numpydoc never looks inside its prose regions — it strips, dedents and joins
them as raw lines and hands the result to Sphinx. This grammar does the same,
and `queries/injections.scm` says who *should* look inside: `rst`. Install
[tree-sitter-rst](https://github.com/stsewd/tree-sitter-rst) and bullet lists,
roles, inline literals, directives and doctest blocks all light up inside
docstrings without this grammar knowing what any of them are.

Five regions are handed over:

| Node | Why it is reStructuredText |
| --- | --- |
| `summary` | emitted verbatim into the generated RST |
| `extended_summary` | same |
| `description` | a parameter/return description is free-form RST |
| `see_also_description`, `see_also_continuation` | end up in an RST definition list |
| `section_body` of a `generic_section` | `Notes`, `Examples`, `References`, and anything unrecognised |

Two nodes are deliberately **not** injected:

- **`signature`.** It looks like Python and is not. `ufunc(x, /, out=None, *,
  where=True)`, `f(x[, y])` and `g(a, b=<no value>)` are all signatures
  numpydoc accepts, and all three are syntax errors to tree-sitter-python —
  injecting `python` would put an ERROR node under most of numpy.
- **`type`.** Only 0.5% of types across scipy and scikit-learn contain a role,
  and a type is an inline fragment rather than a block. It is a one-line
  addition if you disagree.

### The indentation cost

An editor hands over the docstring as it appears in the file, and a parameter
description is indented under its header. reStructuredText reads a leading
indent as a **block quote**, so an injected description parses as
`(block_quote (paragraph …))` rather than `(paragraph …)`.

Everything inside still parses and still highlights — the wrapper is the only
difference — and there is no fix available from this side: injection ranges can
be offset, but not dedented per line. `test_indented_regions_become_a_block_quote`
pins the behaviour so this note stays true.

# Highlighting numpydoc docstrings in Neovim

Neovim only. Vim has no tree-sitter runtime, so there is no path there — if you
are on Vim, the closest thing is a regex syntax file, which is a different
project.

## What you get

Section titles, their underlines, parameter names and types, See Also targets
and roles, and the `.. index::` marker, each with its own capture. Plus the
`discarded` node — the text numpydoc's `split(' : ')[:2]` throws away — which
you can style as an error to see documentation that is being silently dropped.

**Read the [limitation](#the-indentation-limitation) first.** It is real and it
is visible.

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

## The indentation limitation

numpydoc dedents a docstring before parsing and then anchors parameter entries
at column 0 (`Reader.read_to_next_unindented_line`). This grammar reproduces
that exactly, because being answer-for-answer identical to numpydoc is the point
of the project. An editor, though, hands over the docstring as it appears in the
file — indented to the function body.

The consequence, which you can see for yourself:

```sh
python3 tools/highlight_demo.py --color
```

On the built-in sample — three parameters in `Parameters`, one in `Returns` —
that reports:

```
captures: comment=5, function=1, markup.heading=4, markup.italic=1, markup.raw.block=1, punctuation.delimiter=3, punctuation.special=4, type=2, variable.parameter=2
```

Four section titles and four underlines, but only **two** `variable.parameter`
captures: the first entry of each of the two entry sections. For an indented
docstring:

- section titles and underlines highlight correctly,
- the **first** parameter of each section highlights correctly,
- **every parameter after the first** is absorbed into the previous one's
  description and highlights as body text.

This is not a bug in the queries; it is numpydoc's column-0 anchor meeting text
that was never dedented. numpydoc has the same problem — pass an indented
docstring straight to `NumpyDocString` and you get one parameter instead of
three (DESIGN.md §2.1).

### The fix, and what it costs

Anchor entries at the indentation of the section's *first* body line instead of
at column 0. For dedented input the two are the same thing, so nothing changes
for numpydoc's own callers; for an editor it is exactly right.

It has been prototyped and measured:

| | faithful (today) | indent-relative |
| --- | --- | --- |
| editor highlighting | first parameter per section | all parameters |
| curated corpus | 82 / 82 | 80 / 82 |
| numpy + scipy + pandas | 9904 / 9904 | 9904 / 9905 |
| tree-sitter corpus | 57 / 57 | 57 / 57 |

Every one of the three regressions is a docstring that was never dedented, where
numpydoc collapses several parameters into one and the indent-relative anchor
does not. In other words it diverges from numpydoc only where numpydoc is
wrong — but it *is* a divergence, and this project's promise is to be a drop-in
replacement, so it is not the default. See PLAN.md §0: the honest shape of this
is a `compat=` switch, not a silent behaviour change.

## Capture names

From `queries/highlights.scm`:

| Node | Capture |
| --- | --- |
| `section_name` | `@markup.heading` |
| `section_underline` | `@punctuation.special` |
| `name` (parameter) | `@variable.parameter` |
| `type` | `@type` |
| `separator` (` : `) | `@punctuation.delimiter` |
| `discarded` | `@error` |
| `role` (See Also) | `@property` |
| `index_marker` | `@comment` |
| `ERROR` | `@error` |

`queries/injections.scm` additionally hands the prose sections (`Notes`,
`Examples`, `References`, and parameter descriptions) to `rst`, so install
[tree-sitter-rst](https://github.com/stsewd/tree-sitter-rst) if you want those
highlighted as reStructuredText rather than as plain text.

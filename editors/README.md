# Highlighting numpydoc docstrings in Neovim

Neovim only. Vim has no tree-sitter runtime, so there is no path there — if you
are on Vim, the closest thing is a regex syntax file, which is a different
project.

## What you get

Section titles, their underlines, parameter names and types, See Also targets
and roles, and the `.. index::` marker, each with its own capture. Plus the
`dangling_separator` node — the ` :` that `header.removesuffix(" :")` throws
away — which you can style as an error to see a header that declared a type and
then did not.

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
captures: comment=6, function=2, markup.heading=4, markup.italic=1,
markup.raw.block=1, property=1, punctuation.bracket=2,
punctuation.delimiter=7, punctuation.special=4, type=4, variable.parameter=4
```

Four headings, four underlines, four parameter names, four types.

## Capture names

From `queries/highlights.scm`:

| Node | Capture |
| --- | --- |
| `section_name` | `@markup.heading` |
| `section_underline` | `@punctuation.special` |
| `name` (parameter) | `@variable.parameter` |
| `type` | `@type` |
| `separator` (` : `) | `@punctuation.delimiter` |
| `dangling_separator` | `@error` |
| `role` (See Also) | `@property` |
| `index_marker` | `@comment` |
| `ERROR` | `@error` |

`queries/injections.scm` additionally hands the prose sections (`Notes`,
`Examples`, `References`, and parameter descriptions) to `rst`, so install
[tree-sitter-rst](https://github.com/stsewd/tree-sitter-rst) if you want those
highlighted as reStructuredText rather than as plain text.

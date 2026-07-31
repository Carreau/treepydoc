; Hand Python docstrings to the numpydoc parser.
;
; Goes in `~/.config/nvim/after/queries/python/injections.scm` so it *extends*
; nvim-treesitter's own python injections rather than replacing them.
;
; Only the string's content is injected, not the quotes: `string_content`
; excludes the `"""` delimiters, which would otherwise be parsed as docstring
; text and show up as a stray section entry.

; Module docstring: the first statement in the file.
((module . (expression_statement (string (string_content) @injection.content)))
 (#set! injection.language "numpydoc"))

; Function and method docstrings: the first statement in the body.
((function_definition
   body: (block . (expression_statement (string (string_content) @injection.content))))
 (#set! injection.language "numpydoc"))

; Class docstrings.
((class_definition
   body: (block . (expression_statement (string (string_content) @injection.content))))
 (#set! injection.language "numpydoc"))

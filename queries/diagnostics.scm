; Diagnostic queries for the numpydoc grammar.
;
; These are not standard tree-sitter editor queries (highlights, locals,
; injections, …); they are example patterns for tools that want to surface
; warnings in an editor while a docstring is being written.
;
; Run with the tree-sitter Python bindings, e.g.:
;
;     import tree_sitter, treepydoc
;     q = tree_sitter.Query(treepydoc.language(), open("queries/diagnostics.scm").read())
;     qc = tree_sitter.QueryCursor(q)
;     for _, caps in qc.matches(tree.root_node):
;         ...


; ---------------------------------------------------------------------------
; Text numpydoc silently discards
; ---------------------------------------------------------------------------
;
; `header.split(' : ')[:2]` throws away everything past the second ' : ' in
; a parameter/return header, e.g. `x : int : leftover` keeps `x` and `int`
; and drops `leftover` without any warning. The grammar keeps that text as
; a `discarded` node specifically so tooling can flag it -- it is almost
; always a typo (an extra `:` in a type description) rather than intentional.

(discarded) @diagnostic.discarded_field


; ---------------------------------------------------------------------------
; Parser error nodes
; ---------------------------------------------------------------------------
;
; Anywhere the grammar could not make sense of the input -- most commonly a
; See Also line that is neither a continuation nor a parsable item list,
; which is exactly where numpydoc itself raises `ParseError`.

(ERROR) @diagnostic.parse_error

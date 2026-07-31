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
; A header that declares a type and then does not
; ---------------------------------------------------------------------------
;
; `_parse_param_list` runs `header.removesuffix(" :")`, so a header like
; `formats, names, byteorder :` silently loses its trailing colon. It reads as
; someone starting to write a type and stopping, and numpydoc says nothing
; about it -- the grammar keeps the colon as a node so tooling can.

(dangling_separator) @diagnostic.dangling_separator


; ---------------------------------------------------------------------------
; Parser error nodes
; ---------------------------------------------------------------------------
;
; Anywhere the grammar could not make sense of the input -- most commonly a
; See Also line that is neither a continuation nor a parsable item list,
; which is exactly where numpydoc itself raises `ParseError`.

(ERROR) @diagnostic.parse_error

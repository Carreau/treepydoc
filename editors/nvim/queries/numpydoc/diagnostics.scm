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


; ---------------------------------------------------------------------------
; An underline that is the wrong length
; ---------------------------------------------------------------------------
;
; `_is_at_section` matches with `startswith`, so a longer-than-the-title
; underline still opens a section and only produces a warning on stderr. The
; node exists precisely so an editor can show it where the author is looking.
;
; The opposite case -- an underline *shorter* than its title -- is not
; reachable from here, because numpydoc does not treat it as a section at all:
; the title and its body silently join the previous section. Catching that one
; needs a check over prose lines, not a node.

(section_underline_overlong) @diagnostic.overlong_underline

; Language injections for the numpydoc grammar.
;
; numpydoc treats these regions as arbitrary reStructuredText and only ever
; strips/dedents/joins them as raw lines -- the grammar does not parse their
; contents any further, so an editor should hand them to the `rst` parser.
;
; Every pattern sets `injection.include-children`, and it is load-bearing
; rather than decorative. These nodes are built out of `line` children, and
; without the directive an editor injects one region *per line*, each starting
; at that line's first non-blank column. rst is block-structured and reads a
; run of mid-line fragments as nothing at all: the child tree comes back with
; zero named children and not a single capture. With the directive the whole
; node goes over as one contiguous region and the block structure survives.


; The body of a Notes / Warnings / References / Examples (or any
; unrecognised) section is free-form RST: doctests, math directives,
; citations, bullet lists, ...
((generic_section
   (section_body) @injection.content)
 (#set! injection.language "rst")
 (#set! injection.include-children))

; The extended summary paragraph(s) between the summary and the first
; section are free-form RST as well.
((extended_summary) @injection.content
 (#set! injection.language "rst")
 (#set! injection.include-children))

; A parameter/return/... description can itself contain RST markup (roles,
; math directives, doctests, bullet lists, ...).
((description) @injection.content
 (#set! injection.language "rst")
 (#set! injection.include-children))

; The one-line summary is prose too, and numpydoc emits it into the generated
; reStructuredText verbatim -- roles, inline literals and emphasis all work
; there. Across scipy and scikit-learn, 105 summaries carry an RST role.
((summary) @injection.content
 (#set! injection.language "rst")
 (#set! injection.include-children))

; A See Also description and its continuation lines end up in an RST
; definition list, so they are RST as well. Roles are rare here (2 in the same
; corpus) but there is no reason for the one person who writes one to miss out.
((see_also_description (text) @injection.content)
 (#set! injection.language "rst")
 (#set! injection.include-children))

((see_also_continuation (text) @injection.content)
 (#set! injection.language "rst")
 (#set! injection.include-children))


; Deliberately not injected:
;
; * `signature`. It looks like Python and is not: `ufunc(x, /, out=None, *,
;   where=True)`, `f(x[, y])` and `g(a, b=<no value>)` are all signatures
;   numpydoc accepts and all three are syntax errors to tree-sitter-python, so
;   injecting `python` would put an ERROR node under most of numpy.
; * `type`. Only 0.5% of types in scipy and scikit-learn contain a role, and a
;   type is an inline fragment rather than a block -- feeding it to a
;   block-structured grammar is the wrong shape for a 1-in-200 gain.

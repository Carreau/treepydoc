; Language injections for the numpydoc grammar.
;
; numpydoc treats these regions as arbitrary reStructuredText and only ever
; strips/dedents/joins them as raw lines -- the grammar does not parse their
; contents any further, so an editor should hand them to the `rst` parser.


; The body of a Notes / Warnings / References / Examples (or any
; unrecognised) section is free-form RST: doctests, math directives,
; citations, bullet lists, ...
((generic_section
   (section_body) @injection.content)
 (#set! injection.language "rst"))

; The extended summary paragraph(s) between the summary and the first
; section are free-form RST as well.
((extended_summary) @injection.content
 (#set! injection.language "rst"))

; A parameter/return/... description can itself contain RST markup (roles,
; math directives, doctests, bullet lists, ...).
((description) @injection.content
 (#set! injection.language "rst"))

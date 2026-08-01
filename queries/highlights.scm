; Syntax highlighting queries for the numpydoc grammar.
;
; Capture names follow the conventions used by tree-sitter-rst and the
; broader nvim-treesitter / helix ecosystem (@markup.*, @punctuation.*,
; @variable.parameter, @type, @property, @string, @comment, @error, ...).
;
; Run with the tree-sitter Python bindings, e.g.:
;
;     import tree_sitter, treepydoc
;     q = tree_sitter.Query(treepydoc.language(), open("queries/highlights.scm").read())


; ---------------------------------------------------------------------------
; Section headers: "Parameters" / "----------" and friends
; ---------------------------------------------------------------------------

(section_name) @markup.heading
(section_underline) @punctuation.special

; An underline longer than its title. numpydoc still reads the section, and
; warns to stderr -- which nobody sees outside a docs build. Style it as a
; warning: it is still the underline, so it keeps the base capture, and the
; later capture wins where a theme defines both.
(section_underline_overlong) @punctuation.special
(section_underline_overlong) @comment.warning

; The `.. index::` marker line is directive-shaped, like an RST directive.
(index_marker) @comment
(index_field_line) @string.special


; ---------------------------------------------------------------------------
; Preamble: signature and summary
; ---------------------------------------------------------------------------

; A leading `foo(a, b)`-shaped paragraph, kept verbatim.
(signature) @function
(summary) @markup.italic


; ---------------------------------------------------------------------------
; Parameters / Other Parameters / Attributes / Methods entries
; ---------------------------------------------------------------------------

(entry_header name: (name) @variable.parameter)
(entry_header type: (type) @type)
(entry_header (separator) @punctuation.delimiter)

; `x : int : leftover` -- `leftover` is silently dropped by numpydoc; flag it
; visually as suspect content rather than an ordinary type/description.
(entry_header (dangling_separator) @error)


; ---------------------------------------------------------------------------
; Returns / Yields / Receives / Raises / Warns entries
; ---------------------------------------------------------------------------

(typed_entry_header name: (name) @variable.parameter)
(typed_entry_header type: (type) @type)
(typed_entry_header (separator) @punctuation.delimiter)
(typed_entry_header (dangling_separator) @error)


; ---------------------------------------------------------------------------
; See Also: roles, targets, descriptions
; ---------------------------------------------------------------------------

(role_target role: (role) @property)
(role_target name: (name) @function)
(plain_target name: (name) @function)
(role_target ":" @punctuation.delimiter)
(role_target "`" @punctuation.bracket)

(see_also_targets (trailing_punctuation) @punctuation.delimiter)

(see_also_description ":" @punctuation.delimiter)
(see_also_description (text) @comment)
(see_also_continuation (text) @comment)


; ---------------------------------------------------------------------------
; Generic sections (Notes / Warnings / References / Examples / unrecognised)
; ---------------------------------------------------------------------------

(generic_section (section_body) @markup.raw.block)


; ---------------------------------------------------------------------------
; Descriptions and free text
; ---------------------------------------------------------------------------

(description) @comment
(extended_summary) @comment


; ---------------------------------------------------------------------------
; Parser errors
; ---------------------------------------------------------------------------

(ERROR) @error

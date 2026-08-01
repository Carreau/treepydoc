/**
 * @file numpydoc docstring grammar for tree-sitter
 * @license MIT
 *
 * Reproduces the structure that `numpydoc.docscrape.NumpyDocString` derives
 * from a docstring, including the behaviours that are arguably wrong (see
 * DESIGN.md). Input is expected to be already `textwrap.dedent`-ed, exactly as
 * `NumpyDocString.__init__` does it; column 0 is the structural anchor
 * throughout, mirroring `Reader.read_to_next_unindented_line`.
 *
 * Every decision that needs more lookahead than a token boundary allows -- "is
 * this line a section title?", "does this paragraph look like a signature?",
 * "does this See Also line open an item or continue the previous one?" -- is
 * made by a zero-width guard token in the external scanner. Once a guard fires
 * the parser is committed to one branch, so the tokens that follow can be
 * ordinary regular expressions and the scanner never needs to rewind.
 *
 * Portions of the external scanner's approach are adapted from tree-sitter-rst,
 * (c) 2020 Santos Gallegos, MIT License.
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

module.exports = grammar({
  name: 'numpydoc',

  // numpydoc is line- and column-oriented, so the grammar accounts for every
  // byte rather than letting whitespace be skipped implicitly.
  extras: _$ => [],

  externals: $ => [
    // Consuming.
    $._newline,
    $._blank_line,
    // Zero-width, emitted at end of input. Paragraphs are delimited by blank
    // lines (`read_to_next_empty_line`), and the last one is delimited by this.
    $._eof,

    // Zero-width classification guards, emitted only at column 0.
    $._signature_start,
    $._param_section_start,
    $._type_section_start,
    $._see_also_section_start,
    $._generic_section_start,
    $._index_section_start,
    $._entry_start,
    // Distinguishes a description line from the next entry header:
    // `read_to_next_unindented_line` stops at the first non-blank line with no
    // leading whitespace.
    $._indented_line_start,
    $._see_also_item_start,
    $._see_also_continuation_start,

    // `header.strip().split(' : ')` decomposition, only ever requested once a
    // guard has committed the parser to a parameter entry.
    $._entry_first,
    $._entry_separator,
    $._entry_second,
    $._dangling_separator,

    $._error_sentinel,
  ],

  supertypes: $ => [$._section],

  // A `, ` after a target is either the separator before another target or a
  // trailing comma followed by a description. The lexer prefers the longer
  // token and never backtracks, so both readings have to stay alive until the
  // token after it decides.
  conflicts: $ => [[$.see_also_targets]],

  rules: {
    document: $ => seq(
      repeat($._blank_line),
      optional($.preamble),
      repeat($._section),
    ),

    // ---------------------------------------------------------------- preamble

    // `_parse_summary` loops over signature-shaped paragraphs, keeps the last
    // one, and hands whatever paragraph it stopped on to `Summary`. Everything
    // from there to the first section is the extended summary.
    preamble: $ => choice(
      seq(
        repeat1(seq($.signature, $._paragraph_break)),
        optional($._summary_tail),
      ),
      $._summary_tail,
    ),

    _summary_tail: $ => seq(
      $.summary,
      optional(seq($._paragraph_break, optional($.extended_summary))),
    ),

    // `read_to_next_empty_line` ends a paragraph at a blank line or at EOF.
    _paragraph_break: $ => choice(repeat1($._blank_line), $._eof),

    signature: $ => seq($._signature_start, repeat1($._any_line)),

    summary: $ => repeat1($._any_line),

    // `_read_to_next_section` flattens the remaining paragraphs into one list,
    // so there is nothing to gain from modelling their boundaries here.
    extended_summary: $ => seq(
      $._any_line,
      repeat(choice($._any_line, $._blank_line)),
    ),

    _any_line: $ => seq(alias($._text_line, $.line), $._newline),

    // ---------------------------------------------------------------- sections

    _section: $ => choice(
      $.parameters_section,
      $.typed_section,
      $.see_also_section,
      $.generic_section,
      $.index_section,
    ),

    // Parameters / Other Parameters / Attributes / Methods.
    // A header with no ` : ` is a *name*.
    parameters_section: $ => seq(
      $._param_section_start,
      $._section_head,
      repeat($._blank_line),
      repeat($.parameter),
    ),

    // Returns / Yields / Receives / Raises / Warns.
    // `single_element_is_type=True`: a header with no ` : ` is a *type*.
    typed_section: $ => seq(
      $._type_section_start,
      $._section_head,
      repeat($._blank_line),
      repeat($.typed_entry),
    ),

    see_also_section: $ => seq(
      $._see_also_section_start,
      $._section_head,
      repeat($._blank_line),
      // Continuation lines before any item. numpydoc appends these to a list
      // that is never attached to anything, silently losing the text; the
      // grammar keeps them addressable instead.
      optional($.orphan_continuation),
      repeat($.see_also_entry),
    ),

    // `_parse_see_also` opens with `if not line.strip(): continue`, so a blank
    // line inside the section is skipped entirely rather than ending an entry:
    // an indented line after one still continues the entry above it. Blanks
    // therefore live inside the entry, not between entries.
    orphan_continuation: $ => repeat1(
      seq($.see_also_continuation, repeat($._blank_line)),
    ),

    // Notes / Warnings / References / Examples and any unrecognised title: the
    // body is kept verbatim as lines.
    generic_section: $ => seq(
      $._generic_section_start,
      $._section_head,
      optional($.section_body),
    ),

    // `_is_at_section` compares `peek().strip()` against `peek(1).strip()`, so
    // both lines may carry whitespace on either side without affecting the
    // match, and neither the title nor the underline node includes it.
    _section_head: $ => seq(
      optional($._h_space),
      field('name', alias($._stripped_line, $.section_name)),
      optional($._h_space),
      $._newline,
      optional($._h_space),
      field('underline', alias($._stripped_line, $.section_underline)),
      optional($._h_space),
      $._newline,
    ),

    section_body: $ => repeat1(choice($._any_line, $._blank_line)),

    // `.. index::` is the only directive `_is_at_section` recognises, and it
    // must be spelled with no space before the colons.
    index_section: $ => seq(
      $._index_section_start,
      optional($._h_space),
      field('marker', alias($._stripped_line, $.index_marker)),
      optional($._h_space),
      $._newline,
      repeat(choice($.index_field, $._blank_line)),
    ),

    index_field: $ => seq(
      alias($._text_line, $.index_field_line),
      $._newline,
    ),

    // ------------------------------------------------------- parameter entries

    // The header is `.strip()`ed before it is split, so trailing whitespace is
    // outside every field node.
    parameter: $ => seq(
      $._entry_start,
      $.entry_header,
      optional($._h_space),
      $._newline,
      optional($.description),
    ),

    typed_entry: $ => seq(
      $._entry_start,
      $.typed_entry_header,
      optional($._h_space),
      $._newline,
      optional($.description),
    ),

    entry_header: $ => seq(
      field('name', alias($._entry_first, $.name)),
      optional($._entry_tail),
      optional(alias($._dangling_separator, $.dangling_separator)),
    ),

    typed_entry_header: $ => seq(
      choice(
        seq(field('name', alias($._entry_first, $.name)), $._entry_tail),
        field('type', alias($._entry_first, $.type)),
      ),
      optional(alias($._dangling_separator, $.dangling_separator)),
    ),

    // `header.removesuffix(" :")`. A header with no separator that still ends
    // in ` :` looks like it meant to declare a type and did not; numpydoc drops
    // the colon silently, and the node is kept so tooling can point at it.
    //
    // Separator and dangling colon overlap -- ` : ` versus ` :` -- and the
    // lexer would always prefer the longer one, which is wrong for a header
    // like `... : ` whose trailing space is outside the stripped text. The
    // scanner knows where the header ends, so it decides.

    // `header.split(' : ', maxsplit=1)`: only the first separator splits, so
    // the type is everything after it, up to the end of the stripped header.
    _entry_tail: $ => seq(
      alias($._entry_separator, $.separator),
      field('type', alias($._entry_second, $.type)),
    ),

    description: $ => repeat1(choice($._description_line, $._blank_line)),

    _description_line: $ => seq($._indented_line_start, $._any_line),

    // ---------------------------------------------------------------- see also

    see_also_entry: $ => seq(
      $._see_also_item_start,
      optional($._h_space),
      $.see_also_targets,
      optional($._h_space),
      optional($.see_also_description),
      $._newline,
      repeat(choice($.see_also_continuation, $._blank_line)),
    ),

    see_also_continuation: $ => seq(
      $._see_also_continuation_start,
      $._h_space,
      alias($._stripped_line, $.text),
      optional($._h_space),
      $._newline,
    ),

    // `<funcname> ([,]\s+ <funcname>)* [,.]?` -- note the separator requires
    // whitespace after the comma and forbids it before, so it is one token.
    see_also_targets: $ => seq(
      $.see_also_target,
      repeat(seq($._target_separator, $.see_also_target)),
      // A trailing comma may be followed by whitespace, which makes it lex as
      // the separator token; accept that spelling here too, since the lexer
      // prefers the longer match and never backtracks.
      optional(field(
        'trailing',
        alias(choice(/[,.]/, $._target_separator), $.trailing_punctuation),
      )),
    ),

    _target_separator: _$ => token(/,[ \t]+/),

    see_also_target: $ => choice($.role_target, $.plain_target),

    // `\w` in numpydoc's regexes is Python's, which is Unicode-aware;
    // tree-sitter's `\w` is ASCII, so the class is spelled out.
    role_target: $ => seq(
      ':',
      field('role', alias(/(?:py:)?[\p{L}\p{N}_]+/, $.role)),
      ':',
      '`',
      field('name', alias(/(?:~[\p{L}\p{N}_]+\.)?[a-zA-Z0-9_.-]+/, $.name)),
      '`',
    ),

    plain_target: $ => field('name', alias(/[a-zA-Z0-9_.-]+/, $.name)),

    // `(?P<desc>\S+.*)` is greedy, so the description runs to end of line.
    see_also_description: $ => seq(
      ':',
      optional(seq($._h_space, alias(/\S[^\r\n]*/, $.text))),
    ),

    // ------------------------------------------------------------------ tokens

    // A line with content, kept verbatim including any indentation. numpydoc
    // stores section bodies as raw lines and only dedents them later.
    _text_line: _$ => token(/[ \t]*[^ \t\r\n][^\r\n]*/),

    // The same, with surrounding whitespace trimmed, for the places numpydoc
    // applies `.strip()` before looking at the text.
    _stripped_line: _$ => token(/[^ \t\r\n](?:[^\r\n]*[^ \t\r\n])?/),

    _h_space: _$ => token(/[ \t]+/),
  },
});

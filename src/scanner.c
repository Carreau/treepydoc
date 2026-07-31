// External scanner for tree-sitter-numpydoc.
//
// numpydoc's parser (numpydoc/docscrape.py) is line-oriented: it reads a
// dedented docstring as a list of lines and makes every structural decision by
// inspecting a whole line at a time, occasionally peeking one line ahead. This
// scanner mirrors that shape, so each predicate below has a direct counterpart
// in docscrape.py, named in the comments.
//
// Nearly everything the scanner emits is a *zero-width guard*: it marks the
// token end at the current position, then reads as far ahead as it likes to
// classify the line, and returns a token of width zero. The grammar uses the
// guard to commit to a single branch, after which ordinary regular-expression
// tokens can consume the line without ambiguity. This is what lets the scanner
// look two lines ahead without ever needing to rewind.
//
// Portions of this approach are adapted from tree-sitter-rst,
// Copyright (c) 2020 Santos Gallegos, MIT License.

#include "tree_sitter/alloc.h"
#include "tree_sitter/parser.h"

#include <stdbool.h>
#include <stddef.h>
#include <string.h>

enum TokenType {
  NEWLINE,
  BLANK_LINE,
  EOF_TOKEN,
  SIGNATURE_START,
  PARAM_SECTION_START,
  TYPE_SECTION_START,
  SEE_ALSO_SECTION_START,
  GENERIC_SECTION_START,
  INDEX_SECTION_START,
  ENTRY_START,
  INDENTED_LINE_START,
  SEE_ALSO_ITEM_START,
  SEE_ALSO_CONTINUATION_START,
  ENTRY_FIRST,
  ENTRY_SECOND,
  ENTRY_DISCARDED,
  ERROR_SENTINEL,
};

#define LINE_CAPACITY 4096

typedef struct {
  // `_is_at_section` is only ever reached through `seek_next_non_empty_line`,
  // so a section header must be preceded by a blank line or start the
  // docstring. Without this, a header glued to the end of a paragraph would be
  // recognised here but not by numpydoc.
  bool after_blank;
  // Guard the zero-width tokens emitted at end of input so they cannot loop.
  bool eof_newline_emitted;
  bool eof_emitted;
  // Column just past the last non-space character of the entry header the
  // parser is currently inside. `header.strip()` runs before the split, so a
  // ` : ` that reaches into the trailing whitespace is not a separator at all:
  // `'... : '` strips to `'... :'`, which contains no separator.
  uint16_t header_end;
} Scanner;

// ---------------------------------------------------------------- char classes

static inline bool is_space(int32_t c) { return c == ' ' || c == '\t'; }

static inline bool is_newline(int32_t c) { return c == '\n' || c == '\r'; }

// What `str.strip()` removes from the ends of a line, minus the line
// terminators, which end the line anyway.
static inline bool is_strippable(int32_t c) {
  return c == ' ' || c == '\t' || c == '\f' || c == '\v';
}

// Every non-ASCII code point is folded to this byte in the line buffer, so
// that buffer offsets count code points the way Python's `len()` does.
#define NON_ASCII 0x80

// Python's `\w` is Unicode-aware, so a role like `:méth:` matches. The buffer
// cannot tell a letter from a symbol once folded, so every non-ASCII code point
// counts as a word character -- an over-approximation, but far closer than
// restricting `\w` to ASCII.
static inline bool is_word(int32_t c) {
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
         (c >= '0' && c <= '9') || c == '_' || (unsigned char)c == NON_ASCII;
}

// `[a-zA-Z0-9_.-]`, the class numpydoc uses for See Also targets. Unlike `\w`
// this one is written out literally, so it stays ASCII.
static inline bool is_name_char(int32_t c) {
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
         (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-';
}

static inline char lower(char c) { return (c >= 'A' && c <= 'Z') ? c + 32 : c; }

// ------------------------------------------------------------- line buffering

typedef struct {
  char data[LINE_CAPACITY];
  uint32_t len;
  // Code points seen so far, which exceeds `len` once the buffer overflows.
  uint32_t count;
  // Code points past the last non-space character, counted over the whole line
  // even when it overflows the buffer, so that `header.strip()`'s end position
  // is right for lines longer than `LINE_CAPACITY`.
  uint32_t content_end;
  bool truncated;
} Line;

static void line_push(Line *line, int32_t c) {
  line->count++;
  if (!is_strippable(c)) line->content_end = line->count;
  if (line->len + 1 >= LINE_CAPACITY) {
    line->truncated = true;
    return;
  }
  // Non-ASCII code points fold to one placeholder byte so that `len` counts
  // code points, matching Python's `len()`. Only ASCII is compared byte-wise.
  line->data[line->len++] = (c >= 0 && c < 128) ? (char)c : (char)NON_ASCII;
  line->data[line->len] = '\0';
}

// Consumes the rest of the current line, excluding its terminator.
static void read_line(TSLexer *lexer, Line *line) {
  line->len = 0;
  line->count = 0;
  line->content_end = 0;
  line->truncated = false;
  line->data[0] = '\0';
  while (!lexer->eof(lexer) && !is_newline(lexer->lookahead)) {
    line_push(line, lexer->lookahead);
    lexer->advance(lexer, false);
  }
}

static bool consume_line_terminator(TSLexer *lexer) {
  if (lexer->lookahead == '\r') {
    lexer->advance(lexer, false);
    if (lexer->lookahead == '\n') lexer->advance(lexer, false);
    return true;
  }
  if (lexer->lookahead == '\n') {
    lexer->advance(lexer, false);
    return true;
  }
  return false;
}

// `str.strip()` over the whitespace characters that actually occur in
// docstrings.
static void line_strip(const Line *line, uint32_t *start, uint32_t *end) {
  uint32_t s = 0;
  uint32_t e = line->len;
  while (s < e && is_strippable(line->data[s])) s++;
  while (e > s && is_strippable(line->data[e - 1])) e--;
  *start = s;
  *end = e;
}

static bool line_is_blank(const Line *line) {
  uint32_t s;
  uint32_t e;
  line_strip(line, &s, &e);
  return s == e;
}

// --------------------------------------------------------- numpydoc predicates

// `_parse_summary`'s `re.compile(r'^([\w., ]+=)?\s*[\w\.]+\(.*\)$')`, applied to
// `" ".join(l.strip() for l in paragraph).strip()`.
//
// The optional prefix never backtracks: `[\w., ]` cannot match `=`, so it
// matches iff the maximal run of `[\w., ]` is immediately followed by `=`.
static bool signature_match(const char *s, uint32_t n) {
  uint32_t i = 0;

  uint32_t j = 0;
  while (j < n &&
         (is_word(s[j]) || s[j] == '.' || s[j] == ',' || s[j] == ' ')) {
    j++;
  }
  if (j > 0 && j < n && s[j] == '=') i = j + 1;

  while (i < n && is_space(s[i])) i++;

  uint32_t k = i;
  while (k < n && (is_word(s[k]) || s[k] == '.')) k++;
  if (k == i) return false;

  if (k >= n || s[k] != '(') return false;
  // `.*\)$` is greedy, so the joined paragraph must end with the closing paren.
  return s[n - 1] == ')' && n - 1 > k;
}

// `_funcname`: either ``:role:`name` `` or a bare `[a-zA-Z0-9_.-]+`.
static bool match_funcname(const char *s, uint32_t n, uint32_t *pos) {
  uint32_t i = *pos;

  if (i < n && s[i] == ':') {
    uint32_t j = i + 1;
    uint32_t role_start = j;
    while (j < n && is_word(s[j])) j++;
    if (j == role_start) return false;
    if (j >= n || s[j] != ':') return false;
    j++;
    if (j >= n || s[j] != '`') return false;
    j++;

    // `(?:~\w+\.)?` requires a trailing dot, which is exactly why
    // ``:func:`~foo` `` is a ParseError while ``:obj:`~baz.obj_r` `` is not.
    if (j < n && s[j] == '~') {
      uint32_t m = j + 1;
      uint32_t word_start = m;
      while (m < n && is_word(s[m])) m++;
      if (m > word_start && m < n && s[m] == '.') j = m + 1;
    }

    uint32_t name_start = j;
    while (j < n && is_name_char(s[j])) j++;
    if (j == name_start) return false;
    if (j >= n || s[j] != '`') return false;
    *pos = j + 1;
    return true;
  }

  uint32_t start = i;
  while (i < n && is_name_char(s[i])) i++;
  if (i == start) return false;
  *pos = i;
  return true;
}

enum SeeAlsoMatch {
  SEE_ALSO_NO_MATCH = 0,
  SEE_ALSO_MATCH_NO_DESC = 1,
  SEE_ALSO_MATCH_WITH_DESC = 2,
};

// `_line_rgx`:
//   ^\s* <allfuncs> (?P<trailing>[,.])? (\s*:(\s+(?P<desc>\S+.*))?)? \s*$
static int see_also_line_match(const char *s, uint32_t n) {
  uint32_t i = 0;
  while (i < n && is_space(s[i])) i++;

  if (!match_funcname(s, n, &i)) return SEE_ALSO_NO_MATCH;

  // `(?P<morefuncs>([,]\s+ <funcname>)*)`
  for (;;) {
    if (i >= n || s[i] != ',') break;
    uint32_t j = i + 1;
    uint32_t ws_start = j;
    while (j < n && is_space(s[j])) j++;
    if (j == ws_start) break;  // `\s+` needs at least one space
    if (!match_funcname(s, n, &j)) break;
    i = j;
  }

  if (i < n && (s[i] == ',' || s[i] == '.')) i++;

  uint32_t j = i;
  while (j < n && is_space(s[j])) j++;
  if (j < n && s[j] == ':') {
    j++;
    uint32_t k = j;
    while (k < n && is_space(s[k])) k++;
    // `\s+(?P<desc>\S+.*)`; `.*` swallows the remainder of the line.
    if (k > j && k < n) return SEE_ALSO_MATCH_WITH_DESC;
    // The description group matched but captured nothing, so `\s*$` must hold.
    for (uint32_t m = j; m < n; m++) {
      if (!is_space(s[m])) return SEE_ALSO_NO_MATCH;
    }
    return SEE_ALSO_MATCH_NO_DESC;
  }

  for (uint32_t m = i; m < n; m++) {
    if (!is_space(s[m])) return SEE_ALSO_NO_MATCH;
  }
  return SEE_ALSO_MATCH_NO_DESC;
}

// numpydoc normalises a title with
// `' '.join(w.capitalize() for w in title.split(' '))` before dispatching,
// which is equivalent to comparing case-insensitively against the canonical
// spelling.
static bool title_equals(const char *s, uint32_t len, const char *name) {
  if (strlen(name) != len) return false;
  for (uint32_t i = 0; i < len; i++) {
    if (lower(s[i]) != lower(name[i])) return false;
  }
  return true;
}

static int classify_section(const char *s, uint32_t len) {
  static const char *param_sections[] = {"Parameters", "Other Parameters",
                                         "Attributes", "Methods"};
  static const char *type_sections[] = {"Returns", "Yields", "Raises", "Warns",
                                        "Receives"};

  for (size_t i = 0; i < sizeof(param_sections) / sizeof(char *); i++) {
    if (title_equals(s, len, param_sections[i])) return PARAM_SECTION_START;
  }
  for (size_t i = 0; i < sizeof(type_sections) / sizeof(char *); i++) {
    if (title_equals(s, len, type_sections[i])) return TYPE_SECTION_START;
  }
  if (title_equals(s, len, "See Also")) return SEE_ALSO_SECTION_START;
  return GENERIC_SECTION_START;
}

// `l2.startswith('-'*len(l1)) or l2.startswith('='*len(l1))`. This is
// `startswith`, not equality: a longer underline, or one with trailing junk
// after enough adornment characters, still counts.
static bool underline_matches(const Line *underline, uint32_t title_len) {
  uint32_t s;
  uint32_t e;
  line_strip(underline, &s, &e);
  if (title_len == 0 || underline->truncated) return false;
  if (e - s < title_len) return false;

  char adornment = underline->data[s];
  if (adornment != '-' && adornment != '=') return false;
  for (uint32_t i = 0; i < title_len; i++) {
    if (underline->data[s + i] != adornment) return false;
  }
  return true;
}

// ------------------------------------------------------------- token scanners

// `header.strip().split(' : ')` -- the separator is literally space, colon,
// space. The token ends at the space that starts the first separator, or at the
// last non-space character when there is none, which is where the `.strip()`
// preceding the split leaves it.
//
// Because a candidate separator can only be recognised after consuming it, the
// end is marked at each candidate space *before* looking, and re-marked past
// each non-space character otherwise. Whichever mark is current when the scan
// stops is the right one.
static bool scan_entry_field(TSLexer *lexer, enum TokenType symbol,
                             uint16_t header_end) {
  // `header.strip()` happens once, before the split, so only the first field
  // loses its leading whitespace. `x :  int` really does yield a type of
  // `' int'`, space included.
  if (symbol == ENTRY_FIRST) {
    while (is_strippable(lexer->lookahead)) lexer->advance(lexer, true);
  }

  bool any = false;
  while (!lexer->eof(lexer) && !is_newline(lexer->lookahead)) {
    if (lexer->lookahead == ' ') {
      uint32_t column = lexer->get_column(lexer);
      // Candidate separator: mark here first, so that if it turns out to be
      // one the token stops before the space.
      lexer->mark_end(lexer);
      lexer->advance(lexer, false);
      if (lexer->lookahead == ':') {
        lexer->advance(lexer, false);
        if (lexer->lookahead == ' ' && column + 3 <= header_end) {
          if (!any) return false;
          lexer->result_symbol = symbol;
          return true;
        }
        // Not a separator: either the colon is ordinary content, as in a
        // header ending `byteorder :`, or the ` : ` runs off the end of the
        // stripped header. Either way the colon belongs to the field, so take
        // the mark back past it.
        lexer->mark_end(lexer);
        any = true;
      }
      continue;
    }
    if (is_strippable(lexer->lookahead)) {
      // Only a space can open a separator, and whitespace that turns out to be
      // trailing must stay outside the token, so leave the mark where it is.
      lexer->advance(lexer, false);
      continue;
    }
    lexer->advance(lexer, false);
    lexer->mark_end(lexer);
    any = true;
  }

  if (!any) return false;
  lexer->result_symbol = symbol;
  return true;
}

// Everything past the second separator, which `split(' : ')[:2]` throws away.
static bool scan_entry_discarded(TSLexer *lexer) {
  bool any = false;
  while (!lexer->eof(lexer) && !is_newline(lexer->lookahead)) {
    if (is_strippable(lexer->lookahead)) {
      lexer->advance(lexer, false);
      continue;
    }
    lexer->advance(lexer, false);
    lexer->mark_end(lexer);
    any = true;
  }
  if (!any) return false;
  lexer->result_symbol = ENTRY_DISCARDED;
  return true;
}

// ------------------------------------------------------------------- entry pt

bool tree_sitter_numpydoc_external_scanner_scan(void *payload, TSLexer *lexer,
                                                const bool *valid_symbols) {
  Scanner *scanner = (Scanner *)payload;

  if (valid_symbols[ERROR_SENTINEL]) return false;

  // Mid-line tokens, reachable only once a guard has committed the parser.
  if (valid_symbols[ENTRY_FIRST]) {
    return scan_entry_field(lexer, ENTRY_FIRST, scanner->header_end);
  }
  if (valid_symbols[ENTRY_SECOND]) {
    return scan_entry_field(lexer, ENTRY_SECOND, scanner->header_end);
  }
  if (valid_symbols[ENTRY_DISCARDED]) return scan_entry_discarded(lexer);

  if (valid_symbols[NEWLINE] && is_newline(lexer->lookahead)) {
    consume_line_terminator(lexer);
    lexer->mark_end(lexer);
    lexer->result_symbol = NEWLINE;
    scanner->after_blank = false;
    scanner->eof_newline_emitted = false;
    scanner->eof_emitted = false;
    return true;
  }

  // End of input. Both tokens here have zero width, so each is emitted at most
  // once; the flags are cleared by any token that actually consumes something,
  // which is the only way the scanner can reach this point again.
  if (lexer->eof(lexer)) {
    lexer->mark_end(lexer);
    // A docstring that does not end in a newline still has to close its last
    // line before the paragraph it belongs to can be closed.
    if (valid_symbols[NEWLINE] && !scanner->eof_newline_emitted) {
      lexer->result_symbol = NEWLINE;
      scanner->after_blank = false;
      scanner->eof_newline_emitted = true;
      return true;
    }
    if (valid_symbols[EOF_TOKEN] && !scanner->eof_emitted) {
      lexer->result_symbol = EOF_TOKEN;
      scanner->eof_emitted = true;
      return true;
    }
    return false;
  }

  if (lexer->get_column(lexer) != 0) return false;

  // Baseline for every guard below: the token ends here, whatever we read next.
  lexer->mark_end(lexer);

  bool starts_with_space = lexer->lookahead == ' ';
  bool starts_with_indent = is_space(lexer->lookahead);
  bool consumed_indent = starts_with_indent;
  uint32_t indent_columns = 0;
  while (is_space(lexer->lookahead)) {
    indent_columns++;
    lexer->advance(lexer, false);
  }

  if (lexer->eof(lexer) || is_newline(lexer->lookahead)) {
    if (!valid_symbols[BLANK_LINE]) return false;
    bool terminated = consume_line_terminator(lexer);
    // Nothing was consumed, so there is no blank line here -- only the end of
    // the input, which is handled above. Emitting a token would not advance.
    if (!terminated && !consumed_indent) return false;
    lexer->mark_end(lexer);
    lexer->result_symbol = BLANK_LINE;
    scanner->after_blank = true;
    scanner->eof_newline_emitted = false;
    scanner->eof_emitted = false;
    return true;
  }

  Line line;
  read_line(lexer, &line);
  uint32_t start;
  uint32_t end;
  line_strip(&line, &start, &end);
  const char *title = line.data + start;
  uint32_t title_len = end - start;

  // The next line is needed by two different questions -- "is this a section
  // title?" and "where does this paragraph end?" -- so it is read exactly once.
  bool is_index = scanner->after_blank && !line.truncated && title_len >= 10 &&
                  memcmp(title, ".. index::", 10) == 0;

  if (is_index && valid_symbols[INDEX_SECTION_START]) {
    lexer->result_symbol = INDEX_SECTION_START;
    return true;
  }

  bool want_section = scanner->after_blank && !is_index && !line.truncated;
  Line next;
  bool have_next = false;
  bool next_is_blank = true;

  if ((want_section || valid_symbols[SIGNATURE_START]) &&
      consume_line_terminator(lexer)) {
    read_line(lexer, &next);
    have_next = true;
    next_is_blank = line_is_blank(&next);
  }

  // Section headers outrank every other reading of the line, because
  // `_read_to_next_section` stops at one.
  if (want_section && have_next && underline_matches(&next, title_len)) {
    int symbol = classify_section(title, title_len);
    if (!valid_symbols[symbol]) {
      // A section starts here but the grammar cannot accept this kind of
      // section yet; let the parser recover rather than mis-lex the line.
      return false;
    }
    lexer->result_symbol = symbol;
    return true;
  }

  if (valid_symbols[SIGNATURE_START]) {
    // Reading ahead is free: the mark is still at the line start, so nothing
    // consumed here becomes part of the zero-width token.
    char joined[LINE_CAPACITY];
    uint32_t joined_len = 0;
    bool overflow = line.truncated;
    Line current = line;
    bool have_current = true;

    while (have_current) {
      uint32_t s;
      uint32_t e;
      line_strip(&current, &s, &e);
      if (joined_len > 0 && joined_len + 1 < LINE_CAPACITY) {
        joined[joined_len++] = ' ';
      }
      for (uint32_t i = s; i < e && joined_len + 1 < LINE_CAPACITY; i++) {
        joined[joined_len++] = current.data[i];
      }
      overflow = overflow || current.truncated;

      if (have_next) {
        // The lookahead line was already read; consume it as the next
        // paragraph line unless it is the blank that ends the paragraph.
        have_current = !next_is_blank;
        current = next;
        have_next = false;
      } else {
        if (!consume_line_terminator(lexer)) break;
        read_line(lexer, &current);
        have_current = !line_is_blank(&current);
      }
    }

    if (!overflow && signature_match(joined, joined_len)) {
      lexer->result_symbol = SIGNATURE_START;
      return true;
    }
    // Not a signature: fall through, the mark is untouched.
  }

  if (valid_symbols[SEE_ALSO_ITEM_START] ||
      valid_symbols[SEE_ALSO_CONTINUATION_START]) {
    int match = see_also_line_match(line.data, line.len);
    // `if not description and line.startswith(' ')` -- an ASCII space, and only
    // when the line carries no description of its own.
    bool continuation = match != SEE_ALSO_MATCH_WITH_DESC && starts_with_space;

    if (continuation) {
      if (valid_symbols[SEE_ALSO_CONTINUATION_START]) {
        lexer->result_symbol = SEE_ALSO_CONTINUATION_START;
        return true;
      }
    } else if (match != SEE_ALSO_NO_MATCH &&
               valid_symbols[SEE_ALSO_ITEM_START]) {
      lexer->result_symbol = SEE_ALSO_ITEM_START;
      return true;
    }
    // Neither reading applies: numpydoc raises ParseError here, and we let the
    // parser produce an ERROR node instead.
    return false;
  }

  // `read_to_next_unindented_line`: an indented line continues the previous
  // entry's description, a column-0 line starts the next entry. The one
  // exception is the first line of a section body, which numpydoc reads as a
  // header whatever its indentation -- and that is exactly the position where
  // no description could be pending, so `INDENTED_LINE_START` is not valid.
  if (starts_with_indent) {
    if (valid_symbols[INDENTED_LINE_START]) {
      lexer->result_symbol = INDENTED_LINE_START;
      return true;
    }
    if (valid_symbols[ENTRY_START]) {
      scanner->header_end = (uint16_t)(indent_columns + line.content_end);
      lexer->result_symbol = ENTRY_START;
      return true;
    }
  } else if (valid_symbols[ENTRY_START]) {
    scanner->header_end = (uint16_t)(indent_columns + line.content_end);
    lexer->result_symbol = ENTRY_START;
    return true;
  }

  // Nothing special about this line; the regular lexer will read it as text.
  return false;
}

void *tree_sitter_numpydoc_external_scanner_create(void) {
  Scanner *scanner = (Scanner *)ts_malloc(sizeof(Scanner));
  scanner->after_blank = true;
  scanner->eof_newline_emitted = false;
  scanner->eof_emitted = false;
  scanner->header_end = 0;
  return scanner;
}

void tree_sitter_numpydoc_external_scanner_destroy(void *payload) {
  ts_free(payload);
}

unsigned tree_sitter_numpydoc_external_scanner_serialize(void *payload,
                                                         char *buffer) {
  Scanner *scanner = (Scanner *)payload;
  buffer[0] = (char)scanner->after_blank;
  buffer[1] = (char)scanner->eof_newline_emitted;
  buffer[2] = (char)scanner->eof_emitted;
  buffer[3] = (char)(scanner->header_end & 0xFF);
  buffer[4] = (char)((scanner->header_end >> 8) & 0xFF);
  return 5;
}

void tree_sitter_numpydoc_external_scanner_deserialize(void *payload,
                                                       const char *buffer,
                                                       unsigned length) {
  Scanner *scanner = (Scanner *)payload;
  if (length >= 5) {
    scanner->after_blank = (bool)buffer[0];
    scanner->eof_newline_emitted = (bool)buffer[1];
    scanner->eof_emitted = (bool)buffer[2];
    scanner->header_end = (uint16_t)((unsigned char)buffer[3]) |
                          (uint16_t)((unsigned char)buffer[4] << 8);
  } else {
    scanner->after_blank = true;
    scanner->eof_newline_emitted = false;
    scanner->eof_emitted = false;
    scanner->header_end = 0;
  }
}

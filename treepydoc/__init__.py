"""A numpydoc docstring parser built on tree-sitter.

`NumpyDocString` here is a drop-in replacement for
`numpydoc.docscrape.NumpyDocString`: same keys, same values, same warnings and
errors. The difference is that the parse is backed by a tree-sitter syntax tree,
so every piece of the result can be traced back to a byte range in the source.

Use `parse()` when you want the tree itself.
"""

from __future__ import annotations

import copy
import textwrap
import warnings
from collections import namedtuple
from collections.abc import Mapping

import tree_sitter
import tree_sitter_numpydoc

__all__ = ["NumpyDocString", "Parameter", "ParseError", "parse", "language"]

Parameter = namedtuple("Parameter", ["name", "type", "desc"])

_LANGUAGE = None
_PARSER = None


def language() -> tree_sitter.Language:
    """The compiled tree-sitter language for numpydoc docstrings."""
    global _LANGUAGE
    if _LANGUAGE is None:
        _LANGUAGE = tree_sitter.Language(tree_sitter_numpydoc.language())
    return _LANGUAGE


def _parser() -> tree_sitter.Parser:
    global _PARSER
    if _PARSER is None:
        _PARSER = tree_sitter.Parser(language())
    return _PARSER


def parse(docstring: str) -> tree_sitter.Tree:
    """Parse a docstring and return the raw tree-sitter tree.

    The docstring is dedented first, exactly as `NumpyDocString` does, so byte
    offsets in the tree refer to `textwrap.dedent(docstring)` rather than to the
    original string.
    """
    return _parser().parse(textwrap.dedent(docstring).encode("utf-8"))


class ParseError(Exception):
    def __str__(self):
        message = self.args[0]
        if hasattr(self, "docstring"):
            message = "%s in %r" % (message, self.docstring)
        return message


def strip_blank_lines(lines):
    """Remove leading and trailing blank lines from a list of lines."""
    while lines and not lines[0].strip():
        del lines[0]
    while lines and not lines[-1].strip():
        del lines[-1]
    return lines


def dedent_lines(lines):
    """Deindent a list of lines maximally."""
    return textwrap.dedent("\n".join(lines)).split("\n")


def _collapse_blanks(lines):
    """Collapse each run of blank lines to a single empty string.

    `_read_to_next_section` rebuilds a section body one paragraph at a time and
    inserts exactly one `''` between them, so a body that had three blank lines
    in the source comes back with one. Anything reading a section body has to
    reproduce that or it will disagree with numpydoc on descriptions containing
    vertical whitespace.
    """
    out = []
    pending_blank = False
    for line in lines:
        if line.strip():
            if pending_blank and out:
                out.append("")
            pending_blank = False
            out.append(line)
        else:
            pending_blank = True
    return out


class _Source:
    """Line-addressable view of the dedented docstring."""

    def __init__(self, text: str):
        self.text = text
        self.lines = text.split("\n")

    def node_lines(self, node) -> list[str]:
        start = node.start_point[0]
        end = node.end_point[0]
        # Line-oriented nodes end at column 0 of the line after their last one.
        if node.end_point[1] > 0:
            end += 1
        return self.lines[start:end]

    def node_text(self, node) -> str:
        if node is None:
            return ""
        return node.text.decode("utf-8")


def _child(node, type_):
    for c in node.named_children:
        if c.type == type_:
            return c
    return None


def _children(node, type_):
    return [c for c in node.named_children if c.type == type_]


class NumpyDocString(Mapping):
    """Parses a numpydoc string to an abstract representation."""

    sections = {
        "Signature": "",
        "Summary": [""],
        "Extended Summary": [],
        "Parameters": [],
        "Returns": [],
        "Yields": [],
        "Receives": [],
        "Raises": [],
        "Warns": [],
        "Other Parameters": [],
        "Attributes": [],
        "Methods": [],
        "See Also": [],
        "Notes": [],
        "Warnings": [],
        "References": "",
        "Examples": "",
        "index": {},
    }

    _param_sections = ("Parameters", "Other Parameters", "Attributes", "Methods")
    _typed_sections = ("Returns", "Yields", "Raises", "Warns", "Receives")

    def __init__(self, docstring, config=None):
        orig_docstring = docstring
        self._src = _Source(textwrap.dedent(docstring))
        self._tree = _parser().parse(self._src.text.encode("utf-8"))
        self._parsed_data = copy.deepcopy(self.sections)

        try:
            self._parse()
        except ParseError as e:
            e.docstring = orig_docstring
            raise

    # ------------------------------------------------------------- Mapping API

    def __getitem__(self, key):
        return self._parsed_data[key]

    def __setitem__(self, key, val):
        if key not in self._parsed_data:
            self._error_location("Unknown section %s" % key, error=False)
        else:
            self._parsed_data[key] = val

    def __iter__(self):
        return iter(self._parsed_data)

    def __len__(self):
        return len(self._parsed_data)

    @property
    def tree(self) -> tree_sitter.Tree:
        """The tree-sitter tree this result was derived from."""
        return self._tree

    # ----------------------------------------------------------------- parsing

    def _parse(self):
        root = self._tree.root_node
        preamble = _child(root, "preamble")

        # A See Also line that is neither a continuation nor a parsable item
        # leaves an ERROR node where the entry would have been; numpydoc raises
        # ParseError at exactly that point.
        previous = None
        for node in root.named_children:
            if node.type == "ERROR":
                if previous is not None and previous.type == "see_also_section":
                    line = self._src.lines[node.start_point[0]]
                    raise ParseError("%s is not a item name" % line)
            else:
                previous = node

        sections = [
            c for c in root.named_children
            if c is not preamble and c.type != "ERROR"
        ]

        if preamble is not None:
            self._parse_preamble(preamble, has_sections=bool(sections))
        elif not sections:
            # `_parse_summary` only returns early when the docstring opens on a
            # section. Otherwise it always assigns, even when the read came back
            # empty, which is how a blank docstring ends up with `Summary == []`
            # rather than the `['']` default.
            self["Summary"] = []

        self._validate(sections)

        for node in sections:
            if node.type == "index_section":
                self["index"] = self._parse_index(node)
                continue

            name = self._section_name(node)
            if self.get(name):
                self._error_location("The section %s appears twice" % name)

            if node.type == "parameters_section":
                self[name] = self._parse_param_list(node, single_element_is_type=False)
            elif node.type == "typed_section":
                self[name] = self._parse_param_list(node, single_element_is_type=True)
            elif node.type == "see_also_section":
                self[name] = self._parse_see_also(node)
            else:
                self[name] = self._section_body(node)

    def _section_name(self, node) -> str:
        raw = self._src.node_text(node.child_by_field_name("name"))
        return " ".join(s.capitalize() for s in raw.split(" "))

    def _section_body(self, node) -> list[str]:
        body = _child(node, "section_body")
        if body is None:
            return []
        return strip_blank_lines(_collapse_blanks(self._src.node_lines(body)))

    def _validate(self, sections):
        names = set()
        for node in sections:
            if node.type != "index_section":
                names.add(self._section_name(node))

        has_returns = "Returns" in names
        has_yields = "Yields" in names
        if has_returns and has_yields:
            raise ValueError("Docstring contains both a Returns and Yields section.")
        if not has_yields and "Receives" in names:
            raise ValueError("Docstring contains a Receives section but not Yields.")

    # ---------------------------------------------------------------- preamble

    def _parse_preamble(self, preamble, has_sections: bool):
        signatures = _children(preamble, "signature")
        summary = _child(preamble, "summary")
        extended = _child(preamble, "extended_summary")

        if signatures:
            lines = self._src.node_lines(signatures[-1])
            self["Signature"] = " ".join(s.strip() for s in lines).strip()

        if summary is not None:
            self["Summary"] = self._src.node_lines(summary)
        elif signatures and has_sections:
            # `_parse_summary` breaks out of its loop as soon as a signature is
            # followed by a section, and then assigns whatever paragraph it last
            # read -- the signature itself -- to Summary.
            self["Summary"] = self._src.node_lines(signatures[-1])
        elif signatures:
            # The loop instead ran off the end of the docstring and assigned the
            # empty read to Summary.
            self["Summary"] = []

        if extended is not None:
            self["Extended Summary"] = strip_blank_lines(
                _collapse_blanks(self._src.node_lines(extended))
            )

    # ------------------------------------------------------------- param lists

    def _parse_param_list(self, node, single_element_is_type: bool):
        entry_type = "typed_entry" if single_element_is_type else "parameter"
        params = []
        for entry in _children(node, entry_type):
            header = entry.named_child(0)
            name = self._src.node_text(header.child_by_field_name("name"))
            type_ = self._src.node_text(header.child_by_field_name("type"))

            desc_node = _child(entry, "description")
            if desc_node is None:
                desc = []
            else:
                desc = _collapse_blanks(self._src.node_lines(desc_node))
                desc = dedent_lines(desc)
                desc = strip_blank_lines(desc)

            params.append(Parameter(name, type_, desc))
        return params

    # ---------------------------------------------------------------- see also

    def _parse_see_also(self, node):
        # numpydoc raises when a line is neither a continuation nor a parsable
        # item; the grammar records that as an ERROR node instead.
        for child in node.children:
            if child.type == "ERROR" or child.is_missing:
                line = self._src.lines[child.start_point[0]]
                raise ParseError("%s is not a item name" % line)

        items = []
        for entry in _children(node, "see_also_entry"):
            funcs = []
            targets = _child(entry, "see_also_targets")
            for target in _children(targets, "see_also_target"):
                inner = target.named_child(0)
                name = self._src.node_text(inner.child_by_field_name("name"))
                role = (
                    self._src.node_text(inner.child_by_field_name("role"))
                    if inner.type == "role_target"
                    else None
                )
                funcs.append((name, role))

            trailing = targets.child_by_field_name("trailing")
            description_node = _child(entry, "see_also_description")
            description = None
            if description_node is not None:
                text = _child(description_node, "text")
                description = self._src.node_text(text) if text is not None else None

            if trailing is not None and description:
                self._error_location(
                    'Unexpected comma or period after function list at index %d of '
                    'line "%s"'
                    % (
                        # numpydoc's `trailing` group is the single punctuation
                        # character; ours may also cover the space after it.
                        trailing.start_point[1] + 1,
                        self._src.lines[entry.start_point[0]],
                    ),
                    error=False,
                )

            rest = list(filter(None, [description]))
            for cont in _children(entry, "see_also_continuation"):
                rest.append(self._src.node_text(_child(cont, "text")).strip())

            items.append((funcs, rest))
        return items

    # ------------------------------------------------------------------- index

    def _parse_index(self, node):
        def strip_each_in(lst):
            return [s.strip() for s in lst]

        out = {}
        marker = self._src.node_text(node.child_by_field_name("marker"))
        parts = marker.split("::")
        if len(parts) > 1:
            out["default"] = strip_each_in(parts[1].split(","))[0]

        for field in _children(node, "index_field"):
            line = self._src.node_text(field.named_child(0)).split(":")
            if len(line) > 2:
                out[line[1]] = strip_each_in(line[2].split(","))
        return out

    # ------------------------------------------------------------------ errors

    def _error_location(self, msg, error=True):
        if hasattr(self, "_obj"):
            import inspect

            try:
                filename = inspect.getsourcefile(self._obj)
            except TypeError:
                filename = None
            msg = msg + (" in the docstring of %s in %s." % (self._obj, filename))
        if error:
            raise ValueError(msg)
        else:
            warnings.warn(msg)

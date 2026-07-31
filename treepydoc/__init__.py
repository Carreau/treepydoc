"""A numpydoc docstring parser built on tree-sitter.

`NumpyDocString` here is a drop-in replacement for
`numpydoc.docscrape.NumpyDocString`: same keys, same values, same warnings and
errors. The difference is that the parse is backed by a tree-sitter syntax tree,
so every piece of the result can be traced back to a byte range in the source.

Use `parse()` when you want the tree itself.
"""

from __future__ import annotations

import copy
import inspect
import pydoc
import sys
import textwrap
import warnings
from collections import namedtuple
from collections.abc import Callable, Mapping

import tree_sitter_numpydoc

import tree_sitter

__all__ = [
    "NumpyDocString",
    "FunctionDoc",
    "ClassDoc",
    "ObjDoc",
    "Parameter",
    "ParseError",
    "get_doc_object",
    "parse",
    "language",
    "dedent_lines",
    "strip_blank_lines",
    "indent",
    "header",
]

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


def indent(str, indent=4):
    indent_str = " " * indent
    if str is None:
        return indent_str
    lines = str.split("\n")
    return "\n".join(indent_str + line for line in lines)


def header(text, style="-"):
    return text + "\n" + style * len(text) + "\n"


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


class _Reader:
    """numpydoc's line `Reader`, provided for code that reaches into `_doc`.

    Nothing in treepydoc's own parse uses this. It exists because third-party
    code drives the reference parser's private line reader directly --
    `numpydoc.validate.Validator.section_titles` calls `doc._doc.reset()`,
    `doc._doc.eof()` and `doc._read_to_next_section()` -- and a parser that
    cannot be swapped in without breaking `numpydoc lint` is not much of a
    drop-in replacement. Ported faithfully so the chunking matches.
    """

    def __init__(self, data):
        if isinstance(data, list):
            self._str = data
        else:
            self._str = data.split("\n")
        self.reset()

    def __getitem__(self, n):
        return self._str[n]

    def reset(self):
        self._l = 0

    def read(self):
        if not self.eof():
            out = self[self._l]
            self._l += 1
            return out
        return ""

    def seek_next_non_empty_line(self):
        for line in self[self._l:]:
            if line.strip():
                break
            self._l += 1

    def eof(self):
        return self._l >= len(self._str)

    def read_to_condition(self, condition_func):
        start = self._l
        for line in self[start:]:
            if condition_func(line):
                return self[start:self._l]
            self._l += 1
            if self.eof():
                return self[start:self._l + 1]
        return []

    def read_to_next_empty_line(self):
        self.seek_next_non_empty_line()

        def is_empty(line):
            return not line.strip()

        return self.read_to_condition(is_empty)

    def read_to_next_unindented_line(self):
        def is_unindented(line):
            return line.strip() and (len(line.lstrip()) == len(line))

        return self.read_to_condition(is_unindented)

    def peek(self, n=0):
        if self._l + n < len(self._str):
            return self[self._l + n]
        return ""

    def is_empty(self):
        return not "".join(self._str).strip()


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


def _see_also_item_parses(line: str) -> bool:
    """Would `_parse_see_also` accept this line as an item?

    Answered by parsing it as a one-line See Also body, so the rule stays in
    one place -- the scanner -- instead of being duplicated here.
    """
    probe = "See Also\n--------\n%s\n" % line
    return not _parser().parse(probe.encode("utf-8")).root_node.has_error


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

    # What `_str_see_also` renders for an entry with no description.
    empty_description = ".."

    def __init__(self, docstring, config=None):
        orig_docstring = docstring
        self._src = _Source(textwrap.dedent(docstring))
        self._tree = _parser().parse(self._src.text.encode("utf-8"))
        self._parsed_data = copy.deepcopy(self.sections)
        self._doc_reader = None

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

    # ------------------------------------------- reference-parser internals

    # `numpydoc.validate` drives the reference parser's private line reader, so
    # these exist to keep that working. They take no part in the parse.

    @property
    def _doc(self) -> _Reader:
        if self._doc_reader is None:
            self._doc_reader = _Reader(list(self._src.lines))
        return self._doc_reader

    def _is_at_section(self) -> bool:
        self._doc.seek_next_non_empty_line()
        if self._doc.eof():
            return False
        l1 = self._doc.peek().strip()
        if l1.startswith(".. index::"):
            return True
        l2 = self._doc.peek(1).strip()
        return l2.startswith("-" * len(l1)) or l2.startswith("=" * len(l1))

    def _read_to_next_section(self) -> list[str]:
        section = self._doc.read_to_next_empty_line()
        while not self._is_at_section() and not self._doc.eof():
            if not self._doc.peek(-1).strip():  # previous line was empty
                section += [""]
            section += self._doc.read_to_next_empty_line()
        return section

    # ----------------------------------------------------------------- parsing

    def _parse(self):
        root = self._tree.root_node
        preamble = _child(root, "preamble")

        # A See Also line that is neither a continuation nor a parsable item
        # makes numpydoc raise ParseError. Here it leaves an ERROR node, which
        # may swallow the whole section, so the offending line is located
        # explicitly rather than read off the error's position.
        error = self._see_also_parse_error()
        if error is not None:
            raise error

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

    def _see_also_parse_error(self):
        """The `ParseError` numpydoc would raise for a See Also body, or None.

        `_parse_see_also` rejects a line that is neither indented (a
        continuation, which never fails) nor matched by its item regex. Rather
        than reimplement that regex, each suspect line is probed through the
        grammar itself, which is where the rule already lives.
        """
        if not self._tree.root_node.has_error:
            return None

        for title_row in self._see_also_title_rows():
            for row in range(title_row + 2, len(self._src.lines)):
                line = self._src.lines[row]
                if not line.strip():
                    continue
                if line.startswith(" ") or line.startswith("\t"):
                    continue  # a continuation; numpydoc never fails on one
                if self._is_section_header(row):
                    break  # the body ended before anything went wrong
                if not _see_also_item_parses(line):
                    return ParseError("%s is not a item name" % line)
        return None

    def _see_also_title_rows(self) -> list[int]:
        """Rows holding a See Also title, whether or not the section parsed."""
        rows = []
        stack = [self._tree.root_node]
        while stack:
            node = stack.pop()
            if node.type == "section_name":
                name = " ".join(
                    part.capitalize()
                    for part in self._src.node_text(node).split(" ")
                )
                if name == "See Also":
                    rows.append(node.start_point[0])
            stack.extend(node.children)
        return sorted(rows)

    def _is_section_header(self, row: int) -> bool:
        """`_is_at_section`'s underline rule, applied at one row."""
        title = self._src.lines[row].strip()
        if row + 1 >= len(self._src.lines) or not title:
            return False
        underline = self._src.lines[row + 1].strip()
        return underline.startswith("-" * len(title)) or underline.startswith(
            "=" * len(title)
        )

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

    # ------------------------------------------------- string conversion

    # These reproduce `docscrape.py`'s rendering exactly, because
    # `numpydoc.docscrape_sphinx.SphinxDocString` subclasses `NumpyDocString`
    # and calls into them (`_str_header`, `_str_indent`, `_str_see_also`, ...)
    # while overriding others. Rendering has to come from the same place as the
    # parse for a Sphinx build to be byte-identical.

    def _str_header(self, name, symbol="-"):
        return [name, len(name) * symbol]

    def _str_indent(self, doc, indent=4):
        out = []
        for line in doc:
            out += [" " * indent + line]
        return out

    def _str_signature(self):
        if self["Signature"]:
            return [self["Signature"].replace("*", r"\*")] + [""]
        else:
            return [""]

    def _str_summary(self):
        if self["Summary"]:
            return self["Summary"] + [""]
        else:
            return []

    def _str_extended_summary(self):
        if self["Extended Summary"]:
            return self["Extended Summary"] + [""]
        else:
            return []

    def _str_param_list(self, name):
        out = []
        if self[name]:
            out += self._str_header(name)
            for param in self[name]:
                parts = []
                if param.name:
                    parts.append(param.name)
                if param.type:
                    parts.append(param.type)
                out += [" : ".join(parts)]
                if param.desc and "".join(param.desc).strip():
                    out += self._str_indent(param.desc)
            out += [""]
        return out

    def _str_section(self, name):
        out = []
        if self[name]:
            out += self._str_header(name)
            out += self[name]
            out += [""]
        return out

    def _str_see_also(self, func_role):
        if not self["See Also"]:
            return []
        out = []
        out += self._str_header("See Also")
        out += [""]
        last_had_desc = True
        for funcs, desc in self["See Also"]:
            assert isinstance(funcs, list)
            links = []
            for func, role in funcs:
                if role:
                    link = ":%s:`%s`" % (role, func)
                elif func_role:
                    link = ":%s:`%s`" % (func_role, func)
                else:
                    link = "`%s`_" % func
                links.append(link)
            link = ", ".join(links)
            out += [link]
            if desc:
                out += self._str_indent([" ".join(desc)])
                last_had_desc = True
            else:
                last_had_desc = False
                out += self._str_indent([self.empty_description])

        if last_had_desc:
            out += [""]
        out += [""]
        return out

    def _str_index(self):
        idx = self["index"]
        out = []
        output_index = False
        default_index = idx.get("default", "")
        if default_index:
            output_index = True
        out += [".. index:: %s" % default_index]
        for section, references in idx.items():
            if section == "default":
                continue
            output_index = True
            out += ["   :%s: %s" % (section, ", ".join(references))]
        if output_index:
            return out
        else:
            return ""

    def __str__(self, func_role=""):
        out = []
        out += self._str_signature()
        out += self._str_summary()
        out += self._str_extended_summary()
        for param_list in (
            "Parameters",
            "Returns",
            "Yields",
            "Receives",
            "Other Parameters",
            "Raises",
            "Warns",
        ):
            out += self._str_param_list(param_list)
        out += self._str_section("Warnings")
        out += self._str_see_also(func_role)
        for s in ("Notes", "References", "Examples"):
            out += self._str_section(s)
        for param_list in ("Attributes", "Methods"):
            out += self._str_param_list(param_list)
        out += self._str_index()
        return "\n".join(out)


class FunctionDoc(NumpyDocString):
    def __init__(self, func, role="func", doc=None, config=None):
        self._f = func
        self._role = role  # e.g. "func" or "meth"

        if doc is None:
            if func is None:
                raise ValueError("No function or docstring given")
            doc = inspect.getdoc(func) or ""
        NumpyDocString.__init__(self, doc, config)

    def get_func(self):
        func_name = getattr(self._f, "__name__", self.__class__.__name__)
        if inspect.isclass(self._f):
            func = getattr(self._f, "__call__", self._f.__init__)
        else:
            func = self._f
        return func, func_name

    def __str__(self):
        out = ""

        func, func_name = self.get_func()

        roles = {"func": "function", "meth": "method"}

        if self._role:
            if self._role not in roles:
                print("Warning: invalid role %s" % self._role)
            out += ".. %s:: %s\n    \n\n" % (roles.get(self._role, ""), func_name)

        out += super(FunctionDoc, self).__str__(func_role=self._role)
        return out


class ClassDoc(NumpyDocString):

    extra_public_methods = ["__call__"]

    def __init__(self, cls, doc=None, modulename="", func_doc=FunctionDoc,
                 config=None):
        if not inspect.isclass(cls) and cls is not None:
            raise ValueError("Expected a class or None, but got %r" % cls)
        self._cls = cls

        if "sphinx" in sys.modules:
            from sphinx.ext.autodoc import ALL
        else:
            ALL = object()

        config = {} if config is None else config
        self.show_inherited_members = config.get("show_inherited_class_members", True)

        if modulename and not modulename.endswith("."):
            modulename += "."
        self._mod = modulename

        if doc is None:
            if cls is None:
                raise ValueError("No class or documentation string given")
            doc = pydoc.getdoc(cls)

        NumpyDocString.__init__(self, doc)

        _members = config.get("members", [])
        if _members is ALL:
            _members = None
        _exclude = config.get("exclude-members", [])

        if config.get("show_class_members", True) and _exclude is not ALL:

            def splitlines_x(s):
                if not s:
                    return []
                else:
                    return s.splitlines()

            for field, items in [
                ("Methods", self.methods),
                ("Attributes", self.properties),
            ]:
                if not self[field]:
                    doc_list = []
                    for name in sorted(items):
                        if name in _exclude or (_members and name not in _members):
                            continue
                        try:
                            doc_item = pydoc.getdoc(getattr(self._cls, name))
                            doc_list.append(Parameter(name, "", splitlines_x(doc_item)))
                        except AttributeError:
                            pass  # method doesn't exist
                    self[field] = doc_list

    @property
    def methods(self):
        if self._cls is None:
            return []
        return [
            name
            for name, func in inspect.getmembers(self._cls)
            if (
                (not name.startswith("_") or name in self.extra_public_methods)
                and isinstance(func, Callable)
                and self._is_show_member(name)
            )
        ]

    @property
    def properties(self):
        if self._cls is None:
            return []
        return [
            name
            for name, func in inspect.getmembers(self._cls)
            if (
                not name.startswith("_")
                and (
                    func is None
                    or isinstance(func, property)
                    or inspect.isdatadescriptor(func)
                )
                and self._is_show_member(name)
            )
        ]

    def _is_show_member(self, name):
        if self.show_inherited_members:
            return True  # show all class members
        if name not in self._cls.__dict__:
            return False  # class member is inherited, we do not show it
        return True


class ObjDoc(NumpyDocString):
    """Anything that is neither a class nor a callable."""

    def __init__(self, obj, doc=None, config=None):
        self._f = obj
        NumpyDocString.__init__(self, doc or "", config=config)


def get_doc_object(obj, what=None, doc=None, config=None):
    """Dispatch to the right documenter, the way numpydoc's Sphinx layer does.

    This is the plain-text counterpart of
    `numpydoc.docscrape_sphinx.get_doc_object`; see `treepydoc.sphinx` for the
    Sphinx-rendering one.
    """
    if what is None:
        if inspect.isclass(obj):
            what = "class"
        elif inspect.ismodule(obj):
            what = "module"
        elif isinstance(obj, Callable):
            what = "function"
        else:
            what = "object"

    config = {} if config is None else config

    if what == "class":
        return ClassDoc(obj, func_doc=FunctionDoc, doc=doc, config=config)
    elif what in ("function", "method"):
        return FunctionDoc(obj, doc=doc, config=config)
    else:
        if doc is None:
            doc = pydoc.getdoc(obj)
        return ObjDoc(obj, doc, config=config)

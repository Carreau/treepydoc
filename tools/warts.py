"""Find live instances of numpydoc's parsing warts in real source trees.

DESIGN.md lists the places where `NumpyDocString` quietly does the wrong thing.
This answers the question that decides whether any of them is worth an upstream
patch: *does it happen to anybody?*

Each docstring is located with tree-sitter-python (so every finding has a real
`file:line`), parsed with treepydoc (so the offending token has a range), and
then **confirmed against numpydoc itself** -- a pattern match alone is not a
finding, the reported consequence has to be observable in what
`NumpyDocString` actually returns. Anything the two parsers disagree about is
reported separately as a treepydoc bug rather than a numpydoc one.

Usage:
    python3 tools/warts.py ~/numpy-src ~/scipy-src
    python3 tools/warts.py ~/numpy-src --kind unknown-section --show 20
    python3 tools/warts.py ~/numpy-src --json findings.json
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import textwrap
import warnings
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import tree_sitter_python

import tree_sitter
import treepydoc

REPO = Path(__file__).resolve().parent.parent
INJECTIONS = REPO / "editors" / "nvim" / "queries" / "python" / "injections.scm"

# Directories that are never anybody's public documentation.
SKIP_DIRS = {
    ".git",
    "build",
    "dist",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    "_build",
    "vendored",
    "vendor",
    "third_party",
}

SPACED_INDEX = re.compile(r"^\s*\.\.\s+index\s*::")


@dataclass(frozen=True)
class Finding:
    kind: str
    package: str
    path: str
    line: int  # 1-based, in the file
    column: int  # 0-based, in the file
    evidence: str
    detail: str
    # sha1 of the docstring the finding came from. Stable when the enclosing
    # file is edited around it, which `path:line` is not -- so it is what the
    # weekly issue sync keys on.
    fingerprint: str


# ---------------------------------------------------------------------------
# What each wart costs, in one line, for the report header.
# ---------------------------------------------------------------------------

KINDS = {
    "unknown-section": "content dropped: __setitem__ warns and discards the body",
    "misspelled-section": "same, and the title is one edit from a real section name",
    "unstripped-field": "name or type keeps stray whitespace, never comparing equal",
    "dangling-separator": "a header ending ' :' declared a type and lost it silently",
    "empty-section": "an empty body becomes one blank Parameter rather than none",
    "underline-length": "underline length does not match the title (numpydoc warns)",
    "spaced-index": "'.. index ::' is not recognised; the directive is read as prose",
    "numpydoc-raises": "numpydoc raises on this docstring",
    "parser-disagreement": "treepydoc and numpydoc disagree -- our bug, not numpydoc's",
}


def iter_python_files(roots):
    """Yield (label, path); the label is the tree the file came from."""
    for root in roots:
        root = Path(root)
        label = root.name
        if root.is_file():
            yield label, root
            continue
        for path in sorted(root.rglob("*.py")):
            if SKIP_DIRS & set(path.parts):
                continue
            yield label, path


def docstring_query():
    language = tree_sitter.Language(tree_sitter_python.language())
    return language, tree_sitter.Query(language, INJECTIONS.read_text())


def iter_docstrings(path, language, query):
    """Yield (text, start_row, start_column) for every docstring in a file."""
    try:
        source = path.read_bytes()
    except OSError:
        return
    tree = tree_sitter.Parser(language).parse(source)
    captured = tree_sitter.QueryCursor(query).captures(tree.root_node)
    for node in captured.get("injection.content", []):
        row, column = node.start_point
        yield node.text.decode("utf-8", "replace"), row, column


def find_all(node, types):
    if node.type in types:
        yield node
    for child in node.children:
        yield from find_all(child, types)


def sections_of(node):
    """Yield every section node, whatever its flavour."""
    yield from find_all(
        node,
        {
            "parameters_section",
            "typed_section",
            "see_also_section",
            "generic_section",
            "index_section",
        },
    )


def numpydoc_parse(text):
    """Parse with numpydoc, returning (doc, warnings, exception)."""
    import numpydoc.docscrape as docscrape

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            doc = docscrape.NumpyDocString(text)
        except Exception as exc:  # noqa: BLE001 - the exception *is* the finding
            return None, [str(w.message) for w in caught], exc
    return doc, [str(w.message) for w in caught], None


def known_sections():
    import numpydoc.docscrape as docscrape

    return list(docscrape.NumpyDocString.sections)


def scan_docstring(text, known):
    """Yield (kind, row, column, evidence, detail) for one docstring.

    Rows and columns are relative to the *dedented* docstring; the caller maps
    them back. `textwrap.dedent` never adds or removes lines, so the row is
    already right; only the column has to be recovered.
    """
    doc, caught, exc = numpydoc_parse(text)
    if exc is not None:
        yield "numpydoc-raises", 0, 0, type(exc).__name__, str(exc)
        return

    tree = treepydoc.parse(text)
    root = tree.root_node

    # A treepydoc bug would make everything below untrustworthy, so check first.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ours = treepydoc.NumpyDocString(text)
        differing = [k for k in known if ours[k] != doc[k]]
    except Exception as our_exc:  # noqa: BLE001
        yield "parser-disagreement", 0, 0, type(our_exc).__name__, str(our_exc)
        return
    if differing:
        yield "parser-disagreement", 0, 0, ", ".join(differing), "keys differ"
        return

    for section in sections_of(root):
        title_node = section.child_by_field_name("name")
        underline = section.child_by_field_name("underline")
        if title_node is None:
            continue
        title = title_node.text.decode()
        row, col = title_node.start_point

        if section.type == "generic_section" and title not in known:
            # numpydoc's __setitem__ warns and throws the body away.
            near = difflib.get_close_matches(title, known, n=1, cutoff=0.75)
            confirmed = any(f"Unknown section {title}" in w for w in caught)
            if confirmed:
                if near and near[0] != title:
                    yield (
                        "misspelled-section",
                        row,
                        col,
                        title,
                        f"did you mean {near[0]!r}? the body is discarded",
                    )
                else:
                    yield "unknown-section", row, col, title, "the body is discarded"

        if underline is not None:
            want, got = len(title), len(underline.text.decode())
            if want != got:
                r, c = underline.start_point
                yield (
                    "underline-length",
                    r,
                    c,
                    underline.text.decode(),
                    f"{got} characters under a {want}-character title",
                )

        if section.type in ("parameters_section", "typed_section"):
            kinds = ("parameter", "typed_entry")
            entries = [c for c in section.children if c.type in kinds]
            if not entries and doc[title] == [("", "", [""])]:
                yield "empty-section", row, col, title, "yields one blank Parameter"

    for node in find_all(root, {"name", "type"}):
        text_ = node.text.decode()
        if text_ != text_.strip():
            r, c = node.start_point
            yield (
                "unstripped-field",
                r,
                c,
                text_,
                f"numpydoc keeps this as {text_!r}, not {text_.strip()!r}",
            )

    for node in find_all(root, {"dangling_separator"}):
        r, c = node.start_point
        header = node.parent.text.decode() if node.parent else ""
        detail = "the ' :' is dropped and the type is ''"
        yield "dangling-separator", r, c, header, detail

    for i, line in enumerate(textwrap.dedent(text).splitlines()):
        if SPACED_INDEX.match(line) and ".. index::" not in line:
            indent = len(line) - len(line.lstrip())
            yield "spaced-index", i, indent, line.strip(), "read as prose"


def scan(roots, known):
    language, query = docstring_query()
    findings = []
    files = 0
    docstrings = 0
    for label, path in iter_python_files(roots):
        files += 1
        for text, start_row, start_col in iter_docstrings(path, language, query):
            if not text.strip():
                continue
            docstrings += 1
            fingerprint = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
            raw_lines = text.splitlines()
            for kind, row, col, evidence, detail in scan_docstring(text, known):
                # The docstring's first line starts after the opening quotes;
                # every later line is at its own column in the file. Recover the
                # column by finding the evidence in the raw line, since the tree
                # is positioned in the dedented copy.
                line_in_file = start_row + row
                raw = raw_lines[row] if row < len(raw_lines) else ""
                found = raw.find(evidence.splitlines()[0]) if evidence else -1
                column = found if found >= 0 else (col if row else start_col + col)
                findings.append(
                    Finding(
                        kind, label, str(path), line_in_file + 1,
                        column, evidence, detail, fingerprint,
                    )
                )
    return findings, files, docstrings


def report(findings, roots, files, docstrings, show, only):
    by_kind = defaultdict(list)
    for f in findings:
        by_kind[f.kind].append(f)

    print(f"scanned {docstrings} docstrings in {files} files under:")
    for root in roots:
        print(f"  {root}")
    print()

    if not findings:
        print("no findings.")
        return

    width = max(len(k) for k in by_kind)
    print("summary")
    for kind, group in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        per_pkg = Counter(f.package for f in group)
        spread = ", ".join(f"{n} {p}" for p, n in per_pkg.most_common(8))
        print(f"  {kind:<{width}}  {len(group):>5}   {spread}")
    print()
    for kind, group in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        if only and kind not in only:
            continue
        print(f"--- {kind}: {KINDS.get(kind, '')}")
        for f in group[:show]:
            print(f"  {f.path}:{f.line}:{f.column}")
            print(f"      {f.evidence.strip()[:100]}")
            print(f"      -> {f.detail}")
        if len(group) > show:
            print(f"  ... and {len(group) - show} more")
        print()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("roots", nargs="+", help="source trees or files to scan")
    ap.add_argument("--show", type=int, default=5, help="examples per kind")
    ap.add_argument("--kind", action="append", help="only detail these kinds")
    ap.add_argument("--json", metavar="PATH", help="also write every finding as JSON")
    args = ap.parse_args()

    try:
        known = known_sections()
    except ImportError:
        sys.exit("numpydoc is required: every finding is confirmed against it")

    findings, files, docstrings = scan(args.roots, known)
    report(findings, args.roots, files, docstrings, args.show, set(args.kind or ()))

    if args.json:
        Path(args.json).write_text(json.dumps([asdict(f) for f in findings], indent=2))
        print(f"wrote {len(findings)} findings to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

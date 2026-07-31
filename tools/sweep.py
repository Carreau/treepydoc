"""Differential test over every docstring in a set of installed packages.

The curated corpus proves the grammar handles the cases numpydoc's own tests
care about. This proves it handles what people actually write: it walks the
public API of numpy, scipy and pandas, feeds every docstring to both parsers,
and reports any disagreement.

Usage:
    python3 tools/sweep.py [numpy scipy pandas ...] [--limit N] [--show N]
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from conformance import compare  # noqa: E402

DEFAULT_PACKAGES = ["numpy", "scipy", "pandas"]


def iter_docstrings(package_names):
    """Yield (qualified_name, docstring) for everything importable and public."""
    seen_docs = set()

    for package_name in package_names:
        try:
            package = importlib.import_module(package_name)
        except Exception:  # noqa: BLE001 - a missing package is not a failure
            continue

        modules = [package]
        if hasattr(package, "__path__"):
            for info in pkgutil.walk_packages(package.__path__, package_name + "."):
                if any(
                    part in info.name
                    for part in (".tests", ".testing", "__main__", ".setup", "f2py")
                ):
                    continue
                try:
                    modules.append(importlib.import_module(info.name))
                except BaseException:  # noqa: BLE001 - some submodules exit
                    continue

        for module in modules:
            for name, obj in vars(module).items():
                if name.startswith("_"):
                    continue
                try:
                    doc = inspect.getdoc(obj)
                except Exception:  # noqa: BLE001
                    continue
                if not doc or len(doc) < 20:
                    continue
                key = hash(doc)
                if key in seen_docs:
                    continue
                seen_docs.add(key)
                yield f"{getattr(module, '__name__', '?')}.{name}", doc

                if inspect.isclass(obj):
                    for attr in dir(obj):
                        if attr.startswith("_"):
                            continue
                        try:
                            doc = inspect.getdoc(getattr(obj, attr))
                        except Exception:  # noqa: BLE001
                            continue
                        if not doc or len(doc) < 20:
                            continue
                        key = hash(doc)
                        if key in seen_docs:
                            continue
                        seen_docs.add(key)
                        yield f"{getattr(module, '__name__', '?')}.{name}.{attr}", doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="*", default=DEFAULT_PACKAGES)
    ap.add_argument("--limit", type=int, default=0, help="stop after N docstrings")
    ap.add_argument("--show", type=int, default=5, help="how many diffs to print")
    args = ap.parse_args()

    warnings.simplefilter("ignore")
    # Importing every submodule of a scientific package runs a lot of code that
    # was never meant to be imported; some of it parses `sys.argv`.
    sys.argv = sys.argv[:1]

    checked = 0
    skipped = 0
    mismatches = []

    for name, doc in iter_docstrings(args.packages or DEFAULT_PACKAGES):
        if args.limit and checked >= args.limit:
            break
        try:
            diffs = compare(doc)
        except Exception as exc:  # noqa: BLE001
            # numpydoc itself rejects a fair number of real docstrings; those
            # are only interesting if the two implementations disagree about it.
            if _both_raise(doc, exc):
                skipped += 1
                continue
            mismatches.append((name, doc, [("<exception>", "?", repr(exc))]))
            checked += 1
            continue
        checked += 1
        if diffs:
            mismatches.append((name, doc, diffs))

    for name, doc, diffs in mismatches[: args.show]:
        print(f"\n{'=' * 70}\nMISMATCH {name}\n{'=' * 70}")
        print(repr(doc[:500]))
        for key, want, got in diffs:
            print(f"--- {key} ---")
            print(f"  numpydoc : {want!r}"[:400])
            print(f"  treepydoc: {got!r}"[:400])

    if len(mismatches) > args.show:
        print(f"\n... and {len(mismatches) - args.show} more")

    print(
        f"\nchecked {checked} docstrings, "
        f"{checked - len(mismatches)} identical, "
        f"{len(mismatches)} differ "
        f"({skipped} rejected by both parsers)"
    )
    return 1 if mismatches else 0


def _both_raise(doc, exc):
    """True when numpydoc rejects this docstring the same way treepydoc did."""
    from numpydoc import docscrape

    try:
        docscrape.NumpyDocString(doc)
    except Exception as ref:  # noqa: BLE001
        return type(ref).__name__ == type(exc).__name__
    return False


if __name__ == "__main__":
    sys.exit(main())

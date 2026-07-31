"""Differential test: treepydoc against numpydoc.docscrape, case by case.

Every entry in the corpus is parsed by both implementations and the resulting
mappings are compared key by key. Anything that differs is reported with the
docstring that produced it, so a divergence is always reproducible.

Usage:
    python3 tools/conformance.py [-v] [--only NAME]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import corpus  # noqa: E402

import treepydoc  # noqa: E402
from numpydoc import docscrape  # noqa: E402

SECTION_KEYS = list(docscrape.NumpyDocString.sections)


def normalise(value):
    """Make the two implementations' values structurally comparable."""
    if isinstance(value, list):
        return [normalise(v) for v in value]
    if isinstance(value, tuple):
        return tuple(normalise(v) for v in value)
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in value.items()}
    return value


def compare(text):
    """Return a list of (key, expected, actual) differences."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = docscrape.NumpyDocString(text)
        actual = treepydoc.NumpyDocString(text)

    diffs = []
    for key in SECTION_KEYS:
        want = normalise(expected[key])
        got = normalise(actual[key])
        if want != got:
            diffs.append((key, want, got))
    return diffs


def check_raising(text, exc_name):
    """Both implementations must reject the same docstrings the same way."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            treepydoc.NumpyDocString(text)
        except Exception as exc:  # noqa: BLE001 - we are comparing behaviour
            got = type(exc).__name__
            return None if got == exc_name else f"raised {got}, expected {exc_name}"
        return f"did not raise, expected {exc_name}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--only", help="run a single named case")
    args = ap.parse_args()

    cases = corpus.CORPUS
    raising = corpus.RAISING_CORPUS
    if args.only:
        cases = [c for c in cases if c[0] == args.only]
        raising = [c for c in raising if c[0] == args.only]

    failures = []
    for name, text in cases:
        try:
            diffs = compare(text)
        except Exception as exc:  # noqa: BLE001
            failures.append((name, text, [("<exception>", "no exception", repr(exc))]))
            continue
        if diffs:
            failures.append((name, text, diffs))
        elif args.verbose:
            print(f"ok   {name}")

    for name, text, exc_name in raising:
        problem = check_raising(text, exc_name)
        if problem:
            failures.append((name, text, [("<raises>", exc_name, problem)]))
        elif args.verbose:
            print(f"ok   {name} (raises {exc_name})")

    total = len(cases) + len(raising)
    if not failures:
        print(f"\n{total}/{total} cases match numpydoc exactly.")
        return 0

    for name, text, diffs in failures:
        print(f"\n{'=' * 70}\nFAIL {name}\n{'=' * 70}")
        print("--- docstring ---")
        print(repr(text[:600]))
        for key, want, got in diffs:
            print(f"--- {key} ---")
            print(f"  numpydoc : {want!r}")
            print(f"  treepydoc: {got!r}")

    print(f"\n{total - len(failures)}/{total} cases match; {len(failures)} differ.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

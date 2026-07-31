"""Run numpydoc's own test suite twice: as-is, and with treepydoc swapped in.

The suite is the most demanding conformance test available. It was written to
pin down numpydoc's behaviour, not to be easy to pass, and it asserts on parse
results, rendered reStructuredText, warning text, exception messages and Sphinx
output alike. If treepydoc can be dropped underneath it and every single test
lands the same way, the parsers are interchangeable in the only sense that
matters to a user.

Comparing the two runs is the point. numpydoc checkouts have pre-existing
failures for reasons that have nothing to do with the parser -- an old test file
against a modern Python, a newer Sphinx than the pinned one -- so the bar is not
"everything passes", it is "the same tests pass and the same tests fail".

Usage:
    python3 tools/run_numpydoc_suite.py

Runs against whichever numpydoc is installed; treepydoc targets >= 1.10. Point
NUMPYDOC_PATH at a checkout to use that instead.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(numpydoc: Path, swap: bool) -> tuple[str, set[str]]:
    """Run the suite once. Returns its summary line and the failing test IDs."""
    args = [
        sys.executable,
        "-m",
        "pytest",
        "numpydoc/tests",
        "-q",
        "--tb=no",
        # The checked-in addopts ask for coverage plugins that may not be
        # installed, and the cache would be written into the checkout.
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
    ]
    if swap:
        args += ["-p", "numpydoc_swap"]

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(HERE), str(numpydoc), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    result = subprocess.run(
        args, cwd=numpydoc, capture_output=True, text=True, env=env
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else "(no output)"
    failures = {
        line.split(" - ")[0].strip()
        for line in result.stdout.splitlines()
        if line.startswith("FAILED")
    }
    return summary, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--numpydoc",
        default=os.environ.get("NUMPYDOC_PATH"),
        help="a numpydoc checkout; defaults to the installed package",
    )
    args = ap.parse_args()

    if args.numpydoc:
        numpydoc = Path(args.numpydoc).resolve()
    else:
        # numpydoc ships its test suite inside the package, so an installed
        # copy is enough: pytest runs from the directory that contains it.
        import numpydoc as installed

        numpydoc = Path(installed.__file__).resolve().parent.parent
    if not (numpydoc / "numpydoc" / "tests").is_dir():
        raise SystemExit(f"no numpydoc test suite under {numpydoc}")

    print(f"numpydoc checkout: {numpydoc}\n")

    baseline_summary, baseline_failures = run(numpydoc, swap=False)
    print(f"  numpydoc  : {baseline_summary}")
    swapped_summary, swapped_failures = run(numpydoc, swap=True)
    print(f"  treepydoc : {swapped_summary}")

    if baseline_failures:
        print(
            f"\n{len(baseline_failures)} tests already fail without treepydoc "
            "(old test file, newer Python/Sphinx); those are not the question."
        )

    regressions = sorted(swapped_failures - baseline_failures)
    fixed = sorted(baseline_failures - swapped_failures)

    for label, tests in (("newly failing", regressions), ("newly passing", fixed)):
        if tests:
            print(f"\n{len(tests)} {label}:")
            for test in tests[:20]:
                print(f"  {test}")
            if len(tests) > 20:
                print(f"  ... and {len(tests) - 20} more")

    if regressions or fixed:
        return 1

    print(
        f"\nIdentical: the same {len(baseline_failures)} tests fail and the "
        "same tests pass, either way."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

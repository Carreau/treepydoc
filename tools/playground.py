"""Serve the tree-sitter browser playground with a numpydoc docstring in it.

`tree-sitter playground` serves its own HTML, and that HTML starts empty --
worse, `playground.js` restores `sourceCode` from `localStorage`, and the key is
not namespaced by grammar. Any other grammar you have ever served on the same
host and port leaves its source behind, so opening this one can greet you with
somebody else's Rust.

So this exports the playground instead of serving it, seeds `localStorage` with
a docstring that exercises most of the grammar, and serves the result. Once
seeded it gets out of the way: the marker key stops it from overwriting your
edits on every reload.

Usage:
    python3 tools/playground.py                 # build, export, serve, open a browser
    python3 tools/playground.py -q              # don't open a browser
    python3 tools/playground.py --export DIR    # write the static files and stop
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WASM = REPO / "tree-sitter-numpydoc.wasm"

# Chosen to put something under most of the grammar: a signature, a summary and
# an extended summary, both entry flavours (`Parameters` names, `Returns`
# types), an optional-type header, a See Also with a role and with a
# description, a `.. index::`, and -- deliberately -- two things numpydoc gets
# wrong quietly: the `shape :` it drops, which shows up as a
# `dangling_separator`, and an over-long `Raises` underline, which shows up as a
# `section_underline_overlong`.
SAMPLE = '''\
multivariate_normal(mean, cov, shape=None)

Draw samples from a multivariate normal distribution.

The multivariate normal is a generalisation of the one-dimensional normal
distribution to higher dimensions. Such a distribution is specified by its
mean and covariance matrix.

Parameters
----------
mean : (N,) ndarray
    Mean of the N-dimensional distribution.
cov : (N, N) ndarray
    Covariance matrix of the distribution. It must be symmetric and
    positive-semidefinite.
shape :
    Deliberately malformed: a separator with no type. numpydoc drops the
    trailing " :" and reads the name as "shape"; the tree keeps it as a
    dangling_separator so an editor can underline it.
tol : float, optional
    Tolerance when checking the singular values.

Returns
-------
out : ndarray
    The drawn samples, of shape (size, N).

Raises
----------
ValueError
    If `cov` is not square. The underline above is longer than the title:
    numpydoc parses the section and warns to stderr, and the tree marks it.

See Also
--------
normal : The one-dimensional case.
standard_normal, random_sample
:func:`scipy.stats.multivariate_normal`

Notes
-----
Instead of specifying the full covariance matrix, popular approximations
include diagonal and low-rank forms.

.. index:: random, distribution

Examples
--------
>>> mean = (1, 2)
>>> cov = [[1, 0], [0, 1]]
>>> x = multivariate_normal(mean, cov, (3, 3))
'''

# Bump when SAMPLE or the seeded query changes, so an existing visitor picks the
# new one up once. Anything else they typed survives.
SEED_VERSION = "2"

SEED_TEMPLATE = """\
    <script>
      // Seed the playground once. `playground.js` reads these keys in
      // loadState(); they are not namespaced by grammar, so without this you
      // get whatever the last locally-served grammar left behind.
      (() => {{
        const MARKER = "treepydoc.seed";
        if (localStorage.getItem(MARKER) === {version}) return;
        localStorage.setItem(MARKER, {version});
        localStorage.setItem("language", "parser");
        localStorage.setItem("sourceCode", {source});
        localStorage.setItem("query", {query});
        localStorage.setItem("queryEnabled", "false");
        localStorage.setItem("anonymousNodes", "false");
      }})();
    </script>
"""

# The classic script that the module `playground.js` is deferred behind, so
# anything inserted after it still runs first.
ANCHOR = '    <script>LANGUAGE_BASE_URL = "";</script>\n'


def run(*cmd: str) -> None:
    print("$", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, cwd=REPO, check=True)


def tree_sitter_cli() -> list[str]:
    """The pinned CLI, whether it came from `npm install` or is on PATH."""
    local = REPO / "node_modules" / ".bin" / "tree-sitter"
    if local.exists():
        return [str(local)]
    found = shutil.which("tree-sitter")
    if found:
        return [found]
    sys.exit(
        "tree-sitter CLI not found. Run `npm install` in the repository root, "
        "which installs the pinned version."
    )


def build_and_export(dest: Path, *, rebuild: bool) -> None:
    cli = tree_sitter_cli()
    if rebuild or not WASM.exists():
        # Downloads wasi-sdk into ~/.cache/tree-sitter on first use; no
        # Emscripten and no Docker involved.
        run(*cli, "build", "--wasm")
    run(*cli, "playground", "--export", str(dest))

    index = dest / "index.html"
    html = index.read_text(encoding="utf-8")
    if ANCHOR not in html:
        sys.exit(
            f"{index}: the CLI's playground HTML changed shape; "
            f"could not find the insertion point.\n  looked for: {ANCHOR!r}"
        )
    query = (REPO / "queries" / "highlights.scm").read_text(encoding="utf-8")
    seed = SEED_TEMPLATE.format(
        version=json.dumps(SEED_VERSION),
        source=json.dumps(SAMPLE),
        query=json.dumps(query),
    )
    index.write_text(html.replace(ANCHOR, ANCHOR + seed, 1), encoding="utf-8")


def serve(root: Path, host: str, port: int, *, open_browser: bool) -> None:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(root)
    )
    with http.server.ThreadingHTTPServer((host, port), handler) as httpd:
        url = f"http://{host}:{httpd.server_address[1]}/"
        print(f"Started playground on: {url}", file=sys.stderr)
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--export", metavar="DIR", help="write the static files there and exit"
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free one")
    ap.add_argument("-q", "--quiet", action="store_true", help="do not open a browser")
    ap.add_argument(
        "--rebuild", action="store_true", help="rebuild the Wasm parser first"
    )
    args = ap.parse_args()

    dest = Path(args.export) if args.export else REPO / "playground"
    dest.mkdir(parents=True, exist_ok=True)
    build_and_export(dest, rebuild=args.rebuild)
    if args.export:
        print(f"Exported playground to {dest}", file=sys.stderr)
        return 0
    serve(dest, args.host, args.port, open_browser=not args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

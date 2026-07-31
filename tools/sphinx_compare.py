"""End-to-end check: does a Sphinx build come out the same either way?

The unit-level suites compare parse results and rendered reStructuredText. This
one builds an actual Sphinx project twice -- once with `numpydoc` in
`extensions`, once with `treepydoc.sphinx` -- and byte-compares the generated
HTML. It is the only test that exercises the whole chain: autodoc hook,
`get_doc_object` dispatch, the Jinja template, and the RST that comes out.

The project it builds is numpydoc's own `tests/tinybuild`.

Usage:
    NUMPYDOC_PATH=/path/to/numpydoc python3 tools/sphinx_compare.py [--keep]
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_tinybuild() -> Path:
    """Locate numpydoc's tinybuild project."""
    import numpydoc

    candidate = Path(numpydoc.__file__).parent / "tests" / "tinybuild"
    if not (candidate / "conf.py").is_file():
        raise SystemExit(f"no tinybuild project under {candidate}")
    return candidate


# tinybuild points intersphinx at docs.python.org. Whether that inventory
# download succeeds decides if a cross-reference renders as a link or as an
# unresolved `xref` span -- so with it enabled the comparison depends on the
# network rather than on the parser, and two runs of the *same* parser can
# disagree. Turning the mapping off makes the build hermetic.
HERMETIC = """

# Appended by treepydoc's comparison harness: keep the build off the network so
# the only thing that can differ between the two runs is the parser.
intersphinx_mapping = {}
"""


def prepare(source: Path, dest: Path, extension: str) -> Path:
    shutil.copytree(source, dest)
    shutil.rmtree(dest / "_build", ignore_errors=True)
    conf = dest / "conf.py"
    text = conf.read_text()
    if extension != "numpydoc":
        text = text.replace("    'numpydoc',", f"    '{extension}',")
        if extension not in text:
            raise SystemExit("could not swap the extension in conf.py")
    conf.write_text(text + HERMETIC)
    return dest


def build(project: Path) -> Path:
    out = project / "_build"
    # Sphinx runs in a child process, so `sys.path` edits made here do not
    # reach it; NUMPYDOC_PATH has to go through the environment.
    env = dict(os.environ)
    if "NUMPYDOC_PATH" in env:
        env["PYTHONPATH"] = os.pathsep.join(
            [env["NUMPYDOC_PATH"], env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", "-q", str(project), str(out)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print(result.stdout[-4000:])
        print(result.stderr[-4000:])
        raise SystemExit(f"sphinx build failed for {project.name}")
    return out


def compare(left: Path, right: Path) -> list[str]:
    """Byte-compare every generated HTML file. Returns the paths that differ.

    Only HTML is compared: the pickled doctrees embed absolute source paths, so
    they differ between the two build directories for reasons that have nothing
    to do with the parser.
    """
    differing = []
    for path in sorted(left.rglob("*.html")):
        relative = path.relative_to(left)
        other = right / relative
        if not other.is_file():
            differing.append(f"{relative} (missing on the right)")
        elif not filecmp.cmp(path, other, shallow=False):
            differing.append(str(relative))
    return differing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="do not delete the builds")
    args = ap.parse_args()

    tinybuild = find_tinybuild()
    workdir = Path(tempfile.mkdtemp(prefix="treepydoc-sphinx-"))

    try:
        left = build(prepare(tinybuild, workdir / "numpydoc", "numpydoc"))
        right = build(prepare(tinybuild, workdir / "treepydoc", "treepydoc.sphinx"))

        pages = sorted(p.relative_to(left) for p in left.rglob("*.html"))
        if not pages:
            raise SystemExit("the build produced no HTML; nothing was compared")

        differing = compare(left, right)
        for page in pages:
            mark = "DIFFERS" if str(page) in differing else "identical"
            print(f"  {mark:9} {page}")

        if differing:
            print(f"\n{len(differing)} of {len(pages)} pages differ")
            print(f"builds left in {workdir}")
            args.keep = True
            return 1

        print(f"\n{len(pages)}/{len(pages)} generated pages are byte-identical.")
        return 0
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            print(f"builds kept in {workdir}")


if __name__ == "__main__":
    if "NUMPYDOC_PATH" in os.environ:
        sys.path.insert(0, os.environ["NUMPYDOC_PATH"])
    sys.exit(main())

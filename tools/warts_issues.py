"""Turn a weekly `tools/warts.py` scan into issues on this repository.

Two signals come out of the scan, and they deserve different treatment:

* **`parser-disagreement`** -- treepydoc and numpydoc read the same docstring
  differently. That is a treepydoc bug, it is actionable, and it gets its own
  issue, keyed by the docstring's fingerprint so that it survives the file
  being edited around it. The issue is closed automatically once the
  disagreement stops reproducing.

* **everything else** -- numpydoc's own warts in other people's docstrings.
  There are hundreds and there always will be, so one issue per finding would
  be noise. They go into a single rolling census issue whose body is rewritten
  each week, with the week-over-week delta computed from data embedded in the
  previous body.

A third key covers the scan run against numpydoc `main` instead of the pinned
release: any disagreement there is upstream changing behaviour under us, which
is the early warning PLAN.md section 0 asks for.

Every issue carries an HTML-comment marker so a rerun updates the issue it
created last time instead of opening another one.

Usage:
    python3 tools/warts_issues.py --pinned findings.json [--main findings-main.json]
    python3 tools/warts_issues.py --pinned findings.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

LABEL = "warts"
LABEL_COLOR = "5319e7"
LABEL_DESC = "Opened automatically by the weekly docstring scan"

MARKER = "<!-- warts-key: {key} -->"
DATA_OPEN = "<!-- warts-data: "
DATA_CLOSE = " -->"

FOOTER = (
    "\n\n---\n_Opened and maintained automatically by "
    "[`tools/warts.py`](../blob/main/tools/warts.py); "
    "it closes itself when the finding stops reproducing._\n"
)


class Gh:
    """The `gh` CLI, or a no-op that prints what it would have done."""

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run

    def _run(self, args, *, capture, check=True):
        return subprocess.run(
            ["gh", *args],
            capture_output=capture,
            text=True,
            check=check,
        )

    def read(self, args):
        try:
            return self._run(args, capture=True).stdout
        except FileNotFoundError:
            # Only reachable under --dry-run; the workflow always has `gh`.
            if not self.dry_run:
                raise
            print("  (no gh CLI here -- assuming no issues exist yet)")
            return ""

    def write(self, args, *, check=True):
        if self.dry_run:
            printable = " ".join(a if " " not in a else repr(a) for a in args)
            print("  would run: gh " + printable)
            return
        self._run(args, capture=True, check=check)

    def ensure_label(self):
        self.write(
            [
                "label",
                "create",
                LABEL,
                "--color",
                LABEL_COLOR,
                "--description",
                LABEL_DESC,
            ],
            # Already exists is the normal case, and `gh` has no --if-missing.
            check=False,
        )

    def existing(self):
        """Every issue this script has ever opened, keyed by its marker."""
        raw = self.read(
            [
                "issue",
                "list",
                "--label",
                LABEL,
                "--state",
                "all",
                "--limit",
                "200",
                "--json",
                "number,title,body,state",
            ]
        )
        found = {}
        for issue in json.loads(raw or "[]"):
            body = issue.get("body") or ""
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("<!-- warts-key:") and line.endswith("-->"):
                    found[line[len("<!-- warts-key:") : -len("-->")].strip()] = issue
                    break
        return found

    def upsert(self, existing, key, title, body):
        body = f"{MARKER.format(key=key)}\n\n{body}{FOOTER}"
        issue = existing.get(key)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(body)
            path = fh.name
        try:
            if issue is None:
                print(f"open   {key}: {title}")
                self.write(
                    ["issue", "create", "--title", title, "--body-file", path,
                     "--label", LABEL]
                )
                return
            print(f"update #{issue['number']} {key}")
            self.write(["issue", "edit", str(issue["number"]),
                        "--title", title, "--body-file", path])
            if issue["state"] != "OPEN":
                self.write(["issue", "reopen", str(issue["number"])])
        finally:
            os.unlink(path)

    def resolve(self, issue, key):
        if issue["state"] != "OPEN":
            return
        print(f"close  #{issue['number']} {key}")
        self.write(
            [
                "issue",
                "close",
                str(issue["number"]),
                "--comment",
                "No longer reproduces in the latest scan; closing automatically.",
                "--reason",
                "completed",
            ]
        )


def load(path):
    if not path:
        return None
    return json.loads(Path(path).read_text())


def previous_counts(issue):
    """Recover last week's counts from the data block in the old body."""
    if not issue:
        return {}
    body = issue.get("body") or ""
    start = body.find(DATA_OPEN)
    if start < 0:
        return {}
    end = body.find(DATA_CLOSE, start)
    if end < 0:
        return {}
    try:
        return json.loads(body[start + len(DATA_OPEN) : end])
    except json.JSONDecodeError:
        return {}


def delta(now, before):
    if not before:
        return ""
    diff = now - before.get("total", now)
    if diff == 0:
        return " (no change)"
    return f" ({diff:+d})"


def census_body(findings, before, numpydoc_version):
    by_kind = Counter(f["kind"] for f in findings)
    by_pkg = defaultdict(Counter)
    for f in findings:
        by_pkg[f["kind"]][f["package"]] += 1

    old_kinds = before.get("kinds", {})
    lines = [
        "Weekly scan of the `main` branch of numpy, scipy, pandas, matplotlib and",
        f"scikit-learn against numpydoc `{numpydoc_version}`. Every count below is a",
        "place `NumpyDocString` demonstrably mis-handles a real docstring: the",
        "consequence is confirmed against numpydoc itself, not pattern-matched.",
        "",
        "| Finding | Count | Change | Spread |",
        "| --- | ---: | ---: | --- |",
    ]
    for kind, count in by_kind.most_common():
        was = old_kinds.get(kind)
        change = "new" if was is None else f"{count - was:+d}" if count != was else "—"
        spread = ", ".join(
            f"{n} {p}" for p, n in by_pkg[kind].most_common(8)
        )
        lines.append(f"| `{kind}` | {count} | {change} | {spread} |")

    lines += [
        "",
        f"**{len(findings)} findings**{delta(len(findings), before)}.",
        "",
        "Reproduce with:",
        "",
        "```sh",
        "python3 tools/warts.py ~/numpy-src ~/scipy-src ~/pandas-src \\",
        "    ~/matplotlib-src ~/scikit-learn-src --show 20",
        "```",
        "",
        DATA_OPEN
        + json.dumps({"total": len(findings), "kinds": dict(by_kind)})
        + DATA_CLOSE,
    ]
    return "\n".join(lines)


def disagreement_body(group, numpydoc_version):
    lines = [
        "`tools/warts.py` found a docstring that treepydoc and numpydoc",
        f"`{numpydoc_version}` parse differently. treepydoc's contract is to be",
        "answer-for-answer identical, so this is a treepydoc bug.",
        "",
    ]
    for f in group:
        rel = f["path"].split("/")[-3:]
        lines += [
            f"- `{'/'.join(rel)}:{f['line']}` in **{f['package']}**",
            f"  - differing: `{f['evidence']}` ({f['detail']})",
        ]
    lines += [
        "",
        f"Docstring fingerprint `{group[0]['fingerprint']}`.",
    ]
    return "\n".join(lines)


def upstream_body(findings):
    lines = [
        "The scan against numpydoc `main` disagrees with treepydoc where the scan",
        "against the pinned release does not. treepydoc is pinned to one numpydoc",
        "release by convention (PLAN.md section 0); this is that convention",
        "breaking, ahead of the release that would break it for users.",
        "",
        f"{len(findings)} docstring(s) affected:",
        "",
    ]
    for f in findings[:40]:
        rel = "/".join(f["path"].split("/")[-3:])
        lines.append(f"- `{rel}:{f['line']}` — `{f['evidence']}` ({f['detail']})")
    if len(findings) > 40:
        lines.append(f"- ... and {len(findings) - 40} more")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--pinned", required=True, help="findings JSON, pinned numpydoc")
    ap.add_argument("--main", help="findings JSON, numpydoc main (optional)")
    ap.add_argument("--numpydoc-version", default="pinned")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not args.dry_run and not token:
        sys.exit("GH_TOKEN is required unless --dry-run")

    pinned = load(args.pinned)
    upstream = load(args.main)

    gh = Gh(args.dry_run)
    gh.ensure_label()
    existing = gh.existing()
    wanted = set()

    # 1. treepydoc bugs, one issue per affected docstring.
    disagreements = defaultdict(list)
    for f in pinned:
        if f["kind"] == "parser-disagreement":
            disagreements[f["fingerprint"]].append(f)
    for fingerprint, group in sorted(disagreements.items()):
        key = f"disagreement:{fingerprint}"
        wanted.add(key)
        where = f"{group[0]['package']}: {'/'.join(group[0]['path'].split('/')[-2:])}"
        gh.upsert(
            existing,
            key,
            f"Parser disagreement in {where}",
            disagreement_body(group, args.numpydoc_version),
        )

    # 2. the rolling census of numpydoc's warts in other people's docstrings.
    census = [f for f in pinned if f["kind"] != "parser-disagreement"]
    if census:
        key = "census"
        wanted.add(key)
        gh.upsert(
            existing,
            key,
            f"Weekly docstring scan: {len(census)} numpydoc warts in the wild",
            census_body(
                census, previous_counts(existing.get(key)), args.numpydoc_version
            ),
        )

    # 3. upstream drift: disagreements that only the numpydoc-main run sees.
    if upstream is not None:
        seen = set(disagreements)
        drift = [
            f
            for f in upstream
            if f["kind"] == "parser-disagreement" and f["fingerprint"] not in seen
        ]
        if drift:
            key = "numpydoc-main"
            wanted.add(key)
            gh.upsert(
                existing,
                key,
                f"numpydoc main diverges from treepydoc ({len(drift)} docstrings)",
                upstream_body(drift),
            )

    # 4. anything we opened before and no longer see.
    for key, issue in sorted(existing.items()):
        if key not in wanted:
            gh.resolve(issue, key)

    if disagreements:
        print(f"\n{len(disagreements)} parser disagreement(s) -- treepydoc bugs.")
        return 1
    print("\nno parser disagreements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

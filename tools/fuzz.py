"""Mutation fuzzer: do the two parsers still agree on malformed docstrings?

The conformance and sweep suites both run on docstrings someone meant to write.
This one takes real docstrings and corrupts them -- flipping the characters that
carry structure, `-`, `=`, `:`, spaces and newlines -- then checks that
treepydoc and numpydoc still produce the same answer, or reject the input the
same way.

It is also the cheapest way to catch a scanner that loops forever, which is the
characteristic failure mode of an external scanner that emits a zero-width token
without making progress.

Usage:
    python3 tools/fuzz.py [--seeds N] [--mutants N] [--rounds N]
"""

from __future__ import annotations

import argparse
import random
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from conformance import compare  # noqa: E402
from sweep import iter_docstrings  # noqa: E402

# The characters that mean something structurally, plus a little noise.
MUTATION_ALPHABET = list("-=: \t\n.,`~*|(){}[]#>abcXY")


def mutate(text: str, rng: random.Random, edits: int) -> str:
    chars = list(text)
    for _ in range(rng.randint(1, edits)):
        if not chars:
            break
        roll = rng.random()
        i = rng.randrange(len(chars))
        if roll < 0.4:
            chars[i] = rng.choice(MUTATION_ALPHABET)
        elif roll < 0.7:
            chars.insert(i, rng.choice(MUTATION_ALPHABET))
        else:
            del chars[i]
    return "".join(chars)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=400, help="docstrings to corrupt")
    ap.add_argument("--mutants", type=int, default=12, help="mutants per seed")
    ap.add_argument("--edits", type=int, default=6, help="max edits per mutant")
    ap.add_argument("--seed", type=int, default=20260731)
    ap.add_argument("--show", type=int, default=3)
    args = ap.parse_args()

    warnings.simplefilter("ignore")
    sys.argv = sys.argv[:1]

    from numpydoc import docscrape

    seeds = [doc for _, doc in iter_docstrings(["numpy"])][: args.seeds]
    rng = random.Random(args.seed)

    total = identical = rejected_alike = 0
    disagreements = []

    for seed in seeds:
        for _ in range(args.mutants):
            doc = mutate(seed, rng, args.edits)
            total += 1
            try:
                diffs = compare(doc)
            except Exception as exc:  # noqa: BLE001 - comparing behaviour
                try:
                    docscrape.NumpyDocString(doc)
                except Exception as ref:  # noqa: BLE001
                    if type(ref).__name__ == type(exc).__name__:
                        rejected_alike += 1
                    else:
                        disagreements.append(
                            (doc, f"numpydoc {type(ref).__name__}, "
                                  f"treepydoc {type(exc).__name__}")
                        )
                else:
                    disagreements.append((doc, f"only treepydoc raised: {exc!r}"))
                continue

            if diffs:
                disagreements.append((doc, diffs[0]))
            else:
                identical += 1

    for doc, info in disagreements[: args.show]:
        print(f"\n{'=' * 70}")
        print(repr(doc[:400]))
        print(info)

    print(
        f"\n{total} mutants: {identical} identical, "
        f"{rejected_alike} rejected alike, {len(disagreements)} disagree"
    )
    return 1 if disagreements else 0


if __name__ == "__main__":
    sys.exit(main())

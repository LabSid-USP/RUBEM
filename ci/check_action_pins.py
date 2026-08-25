"""Fail when a workflow uses a third-party action that is not pinned to a commit SHA.

Local reusable workflows (``./.github/...``) are exempt; every other ``uses:``
must reference a 40-character commit SHA, optionally followed by a comment
with the human-readable version (``@<sha> # v7``).
"""

import re
import sys
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>\S+)")
PINNED = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def main() -> int:
    failures = []
    for workflow in sorted(Path(".github/workflows").glob("*.y*ml")):
        for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES.match(line)
            if not match:
                continue
            ref = match.group("ref").strip("'\"")
            if ref.startswith("./"):
                continue
            if not PINNED.match(ref):
                failures.append(f"{workflow}:{number}: {ref}")
    for failure in failures:
        print(f"unpinned action: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

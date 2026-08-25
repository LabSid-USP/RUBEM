"""Write the conda packages of an explicit lock file as a JSON inventory.

The golden environment lock (``ci/golden-env.lock``) lists every conda
package as a URL; the inventory records name, version, build, channel and
the MD5 of each, next to the wheel's SBOM in a release.
"""

import json
import re
import sys
from pathlib import Path

ENTRY = re.compile(
    r"^(?P<url>https?://\S+/(?P<channel>[^/]+)/(?P<subdir>[^/]+)/"
    r"(?P<name>.+?)-(?P<version>[^-]+)-(?P<build>[^-]+)\.(?P<ext>conda|tar\.bz2))"
    r"(?:#(?P<md5>[0-9a-f]{32}))?$"
)


def inventory(lock: Path) -> list[dict]:
    packages = []
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "@")):
            continue
        match = ENTRY.match(line)
        if not match:
            raise ValueError(f"unrecognised lock entry: {line}")
        packages.append(
            {
                "name": match.group("name"),
                "version": match.group("version"),
                "build": match.group("build"),
                "channel": match.group("channel"),
                "subdir": match.group("subdir"),
                "url": match.group("url"),
                "md5": match.group("md5"),
            }
        )
    return packages


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: conda_inventory.py <explicit lock> <output json>", file=sys.stderr)
        return 2
    lock, output = Path(argv[1]), Path(argv[2])
    packages = inventory(lock)
    output.write_text(
        json.dumps({"source": str(lock), "packages": packages}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(packages)} packages -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

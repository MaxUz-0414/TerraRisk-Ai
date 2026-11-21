"""Compares a folder (your clone of the repository) with MANIFEST.csv.

    python check_package.py PATH_TO_CLONE [MANIFEST.csv]        (use python3 on macOS / Linux)

Prints OK when every file in MANIFEST.csv exists in the clone with the same size and SHA-256 hash.
Exit code 0 = OK, 1 = a problem. Needs only Python 3 and nothing from the internet.
"""
import csv
import hashlib
import sys
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    clone = Path(argv[1])
    manifest = Path(argv[2]) if len(argv) > 2 else Path(__file__).with_name("MANIFEST.csv")
    if not clone.is_dir():
        print("FOLDER NOT FOUND:", clone)
        return 1
    problems = []
    n = 0
    with open(manifest, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n += 1
            target = clone.joinpath(*row["path"].split("/"))
            if not target.is_file():
                problems.append("MISSING    " + row["path"])
            elif target.stat().st_size != int(row["bytes"]) or sha256(target) != row["sha256"]:
                problems.append("DIFFERENT  " + row["path"])
    if problems:
        print("\n".join(problems[:50]))
        print(f"PROBLEM: {len(problems)} of {n} files are missing or different.")
        return 1
    print(f"OK: all {n} files are present and identical to the package.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Re-create the pinned corpus from FinCEN's site and check it against data/MANIFEST.json.

Downloads each included order's PDF into data/pdf/ (not committed), checks its sha256 against data/orders.json,
extracts the text with `pdftotext -enc UTF-8` (Poppler; the pinned text came from version 26.09.0) and writes any
missing data/orders/<id>.txt. Another Poppler version may extract slightly different text: that is reported, and
the pinned text stays the reference. `--verify` only checks the pinned files and needs no network.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def changed_files(manifest):
    return [name for name, entry in manifest["files"].items()
            if not (DATA / name).is_file() or sha256((DATA / name).read_bytes()) != entry["sha256"]]  # fmt: skip


def download(url, target):
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "examcheck fetch"})
        with urllib.request.urlopen(request, timeout=120) as response:
            target.write_bytes(response.read())
        time.sleep(1)
    return target.read_bytes()


def fetch(manifest):
    problems = []
    for order in json.loads((DATA / "orders.json").read_text()):
        if order["status"] != "included":
            continue
        pdf = DATA / "pdf" / f"{order['id']}.pdf"
        if sha256(download(order["url"], pdf)) != order["pdf_sha256"]:
            problems.append(f"{order['id']}: the PDF on FinCEN's site changed")
            continue
        text = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, check=True).stdout
        target = DATA / order["text"]
        if not target.is_file():
            target.write_bytes(text)
        if sha256(text) != manifest["files"][order["text"]]["sha256"]:
            print(f"{order['id']}: this pdftotext extracts different text; the pinned text is kept", file=sys.stderr)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="check the pinned files only; no network")
    args = parser.parse_args()
    manifest = json.loads((DATA / "MANIFEST.json").read_text())
    problems = [] if args.verify else fetch(manifest)
    problems += [f"missing or changed: {name}" for name in changed_files(manifest)]
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        sys.exit("the data no longer matches the pinned snapshot; results may differ")
    print(f"{len(manifest['files'])} files match MANIFEST.json")


if __name__ == "__main__":
    main()

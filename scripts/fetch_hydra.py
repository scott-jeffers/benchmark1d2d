#!/usr/bin/env python3
"""Download the pinned Hydra CLI (NEER AI) for Linux x86-64, verify it and print its path.

Hydra is AGPL-3.0 (or commercial); the suite runs the official release binary
as a black box and does not redistribute it. The archive is checked against a
pinned SHA-256 before it is unpacked.

Usage::

    HYDRA=$(python scripts/fetch_hydra.py "$RUNNER_TEMP/hydra")
"""

from __future__ import annotations

import hashlib
import sys
import tarfile
import urllib.request
from pathlib import Path

VERSION = "4.1.1"  # CLI 4.1.1 = library 17.0.0
URL = f"https://github.com/neeraip/hydra/releases/download/cli-v{VERSION}/hydra-cli-{VERSION}-x86_64-unknown-linux-gnu.tar.gz"
SHA256 = "bffb9859c0a84391f4a28e61b9df96dfc12890c10af24b182246c0f476e3591d"


def main() -> int:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "hydra").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    exe = dest / "hydra"
    if not exe.is_file():
        archive = dest / "hydra-cli.tar.gz"
        urllib.request.urlretrieve(URL, archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != SHA256:
            raise SystemExit(f"Hydra archive SHA-256 {digest} does not match the pinned {SHA256}")
        with tarfile.open(archive) as tf:
            member = next(m for m in tf.getmembers() if Path(m.name).name == "hydra" and m.isfile())
            member.name = "hydra"
            tf.extract(member, dest, filter="data")
        exe.chmod(0o755)
    print(exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Rewrite database-url secret without trailing whitespace and with psycopg2 driver."""
from __future__ import annotations

import shutil
import subprocess
import sys

PROJECT = "asanclip-rag-prod"
SECRET = "database-url"


def main() -> int:
    gcloud = shutil.which("gcloud")
    if not gcloud:
        print("gcloud not found", file=sys.stderr)
        return 1

    raw = subprocess.check_output(
        [gcloud, "secrets", "versions", "access", "latest", "--secret", SECRET, "--project", PROJECT],
        text=True,
    ).strip()
    raw = raw.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    subprocess.run(
        [gcloud, "secrets", "versions", "add", SECRET, "--project", PROJECT, "--data-file=-"],
        input=raw,
        text=True,
        check=True,
    )

    verify = subprocess.check_output(
        [gcloud, "secrets", "versions", "access", "latest", "--secret", SECRET, "--project", PROJECT],
        text=True,
    )
    print(f"secret_bytes={len(verify)} newline={chr(10) in verify or chr(13) in verify}")
    print(f"driver={verify.split('://', 1)[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

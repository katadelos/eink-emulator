#!/usr/bin/env python3
"""Add a blank local account to a database created by a fresh Kobo emulator."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def add_account(path: Path) -> None:
    with sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True) as database:
        database.execute("BEGIN IMMEDIATE")
        if database.execute("SELECT COUNT(*) FROM user").fetchone()[0]:
            raise ValueError("database already contains an account")
        # Nickel treats an empty UserID as no account; all personal fields stay blank.
        database.execute(
            "INSERT INTO user (UserID, UserKey, UserDisplayName, UserEmail, ___DeviceID) "
            "VALUES (?, ?, ?, ?, ?)",
            ("offline", "", "", "", ""),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="existing KoboReader.sqlite copied from a stopped guest")
    args = parser.parse_args()
    try:
        add_account(args.database)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"cannot add account: {error}\n")
    print(f"Added a blank local account to {args.database}")


if __name__ == "__main__":
    main()

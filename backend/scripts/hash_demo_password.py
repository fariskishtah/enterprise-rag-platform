#!/usr/bin/env python3
from __future__ import annotations

from getpass import getpass

from app.core.security import get_password_hash


def main() -> int:
    first = getpass("Demo password: ")
    second = getpass("Confirm demo password: ")
    if first != second:
        raise SystemExit("Passwords did not match.")
    if len(first) < 12:
        raise SystemExit("Use at least 12 characters for the public demo password.")
    print(get_password_hash(first))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

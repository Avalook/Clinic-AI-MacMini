#!/usr/bin/env python3
"""Parse a PostgreSQL URL from stdin into newline-delimited libpq fields.

The URL is deliberately read from stdin so credentials never appear in argv.
Output order: host, port, user, password, database, sslmode.
"""

from __future__ import annotations

import sys
from urllib.parse import parse_qs, unquote, urlsplit


def main() -> int:
    raw = sys.stdin.readline().rstrip("\r\n")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use postgres:// or postgresql://")
    if not parsed.hostname or parsed.username is None:
        raise ValueError("DATABASE_URL must include host and user")

    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    unsupported = set(query) - {"sslmode"}
    if unsupported:
        raise ValueError(f"unsupported DATABASE_URL query settings: {sorted(unsupported)}")
    sslmodes = query.get("sslmode", [""])
    if len(sslmodes) != 1:
        raise ValueError("DATABASE_URL must contain at most one sslmode")

    fields = (
        parsed.hostname,
        str(parsed.port or 5432),
        unquote(parsed.username),
        unquote(parsed.password or ""),
        unquote(parsed.path.lstrip("/")),
        sslmodes[0],
    )
    if not fields[4]:
        raise ValueError("DATABASE_URL must include a database name")
    if any("\n" in value or "\r" in value for value in fields):
        raise ValueError("DATABASE_URL fields must not contain newlines")
    sys.stdout.write("\n".join(fields) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, UnicodeError) as exc:
        print(f"invalid DATABASE_URL: {exc}", file=sys.stderr)
        raise SystemExit(2)

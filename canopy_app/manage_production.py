"""Hosted Postgres maintenance. Destructive actions preview unless --apply is set."""

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from canopy_app.production import _db


def _pg_env():
    parsed = urlparse(os.environ["DATABASE_URL"])
    query = parse_qs(parsed.query)
    host = parsed.hostname or query.get("host", [None])[0]
    port = parsed.port or query.get("port", [None])[0] or 5432
    if parsed.scheme not in {"postgres", "postgresql"} or not host:
        raise ValueError("Backup requires a PostgreSQL URL with a host")
    env = os.environ.copy()
    env.update(PGHOST=host,
               PGPORT=str(port),
               PGUSER=unquote(parsed.username or ""),
               PGDATABASE=unquote(parsed.path.lstrip("/")),
               PGPASSWORD=unquote(parsed.password or ""))
    if "sslmode" in query:
        env["PGSSLMODE"] = query["sslmode"][0]
    if "sslrootcert" in query:
        env["PGSSLROOTCERT"] = query["sslrootcert"][0]
    env.pop("DATABASE_URL", None)
    return env


def backup(destination):
    target = Path(destination)
    if target.exists():
        raise ValueError("Backup destination must be new")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
                        "--file", str(target)], check=True, env=_pg_env(),
                       capture_output=True, timeout=120)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def purge(days, apply=False):
    if days < 1:
        raise ValueError("Retention days must be positive")
    with _db() as db:
        count = db.execute("""SELECT count(*) AS n FROM canopy_cases WHERE
            organization_id=%s AND created_at < now() - (%s * interval '1 day')""",
            (os.environ["CANOPY_WORKOS_ORG_ID"], days)).fetchone()["n"]
        if apply:
            db.execute("""DELETE FROM canopy_cases WHERE organization_id=%s
                AND created_at < now() - (%s * interval '1 day')""",
                (os.environ["CANOPY_WORKOS_ORG_ID"], days))
    return count


def delete_case(case_id, apply=False):
    if case_id < 1:
        raise ValueError("Case ID must be positive")
    with _db() as db:
        count = db.execute("""SELECT count(*) AS n FROM canopy_cases WHERE
            organization_id=%s AND id=%s""",
            (os.environ["CANOPY_WORKOS_ORG_ID"], case_id)).fetchone()["n"]
        if apply:
            db.execute("""DELETE FROM canopy_cases WHERE organization_id=%s AND id=%s""",
                (os.environ["CANOPY_WORKOS_ORG_ID"], case_id))
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    backup_parser = actions.add_parser("backup")
    backup_parser.add_argument("--output", required=True)
    purge_parser = actions.add_parser("purge")
    purge_parser.add_argument("--older-than-days", type=int, required=True)
    purge_parser.add_argument("--apply", action="store_true")
    delete_parser = actions.add_parser("delete-case")
    delete_parser.add_argument("--id", type=int, required=True)
    delete_parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL is required")
    if args.action != "backup" and not os.environ.get("CANOPY_WORKOS_ORG_ID"):
        parser.error("CANOPY_WORKOS_ORG_ID is required for case deletion")
    if args.action == "backup":
        print("Backup saved:", backup(args.output))
    elif args.action == "purge":
        count = purge(args.older_than_days, args.apply)
        print(f"{'Deleted' if args.apply else 'Would delete'} {count} old cases")
    else:
        count = delete_case(args.id, args.apply)
        print(f"{'Deleted' if args.apply else 'Would delete'} {count} matching case")


if __name__ == "__main__":
    main()

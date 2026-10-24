"""Local single-operator database maintenance. Destructive actions require --apply."""

import argparse
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import canopy


def backup(destination):
    destination = Path(destination)
    if destination.resolve() == canopy.DB_PATH.resolve() or destination.exists():
        raise ValueError("Backup destination must be a new path distinct from the database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        with closing(canopy.database()) as source:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def purge(days, apply=False):
    if days < 1:
        raise ValueError("Retention days must be positive")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with closing(canopy.database()) as db:
        count = db.execute("SELECT count(*) FROM decisions WHERE created_at < ?", (cutoff,)).fetchone()[0]
        if apply:
            db.execute("DELETE FROM decisions WHERE created_at < ?", (cutoff,))
            db.commit()
    return count


def delete_case(case_id, apply=False):
    if case_id < 1:
        raise ValueError("Case ID must be positive")
    with closing(canopy.database()) as db:
        exists = db.execute("SELECT count(*) FROM decisions WHERE id=?", (case_id,)).fetchone()[0]
        if apply:
            db.execute("DELETE FROM decisions WHERE id=?", (case_id,))
            db.commit()
    return exists


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
    if args.action == "backup":
        print(f"Backup saved: {backup(args.output)}")
    elif args.action == "purge":
        count = purge(args.older_than_days, args.apply)
        print(f"{'Deleted' if args.apply else 'Would delete'} {count} old cases")
    else:
        count = delete_case(args.id, args.apply)
        print(f"{'Deleted' if args.apply else 'Would delete'} {count} matching case")


if __name__ == "__main__":
    main()

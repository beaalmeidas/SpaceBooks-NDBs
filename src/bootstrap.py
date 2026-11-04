"""Initialize MongoDB/Neo4j seed data and check all three databases."""

import argparse
import json
import sys
from pathlib import Path

from .database.clients import DatabaseError, connect
from .database.config import Settings
from .database.seed import PreparedData, load, totals, verify
from .prepare_data import ROOT, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/prepared")
    parser.add_argument("--prepare", action="store_true", help="Regenerate prepared data from the repository CSVs")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing data without loading it")
    parser.add_argument("--check-idempotence", action="store_true", help="Load twice and compare database counts")
    args = parser.parse_args()
    if args.verify_only and args.check_idempotence:
        parser.error("--verify-only cannot be combined with --check-idempotence")
    try:
        if args.prepare:
            prepare(ROOT / "data/books-processed.csv", ROOT / "data/users.csv", args.data_dir)
        data = PreparedData.read(args.data_dir)
        settings = Settings.from_env()
        with connect(settings) as connections:
            print("Checking database connections and Redis expiration...", file=sys.stderr, flush=True)
            health = connections.health()
            if not args.verify_only:
                print("Creating indexes and loading seed data...", file=sys.stderr, flush=True)
                load(connections, data)
            print("Verifying prepared identifiers and graph relationships...", file=sys.stderr, flush=True)
            report = verify(connections, data)
            if args.check_idempotence:
                print("Repeating the load to check idempotence...", file=sys.stderr, flush=True)
                before = totals(connections)
                load(connections, data)
                if totals(connections) != before or verify(connections, data) != report:
                    raise DatabaseError("Idempotence check failed: counts changed after second load")
            print(json.dumps({"health": health, "seed": report, "idempotence_checked": args.check_idempotence}, indent=2))
    except DatabaseError as error:
        parser.exit(1, f"{error}\n")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Invalid configuration or prepared data ({type(error).__name__}). Check .env and run src.prepare_data.\n")


if __name__ == "__main__":
    main()

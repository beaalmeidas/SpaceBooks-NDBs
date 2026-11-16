"""Check database authentication, read/write and Redis expiration."""

import argparse
import json

from .database.clients import DatabaseError, connect
from .database.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        with connect(Settings.from_env()) as connections:
            print(json.dumps(connections.health(), indent=2))
    except DatabaseError as error:
        parser.exit(1, f"{error}\n")
    except (ValueError, OSError):
        parser.exit(1, "Invalid database configuration. Check .env.\n")


if __name__ == "__main__":
    main()

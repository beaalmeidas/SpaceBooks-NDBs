"""Invalidate catalog entries or retry a pending invalidation after external edits."""

import argparse
import json

from pymongo.errors import PyMongoError

from src.domain.contracts import ServiceError
from src.services.cached_catalog import CachedCatalogService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry-only", action="store_true", help="Only process existing invalidation intent")
    args = parser.parse_args()
    service = None
    try:
        service = CachedCatalogService.from_env()
        done = service.invalidator.flush() if args.retry_only else service.invalidator.invalidate()
        print(json.dumps({"cache_invalidation_done": done, "retry_required": not done}))
        if not done:
            parser.exit(2, "Redis indisponível ou invalidação pendente. Tente novamente com --retry-only.\n")
    except (ServiceError, PyMongoError):
        parser.exit(1, "Não foi possível registrar a invalidação no MongoDB. Confira a conexão.\n")
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    main()

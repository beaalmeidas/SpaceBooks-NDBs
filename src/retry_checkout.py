"""Internal reconciliation worker; never accepts a customer ID from a public screen."""

import argparse

from src.domain.contracts import ServiceError
from src.services.checkout import MongoCheckoutService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    service = None
    try:
        service = MongoCheckoutService.from_env()
        print(f"Pedidos regularizados: {service.retry_pending(args.limit)}")
    except ServiceError as error:
        parser.exit(1, f"{error}\n")
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    main()

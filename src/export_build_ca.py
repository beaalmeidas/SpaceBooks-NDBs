"""Export the host's public CA trust bundle for an optional Docker build secret."""

import ssl
from pathlib import Path


def main() -> None:
    certificates = ssl.create_default_context().get_ca_certs(binary_form=True)
    if not certificates:
        raise SystemExit("No trusted CA certificates found in the host trust store")
    target = Path(__file__).resolve().parents[1] / ".local/pip-ca.pem"
    target.parent.mkdir(exist_ok=True)
    target.write_text("".join(ssl.DER_cert_to_PEM_cert(cert) for cert in certificates), encoding="ascii")
    print(f"Exported {len(certificates)} public CA certificates to .local/pip-ca.pem")


if __name__ == "__main__":
    main()

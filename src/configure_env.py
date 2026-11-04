"""Create local credentials without overwriting an existing .env file."""

import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / ".env.example").read_text(encoding="utf-8")
    for service in ("MONGO", "REDIS", "NEO4J"):
        template = template.replace(f"CHANGE_ME_{service}", secrets.token_hex(24))
    try:
        with (root / ".env").open("x", encoding="utf-8") as output:
            output.write(template)
    except FileExistsError:
        print("Existing .env preserved.")
    else:
        print("Created .env with local random passwords.")


if __name__ == "__main__":
    main()

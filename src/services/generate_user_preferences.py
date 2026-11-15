import ast
import csv
import json
import random
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOKS_PATH = ROOT / "data" / "books-processed.csv"
USERS_PATH = ROOT / "data" / "users.csv"

SEED = 42
MIN_CATEGORIES = 1
MAX_CATEGORIES = 3



def load_categories() -> list[str]:
    categories = set()

    with BOOKS_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)

        if "categories" not in (reader.fieldnames or []):
            raise ValueError("Books CSV must contain a categories column")

        for row in reader:
            raw_categories = row["categories"]

            if not raw_categories or not raw_categories.strip():
                continue

            values = ast.literal_eval(raw_categories)

            if not isinstance(values, list):
                raise ValueError(f"Invalid categories format: {raw_categories}")

            categories.update(
                category.strip()
                for category in values
                if isinstance(category, str) and category.strip()
            )

    if not categories:
        raise ValueError("No categories found in books dataset")

    return sorted(categories)



def generate_preferences() -> None:
    categories = load_categories()
    rng = random.Random(SEED)

    with USERS_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames

        if not fieldnames or "favorite_categories" not in fieldnames:
            raise ValueError("Users CSV must contain favorite_categories")

        users = list(reader)

    for user in users:
        quantity = rng.randint(
            MIN_CATEGORIES,
            min(MAX_CATEGORIES, len(categories)),
        )

        preferences = rng.sample(categories, quantity)
        user["favorite_categories"] = json.dumps(
            preferences,
            ensure_ascii=False,
        )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".tmp",
            dir=USERS_PATH.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            writer = csv.DictWriter(
                temporary,
                fieldnames=fieldnames,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(users)

        temporary_path.replace(USERS_PATH)

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    print(f"Categories available: {len(categories)}")
    print(f"Users updated: {len(users)}")
    print("Favorite categories generated successfully.")


if __name__ == "__main__":
    generate_preferences()

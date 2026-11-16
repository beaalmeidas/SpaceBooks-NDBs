"""Audit tracked and publishable files without displaying credential values."""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIRS = {".local", ".venv", "venv", ".aws", ".codex", ".agents", ".idea", ".vscode", "__pycache__"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}\b"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
)
REQUIRED = (
    "README.md", ".env.example", ".gitignore", ".dockerignore", ".gitattributes",
    "compose.yaml", "Dockerfile", "requirements.txt", "requirements-app.txt",
    "requirements-db.txt", "requirements-notebook.txt", "docker/mongo-entrypoint.sh",
    "docker/mongo-init.js", "data/books-processed.csv", "data/users.csv",
    "data/recommendation-demo.json", "src/configure_env.py", "src/bootstrap.py",
    "src/catalogo.py", "tests/test_system_flow.py",
)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def local_path(name):
    path = PurePosixPath(name)
    return (bool(LOCAL_DIRS.intersection(path.parts))
            or any(part.startswith(".venv-") for part in path.parts)
            or name.startswith("data/prepared/")
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".rdb", ".aof", ".log"}
            or name == ".streamlit/secrets.toml")


def local_secrets():
    """Only compare long credential values; never include them in reports."""
    path = ROOT / ".env"
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        value = value.strip().strip("\"'")
        if separator and any(word in key.upper() for word in ("PASSWORD", "TOKEN", "SECRET")):
            if len(value) >= 12 and not value.startswith("CHANGE_ME_"):
                result.append(value.encode("utf-8"))
    return result


def has_secret(content, secrets):
    return any(value in content for value in secrets) or any(pattern.search(content) for pattern in SECRET_PATTERNS)


def audit(history=False):
    candidates = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
                            .decode("utf-8").strip("\0").split("\0")) - {""})
    secrets = local_secrets()
    issues = []
    for name in REQUIRED:
        if name not in candidates or not (ROOT / name).is_file():
            issues.append({"path": name, "reason": "Missing delivery file"})
    for name in candidates:
        if local_path(name):
            issues.append({"path": name, "reason": "Local/private file included in delivery"})
        path = ROOT / name
        if path.is_file() and has_secret(path.read_bytes(), secrets):
            issues.append({"path": name, "reason": "Credential pattern or local credential value detected"})
    checked_history = 0
    if history:
        # Object IDs and values are never printed. Check reachable blobs, including deleted files.
        objects = git("rev-list", "--objects", "--all").decode("utf-8").splitlines()
        names = dict(entry.partition(" ")[::2] for entry in objects)
        contents = subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT,
                                           input="".join(f"{key}\n" for key in names).encode("ascii"))
        offset = 0
        while offset < len(contents):
            header_end = contents.index(b"\n", offset)
            object_id, kind, size = contents[offset:header_end].split()
            start = header_end + 1
            end = start + int(size)
            content = contents[start:end]
            offset = end + 1
            if kind != b"blob":
                continue
            checked_history += 1
            name = names[object_id.decode("ascii")]
            if local_path(name) or has_secret(content, secrets):
                issues.append({"path": name, "reason": "Local file or credential detected in Git history"})
    return {"files_checked": len(candidates), "history_blobs_checked": checked_history,
            "issues": issues, "ok": not issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also scan reachable Git history")
    args = parser.parse_args()
    try:
        report = audit(args.history)
    except FileNotFoundError:
        parser.exit(1, "Git is required. Run this command on the host inside a Git clone.\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()

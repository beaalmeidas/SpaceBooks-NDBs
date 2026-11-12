"""Exercise the delivery audit against real, temporary Git repositories."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src import check_delivery


@unittest.skipUnless(shutil.which("git"), "Delivery audit tests require Git on the host")
class DeliveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git("init", "-q")
        for name in check_delivery.REQUIRED:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        (self.root / ".gitignore").write_text(".env\n.local/\n", encoding="utf-8")
        self.secret = "delivery-fixture-only-password-93817"
        (self.root / ".env").write_text(f"REDIS_PASSWORD={self.secret}\n", encoding="utf-8")
        root = patch.object(check_delivery, "ROOT", self.root)
        root.start()
        self.addCleanup(root.stop)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def commit(self):
        self.git("-c", "user.name=Delivery Test", "-c", "user.email=delivery@example.com",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Temporary fixture")

    def test_ignored_secrets_are_excluded_but_new_leaks_are_detected_without_values(self):
        self.assertTrue(check_delivery.audit()["ok"])
        (self.root / "notes.txt").write_text(self.secret, encoding="utf-8")
        report = check_delivery.audit()
        self.assertFalse(report["ok"])
        self.assertEqual(report["issues"][0]["path"], "notes.txt")
        self.assertNotIn(self.secret, str(report))

    def test_forced_tracked_private_files_are_not_hidden_by_gitignore(self):
        self.git("add", "-f", ".env")
        self.assertTrue(any(issue["path"] == ".env" for issue in check_delivery.audit()["issues"]))

    def test_deleted_historical_secret_is_detected(self):
        leak = self.root / "removed.txt"
        leak.write_text(self.secret, encoding="utf-8")
        self.git("add", ".")
        self.commit()
        self.git("rm", "removed.txt")
        self.commit()
        self.assertTrue(check_delivery.audit()["ok"])
        report = check_delivery.audit(history=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any(issue["path"] == "removed.txt" for issue in report["issues"]))
        self.assertNotIn(self.secret, str(report))


if __name__ == "__main__":
    unittest.main()

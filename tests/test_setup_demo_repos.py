import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import setup_demo_repos


class SetupDemoReposTests(unittest.TestCase):
    def test_pinned_commit_fetch_uses_shallow_history_and_creates_clean_worktree(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            origin = root / "origin.git"
            seed = root / "seed"
            self._git("init", "--bare", str(origin))
            self._git("init", "-b", "main", str(seed))
            self._git("config", "user.name", "Citeproof test", cwd=seed)
            self._git("config", "user.email", "citeproof@example.test", cwd=seed)
            (seed / "sample.py").write_text("VALUE = 1\n", encoding="utf-8")
            self._git("add", "sample.py", cwd=seed)
            self._git("commit", "-m", "initial source", cwd=seed)
            commit = self._git("rev-parse", "HEAD", cwd=seed)
            self._git("remote", "add", "origin", str(origin), cwd=seed)
            self._git("push", "origin", "main", cwd=seed)

            demo_root = root / "demo_repos"
            repository = {
                "name": "fixture",
                "url": str(origin),
                "branch": "main",
                "source_candidates": ("fixture-source",),
                "fetch_pinned_commits": True,
                "cases": (("fixture-case", commit),),
            }
            with (
                patch.object(setup_demo_repos, "ROOT", root),
                patch.object(setup_demo_repos, "DEMO_ROOT", demo_root),
                patch.object(setup_demo_repos, "REPOSITORIES", (repository,)),
            ):
                self.assertEqual(setup_demo_repos.main(), 0)

            source = demo_root / "fixture-source"
            checkout = demo_root / "fixture-case"
            self.assertEqual(self._git("rev-parse", "--is-shallow-repository", cwd=source), "true")
            self.assertEqual(self._git("rev-parse", "HEAD", cwd=checkout), commit)
            self.assertEqual(self._git("status", "--porcelain", cwd=checkout), "")

    @staticmethod
    def _git(*args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()


if __name__ == "__main__":
    unittest.main()

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from citeproof.repo import Repo, RepoError


PINNED = "df2e5ed8c4e89f51ff4eddb9600d913083613e62"
OTHER = "6f85d26f85d26f85d26f85d26f85d26f85d26f8"


class PinnedRepositoryTests(unittest.TestCase):
    def run_git(self, revision, status=""):
        def fake_run(command, **kwargs):
            if command == ["git", "rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(command, 0, stdout=revision + "\n", stderr="")
            if command == ["git", "status", "--porcelain=v1", "--untracked-files=all"]:
                return subprocess.CompletedProcess(command, 0, stdout=status, stderr="")
            self.fail(f"Unexpected Git command: {command}")
        return fake_run

    def test_curated_repo_rejects_wrong_head(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run", side_effect=self.run_git(OTHER)
        ):
            with self.assertRaisesRegex(RepoError, "pinned pre-fix commit"):
                Repo(tmp, expected_commit=PINNED)

    def test_curated_repo_rejects_dirty_worktree(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run",
            side_effect=self.run_git(PINNED, " M src/click/types.py\n"),
        ):
            with self.assertRaisesRegex(RepoError, "clean working tree"):
                Repo(tmp, expected_commit=PINNED)

    def test_matching_clean_commit_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run", side_effect=self.run_git(PINNED)
        ) as run:
            repo = Repo(tmp, expected_commit=PINNED)
        self.assertEqual(repo.commit, PINNED)
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()

"""Create or verify clean, pinned checkouts for the curated issue cases."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "demo_repos"
REPOSITORIES = (
    {
        "name": "click",
        "url": "https://github.com/pallets/click.git",
        "branch": "stable",
        "source_candidates": ("click-3449-full", "click-3059", "click-2994", "click"),
        "cases": (
            ("click", "df2e5ed8c4e89f51ff4eddb9600d913083613e62"),
            ("click-3449-full", "a5f5aa6d4012d256ccca24638f2642fc371e9f77"),
            ("click-2994", "3c12ce7050bf63c9fa522e5d7b95543037da0f63"),
            ("click-3059", "8240d25bdbb8c081b745199620b8f2fe03b10579"),
        ),
    },
    {
        "name": "httpx",
        "url": "https://github.com/encode/httpx.git",
        "branch": "master",
        "source_candidates": ("httpx-source", "httpx-2883"),
        "cases": (("httpx-2883", "3b9060ee1121b48669e0b30045c9344065f4f2ae"),),
    },
    {
        "name": "pydantic",
        "url": "https://github.com/pydantic/pydantic.git",
        "branch": "main",
        "source_candidates": ("pydantic-source", "pydantic-13957"),
        "fetch_pinned_commits": True,
        "cases": (("pydantic-13957", "ca359e009fcfaff2a80df33cb99ee6ab21aaf033"),),
    },
    {
        "name": "sse-starlette",
        "url": "https://github.com/sysid/sse-starlette.git",
        "branch": "main",
        "source_candidates": ("sse-starlette-source", "sse-starlette-211"),
        "cases": (("sse-starlette-211", "6754ef387da97cf6cfbcd1bd5c216b533937b304"),),
    },
    {
        "name": "openai-python",
        "url": "https://github.com/openai/openai-python.git",
        "branch": "main",
        "source_candidates": ("openai-python-source", "openai-python-3811"),
        "cases": (("openai-python-3811", "ae41bc46cdd53d17e948ac8a73e16bdbf34123a1"),),
    },
)


def git(*args: str, cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(details) from exc
    return completed.stdout.strip()


def is_repo_checkout(path: Path, repository_url: str) -> bool:
    if not path.exists():
        return False
    try:
        remote = git("remote", "get-url", "origin", cwd=path)
    except subprocess.CalledProcessError:
        return False
    expected = repository_url.rstrip("/").removesuffix(".git").casefold()
    return remote.rstrip("/").removesuffix(".git").casefold() == expected


def verify_checkout(path: Path, expected_commit: str) -> None:
    actual = git("rev-parse", "HEAD", cwd=path)
    if actual != expected_commit:
        raise RuntimeError(f"{path} is at {actual}, expected pinned commit {expected_commit}; it was left untouched.")
    if git("status", "--porcelain", cwd=path):
        raise RuntimeError(f"{path} has local changes; it was left untouched.")


def find_source_repo(repository: dict) -> Path | None:
    for name in repository["source_candidates"]:
        candidate = DEMO_ROOT / name
        if is_repo_checkout(candidate, repository["url"]):
            return candidate
    return None


def main() -> int:
    DEMO_ROOT.mkdir(parents=True, exist_ok=True)
    for repository in REPOSITORIES:
        source = find_source_repo(repository)
        if source is None:
            source = DEMO_ROOT / f"{repository['name']}-source"
            if source.exists():
                raise RuntimeError(f"{source} exists but is not the expected GitHub checkout; it was left untouched.")
            if repository.get("fetch_pinned_commits"):
                source.mkdir(parents=True)
                git("init", str(source))
                git("remote", "add", "origin", repository["url"], cwd=source)
            else:
                git("clone", repository["url"], str(source))

        missing_pins = []
        for _, commit in repository["cases"]:
            try:
                git("cat-file", "-e", f"{commit}^{{commit}}", cwd=source)
            except RuntimeError:
                missing_pins.append(commit)
        if missing_pins:
            if repository.get("fetch_pinned_commits"):
                for commit in missing_pins:
                    git("fetch", "--depth=1", "origin", commit, cwd=source)
            else:
                git("fetch", "origin", repository["branch"], cwd=source)

        for name, commit in repository["cases"]:
            destination = DEMO_ROOT / name
            if destination.exists():
                if not is_repo_checkout(destination, repository["url"]):
                    raise RuntimeError(f"{destination} exists but is not the expected GitHub checkout; it was left untouched.")
                verify_checkout(destination, commit)
                print(f"Verified {name} at {commit}")
                continue
            git("worktree", "add", "--detach", str(destination), commit, cwd=source)
            verify_checkout(destination, commit)
            print(f"Created {name} at {commit}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Demo repository setup stopped safely: {exc}", file=sys.stderr)
        raise SystemExit(1)

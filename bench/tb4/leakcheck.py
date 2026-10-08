"""Refuse to commit when any staged file contains the OAuth token."""
import subprocess
import sys

from bench.tb4 import config
from bench.tb4 import run as runner


def staged_leaks(token: str, run=subprocess.run, repo=config.REPO_ROOT) -> list:
    names = run(["git", "-C", str(repo), "diff", "--cached", "--name-only", "-z"],
                capture_output=True, check=True).stdout.split(b"\0")
    leaks = []
    for name in (n.decode() for n in names if n):
        blob = run(["git", "-C", str(repo), "show", f":{name}"], capture_output=True).stdout
        if token.encode() in blob:
            leaks.append(name)
    return leaks


def main(argv=None) -> int:
    leaks = staged_leaks(runner.read_token())
    if leaks:
        print(f"TOKEN FOUND in staged files: {leaks}", file=sys.stderr)
        return 1
    print("no token in staged files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

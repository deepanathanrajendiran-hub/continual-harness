"""Rewrite a Dockerfile's linux-amd64 Go and yq downloads to linux-arm64; refuse any other amd64 pattern."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

PATCHED = ("RUN", "ADD", "ENV", "ARG")
BUNDLING = ("COPY", "ADD")
RULES = (
    (re.compile(r"(?<![\w.-])(go(?:\d+(?:\.\d+)*(?:(?:rc|beta)\d+)?|\$\{[^}\s]+\}|\$\w+))"
                r"\.linux-amd64\.tar\.gz"), r"\1.linux-arm64.tar.gz"),
    (re.compile(r"(?<![A-Za-z0-9])yq_linux_amd64(?![A-Za-z0-9])"), "yq_linux_arm64"),
    (re.compile(r"(\bGOARCH(?:=|[ \t]+)[\"']?)amd64(?![A-Za-z0-9])"), r"\1arm64"),
)
ARCH_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?:amd64|x86_64)(?![A-Za-z0-9])")
SHA256 = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")


class UnknownArchPattern(ValueError):
    pass


def _instructions(lines: list):
    """Yield (keyword, code line indexes) per logical instruction; comment and blank lines belong to none."""
    keyword, members, continuing = None, [], False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not continuing:
            if members:
                yield keyword, members
            keyword, members = stripped.split(None, 1)[0].upper(), []
        members.append(index)
        continuing = stripped.endswith("\\")
    if members:
        yield keyword, members


def _refuse_bundled(keyword: str, lines: list, members: list) -> None:
    for index in members:
        for token in lines[index].split():
            if ARCH_TOKEN.search(token) and "://" not in token:
                raise UnknownArchPattern(
                    f"line {index + 1}: {keyword} of a bundled amd64 file needs an arm64 file in the "
                    f"build context: {lines[index].strip()}")


def _rewrite(line: str) -> str:
    for pattern, replacement in RULES:
        line = pattern.sub(replacement, line)
    return line


def arm_patch(dockerfile: str) -> tuple:
    lines = dockerfile.splitlines(keepends=True)
    changed = []
    for keyword, members in _instructions(lines):
        if keyword in BUNDLING:
            _refuse_bundled(keyword, lines, members)
        rewritten = False
        if keyword in PATCHED:
            for index in members:
                old, new = lines[index], _rewrite(lines[index])
                if new != old:
                    lines[index], rewritten = new, True
                    changed.append(f"{index + 1}: {old.strip()} -> {new.strip()}")
        for index in members:
            if rewritten and SHA256.search(lines[index]):
                raise UnknownArchPattern(
                    f"line {index + 1}: a pinned sha256 sits in an instruction whose amd64 artifact was "
                    f"rewritten; the arm64 artifact needs its own checksum: {lines[index].strip()}")
            if ARCH_TOKEN.search(lines[index]):
                raise UnknownArchPattern(
                    f"line {index + 1}: amd64 pattern this patcher does not know: {lines[index].strip()}")
    return "".join(lines), changed


GO_RELEASES_URL = "https://go.dev/dl/?mode=json&include=all"
_GO_AMD64 = re.compile(r"go(?P<ver>\d+(?:\.\d+)*(?:(?:rc|beta)\d+)?)\.linux-amd64\.tar\.gz")


def _fetch(url: str, dest=None):
    """GET url: parsed JSON when dest is None, else the body written to dest."""
    request = urllib.request.Request(url, headers={"User-Agent": "evocode-horizon-first-look"})
    with urllib.request.urlopen(request, timeout=600) as response:
        if dest is None:
            return json.load(response)
        with open(dest, "wb") as out:
            shutil.copyfileobj(response, out, 1 << 20)


def replace_bundled_go(env_dir: Path, dockerfile: str, *, releases=None, download=None) -> tuple:
    """Swap each go<ver>.linux-amd64.tar.gz that a COPY or ADD takes from the build context for go.dev's
    linux-arm64 archive of the same version, checked against go.dev's published sha256, and rewrite that
    instruction. Returns (dockerfile, artifacts); go.dev is contacted only when such a file exists."""
    releases = releases or (lambda: _fetch(GO_RELEASES_URL))
    download = download or _fetch
    env_dir = Path(env_dir)
    lines = dockerfile.splitlines(keepends=True)
    artifacts, published = [], None
    for keyword, members in _instructions(lines):
        if keyword not in BUNDLING:
            continue
        for index in members:
            swapped = False
            for token in lines[index].split():
                match = _GO_AMD64.fullmatch(Path(token).name)
                source = env_dir / token
                # a COPY destination or a path outside the build context is never touched
                inside = source.resolve().is_relative_to(env_dir.resolve())
                if not match or "://" in token or not inside or not source.is_file():
                    continue
                name = f"go{match['ver']}.linux-arm64.tar.gz"
                if published is None:
                    published = {f.get("filename"): f.get("sha256") for r in releases() for f in r.get("files") or []}
                if not published.get(name):
                    raise UnknownArchPattern(f"line {index + 1}: go.dev publishes no {name}: {lines[index].strip()}")
                target = source.with_name(name)
                download(f"https://go.dev/dl/{name}", target)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest != published[name]:
                    target.unlink()
                    raise UnknownArchPattern(f"line {index + 1}: {name} has sha256 {digest}, go.dev publishes "
                                             f"{published[name]}: {lines[index].strip()}")
                source.unlink()
                swapped = True
                artifacts.append({"line": index + 1, "file": target.relative_to(env_dir).as_posix(),
                                  "replaces": token, "url": f"https://go.dev/dl/{name}", "sha256": digest})
            if swapped:
                lines[index] = _GO_AMD64.sub(lambda m: f"go{m['ver']}.linux-arm64.tar.gz", lines[index])
    return "".join(lines), artifacts


def needs_patch(dockerfile: str) -> bool:
    lines = dockerfile.splitlines()
    return any(ARCH_TOKEN.search(lines[i]) for _, members in _instructions(lines) for i in members)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Show the arm64 patch for a Dockerfile; never writes it.")
    parser.add_argument("dockerfile", type=Path)
    args = parser.parse_args(argv)
    try:
        _, changed = arm_patch(args.dockerfile.read_text())
    except UnknownArchPattern as err:
        print(err, file=sys.stderr)
        return 2
    print("\n".join(changed) if changed else "no change")
    return 0


if __name__ == "__main__":
    sys.exit(main())

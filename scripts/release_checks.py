#!/usr/bin/env python3
"""Release checks for the git2-rs fork's two packages, which share one tag.

The tag's version is gwz-git2's. gwz-libgit2-sys keeps its own version (0.18.8+1.9.7)
and is published first, from the same tag; gwz-git2 asks for it exactly. Gearu checks
its candidate before committing it, and `cargo package` refuses uncommitted files, so
packaging is the exact stage (`--exact`), run on the release commit.

The vendored libgit2 must be the pinned commit. Changing the pin is a decision of
its own: edit PINNED_LIBGIT2 with it.
"""
import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

PINNED_LIBGIT2 = "b172e3d187a4b6866fd9f696f40a1b8e7f56d348"
SUBMODULE = "libgit2-sys/libgit2"
API_MANIFEST = "Cargo.toml"
SYS_MANIFEST = "libgit2-sys/Cargo.toml"
SYS_PACKAGE = "gwz-libgit2-sys"
API_PACKAGE = "gwz-git2"


def load(root, relative):
    with (root / relative).open("rb") as source:
        return tomllib.load(source)


def api_version(root):
    return load(root, API_MANIFEST)["package"]["version"]


def read_gitlink(root):
    """The libgit2 commit that HEAD's tree records for the submodule path."""
    result = subprocess.run(
        ["git", "ls-tree", "HEAD", SUBMODULE],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    fields = result.stdout.split()
    if len(fields) < 3 or fields[0] != "160000":
        return ""
    return fields[2]


def problems(root, version, gitlink=read_gitlink):
    found = []
    api = load(root, API_MANIFEST)
    sys_manifest = load(root, SYS_MANIFEST)
    for manifest, expected in ((api, API_PACKAGE), (sys_manifest, SYS_PACKAGE)):
        package = manifest["package"]
        if package["name"] != expected:
            found.append(f"package {package['name']!r} where {expected!r} is expected")
        if package.get("publish") is False:
            found.append(f"{package['name']} still has publish = false")
    if api["package"]["version"] != version:
        found.append("the requested version is not gwz-git2's Cargo version")
    requirement = api["dependencies"]["libgit2-sys"]["version"]
    sys_version = sys_manifest["package"]["version"].split("+")[0]
    if requirement != f"={sys_version}":
        found.append(f"gwz-git2 requires {requirement} but {SYS_PACKAGE} is {sys_version}")
    if gitlink(root) != PINNED_LIBGIT2:
        found.append(f"the vendored libgit2 is not the pinned commit {PINNED_LIBGIT2}")
    return found


def gates(exact):
    """Each gate's command, in order."""
    checkout = ["git", "submodule", "update", "--init", SUBMODULE]
    if exact:
        return [
            checkout,
            ["cargo", "publish", "--dry-run", "--locked", "-p", SYS_PACKAGE, "-p", API_PACKAGE],
        ]
    return [checkout, ["cargo", "test", "--locked"]]


def check(root, version, run=subprocess.run, exact=False, gitlink=read_gitlink):
    found = problems(root, version, gitlink)
    for message in found:
        print(f"release refused: {message}", file=sys.stderr)
    if found:
        return 1
    for command in gates(exact):
        result = run(command, cwd=root, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--exact", action="store_true", help="the release commit's stage: dry-run both packages")
    args = parser.parse_args()
    return check(Path(__file__).resolve().parents[1], args.version, exact=args.exact)


if __name__ == "__main__":
    raise SystemExit(main())

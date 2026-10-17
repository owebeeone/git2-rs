# Release Process

<!-- gearu:release:start -->
## Gearu Release Process

Gearu prepares and verifies the repository, creates an immutable tag, and can
create the GitHub Release that starts this repository's publication workflow.
It does not publish directly to package registries.

Full documentation: <https://owebeeone.github.io/gearu/>

### Install

Install the released tool with:

```sh
uv tool install gearu
```

Upgrade an existing installation with:

```sh
uv tool upgrade gearu
```

To test the unreleased `main` branch, install it directly from its repository:

```sh
uv tool install git+https://github.com/owebeeone/gearu.git
```

Verify the installation with `gearu --version`.

### Preconditions

- Read `gearu.toml` and this repository's release workflow.
- Choose an explicit release version or an explicit major, minor, or patch bump.
  Gearu does not infer release intent from commits.
- Use a clean checkout on the branch configured by `project.branch`.
- Synchronize configured release and source branches with their remote.
- Release required cross-repository dependencies first.
- Install and authenticate `gh` before requesting GitHub Release creation.

### Plan

Always inspect the read-only plan first:

```sh
gearu plan VERSION
```

Or ask Gearu to select the next version:

```sh
gearu plan --bump patch
gearu plan --bump minor
gearu plan --bump major
```

Gearu compares configured package versions with valid local and remote release
tags, then bumps the highest version. It reads remote tags directly and does not
fetch or create local tags while planning.

For a release candidate, use a numbered version such as `1.2.3-rc.1`.

Override a configured dependency tag only when the release intentionally uses a
different version:

```sh
gearu plan VERSION --dependency-tag DEPENDENCY=TAG
```

### Prepare the Local Release

After reviewing the plan:

```sh
gearu release VERSION
```

The release command can select the version itself:

```sh
gearu release --bump minor
```

This recalculates the next version at release time. To lock the version reviewed
in a prior bump plan, pass that plan's reported `VERSION` explicitly.

Gearu builds and tests in a temporary worktree. Only a successful candidate is
applied to the local release branch and tagged. This step does not change a
remote repository.

### Push and Create the GitHub Release

Push the exact release commit and tag atomically:

```sh
gearu release VERSION --push
```

Create the GitHub Release after that push:

```sh
gearu release VERSION --push --github-release
```

The final command starts workflows listening for `release.published`, including
package publication and documentation deployment where configured.

### Recovery

- If candidate checks fail, fix the problem and rerun; the normal checkout is
  left unchanged.
- If local preparation succeeds, rerun the same version with `--push`.
- If the push succeeds but GitHub Release creation fails, rerun with
  `--push --github-release`.
- If released contents must change, use a new patch or release-candidate version.
  Never move or replace the existing tag.
- If only a publication workflow fails, repair and rerun that workflow for the
  same GitHub Release.
<!-- gearu:release:end -->

## Publishing the fork's two packages

One tag publishes two crates. `gearu release VERSION` tags `vVERSION`, and VERSION is
`gwz-git2`'s version. `gwz-libgit2-sys` keeps its own version (`0.18.8+1.9.7`), which
gearu does not manage: change it by hand, together with `gwz-git2`'s exact (`=`)
requirement on it. `scripts/release_checks.py` refuses a release when the pair
disagrees. `.github/workflows/release.yml` publishes `gwz-libgit2-sys` first, then
`gwz-git2`, and skips a package whose version is already on crates.io, so rerunning it
after a partial failure resumes where it stopped.

### Before the first release

- Gearu releases only from `main`. The fork's GWZ work must be on `main` first.
- The vendored libgit2 must be the pinned commit, `PINNED_LIBGIT2` in
  `scripts/release_checks.py` (a gitlink at `libgit2-sys/libgit2`). Both check stages
  refuse any other commit. Moving the pin is a decision of its own: edit the constant
  with it. Gearu's checks fetch the submodule from its URL, so the pinned commit must
  be pushed to `owebeeone/libgit2`.
- Both package names are registered on crates.io (`0.0.0-bootstrap.1` placeholders).
  Each needs a trusted publisher: owner `owebeeone`, repository `git2-rs`, workflow
  `release.yml`, environment `crates-io`.
- Nothing in this repository holds a registry token. The old token-based bootstrap and
  publish workflows are gone; publication is only `release.yml`, through Trusted
  Publishing.

### Release

```sh
gearu plan VERSION
gearu release VERSION --push --github-release
```

The candidate stage runs `cargo test --locked`. The exact stage runs
`cargo publish --dry-run --locked -p gwz-libgit2-sys -p gwz-git2` on the release commit.
`release.yml` reruns both on the tag before it publishes.

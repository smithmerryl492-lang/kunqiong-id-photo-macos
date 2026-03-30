# GitHub build guide

This project can be packaged on GitHub Actions as a macOS desktop app without
changing the desktop business flow. The workflow builds an unsigned portable
macOS app, then uploads it as a workflow artifact.

## What was added

- `scripts/build_ci.py`: a PyInstaller entrypoint for CI builds
- `scripts/package_artifact.py`: zips the generated portable output
- `.github/workflows/build-desktop.yml`: GitHub Actions workflow

## How the workflow behaves

- The workflow runs only on `macos-latest`.
- It produces an unsigned `.app`, zips it, and creates an unsigned `.dmg`.
- All outputs are uploaded under the workflow artifact named
  `desktop-build-macos`.

## How to trigger it

1. Push to `main` or `master`, or open the workflow manually in GitHub Actions.
2. Wait for the `Build Desktop App` workflow to finish.
3. Download the `desktop-build-macos` artifact from the workflow run page.

## Current limitations

- The macOS output is unsigned.
- If a Python dependency has no wheel for GitHub's macOS runner, the build will
  fail until that dependency is pinned or replaced.
- The workflow does not produce Windows output.

## Next step for signing

If you later want signed macOS outputs, keep the current build flow and add a
second job that imports the Apple signing certificate from GitHub Secrets, signs
the `.app`, and optionally notarizes the `.dmg`.

## Runner policy — owner directive, 2026-10-26

All repositories and all GitHub Actions build, test, scan, packaging and release
jobs must use compatible private ephemeral JIT runners. GitHub-hosted runners
and automatic hosted fallback are not authorized. This directive supersedes
older hosted-first, pilot-only, selected-jobs-only and permission-pending notes.
Do not restore `NG_HOSTED_FIRST`, a hosted literal, or a hosted matrix fallback.
Missing capacity is a provisioning blocker, never permission to spend hosted
minutes. Preserve OS and architecture requirements. Keep untrusted pull-request
code on an isolated disposable runner with no secrets; do not widen trusted
runner-group access to make it run. Preserve active builds and other agents'
work. Do not restart the broker while it owns running guests. Validate a new
workflow revision on private JIT; rerunning an old run uses its old revision.

The shared policy and exact workflow inventory live in
`snapetech-org/packer/scripts/shared-jit-runner-pool/`. Source routing, deployed
broker policy, runner-group access and live platform capacity must all agree.
Do not report the rollout complete from YAML changes alone.

# Agent instructions

Follow `.github/copilot-instructions.md` for repository-specific development guidance.

## Issues

Before filing a GitHub issue in this repository:

1. Search existing open and closed issues for duplicates.
2. Use the GitHub issue forms in `.github/ISSUE_TEMPLATE/`; do not file a blank issue unless a maintainer explicitly asks for one.
3. Use `package_issue.yml` for package behavior problems, `package_request.yml` for new package requests, `update_request.yml` for version update requests, and `feature_request.yml` for repository or process improvements.
4. Do not file WinGet client issues here; use `microsoft/winget-cli` for client behavior.
5. Keep issue bodies concise and evidence-based. Do not paste large speculative patches into issue bodies; open a pull request or link a branch when manifest changes are available.

## Pull requests

Before opening a pull request:

1. Review `CONTRIBUTING.md` and follow the repository PR template.
2. Modify exactly one package per PR.
3. Validate manifests locally when practical with `winget validate --manifest <path-to-version-folder>`.
4. Do not recursively scan or search the entire `manifests/` directory; work only in the specific package folder being modified.
5. Summarize validation performed, or explain why validation was not run.

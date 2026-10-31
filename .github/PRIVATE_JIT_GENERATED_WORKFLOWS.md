# Private JIT for generated workflows

All nine agentic workflow Markdown sources select private Linux x64 JIT through
`runs-on` and `runs-on-slim`. Threat detection uses the same private runner
pool. The checked-in lock files must keep both the shared run label and a
job-specific `gha-<run_id>-<job_id>` label so the broker assigns each ephemeral
guest to the matching generated job.

`runs-on-slim` is a workflow-wide setting in gh-aw: it routes the generated
framework jobs, but it cannot give each one a different broker label. Raw
`gh aw compile` therefore regenerates the private group while dropping the
job-specific labels. Do not use it directly to refresh checked-in locks.

Use the repository wrapper, which pins the compiler to gh-aw v0.88.7, compiles
the selected Markdown sources, and reproducibly restores and verifies the
job-scoped labels:

```sh
python3 scripts/compile-agentic-workflows.py elevation-requirement-review label-reconciliation-assist manifest-metadata-review unattended-artifact-triage wingetbot-pr-triage
```

With no workflow IDs, the wrapper compiles all Markdown sources. It fails if
the compiler version changes, a generated job lacks the private group/run
labels, a manual workflow loses its required private action/pool inputs or
run-name, or a lock file is missing. Review the generated diff before committing.

The source frontmatter and generated locks must retain private routing; never
restore a hosted runner or fallback. The runner policy is separate from broker
admission, runner-group access, isolated PR execution, and live capacity. See
the [official gh-aw self-hosted runner reference](https://github.github.com/gh-aw/reference/self-hosted-runners/)
for how `runs-on`, `runs-on-slim`, and safe-output runner overrides are applied.

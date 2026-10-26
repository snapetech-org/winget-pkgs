# Private JIT for generated workflows

The owner requires private ephemeral JIT for every repository. The nine agentic
workflow Markdown sources now explicitly set both `runs-on` and `runs-on-slim`;
custom safe-output jobs also select the private group. This syntax is supported
by the currently pinned gh-aw v0.88.7. Updating only the lock files would allow
the compiler defaults to restore hosted runners.

The checked-in lock files have a routing-only override to the same private,
repository/run-scoped labels. Their application steps, permissions, action
pins and container digests are preserved. They were parsed and inspected,
but were **not regenerated with gh-aw** in the editing environment, which has
no gh-aw executable. Existing compiler metadata is retained as historical
generation metadata; it is not evidence of a new compile.

Before the next agentic workflow rollout, run `gh aw compile` with v0.88.7 on
private Linux JIT, review the generated changes and refreshed hashes, and
verify every generated job still selects private capacity. Preserve these
frontmatter runner settings. If a future compiler supports
`require_self_hosted_runners`, enable it after verifying that version's schema.
Do not upgrade the compiler or substitute a hosted runner to bypass this check.

Runner-group admission, isolated PR handling, Docker/egress compatibility and
runtime validation are separate deployment requirements. The source override
does not claim that those requirements or a live agentic run have passed.

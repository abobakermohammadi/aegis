## What changed?

Describe the smallest coherent behavior or documentation change in this PR.

## Why?

What concrete failure mode, user need, maintenance need, or reproducible defect does this address?

## Evidence

List the exact commands/tests used to verify the change and summarize the result.

```text
./verify.sh
# result:
```

## Claim check

- [ ] I added or updated tests for behavior changes.
- [ ] `./verify.sh` passes locally, or I explained why it cannot be run here.
- [ ] README/security/benchmark/changelog claims are still accurate after this change.
- [ ] I did not add secrets, private prompts, transcripts, credentials, or private project data.
- [ ] Any performance or benchmark statement is no broader than the evidence included in the repository.
- [ ] Website links/assets still work under the `/aegis/` GitHub Pages base path if `docs/` changed.

## Compatibility / security impact

State any compatibility, install, security-boundary, migration, or release-note impact. Write `None` if there is none.

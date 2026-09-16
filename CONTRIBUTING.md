# Contributing

Thanks for improving Aegis. The project rule is simple: **every behavioral claim must be backed by evidence a stranger can reproduce.**

## Before you start

- For a bug, use the bug-report issue form and include the smallest reproducible case you can.
- For a feature, explain the failure mode it addresses and how success can be measured.
- For security-sensitive behavior, follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue.

Small, evidence-rich pull requests are preferred over broad rewrites.

## Ground rules

1. Skills are Markdown contracts for agents. Edit them only when you can state what behavior changes and how you verified it.
2. Python tools stay stdlib-only and Python 3.9-compatible unless a release explicitly changes that contract.
3. Every behavior change ships with a test that would fail without the change.
4. No secrets, private prompts, transcripts, credentials, or telemetry in code, tests, fixtures, issues, or docs.
5. Do not make benchmark, adoption, security, or performance claims that are stronger than the evidence in the repository.
6. Keep the project website self-contained and free of required third-party scripts, styles, or font origins.

## Local verification

Run the same repository verifier used by CI:

```sh
./verify.sh
```

A pull request that changes behavior should explain:

- what changed;
- which failure or use case motivated it;
- which command demonstrates the result;
- which tests protect the behavior from regression;
- whether docs, benchmark claims, security boundaries, or compatibility expectations changed.

## Workflow

1. Change the smallest coherent surface.
2. Add or adjust tests for the changed behavior.
3. Run `./verify.sh` and keep the exact result available for the PR.
4. Update `README.md`, `SECURITY.md`, benchmark docs, or `CHANGELOG.md` when their claims change.
5. For website changes, edit `docs/`, check it at narrow and wide viewports, and keep links valid for the `/aegis/` GitHub Pages base path.
6. Open a pull request using the repository template.

## Review standard

A change is ready to merge when its behavior is understandable from the diff, its claims are no broader than its evidence, and the relevant verification is reproducible by someone who did not author the patch.

## Reporting problems

Security issues: see [`SECURITY.md`](SECURITY.md) and use a private repository security advisory.

Everything else: open an issue with environment details, reproduction steps, expected behavior, actual behavior, and the evidence you used to distinguish the two.

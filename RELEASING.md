# Releasing Aegis

A release should make the repository easier to trust, not merely create a tag.

## Release checklist

1. Confirm the working tree only contains intended release changes.
2. Run the full verifier:

```sh
./verify.sh
```

3. Re-read `README.md`, `SECURITY.md`, `QUICKSTART.md`, benchmark documentation, and `CHANGELOG.md` for claims affected by the release.
4. Move completed entries from `Unreleased` into the new semantic-version section in `CHANGELOG.md`.
5. Confirm install, upgrade, and uninstall behavior if the release touches installation paths.
6. Confirm benchmark fixtures and scorers are deterministic if benchmark behavior changed.
7. Confirm no credentials, private prompts, transcripts, local paths, or private user data entered fixtures, logs, docs, or examples.
8. Merge only with green CI.
9. Create the version tag from the verified commit.
10. Publish a GitHub Release whose notes summarize shipped behavior, compatibility changes, verification performed, and known limitations.
11. If the website changed, verify the public `/aegis/` Pages route after deployment.

## Release-note standard

Release notes should answer four questions:

- What materially changed for a user or contributor?
- What command or test demonstrates the change?
- Did compatibility, security boundaries, or installation behavior change?
- What remains unproven or intentionally out of scope?

Do not describe self-run benchmark results as independent performance evidence. Do not imply adoption numbers that are not publicly verifiable.

## Emergency fixes

For a security or correctness hotfix, keep the patch minimal, add regression coverage, run the verifier, document the affected versions, and publish the smallest new patch release that communicates the fix clearly.

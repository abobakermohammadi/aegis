## What changed?

Describe the smallest coherent behavior or documentation change in this PR.

## Why?

What failure mode, user need, or maintainer problem does this address?

## Evidence

List the exact commands, tests, or other reproducible checks you used.

```sh
./verify.sh
```

Add any narrower commands that specifically prove the changed behavior.

## Regression protection

- [ ] I added or updated tests for behavior changes, or this PR is documentation-only.
- [ ] The relevant checks fail without the fix where practical.
- [ ] `./verify.sh` passes on this branch.

## Claims and docs

- [ ] README / QUICKSTART / SECURITY / benchmark docs still match shipped behavior.
- [ ] I did not add adoption, security, benchmark, or performance claims stronger than the public evidence.
- [ ] I updated `CHANGELOG.md` when the change is user-visible or maintainer-significant.

## Safety

- [ ] No secrets, credentials, private prompts, transcripts, or private project data are included.
- [ ] Security-sensitive findings were handled through the private advisory process when appropriate.

## Website changes, if any

- [ ] Links work with the `/aegis/` GitHub Pages base path.
- [ ] I checked the page at narrow and wide viewport sizes.

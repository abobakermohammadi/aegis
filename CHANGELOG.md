# Changelog

All notable changes to Aegis. Format follows Keep a Changelog; versioning is semantic (MAJOR.MINOR.PATCH).

## [Unreleased]

### Added
- Dedicated Aegis project website source under `docs/`, ready for GitHub Pages from `main` / `docs`.
- GitHub Actions CI running the repository verifier on pushes and pull requests.
- Maintainer, roadmap, release-process, issue-template, CODEOWNERS, and pull-request guidance for reproducible external contributions.
- **Machine-readable CI report** (`aegis-engine/aegis_ci.py`) with stable JSON output for mission/gate state, doctor health, open work, git/deploy state, checkpoints, and regression-memory counts.
- Fail-closed CI modes: `--require-complete` and `--require-healthy`, with explicit exit codes and end-to-end coverage for stale evidence, missing state, successful gates, and project paths containing spaces.

### Changed
- Repository and website links now use `abobakermohammadi/aegis` as the canonical public project.
- Contribution guidance now requires reproducible evidence for behavior changes and documents the `/aegis/` Pages base path.
- Reviewer-facing documentation now explicitly labels Aegis as early-stage and avoids inflated adoption or benchmark claims.
- Quickstart and README now document the JSON CI/agent automation contract.

## [2.1.0] — 2026-08-25

### Added
- **Regression Memory V2**: records carry guarded paths and keywords; `aegis regressions-for --files …` returns ranked, explainable matches (path-prefix > area > keyword), and `status` / `next` / `resume` auto-surface relevant past failures with rerun-guard hints. Capped at 5 to prevent noise. Secret-redacted at write time.
- **`aegis verify --rerun`**: re-executes stored evidence commands and flags any disagreement with recorded exits, providing deterministic defense against forged or wrong recorded results.
- **`aegis archive`**: preserve a finished mission directory and start a new one.
- **Doctor** now flags trivial evidence commands (`true`/`echo`) that verify nothing.
- **Benchmark v2**: second mission (M2 `taskapi`: failing test, incomplete feature, hidden regression, SQL injection, doc/implementation mismatch, unscored distraction), aggregate scorer (`score_all.py`), interruption modifier, and validated determinism.

### Fixed
- Engine: checkpoint checksum covered the payload before the file field existed (restore mismatch); `--project` flag clobbered by subparser defaults; read-only state dirs crashed instead of reporting; manual evidence with null exit failed validation; keyword matching used record text instead of changed paths.

## [2.0.0] — 2026-08-25

### Added
- **Aegis Mission Engine** (`aegis-engine/`): persistent execution state, evidence ledger with git-aware staleness invalidation, derived release gates, checksummed checkpoints, resume briefs, next-action ranking, blocker classification, regression and decision memory, deploy tracking, and diagnostics.
- **Benchmark harness** (`benchmarks/`): deterministic broken-project fixture, objective scorer, and A/B protocol for measuring agent performance with vs without Aegis.
- Installer ships the engine (`~/.agents/aegis`) with backup, upgrade, and uninstall guarantees.

### Changed
- `verify.sh` includes the engine test suite.
- Project documentation was updated to describe the shipped mission engine.

## [1.1.0] — 2026-08-25

### Added
- `install.sh`: safe, idempotent installer with `--target`, `--keep`, `--uninstall`, timestamped backups before replacement, refusal to touch non-directory obstructions, and a post-install router smoke check.
- `QUICKSTART.md`: first-success path from install to observable verification.
- `verify.sh`: one command that runs every check in the repository.
- Security hardening for git-remote sanitization and boundary/adversarial router tests.
- Trust set: MIT license, security policy, contribution guide, changelog, and release tags.

### Changed
- Install instructions were aligned with the tested installer and host-directory hints.

## [1.0.0] — 2026-08-25

### Added
- `aegis-ceo-skills`: autonomous end-to-end delivery skill with mission graph, worker activation gates, usage governor, and release gates.
- `usage-optimizer`: usage-minimizing skill with tested deterministic router.
- `second-brain-context`: Obsidian vault context skill with project-graph builder (credential-sanitizing, idempotent).
- `five-year-old`: plain-language end-to-end ownership skill.
- Initial product-site work, later replaced by the canonical project site source in `docs/`.

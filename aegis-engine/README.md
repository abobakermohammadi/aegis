# Aegis Mission Engine

A persistent execution layer for AI coding missions. Zero runtime dependencies beyond the Python 3.9+ standard library. State lives in `<project>/aegis/mission.json`.

## The problem it solves

Long agent missions can fail through lost state, goal drift, stale verification, and false completion. The engine makes state, evidence, and completion mechanical:

- **Evidence is captured, not claimed.** `aegis evidence add --run "<cmd>"` executes the command and records its real exit code. Free-text claims are stored as `UNVERIFIED` and cannot satisfy a required gate.
- **Gates are derived.** A criterion passes only while fresh passing evidence exists. If later git changes touch the files the evidence guarded, the gate can become `stale` automatically.
- **Completion refuses.** `aegis complete` exits non-zero while a required gate lacks fresh passing evidence or while a blocking decision/credential condition remains open.
- **Resume is one command.** `aegis resume` prints the minimum brief a fresh session needs: goal, rationale, decisions, gate statuses, stale evidence, open defects/blockers, completed work, regression memory, deploy state, and the recommended next action.
- **Checkpoints survive state loss.** Each checkpoint embeds a full state snapshot with a checksum. If `mission.json` is deleted or corrupt, `aegis restore` can rebuild from the checkpoint.
- **Regression memory is actionable.** Recorded regressions include guarded paths/keywords so relevant past failures can be surfaced when similar files change again.
- **Evidence can be re-run.** `aegis verify --rerun` executes stored evidence commands again and surfaces disagreement instead of trusting a historical result forever.

## Commands

```text
init status next verify resume checkpoint restore complete
evidence criteria workstream defect blocker regression decision
deploy doctor report archive regressions-for
```

Every command supports `--help`; `--project <dir>` operates on another directory. Exit codes distinguish success, failed checks, and invalid input/state.

## State model

`aegis/mission.json` uses schema-versioned atomic writes with `.bak` recovery.

| Section | Purpose |
|---|---|
| mission | id, goal, why, phase, constraints, non-goals, release |
| criteria | release gates whose status is derived from evidence |
| workstreams / defects | prioritized work and known failures |
| blockers | credentials, decisions, failures, and inconveniences |
| evidence | command, exit, clipped/redacted output, commit, timestamp |
| decisions | context, options, choice, reason, revisit conditions |
| regressions | defect, cause, fix, guard test, area, guarded paths/keywords |
| checkpoints | rolling window of self-contained state snapshots |
| deploy | target, state, URL, last checked |

## Security model

Repository content is treated as potentially hostile. The engine uses argv execution rather than shell-string execution for stored evidence commands, strips ANSI escapes, redacts secret-like strings before persistence, caps captured output and state size, refuses symlinked state paths, times out commands and git calls, and does not require network access.

The repository security policy documents the wider trust boundaries and non-goals: [`../SECURITY.md`](../SECURITY.md).

## Testing

Run the engine suite directly:

```sh
python3 -m unittest discover aegis-engine -p "test_*.py"
```

The automated coverage exercises the mission lifecycle, git-aware staleness, completion refusal, corruption/repair, checkpoint integrity and state-loss recovery, secret redaction, clipping, symlink attacks, concurrent writers, unicode/space paths, detached HEAD behavior, migrations, regression matching, evidence re-runs, and false-completion defenses.

Run the whole repository verifier with:

```sh
./verify.sh
```

For outcome-based agent testing, see [`../benchmarks/PROTOCOL.md`](../benchmarks/PROTOCOL.md).

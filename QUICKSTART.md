# Quickstart: first success in five minutes

Goal: install Aegis, prove it works on your machine, and see one deterministic tool do real work. Every step below is observable.

## 0. What you need

- A terminal on macOS or Linux.
- Python 3.9+ (`python3 --version`) for the deterministic tools.
- An agent host that can load local skill folders if you want to use the Markdown skills. The mission engine and deterministic tools work without an agent host.

## 1. Clone and verify

```sh
git clone https://github.com/abobakermohammadi/aegis.git
cd aegis
./verify.sh
```

`verify.sh` runs the Python test suites and a clean-environment installer smoke test. It exits non-zero if a required check fails and ends with `RESULT: all checks passed` when verification succeeds.

## 2. Install

```sh
./install.sh
```

The default skill target is `~/.agents/skills` and the mission engine is installed under `~/.agents/aegis`.

The installer is designed to be reversible:

- differing existing copies are backed up before replacement;
- `--keep` leaves an existing copy untouched;
- `--target DIR` selects another skills directory;
- `--uninstall` removes installed Aegis copies while preserving timestamped backups;
- non-directory obstructions are refused rather than overwritten.

A successful install finishes with a live router smoke check.

## 3. Use a deterministic tool directly

```sh
python3 ~/.agents/skills/usage-optimizer/scripts/route_task.py \
  --task "review authentication vulnerability" \
  --kind security \
  --risk high
```

The router returns structured JSON describing the selected route and why it met the requested quality/risk floor. Change the flags and the deterministic routing decision changes with them.

## 4. Start a mission

Inside any project:

```sh
python3 ~/.agents/aegis/aegis.py init \
  --goal "Ship feature X" \
  --criterion "Tests pass"

python3 ~/.agents/aegis/aegis.py next
```

Then capture real evidence instead of free-text completion claims:

```sh
python3 ~/.agents/aegis/aegis.py evidence add --run "python -m pytest"
python3 ~/.agents/aegis/aegis.py status
python3 ~/.agents/aegis/aegis.py verify --rerun
```

If relevant code changes later, git-aware evidence can become stale and the release gate must be satisfied again.

## 5. Hand the skills to an agent

Point your agent host at the installed skills directory (for example `~/.agents/skills`, or the equivalent directory for your host), then invoke a skill by name.

Expected behavior is defined in each `SKILL.md`; the deterministic tools remain independently runnable and testable outside the model.

## 6. Inspect the reliability benchmark

Read [`benchmarks/PROTOCOL.md`](benchmarks/PROTOCOL.md). It defines two broken-project missions, objective scorers, false-completion detection, an interruption/resume modifier, and contamination rules for comparing the same coding agent with and without Aegis.

## Where to go next

- [`README.md`](README.md) — project overview and reviewer path.
- [`aegis-engine/README.md`](aegis-engine/README.md) — mission-engine state and evidence model.
- [`benchmarks/PROTOCOL.md`](benchmarks/PROTOCOL.md) — benchmark methodology.
- [`SECURITY.md`](SECURITY.md) — threat model and boundaries.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution workflow.

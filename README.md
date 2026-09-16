# Aegis

[![CI](https://github.com/abobakermohammadi/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/abobakermohammadi/aegis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A reliability layer for long-horizon AI coding agents.** Aegis turns a coding mission into durable state, reproducible evidence, release gates, regression memory, and deterministic verification so an agent cannot call work complete just because it says it is done.

The mission engine and benchmark harness are local-first and model/provider-independent. The optional agent skills are plain Markdown contracts plus local scripts and can be adapted to hosts that support local skill folders. The deterministic Python tooling targets Python 3.9+ stdlib and has no required account, daemon, hosted service, or telemetry.

## Why Aegis exists

Coding agents are increasingly capable, but long-running work still has recurring failure modes:

- **False completion** — the agent says a task is finished without strong evidence.
- **Stale evidence** — tests passed, then later changes invalidated what they proved.
- **Context loss** — a restarted session has to rediscover decisions, failures, and remaining work.
- **Repeated regressions** — previously fixed defects return because the guard and cause were forgotten.
- **Usage waste** — expensive reasoning is used where deterministic or cheaper routes would be enough.

Aegis makes those concerns explicit and machine-checkable instead of relying on prompt discipline alone.

## 60-second proof

```sh
git clone https://github.com/abobakermohammadi/aegis.git
cd aegis
./verify.sh
```

`verify.sh` runs the Python suites plus a clean-environment installer smoke test and exits non-zero on failure. GitHub Actions runs the same verifier on pushes and pull requests.

For the reliability claim, read [`benchmarks/PROTOCOL.md`](benchmarks/PROTOCOL.md). The benchmark harness contains two deterministic broken-project missions with objective scorers, planted functional/security defects, false-completion detection, and an interruption/resume protocol.

**Benchmark honesty:** the recorded results are self-runs used to validate the harness. Aegis does **not** claim an external A/B performance advantage until the same external agent is run in both protocol arms and the raw evidence is published.

## Core components

| Path | What it does |
|---|---|
| [`aegis-engine/`](aegis-engine/) | Persistent mission state, evidence-gated completion, git-aware staleness, checksummed checkpoints, one-command resume, blocker/decision tracking, regression memory, and diagnostics. |
| [`benchmarks/`](benchmarks/) | Deterministic M1/M2 agent-reliability missions, objective scorers, aggregate scoring, false-completion detection, and an A/B protocol. |
| [`aegis-ceo-skills/`](aegis-ceo-skills/) | End-to-end delivery skill with explicit capability probes, usage governance, and release gates. |
| [`usage-optimizer/`](usage-optimizer/) | Deterministic task router that chooses the lowest-cost route meeting the requested quality/risk floor. |
| [`second-brain-context/`](second-brain-context/) | Local project-graph builder for durable context; sanitizes git credentials and does not copy source into the vault. |
| [`five-year-old/`](five-year-old/) | Plain-language execution/reporting skill for simple progress updates and explicit verification status. |

## Install

```sh
git clone https://github.com/abobakermohammadi/aegis.git
cd aegis
./install.sh
```

The installer is designed to be safe and reversible: it backs up differing existing copies before upgrade, refuses non-directory obstructions, supports `--keep`, `--target`, and `--uninstall`, and finishes with a live router smoke check.

This installs the skills and the mission engine. To start a mission inside any project:

```sh
cd your-project
python3 ~/.agents/aegis/aegis.py init \
  --goal "Ship feature X" \
  --criterion "Tests pass"

python3 ~/.agents/aegis/aegis.py next
```

See [`QUICKSTART.md`](QUICKSTART.md) for the first verified run.

## Evidence instead of claims

The mission engine treats free-text status as information, not proof. Required gates are satisfied only by fresh passing evidence. Evidence can become stale after relevant git changes, and `aegis complete` refuses completion while required gates or blocking decisions remain unresolved.

```sh
python3 ~/.agents/aegis/aegis.py evidence add --run "python -m pytest"
python3 ~/.agents/aegis/aegis.py verify --rerun
python3 ~/.agents/aegis/aegis.py status
python3 ~/.agents/aegis/aegis.py complete
```

The engine also rejects trivial evidence patterns in diagnostics and redacts secret-like strings before persisting captured output. See [`aegis-engine/README.md`](aegis-engine/README.md) and [`SECURITY.md`](SECURITY.md).

## Benchmark design

The included benchmark is intentionally harder than “make tests green.” Missions mix visible failing tests with defects that require inspection, including hidden regressions, documentation/implementation mismatch, and SQL injection. An independent scorer judges the resulting repository rather than trusting the agent's completion message.

The protocol also includes an interruption modifier: the treatment arm resumes through durable Aegis state while the baseline receives the same opportunity to leave successor notes. This makes restart behavior measurable instead of anecdotal.

See [`benchmarks/PROTOCOL.md`](benchmarks/PROTOCOL.md) for contamination rules, scoring, and current self-run results.

## Project status

Aegis is an **active, early-stage open-source project**. External adoption is still early, so the repository does not inflate usage claims. The current value is the shipped implementation, reproducible verification, explicit security model, and benchmark protocol. Contributions and independent benchmark runs are welcome.

The evidence-first development plan is in [`ROADMAP.md`](ROADMAP.md), including independent external-agent A/B benchmarks, real maintainer-workflow dogfooding, broader deterministic benchmark coverage, portability work, and release hygiene.

Primary maintainer: **Abobaker Mohammadi** ([@abobakermohammadi](https://github.com/abobakermohammadi)). Maintainer responsibilities are documented in [`MAINTAINERS.md`](MAINTAINERS.md).

## Contributing and security

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution rules and verification workflow.
- [`SECURITY.md`](SECURITY.md) — threat model, trust boundaries, and private vulnerability reporting.
- [`ROADMAP.md`](ROADMAP.md) — evidence-first development priorities.
- [`CHANGELOG.md`](CHANGELOG.md) — versioned project history.
- [`QUICKSTART.md`](QUICKSTART.md) — five-minute first-success path.

## License

MIT — see [`LICENSE`](LICENSE).

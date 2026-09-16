# Security policy

Aegis runs inside your machine and your agent. Its important trust boundaries are your files, git remotes, local project state, vault data, recorded evidence commands, and anything the agent host sends it.

## Supported versions

| Version | Supported |
|---------|-----------|
| 2.1.x | Yes |
| 2.0.x | Best effort |
| < 2.0 | No |

Use the newest 2.1.x revision available from the repository when evaluating or deploying Aegis.

## How to report

Open a private security advisory through the repository's **Security → Advisories** flow. Please include a minimal reproduction, affected paths, expected behavior, actual behavior, and any evidence needed to validate the issue. Do not open a public issue for exploitable behavior before a fix is available.

## Threat model

| Boundary | Trust stance | Controls in place |
|----------|--------------|-------------------|
| Task input to `route_task.py` | Hostile | Strict schema validation, typed flags, compact JSON errors, exit code 2 on invalid input, and automated boundary/adversarial tests. |
| Filesystem walked by `build_project_graph.py` | Semi-trusted local data | Excluded directories, traversal depth/file caps, git subprocess timeout, argv-based subprocess execution, and symlink traversal disabled by default. |
| Git remote URLs | Hostile | Credentials plus query/fragment material are stripped before generated vault metadata is written; this behavior has regression coverage. |
| Vault writes | User data | Writes only generated project metadata into the configured vault area; source files, `.env` files, keys, build output, and secrets are not copied into the vault. |
| Recorded evidence commands | Semi-trusted | `aegis verify --rerun` re-executes stored evidence commands and compares their real exits with recorded results; `doctor` flags trivial evidence such as `true`/`echo`. |
| Mission state | Local persistent state | Schema validation, atomic writes, `.bak` recovery, size limits, checksummed checkpoints, and refusal of symlinked state paths. |
| Captured command output | Potentially sensitive | ANSI stripping, secret-pattern redaction, and clipping before persistence. |
| Regression records | User/agent input | Redacted and clipped before write; matching is read-only over stored paths/keywords. |
| Installer | Local only | Refuses non-directory obstructions, backs up before replacement, supports reversible uninstall, and does not fetch code from the network during installation. |

## Security properties worth testing

Aegis is designed so these claims can be checked rather than merely stated:

- A free-text claim cannot satisfy a required evidence gate.
- Completion refuses while required gates lack fresh passing evidence.
- Relevant git changes can invalidate previously passing evidence as stale.
- Stored evidence can be re-run and disagreement is surfaced as a verification failure.
- Checkpoints include integrity protection and can reconstruct mission state after state loss.
- Secret-like captured values are redacted before persistence.
- Symlinked mission-state paths are refused.

The engine and helper test suites include corruption, tamper, recovery, path, redaction, malformed-input, and false-completion cases. Run the repository verifier with:

```sh
./verify.sh
```

## What Aegis does not do on its own

- It does not transmit source code, secrets, mission state, or vault content to a hosted Aegis service. There is no required hosted Aegis service.
- It does not silently turn free-text agent claims into passing release evidence.
- It does not replace the sandbox or permission model of the agent host.

## Known non-goals

The Markdown skills are instructions interpreted by an external agent host. Aegis can define rules such as capability probing, evidence capture, and stopping before irreversible actions, but the host remains responsible for enforcing filesystem, network, shell, credential, and user-approval permissions.

The deterministic benchmark in [`benchmarks/PROTOCOL.md`](benchmarks/PROTOCOL.md) is designed to test outcomes independently of agent claims. Security findings in benchmark fixtures are synthetic and are not evidence of vulnerabilities in third-party projects.

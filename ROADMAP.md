# Roadmap

Aegis is early-stage. The roadmap is intentionally evidence-first: new claims should follow reproducible implementation and measurement, not precede them.

## Near term

### 1. Run independent agent A/B benchmarks

Use the existing deterministic M1/M2 protocol with the same external coding agent in both arms:

- baseline: normal agent workflow;
- treatment: same prompt plus the Aegis mission engine;
- fresh fixture directories for every run;
- at least one interruption/resume trial;
- publish scorer outputs and raw/appropriately redacted transcripts;
- report false-completion attempts, rediscovery events, and resume behavior;
- make no comparative performance claim until the protocol has actually been run.

Codex is a particularly useful target because Aegis is intended to improve long-horizon coding-agent maintenance workflows without depending on a specific model in the mission engine itself.

### 2. Improve maintainer workflows

Exercise Aegis on real repository maintenance tasks:

- issue reproduction and defect tracking;
- regression-test generation from confirmed failures;
- pull-request verification against explicit evidence gates;
- release checklists and evidence re-runs;
- interruption/resume across multi-session maintenance work.

Automation should assist review, not silently merge or publish changes.

### 3. Expand benchmark coverage

Add missions that cover different failure shapes while keeping scoring deterministic, for example:

- cross-file API contract changes;
- migration/state compatibility;
- concurrency or race-condition regressions;
- dependency/configuration drift;
- security fixes where test-green alone is insufficient.

Each mission should have objective scoring and a clearly documented contamination boundary.

### 4. Harden portability

Keep the core engine and benchmark model/provider-independent while documenting adapters for agent hosts that support local skill folders. Avoid coupling completion logic to a hosted control plane.

### 5. Strengthen release hygiene

For every behavior-changing release:

- update tests and `CHANGELOG.md`;
- run `./verify.sh` through CI;
- keep security/support documentation aligned with the shipped version;
- preserve tagged versions and reproducible upgrade/uninstall behavior.

## Longer term

- External contributors running and publishing independent benchmark results.
- More compact mission-state handoffs for very large repositories.
- Better evidence scoping so unrelated changes do not invalidate useful proof.
- Optional machine-readable reports for CI and maintainer automation.
- Broader host integration without weakening local-first operation or evidence requirements.

## Non-goals

- Inflating adoption metrics or benchmark results.
- Replacing an agent host's sandbox/permission system.
- Treating model-generated text as release evidence by itself.
- Auto-merging, deploying, or publishing consequential changes without explicit maintainer policy.

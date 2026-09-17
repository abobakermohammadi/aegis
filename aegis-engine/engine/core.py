"""Core mission-engine logic: evidence, staleness, gates, next action,
checkpoints, resume briefs, and doctor diagnostics.

Design rules enforced here:
- Evidence is captured by *running* commands; exit codes come from the
  process, never from the agent's claims. Manual evidence is marked
  verified=False and displayed as UNVERIFIED.
- Captured output is truncated, ANSI-stripped, and secret-redacted before it
  is ever persisted.
- Gate status is derived from evidence freshness; it can never be asserted.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import cmdline
from . import gitinfo
from . import state as state_mod

split_command = cmdline.split_command

CHECKPOINT_LIMIT = 20
OUTPUT_KEEP = 4_000

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
SECRET_RES = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b\s*[=:]\s*\S+"),
]


def redact(text: str) -> str:
    for pattern in SECRET_RES:
        text = pattern.sub("[REDACTED]", text)
    return ANSI_RE.sub("", text)


def clip(text: str, limit: int = OUTPUT_KEEP) -> str:
    text = redact(text)
    if len(text) <= limit:
        return text
    return text[:limit] + " …[truncated]"


def run_command(project: Path, command: str, timeout: int = 600) -> dict:
    """Run a verification command and return a deterministic record."""
    try:
        argv = split_command(command)
    except ValueError as exc:
        return {"exit": 2, "summary": f"unparseable command: {exc}", "output": ""}
    if not argv:
        return {"exit": 2, "summary": "empty command", "output": ""}
    try:
        result = subprocess.run(
            argv, cwd=str(project), capture_output=True,
            timeout=timeout, check=False,
        )
        exit_code = result.returncode
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    except FileNotFoundError:
        return {"exit": 127, "summary": "command not found: " + argv[0], "output": ""}
    except subprocess.TimeoutExpired:
        return {"exit": 124, "summary": f"timed out after {timeout}s", "output": ""}
    except PermissionError:
        return {"exit": 126, "summary": "permission denied", "output": ""}
    tail_lines = [line for line in output.splitlines() if line.strip()]
    summary = clip("; ".join(tail_lines[-3:]) or "(no output)", 300)
    return {"exit": exit_code, "summary": summary, "output": clip(output)}


def add_evidence(project: Path, st: dict, criterion: str, kind: str,
                 command: str | None, manual_note: str | None) -> tuple[dict, str]:
    """Record evidence. Returns (evidence_entry, message)."""
    crit = next((c for c in st["criteria"] if c["id"] == criterion), None)
    if crit is None:
        raise ValueError(f"unknown criterion {criterion}")
    commit = gitinfo.head_commit(project)
    if manual_note is not None:
        entry = {
            "id": state_mod.new_id("E", st["evidence"]),
            "criterion": criterion,
            "kind": kind,
            "command": None,
            "exit": None,
            "summary": clip(manual_note, 300),
            "commit": commit,
            "files": [],
            "captured_at": state_mod.now_iso(),
            "verified": False,
        }
        note = "recorded UNVERIFIED manual evidence (does not satisfy required gates)"
    else:
        outcome = run_command(project, command or "")
        entry = {
            "id": state_mod.new_id("E", st["evidence"]),
            "criterion": criterion,
            "kind": kind,
            "command": clip(command or "", 500),
            "exit": outcome["exit"],
            "summary": outcome["summary"],
            "output": outcome["output"],
            "commit": commit,
            "files": [],
            "captured_at": state_mod.now_iso(),
            "verified": True,
        }
        note = f"exit={outcome['exit']}"
    st["evidence"].append(entry)
    crit.setdefault("evidence", []).append(entry["id"])
    return entry, note


def _freshness(project: Path, ev: dict) -> str:
    """fresh | aged-ok | stale | unverifiable"""
    if not ev.get("verified"):
        return "unverified"
    if not ev.get("commit"):
        return "unverifiable"
    if not gitinfo.is_repo(project):
        return "unverifiable"
    head = gitinfo.head_commit(project)
    if not head:
        return "unverifiable"
    if ev["commit"] == head:
        return "fresh"
    changed = gitinfo.changed_since(project, ev["commit"])
    if changed is None:
        return "unverifiable"
    files = ev.get("files") or []
    if not files:
        return "stale"
    return "stale" if set(changed) & set(files) else "aged-ok"


TRIVIAL_COMMANDS = {"true", ":"}


def _is_trivial(command):
    if not command:
        return False
    try:
        argv = split_command(command)
    except ValueError:
        return False
    if not argv:
        return True
    if argv[0] in TRIVIAL_COMMANDS:
        return True
    return argv[0] == "echo" and len(argv) <= 3


def gate_status(project: Path, st: dict, criterion: dict) -> tuple[str, list[str]]:
    """Derived status: pass | stale | failed | blocked | open (+ reasons)."""
    if criterion.get("blocked_reason"):
        return "blocked", [criterion["blocked_reason"]]
    evs = [e for e in st["evidence"] if e["id"] in criterion.get("evidence", [])]
    if not evs:
        return "open", ["no evidence recorded"]
    if all(not e.get("verified") for e in evs):
        return "stale", ["only UNVERIFIED manual claims; run a real check"]
    freshest: dict[str, list[dict]] = {}
    for ev in evs:
        freshest.setdefault(_freshness(project, ev), []).append(ev)
    successful = [ev for ev in evs if ev.get("exit") == 0]
    passing = [ev for ev in successful if not _is_trivial(ev.get("command"))]
    if passing:
        kinds = sorted({_freshness(project, ev) for ev in passing})
        if "fresh" in kinds or "aged-ok" in kinds:
            return "pass", []
        if "unverifiable" in kinds:
            return "pass", ["evidence cannot be staleness-checked (no git)"]
        if "unverified" in kinds:
            return "stale", ["only UNVERIFIED manual claims; run a real check"]
        return "stale", ["all passing evidence is stale after later commits"]
    if successful:
        return "failed", ["only trivial successful evidence; run a check that exercises real behavior"]
    latest = max(evs, key=lambda e: e["captured_at"])
    return "failed", [f"last check exited {latest.get('exit')}: {latest.get('summary', '')[:120]}"]


def rerun_evidence(project: Path, st: dict) -> list:
    """Re-execute stored verified evidence commands; compare exits."""
    disagreements = []
    seen = set()
    for ev in st["evidence"]:
        if not ev.get("verified") or not ev.get("command"):
            continue
        key = (ev["id"], ev["command"], ev.get("exit"))
        if key in seen:
            continue
        seen.add(key)
        actual = run_command(project, ev["command"])
        if actual["exit"] != ev.get("exit"):
            disagreements.append({
                "id": ev["id"], "criterion": ev["criterion"],
                "recorded": ev.get("exit"), "actual": actual["exit"],
                "command": ev["command"], "summary": actual["summary"][:200],
            })
    return disagreements


def verify_mission(project: Path, st: dict, rerun: bool = False) -> dict:
    rerun_disagreements = []
    if rerun:
        rerun_disagreements = rerun_evidence(project, st)
        bad = {d["id"] for d in rerun_disagreements}
        if bad:
            for ev in st["evidence"]:
                if ev["id"] in bad:
                    ev["exit"] = next(d["actual"] for d in rerun_disagreements
                                      if d["id"] == ev["id"])
    rows = []
    for c in st["criteria"]:
        status, reasons = gate_status(project, st, c)
        rows.append({"id": c["id"], "text": c["text"], "required": c.get("required", True),
                     "status": status, "reasons": reasons})
    required = [r for r in rows if r["required"]]
    complete_ok = all(r["status"] == "pass" for r in required) and bool(required)
    return {
        "criteria": rows,
        "required_total": len(required),
        "required_pass": sum(1 for r in required if r["status"] == "pass"),
        "can_complete": complete_ok,
        "phase": st["mission"]["phase"],
        "rerun_disagreements": rerun_disagreements,
    }


def score_workstream(w: dict, ctx: dict) -> int:
    impact = w.get("impact", 2)
    effort = w.get("effort", 2)
    deps_done = all(
        next((o for o in ctx["workstreams"] if o["id"] == dep), {}).get("status") == "done"
        for dep in w.get("depends_on", [])
    )
    score = impact * 3 - effort * 2
    if not deps_done:
        score -= 5
    if w.get("status") == "done":
        score -= 100
    for gid in ctx.get("gate_blockers", []):
        if gid in (w.get("notes") or ""):
            score += 4
    return score


def score_defect(d: dict, ctx: dict) -> int:
    return d.get("severity", 2) * 3 - 2


def next_action(project: Path, st: dict) -> dict:
    report = verify_mission(project, st)
    gate_blockers = [
        c["id"] for c in report["criteria"]
        if c["required"] and c["status"] in ("failed", "stale")
    ]
    ctx = {"workstreams": st["workstreams"], "gate_blockers": gate_blockers}
    candidates: list[dict] = []
    for d in st["defects"]:
        if d.get("status") != "open":
            continue
        candidates.append({
            "type": "defect", "id": d["id"], "title": d["title"],
            "score": score_defect(d, ctx),
            "why": f"severity {d.get('severity', 2)}/3 open defect",
        })
    for w in st["workstreams"]:
        if w.get("status") != "open":
            continue
        deps = w.get("depends_on", [])
        waiting = [dep for dep in deps
                   if next((o for o in st['workstreams'] if o['id'] == dep), {}).get('status') != 'done']
        why = f"impact {w.get('impact', 2)}/3"
        if waiting:
            why += f"; waiting on {', '.join(waiting)}"
        for gid in gate_blockers:
            if gid in (w.get("notes") or ""):
                why += f"; unblocks required gate {gid}"
        candidates.append({
            "type": "workstream", "id": w["id"], "title": w["title"],
            "score": score_workstream(w, ctx), "why": why,
        })
    for row in report["criteria"]:
        if row["required"] and row["status"] in ("failed", "stale"):
            candidates.append({
                "type": "re-verify", "id": row["id"], "title": row["text"][:90],
                "score": 8,
                "why": f"required gate is {row['status']}; evidence must be refreshed",
            })
    for b in st["blockers"]:
        if not b.get("resolved") and b.get("kind") == "failure":
            candidates.append({
                "type": "blocker-failure", "id": b["id"], "title": b["title"],
                "score": 6, "why": "unresolved failure-class blocker",
            })
    candidates.sort(key=lambda item: (-item["score"], item["id"]))
    return {
        "recommendation": candidates[0] if candidates else None,
        "alternatives": candidates[1:4],
        "gates": {"required_pass": report["required_pass"],
                  "required_total": report["required_total"],
                  "can_complete": report["can_complete"]},
    }


def checkpoint_path(project: Path) -> Path:
    return state_mod.state_dir(project) / "checkpoints"


def create_checkpoint(project: Path, st: dict, note: str = "",
                      tests_command: str | None = None) -> dict:
    cp_dir = checkpoint_path(project)
    cp_dir.mkdir(parents=True, exist_ok=True)
    n = max((c.get("n", 0) for c in st.get("checkpoints", [])), default=0) + 1
    ts = state_mod.now_iso()
    changed = gitinfo.dirty_files(project)
    tests = None
    if tests_command:
        outcome = run_command(project, tests_command)
        tests = {"command": tests_command, "exit": outcome["exit"],
                 "summary": outcome["summary"]}
    payload = {
        "schema": state_mod.SCHEMA_VERSION,
        "mission_id": st["mission"]["id"],
        "n": n,
        "created_at": ts,
        "note": clip(note, 300),
        "git": {
            "commit": gitinfo.head_commit(project),
            "branch": gitinfo.branch(project),
            "dirty_files": changed[:200],
        },
        "tests": tests,
        "next_recommended": next_action(project, st)["recommendation"],
        "state_snapshot": st,
        "checksum": "",
    }
    fname = f"checkpoint-{n:04d}-{ts.replace(':', '')}.json"
    path = cp_dir / fname
    payload["file"] = f"checkpoints/{fname}"
    body = json.dumps({k: v for k, v in payload.items() if k != "checksum"},
                      ensure_ascii=False, sort_keys=True)
    payload["checksum"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    st.setdefault("checkpoints", []).append({
        "n": n, "file": f"checkpoints/{fname}", "commit": payload["git"]["commit"],
        "created_at": ts, "note": clip(note, 120),
    })
    cps = sorted(st["checkpoints"], key=lambda c: c.get("n", 0))
    while len(cps) > CHECKPOINT_LIMIT:
        old = cps.pop(0)
        old_path = cp_dir / Path(old["file"]).name
        try:
            old_path.unlink()
        except OSError:
            pass
    st["checkpoints"] = cps
    return payload


def read_checkpoint(project: Path, rel_name: str) -> dict:
    path = state_mod.state_dir(project) / rel_name
    raw = json.loads(path.read_text(encoding="utf-8"))
    checksum = raw.pop("checksum", "")
    body = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != checksum:
        raise ValueError(f"checkpoint checksum mismatch: {rel_name}")
    return raw


def restore_checkpoint(project: Path, rel_name: str) -> dict:
    payload = read_checkpoint(project, rel_name)
    snapshot = payload.get("state_snapshot")
    if not snapshot:
        raise ValueError("checkpoint has no state snapshot")
    problems = state_mod.validate(snapshot)
    if problems:
        raise ValueError("snapshot invalid:\n  - " + "\n  - ".join(problems))
    state_mod.save(project, snapshot)
    return payload


def resume_brief(project: Path, st: dict) -> str:
    report = verify_mission(project, st)
    na = next_action(project, st)
    lines: list[str] = []
    m = st["mission"]
    lines.append(f"MISSION {m['id']} — phase: {m['phase']}")
    lines.append(f"GOAL: {m['goal']}")
    if m.get("why"):
        lines.append(f"WHY: {m['why']}")
    for dec in st.get("decisions", [])[-5:]:
        lines.append(f"DECISION {dec['id']}: chose “{dec['choice']}” because {dec['reason']}"
                     + (f" (revisit when: {dec['revisit_when']})" if dec.get("revisit_when") else ""))
    lines.append(f"GATES: {report['required_pass']}/{report['required_total']} required criteria pass"
                 + (" — MISSION MAY COMPLETE" if report["can_complete"] else ""))
    for row in report["criteria"]:
        if row["status"] != "pass":
            reasons = "; ".join(row["reasons"]) if row["reasons"] else ""
            req = "required" if row["required"] else "optional"
            lines.append(f"  [{row['status']}] {row['id']} ({req}): {row['text'][:110]} {reasons}".rstrip())
    stale = [e["id"] for e in st["evidence"] if _freshness(project, e) == "stale"]
    if stale:
        lines.append("STALE EVIDENCE (do not trust; refresh): " + ", ".join(stale[:12]))
    unverified = [e["id"] for e in st["evidence"] if not e.get("verified")]
    if unverified:
        lines.append("UNVERIFIED CLAIMS (never cite as proof): " + ", ".join(unverified[:12]))
    defects = [d for d in st["defects"] if d.get("status") == "open"]
    if defects:
        lines.append("OPEN DEFECTS: " + "; ".join(f"{d['id']} {d['title'][:70]}" for d in defects))
    blocks = [b for b in st["blockers"] if not b.get("resolved")]
    if blocks:
        lines.append("BLOCKERS: " + "; ".join(f"{b['id']}({b['kind']}) {b['title'][:60]}" for b in blocks))
    done = [w["id"] + " " + w["title"][:60] for w in st["workstreams"] if w.get("status") == "done"]
    if done:
        lines.append("DO NOT REPEAT (completed): " + "; ".join(done[:10]))
    from . import regressions as reg
    changed = gitinfo.dirty_files(project)
    watch = reg.surface_block(str(project), st.get("regressions", []), changed)
    if watch:
        lines.append(watch)
    for r in st.get("regressions", [])[-3:]:
        lines.append(f"REGRESSION MEMORY {r['id']}: {r['defect'][:80]} — guard: {r.get('test', 'n/a')}")
    deploy = st.get("deploy", {})
    lines.append(f"DEPLOY: {deploy.get('state', 'unknown')}"
                 + (f" at {deploy['url']}" if deploy.get("url") else "")
                 + (f" (checked {deploy['last_checked_at']})" if deploy.get("last_checked_at") else ""))
    if st.get("checkpoints"):
        last = st["checkpoints"][-1]
        lines.append(f"LAST CHECKPOINT: #{last['n']} at {last['created_at']}"
                     + (f" commit {last['commit'][:10]}" if last.get("commit") else ""))
    rec = na["recommendation"]
    if rec:
        lines.append(f"NEXT: [{rec['type']} {rec['id']}] {rec['title']} — {rec['why']}")
    elif na["gates"]["can_complete"]:
        lines.append("NEXT: run 'aegis complete' — all required gates pass.")
    else:
        lines.append("NEXT: define workstreams or criteria; nothing actionable is recorded.")
    dirty = gitinfo.dirty_files(project)
    if dirty:
        lines.append(f"GIT: working tree has {len(dirty)} uncommitted change(s)")
    return "\n".join(lines)


def doctor(project: Path) -> dict:
    """Diagnose the mission directory. Returns findings + recovery hints."""
    findings: list[dict] = []
    spath = state_mod.state_path(project)

    def add(severity: str, code: str, message: str, hint: str = "") -> None:
        findings.append({"severity": severity, "code": code, "message": message, "hint": hint})

    if not spath.exists():
        add("error", "NO_STATE", f"no mission state at {spath}", "run 'aegis init'")
        return {"healthy": False, "findings": findings}
    try:
        st, notes = state_mod.load(project)
        for note in notes:
            add("info", "MIGRATED", note)
    except state_mod.StateError as exc:
        bak = spath.with_suffix(".json.bak")
        hint = "recover with 'aegis doctor --repair' or inspect the .bak file" if bak.exists() \
            else "no backup exists; inspect the file manually"
        add("error", "CORRUPT_STATE", str(exc), hint)
        return {"healthy": False, "findings": findings}

    for c in st["criteria"]:
        for ev in c.get("evidence", []):
            if not any(e["id"] == ev for e in st["evidence"]):
                add("error", "DANGLING_REF",
                    f"criterion {c['id']} references missing evidence {ev}",
                    "remove the reference or re-record evidence")
    report = verify_mission(project, st)
    stale_count = sum(1 for row in report["criteria"] if row["status"] == "stale")
    failed_count = sum(1 for row in report["criteria"] if row["status"] == "failed")
    if stale_count:
        add("warn", "STALE_GATES", f"{stale_count} criteria hold only stale evidence",
            "re-run the recorded commands, then 'aegis evidence add --run'")
    if failed_count:
        add("warn", "FAILED_GATES", f"{failed_count} criteria have failing evidence",
            "fix the underlying problem or mark the criterion blocked with a reason")
    trivial = [e["id"] for e in st["evidence"]
               if e.get("verified") and _is_trivial(e.get("command"))]
    if trivial:
        add("warn", "TRIVIAL_EVIDENCE",
            f"evidence {', '.join(trivial[:8])} records trivial command(s) "
            "(true/echo) that verify nothing",
            "replace with a command that exercises real behavior; benchmark "
            "scoring is outcome-based and will not credit these")
    unverified = [e["id"] for e in st["evidence"] if not e.get("verified")]
    if unverified:
        add("info", "UNVERIFIED_EVIDENCE",
            f"{len(unverified)} UNVERIFIED manual claim(s): {', '.join(unverified[:8])}",
            "replace with command-run evidence before completion")
    if gitinfo.available() and gitinfo.is_repo(project):
        dirty = gitinfo.dirty_files(project)
        if dirty:
            add("warn", "DIRTY_TREE", f"{len(dirty)} uncommitted changes",
                "commit or stash; checkpoints pin commits, not dirty trees")
        last_cp = st.get("checkpoints", [])[-1] if st.get("checkpoints") else None
        if last_cp and last_cp.get("commit"):
            head = gitinfo.head_commit(project)
            moved = gitinfo.changed_since(project, last_cp["commit"])
            if head != last_cp["commit"] and moved:
                add("info", "WORK_SINCE_CHECKPOINT",
                    f"{len(moved)} file(s) changed since checkpoint #{last_cp['n']}",
                    "consider creating a fresh checkpoint")
    else:
        add("info", "NO_GIT", "not a git repository; evidence staleness cannot be checked",
            "git init for full protection")
    for cp in st.get("checkpoints", []):
        try:
            read_checkpoint(project, cp["file"])
        except Exception as exc:
            add("error", "BAD_CHECKPOINT", f"{cp['file']}: {exc}",
                "restore state via 'aegis restore --backup' or remove the broken checkpoint")
    listed = {Path(c["file"]).name for c in st.get("checkpoints", [])}
    cp_dir = checkpoint_path(project)
    if cp_dir.is_dir():
        orphans = [p.name for p in cp_dir.glob("checkpoint-*.json")
                   if p.name not in listed]
        if orphans:
            add("info", "ORPHAN_CHECKPOINTS",
                f"{len(orphans)} checkpoint file(s) on disk are not in state: "
                + ", ".join(orphans[-3:]),
                "harmless; restore one with 'aegis restore --checkpoint <name>'")
    healthy = not any(f["severity"] == "error" for f in findings)
    return {"healthy": healthy, "findings": findings,
            "gates": {"required_pass": report["required_pass"],
                      "required_total": report["required_total"]}}

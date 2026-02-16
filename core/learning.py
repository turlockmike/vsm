#!/usr/bin/env python3
"""
VSM Learning System — Recursive Self-Improvement Engine

Transforms cycle experiences into capabilities.
The bridge between "things happened" and "I know how to do things."
"""

import json
import random
from datetime import datetime
from pathlib import Path

VSM_ROOT = Path(__file__).parent.parent
CAPABILITIES_FILE = VSM_ROOT / "state" / "capabilities.json"
EXPERIENCES_FILE = VSM_ROOT / "state" / "experiences.jsonl"
MAX_EXPERIENCES = 100

# Bayesian prior: 2 pseudo-observations prevent 0% or 100% confidence
PRIOR_SUCCESSES = 1
PRIOR_FAILURES = 1


def load_capabilities():
    if not CAPABILITIES_FILE.exists():
        CAPABILITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        CAPABILITIES_FILE.write_text(json.dumps({
            "version": 1,
            "capabilities": {},
            "anti_patterns": {},
            "exploration_log": {
                "last_exploration_cycle": 0,
                "exploration_rate": 0.15,
                "recent_experiments": [],
            },
        }, indent=2))
    return json.loads(CAPABILITIES_FILE.read_text())


def save_capabilities(capabilities):
    capabilities["updated"] = datetime.now().isoformat()
    CAPABILITIES_FILE.write_text(json.dumps(capabilities, indent=2))


def extract_experience(result, state, tasks):
    """Extract structured experience from cycle result. No LLM call — pure Python."""
    return {
        "cycle": state.get("cycle_count", 0),
        "timestamp": datetime.now().isoformat(),
        "model": result.get("model", "unknown"),
        "success": result.get("success", False),
        "cost_usd": result.get("cost_usd", 0),
        "duration_ms": result.get("duration_ms", 0),
        "output_summary": result.get("output", "")[:300],
        "error": result.get("error"),
        "was_exploration": False,
    }


def append_experience(experience):
    """Append to rotating JSONL buffer."""
    EXPERIENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPERIENCES_FILE, "a") as f:
        f.write(json.dumps(experience) + "\n")

    # Rotate: keep last MAX_EXPERIENCES
    try:
        lines = EXPERIENCES_FILE.read_text().strip().split("\n")
        if len(lines) > MAX_EXPERIENCES:
            EXPERIENCES_FILE.write_text("\n".join(lines[-MAX_EXPERIENCES:]) + "\n")
    except Exception:
        pass


def load_recent_experiences(n=10):
    if not EXPERIENCES_FILE.exists():
        return []
    try:
        lines = EXPERIENCES_FILE.read_text().strip().split("\n")
        return [json.loads(line) for line in lines[-n:] if line.strip()]
    except Exception:
        return []


def _compute_confidence(successes, failures):
    total_s = successes + PRIOR_SUCCESSES
    total_f = failures + PRIOR_FAILURES
    return round(total_s / (total_s + total_f), 2)


def update_capabilities_from_experience(capabilities, experience):
    """Update capability confidence from cycle result. No LLM — keyword matching.
    Imprecise but free. Consolidation (haiku, every 10 cycles) corrects errors."""
    output = experience.get("output_summary", "").lower()
    if not output:
        return

    caps = capabilities.get("capabilities", {})
    for cap_id, cap in caps.items():
        tags = cap.get("tags", [])
        keywords = tags + cap_id.split("-")
        if any(kw.lower() in output for kw in keywords if len(kw) > 2):
            cap["times_used"] = cap.get("times_used", 0) + 1
            if experience["success"]:
                cap["times_succeeded"] = cap.get("times_succeeded", 0) + 1
            else:
                cap["times_failed"] = cap.get("times_failed", 0) + 1
            cap["last_used"] = experience["timestamp"]
            cap["confidence"] = _compute_confidence(
                cap.get("times_succeeded", 0),
                cap.get("times_failed", 0),
            )
            break  # One capability per cycle


def should_explore(capabilities, state):
    """Determine if this cycle should explore vs exploit."""
    exp_log = capabilities.get("exploration_log", {})
    rate = exp_log.get("exploration_rate", 0.15)

    recent = load_recent_experiences(n=10)
    if recent:
        # Reduce rate after 3 consecutive exploration failures
        recent_explores = [e for e in recent if e.get("was_exploration")]
        if len(recent_explores) >= 3:
            if all(not e["success"] for e in recent_explores[-3:]):
                rate = max(0.05, rate - 0.05)

        # Increase rate if last 5 were all exploitation
        recent_exploits = [e for e in recent[-5:] if not e.get("was_exploration")]
        if len(recent_exploits) == 5:
            rate = min(0.30, rate + 0.05)

    # Criticality override
    crit = state.get("criticality", 0.5)
    if crit < 0.3:
        return False  # Chaos: only exploit known-good patterns
    if crit > 0.7:
        rate = min(0.40, rate + 0.10)  # Stagnant: explore more

    exp_log["exploration_rate"] = round(rate, 2)
    return random.random() < rate


def consolidate_knowledge(capabilities, run_fn):
    """Every 10 cycles: use haiku to find patterns. ~$0.01/run.

    run_fn: callable(prompt, model, timeout) -> result dict
    This is the ONLY part of learning that costs tokens.
    """
    experiences = load_recent_experiences(n=10)
    if not experiences:
        return

    prompt = (
        "You are the learning subsystem of an autonomous AI computer (VSM). "
        "Review these 10 recent cycle experiences and update the capability registry.\n\n"
        f"## Experiences\n{json.dumps(experiences, indent=2)}\n\n"
        f"## Current Capabilities\n{json.dumps(capabilities.get('capabilities', {}), indent=2)}\n\n"
        f"## Current Anti-Patterns\n{json.dumps(capabilities.get('anti_patterns', {}), indent=2)}\n\n"
        "Output ONLY valid JSON with these fields:\n"
        '{"new_capabilities": [{"id":"...","description":"...","tags":[...],"notes":"..."}], '
        '"updated_capabilities": [{"id":"...","notes":"updated..."}], '
        '"new_anti_patterns": [{"id":"...","description":"...","mitigation":"..."}], '
        '"confidence_adjustments": [{"id":"...","new_confidence":0.8,"reason":"..."}], '
        '"insights": "one sentence summary"}'
    )

    result = run_fn(prompt, model="haiku", timeout=60)
    if result.get("success"):
        _apply_consolidation(capabilities, result.get("output", ""))


def _apply_consolidation(capabilities, output):
    try:
        output = output.strip()
        start = output.find("{")
        end = output.rfind("}") + 1
        if start < 0 or end <= start:
            return
        updates = json.loads(output[start:end])
        now = datetime.now().isoformat()

        for cap in updates.get("new_capabilities", []):
            cid = cap.get("id")
            if cid and cid not in capabilities["capabilities"]:
                capabilities["capabilities"][cid] = {
                    "description": cap.get("description", ""),
                    "confidence": 0.50,
                    "times_used": 0, "times_succeeded": 0, "times_failed": 0,
                    "first_learned": now, "last_used": now,
                    "tags": cap.get("tags", []),
                    "notes": cap.get("notes", ""),
                }

        for update in updates.get("updated_capabilities", []):
            cid = update.get("id")
            if cid and cid in capabilities["capabilities"]:
                for k, v in update.items():
                    if k != "id":
                        capabilities["capabilities"][cid][k] = v

        for ap in updates.get("new_anti_patterns", []):
            aid = ap.get("id")
            if aid and aid not in capabilities["anti_patterns"]:
                capabilities["anti_patterns"][aid] = {
                    "description": ap.get("description", ""),
                    "times_observed": 1,
                    "first_observed": now,
                    "mitigation": ap.get("mitigation", ""),
                }

        for adj in updates.get("confidence_adjustments", []):
            cid = adj.get("id")
            if cid and cid in capabilities["capabilities"]:
                capabilities["capabilities"][cid]["confidence"] = adj["new_confidence"]

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

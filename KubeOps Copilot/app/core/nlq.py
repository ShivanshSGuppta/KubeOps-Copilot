from __future__ import annotations

import json
import re
from typing import Optional

import requests

from .security import Action

# Rule-based patterns
RE_PODS_IN_NS = re.compile(r"\bpods?\s+(in|from)\s+(namespace\s+)?(?P<ns>[a-z0-9\-]+)\b", re.IGNORECASE)
RE_EVENTS_IN_NS = re.compile(r"\bevents?\s+(in|from)\s+(namespace\s+)?(?P<ns>[a-z0-9\-]+)\b", re.IGNORECASE)
RE_FAILING_PODS = re.compile(r"\b(failing|crashing|error)\s+pods?\s+(in|from)\s+(namespace\s+)?(?P<ns>[a-z0-9\-]+)\b", re.IGNORECASE)
RE_LOGS = re.compile(r"\blogs?\s+(for|of)\s+(pod\s+)?(?P<pod>[a-z0-9\-]+)\s+(in|from)\s+(namespace\s+)?(?P<ns>[a-z0-9\-]+)\b", re.IGNORECASE)

def parse_rule_based(prompt: str) -> Action:
    p = (prompt or "").strip()
    if not p:
        return Action("cluster_overview", {})

    lp = p.lower()

    if "namespaces" in lp or ("namespace" in lp and "list" in lp and "pod" not in lp):
        return Action("list_namespaces", {})

    if "nodes" in lp:
        return Action("list_nodes", {})

    if "overview" in lp or "cluster" in lp:
        return Action("cluster_overview", {})

    m = RE_LOGS.search(p)
    if m:
        return Action("get_pod_logs", {"namespace": m.group("ns"), "pod": m.group("pod"), "tail_lines": 200})

    m = RE_FAILING_PODS.search(p)
    if m:
        return Action("list_pods", {"namespace": m.group("ns"), "filter": "failing"})

    m = RE_PODS_IN_NS.search(p)
    if m:
        return Action("list_pods", {"namespace": m.group("ns"), "filter": "all"})

    m = RE_EVENTS_IN_NS.search(p)
    if m:
        return Action("list_events", {"namespace": m.group("ns")})

    return Action("cluster_overview", {})

def parse_with_ollama(prompt: str, ollama_url: str, model: str) -> Optional[Action]:
    sys = (
        "Return ONLY valid JSON with keys: action, params. "
        "Allowed actions: cluster_overview, list_namespaces, list_nodes, list_pods, get_pod_logs, list_events. "
        "Params must include namespace and pod when required. "
        "Never propose mutating actions."
    )
    full_prompt = f"{sys}\n\nUser: {prompt}\nJSON:"
    try:
        resp = requests.post(
            f"{ollama_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False},
            timeout=12,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        obj = json.loads(text[start:end + 1])
        action = obj.get("action")
        params = obj.get("params") or {}
        if not action:
            return None
        return Action(str(action), dict(params))
    except Exception:
        return None

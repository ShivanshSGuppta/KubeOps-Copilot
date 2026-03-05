from __future__ import annotations

import re
from dataclasses import dataclass

# Kubernetes DNS label for names like namespaces and pod names.
K8S_NAME_RE = re.compile(r"^[a-z0-9]([\-a-z0-9]*[a-z0-9])?$")

ALLOWED_ACTIONS = {
    "cluster_overview",
    "list_namespaces",
    "list_nodes",
    "list_pods",
    "get_pod_logs",
    "list_events",
}

@dataclass(frozen=True)
class Action:
    name: str
    params: dict

def sanitize_k8s_name(value: str) -> str:
    v = (value or "").strip().lower()
    if not v or len(v) > 253:
        raise ValueError("Invalid Kubernetes name length.")
    if not K8S_NAME_RE.match(v):
        raise ValueError("Invalid Kubernetes name format.")
    return v

def validate_action(action: Action) -> Action:
    if action.name not in ALLOWED_ACTIONS:
        raise ValueError(f"Action not allowed: {action.name}")

    params = dict(action.params or {})

    if action.name in {"list_pods", "get_pod_logs", "list_events"}:
        ns = params.get("namespace")
        if ns:
            params["namespace"] = sanitize_k8s_name(str(ns))

    if action.name == "get_pod_logs":
        pod = params.get("pod")
        if pod:
            params["pod"] = sanitize_k8s_name(str(pod))
        tail = params.get("tail_lines", 200)
        try:
            tail_i = int(tail)
        except Exception:
            tail_i = 200
        params["tail_lines"] = max(20, min(2000, tail_i))

    return Action(name=action.name, params=params)

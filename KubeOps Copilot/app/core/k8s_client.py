from __future__ import annotations

import json
import os
from typing import Any

from .config import Settings

class K8sAdapter:
    def list_namespaces(self) -> list[str]: ...
    def list_nodes(self) -> list[dict[str, Any]]: ...
    def list_pods(self, namespace: str) -> list[dict[str, Any]]: ...
    def get_pod_logs(self, namespace: str, pod: str, tail_lines: int = 200) -> list[str]: ...
    def list_events(self, namespace: str) -> list[dict[str, Any]]: ...

class MockK8sAdapter(K8sAdapter):
    def __init__(self, mock_path: str) -> None:
        with open(mock_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def list_namespaces(self) -> list[str]:
        return list(self.data.get("namespaces", []))

    def list_nodes(self) -> list[dict[str, Any]]:
        return list(self.data.get("nodes", []))

    def list_pods(self, namespace: str) -> list[dict[str, Any]]:
        return list(self.data.get("pods", {}).get(namespace, []))

    def get_pod_logs(self, namespace: str, pod: str, tail_lines: int = 200) -> list[str]:
        key = f"{namespace}/{pod}"
        lines = self.data.get("logs", {}).get(key, [])
        return list(lines)[-tail_lines:]

    def list_events(self, namespace: str) -> list[dict[str, Any]]:
        return list(self.data.get("events", {}).get(namespace, []))

class RealK8sAdapter(K8sAdapter):
    def __init__(self, settings: Settings) -> None:
        from kubernetes import client, config

        if settings.kubeconfig:
            config.load_kube_config(config_file=settings.kubeconfig)
        else:
            try:
                config.load_kube_config()
            except Exception:
                config.load_incluster_config()

        self.v1 = client.CoreV1Api()

    def list_namespaces(self) -> list[str]:
        ns_list = self.v1.list_namespace()
        return sorted([item.metadata.name for item in ns_list.items if item.metadata and item.metadata.name])

    def list_nodes(self) -> list[dict[str, Any]]:
        nodes = self.v1.list_node().items
        out: list[dict[str, Any]] = []
        for n in nodes:
            name = n.metadata.name if n.metadata else "unknown"
            status = "Unknown"
            if n.status and n.status.conditions:
                for c in n.status.conditions:
                    if c.type == "Ready":
                        status = "Ready" if c.status == "True" else "NotReady"
            version = n.status.node_info.kubelet_version if n.status and n.status.node_info else ""
            out.append({"name": name, "status": status, "kubeletVersion": version})
        return out

    def list_pods(self, namespace: str) -> list[dict[str, Any]]:
        pods = self.v1.list_namespaced_pod(namespace=namespace).items
        out: list[dict[str, Any]] = []
        for p in pods:
            name = p.metadata.name if p.metadata else "unknown"
            status = p.status.phase if p.status else "Unknown"
            restarts = 0
            if p.status and p.status.container_statuses:
                restarts = sum(cs.restart_count or 0 for cs in p.status.container_statuses)
                for cs in p.status.container_statuses:
                    if cs.state and cs.state.waiting and cs.state.waiting.reason:
                        status = cs.state.waiting.reason
            node = p.spec.node_name if p.spec else ""
            age = ""
            if p.metadata and p.metadata.creation_timestamp:
                age = str(p.metadata.creation_timestamp)
            out.append({"name": name, "status": status, "restarts": restarts, "node": node, "age": age})
        return out

    def get_pod_logs(self, namespace: str, pod: str, tail_lines: int = 200) -> list[str]:
        text = self.v1.read_namespaced_pod_log(
            name=pod,
            namespace=namespace,
            tail_lines=tail_lines,
            timestamps=True,
        )
        return text.splitlines()

    def list_events(self, namespace: str) -> list[dict[str, Any]]:
        events = self.v1.list_namespaced_event(namespace=namespace).items
        out: list[dict[str, Any]] = []
        for e in events:
            out.append({
                "type": getattr(e, "type", ""),
                "reason": getattr(e, "reason", ""),
                "message": getattr(e, "message", ""),
                "involvedObject": getattr(getattr(e, "involved_object", None), "name", ""),
                "time": str(getattr(e, "last_timestamp", "") or getattr(e, "event_time", "") or ""),
            })
        return out

def build_adapter(settings: Settings) -> K8sAdapter:
    if settings.k8s_mode == "real":
        return RealK8sAdapter(settings)

    mock_path = os.path.join(os.getcwd(), "sample", "mock_cluster.json")
    return MockK8sAdapter(mock_path)

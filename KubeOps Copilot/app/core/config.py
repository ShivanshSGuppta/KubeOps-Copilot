from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    k8s_mode: str
    kubeconfig: str | None
    use_ollama: bool
    ollama_url: str
    ollama_model: str
    data_dir: str

def load_settings() -> Settings:
    mode = os.getenv("K8S_MODE", "mock").strip().lower()
    if mode not in {"mock", "real"}:
        mode = "mock"

    kubeconfig = os.getenv("KUBECONFIG") or None

    use_ollama = os.getenv("USE_OLLAMA", "0").strip().lower() in {"1", "true", "yes"}
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1").strip()

    data_dir = os.getenv("DATA_DIR", "./data").strip()
    os.makedirs(data_dir, exist_ok=True)

    return Settings(
        k8s_mode=mode,
        kubeconfig=kubeconfig,
        use_ollama=use_ollama,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        data_dir=data_dir,
    )

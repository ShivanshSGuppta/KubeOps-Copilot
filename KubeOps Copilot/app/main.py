from __future__ import annotations

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .core.config import load_settings
from .core.k8s_client import build_adapter
from .core.security import Action, validate_action
from .core.audit import AuditLog, AuditEvent, now_iso
from .core import nlq as nlq_mod

settings = load_settings()
k8s = build_adapter(settings)
audit = AuditLog(db_path=f"{settings.data_dir.rstrip('/')}/audit.sqlite")

app = FastAPI(title="KubeOps Copilot", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def is_failing(status: str) -> bool:
    s = (status or "").lower()
    if "running" in s or s in {"succeeded"}:
        return False
    return True

def diagnose_pod(pod: dict) -> list[str]:
    status = str(pod.get("status") or "")
    restarts = int(pod.get("restarts") or 0)
    tips: list[str] = []
    low = status.lower()

    if "crashloop" in low:
        tips.append("CrashLoopBackOff: open logs; verify env vars and dependent services (DB/queue).")
        tips.append("Check readiness/liveness probes and resource limits (CPU/memory).")
    if "imagepull" in low:
        tips.append("Image pull error: verify image tag and registry credentials.")
    if restarts >= 3:
        tips.append("High restart count: check OOMKilled events and memory limits.")
    return tips

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})

@app.get("/cluster", response_class=HTMLResponse)
def cluster(request: Request):
    namespaces = k8s.list_namespaces()
    nodes = k8s.list_nodes()
    pod_counts = {}
    failing_counts = {}
    for ns in namespaces:
        pods = k8s.list_pods(ns)
        pod_counts[ns] = len(pods)
        failing_counts[ns] = sum(1 for p in pods if is_failing(str(p.get("status",""))))
    return templates.TemplateResponse(
        "cluster.html",
        {"request": request, "settings": settings, "namespaces": namespaces, "nodes": nodes, "pod_counts": pod_counts, "failing_counts": failing_counts},
    )

@app.get("/namespaces", response_class=HTMLResponse)
def namespaces(request: Request):
    namespaces = k8s.list_namespaces()
    return templates.TemplateResponse("namespaces.html", {"request": request, "settings": settings, "namespaces": namespaces})

@app.get("/namespaces/{namespace}/pods", response_class=HTMLResponse)
def pods(request: Request, namespace: str, filter: str = "all"):
    action = validate_action(Action("list_pods", {"namespace": namespace, "filter": filter}))
    pods = k8s.list_pods(action.params["namespace"])
    if filter == "failing":
        pods = [p for p in pods if is_failing(str(p.get("status","")))]
    for p in pods:
        p["tips"] = diagnose_pod(p)
    return templates.TemplateResponse("pods.html", {"request": request, "settings": settings, "namespace": action.params["namespace"], "pods": pods, "filter": filter})

@app.get("/namespaces/{namespace}/events", response_class=HTMLResponse)
def events(request: Request, namespace: str):
    action = validate_action(Action("list_events", {"namespace": namespace}))
    events = k8s.list_events(action.params["namespace"])
    return templates.TemplateResponse("events.html", {"request": request, "settings": settings, "namespace": action.params["namespace"], "events": events})

@app.get("/namespaces/{namespace}/pods/{pod}/logs", response_class=HTMLResponse)
def pod_logs(request: Request, namespace: str, pod: str, tail: int = 200):
    action = validate_action(Action("get_pod_logs", {"namespace": namespace, "pod": pod, "tail_lines": tail}))
    lines = k8s.get_pod_logs(action.params["namespace"], action.params["pod"], action.params["tail_lines"])
    return templates.TemplateResponse("logs.html", {"request": request, "settings": settings, "namespace": action.params["namespace"], "pod": action.params["pod"], "tail": action.params["tail_lines"], "lines": lines})

@app.get("/nlq", response_class=HTMLResponse)
def nlq_page(request: Request):
    return templates.TemplateResponse("nlq.html", {"request": request, "settings": settings})

@app.post("/api/nlq", response_class=JSONResponse)
async def nlq_api(request: Request, prompt: str = Form(...)):
    ua = request.headers.get("user-agent", "")
    route = "/api/nlq"
    parsed = None

    if settings.use_ollama:
        parsed = nlq_mod.parse_with_ollama(prompt, settings.ollama_url, settings.ollama_model)

    if parsed is None:
        parsed = nlq_mod.parse_rule_based(prompt)

    status = "ok"
    details = ""
    result = None

    try:
        action = validate_action(parsed)
        result = execute_action(action)
    except Exception as e:
        status = "error"
        details = str(e)
        action = parsed

    audit.write(
        AuditEvent(
            ts=now_iso(),
            route=route,
            user_agent=ua,
            prompt=prompt,
            action=f"{action.name}:{action.params}",
            status=status,
            details=details,
        )
    )

    return JSONResponse({"status": status, "action": {"name": action.name, "params": action.params}, "result": result, "error": details})

def execute_action(action: Action):
    name = action.name
    p = action.params or {}

    if name == "cluster_overview":
        return {"namespaces": k8s.list_namespaces(), "nodes": k8s.list_nodes()}

    if name == "list_namespaces":
        return {"namespaces": k8s.list_namespaces()}

    if name == "list_nodes":
        return {"nodes": k8s.list_nodes()}

    if name == "list_pods":
        ns = p.get("namespace", "default")
        pods = k8s.list_pods(ns)
        if p.get("filter") == "failing":
            pods = [pp for pp in pods if is_failing(str(pp.get("status","")))]
        return {"namespace": ns, "pods": pods}

    if name == "get_pod_logs":
        ns = p.get("namespace", "default")
        pod = p.get("pod")
        tail = int(p.get("tail_lines", 200))
        lines = k8s.get_pod_logs(ns, pod, tail)
        return {"namespace": ns, "pod": pod, "tail_lines": tail, "lines": lines}

    if name == "list_events":
        ns = p.get("namespace", "default")
        return {"namespace": ns, "events": k8s.list_events(ns)}

    raise ValueError("Unsupported action")


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return templates.TemplateResponse(
        "help.html",
        {
            "request": request,
            "settings": settings,
            "title": "Help",
        },
    )

@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    rows = audit.tail(200)
    return templates.TemplateResponse("audit.html", {"request": request, "settings": settings, "rows": rows})

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import ensure_within, safe_slug, sha256_file, utc_now, write_json, write_jsonl


PROJECT_DIRS = (
    "evidence",
    "sources/raw",
    "sources/normalized",
    "analysis",
    "attachments",
    "history",
)


def find_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / ".universal-distiller-root").is_file():
            return candidate
    raise FileNotFoundError("Cannot locate .universal-distiller-root")


def validate_root(root: Path) -> Path:
    root = root.resolve()
    if not (root / ".universal-distiller-root").is_file():
        raise ValueError(f"Not a Universal Distiller root: {root}")
    return root


def validate_project_dir(project_dir: Path) -> Path:
    project_dir = project_dir.resolve()
    root = find_root(project_dir)
    ensure_within(root / "projects", project_dir)
    if not (project_dir / "project.json").is_file():
        raise ValueError(f"Not a Universal Distiller project: {project_dir}")
    return project_dir


def initialize_project(root: Path, title: str, goal: str, task_type: str = "auto") -> Path:
    root = validate_root(root)
    slug = safe_slug(title)
    project_dir = ensure_within(root, root / "projects" / slug)
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")
    for relative in PROJECT_DIRS:
        (project_dir / relative).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0",
        "slug": slug,
        "title": title.strip(),
        "goal": goal.strip(),
        "task_type": task_type,
        "status": "initialized",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "report": "report.html",
    }
    write_json(project_dir / "project.json", manifest)
    write_json(
        project_dir / "analysis" / "research-plan.json",
        {
            "schema_version": "1.0",
            "goal": goal.strip(),
            "task_type": task_type,
            "core_questions": [],
            "supporting_questions": [],
            "source_plan": [],
            "stop_conditions": [],
            "plan_changes": [],
        },
    )
    write_jsonl(project_dir / "evidence" / "sources.jsonl", [])
    write_jsonl(project_dir / "evidence" / "claims.jsonl", [])
    write_json(
        project_dir / "analysis" / "result.json",
        {
            "schema_version": "1.0",
            "title": title.strip(),
            "question": goal.strip(),
            "one_sentence_answer": "",
            "executive_summary": [],
            "key_findings": [],
            "uncertainties": [],
            "recommendations": [],
            "attachment_notes": [],
        },
    )
    return project_dir


def project_manifest(project_dir: Path) -> dict[str, Any]:
    project_dir = validate_project_dir(project_dir)
    files: list[dict[str, Any]] = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file() or "history" in path.parts:
            continue
        files.append(
            {
                "path": path.relative_to(project_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {"generated_at": utc_now(), "files": files}


def snapshot_project(project_dir: Path) -> Path:
    project_dir = validate_project_dir(project_dir)
    history_root = project_dir / "history"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot_dir = history_root / timestamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for name in ("project.json", "report.html", "report.md", "evidence", "analysis"):
        source = project_dir / name
        if not source.exists():
            continue
        destination = snapshot_dir / name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    write_json(snapshot_dir / "manifest.json", project_manifest(project_dir))
    return snapshot_dir


def compare_manifests(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old = {item["path"]: item for item in before.get("files", [])}
    new = {item["path"]: item for item in after.get("files", [])}
    added = sorted(path for path in new if path not in old)
    removed = sorted(path for path in old if path not in new)
    changed = sorted(path for path in new if path in old and new[path]["sha256"] != old[path]["sha256"])
    return {
        "generated_at": utc_now(),
        "added": added,
        "changed": changed,
        "removed": removed,
        "has_changes": bool(added or changed or removed),
    }

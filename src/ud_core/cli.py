from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .io_utils import read_json, read_jsonl, write_json, configure_console
from .models import validate_research
from .project import (
    compare_manifests,
    find_root,
    initialize_project,
    project_manifest,
    snapshot_project,
    validate_project_dir,
    validate_root,
)
from .report import render_project
from .collect import collect, record_gap, add_claim
from .models import SOURCE_TIERS


def resolve_root(value: str | None) -> Path:
    if value:
        return validate_root(Path(value))
    return validate_root(find_root(Path.cwd()))


def command_init(args: argparse.Namespace) -> int:
    if args.root:
        root = Path(args.root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        (root / ".universal-distiller-root").touch(exist_ok=True)
    project_dir = initialize_project(resolve_root(args.root), args.title, args.goal, args.task_type)
    print(project_dir)
    return 0


def command_validate(args: argparse.Namespace) -> int:
    project_dir = validate_project_dir(Path(args.project))
    result = validate_research(
        read_jsonl(project_dir / "evidence" / "sources.jsonl"),
        read_jsonl(project_dir / "evidence" / "claims.jsonl"),
        project_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


def command_render(args: argparse.Namespace) -> int:
    validation = render_project(validate_project_dir(Path(args.project)))
    print(json.dumps(validation["summary"], ensure_ascii=False, indent=2))
    return 0


def command_snapshot(args: argparse.Namespace) -> int:
    project_dir = validate_project_dir(Path(args.project))
    before = project_manifest(project_dir)
    snapshot_dir = snapshot_project(project_dir)
    write_json(snapshot_dir / "before-update.json", before)
    print(snapshot_dir)
    return 0


def command_diff(args: argparse.Namespace) -> int:
    project_dir = validate_project_dir(Path(args.project))
    snapshot_dir = Path(args.snapshot).resolve()
    ensure_snapshot = snapshot_dir / "before-update.json"
    if not ensure_snapshot.is_file() or snapshot_dir.parent != project_dir / "history":
        raise ValueError(f"Not a Universal Distiller snapshot: {snapshot_dir}")
    before = read_json(ensure_snapshot)
    after = project_manifest(project_dir)
    changes = compare_manifests(before, after)
    write_json(project_dir / "analysis" / "changes.json", changes)
    print(json.dumps(changes, ensure_ascii=False, indent=2))
    return 0


def command_collect(args: argparse.Namespace) -> int:
    project = validate_project_dir(Path(args.project))
    location = args.file or args.url
    try:
        result = collect(project, location, local=bool(args.file), title=args.title,
                         tier=args.tier, publisher=args.publisher, group=args.group,
                         published_at=args.published_at)
    except Exception as exc:
        record_gap(project, location, exc)
        raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_claim(args: argparse.Namespace) -> int:
    project = validate_project_dir(Path(args.project))
    add_claim(project, read_json(Path(args.file)))
    print("Claim added")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="universal-distiller")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Archive an explicit URL or UTF-8 file")
    collect_parser.add_argument("--project", required=True)
    location = collect_parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--url")
    location.add_argument("--file")
    collect_parser.add_argument("--title", default="")
    collect_parser.add_argument("--tier", choices=sorted(SOURCE_TIERS), default="unknown")
    collect_parser.add_argument("--publisher", default="")
    collect_parser.add_argument("--group", default="", help="Independent origin, not republisher")
    collect_parser.add_argument("--published-at", default="", help="Known publication date, YYYY-MM-DD")
    collect_parser.set_defaults(handler=command_collect)

    claim_parser = subparsers.add_parser("claim", help="Validate and add a reviewed claim JSON")
    claim_parser.add_argument("--project", required=True)
    claim_parser.add_argument("--file", required=True)
    claim_parser.set_defaults(handler=command_claim)

    init_parser = subparsers.add_parser("init", help="Create an isolated research project")
    init_parser.add_argument("--root")
    init_parser.add_argument("--title", required=True)
    init_parser.add_argument("--goal", required=True)
    init_parser.add_argument("--task-type", default="auto")
    init_parser.set_defaults(handler=command_init)

    validate_parser = subparsers.add_parser("validate", help="Validate sources and claims")
    validate_parser.add_argument("--project", required=True)
    validate_parser.set_defaults(handler=command_validate)

    render_parser = subparsers.add_parser("render", help="Generate offline HTML and Markdown reports")
    render_parser.add_argument("--project", required=True)
    render_parser.set_defaults(handler=command_render)

    snapshot_parser = subparsers.add_parser("snapshot", help="Preserve the current project before update")
    snapshot_parser.add_argument("--project", required=True)
    snapshot_parser.set_defaults(handler=command_snapshot)

    diff_parser = subparsers.add_parser("diff", help="Compare a project with a prior snapshot")
    diff_parser.add_argument("--project", required=True)
    diff_parser.add_argument("--snapshot", required=True)
    diff_parser.set_defaults(handler=command_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

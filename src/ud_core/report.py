from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .io_utils import read_json, read_jsonl, utc_now
from .models import validate_research


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_list(items: list[Any], empty: str = "未记录") -> str:
    if not items:
        return f'<p class="muted">{esc(empty)}</p>'
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def claim_card(claim: dict[str, Any], source_index: dict[str, dict[str, Any]]) -> str:
    badges = (
        f'<span class="badge">{esc(claim.get("type", "unknown"))}</span>'
        f'<span class="badge {esc(claim.get("status", ""))}">{esc(claim.get("status", "unknown"))}</span>'
        f'<span class="badge">{esc(claim.get("confidence", "unknown"))}</span>'
    )
    evidence_links: list[str] = []
    for source_id in claim.get("evidence", []):
        source = source_index.get(source_id)
        if source:
            evidence_links.append(f'<a href="#source-{esc(source_id)}">{esc(source.get("title", source_id))}</a>')
    evidence = " · ".join(evidence_links) or "无可追溯证据"
    opposing = " · ".join(f'<a href="#source-{esc(sid)}">{esc(source_index[sid]["title"])}</a>' for sid in claim.get("opposing_evidence", []) if sid in source_index)
    quotes = "".join(f'<blockquote>{esc(quote)} <small>— {esc(sid)}</small></blockquote>' for sid, quote in claim.get("quotes", {}).items())
    return (
        f'<article class="claim" id="claim-{esc(claim.get("id", ""))}">'
        f"<div>{badges}</div><h3>{esc(claim.get('text', ''))}</h3>"
        f'<p class="evidence">证据：{evidence}</p>'
        f'{("<p>相反证据：" + opposing + "</p>") if opposing else ""}{quotes}</article>'
    )


def build_html(project: dict[str, Any], result: dict[str, Any], sources: list[dict[str, Any]], claims: list[dict[str, Any]]) -> str:
    validation = validate_research(sources, claims)
    source_index = {source["id"]: source for source in sources if source.get("id")}
    included_claims = [claim for claim in claims if claim.get("included")]
    included_claims.sort(key=lambda item: (item.get("importance", 0), item.get("relevance", 0)), reverse=True)
    source_cards = []
    used_source_ids = {
        source_id for claim in included_claims for source_id in claim.get("evidence", []) + claim.get("opposing_evidence", [])
    }
    for source in sources:
        if source.get("id") not in used_source_ids:
            continue
        uri = source.get("uri", "")
        link = f'<a href="{esc(uri)}">{esc(source.get("title", source.get("id")))}</a>' if uri.startswith(("http://", "https://")) else esc(source.get("title", source.get("id")))
        source_cards.append(
            f'<article class="source" id="source-{esc(source.get("id"))}"><h3>{link}</h3>'
            f'<p>{esc(source.get("publisher", "未知发布者"))} · {esc(source.get("published_at", "日期未知"))} · '
            f'{esc(source.get("tier", "unknown"))}</p><blockquote>{esc(source.get("excerpt", "未保存摘录"))}</blockquote></article>'
        )

    css = """
    :root{color-scheme:light;--ink:#18212f;--muted:#64748b;--line:#dbe2ea;--paper:#fff;--soft:#f5f7fa;--accent:#2457d6;--warn:#a15c00}
    *{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}
    main{max-width:1040px;margin:auto;background:var(--paper);min-height:100vh;padding:56px 72px}
    h1{font-size:40px;line-height:1.15;margin:0 0 12px}h2{margin:48px 0 16px;padding-bottom:10px;border-bottom:1px solid var(--line)}
    h3{font-size:18px;margin:8px 0}.kicker,.muted{color:var(--muted)}.answer{font-size:22px;border-left:5px solid var(--accent);padding:18px 22px;background:#eef4ff}
    .meta{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:14px}.claim,.source,.panel{border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
    .badge{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:2px 8px;margin:0 6px 5px 0;font-size:12px;color:var(--muted)}
    .badge.conflicted{color:var(--warn);border-color:#e9be78}.badge.unsupported{color:#a12b2b;border-color:#e7a3a3}.evidence{font-size:14px;color:var(--muted)}
    a{color:var(--accent)}blockquote{margin:12px 0 0;padding-left:14px;border-left:3px solid var(--line);color:#334155}
    footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
    @media(max-width:720px){main{padding:32px 22px}h1{font-size:32px}}
    @media print{body{background:#fff}main{max-width:none;padding:0}.claim,.source,.panel{break-inside:avoid}a{color:inherit;text-decoration:none}}
    """
    claims_html = "".join(claim_card(claim, source_index) for claim in included_claims)
    if not claims_html:
        claims_html = '<p class="muted">尚无通过筛选的核心结论。</p>'
    status = "通过" if validation["valid"] else "存在错误"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(result.get("title") or project.get("title"))}</title><style>{css}</style></head>
<body><main>
<header><p class="kicker">UNIVERSAL DISTILLER · 离线研究报告</p>
<h1>{esc(result.get("title") or project.get("title"))}</h1>
<p>{esc(result.get("question") or project.get("goal"))}</p>
<div class="meta"><span>生成：{esc(utc_now())}</span><span>结构校验：{status}（不等于事实已核实）</span>
<span>来源：{len(sources)}</span><span>结论：{len(claims)}</span></div></header>
<section><h2>研究者摘要</h2><p class="muted">摘要由研究者撰写；引用与证据见下方逐条结论。</p><p class="answer">{esc(result.get("one_sentence_answer") or "研究尚未完成。")}</p></section>
<section><h2>执行摘要</h2>{render_list(result.get("executive_summary", []))}</section>
<section><h2>核心发现</h2>{claims_html}</section>
<section><h2>不确定性与资料缺口</h2>{render_list(result.get("uncertainties", []), "未填写不确定性；不代表不存在资料缺口。")}</section>
<section><h2>判断与建议</h2>{render_list(result.get("recommendations", []), "本任务不需要行动建议。")}</section>
<section><h2>关键来源</h2>{''.join(source_cards) or '<p class="muted">尚无进入正文的关键来源。</p>'}</section>
<section><h2>附件</h2>{render_list(result.get("attachment_notes", []), "完整资料位于项目的 sources、evidence、analysis 与 attachments 目录。")}</section>
<footer>本报告只展示与研究目标直接相关的信息。完整采集材料、冲突证据和中间分析保存在本地项目附件中。</footer>
</main></body></html>"""


def build_markdown(project: dict[str, Any], result: dict[str, Any], claims: list[dict[str, Any]], sources: list[dict[str, Any]] | None = None) -> str:
    included = [claim for claim in claims if claim.get("included")]
    included.sort(key=lambda item: (item.get("importance", 0), item.get("relevance", 0)), reverse=True)
    lines = [
        f"# {result.get('title') or project.get('title')}",
        "",
        f"> {result.get('one_sentence_answer') or '研究尚未完成。'}",
        "",
        "## 执行摘要",
        "",
    ]
    lines.extend(f"- {item}" for item in result.get("executive_summary", []))
    lines.extend(["", "## 核心发现", ""])
    for claim in included:
        lines.append(f"- **{claim.get('text', '')}** `{claim.get('status', 'unknown')}` `{claim.get('confidence', 'unknown')}`")
        lines.append("  - 证据：" + ", ".join(claim.get("evidence", [])))
        if claim.get("opposing_evidence"):
            lines.append("  - 相反证据：" + ", ".join(claim["opposing_evidence"]))
        for sid, quote in claim.get("quotes", {}).items():
            lines.append(f"  - {sid} 原文：{quote}")
    lines.extend(["", "## 不确定性与资料缺口", ""])
    lines.extend(f"- {item}" for item in result.get("uncertainties", []))
    lines.extend(["", "## 判断与建议", ""])
    lines.extend(f"- {item}" for item in result.get("recommendations", []))
    lines.extend(["", "## 来源索引", ""])
    for source in sources or []:
        lines.append(f"- {source['id']} — {source['title']} — {source['uri']} — 发布：{source.get('published_at') or '未知'}；采集：{source['retrieved_at']}")
    lines.extend(["", "结构校验不等于事实核实。研究者摘要需人工复核。"])
    return "\n".join(lines).rstrip() + "\n"


def render_project(project_dir: Path) -> dict[str, Any]:
    project = read_json(project_dir / "project.json")
    result = read_json(project_dir / "analysis" / "result.json")
    sources = read_jsonl(project_dir / "evidence" / "sources.jsonl")
    claims = read_jsonl(project_dir / "evidence" / "claims.jsonl")
    validation = validate_research(sources, claims, project_dir)
    if not validation["valid"]:
        raise ValueError(json.dumps(validation, ensure_ascii=False, indent=2))
    result = dict(result)
    result["uncertainties"] = list(result.get("uncertainties", []))
    for gap in read_jsonl(project_dir / "evidence" / "gaps.jsonl"):
        result["uncertainties"].append(f"采集失败（历史记录）：{gap['location']} — {gap['error']}")
    for issue in validation["issues"]:
        if issue["level"] == "warning":
            result["uncertainties"].append(f"{issue.get('record_id')}: {issue['message']}")
    html_output = build_html(project, result, sources, claims)
    markdown_output = build_markdown(project, result, claims, sources)
    (project_dir / "report.html").write_text(html_output, encoding="utf-8", newline="\n")
    (project_dir / "report.md").write_text(markdown_output, encoding="utf-8", newline="\n")
    return validation

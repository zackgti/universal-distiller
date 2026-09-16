"""Explicit URL / file collection. Never executes scripts or collected instructions."""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .io_utils import ensure_within, read_jsonl, utc_now, write_jsonl

MAX_BYTES = 5 * 1024 * 1024


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.title = []
        self.hidden = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden.append(tag)
        if tag == "title":
            self.in_title = True
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "li", "h1", "h2", "h3", "tr", "article"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_title:
            self.title.append(data)
        else:
            self.parts.append(data)

    def text(self):
        return "\n".join(line for part in "".join(self.parts).splitlines()
                         if (line := re.sub(r"\s+", " ", part).strip()))


def normalize(raw: bytes, kind: str, charset: str = "utf-8") -> tuple[str, str]:
    text = raw.decode(charset, errors="replace").lstrip("\ufeff")
    if kind == "html":
        parser = PageText()
        parser.feed(text)
        return parser.text(), "".join(parser.title).strip()
    return text.replace("\r\n", "\n").strip(), ""


def web_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use an HTTP(S) URL without embedded credentials")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def collect(project: Path, location: str, *, local: bool = False,
            title: str = "", tier: str = "unknown", publisher: str = "",
            group: str = "", published_at: str = "") -> dict:
    if local:
        path = Path(location).resolve(strict=True)
        if path.suffix.lower() not in {".txt", ".md", ".html", ".htm", ".csv", ".json"}:
            raise ValueError("Supported local formats: UTF-8 txt, md, html, csv, json")
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Source exceeds 5 MiB limit")
        raw = path.read_bytes()
        kind = "html" if path.suffix.lower() in {".html", ".htm"} else "text"
        charset, uri, final_uri = "utf-8", path.as_uri(), path.as_uri()
        default_title = path.name
    else:
        uri = web_url(location)
        req = Request(uri, headers={"User-Agent": "UniversalDistiller/0.1 (+local research tool)",
                                    "Accept": "text/html,text/plain,application/json"})
        with urlopen(req, timeout=20) as response:
            final_uri = web_url(response.geturl())
            mime = response.headers.get_content_type()
            if mime not in {"text/html", "application/xhtml+xml", "text/plain", "text/markdown", "application/json"}:
                raise ValueError(f"Unsupported content type: {mime}")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Source exceeds 5 MiB limit")
            kind = "html" if "html" in mime else "text"
            charset = response.headers.get_content_charset() or "utf-8"
        default_title = urlsplit(final_uri).hostname
    text, detected_title = normalize(raw, kind, charset)
    if not text:
        raise ValueError("No readable text; page may require JavaScript or login")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    raw_hash = hashlib.sha256(raw).hexdigest()
    sources_file = project / "evidence" / "sources.jsonl"
    sources = read_jsonl(sources_file)
    existing = next((s for s in sources if s.get("uri") == uri and s.get("content_sha256") == digest), None)
    if existing:
        return {"source": existing, "duplicate": True}
    source_id = "s-" + hashlib.sha256((uri + digest).encode()).hexdigest()[:16]
    raw_rel = f"sources/raw/{raw_hash}.bin"
    normalized_rel = f"sources/normalized/{digest}.txt"
    for rel, data in ((raw_rel, raw), (normalized_rel, text.encode("utf-8"))):
        destination = ensure_within(project, project / rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(data)
    record = {"id": source_id, "title": title or detected_title or default_title,
              "uri": uri, "final_uri": final_uri, "kind": "local" if local else "web",
              "publisher": publisher, "independence_group": group,
              "published_at": published_at, "retrieved_at": utc_now(), "tier": tier,
              "excerpt": text[:1200], "content_sha256": digest,
              "raw_sha256": raw_hash, "raw_path": raw_rel, "text_path": normalized_rel}
    sources.append(record)
    write_jsonl(sources_file, sources)
    return {"source": record, "duplicate": False}


def record_gap(project: Path, location: str, error: Exception) -> None:
    path = project / "evidence" / "gaps.jsonl"
    records = read_jsonl(path)
    records.append({"location": location, "attempted_at": utc_now(), "error": str(error)})
    write_jsonl(path, records)


def add_claim(project: Path, claim: dict) -> None:
    from .models import validate_research
    sources = read_jsonl(project / "evidence" / "sources.jsonl")
    path = project / "evidence" / "claims.jsonl"
    claims = read_jsonl(path)
    if any(c.get("id") == claim.get("id") for c in claims):
        raise ValueError("Claim ID already exists; edit the JSONL record to revise it")
    result = validate_research(sources, claims + [claim], project)
    if not result["valid"]:
        raise ValueError(json.dumps(result, ensure_ascii=False, indent=2))
    write_jsonl(path, claims + [claim])

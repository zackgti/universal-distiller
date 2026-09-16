from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path
from datetime import datetime
from .io_utils import ensure_within, sha256_file


SOURCE_TIERS = {"primary", "authoritative", "reliable", "context", "unknown"}
CLAIM_TYPES = {"fact", "viewpoint", "inference", "forecast"}
CLAIM_STATUSES = {"supported", "single-source", "conflicted", "unsupported"}
CONFIDENCE_LEVELS = {"high", "medium", "low", "unknown"}


@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str
    record_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "record_id": self.record_id,
        }


def _required(record: dict[str, Any], names: tuple[str, ...], kind: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id", "")) or None
    for name in names:
        if name not in record or record[name] in (None, "", []):
            issues.append(
                ValidationIssue("error", f"{kind}.missing.{name}", f"Missing required field: {name}", record_id)
            )
    return issues


def validate_source(source: dict[str, Any]) -> list[ValidationIssue]:
    issues = _required(source, ("id", "title", "uri", "kind", "retrieved_at", "tier"), "source")
    tier = source.get("tier")
    if tier and tier not in SOURCE_TIERS:
        issues.append(ValidationIssue("error", "source.invalid.tier", f"Invalid source tier: {tier}", source.get("id")))
    if source.get("uri", "").lower().startswith(("javascript:", "data:")):
        issues.append(ValidationIssue("error", "source.unsafe.uri", "Unsafe source URI scheme", source.get("id")))
    if not source.get("excerpt"):
        issues.append(ValidationIssue("warning", "source.missing.excerpt", "Source has no preserved excerpt", source.get("id")))
    return issues


def validate_claim(claim: dict[str, Any], sources: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
    issues = _required(
        claim,
        ("id", "text", "type", "importance", "relevance", "confidence", "status", "evidence"),
        "claim",
    )
    claim_id = claim.get("id")
    if claim.get("type") and claim["type"] not in CLAIM_TYPES:
        issues.append(ValidationIssue("error", "claim.invalid.type", f"Invalid claim type: {claim['type']}", claim_id))
    if claim.get("status") and claim["status"] not in CLAIM_STATUSES:
        issues.append(
            ValidationIssue("error", "claim.invalid.status", f"Invalid claim status: {claim['status']}", claim_id)
        )
    if claim.get("confidence") and claim["confidence"] not in CONFIDENCE_LEVELS:
        issues.append(
            ValidationIssue("error", "claim.invalid.confidence", f"Invalid confidence: {claim['confidence']}", claim_id)
        )
    for field in ("importance", "relevance"):
        value = claim.get(field)
        if value is not None and (not isinstance(value, int) or value < 1 or value > 5):
            issues.append(
                ValidationIssue("error", f"claim.invalid.{field}", f"{field} must be an integer from 1 to 5", claim_id)
            )

    evidence_ids = claim.get("evidence", [])
    evidence_sources = [sources[source_id] for source_id in evidence_ids if source_id in sources]
    missing = [source_id for source_id in evidence_ids if source_id not in sources]
    if missing:
        issues.append(
            ValidationIssue("error", "claim.missing.sources", f"Unknown evidence source IDs: {', '.join(missing)}", claim_id)
        )

    if claim.get("type") == "fact" and claim.get("status") == "supported":
        has_primary = any(source.get("tier") == "primary" for source in evidence_sources)
        independent_groups = {
            source.get("independence_group")
            for source in evidence_sources
            if source.get("tier") in {"primary", "authoritative", "reliable"} and source.get("independence_group")
        }
        distinct_documents = {
            source.get("content_sha256") or source.get("uri")
            for source in evidence_sources
            if source.get("tier") in {"primary", "authoritative", "reliable"}
            and source.get("independence_group")
        }
        if not has_primary and (len(independent_groups) < 2 or len(distinct_documents) < 2):
            issues.append(
                ValidationIssue(
                    "error",
                    "claim.insufficient.support",
                    "Supported fact requires one primary source or two independent reliable sources",
                    claim_id,
                )
            )

    if claim.get("included") and claim.get("status") == "unsupported":
        issues.append(
            ValidationIssue("error", "claim.unsupported.included", "Unsupported claim cannot enter the report", claim_id)
        )
    if claim.get("status") == "conflicted" and not claim.get("opposing_evidence"):
        issues.append(
            ValidationIssue("warning", "claim.conflict.missing", "Conflicted claim lacks opposing evidence", claim_id)
        )
    return issues


def validate_research(sources: list[dict[str, Any]], claims: list[dict[str, Any]], project: Path | None = None) -> dict[str, Any]:
    issues: list[ValidationIssue] = []
    # Reject malformed shapes before set/dictionary operations or sorting.
    for kind, records in (("source", sources), ("claim", claims)):
        for record in records:
            required_strings = ("id", "title", "uri", "kind", "retrieved_at", "tier") if kind == "source" else ("id", "text", "type", "confidence", "status")
            if not isinstance(record, dict) or any(not isinstance(record.get(k), str) or not record[k].strip() for k in required_strings):
                issues.append(ValidationIssue("error", f"{kind}.invalid.shape", "Required string fields must be nonempty"))
                continue
            if kind == "claim":
                for key in ("evidence", "opposing_evidence"):
                    value = record.get(key, [])
                    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                        issues.append(ValidationIssue("error", "claim.invalid.references", "Evidence must be a list of source IDs", record["id"]))
                if any(type(record.get(k)) is not int or not 1 <= record[k] <= 5 for k in ("importance", "relevance")):
                    issues.append(ValidationIssue("error", "claim.invalid.score", "Scores must be integers from 1 to 5", record["id"]))
                if "included" in record and type(record["included"]) is not bool:
                    issues.append(ValidationIssue("error", "claim.invalid.included", "included must be a boolean", record["id"]))
                quotes = record.get("quotes", {})
                if not isinstance(quotes, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() for k, v in quotes.items()):
                    issues.append(ValidationIssue("error", "claim.invalid.quotes", "quotes must map source IDs to nonempty excerpts", record["id"]))
    if issues:
        return {"valid": False, "summary": {"sources": len(sources), "claims": len(claims), "errors": len(issues), "warnings": 0}, "issues": [i.as_dict() for i in issues]}
    source_index: dict[str, dict[str, Any]] = {}
    seen_source_ids: set[str] = set()
    for source in sources:
        issues.extend(validate_source(source))
        for key in ("retrieved_at", "published_at"):
            if source.get(key):
                try:
                    datetime.fromisoformat(source[key].replace("Z", "+00:00"))
                except (TypeError, ValueError, AttributeError):
                    issues.append(ValidationIssue("error", "source.invalid.date", f"Invalid ISO date: {key}", source["id"]))
        if project and source.get("text_path"):
            try:
                for path_key, hash_key in (("text_path", "content_sha256"), ("raw_path", "raw_sha256")):
                    artifact = ensure_within(project, project / source[path_key])
                    if not artifact.is_file() or sha256_file(artifact) != source.get(hash_key):
                        raise ValueError("Missing or modified archive")
            except (ValueError, KeyError, TypeError, OSError) as exc:
                issues.append(ValidationIssue("error", "source.archive.invalid", str(exc), source["id"]))
        source_id = source.get("id")
        if source_id in seen_source_ids:
            issues.append(ValidationIssue("error", "source.duplicate.id", "Duplicate source ID", source_id))
        if source_id:
            source_index[source_id] = source
            seen_source_ids.add(source_id)

    seen_claim_ids: set[str] = set()
    for claim in claims:
        issues.extend(validate_claim(claim, source_index))
        opposing = claim.get("opposing_evidence", [])
        for sid in opposing:
            if sid not in source_index:
                issues.append(ValidationIssue("error", "claim.opposing.missing", "Unknown opposing source", claim["id"]))
        if claim.get("included") and claim.get("status") == "conflicted" and not opposing:
            issues.append(ValidationIssue("error", "claim.conflict.empty", "Included conflict must show opposing sources", claim["id"]))
        for sid in claim.get("evidence", []) + opposing:
            source = source_index.get(sid)
            if not source:
                continue
            quote = claim.get("quotes", {}).get(sid)
            if project and source.get("text_path"):
                try:
                    text = ensure_within(project, project / source["text_path"]).read_text(encoding="utf-8")
                    if not quote or quote not in text:
                        issues.append(ValidationIssue("error", "claim.quote.mismatch", "Each archived source needs an exact quote in quotes[source_id]", claim["id"]))
                except (ValueError, OSError, TypeError):
                    pass  # Archive errors are already reported above.
            elif not quote:
                issues.append(ValidationIssue("warning", "claim.quote.missing", "Legacy source has no claim-specific quote", claim["id"]))
        claim_id = claim.get("id")
        if claim_id in seen_claim_ids:
            issues.append(ValidationIssue("error", "claim.duplicate.id", "Duplicate claim ID", claim_id))
        if claim_id:
            seen_claim_ids.add(claim_id)

    core_claims = [claim for claim in claims if claim.get("importance", 0) >= 4]
    resolved_core = [
        claim for claim in core_claims if claim.get("status") in {"supported", "single-source", "conflicted"}
    ]
    coverage = len(resolved_core) / len(core_claims) if core_claims else 0.0
    errors = [issue for issue in issues if issue.level == "error"]
    warnings = [issue for issue in issues if issue.level == "warning"]
    return {
        "valid": not errors,
        "summary": {
            "sources": len(sources),
            "claims": len(claims),
            "core_claims": len(core_claims),
            "core_coverage": round(coverage, 4),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "issues": [issue.as_dict() for issue in issues],
    }

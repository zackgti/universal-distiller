from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


CORE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(CORE))

from ud_core.io_utils import read_json, safe_slug, write_json, write_jsonl  # noqa: E402
from ud_core.models import validate_research  # noqa: E402
from ud_core.project import compare_manifests, initialize_project, project_manifest, snapshot_project  # noqa: E402
from ud_core.report import render_project  # noqa: E402


def source(source_id: str, tier: str, group: str) -> dict:
    return {
        "id": source_id,
        "title": f"Source {source_id}",
        "uri": f"https://example.com/{source_id}",
        "kind": "web",
        "publisher": group,
        "published_at": "2026-07-01",
        "retrieved_at": "2026-07-29T00:00:00+00:00",
        "tier": tier,
        "independence_group": group,
        "excerpt": "A preserved excerpt.",
    }


class UniversalDistillerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".universal-distiller-root").write_text("test", encoding="utf-8")
        self.project = initialize_project(self.root, "测试 项目", "验证研究系统")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_safe_slug(self) -> None:
        self.assertEqual(safe_slug("  AI 研究 / 2026  "), "ai-研究-2026")
        with self.assertRaises(ValueError):
            safe_slug("///")

    def test_primary_source_supports_fact(self) -> None:
        sources = [source("s1", "primary", "origin")]
        claims = [
            {
                "id": "c1",
                "text": "Verified fact",
                "type": "fact",
                "importance": 5,
                "relevance": 5,
                "confidence": "high",
                "status": "supported",
                "evidence": ["s1"],
                "included": True,
            }
        ]
        self.assertTrue(validate_research(sources, claims)["valid"])

    def test_single_secondary_cannot_be_supported_fact(self) -> None:
        sources = [source("s1", "reliable", "one")]
        claims = [
            {
                "id": "c1",
                "text": "Under-supported fact",
                "type": "fact",
                "importance": 5,
                "relevance": 5,
                "confidence": "medium",
                "status": "supported",
                "evidence": ["s1"],
                "included": True,
            }
        ]
        result = validate_research(sources, claims)
        self.assertFalse(result["valid"])
        self.assertIn("claim.insufficient.support", {item["code"] for item in result["issues"]})

    def test_two_independent_reliable_sources_support_fact(self) -> None:
        sources = [source("s1", "reliable", "one"), source("s2", "authoritative", "two")]
        claims = [
            {
                "id": "c1",
                "text": "Corroborated fact",
                "type": "fact",
                "importance": 4,
                "relevance": 5,
                "confidence": "high",
                "status": "supported",
                "evidence": ["s1", "s2"],
                "included": True,
            }
        ]
        self.assertTrue(validate_research(sources, claims)["valid"])

    def test_render_is_offline_and_escaped(self) -> None:
        sources = [source("s1", "primary", "origin")]
        claims = [
            {
                "id": "c1",
                "text": "<script>alert(1)</script>",
                "type": "fact",
                "importance": 5,
                "relevance": 5,
                "confidence": "high",
                "status": "supported",
                "evidence": ["s1"],
                "included": True,
            }
        ]
        write_jsonl(self.project / "evidence" / "sources.jsonl", sources)
        write_jsonl(self.project / "evidence" / "claims.jsonl", claims)
        result_path = self.project / "analysis" / "result.json"
        result = read_json(result_path)
        result.update(
            {
                "one_sentence_answer": "测试通过",
                "executive_summary": ["只显示重点"],
                "uncertainties": [],
                "recommendations": [],
            }
        )
        write_json(result_path, result)
        render_project(self.project)
        output = (self.project / "report.html").read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", output)
        self.assertNotIn("<script src=", output)
        self.assertNotIn("cdn.", output.lower())
        self.assertNotIn("analytics", output.lower())

    def test_snapshot_and_diff(self) -> None:
        before = project_manifest(self.project)
        snapshot = snapshot_project(self.project)
        self.assertTrue((snapshot / "manifest.json").exists())
        result = read_json(self.project / "analysis" / "result.json")
        result["one_sentence_answer"] = "changed"
        write_json(self.project / "analysis" / "result.json", result)
        after = project_manifest(self.project)
        changes = compare_manifests(before, after)
        self.assertTrue(changes["has_changes"])
        self.assertIn("analysis/result.json", changes["changed"])


if __name__ == "__main__":
    unittest.main()

import json
import sys
import tempfile
import unittest
from io import BytesIO
from email.message import Message
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ud_core.collect import collect, add_claim, normalize, web_url
from ud_core.io_utils import read_jsonl, write_jsonl
from ud_core.project import initialize_project, snapshot_project
from ud_core.models import validate_research
from ud_core.report import render_project
from ud_core.cli import main


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".universal-distiller-root").touch()
        self.project = initialize_project(self.root, "test", "test")
        self.file = self.root / "source.txt"
        self.file.write_text("A preserved fact. 中文资料。", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def source(self):
        return collect(self.project, str(self.file), local=True, tier="primary")["source"]

    def claim(self, sid):
        return {"id": "c1", "text": "A fact", "type": "fact", "status": "supported",
                "confidence": "high", "importance": 5, "relevance": 5, "included": True,
                "evidence": [sid], "quotes": {sid: "A preserved fact."}}

    def test_duplicate_and_distinct_provenance(self):
        first = self.source()
        self.assertTrue(collect(self.project, str(self.file), local=True)["duplicate"])
        other = self.root / "other.txt"
        other.write_bytes(self.file.read_bytes())
        second = collect(self.project, str(other), local=True)["source"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["text_path"], second["text_path"])
        self.assertEqual(len(read_jsonl(self.project / "evidence/sources.jsonl")), 2)

    def test_html_excludes_executable_content(self):
        text, title = normalize(b"<title>T</title><p>Hi</p><script>evil()</script><style>bad</style><p>Bye</p>", "html")
        self.assertEqual(title, "T")
        self.assertEqual(text, "Hi\nBye")

    def test_exact_quote_required_and_archive_tampering_detected(self):
        source = self.source()
        claim = self.claim(source["id"])
        add_claim(self.project, claim)
        render_project(self.project)
        claim["id"] = "c2"
        claim["quotes"][source["id"]] = "Invented quote"
        with self.assertRaises(ValueError):
            add_claim(self.project, claim)
        (self.project / source["text_path"]).write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            render_project(self.project)

    def test_missing_independence_is_not_two_sources(self):
        first = self.source()
        first["tier"] = "reliable"
        second = dict(first, id="s2")
        claim = self.claim(first["id"])
        claim["evidence"].append("s2")
        self.assertFalse(validate_research([first, second], [claim])["valid"])

    def test_identical_text_is_not_independent_corroboration(self):
        first = self.source()
        first.update(tier="reliable", independence_group="one")
        second = dict(first, id="s2", uri="https://example.org/reprint", independence_group="two")
        claim = self.claim(first["id"])
        claim["evidence"].append("s2")
        self.assertFalse(validate_research([first, second], [claim])["valid"])

    def test_empty_research_has_no_coverage(self):
        self.assertEqual(validate_research([], [])["summary"]["core_coverage"], 0.0)

    def test_conflict_references_in_both_formats(self):
        first = self.source()
        second = dict(first, id="s2", title="Opposing source")
        write_jsonl(self.project / "evidence/sources.jsonl", [first, second])
        claim = self.claim(first["id"])
        claim.update(status="conflicted", opposing_evidence=["s2"])
        claim["quotes"]["s2"] = "中文资料。"
        add_claim(self.project, claim)
        render_project(self.project)
        for name in ("report.md", "report.html"):
            output = (self.project / name).read_text(encoding="utf-8")
            self.assertIn("相反证据", output)
            self.assertIn("Opposing source", output)

    def test_malformed_records_are_validation_errors(self):
        for claim in ({"id": []}, {**self.claim("s1"), "evidence": "s1"}, {**self.claim("s1"), "importance": True}):
            self.assertFalse(validate_research([], [claim])["valid"])

    def test_missing_url_is_recorded_as_gap(self):
        with patch("ud_core.collect.urlopen", side_effect=OSError("network unavailable")):
            code = main(["collect", "--project", str(self.project), "--url", "https://example.org/"])
        self.assertEqual(code, 1)
        self.assertEqual(len(read_jsonl(self.project / "evidence/gaps.jsonl")), 1)
        render_project(self.project)
        self.assertIn("network unavailable", (self.project / "report.html").read_text(encoding="utf-8"))

    def test_http_response_and_final_url(self):
        class Response(BytesIO):
            headers = Message()
            headers["Content-Type"] = "text/html; charset=utf-8"
            def geturl(self):
                return "https://example.org/final"
        with patch("ud_core.collect.urlopen", return_value=Response(b"<p>hello</p>")):
            result = collect(self.project, "https://example.org/start")
        self.assertEqual(result["source"]["final_uri"], "https://example.org/final")
        self.assertEqual(result["source"]["tier"], "unknown")

    def test_scheme_credentials_and_path_escape(self):
        for url in ("file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.org/"):
            with self.assertRaises(ValueError):
                web_url(url)
        source = self.source()
        source["text_path"] = "../../outside.txt"
        self.assertFalse(validate_research([source], [], self.project)["valid"])

    def test_snapshots_do_not_collide(self):
        self.assertNotEqual(snapshot_project(self.project), snapshot_project(self.project))


if __name__ == "__main__":
    unittest.main()

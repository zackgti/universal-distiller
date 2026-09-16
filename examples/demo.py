"""Offline, synthetic end-to-end example; no API key or network required."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ud_core.cli import main
from ud_core.collect import collect, add_claim
from ud_core.io_utils import read_json, write_json
from ud_core.project import initialize_project
from ud_core.report import render_project

parser = argparse.ArgumentParser()
parser.add_argument("--root", default="workspace/demo")
args = parser.parse_args()
root = Path(args.root).resolve()
root.mkdir(parents=True, exist_ok=True)
(root / ".universal-distiller-root").touch()
project = initialize_project(root, "示例-图书馆开放时间", "虚构演示：周六何时闭馆？")
here = Path(__file__).resolve().parent
a = collect(project, str(here / "source-a.html"), local=True, tier="primary", publisher="虚构图书馆", group="library", published_at="2026-09-01")["source"]["id"]
b = collect(project, str(here / "source-b.txt"), local=True, tier="reliable", publisher="虚构社区", group="community", published_at="2026-08-01")["source"]["id"]
add_claim(project, {"id": "c1", "text": "新公告与旧通知的周六闭馆时间不同，使用前应向图书馆确认。",
    "type": "fact", "status": "conflicted", "confidence": "medium", "importance": 5, "relevance": 5,
    "included": True, "evidence": [a], "opposing_evidence": [b],
    "quotes": {a: "青禾图书馆将在周六开放至晚上八点。", b: "青禾图书馆周六在下午六点闭馆。"}})
result = read_json(project / "analysis/result.json")
result.update({"one_sentence_answer": "虚构演示：两份资料存在时间冲突，新公告还限定了试运行月份。",
    "executive_summary": ["本示例演示采集、原文引用、冲突保留及离线报告，不代表真实事件。"],
    "uncertainties": ["实际开放安排未核实；所有源材料为项目原创的虚构测试资料。"],
    "recommendations": ["真实研究中应补充最新的一手确认。"]})
write_json(project / "analysis/result.json", result)
render_project(project)
print(project / "report.html")

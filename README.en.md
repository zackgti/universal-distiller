# Universal Distiller

[中文说明](README.md)

A local-first research evidence toolkit. Collect explicit webpages or UTF-8 files,
preserve raw and normalized content, attach exact quotations to reviewed claims,
retain conflicting evidence, and export offline HTML and Markdown reports.

Python 3.10+, no runtime dependencies, no API key required.

```sh
python -m pip install .
python examples/demo.py
```

The demo prints a local HTML report path. Its two source documents are original,
synthetic fixtures illustrating a disagreement about library opening hours.
To repeat it, choose a new directory: `python examples/demo.py --root workspace/demo2`.

## Research workflow

```sh
ud init --root workspace/research --title my-topic --goal "Your research question"
ud collect --project workspace/research/projects/my-topic --url https://example.com
ud collect --project workspace/research/projects/my-topic --file notes.txt
ud claim --project workspace/research/projects/my-topic --file claim.json
ud validate --project workspace/research/projects/my-topic
ud render --project workspace/research/projects/my-topic
```

Collection prints source IDs. Read their saved text and prepare a claim:

```json
{
  "id": "c1",
  "text": "Your reviewed conclusion",
  "type": "fact",
  "status": "single-source",
  "confidence": "medium",
  "importance": 5,
  "relevance": 5,
  "included": true,
  "evidence": ["s-replace-with-actual-id"],
  "quotes": {"s-replace-with-actual-id": "Exact quotation from saved text"}
}
```

Sources default to `unknown`. Annotate source quality explicitly; downloading a
page does not make it authoritative. A supported fact needs a primary source or
two reliable independent origins. Identical archived text cannot count as two
independent supporting documents. Researchers still assess actual independence
and whether quotations support the claim.

Conflicted claims use `opposing_evidence` and quotations for both sides.
Unsupported claims cannot enter a report. Missing or modified archives and
non-matching quotations fail validation. Collection failures remain visible in
the report as historical gaps. **Validation is not automatic fact-checking.**

Edit `analysis/result.json` for the researcher-written summary and uncertainties.
Use `ud snapshot --project PATH` before updating, then `ud diff --project PATH
--snapshot SNAPSHOT_PATH` to compare file hashes.

## Scope and limitations

This experimental CLI performs collection and deterministic evidence checks.
Search discovery, semantic synthesis and factual review are done by a human or
their assistant. It does not call a model, automate search, render JavaScript,
import PDF/OCR, or bypass login/paywalls. HTML extraction can retain navigation
noise. Local text must be UTF-8; each source is limited to 5 MiB.

Use only as a trusted local CLI; do not expose arbitrary URL collection through
a public service. URL redirects and system proxy settings apply. Archives can
contain private paths or copyrighted text; inspect before sharing. One writer
per research project. The report UI is currently Chinese.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [contribution guide](CONTRIBUTING.md) and [provenance](docs/PROVENANCE.md).
MIT-licensed code and synthetic fixtures; collected third-party material retains
its original rights. This project is not affiliated with or sponsored by OpenAI.

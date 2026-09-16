# v0.1 design

The user approved extending the existing research skills into a usable open-source
tool. This implementation builds on the local Universal Distiller prototype.

Choices considered: prompt-only skill (easy distribution, no deterministic data
checks); local Python CLI (chosen: portable, testable, no account or API costs);
hosted application (more operational overhead, deferred).

Flow: research question → explicit URLs/local UTF-8 text → archived raw bytes and
normalized text → source records → reviewed claims with exact excerpts → evidence
checks → Markdown and offline HTML. Discovery and semantic synthesis remain with
the researcher or their assistant; this CLI does not pretend to verify truth.

Modules: collection, evidence validation, project history, rendering, CLI.
Content hashes deduplicate stored material, but distinct source URLs retain separate
provenance. Publication dates and source independence are explicit annotations.
Failures are recorded as collection gaps. A source is not primary merely because
it was successfully downloaded. Opposing evidence must remain visible.

Acceptance: installable package; no runtime dependencies; deterministic offline
example; URL/local input; deduplication; exact quotation validation; unsupported
claims blocked; report citations; missing evidence visible; network errors recorded;
snapshot and diff; CI on Windows and Linux. No external publishing in the build step.

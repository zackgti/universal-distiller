# Contributing

Use Python 3.10+. Install with `python -m pip install -e .`, then run
`python -m unittest discover -s tests -v` and `python examples/demo.py --root workspace/check`.

Bug reports should include the command, Python/OS version, expected behavior,
and a small synthetic fixture. Remove private sources, tokens and personal paths.
Keep collection, validation and reporting separate. Add regression tests for
evidence loss, citation errors, extraction failures or misleading verification.
Do not add real user archives to fixtures. Propose dependencies before adding them.

Useful next contributions: extraction quality fixtures, citations to paragraphs,
PDF import, human-reviewed stale-source reminders, and explicit search adapters.

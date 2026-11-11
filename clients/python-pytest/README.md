# pytest-prism

A pytest plugin that captures per-test artifacts and per-run context, then uploads them to a [Prism](https://github.com/analogdevicesinc/prism) instance.

The plugin itself is generic — it ships no domain knowledge. Consumers register **renderers** (turn a test payload into displayable artifacts) and **session hooks** (capture run-level context) via setuptools entry points.

## Quickstart

```bash
pip install pytest-prism
pytest --prism-report --prism-out=./out
```

See `docs/extending.md` for the renderer/hook authoring guide.

Enabled reporting saves the terminal transcript and per-test stdout, stderr,
and logging for setup, call, and teardown, including passing tests and xdist
workers. Session metadata includes GitHub Actions context and the labgrid
session hook's hardware provenance and dmesg collection errors. The upload
retains case ownership through the archive manifest, including duplicate test
names across modules.

Set `PRISM_CI_MATRIX` to matrix JSON and `PRISM_CI_JOB_URL` to an explicit job
URL when available. `PRISM_CI_JSON` accepts a JSON object or file for other CI
providers.

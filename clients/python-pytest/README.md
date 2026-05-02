# pytest-prism

A pytest plugin that captures per-test artifacts and per-run context, then uploads them to a [Prism](https://github.com/analogdevicesinc/prism) instance.

The plugin itself is generic — it ships no domain knowledge. Consumers register **renderers** (turn a test payload into displayable artifacts) and **session hooks** (capture run-level context) via setuptools entry points.

## Quickstart

```bash
pip install pytest-prism
pytest --prism-report --prism-out=./out
```

See `docs/extending.md` for the renderer/hook authoring guide.

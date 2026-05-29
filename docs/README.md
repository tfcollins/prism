# Prism documentation

Sphinx site using Analog Devices' [`adi-doctools`](https://github.com/analogdevicesinc/doctools)
"cosmic" theme (the same theme as [pyadi-iio](https://analogdevicesinc.github.io/pyadi-iio/)).
Content is organised along the [Diátaxis](https://diataxis.fr/) framework:

```text
source/
  tutorials/    learning-oriented   — start here
  how-to/       task-oriented       — recipes
  reference/    information-oriented — API, data model, conventions
  explanation/  understanding       — architecture, design
  _static/      logos, custom CSS, screenshots
```

## Build

From the repo root:

```bash
make docs         # live-reloading preview on http://localhost:8000
make docs-build   # one-shot strict build into docs/build/html
make lint-docs    # strict build used as the docs linter (warnings = errors)
```

These bootstrap an isolated `docs/.venv` from `requirements.txt`. To build by
hand:

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/sphinx-build -b html -W docs/source docs/build/html
```

## Screenshots

The UI screenshots under `source/_static/img/screenshots/` are committed so the
docs build without a running app. To regenerate them, bring up and seed the
stack (see `source/tutorials/getting-started.md`), then:

```bash
make docs-shots   # logs in, walks the UI, rewrites the PNGs
```

The capture script is `shots.py`; logos are generated from `assets/logo.svg`
into `source/_static/logos/`.
